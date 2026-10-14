"""Serial, durable Git effects for approved snapshots. All provider I/O runs in Celery."""

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from verboflex.auth.product_access import membership_stamp, product_roles
from verboflex.integrations.bitbucket.writes import (
    BitbucketWriteAdapter,
    BranchIntent,
    CommitFile,
    CommitIntent,
    CommitReceipt,
    PullRequestIntent,
    PullRequestReceipt,
    WriteContext,
    WriteOutcome,
)
from verboflex.localization.importing.core import (
    MAX_CANONICAL_AGGREGATE_BYTES,
)
from verboflex.localization.writing.core import WritebackRejected
from verboflex.localization.writing.registry import render_file
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.branch_workflow import BranchFile, BranchJob, BranchWorkflow
from verboflex.models.product import Product
from verboflex.models.repository import Repository
from verboflex.models.translation import LocalizationScope, TranslationKey
from verboflex.services.branch_workflow import BranchWorkflowError, active_mapping
from verboflex.services.submission_codec import decode_approval_snapshot, encode_approval_snapshot
from verboflex.services.submission_selection import (
    SubmissionReadAdapter,
    provider_repository_identity,
)
from verboflex.services.writeback import _edit_identity, _side, _snapshot
from verboflex.services.writeback_authority import CapturedWritebackAuthority

LEASE = timedelta(minutes=10)
TERMINAL = ("committed", "open", "merged", "declined")


def _branch_file(session: Session, workflow_id: UUID, path: str) -> BranchFile | None:
    # A bounded index supports long repository paths. Never trust the digest alone.
    digest = hashlib.md5(path.encode(), usedforsecurity=False).hexdigest()
    row = session.get(BranchFile, (workflow_id, digest))
    if row is not None and row.path != path:
        raise BranchWorkflowError("file_identity_conflict")
    return row


def _lock(session: Session, job_id: UUID) -> tuple[BranchWorkflow, BranchJob]:
    workflow_id = session.scalar(select(BranchJob.workflow_id).where(BranchJob.id == job_id))
    workflow = session.get(BranchWorkflow, workflow_id)
    if workflow is None:
        raise BranchWorkflowError("Change unavailable")
    session.execute(
        select(Product.id).where(Product.id == workflow.product_id).with_for_update(read=True)
    ).one()
    session.execute(
        select(BranchWorkflow.id).where(BranchWorkflow.id == workflow.id).with_for_update()
    ).one()
    return workflow, session.get_one(BranchJob, job_id, populate_existing=True)


def _authorize(session: Session, workflow: BranchWorkflow, job: BranchJob) -> None:
    product = session.get_one(Product, workflow.product_id, populate_existing=True)
    mapping = active_mapping(session, workflow)
    if (
        not product.is_active
        or product.deleted_at is not None
        or mapping is None
        or not {"admin", "product_manager_reviewer"}.intersection(
            product_roles(session, job.actor_id, product.id)
        )
        or membership_stamp(session, job.actor_id, product.id) != job.membership
    ):
        raise BranchWorkflowError("authority_changed")
    if job.authority is not None:
        captured = decode_approval_snapshot(job.authority)
        if not isinstance(captured, CapturedWritebackAuthority):
            raise BranchWorkflowError("invalid_snapshot")
        for m in captured.mappings:
            scope = session.get(LocalizationScope, m.scope_id, populate_existing=True)
            if (
                scope is None
                or m.mapping_id != mapping.id
                or scope.current_mapping_id != mapping.id
                or scope.active_execution_id != m.execution_id
            ):
                raise BranchWorkflowError("import_changed")
        for p in captured.proposals:
            key = session.get(TranslationKey, p.key_id, populate_existing=True)
            if key is not None and (
                key.is_deleted or key.constraint_generation != p.constraint_generation
            ):
                raise BranchWorkflowError("constraints_changed")


def _context(workflow: BranchWorkflow, job: BranchJob, data: dict[str, object]) -> WriteContext:
    return WriteContext(
        UUID(str(data["provider_id"])),
        str(data["workspace"]),
        str(data["repository"]),
        job.id,
        int(str(data["generation"])),
        workflow.work_branch,
    )


def _intent(workflow: BranchWorkflow, job: BranchJob) -> CommitIntent | PullRequestIntent:
    if job.intent is None:
        raise BranchWorkflowError("invalid_snapshot")
    data = job.intent
    context = _context(workflow, job, data)
    if job.kind == "pull_request":
        return PullRequestIntent(
            context,
            str(data["parent"]),
            workflow.target_branch,
            str(data["target_head"]),
            str(data["manifest"]),
        )
    files = cast(list[dict[str, object]], data["files"])
    return CommitIntent(
        BranchIntent(context, str(data["parent"])),
        str(data["manifest"]),
        tuple(
            CommitFile(
                str(f["path"]),
                base64.b64decode(str(f["content"]), validate=True),
                str(f["before"]),
                tuple(cast(list[str], f["attributes"])),
            )
            for f in files
        ),
    )


