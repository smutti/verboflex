"""Credential-free current authority and verified original file snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import Text, func, select
from sqlalchemy.orm import Session, load_only, selectinload
from sqlalchemy.sql import Select

from verboflex.integrations.bitbucket.client import BitbucketSourceMetadata
from verboflex.localization.graphemes import grapheme_count
from verboflex.localization.importing.core import (
    MAX_CANONICAL_AGGREGATE_BYTES,
    MAX_CANONICAL_FILES,
    MAX_CANONICAL_VALUES,
    CanonicalLocator,
    CanonicalParserInput,
    CanonicalSelector,
    RepositorySide,
    canonical_selector_bytes,
)
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.preview.core import (
    PreviewLayoutCandidate,
    layout_candidate_from_mapping,
)
from verboflex.localization.writing.core import (
    SourceFileAuthority,
    SourceFileSnapshot,
    WritebackReason,
    WritebackRejected,
    WriteEdit,
    WriteInsert,
    WriteOperation,
)
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.import_job import ImportExecution, ImportJob, ImportSourceReference
from verboflex.models.preview_job import PreviewJob
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.repository import Repository
from verboflex.models.review import TranslationProposal, TranslationProposalValue
from verboflex.models.translation import (
    LocalizationScope,
    TranslationKey,
    TranslationValue,
    TranslationValueLocator,
    TranslationValueRevision,
)
from verboflex.models.translation_constraint import TranslationConstraint
from verboflex.models.user import User
from verboflex.schemas.users import RoleName
from verboflex.services import preview_jobs
from verboflex.services.bitbucket_oauth import PULLREQUEST_WRITE_SCOPE
from verboflex.services.import_jobs import confirmed_file_parser_input
from verboflex.services.translation_constraints import project_effective_constraint


@dataclass(frozen=True, slots=True)
class ProposalSelection:
    proposal_id: UUID
    expected_version: int

    def __post_init__(self) -> None:
        if (
            type(self.proposal_id) is not UUID
            or type(self.expected_version) is not int
            or not 1 <= self.expected_version <= 9_007_199_254_740_991
        ):
            raise WritebackRejected(WritebackReason.STALE_BASIS)


@dataclass(frozen=True, slots=True)
class WritebackSelection:
    actor_id: UUID
    proposals: tuple[ProposalSelection, ...]

    def __post_init__(self) -> None:
        if (
            type(self.actor_id) is not UUID
            or type(self.proposals) is not tuple
            or not 1 <= len(self.proposals) <= MAX_CANONICAL_VALUES
            or any(type(item) is not ProposalSelection for item in self.proposals)
            or len({item.proposal_id for item in self.proposals}) != len(self.proposals)
        ):
            raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)


@dataclass(frozen=True, slots=True)
class CapturedSourceSide:
    repository_side: RepositorySide
    repository_id: UUID
    workspace: str
    repository_slug: str
    configured_branch: str
    commit_hash: str
    localization_root: str | None


@dataclass(frozen=True, slots=True)
class CapturedMapping:
    product_id: UUID
    revision_id: UUID
    revision_version: int
    mapping_id: UUID
    scope_id: UUID
    dataset_version: int
    import_job_id: UUID
    execution_id: UUID
    topology: str
    confirmed_preview_job_id: UUID
    confirmed_preview_digest: str
    selected_layout_candidate_id: UUID
    selected_layout_version: int
    base_language: str
    sides: tuple[CapturedSourceSide, ...]
    source_references: tuple[SourceFileAuthority, ...]
    allowed_targets: tuple[tuple[str, bool], ...]


@dataclass(frozen=True, slots=True)
class CapturedConstraint:
    rule_id: UUID
    language: str
    version: int
    maximum: int


@dataclass(frozen=True, slots=True)
class CapturedMember:
    value_id: UUID
    selector_version: int
    selector_digest: str
    basis_revision_number: int
    basis_digest: str
    authority: SourceFileAuthority
    edit: WriteOperation = field(repr=False)


@dataclass(frozen=True, slots=True)
class CapturedProposal:
    proposal_id: UUID
    version: int
    key_id: UUID
    language: str
    constraint_generation: int
    constraints: tuple[CapturedConstraint, ...]
    effective_maximum: int | None
    members: tuple[CapturedMember, ...]


@dataclass(frozen=True, slots=True)
class CapturedFile:
    mapping_id: UUID
    authority: SourceFileAuthority
    parser_input: CanonicalParserInput = field(repr=False)
    edits: tuple[WriteOperation, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class CapturedWritebackAuthority:
    actor_id: UUID
    actor_token_version: int
    roles: tuple[str, ...]
    connection_generation: int
    proposals: tuple[CapturedProposal, ...]
    mappings: tuple[CapturedMapping, ...]
    files: tuple[CapturedFile, ...]


def _stale() -> WritebackRejected:
    return WritebackRejected(WritebackReason.STALE_BASIS)


def _bounded[T](session: Session, statement: Select[tuple[T]], *, limit: int) -> tuple[T, ...]:
    rows = tuple(
        session.scalars(statement.limit(limit + 1).execution_options(populate_existing=True))
    )
    if len(rows) > limit:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    return rows


def _selector(value: TranslationValue) -> CanonicalSelector:
    try:
        data = json.loads(value.selector_bytes)
        selector = CanonicalSelector(
            data["kind"],
            tuple(
                (name, tuple(item) if isinstance(item, list) else item)
                for name, item in sorted(data["fields"].items())
            ),
            data["version"],
        )
        if (
            canonical_selector_bytes(selector) != value.selector_bytes
            or hashlib.sha256(value.selector_bytes).hexdigest() != value.selector_digest
            or selector.kind != value.selector_kind
            or selector.schema_version != value.selector_version
        ):
            raise _stale()
        return selector
    except KeyError, TypeError, ValueError:
        raise _stale() from None


def _capture_mapping(
    session: Session,
    scope: LocalizationScope,
    *,
    reference_limit: int,
    byte_limit: int,
    require_write_provider: bool = True,
) -> tuple[CapturedMapping, tuple[PreviewLayoutCandidate, ...]]:
    mapping = session.scalar(
        select(ProductRepositoryMapping)
        .where(ProductRepositoryMapping.id == scope.current_mapping_id)
        .options(
            selectinload(ProductRepositoryMapping.sides),
            selectinload(ProductRepositoryMapping.allowed_targets),
        )
        .execution_options(populate_existing=True)
    )
    revision = session.get(ProductRevision, scope.current_revision_id, populate_existing=True)
    job = session.get(ImportJob, scope.active_import_job_id, populate_existing=True)
    execution = session.get(ImportExecution, scope.active_execution_id, populate_existing=True)
    if (
        mapping is None
        or revision is None
        or job is None
        or execution is None
        or not revision.is_published
        or revision.product_id != scope.product_id
        or mapping.revision_id != revision.id
        or mapping.identity_key != scope.mapping_identity_key
        or job.product_id != scope.product_id
        or job.mapping_id != mapping.id
        or job.revision_id != revision.id
        or job.state != "current"
        or job.active_baseline_execution_id != execution.id
        or execution.import_job_id != job.id
        or execution.state != "succeeded"
        or execution.finished_at is None
        or mapping.base_language is None
        or mapping.confirmed_preview_job_id is None
        or mapping.confirmed_preview_digest is None
        or mapping.selected_layout_candidate_id is None
        or mapping.selected_layout_version != 1
    ):
        raise _stale()
    preview = session.get(PreviewJob, mapping.confirmed_preview_job_id, populate_existing=True)
    # Published layout authority is immutable. A later credential generation is a
    # distinct fact; renewing credentials must not rewrite this original proof.
    if (
        preview is None
        or not preview_jobs._confirmation_job_matches(preview, revision, mapping)
        or not preview_jobs._confirmed_layout_matches(preview, mapping)
    ):
        raise _stale()
    try:
        persisted_sides = preview_jobs._repository_sides(preview)
        sides = preview_jobs._complete_sides(
            mapping, {side.role: side.commit_hash for side in persisted_sides}
        )
        _, digest = preview_jobs._canonical_identity(
            product_id=scope.product_id,
            revision=revision,
            mapping=mapping,
            connection_generation=preview.connection_generation,
            repository_sides=sides,
        )
        if digest != preview.input_digest or sides != preview.repository_sides:
            raise _stale()
        assert preview.result is not None
        candidates = tuple(
            layout_candidate_from_mapping(raw)
            for raw in cast(list[object], preview.result["layout_candidates"])
        )
    except KeyError, TypeError, ValueError:
        raise _stale() from None
    roles = {"direct"} if mapping.topology == "direct" else {"keys", "translations"}
    if (
        {side.role for side in mapping.sides} != roles
        or {candidate.repository_side for candidate in candidates} != roles
        or len({candidate.id for candidate in candidates}) != len(candidates)
    ):
        raise _stale()
    references: tuple[ImportSourceReference, ...] = _bounded(
        session,
        select(ImportSourceReference)
        .where(ImportSourceReference.execution_id == execution.id)
        .order_by(ImportSourceReference.position),
        limit=reference_limit,
    )
    authorities = tuple(
        SourceFileAuthority(
            execution.id,
            ref.position,
            ref.repository_id,
            cast(RepositorySide, ref.repository_side),
            ref.source_branch,
            ref.commit_hash,
            ref.path,
            ref.size_bytes,
            ref.sha256,
        )
        for ref in references
    )
    if not authorities or sum(ref.size_bytes for ref in authorities) > byte_limit:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    captured_sides = []
    for side in mapping.sides:
        repository = session.get(Repository, side.repository_id, populate_existing=True)
        if require_write_provider and repository is not None and repository.provider != "bitbucket":
            raise WritebackRejected(WritebackReason.UNSUPPORTED_PROVIDER)
        matching = tuple(ref for ref in authorities if ref.repository_side == side.role)
        if (
            repository is None
            or not matching
            or len({ref.commit_hash for ref in matching}) != 1
            or any(
                ref.repository_id != side.repository_id
                or ref.configured_branch != side.source_branch
                for ref in matching
            )
        ):
            raise _stale()
        captured_sides.append(
            CapturedSourceSide(
                cast(RepositorySide, side.role),
                side.repository_id,
                repository.workspace,
                repository.repository_slug,
                side.source_branch,
                matching[0].commit_hash,
                side.localization_root,
            )
        )
    if {ref.repository_side for ref in authorities} != roles:
        raise _stale()
    return CapturedMapping(
        scope.product_id,
        revision.id,
        revision.version,
        mapping.id,
        scope.id,
        scope.dataset_version,
        job.id,
        execution.id,
        mapping.topology,
        preview.id,
        mapping.confirmed_preview_digest,
        mapping.selected_layout_candidate_id,
        mapping.selected_layout_version,
        mapping.base_language,
        tuple(captured_sides),
        authorities,
        tuple(sorted((target.branch, target.is_default) for target in mapping.allowed_targets)),
    ), candidates


def capture_writeback_authority(
    session: Session, *, selection: WritebackSelection, allow_expired_connection: bool = False
) -> CapturedWritebackAuthority:
    """Capture inside one short caller-owned transaction; never flush or do IO.

    All products and scopes are locked deterministically before per-group locks.
    The caller must close this transaction before contacting the repository.
    Submission-role policy remains the Phase 7 caller's responsibility.
    ``allow_expired_connection`` is only a provisional bootstrap read: a caller
    must acquire the ordinary read lease outside this transaction, then repeat
    strict capture before constructing a prepared manifest.
    """
    if type(selection) is not WritebackSelection:
        raise _stale()
    with session.no_autoflush:
        return _capture(session, selection, allow_expired_connection=allow_expired_connection)


def _capture(
    session: Session, selection: WritebackSelection, *, allow_expired_connection: bool
) -> CapturedWritebackAuthority:
    requested = {item.proposal_id: item.expected_version for item in selection.proposals}
    proposals: tuple[TranslationProposal, ...] = _bounded(
        session,
        select(TranslationProposal)
        .where(TranslationProposal.id.in_(requested))
        .order_by(TranslationProposal.id),
        limit=len(requested),
    )
    from verboflex.models.authoring import AuthoringRequest

    addition_bytes = session.scalar(
        select(
            func.coalesce(func.sum(func.octet_length(AuthoringRequest.payload.cast(Text))), 0)
        ).where(AuthoringRequest.id.in_(requested))
    )
    if addition_bytes is not None and addition_bytes > MAX_CANONICAL_AGGREGATE_BYTES:
        raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
    additions = _bounded(
        session,
        select(AuthoringRequest)
        .where(AuthoringRequest.id.in_(requested))
        .order_by(AuthoringRequest.id),
        limit=len(requested),
    )
    if len(proposals) + len(additions) != len(requested):
        raise _stale()
    scope_ids = {p.scope_id for p in proposals} | {a.scope_id for a in additions}
    scopes: tuple[LocalizationScope, ...] = _bounded(
        session,
        select(LocalizationScope).where(LocalizationScope.id.in_(scope_ids)),
        limit=len(requested),
    )
    product_ids = {scope.product_id for scope in scopes}
    products: tuple[Product, ...] = _bounded(
        session,
        select(Product)
        .where(Product.id.in_(product_ids))
        .order_by(Product.id)
        .with_for_update(read=True),
        limit=len(product_ids),
    )
    scopes = _bounded(
        session,
        select(LocalizationScope)
        .where(LocalizationScope.id.in_({scope.id for scope in scopes}))
        .order_by(LocalizationScope.id)
        .with_for_update(),
        limit=len(requested),
    )
    product_map = {product.id: product for product in products}
    scope_map = {scope.id: scope for scope in scopes}
    for scope in scopes:
        product = product_map.get(scope.product_id)
        if (
            product is None
            or not product.is_active
            or product.deleted_at is not None
            or product.active_revision_id != scope.current_revision_id
            or scope.active_execution_id is None
        ):
            raise _stale()
    actor = session.scalar(
        select(User)
        .where(User.id == selection.actor_id)
        .with_for_update(read=True)
        .options(selectinload(User.roles))
        .execution_options(populate_existing=True)
    )
    if actor is None or not actor.is_active or actor.must_change_password or not actor.roles:
        raise WritebackRejected(WritebackReason.AUTHORITY_UNAVAILABLE)
    try:
        roles = tuple(RoleName(role.name) for role in actor.roles)
    except ValueError:
        raise WritebackRejected(WritebackReason.AUTHORITY_UNAVAILABLE) from None
    # READ permits every known role. Actor validity and that closed role set are
    # checked above; do not build the UI group projection (history/structure/text)
    # just to repeat that policy. Phase 7 applies its separate submission policy.
    mappings = {}
    candidates = {}
    reference_budget = MAX_CANONICAL_FILES
    source_byte_budget = MAX_CANONICAL_AGGREGATE_BYTES
    for scope in scopes:
        mapping, layouts = _capture_mapping(
            session, scope, reference_limit=reference_budget, byte_limit=source_byte_budget
        )
        reference_budget -= len(mapping.source_references)
        source_byte_budget -= sum(ref.size_bytes for ref in mapping.source_references)
        mappings[scope.id], candidates[scope.id] = mapping, layouts
    captured_proposals = []
    captured_files: dict[tuple[UUID, SourceFileAuthority], CapturedFile] = {}
    member_count = 0
    text_bytes = 0
    for proposal in proposals:
        current_scope = scope_map.get(proposal.scope_id)
        if current_scope is None:
            raise _stale()
        scope = current_scope
        proposal = session.scalars(
            select(TranslationProposal)
            .where(TranslationProposal.id == proposal.id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        ).one()
        if (
            proposal.version != requested[proposal.id]
            or proposal.state != "approved"
            or proposal.reconciliation_required
            or proposal.scope_id != scope.id
        ):
            raise _stale()
        remaining = MAX_CANONICAL_VALUES - member_count
        # Cheap counts/octet lengths precede every value/anchor/projection load.
        # The current scope lock serializes normal proposal/import mutations.
        current_count, current_text_size = session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(func.octet_length(TranslationValue.display_text)), 0),
            ).where(
                TranslationValue.translation_key_id == proposal.translation_key_id,
                TranslationValue.language == proposal.language,
                TranslationValue.is_deleted.is_(False),
            )
        ).one()
        pending_count, proposed_text_size = session.execute(
            select(
                func.count(),
                func.coalesce(
                    func.sum(func.octet_length(TranslationProposalValue.proposed_text)), 0
                ),
            ).where(TranslationProposalValue.proposal_id == proposal.id)
        ).one()
        if (
            current_count > remaining
            or pending_count > remaining
            or text_bytes + current_text_size + proposed_text_size > MAX_CANONICAL_AGGREGATE_BYTES
        ):
            raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
        key = session.scalar(
            select(TranslationKey)
            .where(
                TranslationKey.id == proposal.translation_key_id,
                TranslationKey.scope_id == scope.id,
                TranslationKey.product_id == scope.product_id,
                TranslationKey.is_deleted.is_(False),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if key is None:
            raise _stale()
        values: tuple[TranslationValue, ...] = _bounded(
            session,
            select(TranslationValue)
            .where(
                TranslationValue.translation_key_id == key.id,
                TranslationValue.language == proposal.language,
                TranslationValue.is_deleted.is_(False),
            )
            .options(
                load_only(
                    TranslationValue.id,
                    TranslationValue.scope_id,
                    TranslationValue.translation_key_id,
                    TranslationValue.language,
                    TranslationValue.is_deleted,
                    TranslationValue.selector_version,
                    TranslationValue.selector_kind,
                    TranslationValue.selector_bytes,
                    TranslationValue.selector_digest,
                    TranslationValue.display_text,
                )
            )
            .order_by(TranslationValue.id)
            .with_for_update(read=True),
            limit=remaining,
        )
        pending: tuple[TranslationProposalValue, ...] = _bounded(
            session,
            select(TranslationProposalValue)
            .where(TranslationProposalValue.proposal_id == proposal.id)
            .order_by(TranslationProposalValue.translation_value_id),
            limit=remaining,
        )
        if (
            not values
            or len(values) != len(pending)
            or any(value.is_deleted or value.scope_id != scope.id for value in values)
        ):
            raise _stale()
        pending_map = {item.translation_value_id: item for item in pending}
        if set(pending_map) != {value.id for value in values}:
            raise _stale()
        mapping = mappings[scope.id]
        rules: tuple[TranslationConstraint, ...] = _bounded(
            session,
            select(TranslationConstraint)
            .where(
                TranslationConstraint.translation_key_id == key.id,
                TranslationConstraint.language.in_({mapping.base_language, proposal.language}),
            )
            .order_by(TranslationConstraint.language)
            .with_for_update(read=True),
            limit=2,
        )
        by_language = {rule.language: rule for rule in rules}
        maximum = project_effective_constraint(
            language=proposal.language,
            base_language=mapping.base_language,
            explicit_constraint=by_language.get(proposal.language),
            base_constraint=by_language.get(mapping.base_language),
        ).maximum
        members = []
        for value in values:
            item = pending_map[value.id]
            revision = session.scalar(
                select(TranslationValueRevision)
                .where(TranslationValueRevision.value_id == value.id)
                .options(
                    load_only(
                        TranslationValueRevision.id,
                        TranslationValueRevision.is_deleted,
                        TranslationValueRevision.translation_key_id,
                        TranslationValueRevision.revision_number,
                        TranslationValueRevision.revision_digest,
                        TranslationValueRevision.display_text,
                    )
                )
                .order_by(TranslationValueRevision.revision_number.desc())
                .limit(1)
                .execution_options(populate_existing=True)
            )
            if (
                revision is None
                or revision.is_deleted
                or revision.translation_key_id != key.id
                or item.selector_version != value.selector_version
                or item.selector_digest != value.selector_digest
                or item.basis_revision_number != revision.revision_number
                or item.basis_digest != revision.revision_digest
                or revision.display_text != value.display_text
            ):
                raise _stale()
            text_bytes += (
                len(item.proposed_text.encode("utf-8"))
                + len(value.display_text.encode("utf-8"))
                + len(key.raw_key.encode("utf-8"))
                + len(value.selector_bytes)
            )
            if text_bytes > MAX_CANONICAL_AGGREGATE_BYTES:
                raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
            if maximum is not None and grapheme_count(item.proposed_text) > maximum:
                raise WritebackRejected(WritebackReason.INVALID_REPLACEMENT)
            locator = session.get(TranslationValueLocator, value.id, populate_existing=True)
            if (
                locator is None
                or locator.translation_key_id != key.id
                or locator.import_job_id != mapping.import_job_id
                or locator.import_execution_id != mapping.execution_id
                or locator.repository_side
                != ("direct" if mapping.topology == "direct" else "translations")
            ):
                raise _stale()
            refs = tuple(
                ref
                for ref in mapping.source_references
                if ref.source_reference_position == locator.source_reference_position
            )
            if len(refs) != 1:
                raise _stale()
            authority = refs[0]
            if (
                authority.repository_id,
                authority.repository_side,
                authority.configured_branch,
                authority.commit_hash,
                authority.path,
            ) != (
                locator.repository_id,
                locator.repository_side,
                locator.configured_branch,
                locator.source_commit_hash,
                locator.path,
            ):
                raise _stale()
            parser = confirmed_file_parser_input(
                candidates[scope.id],
                repository_side=authority.repository_side,
                path=authority.path,
                content=b"",
                base_language=mapping.base_language,
            )
            if parser is None or parser.format != locator.format:
                raise _stale()
            try:
                canonical_locator = CanonicalLocator(
                    locator.format,
                    authority.repository_side,
                    locator.path,
                    locator.position,
                    cast(tuple[str | int, ...], tuple(locator.structural_address)),
                    locator.line,
                    locator.column,
                )
                edit = WriteEdit(
                    key.raw_key,
                    value.language,
                    _selector(value),
                    canonical_locator,
                    value.display_text,
                    item.proposed_text,
                )
            except ValueError:
                raise _stale() from None
            members.append(
                CapturedMember(
                    value.id,
                    value.selector_version,
                    value.selector_digest,
                    revision.revision_number,
                    revision.revision_digest,
                    authority,
                    edit,
                )
            )
            file_key = (mapping.mapping_id, authority)
            existing = captured_files.get(file_key)
            captured_files[file_key] = CapturedFile(
                mapping.mapping_id,
                authority,
                parser,
                (() if existing is None else existing.edits) + (edit,),
            )
        member_count += len(members)
        captured_proposals.append(
            CapturedProposal(
                proposal.id,
                proposal.version,
                key.id,
                proposal.language,
                key.constraint_generation,
                tuple(
                    CapturedConstraint(rule.id, rule.language, rule.version, rule.max_chars)
                    for rule in rules
                ),
                maximum,
                tuple(members),
            )
        )
    from verboflex.services.authoring_writeback import capture_addition

    for addition in additions:
        captured, files = capture_addition(
            session,
            addition,
            requested[addition.id],
            scope_map[addition.scope_id],
            mappings[addition.scope_id],
        )
        member_count += len(captured.members)
        text_bytes += sum(
            len(m.edit.replacement_text.encode())
            + len(m.edit.source_text.encode())
            + len(m.edit.context.encode())
            for m in captured.members
            if isinstance(m.edit, WriteInsert)
        )
        if member_count > MAX_CANONICAL_VALUES or text_bytes > MAX_CANONICAL_AGGREGATE_BYTES:
            raise WritebackRejected(WritebackReason.LIMIT_EXCEEDED)
        captured_proposals.append(captured)
        for file in files:
            addition_file_key = (file.mapping_id, file.authority)
            previous = captured_files.get(addition_file_key)
            captured_files[addition_file_key] = CapturedFile(
                file.mapping_id,
                file.authority,
                file.parser_input,
                (() if previous is None else previous.edits) + file.edits,
            )
    connection = session.get(BitbucketConnection, 1, populate_existing=True)
    if (
        connection is None
        or connection.revoked_at is not None
        or connection.access_token_ciphertext is None
        or connection.refresh_token_ciphertext is not None
        or connection.scope_profile != PULLREQUEST_WRITE_SCOPE
        or connection.provider_expires_at is None
        or (not allow_expired_connection and connection.provider_expires_at <= datetime.now(UTC))
    ):
        raise WritebackRejected(WritebackReason.AUTHORITY_UNAVAILABLE)
    return CapturedWritebackAuthority(
        actor.id,
        actor.token_version,
        tuple(role.value for role in roles),
        connection.generation,
        tuple(captured_proposals),
        tuple(sorted(mappings.values(), key=lambda item: item.mapping_id)),
        tuple(
            captured_files[key]
            for key in sorted(
                captured_files, key=lambda pair: (pair[0], pair[1].source_reference_position)
            )
        ),
    )


def require_source_file_metadata(
    authority: SourceFileAuthority, metadata: BitbucketSourceMetadata
) -> None:
    """Reject changed/special files before fetching their raw bytes."""
    if type(metadata) is not BitbucketSourceMetadata or (
        metadata.path != authority.path
        or metadata.commit_hash != authority.commit_hash
        or type(metadata.size_bytes) is not int
        or metadata.size_bytes != authority.size_bytes
    ):
        raise WritebackRejected(WritebackReason.SOURCE_FILE_CHANGED)
    if metadata.attributes not in ((), ("binary",)):
        raise WritebackRejected(WritebackReason.UNSUPPORTED_FILE_ATTRIBUTES)


def build_source_file_snapshot(
    authority: SourceFileAuthority,
    parser_input: CanonicalParserInput,
    metadata: BitbucketSourceMetadata,
) -> SourceFileSnapshot:
    """Verify immutable coordinates, bytes and explicit regular-text evidence."""
    require_source_file_metadata(authority, metadata)
    snapshot = SourceFileSnapshot(authority, parser_input, metadata.attributes)
    if parser_input.repository_side == "keys":
        raise WritebackRejected(WritebackReason.STALE_BASIS)
    if parser_input.format not in {"android_xml", "qt_ts", "json", "ios_strings"}:
        raise WritebackRejected(WritebackReason.UNSUPPORTED_FORMAT)
    if parse_canonical_snapshot(parser_input).issues:
        raise WritebackRejected(WritebackReason.UNSUPPORTED_SHAPE)
    return snapshot
