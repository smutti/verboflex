"""Durable, permission-checked creation of filename-localized HTML peers."""

import base64
import hashlib
import json
from pathlib import PurePosixPath
from typing import Annotated
from uuid import UUID

from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from verboflex.audit.ledger import record_audit
from verboflex.auth.product_access import membership_stamp
from verboflex.localization.html import html_path
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.preview.core import normalize_preview_locale
from verboflex.localization.writing.core import WriteEdit
from verboflex.localization.writing.registry import render_file
from verboflex.models.branch_workflow import BranchJob, BranchWorkflow
from verboflex.models.translation import LocalizationScope
from verboflex.schemas.submissions import ClosedModel
from verboflex.schemas.translations import LanguageCode
from verboflex.services.branch_workflow import BranchWorkflowError, active_mapping, workflow_for
from verboflex.services.import_jobs import confirmed_file_parser_input
from verboflex.services.submission_reviews import _product_actor
from verboflex.services.submission_selection import SubmissionReadAdapter
from verboflex.services.writeback_authority import _capture_mapping, build_source_file_snapshot


class CreateHtmlLanguage(ClosedModel):
    workflow_id: UUID
    language: LanguageCode
    # Optional reviewed source material, e.g. an administrator's spreadsheet import.
    translations: Annotated[dict[str, str], Field(max_length=5000)] = {}

    @model_validator(mode="after")
    def bounded(self) -> CreateHtmlLanguage:
        path = html_path("Template-" + self.language.upper() + ".html")
        if path is None or path[0] != self.language:
            raise ValueError("Unsupported HTML filename locale")
        if sum(len(k) + len(v) for k, v in self.translations.items()) > 2_097_152:
            raise ValueError("HTML translations exceed the request limit")
        return self


def queue_language(
    session: Session,
    *,
    product_id: UUID,
    actor_id: UUID,
    body: CreateHtmlLanguage,
) -> BranchJob:
    _product_actor(session, product_id, actor_id, action=True)
    workflow = workflow_for(session, product_id, lock=True, workflow_id=body.workflow_id)
    if workflow is None or (mapping := active_mapping(session, workflow)) is None:
        raise BranchWorkflowError("Configure approval branches first")
    scope = session.scalar(
        select(LocalizationScope).where(
            LocalizationScope.product_id == product_id,
            LocalizationScope.current_mapping_id == mapping.id,
        )
    )
    if scope is None or scope.active_execution_id is None:
        raise BranchWorkflowError("Import the HTML source first")
    captured, layouts = _capture_mapping(session, scope, reference_limit=500, byte_limit=20971520)
    if len(layouts) != 1 or layouts[0].format != "html" or mapping.topology != "direct":
        raise BranchWorkflowError("Select a direct HTML template collection")
    if body.language == captured.base_language or body.language in scope.language_counts:
        raise BranchWorkflowError("This language already exists")
    if any(ref.configured_branch != workflow.work_branch for ref in captured.source_references):
        raise BranchWorkflowError(
            "Import from the configured working branch before adding a language"
        )
    pending = session.scalar(
        select(BranchJob.id)
        .where(
            BranchJob.workflow_id == workflow.id,
            BranchJob.state.in_(("queued", "running", "sending", "blocked", "open")),
        )
        .limit(1)
    )
    if pending is not None:
        raise BranchWorkflowError("Finish the pending branch operation first")
    authority = {
        "scope_id": str(scope.id),
        "execution_id": str(scope.active_execution_id),
        "language": body.language,
        "translations": body.translations,
    }
    job = BranchJob(
        workflow_id=workflow.id,
        actor_id=actor_id,
        membership=membership_stamp(session, actor_id, product_id),
        kind="html_language",
        state="queued",
        label=f"HTML language: {body.language}",
        authority=json.dumps(authority, ensure_ascii=False).encode(),
    )
    session.add(job)
    session.flush()
    record_audit(session, actor_id=actor_id, action="html.language_requested", entity_id=job.id)
    return job


