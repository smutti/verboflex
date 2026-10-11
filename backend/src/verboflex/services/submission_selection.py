"""Exact destination partitioning and bounded, read-only grouped preparation."""

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session, sessionmaker

from verboflex.localization.importing.core import (
    MAX_CANONICAL_AGGREGATE_BYTES,
    MAX_CANONICAL_FILES,
    MAX_CANONICAL_VALUES,
)
from verboflex.localization.writing.core import WritebackReason, WritebackRejected
from verboflex.schemas.submissions import MappingDestination, MappingTarget
from verboflex.services.pr_grouping import PullRequestChange, group_pull_request_changes
from verboflex.services.writeback import (
    PreparedWriteback,
    ProposalSelection,
    WritebackReadAdapter,
    WritebackSelection,
    prepare_writeback,
    revalidate_writeback_authority,
)
from verboflex.services.writeback_authority import (
    CapturedMapping,
    CapturedProposal,
    CapturedWritebackAuthority,
)

MAX_SELECTED_PROPOSALS = 100
MAX_SUBMISSION_GROUPS = 20


class SubmissionReadAdapter(WritebackReadAdapter, Protocol):
    async def read_repository_metadata(
        self, session: Session, *, workspace: str, repository_slug: str
    ) -> Mapping[str, object]: ...


async def provider_repository_identity(
    factory: sessionmaker[Session],
    *,
    workspace: str,
    repository_slug: str,
    adapter: SubmissionReadAdapter,
) -> UUID:
    with factory() as session:
        value = await adapter.read_repository_metadata(
            session, workspace=workspace, repository_slug=repository_slug
        )
    identity, full_name = value.get("uuid"), value.get("full_name")
    if (
        value.get("type") != "repository"
        or not isinstance(identity, str)
        or not isinstance(full_name, str)
        or full_name.lower() != f"{workspace}/{repository_slug}"
    ):
        raise rejected(WritebackReason.AUTHORITY_UNAVAILABLE)
    try:
        return UUID(identity)
    except ValueError:
        raise rejected(WritebackReason.AUTHORITY_UNAVAILABLE) from None


def rejected(reason: WritebackReason = WritebackReason.STALE_BASIS) -> WritebackRejected:
    return WritebackRejected(reason)


def proposal_mapping(authority: CapturedWritebackAuthority, proposal_id: UUID) -> CapturedMapping:
    proposal = next((p for p in authority.proposals if p.proposal_id == proposal_id), None)
    if proposal is None or not proposal.members:
        raise rejected()
    matches = [
        m
        for m in authority.mappings
        if all(value.authority.import_execution_id == m.execution_id for value in proposal.members)
    ]
    if len(matches) != 1:
        raise rejected()
    return matches[0]


def destinations(
    authority: CapturedWritebackAuthority, choices: tuple[MappingTarget, ...] = ()
) -> tuple[MappingDestination, ...]:
    requested = {choice.mapping_id: choice.target_branch for choice in choices}
    if len(requested) != len(choices) or set(requested) - {
        m.mapping_id for m in authority.mappings
    }:
        raise rejected()
    result = []
    for mapping in sorted(authority.mappings, key=lambda m: m.mapping_id):
        sides = [s for s in mapping.sides if s.repository_side != "keys"]
        defaults = [branch for branch, default in mapping.allowed_targets if default]
        if len(sides) != 1 or len(defaults) != 1:
            raise rejected()
        allowed = sorted(branch for branch, _ in mapping.allowed_targets)
        chosen = requested.get(mapping.mapping_id, defaults[0])
        if chosen not in allowed:
            raise rejected(WritebackReason.AUTHORITY_UNAVAILABLE)
        side = sides[0]
        result.append(
            MappingDestination(
                mapping_id=mapping.mapping_id,
                repository_id=side.repository_id,
                workspace=side.workspace,
                repository_slug=side.repository_slug,
                allowed_targets=allowed,
                default_target=defaults[0],
                chosen_target=chosen,
            )
        )
    return tuple(result)


@dataclass(frozen=True, slots=True)
class ReviewPartition:
    repository_id: UUID
    workspace: str
    repository_slug: str
    target_branch: str
    mapping_ids: tuple[UUID, ...]
    selection: WritebackSelection


