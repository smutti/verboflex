"""Read-only preparation and fresh revalidation of immutable write-back bytes.

This proof is source-bound, not lasting permission to mutate a repository.
Callers must revalidate immediately before sending and separately verify their
chosen target branch and its original file bytes. No target is chosen here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field, fields, is_dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from verboflex.integrations.bitbucket.client import (
    BitbucketBranch,
    BitbucketProviderReadError,
    BitbucketSourceMetadata,
)
from verboflex.localization.importing.core import (
    MAX_CANONICAL_AGGREGATE_BYTES,
    MAX_CANONICAL_FILE_BYTES,
    MAX_CANONICAL_FILES,
    MAX_CANONICAL_MAPPING_OUTPUT_BYTES,
    MAX_CANONICAL_VALUES,
    canonical_selector_bytes,
)
from verboflex.localization.writing.core import (
    RenderedFile,
    SourceFileSnapshot,
    WritebackReason,
    WritebackRejected,
    WriteOperation,
)
from verboflex.localization.writing.registry import render_file
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.services.bitbucket_oauth import TOKEN_RENEWAL_SKEW_SECONDS
from verboflex.services.writeback_authority import (
    CapturedFile,
    CapturedSourceSide,
    CapturedWritebackAuthority,
    build_source_file_snapshot,
    capture_writeback_authority,
    require_source_file_metadata,
)
from verboflex.services.writeback_authority import (
    ProposalSelection as ProposalSelection,
)
from verboflex.services.writeback_authority import (
    WritebackSelection as WritebackSelection,
)


class WritebackReadAdapter(Protocol):
    async def resolve_repository_branch(
        self, session: Session, *, workspace: str, repository_slug: str, branch: str
    ) -> BitbucketBranch: ...

    async def read_repository_source_metadata(
        self, session: Session, *, workspace: str, repository_slug: str, commit_hash: str, path: str
    ) -> BitbucketSourceMetadata: ...

    async def read_repository_source_file(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        commit_hash: str,
        path: str,
        max_bytes: int,
    ) -> bytes: ...


@dataclass(frozen=True, slots=True)
class PreparedWriteback:
    selection: WritebackSelection
    authority: CapturedWritebackAuthority = field(repr=False)
    files: tuple[RenderedFile, ...] = field(repr=False)
    manifest_digest: str
    manifest_version: int = 1


def _stale() -> WritebackRejected:
    return WritebackRejected(WritebackReason.STALE_BASIS)


def _selection(selection: WritebackSelection) -> WritebackSelection:
    if type(selection) is not WritebackSelection:
        raise _stale()
    # Reconstruct to validate even an externally deserialized/fabricated object.
    normalized = WritebackSelection(selection.actor_id, selection.proposals)
    if len(normalized.proposals) > MAX_CANONICAL_VALUES:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    return replace(
        normalized, proposals=tuple(sorted(normalized.proposals, key=lambda p: p.proposal_id))
    )


def _edit_identity(edit: WriteOperation) -> tuple[str, str, bytes]:
    return edit.logical_key, edit.language, canonical_selector_bytes(edit.selector)


def _normalize(authority: CapturedWritebackAuthority) -> CapturedWritebackAuthority:
    if type(authority) is not CapturedWritebackAuthority:
        raise _stale()
    return replace(
        authority,
        roles=tuple(sorted(authority.roles)),
        proposals=tuple(
            sorted(
                (
                    replace(
                        p,
                        members=tuple(sorted(p.members, key=lambda m: m.value_id)),
                        constraints=tuple(sorted(p.constraints, key=lambda r: r.rule_id)),
                    )
                    for p in authority.proposals
                ),
                key=lambda p: p.proposal_id,
            )
        ),
        mappings=tuple(
            sorted(
                (
                    replace(
                        m,
                        sides=tuple(
                            sorted(
                                m.sides,
                                key=lambda s: (
                                    s.repository_id,
                                    s.repository_side,
                                    s.configured_branch,
                                ),
                            )
                        ),
                        source_references=tuple(
                            sorted(m.source_references, key=lambda r: r.source_reference_position)
                        ),
                        allowed_targets=tuple(sorted(m.allowed_targets)),
                    )
                    for m in authority.mappings
                ),
                key=lambda m: m.mapping_id,
            )
        ),
        files=tuple(
            sorted(
                (
                    replace(f, edits=tuple(sorted(f.edits, key=_edit_identity)))
                    for f in authority.files
                ),
                key=lambda f: (f.authority.repository_id, f.authority.path, f.mapping_id),
            )
        ),
    )


def _capture_bounds(authority: CapturedWritebackAuthority) -> None:
    if type(authority) is not CapturedWritebackAuthority or any(
        type(items) is not tuple
        for items in (authority.proposals, authority.files, authority.mappings)
    ):
        raise _stale()
    if not authority.proposals or not authority.files or not authority.mappings:
        raise _stale()
    if (
        len(authority.proposals) > MAX_CANONICAL_VALUES
        or len(authority.files) > MAX_CANONICAL_FILES
        or len(authority.mappings) > MAX_CANONICAL_FILES
        or sum(len(p.members) for p in authority.proposals) > MAX_CANONICAL_VALUES
        or sum(len(f.edits) for f in authority.files) > MAX_CANONICAL_VALUES
        or sum(len(m.source_references) for m in authority.mappings) > MAX_CANONICAL_FILES
        or sum(len(m.sides) for m in authority.mappings) > MAX_CANONICAL_FILES * 2
        or sum(r.size_bytes for m in authority.mappings for r in m.source_references)
        > MAX_CANONICAL_AGGREGATE_BYTES
        or sum(f.authority.size_bytes for f in authority.files) > MAX_CANONICAL_AGGREGATE_BYTES
    ):
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    text_bytes = 0
    for proposal in authority.proposals:
        for member in proposal.members:
            text_bytes += len(member.edit.expected_text.encode("utf-8")) + len(
                member.edit.replacement_text.encode("utf-8")
            )
            if text_bytes > MAX_CANONICAL_AGGREGATE_BYTES:
                raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)


def _capture(
    factory: sessionmaker[Session], selection: WritebackSelection
) -> CapturedWritebackAuthority:
    with factory.begin() as session:
        captured = capture_writeback_authority(session, selection=selection)
        _capture_bounds(captured)
        return _normalize(captured)


def _renewal_due(session: Session) -> bool:
    expires = session.scalar(
        select(BitbucketConnection.provider_expires_at).where(BitbucketConnection.id == 1)
    )
    return expires is not None and expires <= datetime.now(UTC) + timedelta(
        seconds=TOKEN_RENEWAL_SKEW_SECONDS
    )


def _bootstrap_capture(
    factory: sessionmaker[Session], selection: WritebackSelection
) -> tuple[CapturedWritebackAuthority, bool]:
    # Only the ordinary credential lifecycle may run during the following first
    # head reads. No PreparedWriteback exists yet. Local/source authority is fully
    # checked here; the final capture must match every non-credential fact.
    with factory.begin() as session:
        captured = capture_writeback_authority(
            session, selection=selection, allow_expired_connection=True
        )
        _capture_bounds(captured)
        return _normalize(captured), _renewal_due(session)


def _chunks(value: object, *, depth: int = 0) -> Iterator[bytes]:
    """Versioned canonical JSON stream; bytes bind by SHA-256 and exact length."""
    if depth > 40:
        raise _stale()
    if is_dataclass(value) and not isinstance(value, type):
        yield b"{"
        for index, item in enumerate(sorted(fields(value), key=lambda f: f.name)):
            if index:
                yield b","
            yield json.dumps(item.name).encode()
            yield b":"
            yield from _chunks(getattr(value, item.name), depth=depth + 1)
        yield b"}"
    elif type(value) is tuple:
        yield b"["
        for index, item_value in enumerate(value):
            if index:
                yield b","
            yield from _chunks(item_value, depth=depth + 1)
        yield b"]"
    elif type(value) is bytes:
        yield (
            b'{"sha256":"'
            + hashlib.sha256(value).hexdigest().encode()
            + b'","size":'
            + str(len(value)).encode()
            + b"}"
        )
    elif type(value) is UUID:
        yield json.dumps(str(value)).encode()
    elif value is None or type(value) in (str, int, bool):
        try:
            yield json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except UnicodeEncodeError:
            raise _stale() from None
    else:
        raise _stale()


def _manifest_digest(prepared: PreparedWriteback) -> str:
    digest = hashlib.sha256()
    size = 0
    for chunk in _chunks(
        (
            "verboflex.writeback",
            prepared.manifest_version,
            prepared.selection,
            prepared.authority,
            prepared.files,
        )
    ):
        size += len(chunk)
        if size > MAX_CANONICAL_MAPPING_OUTPUT_BYTES:
            raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
        digest.update(chunk)
    return digest.hexdigest()


def _provider_failure(error: BitbucketProviderReadError, *, file: bool) -> WritebackRejected:
    if error.provider_status in {401, 403}:
        return WritebackRejected(WritebackReason.AUTHORITY_UNAVAILABLE)
    if error.kind == "limit_exceeded":
        return WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    if error.provider_status == 404:
        return WritebackRejected(
            WritebackReason.SOURCE_FILE_MISSING if file else WritebackReason.SOURCE_BRANCH_CHANGED
        )
    return WritebackRejected(WritebackReason.PROVIDER_UNAVAILABLE)


async def _check_heads(
    factory: sessionmaker[Session],
    authority: CapturedWritebackAuthority,
    adapter: WritebackReadAdapter,
) -> None:
    for mapping in authority.mappings:
        for side in mapping.sides:
            try:
                with factory() as session:
                    branch = await adapter.resolve_repository_branch(
                        session,
                        workspace=side.workspace,
                        repository_slug=side.repository_slug,
                        branch=side.configured_branch,
                    )
            except BitbucketProviderReadError as error:
                raise _provider_failure(error, file=False) from None
            if type(branch) is not BitbucketBranch or (branch.name, branch.commit_hash) != (
                side.configured_branch,
                side.commit_hash,
            ):
                raise WritebackRejected(WritebackReason.SOURCE_BRANCH_CHANGED)


def _side(authority: CapturedWritebackAuthority, file: CapturedFile) -> CapturedSourceSide:
    mappings = [m for m in authority.mappings if m.mapping_id == file.mapping_id]
    if len(mappings) != 1 or file.authority not in mappings[0].source_references:
        raise _stale()
    matching = [
        s
        for s in mappings[0].sides
        if (s.repository_id, s.repository_side, s.configured_branch, s.commit_hash)
        == (
            file.authority.repository_id,
            file.authority.repository_side,
            file.authority.configured_branch,
            file.authority.commit_hash,
        )
    ]
    if len(matching) != 1:
        raise _stale()
    return matching[0]


async def _snapshot(
    factory: sessionmaker[Session],
    file: CapturedFile,
    side: CapturedSourceSide,
    adapter: WritebackReadAdapter,
    *,
    remaining: int,
) -> SourceFileSnapshot:
    reference = file.authority
    try:
        with factory() as session:
            metadata = await adapter.read_repository_source_metadata(
                session,
                workspace=side.workspace,
                repository_slug=side.repository_slug,
                commit_hash=reference.commit_hash,
                path=reference.path,
            )
        require_source_file_metadata(reference, metadata)
        with factory() as session:
            content = await adapter.read_repository_source_file(
                session,
                workspace=side.workspace,
                repository_slug=side.repository_slug,
                commit_hash=reference.commit_hash,
                path=reference.path,
                max_bytes=min(reference.size_bytes, MAX_CANONICAL_FILE_BYTES, remaining),
            )
    except BitbucketProviderReadError as error:
        raise _provider_failure(error, file=True) from None
    if type(content) is not bytes or len(content) > remaining:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    return build_source_file_snapshot(
        reference, replace(file.parser_input, content=content), metadata
    )


async def prepare_writeback(
    factory: sessionmaker[Session], *, selection: WritebackSelection, adapter: WritebackReadAdapter
) -> PreparedWriteback:
    selection = _selection(selection)
    provisional, renewal_due = _bootstrap_capture(factory, selection)
    await _check_heads(factory, provisional, adapter)
    captured = _capture(factory, selection)
    comparable = (
        replace(provisional, connection_generation=captured.connection_generation)
        if renewal_due
        else provisional
    )
    if comparable != captured:
        raise _stale()
    groups: dict[
        tuple[UUID, str], tuple[SourceFileSnapshot, dict[tuple[str, str, bytes], WriteOperation]]
    ] = {}
    input_bytes = 0
    for file in captured.files:
        snapshot = await _snapshot(
            factory,
            file,
            _side(captured, file),
            adapter,
            remaining=MAX_CANONICAL_AGGREGATE_BYTES - input_bytes,
        )
        input_bytes += len(snapshot.parser_input.content)
        key = file.authority.repository_id, file.authority.path
        existing = groups.get(key)
        if existing is None:
            edits: dict[tuple[str, str, bytes], WriteOperation] = {}
            groups[key] = snapshot, edits
        else:
            previous, edits = existing
            if (
                previous.parser_input != snapshot.parser_input
                or previous.attributes != snapshot.attributes
                or previous.authority.commit_hash != snapshot.authority.commit_hash
            ):
                raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
        for edit in file.edits:
            identity = _edit_identity(edit)
            if identity in edits and edits[identity] != edit:
                raise WritebackRejected(WritebackReason.AMBIGUOUS_LOCATOR)
            edits[identity] = edit
    rendered = []
    output_bytes = 0
    for key in sorted(groups):
        snapshot, edits = groups[key]
        result = render_file(snapshot, tuple(edits[i] for i in sorted(edits)))
        output_bytes += len(result.content)
        if output_bytes > MAX_CANONICAL_AGGREGATE_BYTES:
            raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
        rendered.append(result)
    await _check_heads(factory, captured, adapter)
    if _capture(factory, selection) != captured:
        raise _stale()
    prepared = PreparedWriteback(selection, captured, tuple(rendered), "")
    return replace(prepared, manifest_digest=_manifest_digest(prepared))


async def revalidate_writeback_authority(
    factory: sessionmaker[Session], *, prepared: PreparedWriteback, adapter: WritebackReadAdapter
) -> None:
    if (
        type(prepared) is not PreparedWriteback
        or type(prepared.manifest_version) is not int
        or prepared.manifest_version != 1
    ):
        raise _stale()
    _capture_bounds(prepared.authority)
    if type(prepared.files) is not tuple or len(prepared.files) > MAX_CANONICAL_FILES:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    input_bytes = output_bytes = 0
    for file in prepared.files:
        if type(file) is not RenderedFile:
            raise _stale()
        try:
            file.__post_init__()
        except WritebackRejected:
            raise _stale() from None
        input_bytes += len(file.original_bytes)
        output_bytes += len(file.content)
    if max(input_bytes, output_bytes) > MAX_CANONICAL_AGGREGATE_BYTES:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    if prepared.manifest_digest != _manifest_digest(prepared):
        raise _stale()
    current = await prepare_writeback(factory, selection=prepared.selection, adapter=adapter)
    if current != prepared:
        raise _stale()
