"""Atomic local admission of frozen reviews; no provider work in HTTP requests."""

import hashlib
import json
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from verboflex.integrations.bitbucket.urls import validate_pull_request_url
from verboflex.localization.writing.core import WritebackReason, WritebackRejected
from verboflex.models.product import Product
from verboflex.models.submission import (
    ChangeSet,
    ChangeSetFile,
    ChangeSetItem,
    ChangeSetProof,
    SubmissionBatch,
    SubmissionReview,
)
from verboflex.models.translation import LocalizationScope
from verboflex.schemas.submissions import (
    ChangeSetResponse,
    ChangeSetStage,
    ChangeSetStatus,
    CreateSubmissionBatchRequest,
    PullRequestTracking,
    SubmissionBatchResponse,
)
from verboflex.services.submission_codec import (
    MAX_PAYLOAD_BYTES,
    decode_prepared_writeback,
    encode_prepared_writeback,
)
from verboflex.services.submission_reviews import (
    SubmissionReviewUnavailable,
    _load_prepared,
    _product_actor,
)
from verboflex.services.submission_selection import PreparedSubmissionGroup, proposal_mapping
from verboflex.services.writeback import PreparedWriteback, _normalize
from verboflex.services.writeback_authority import capture_writeback_authority

SubmissionEnqueuer = Callable[[UUID], None]