def language_authority(
    session: Session, workflow: BranchWorkflow, job: BranchJob
) -> dict[str, object]:
    if job.authority is None:
        raise BranchWorkflowError("invalid_snapshot")
    data = json.loads(job.authority)
    scope = session.get(LocalizationScope, UUID(data["scope_id"]))
    mapping = active_mapping(session, workflow)
    if (
        scope is None
        or mapping is None
        or scope.product_id != workflow.product_id
        or scope.current_mapping_id != mapping.id
        or str(scope.active_execution_id) != data["execution_id"]
        or normalize_preview_locale(data["language"]) != data["language"]
    ):
        raise BranchWorkflowError("import_changed")
    return dict(data)


async def prepare_language_files(
    factory: sessionmaker[Session],
    workflow: BranchWorkflow,
    job: BranchJob,
    reads: SubmissionReadAdapter,
    *,
    head: str,
    workspace: str,
    slug: str,
) -> list[dict[str, object]]:
    with factory() as session:
        data = language_authority(session, workflow, job)
        scope = session.get_one(LocalizationScope, UUID(str(data["scope_id"])))
        captured, layouts = _capture_mapping(
            session, scope, reference_limit=500, byte_limit=20971520
        )
    language = str(data["language"])
    translations = data["translations"]
    if not isinstance(translations, dict):
        raise BranchWorkflowError("invalid_snapshot")
    remaining = set(translations)
    files: list[dict[str, object]] = []
    paths = {ref.path for ref in captured.source_references}
    for ref in captured.source_references:
        identity = html_path(ref.path)
        if identity is None or identity[0] != captured.base_language:
            continue
        if ref.commit_hash != head or ref.configured_branch != workflow.work_branch:
            raise BranchWorkflowError("import_changed")
        suffix = PurePosixPath(ref.path).suffix
        destination = identity[1] + identity[2] + language.upper() + suffix
        if destination in paths:
            raise BranchWorkflowError("file_exists")
        with factory() as session:
            metadata = await reads.read_repository_source_metadata(
                session,
                workspace=workspace,
                repository_slug=slug,
                commit_hash=head,
                path=ref.path,
            )
            content = await reads.read_repository_source_file(
                session,
                workspace=workspace,
                repository_slug=slug,
                commit_hash=head,
                path=ref.path,
                max_bytes=max(1, ref.size_bytes),
            )
        parser = confirmed_file_parser_input(
            layouts,
            repository_side=ref.repository_side,
            path=ref.path,
            content=content,
            base_language=captured.base_language,
        )
        if parser is None:
            raise BranchWorkflowError("invalid_snapshot")
        snapshot = build_source_file_snapshot(ref, parser, metadata)
        parsed = parse_canonical_snapshot(parser)
        if parsed.issues:
            raise BranchWorkflowError("unsupported_shape")
        edits = []
        for value in parsed.values:
            if value.logical_key in translations:
                replacement = translations[value.logical_key]
                if not isinstance(replacement, str):
                    raise BranchWorkflowError("invalid_snapshot")
                remaining.discard(value.logical_key)
                edits.append(
                    WriteEdit(
                        value.logical_key,
                        value.language,
                        value.selector,
                        value.locator,
                        value.display_text,
                        replacement,
                    )
                )
        rendered = render_file(snapshot, tuple(edits)).content
        files.append(
            {
                "path": destination,
                "before": hashlib.sha256(b"").hexdigest(),
                "content": base64.b64encode(rendered).decode(),
                "attributes": [],
                "new_file": True,
            }
        )
    if not files or remaining or len(files) > 100:
        raise BranchWorkflowError("invalid_language_sources")
    return files


def discard_language_job(
    session: Session, *, product_id: UUID, actor_id: UUID, job_id: UUID
) -> None:
    """Release an unsent failed request; uncertain provider effects remain recoverable."""
    _product_actor(session, product_id, actor_id, action=True)
    job = session.get(BranchJob, job_id)
    if job is None:
        raise BranchWorkflowError("Change unavailable")
    workflow = workflow_for(session, product_id, lock=True, workflow_id=job.workflow_id)
    session.refresh(job, with_for_update=True)
    if (
        workflow is None
        or job.kind not in {"html_language", "language"}
        or job.state != "blocked"
        or job.intent is not None
    ):
        raise BranchWorkflowError("Only an unsent failed language request can be discarded")
    job.state, job.owner, job.error_code = "declined", None, None
    record_audit(
        session,
        actor_id=actor_id,
        action="language.discarded" if job.kind == "language" else "html.language_discarded",
        entity_id=job.id,
    )
