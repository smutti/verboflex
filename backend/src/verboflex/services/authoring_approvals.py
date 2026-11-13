"""Atomic project-wide approval with a durable, version-bound database outbox."""

import hashlib
import json
import logging
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from verboflex.audit.ledger import record_audit
from verboflex.auth.product_access import membership_stamp
from verboflex.localization.writing.core import WritebackRejected
from verboflex.models.authoring import AuthoringRequest
from verboflex.models.authoring_approval import AuthoringApproval
from verboflex.models.product import Product
from verboflex.models.translation import LocalizationScope
from verboflex.schemas.authoring_approval import AuthoringApprovalPreview, AuthoringApprovalStatus
from verboflex.services import translation_authoring as authoring
from verboflex.services.branch_workflow import BranchWorkflowError, queue_authoring_batch
from verboflex.services.writeback_authority import ProposalSelection

MAX_DRAFTS = 5000
logger = logging.getLogger(__name__)


def status(row: AuthoringApproval) -> AuthoringApprovalStatus:
    return AuthoringApprovalStatus(
        id=row.id,
        state=cast(Literal["queued", "succeeded", "failed"], row.state),
        count=len(row.selection),
        error=row.error,
        branch_job_ids=[UUID(v) for v in row.branch_job_ids],
        created_at=row.created_at,
    )


def _snapshot(
    session: Session, product: Product
) -> tuple[list[dict[str, object]], int, dict[str, int], str]:
    rows = session.execute(
        select(
            AuthoringRequest.id,
            AuthoringRequest.version,
            AuthoringRequest.language,
            AuthoringRequest.payload["input"]["execution_id"].as_string(),
            LocalizationScope.active_execution_id,
        )
        .join(LocalizationScope, LocalizationScope.id == AuthoringRequest.scope_id)
        .where(
            LocalizationScope.product_id == product.id,
            LocalizationScope.current_revision_id == product.active_revision_id,
            AuthoringRequest.state == "draft",
        )
        .order_by(AuthoringRequest.id)
        .limit(MAX_DRAFTS + 1)
    ).all()
    selection = [{"id": str(r[0]), "version": r[1]} for r in rows]
    digest = hashlib.sha256(
        json.dumps(
            [str(product.active_revision_id), [(str(r[0]), r[1], str(r[4])) for r in rows]],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return (
        selection,
        sum(r[3] != str(r[4]) for r in rows),
        dict(Counter(r[2] for r in rows)),
        digest,
    )


def preview(session: Session, *, product_id: UUID, actor_id: UUID) -> AuthoringApprovalPreview:
    # Polling must not wait for the worker's product lock during atomic validation.
    product = authoring._product(session, product_id, actor_id, "review", lock=False)
    selection, changed, languages, digest = _snapshot(session, product)
    latest = session.scalar(
        select(AuthoringApproval)
        .where(
            AuthoringApproval.product_id == product_id,
        )
        .order_by(AuthoringApproval.created_at.desc(), AuthoringApproval.id.desc())
        .limit(1)
    )
    return AuthoringApprovalPreview(
        count=len(selection),
        languages=languages,
        source_changed=changed,
        over_limit=len(selection) > MAX_DRAFTS,
        fingerprint=digest,
        latest=status(latest) if latest else None,
    )


def create(
    session: Session, *, product_id: UUID, actor_id: UUID, request_id: UUID, fingerprint: str
) -> AuthoringApprovalStatus:
    product = authoring._product(session, product_id, actor_id, "review")
    existing = session.get(AuthoringApproval, request_id)
    if existing is not None:
        if (existing.product_id, existing.actor_id, existing.fingerprint) != (
            product_id,
            actor_id,
            fingerprint,
        ):
            raise authoring.AuthoringError("Approval request identifier is already in use", 409)
        return status(existing)
    if session.scalar(
        select(AuthoringApproval.id).where(
            AuthoringApproval.product_id == product_id,
            AuthoringApproval.state == "queued",
        )
    ):
        raise authoring.AuthoringError("A bulk approval is already in progress", 409)
    selection, changed, _, digest = _snapshot(session, product)
    if digest != fingerprint:
        raise authoring.AuthoringError(
            "Drafts or sources changed. Refresh the approval preview", 409
        )
    if not selection or len(selection) > MAX_DRAFTS:
        raise authoring.AuthoringError("Select a project with between 1 and 5000 drafts", 422)
    if changed:
        raise authoring.AuthoringError(
            "Refresh the translation source before approving drafts", 409
        )
    row = AuthoringApproval(
        id=request_id,
        product_id=product_id,
        actor_id=actor_id,
        membership=membership_stamp(session, actor_id, product_id),
        fingerprint=digest,
        selection=selection,
        state="queued",
        branch_job_ids=[],
    )
    session.add(row)
    session.flush()
    record_audit(session, actor_id=actor_id, action="authoring.bulk_queued", entity_id=row.id)
    return status(row)


def execute(factory: sessionmaker[Session], *, job_id: UUID) -> None:
    # The row lock is the claim: duplicate delivery skips it, crashes roll back and
    # the durable dispatcher retries. Approval, audit and branch outbox commit together.
    with factory.begin() as session:
        job = session.scalar(
            select(AuthoringApproval)
            .where(
                AuthoringApproval.id == job_id,
                AuthoringApproval.state == "queued",
            )
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return
        try:
            with session.begin_nested():
                product = authoring._product(session, job.product_id, job.actor_id, "review")
                if membership_stamp(session, job.actor_id, job.product_id) != job.membership:
                    raise authoring.AuthoringError(
                        "Reviewer permissions changed. Start a new approval", 403
                    )
                groups: dict[UUID, list[ProposalSelection]] = defaultdict(list)
                for selected in job.selection:
                    row = session.get(AuthoringRequest, UUID(str(selected["id"])))
                    if row is None or row.state != "draft" or row.version != selected["version"]:
                        raise authoring.AuthoringError(
                            "A selected draft changed. Refresh and try again", 409
                        )
                    scope = authoring._scope(session, product, row.scope_id)
                    try:
                        authoring.validate_approval(session, scope, row)
                    except authoring.AuthoringError as error:
                        raise authoring.AuthoringError(
                            f"{row.raw_key} ({row.language}): {error}",
                            error.status,
                        ) from error
                    row.version += 1
                    row.state, row.updated_by, row.updated_at = (
                        "approved",
                        job.actor_id,
                        datetime.now(UTC),
                    )
                    record_audit(
                        session,
                        actor_id=job.actor_id,
                        action="authoring.approved",
                        entity_id=row.id,
                    )
                    groups[scope.current_mapping_id].append(ProposalSelection(row.id, row.version))
                session.flush()
                branch_ids = []
                for mapping_id, proposals in groups.items():
                    branch_id = queue_authoring_batch(
                        session,
                        product_id=job.product_id,
                        actor_id=job.actor_id,
                        proposals=tuple(proposals),
                        activity_id=uuid5(job.id, str(mapping_id)),
                    )
                    if branch_id:
                        branch_ids.append(str(branch_id))
                job.branch_job_ids, job.state = branch_ids, "succeeded"
                record_audit(
                    session,
                    actor_id=job.actor_id,
                    action="authoring.bulk_approved",
                    entity_id=job.id,
                )
        except (authoring.AuthoringError, BranchWorkflowError, WritebackRejected) as error:
            job.state, job.error = "failed", str(error)[:1024]
        except Exception:
            logger.exception("Bulk authoring approval failed: %s", job.id)
            job.state, job.error = (
                "failed",
                "Approval could not complete. Your drafts are unchanged. Try again.",
            )
        job.finished_at = datetime.now(UTC)