class SubmissionConflict(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__("Submission requires a current unclaimed review")
        self.code = code


@dataclass(frozen=True, slots=True)
class ChangeSetBundle:
    group: PreparedSubmissionGroup = field(repr=False)
    proof: PreparedWriteback = field(repr=False)
    actor_id: UUID
    actor_token_version: int
    product_id: UUID
    revision_id: UUID


def enqueue_submission(change_set_id: UUID) -> None:
    from verboflex.worker.submission_tasks import run_submission

    run_submission.delay(str(change_set_id))


def load_change_set_bundle(session: Session, change_set_id: UUID) -> ChangeSetBundle:
    """Load bounded immutable bytes, independently validate the current proof."""
    row = session.get(ChangeSet, change_set_id)
    if row is None:
        raise SubmissionReviewUnavailable("submission unavailable")
    batch = session.get(SubmissionBatch, row.batch_id)
    proof_row = session.get(ChangeSetProof, (row.id, row.current_proof_sequence))
    if batch is None or proof_row is None:
        raise SubmissionConflict("invalid_snapshot")
    original_length = session.scalar(
        select(func.octet_length(ChangeSet.original_prepared_payload)).where(ChangeSet.id == row.id)
    )
    proof_length = session.scalar(
        select(func.octet_length(ChangeSetProof.prepared_payload)).where(
            ChangeSetProof.change_set_id == row.id,
            ChangeSetProof.sequence == row.current_proof_sequence,
        )
    )
    if any(
        length is None or not 0 < length <= MAX_PAYLOAD_BYTES
        for length in (original_length, proof_length)
    ):
        raise SubmissionConflict("invalid_snapshot")
    original_payload, payload = row.original_prepared_payload, proof_row.prepared_payload
    if (
        hashlib.sha256(original_payload).hexdigest() != row.original_proof_digest
        or hashlib.sha256(payload).hexdigest() != proof_row.proof_digest
    ):
        raise SubmissionConflict("invalid_snapshot")
    try:
        original = decode_prepared_writeback(original_payload)
        proof = decode_prepared_writeback(payload)
    except ValueError:
        raise SubmissionConflict("invalid_snapshot") from None
    if (
        original.manifest_digest != row.manifest_digest
        or row.source_branch != f"verboflex/change-set-{row.id}"
        or original.authority.actor_id != batch.actor_id
        or original.authority.actor_token_version != batch.actor_token_version
        or proof.authority.connection_generation != proof_row.connection_generation
        or replace(
            proof,
            authority=replace(
                proof.authority, connection_generation=original.authority.connection_generation
            ),
            manifest_digest=original.manifest_digest,
        )
        != original
    ):
        raise SubmissionConflict("invalid_snapshot")
    return ChangeSetBundle(
        PreparedSubmissionGroup(
            id=row.id,
            repository_id=row.repository_id,
            workspace=row.workspace,
            repository_slug=row.repository_slug,
            target_branch=row.target_branch,
            target_head=row.target_head,
            prepared=original,
            provider_repository_id=row.provider_repository_id,
        ),
        proof,
        batch.actor_id,
        batch.actor_token_version,
        batch.product_id,
        batch.revision_id,
    )


def change_set_response(
    row: ChangeSet, *, session: Session | None = None, actor_id: UUID | None = None
) -> ChangeSetResponse:
    url = row.pr_url
    if url is not None:
        try:
            if row.pr_id is None:
                raise ValueError
            validate_pull_request_url(
                url,
                workspace=row.workspace,
                repository_slug=row.repository_slug,
                pull_request_id=row.pr_id,
            )
        except ValueError:
            url = None
    result = ChangeSetResponse(
        id=row.id,
        batch_id=row.batch_id,
        status=cast(ChangeSetStatus, row.status),
        stage=cast(ChangeSetStage, row.stage),
        attempt=row.attempt,
        repository_id=row.repository_id,
        workspace=row.workspace,
        repository_slug=row.repository_slug,
        target_branch=row.target_branch,
        target_head=row.target_head,
        source_branch=row.source_branch,
        proposal_count=row.proposal_count,
        value_count=row.value_count,
        file_count=row.file_count,
        error_code=row.error_code,
        pr_id=row.pr_id,
        pr_url=url,
        pr_state=row.pr_state,
        pr_tracking=PullRequestTracking.model_validate(row.pr_tracking)
        if row.pr_tracking is not None
        else None,
        created_at=row.created_at,
    )
    if session is not None and actor_id is not None:
        from verboflex.services.submission_history import group_metadata
        from verboflex.services.submission_recovery import recovery_capabilities

        result = result.model_copy(
            update={**recovery_capabilities(session, row, actor_id), **group_metadata(session, row)}
        )
    return result


def _batch_response(
    session: Session, batch: SubmissionBatch, actor_id: UUID | None = None
) -> SubmissionBatchResponse:
    groups = list(
        session.scalars(
            select(ChangeSet)
            .where(ChangeSet.batch_id == batch.id)
            .order_by(ChangeSet.repository_id, ChangeSet.target_branch)
            .limit(21)
        )
    )
    if not 1 <= len(groups) <= 20:
        raise SubmissionConflict("invalid_snapshot")
    return SubmissionBatchResponse(
        id=batch.id,
        product_id=batch.product_id,
        review_id=batch.review_id,
        request_key=batch.request_key,
        created_at=batch.created_at,
        groups=[change_set_response(group, session=session, actor_id=actor_id) for group in groups],
    )


def _persist_group(
    session: Session, batch: SubmissionBatch, group: PreparedSubmissionGroup
) -> None:
    prepared = group.prepared
    payload = encode_prepared_writeback(prepared)
    proof_digest = hashlib.sha256(payload).hexdigest()
    row = ChangeSet(
        id=group.id,
        batch_id=batch.id,
        repository_id=group.repository_id,
        provider_repository_id=group.provider_repository_id,
        workspace=group.workspace,
        repository_slug=group.repository_slug,
        target_branch=group.target_branch,
        target_head=group.target_head,
        source_branch=group.source_branch,
        manifest_digest=prepared.manifest_digest,
        original_prepared_payload=payload,
        original_proof_digest=proof_digest,
        proposal_count=len(prepared.authority.proposals),
        value_count=sum(len(p.members) for p in prepared.authority.proposals),
        file_count=len(prepared.files),
    )
    session.add(row)
    session.flush()
    session.add(
        ChangeSetProof(
            change_set_id=group.id,
            sequence=1,
            connection_generation=prepared.authority.connection_generation,
            proof_digest=proof_digest,
            prepared_payload=payload,
        )
    )
    file_changed_values = {file.authority.path: len(file.changed_edits) for file in prepared.files}
    for proposal in prepared.authority.proposals:
        mapping = proposal_mapping(prepared.authority, proposal.proposal_id)
        sources = [
            {
                "mapping_id": str(mapping.mapping_id),
                "repository_id": str(side.repository_id),
                "repository_side": side.repository_side,
                "workspace": side.workspace,
                "repository_slug": side.repository_slug,
                "branch": side.configured_branch,
                "commit_hash": side.commit_hash,
                "import_execution_id": str(mapping.execution_id),
            }
            for side in mapping.sides
        ]
        formats = {file.authority: file.parser_input.format for file in prepared.authority.files}
        session.add(
            ChangeSetItem(
                change_set_id=group.id,
                proposal_id=proposal.proposal_id,
                proposal_version=proposal.version,
                repository_id=group.repository_id,
                provider_repository_id=group.provider_repository_id,
                target_branch=group.target_branch,
                key_id=proposal.key_id,
                language=proposal.language,
                members=[
                    {
                        "value_id": str(member.value_id),
                        "selector_version": member.selector_version,
                        "selector_digest": member.selector_digest,
                        "selector_kind": member.edit.selector.kind,
                        "selector": member.edit.selector.fields,
                        "basis_revision_number": member.basis_revision_number,
                        "basis_digest": member.basis_digest,
                        "path": member.authority.path,
                        "key": member.edit.logical_key,
                        "published_text": member.edit.expected_text,
                        "proposed_text": member.edit.replacement_text,
                        "source": next(
                            source
                            for source in sources
                            if source["repository_side"] == member.authority.repository_side
                        ),
                        "sources": sources if index == 0 else [],
                        "format": formats[member.authority],
                        "file_changed_values": file_changed_values[member.authority.path],
                    }
                    for index, member in enumerate(proposal.members)
                ],
            )
        )
    for file in prepared.files:
        if file.attributes is None:
            raise SubmissionConflict("invalid_snapshot")
        session.add(
            ChangeSetFile(
                id=uuid4(),
                change_set_id=group.id,
                repository_id=group.repository_id,
                provider_repository_id=group.provider_repository_id,
                target_branch=group.target_branch,
                path=file.authority.path,
                original_bytes=file.original_bytes,
                content=file.content,
                before_sha256=hashlib.sha256(file.original_bytes).hexdigest(),
                after_sha256=hashlib.sha256(file.content).hexdigest(),
                attributes=list(file.attributes),
            )
        )


def create_submission_batch(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    request: CreateSubmissionBatchRequest,
    enqueuer: SubmissionEnqueuer = enqueue_submission,
) -> SubmissionBatchResponse:
    request_digest = hashlib.sha256(
        json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    dispatch: list[UUID] = []
    try:
        with session.begin():
            product, actor = _product_actor(session, product_id, actor_id, action=True)
            from verboflex.services.branch_workflow import workflow_for

            if workflow_for(session, product_id) is not None:
                raise SubmissionConflict("approval_branch_enabled")
            existing = session.scalar(
                select(SubmissionBatch).where(
                    SubmissionBatch.product_id == product_id,
                    SubmissionBatch.actor_id == actor_id,
                    SubmissionBatch.request_key == request.request_key,
                )
            )
            if existing is not None:
                if existing.request_digest != request_digest:
                    raise SubmissionConflict("idempotency_conflict")
                return _batch_response(session, existing, actor_id)
            review = session.scalar(
                select(SubmissionReview)
                .where(
                    SubmissionReview.id == request.review_id,
                    SubmissionReview.product_id == product_id,
                    SubmissionReview.actor_id == actor_id,
                )
                .with_for_update()
            )
            if review is None:
                raise SubmissionReviewUnavailable("submission unavailable")
            now = datetime.now(UTC)
            if (
                review.accepted_at is not None
                or review.state != "ready"
                or review.expires_at <= now
                or review.attempt != request.expected_review_attempt
                or review.revision_id != product.active_revision_id
                or review.actor_token_version != actor.token_version
            ):
                raise SubmissionConflict("stale_review")
            prepared = _load_prepared(session, review)
            if prepared.content_digest != request.expected_content_digest:
                raise SubmissionConflict("stale_review")
            # One deterministic batch-wide lock order, before any per-group capture.
            scope_ids = {m.scope_id for g in prepared.groups for m in g.prepared.authority.mappings}
            session.execute(
                select(LocalizationScope.id)
                .where(LocalizationScope.id.in_(scope_ids))
                .order_by(LocalizationScope.id)
                .with_for_update()
            ).all()
            for group in prepared.groups:
                fresh = _normalize(
                    capture_writeback_authority(session, selection=group.prepared.selection)
                )
                if fresh != group.prepared.authority:
                    raise WritebackRejected(WritebackReason.STALE_BASIS)
                if any(
                    m.product_id != product_id or m.revision_id != review.revision_id
                    for m in fresh.mappings
                ):
                    raise WritebackRejected(WritebackReason.STALE_BASIS)
            batch = SubmissionBatch(
                id=uuid4(),
                product_id=product_id,
                revision_id=review.revision_id,
                actor_id=actor_id,
                actor_token_version=actor.token_version,
                review_id=review.id,
                review_attempt=review.attempt,
                request_key=request.request_key,
                request_digest=request_digest,
                content_digest=prepared.content_digest,
            )
            session.add(batch)
            session.flush()
            for group in prepared.groups:
                _persist_group(session, batch, group)
                dispatch.append(group.id)
            review.accepted_at = now
            session.flush()
            result = _batch_response(session, batch, actor_id)
    except IntegrityError:
        raise SubmissionConflict("destination_claimed") from None
    except WritebackRejected:
        # Invalidate only unaccepted authority; a new review must run asynchronously.
        with session.begin():
            session.execute(
                select(Product.id).where(Product.id == product_id).with_for_update()
            ).all()
            session.execute(
                update(SubmissionReview)
                .where(
                    SubmissionReview.id == request.review_id,
                    SubmissionReview.actor_id == actor_id,
                    SubmissionReview.product_id == product_id,
                    SubmissionReview.accepted_at.is_(None),
                )
                .values(expires_at=datetime.now(UTC))
            )
        raise
    for group_id in dispatch:
        with suppress(Exception):
            enqueuer(group_id)
    return result


def get_submission_batch_by_key(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    request_key: UUID,
) -> SubmissionBatchResponse:
    with session.begin():
        _product_actor(session, product_id, actor_id, action=False)
        row = session.scalar(
            select(SubmissionBatch).where(
                SubmissionBatch.product_id == product_id,
                SubmissionBatch.actor_id == actor_id,
                SubmissionBatch.request_key == request_key,
            )
        )
        if row is None:
            raise SubmissionReviewUnavailable("submission unavailable")
        return _batch_response(session, row, actor_id)


def get_submission_batch(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    batch_id: UUID,
) -> SubmissionBatchResponse:
    with session.begin():
        _product_actor(session, product_id, actor_id, action=False)
        row = session.scalar(
            select(SubmissionBatch).where(
                SubmissionBatch.product_id == product_id,
                SubmissionBatch.id == batch_id,
            )
        )
        if row is None:
            raise SubmissionReviewUnavailable("submission unavailable")
        return _batch_response(session, row, actor_id)


def get_change_set(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    change_set_id: UUID,
) -> ChangeSetResponse:
    with session.begin():
        _product_actor(session, product_id, actor_id, action=False)
        row = session.scalar(
            select(ChangeSet)
            .join(SubmissionBatch)
            .where(
                ChangeSet.id == change_set_id,
                SubmissionBatch.product_id == product_id,
            )
        )
        if row is None:
            raise SubmissionReviewUnavailable("submission unavailable")
        return change_set_response(row, session=session, actor_id=actor_id)