def partition_selection(
    authority: CapturedWritebackAuthority, *, targets: tuple[MappingTarget, ...] = ()
) -> tuple[ReviewPartition, ...]:
    proposals = authority.proposals
    if not proposals or len(proposals) > MAX_SELECTED_PROPOSALS:
        raise rejected(WritebackReason.LIMIT_EXCEEDED)
    if len({p.proposal_id for p in proposals}) != len(proposals):
        raise rejected()
    dest = {d.mapping_id: d for d in destinations(authority, targets)}
    changes: list[PullRequestChange] = []
    by_mapping: dict[UUID, list[CapturedProposal]] = {}
    for proposal in proposals:
        mapping = proposal_mapping(authority, proposal.proposal_id)
        target = dest[mapping.mapping_id]
        by_mapping.setdefault(mapping.mapping_id, []).append(proposal)
        for member in proposal.members:
            if (
                member.authority.repository_id != target.repository_id
                or member.authority.repository_side == "keys"
            ):
                raise rejected()
            changes.append(
                PullRequestChange(
                    target.repository_id,
                    target.chosen_target,
                    mapping.mapping_id,
                    member.authority.path,
                    proposal.language,
                )
            )
    groups = group_pull_request_changes(changes)
    if len(groups) > MAX_SUBMISSION_GROUPS:
        raise rejected(WritebackReason.LIMIT_EXCEEDED)
    result = []
    for group in groups:
        mapping_ids = tuple(sorted({change.mapping_id for change in group.changes}))
        first = dest[mapping_ids[0]]
        if any(
            (dest[mid].workspace, dest[mid].repository_slug)
            != (first.workspace, first.repository_slug)
            for mid in mapping_ids
        ):
            raise rejected()
        selected = sorted(
            (p for mid in mapping_ids for p in by_mapping[mid]), key=lambda p: p.proposal_id
        )
        result.append(
            ReviewPartition(
                group.repository_id,
                first.workspace,
                first.repository_slug,
                group.target_branch,
                mapping_ids,
                WritebackSelection(
                    authority.actor_id,
                    tuple(ProposalSelection(p.proposal_id, p.version) for p in selected),
                ),
            )
        )
    return tuple(result)


@dataclass(frozen=True, slots=True)
class PreparedSubmissionGroup:
    id: UUID
    repository_id: UUID
    workspace: str
    repository_slug: str
    target_branch: str
    target_head: str
    prepared: PreparedWriteback = field(repr=False)
    provider_repository_id: UUID

    @property
    def source_branch(self) -> str:
        return f"verboflex/change-set-{self.id}"


@dataclass(frozen=True, slots=True)
class PreparedSubmissionReview:
    groups: tuple[PreparedSubmissionGroup, ...] = field(repr=False)
    content_digest: str
    version: int = 1


