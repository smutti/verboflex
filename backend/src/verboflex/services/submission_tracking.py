"""Live PR observations, separate from immutable evidence of the original send."""

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session, sessionmaker

from verboflex.integrations.bitbucket.writes import (
    MAX_TOTAL_BYTES,
    BitbucketWriteAdapter,
    BranchIntent,
    CommitFile,
    CommitIntent,
    PullRequestIntent,
    PullRequestReceipt,
    _WireError,
)
from verboflex.localization.writing.core import WritebackRejected
from verboflex.localization.writing.rebase import replay_approved_edits
from verboflex.models.submission import ChangeSetEvent
from verboflex.schemas.submissions import PullRequestTracking
from verboflex.services.submissions import ChangeSetBundle

if TYPE_CHECKING:
    from verboflex.services.submission_jobs import AttemptIdentity


async def track_pull_request(
    factory: sessionmaker[Session],
    *,
    identity: AttemptIdentity,
    bundle: ChangeSetBundle,
    writes: BitbucketWriteAdapter,
    intent: PullRequestIntent,
    pull_request_id: int,
    digest: str,
) -> None:
    receipt: PullRequestReceipt | None = None
    tracking: PullRequestTracking | None = None
    error: str | None = None
    try:
        with factory() as session:
            result = await writes.read_pull_request(
                session,
                intent=intent,
                pull_request_id=pull_request_id,
                allow_rebased=True,
            )
            if result.state != "verified" or result.receipt is None:
                error = (
                    "pr_identity_changed" if result.state == "conflict" else "pr_check_unavailable"
                )
            else:
                receipt = result.receipt
                tracking = PullRequestTracking(
                    source_commit=receipt.source_commit,
                    target_commit=receipt.target_commit,
                    content_status="original"
                    if receipt.source_commit == intent.source_commit
                    else "unverified",
                    merge_status="not_applicable",
                    checked_at=datetime.now(UTC),
                )
                if receipt.state == "OPEN":
                    tracking.merge_status = await writes.read_pr_merge_status(
                        session,
                        context=intent.context,
                        pull_request_id=pull_request_id,
                    )
                    if tracking.merge_status == "conflicts":
                        error = "pr_merge_conflicts"
                    elif tracking.merge_status == "unknown":
                        error = "pr_check_unavailable"
                    elif receipt.source_commit != intent.source_commit:
                        await _verify_rebased_files(session, bundle, writes, intent, receipt)
                        tracking.content_status = "verified"
                # Bind the merge check and byte verification to the same live PR heads.
                latest = await writes.read_pull_request(
                    session,
                    intent=intent,
                    pull_request_id=pull_request_id,
                    allow_rebased=True,
                )
                if latest.state != "verified" or latest.receipt != receipt:
                    error = "pr_changed_during_check"
                    tracking.content_status, tracking.merge_status = "unverified", "unknown"
    except WritebackRejected:
        error = "pr_content_changed"
        if tracking is not None:
            tracking.content_status = "changed"
    except _WireError as failure:
        error = "pr_content_changed" if failure.state == "conflict" else "pr_check_unavailable"
        if tracking is not None:
            tracking.content_status = "changed" if failure.state == "conflict" else "unverified"
            tracking.merge_status = "unknown"
    except Exception:
        error = "pr_check_unavailable"
        if tracking is not None:
            tracking.content_status, tracking.merge_status = "unverified", "unknown"
    if tracking is not None:
        tracking.checked_at = datetime.now(UTC)
    _record_status(factory, identity, receipt, tracking, error, digest)


async def _verify_rebased_files(
    session: Session,
    bundle: ChangeSetBundle,
    writes: BitbucketWriteAdapter,
    intent: PullRequestIntent,
    receipt: PullRequestReceipt,
) -> None:
    files = []
    input_bytes = output_bytes = 0
    for original in bundle.group.prepared.files:
        captured = next(
            f
            for f in bundle.group.prepared.authority.files
            if f.authority.repository_id == original.authority.repository_id
            and f.authority.path == original.authority.path
        )
        if original.attributes is None:
            raise ValueError("Missing file authority")
        base = await writes.read_rebase_file(
            session,
            context=intent.context,
            commit=receipt.target_commit,
            path=original.authority.path,
            attributes=original.attributes,
            max_bytes=MAX_TOTAL_BYTES - input_bytes,
        )
        input_bytes += len(base)
        expected = replay_approved_edits(
            replace(captured.parser_input, content=base),
            original.changed_edits,
        )
        output_bytes += len(expected)
        if output_bytes > MAX_TOTAL_BYTES:
            raise ValueError("Rebase verification limit")
        files.append(
            CommitFile(
                original.authority.path,
                expected,
                hashlib.sha256(base).hexdigest(),
                original.attributes,
            )
        )
    await writes.verify_commit_files(
        session,
        intent=CommitIntent(
            BranchIntent(intent.context, receipt.target_commit),
            intent.manifest_digest,
            tuple(files),
        ),
        commit=receipt.source_commit,
    )


def _record_status(
    factory: sessionmaker[Session],
    identity: AttemptIdentity,
    receipt: PullRequestReceipt | None,
    tracking: PullRequestTracking | None,
    error: str | None,
    digest: str,
) -> None:
    from verboflex.services.submission_jobs import _clear_owner, _lock_group, _owns, _receipt_data
    from verboflex.services.submission_recovery import (
        effect_summary,
        release_verified_terminal_claims,
    )

    with factory.begin() as session:
        row = _lock_group(session, identity.change_set_id)
        if row is None:
            return
        # These observations must never be folded into the original send's SHA signature.
        data = _receipt_data(receipt)
        data["tracking"] = tracking.model_dump(mode="json") if tracking else None
        session.add(
            ChangeSetEvent(
                change_set_id=row.id,
                attempt=identity.attempt,
                execution_fence=identity.execution_fence,
                proof_sequence=identity.proof_sequence,
                event_kind="pr_status",
                step="pull_request",
                outcome="verified"
                if error is None
                else "unknown"
                if error in {"pr_check_unavailable", "pr_changed_during_check"}
                else "conflict",
                request_digest=digest,
                receipt=data,
            )
        )
        if not _owns(row, identity):
            return
        if receipt is not None and (
            receipt.id != row.pr_id
            or (
                row.pr_state in {"MERGED", "DECLINED", "SUPERSEDED"}
                and receipt.state != row.pr_state
            )
        ):
            error, tracking = "pr_identity_changed", None
        row.pr_tracking = tracking.model_dump(mode="json") if tracking else None
        if receipt is not None and error != "pr_identity_changed":
            row.pr_state, row.pr_url = receipt.state, receipt.url
            row.pr_target_commit = receipt.target_commit
        if error is None and effect_summary(session, row).unresolved:
            error = "unresolved_evidence"
        row.error_code = error
        row.status = "succeeded" if error is None else "needs_attention"
        row.finished_at = datetime.now(UTC)
        if error is None and release_verified_terminal_claims(session, row):
            return
        _clear_owner(row)
