"""Durable creation of localization catalogs, using the existing serial Git outbox."""

import base64
import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, sessionmaker

from verboflex.audit.ledger import record_audit
from verboflex.auth.product_access import membership_stamp
from verboflex.localization.languages import initialize_language
from verboflex.localization.web.config import JsonCatalogProfile
from verboflex.localization.writing.core import SourceFileSnapshot
from verboflex.localization.writing.parsing import inspect_writeback_snapshot
from verboflex.models.branch_workflow import BranchJob, BranchWorkflow
from verboflex.models.product import ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.translation import LocalizationScope
from verboflex.schemas.submissions import ClosedModel
from verboflex.schemas.translations import LanguageCode
from verboflex.services.branch_workflow import BranchWorkflowError, active_mapping, workflow_for
from verboflex.services.html_languages import language_authority
from verboflex.services.import_jobs import confirmed_file_parser_input
from verboflex.services.submission_reviews import _product_actor
from verboflex.services.submission_selection import SubmissionReadAdapter
from verboflex.services.writeback_authority import _capture_mapping, require_source_file_metadata


class CreateProjectLanguage(ClosedModel):
    workflow_id: UUID
    language: LanguageCode


def queue_project_language(
    session: Session, *, product_id: UUID, actor_id: UUID, body: CreateProjectLanguage
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
        raise BranchWorkflowError("Import the source first")
    captured, _ = _capture_mapping(session, scope, reference_limit=500, byte_limit=20971520)
    if body.language == captured.base_language or body.language in scope.language_counts:
        raise BranchWorkflowError("This language already exists")
    if any(
        ref.configured_branch != workflow.work_branch
        for ref in captured.source_references
        if ref.repository_side != "keys"
    ):
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
    job = BranchJob(
        workflow_id=workflow.id,
        actor_id=actor_id,
        membership=membership_stamp(session, actor_id, product_id),
        kind="language",
        state="queued",
        label=f"Language: {body.language}",
        authority=json.dumps(
            {
                "scope_id": str(scope.id),
                "execution_id": str(scope.active_execution_id),
                "language": body.language,
            }
        ).encode(),
    )
    session.add(job)
    session.flush()
    record_audit(session, actor_id=actor_id, action="language.requested", entity_id=job.id)
    return job


def _profile_digest(profile: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def registered_catalog_profile(
    session: Session, mapping: ProductRepositoryMapping
) -> JsonCatalogProfile | None:
    """Extend an immutable allowlist only with verified, scope-bound creation receipts."""
    if mapping.localization_profile is None:
        return None
    profile = JsonCatalogProfile.model_validate(mapping.localization_profile)
    original = aliased(ProductRepositoryMapping)
    registrations = session.scalars(
        select(BranchJob.intent["catalog_registration"])
        .join(BranchWorkflow, BranchWorkflow.id == BranchJob.workflow_id)
        .join(original, original.id == BranchWorkflow.mapping_id)
        .where(
            original.identity_key == mapping.identity_key,
            BranchWorkflow.product_id
            == select(ProductRevision.product_id)
            .where(ProductRevision.id == mapping.revision_id)
            .scalar_subquery(),
            BranchJob.kind == "language",
            BranchJob.state == "committed",
        )
        .order_by(BranchJob.sequence)
        .limit(501)
    ).all()
    if len(registrations) > 500:
        raise ValueError("language_registration_limit")
    files = dict(profile.files)
    digest = _profile_digest(mapping.localization_profile)
    for registration in registrations:
        if not isinstance(registration, dict) or registration.get("profile_digest") != digest:
            continue
        for locale, path in registration["files"].items():
            if locale in files and files[locale] != path:
                raise ValueError("language_registration_conflict")
            files[locale] = path
    return JsonCatalogProfile.model_validate({**profile.model_dump(mode="json"), "files": files})


async def prepare_project_language(
    factory: sessionmaker[Session],
    workflow: BranchWorkflow,
    job: BranchJob,
    reads: SubmissionReadAdapter,
    *,
    head: str,
    workspace: str,
    slug: str,
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    with factory() as session:
        data = language_authority(session, workflow, job)
        scope = session.get_one(LocalizationScope, UUID(str(data["scope_id"])))
        captured, layouts = _capture_mapping(
            session, scope, reference_limit=500, byte_limit=20971520
        )
        mapping = active_mapping(session, workflow)
        assert mapping is not None
        profile_data = mapping.localization_profile
        translation_side = next(side for side in mapping.sides if side.role != "keys")
        root = translation_side.localization_root
    language = str(data["language"])
    files: list[dict[str, object]] = []
    paths = {ref.path for ref in captured.source_references if ref.repository_side != "keys"}
    xliff_layouts: set[str] = set()
    profile_files: dict[str, str] = {}
    for ref in sorted(captured.source_references, key=lambda ref: ref.path):
        if ref.repository_side == "keys":
            continue
        if (
            ref.repository_id != workflow.repository_id
            or ref.commit_hash != head
            or ref.configured_branch != workflow.work_branch
        ):
            raise BranchWorkflowError("import_changed")
        with factory() as session:
            metadata = await reads.read_repository_source_metadata(
                session, workspace=workspace, repository_slug=slug, commit_hash=head, path=ref.path
            )
            require_source_file_metadata(ref, metadata)
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
        SourceFileSnapshot(ref, parser, metadata.attributes)
        parsed = inspect_writeback_snapshot(parser)
        if parsed.issues:
            raise BranchWorkflowError("unsupported_shape")
        if parser.format == "xliff":
            if parser.layout_identity in xliff_layouts:
                continue
            xliff_layouts.add(parser.layout_identity)
        elif captured.base_language not in {value.language for value in parsed.values}:
            continue
        try:
            created = initialize_language(parser, language)
        except ValueError as error:
            raise BranchWorkflowError(str(error)) from None
        if created.new_file and created.path in paths:
            raise BranchWorkflowError("file_exists")
        files.append(
            {
                "path": created.path,
                "before": hashlib.sha256(b"" if created.new_file else content).hexdigest(),
                "content": base64.b64encode(created.content).decode(),
                "attributes": list(metadata.attributes or ()),
                "new_file": created.new_file,
            }
        )
        if profile_data is not None:
            if root and not created.path.startswith(root + "/"):
                raise BranchWorkflowError("invalid_destination")
            relative = created.path[len(root) + 1 :] if root else created.path
            if language in profile_files:
                raise BranchWorkflowError("ambiguous_language_path")
            profile_files[language] = relative
    if not files or len(files) > 100 or len({file["path"] for file in files}) != len(files):
        raise BranchWorkflowError("invalid_language_sources")
    if sum(len(str(file["content"])) for file in files) > 27_962_028:
        raise BranchWorkflowError("limit_exceeded")
    registration: dict[str, object] | None = None
    if profile_data is not None:
        with factory() as session:
            effective = registered_catalog_profile(
                session, session.get_one(ProductRepositoryMapping, mapping.id)
            )
        assert effective is not None
        JsonCatalogProfile.model_validate(
            {**effective.model_dump(mode="json"), "files": {**effective.files, **profile_files}}
        )
        registration = {"profile_digest": _profile_digest(profile_data), "files": profile_files}
    return files, registration