def review_content_digest(groups: tuple[PreparedSubmissionGroup, ...]) -> str:
    # Random reservation UUID/branch is bound to the immutable review separately.
    values = [
        (
            str(g.repository_id),
            str(g.provider_repository_id),
            g.workspace,
            g.repository_slug,
            g.target_branch,
            g.target_head,
            g.prepared.manifest_digest,
        )
        for g in groups
    ]
    return hashlib.sha256(
        json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()


def enforce_review_bounds(groups: tuple[PreparedSubmissionGroup, ...]) -> None:
    proposals = [p for g in groups for p in g.prepared.authority.proposals]
    files = [f for g in groups for f in g.prepared.files]
    references = [
        r for g in groups for m in g.prepared.authority.mappings for r in m.source_references
    ]
    if (
        not groups
        or len(groups) > MAX_SUBMISSION_GROUPS
        or len(proposals) > MAX_SELECTED_PROPOSALS
        or len(files) > MAX_CANONICAL_FILES
        or len(references) > MAX_CANONICAL_FILES
        or sum(len(p.members) for p in proposals) > MAX_CANONICAL_VALUES
        or sum(r.size_bytes for r in references) > MAX_CANONICAL_AGGREGATE_BYTES
        or sum(len(f.original_bytes) for f in files) > MAX_CANONICAL_AGGREGATE_BYTES
        or sum(len(f.content) for f in files) > MAX_CANONICAL_AGGREGATE_BYTES
        or sum(
            len(m.edit.expected_text.encode()) + len(m.edit.replacement_text.encode())
            for p in proposals
            for m in p.members
        )
        > MAX_CANONICAL_AGGREGATE_BYTES
    ):
        raise rejected(WritebackReason.LIMIT_EXCEEDED)
    if len({p.proposal_id for p in proposals}) != len(proposals) or len(
        {g.id for g in groups}
    ) != len(groups):
        raise rejected()


async def check_target(
    factory: sessionmaker[Session],
    *,
    group: PreparedSubmissionGroup,
    adapter: SubmissionReadAdapter,
    files: bool = True,
) -> None:
    provider_id = await provider_repository_identity(
        factory, workspace=group.workspace, repository_slug=group.repository_slug, adapter=adapter
    )
    if provider_id != group.provider_repository_id:
        raise rejected(WritebackReason.AUTHORITY_UNAVAILABLE)
    with factory() as session:
        head = await adapter.resolve_repository_branch(
            session,
            workspace=group.workspace,
            repository_slug=group.repository_slug,
            branch=group.target_branch,
        )
    if head.name != group.target_branch or head.commit_hash != group.target_head:
        raise rejected(WritebackReason.SOURCE_BRANCH_CHANGED)
    if not files:
        return
    for file in group.prepared.files:
        if (
            file.authority.repository_id != group.repository_id
            or file.authority.repository_side == "keys"
        ):
            raise rejected()
        coordinates = dict(
            workspace=group.workspace,
            repository_slug=group.repository_slug,
            commit_hash=group.target_head,
            path=file.authority.path,
        )
        with factory() as session:
            metadata = await adapter.read_repository_source_metadata(session, **coordinates)
        if (
            metadata.path != file.authority.path
            or metadata.commit_hash != group.target_head
            or metadata.size_bytes != len(file.original_bytes)
            or metadata.attributes != file.attributes
        ):
            raise rejected(WritebackReason.SOURCE_FILE_CHANGED)
        with factory() as session:
            raw = await adapter.read_repository_source_file(
                session, **coordinates, max_bytes=max(1, len(file.original_bytes))
            )
        if raw != file.original_bytes:
            raise rejected(WritebackReason.SOURCE_FILE_CHANGED)


async def prepare_submission_groups(
    factory: sessionmaker[Session],
    *,
    authority: CapturedWritebackAuthority,
    targets: tuple[MappingTarget, ...],
    adapter: SubmissionReadAdapter,
) -> PreparedSubmissionReview:
    partitions = partition_selection(authority, targets=targets)
    groups: list[PreparedSubmissionGroup] = []
    for partition in partitions:
        provider_id = await provider_repository_identity(
            factory,
            workspace=partition.workspace,
            repository_slug=partition.repository_slug,
            adapter=adapter,
        )
        # Crucially, Phase 6 sees only this destination's proposal IDs.
        prepared = await prepare_writeback(factory, selection=partition.selection, adapter=adapter)
        with factory() as session:
            head = await adapter.resolve_repository_branch(
                session,
                workspace=partition.workspace,
                repository_slug=partition.repository_slug,
                branch=partition.target_branch,
            )
        if head.name != partition.target_branch or not re.fullmatch(
            r"[0-9a-f]{40}", head.commit_hash
        ):
            raise rejected(WritebackReason.SOURCE_BRANCH_CHANGED)
        group = PreparedSubmissionGroup(
            uuid4(),
            partition.repository_id,
            partition.workspace,
            partition.repository_slug,
            partition.target_branch,
            head.commit_hash,
            prepared,
            provider_id,
        )
        groups.append(group)
        enforce_review_bounds(tuple(groups))
        await check_target(factory, group=group, adapter=adapter)
    # Later groups can race an earlier group's local or remote basis. Revalidate
    # every frozen group, including Keys-only sides, before publishing the review.
    for group in groups:
        await revalidate_writeback_authority(factory, prepared=group.prepared, adapter=adapter)
        await check_target(factory, group=group, adapter=adapter, files=False)
    if len({g.prepared.authority.connection_generation for g in groups}) != 1:
        raise rejected()
    frozen = tuple(groups)
    return PreparedSubmissionReview(frozen, review_content_digest(frozen))