async def _prepare(
    factory: sessionmaker[Session],
    workflow: BranchWorkflow,
    job: BranchJob,
    reads: SubmissionReadAdapter,
) -> dict[str, object]:
    with factory() as s:
        repository = s.get_one(Repository, workflow.repository_id)
        workspace, slug = repository.workspace, repository.repository_slug
    provider_id = await provider_repository_identity(
        factory, workspace=workspace, repository_slug=slug, adapter=reads
    )
    with factory() as s:
        head = await reads.resolve_repository_branch(
            s, workspace=workspace, repository_slug=slug, branch=workflow.work_branch
        )
    if head.name != workflow.work_branch:
        raise BranchWorkflowError("branch_changed")
    with factory() as s:
        connection = s.get_one(BitbucketConnection, 1)
        generation = connection.generation
    data: dict[str, object] = {
        "provider_id": str(provider_id),
        "workspace": workspace,
        "repository": slug,
        "generation": generation,
        "parent": head.commit_hash,
    }
    if job.kind == "pull_request":
        with factory() as s:
            target = await reads.resolve_repository_branch(
                s, workspace=workspace, repository_slug=slug, branch=workflow.target_branch
            )
        if target.name != workflow.target_branch or target.commit_hash == head.commit_hash:
            raise BranchWorkflowError("no_changes")
        data["target_head"] = target.commit_hash
    else:
        if job.authority is None:
            raise BranchWorkflowError("invalid_snapshot")
        captured = decode_approval_snapshot(job.authority)
        if not isinstance(captured, CapturedWritebackAuthority):
            raise BranchWorkflowError("invalid_snapshot")
        files: list[dict[str, object]] = []
        total = 0
        for file in captured.files:
            if (
                file.authority.repository_id != workflow.repository_id
                or file.authority.repository_side == "keys"
            ):
                raise BranchWorkflowError("invalid_destination")
            snapshot = await _snapshot(
                factory,
                file,
                _side(captured, file),
                reads,
                remaining=MAX_CANONICAL_AGGREGATE_BYTES - total,
            )
            total += len(snapshot.parser_input.content)
            with factory() as s:
                previous = _branch_file(s, workflow.id, file.authority.path)
                adopted = False
                if previous is not None and previous.baseline_sha256 != file.authority.sha256:
                    # A refreshed import can incorporate our already-merged file.
                    # Only adopt bytes identical to the last verified branch file.
                    if previous.content_sha256 != file.authority.sha256:
                        raise BranchWorkflowError("import_changed")
                    adopted = True
                old_edits = (
                    decode_approval_snapshot(previous.edits) if previous and not adopted else ()
                )
                if not isinstance(old_edits, tuple):
                    raise BranchWorkflowError("invalid_snapshot")
                expected = previous.content_sha256 if previous else file.authority.sha256
            edits = {_edit_identity(e): e for e in old_edits}
            edits.update({_edit_identity(e): e for e in file.edits})
            operations = tuple(edits[k] for k in sorted(edits))
            rendered = render_file(snapshot, operations)
            with factory() as s:
                metadata = await reads.read_repository_source_metadata(
                    s,
                    workspace=workspace,
                    repository_slug=slug,
                    commit_hash=head.commit_hash,
                    path=file.authority.path,
                )
                if metadata.attributes != snapshot.attributes or metadata.size_bytes > 1_048_576:
                    raise BranchWorkflowError("file_changed")
                current = await reads.read_repository_source_file(
                    s,
                    workspace=workspace,
                    repository_slug=slug,
                    commit_hash=head.commit_hash,
                    path=file.authority.path,
                    max_bytes=max(1, metadata.size_bytes),
                )
            if hashlib.sha256(current).hexdigest() != expected:
                raise BranchWorkflowError("file_changed")
            files.append(
                {
                    "path": file.authority.path,
                    "before": expected,
                    "content": base64.b64encode(rendered.content).decode(),
                    "baseline": file.authority.sha256,
                    "after": rendered.after_sha256,
                    "edits": base64.b64encode(encode_approval_snapshot(operations)).decode(),
                    "attributes": list(snapshot.attributes or ()),
                }
            )
        if len({str(f["path"]) for f in files}) != len(files):
            raise BranchWorkflowError("duplicate_file")
        data["files"] = files
    data["manifest"] = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return data


def _sent(factory: sessionmaker[Session], job_id: UUID, owner: UUID, generation: int) -> bool:
    with factory.begin() as s:
        workflow, job = _lock(s, job_id)
        if job.owner != owner or job.state != "running":
            return False
        try:
            _authorize(s, workflow, job)
            connection = s.get_one(BitbucketConnection, 1)
            if connection.generation != generation:
                return False
        except BranchWorkflowError, ValueError:
            return False
        job.state, job.updated_at = "sending", datetime.now(UTC)
        return True


def _record(
    factory: sessionmaker[Session],
    job_id: UUID,
    owner: UUID,
    outcome: WriteOutcome[CommitReceipt] | WriteOutcome[PullRequestReceipt],
) -> None:
    with factory.begin() as s:
        workflow, job = _lock(s, job_id)
        if job.owner != owner:
            return
        job.owner, job.updated_at = None, datetime.now(UTC)
        if outcome.state != "verified" or outcome.receipt is None:
            if job.state == "running":
                job.intent = None
            job.state, job.error_code = "blocked", outcome.code
            return
        if isinstance(outcome.receipt, CommitReceipt):
            receipt = outcome.receipt
            job.state, job.commit_hash, job.error_code = "committed", receipt.commit_hash, None
            assert job.intent is not None
            for f in cast(list[dict[str, object]], job.intent["files"]):
                row = _branch_file(s, workflow.id, str(f["path"]))
                if row is None:
                    row = BranchFile(workflow_id=workflow.id, path=str(f["path"]))
                    s.add(row)
                row.baseline_sha256, row.content_sha256 = str(f["baseline"]), str(f["after"])
                row.edits = base64.b64decode(str(f["edits"]), validate=True)
        else:
            pr_receipt = outcome.receipt
            job.state = {
                "OPEN": "open",
                "MERGED": "merged",
                "DECLINED": "declined",
                "SUPERSEDED": "declined",
            }[pr_receipt.state]
            job.pr_id, job.pr_url, job.commit_hash = (
                pr_receipt.id,
                pr_receipt.url,
                pr_receipt.source_commit,
            )
            job.error_code = None


async def execute_branch_job(
    factory: sessionmaker[Session],
    *,
    job_id: UUID,
    reads: SubmissionReadAdapter,
    writes: BitbucketWriteAdapter,
) -> None:
    owner = uuid4()
    with factory.begin() as s:
        workflow, job = _lock(s, job_id)
        if job.state in TERMINAL:
            return
        earlier = s.scalar(
            select(BranchJob.id)
            .where(
                BranchJob.workflow_id == workflow.id,
                BranchJob.sequence < job.sequence,
                BranchJob.state.not_in(TERMINAL),
            )
            .limit(1)
        )
        if earlier or (job.owner is not None and job.updated_at > datetime.now(UTC) - LEASE):
            return
        if job.state == "blocked":
            return
        recovery = job.state == "sending"
        job.owner, job.updated_at = owner, datetime.now(UTC)
        if not recovery:
            try:
                _authorize(s, workflow, job)
            except BranchWorkflowError, ValueError:
                job.state, job.error_code, job.owner = "blocked", "authority_changed", None
                return
            job.state = "running"
        s.expunge(workflow)
        # Deferred payloads must be materialized before closing the session.
        _ = job.authority, job.intent
        s.expunge(job)
    try:
        if not recovery:
            prepared = await _prepare(factory, workflow, job, reads)
            with factory.begin() as s:
                current_workflow, current = _lock(s, job_id)
                if current.owner != owner or current.state != "running":
                    return
                _authorize(s, current_workflow, current)
                current.intent = prepared
            job.intent = prepared
        intent = _intent(workflow, job)
        with factory() as s:
            if recovery:
                outcome = (
                    await writes.reconcile_commit(s, intent=intent)
                    if isinstance(intent, CommitIntent)
                    else await writes.reconcile_pull_request(s, intent=intent)
                )
            else:
                context = (
                    intent.branch.context if isinstance(intent, CommitIntent) else intent.context
                )

                def callback() -> bool:
                    return _sent(factory, job_id, owner, context.expected_generation)

                outcome = (
                    await writes.create_commit(s, intent=intent, before_send=callback)
                    if isinstance(intent, CommitIntent)
                    else await writes.create_pull_request(s, intent=intent, before_send=callback)
                )
        _record(factory, job_id, owner, outcome)
    except Exception as error:
        with factory.begin() as s:
            _, current = _lock(s, job_id)
            if current.owner != owner:
                return
            # Never retry an uncertain send. The explicit recovery action only reads.
            sent = current.state == "sending"
            if not sent:
                current.intent = None
            code = (
                error.reason.value
                if isinstance(error, WritebackRejected)
                else str(error)
                if isinstance(error, BranchWorkflowError)
                else "provider_unavailable"
            )
            current.state, current.error_code, current.owner = "blocked", code[:64], None
            current.updated_at = datetime.now(UTC)


async def refresh_branch_pr(
    factory: sessionmaker[Session], *, job_id: UUID, writes: BitbucketWriteAdapter
) -> None:
    with factory() as s:
        job = s.get(BranchJob, job_id)
        if job is None or job.state != "open" or job.pr_id is None:
            return
        workflow = s.get_one(BranchWorkflow, job.workflow_id)
        intent = _intent(workflow, job)
        assert isinstance(intent, PullRequestIntent)
        pr_id = job.pr_id
    with factory() as s:
        outcome = await writes.read_pull_request(
            s, intent=intent, pull_request_id=pr_id, allow_rebased=True
        )
    with factory.begin() as s:
        _, current = _lock(s, job_id)
        if current.state == "open":
            current.updated_at = datetime.now(UTC)
            if outcome.state == "verified" and outcome.receipt is not None:
                current.state = {
                    "OPEN": "open",
                    "MERGED": "merged",
                    "DECLINED": "declined",
                    "SUPERSEDED": "declined",
                }[outcome.receipt.state]
                current.commit_hash = outcome.receipt.source_commit
