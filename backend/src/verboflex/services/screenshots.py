"""Product-authorized snapshots and durable, idempotent capture requests."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from verboflex.auth.principal import Principal
from verboflex.auth.product_access import current_product_role, membership_stamp
from verboflex.auth.translation_access import (
    TranslationGroupAccessMode,
    TranslationGroupAccessUnavailable,
    resolve_translation_group_access,
)
from verboflex.localization.code_keys.capture import CaptureBundle, resource_overlay
from verboflex.localization.code_keys.catalog import CodeKeyCatalog, CodeSourceConfig
from verboflex.models.import_job import ImportExecution, ImportSourceReference
from verboflex.models.product import Product
from verboflex.models.screenshot import ScreenshotJob
from verboflex.models.translation import LocalizationScope, TranslationKey, TranslationValue
from verboflex.models.user import User
from verboflex.schemas.screenshots import (
    CodeCatalogEntry,
    CodeCatalogPage,
    CodeContextResponse,
    CodeSourcePage,
    CodeSourceSummary,
    ScreenScenario,
    ScreenshotRequest,
)
from verboflex.services.translation_search import TranslationGroupDetail

MAX_INPUT_BYTES = 4 * 1024 * 1024
ACTIVE_STATES = ("queued", "rendering")
logger = logging.getLogger(__name__)


class ScreenshotError(ValueError):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


def code_sources(
    session: Session,
    principal: Principal,
    product_id: UUID,
    after: UUID | None,
) -> CodeSourcePage:
    product = session.get(Product, product_id)
    if (
        product is None
        or not product.is_active
        or product.deleted_at is not None
        or not current_product_role(session, principal.user_id, product_id)
    ):
        raise ScreenshotError("Product unavailable", 404)
    statement = (
        select(LocalizationScope, ImportExecution.code_catalog)
        .join(
            ImportExecution,
            ImportExecution.id == LocalizationScope.active_execution_id,
        )
        .where(
            LocalizationScope.product_id == product_id,
            LocalizationScope.current_revision_id == product.active_revision_id,
            ImportExecution.code_catalog.is_not(None),
        )
    )
    if after is not None:
        statement = statement.where(LocalizationScope.id > after)
    rows = list(session.execute(statement.order_by(LocalizationScope.id).limit(51)))
    return CodeSourcePage(
        items=[
            CodeSourceSummary(
                scope_id=scope.id,
                mapping_id=scope.current_mapping_id,
                key_count=len(CodeKeyCatalog.model_validate(data["catalog"]).keys),
                missing_count=len(data["missing_keys"]),
            )
            for scope, data in rows[:50]
        ],
        next_cursor=rows[49][0].id if len(rows) > 50 else None,
    )


def _group(session: Session, principal: Principal, group_id: UUID) -> TranslationGroupDetail:
    try:
        return resolve_translation_group_access(
            session,
            principal=principal,
            translation_group_id=group_id,
            mode=TranslationGroupAccessMode.READ,
        ).group
    except TranslationGroupAccessUnavailable as error:
        raise ScreenshotError("Translation unavailable", 404) from error


def _scope_for_group(session: Session, group: TranslationGroupDetail) -> LocalizationScope:
    value = session.get(TranslationValue, group.values[0].id)
    if value is None:
        raise ScreenshotError("Translation unavailable", 404)
    scope = session.scalar(
        select(LocalizationScope)
        .where(
            LocalizationScope.id == value.scope_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update(read=True)
    )
    if scope is None:
        raise ScreenshotError("Code source unavailable", 409)
    if scope.active_execution_id is None:
        raise ScreenshotError("Code source unavailable", 409)
    return scope


def _catalog(session: Session, scope: LocalizationScope) -> tuple[CodeKeyCatalog, CodeSourceConfig]:
    execution = session.get(ImportExecution, scope.active_execution_id)
    if execution is None or execution.code_catalog is None:
        raise ScreenshotError("Code source is not configured", 409)
    return (
        CodeKeyCatalog.model_validate(execution.code_catalog["catalog"]),
        CodeSourceConfig.model_validate(execution.code_catalog["config"]),
    )


def screen_scenarios(
    catalog: CodeKeyCatalog, config: CodeSourceConfig, key: str
) -> list[ScreenScenario]:
    if config.compose is None:
        return []
    known = {preview.function for preview in catalog.previews}
    explicit = [scenario for scenario in config.preview_scenarios if key in scenario.keys]
    if explicit:
        return [
            ScreenScenario(
                preview_function=scenario.preview_function, label=scenario.label, explicit=True
            )
            for scenario in explicit
            if scenario.preview_function in known
        ]
    labels = {scenario.preview_function: scenario.label for scenario in config.preview_scenarios}
    functions = dict.fromkeys(
        preview.function
        for preview in catalog.previews
        if key in preview.keys and preview.function in config.compose.preview_functions
    )
    return [
        ScreenScenario(
            preview_function=function,
            label=labels.get(function)
            or re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", function.rsplit(".", 1)[-1])
            .removesuffix(" Preview")
            .strip(),
            explicit=False,
        )
        for function in functions
    ]


def context(session: Session, principal: Principal, group_id: UUID) -> CodeContextResponse:
    group = _group(session, principal, group_id)
    scope = _scope_for_group(session, group)
    try:
        catalog, config = _catalog(session, scope)
    except ScreenshotError:
        return CodeContextResponse(
            configured=False, occurrences=[], previews=[], capture_functions=[]
        )
    occurrences = [item for item in catalog.occurrences if item.key == group.raw_key]
    previews = [item for item in catalog.previews if group.raw_key in item.keys]
    code = session.scalar(
        select(ImportSourceReference)
        .where(
            ImportSourceReference.execution_id == scope.active_execution_id,
            ImportSourceReference.repository_side == "keys",
        )
        .limit(1)
    )
    return CodeContextResponse(
        configured=True,
        occurrences=occurrences[:100],
        previews=previews[:100],
        occurrences_truncated=len(occurrences) > 100,
        capture_functions=list(config.compose.preview_functions) if config.compose else [],
        code_commit=code.commit_hash if code else None,
        scenarios=screen_scenarios(catalog, config, group.raw_key),
    )


def catalog_page(
    session: Session,
    principal: Principal,
    scope_id: UUID,
    after: str | None,
) -> CodeCatalogPage:
    scope = session.get(LocalizationScope, scope_id)
    product = session.get(Product, scope.product_id) if scope else None
    if (
        scope is None
        or product is None
        or not product.is_active
        or product.deleted_at is not None
        or product.active_revision_id != scope.current_revision_id
        or not current_product_role(session, principal.user_id, product.id)
    ):
        raise ScreenshotError("Code source unavailable", 404)
    catalog, _ = _catalog(session, scope)
    data = session.get_one(ImportExecution, scope.active_execution_id).code_catalog
    assert data is not None
    missing = set(cast(list[str], data.get("missing_keys", [])))
    base = set(cast(list[str], data.get("missing_base_keys", [])))
    keys = [key for key in catalog.keys if after is None or key > after][:101]
    return CodeCatalogPage(
        items=[
            CodeCatalogEntry(key=key, missing_translation=key in missing, missing_base=key in base)
            for key in keys[:100]
        ],
        next_cursor=keys[99] if len(keys) > 100 else None,
        orphan_count=len(cast(list[str], data.get("orphan_keys", []))),
    )


def _snapshot(
    session: Session,
    group: TranslationGroupDetail,
    scope: LocalizationScope,
    request: ScreenshotRequest,
) -> dict[str, object]:
    catalog, config = _catalog(session, scope)
    capture = config.compose
    matches = [item for item in catalog.previews if item.function == request.preview_function]
    if (
        capture is None
        or request.preview_function not in capture.preview_functions
        or not matches
        or request.preview_function
        not in {item.preview_function for item in screen_scenarios(catalog, config, group.raw_key)}
    ):
        raise ScreenshotError("Capture preview is unavailable", 409)
    if group.is_deleted:
        raise ScreenshotError("Translation is deleted", 409)
    pending = group.pending_change
    overrides: dict[UUID, str] = {}
    if request.proposal_version is not None:
        if (
            pending is None
            or pending.version != request.proposal_version
            or pending.reconciliation_required
            or pending.state == "rejected"
        ):
            raise ScreenshotError("Save and refresh the proposal before capturing", 409)
        overrides = {value.translation_value_id: value.text for value in pending.values}
    refs = list(
        session.scalars(
            select(ImportSourceReference).where(
                ImportSourceReference.execution_id == scope.active_execution_id,
            )
        )
    )
    commits = {(ref.repository_side, str(ref.repository_id), ref.commit_hash) for ref in refs}
    code = [item for item in commits if item[0] == "keys"]
    translations = [item for item in commits if item[0] == "translations"]
    if len(code) != 1 or len(translations) != 1:
        raise ScreenshotError("Immutable source revisions unavailable", 409)
    rows = session.execute(
        select(TranslationKey.raw_key, TranslationValue)
        .join(
            TranslationValue,
            TranslationValue.translation_key_id == TranslationKey.id,
        )
        .where(
            TranslationKey.scope_id == scope.id,
            TranslationKey.is_deleted.is_(False),
            TranslationValue.is_deleted.is_(False),
            TranslationValue.language.in_([group.language, group.base_language]),
        )
        .order_by(
            TranslationKey.raw_key, TranslationValue.language, TranslationValue.selector_digest
        )
    )
    values = [
        {
            "key": key,
            "language": value.language,
            "selector": json.loads(value.selector_bytes),
            "text": overrides.get(value.id, value.display_text),
        }
        for key, value in rows
    ]
    required_keys = {key for preview in matches for key in preview.keys}
    if required_keys - {str(value["key"]) for value in values}:
        raise ScreenshotError("Preview keys need imported translations or base text", 409)
    payload: dict[str, object] = {
        "version": 1,
        "target_key": group.raw_key,
        "code_repository_id": code[0][1],
        "code_commit": code[0][2],
        "translations_repository_id": translations[0][1],
        "translations_commit": translations[0][2],
        "import_execution_id": str(scope.active_execution_id),
        "language": group.language,
        "base_language": group.base_language,
        "capture": capture.model_dump(mode="json"),
        "request": request.model_dump(mode="json"),
        "values": values,
    }
    try:
        resource_overlay(CaptureBundle.model_validate(payload))
    except ValueError as error:
        raise ScreenshotError("This capture needs valid Android resource values", 409) from error
    if len(encode_inputs(payload)) > MAX_INPUT_BYTES:
        raise ScreenshotError("Capture translation bundle exceeds its limit")
    return payload


def encode_inputs(inputs: dict[str, object]) -> bytes:
    return json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def enqueue_capture(job_id: UUID) -> None:
    """Best-effort dispatch after commit; the reconciler recovers missed sends."""
    from verboflex.worker.celery_app import app

    try:
        app.send_task(
            "verboflex.screenshot.run",
            args=[str(job_id)],
            queue="screenshots",
            serializer="json",
            retry=False,
        )
    except Exception:
        # Keep the durable request queued and omit broker details/credentials.
        logger.warning("Immediate screenshot dispatch failed for job %s; recovery pending", job_id)


def request_capture(
    session: Session,
    principal: Principal,
    group_id: UUID,
    request_id: UUID,
    request: ScreenshotRequest,
    *,
    runner_enabled: bool,
) -> ScreenshotJob:
    # Serialize acceptance per actor, including idempotency and expensive-job quotas.
    session.execute(select(User.id).where(User.id == principal.user_id).with_for_update())
    group = _group(session, principal, group_id)
    existing = session.get(ScreenshotJob, request_id)
    if existing is not None:
        if (
            existing.actor_id != principal.user_id
            or existing.group_id != group_id
            or existing.request != request.model_dump(mode="json")
        ):
            raise ScreenshotError("Screenshot request identity already used", 409)
        return get_capture(session, principal, group_id, existing.id)
    if not runner_enabled:
        raise ScreenshotError("Compose capture runner is not configured", 503)
    session.execute(select(Product.id).where(Product.id == group.product_id).with_for_update())
    now = datetime.now(UTC)
    product_running = (
        session.scalar(
            select(func.count())
            .select_from(ScreenshotJob)
            .where(
                ScreenshotJob.product_id == group.product_id,
                ScreenshotJob.state.in_(ACTIVE_STATES),
            )
        )
        or 0
    )
    count = (
        session.scalar(
            select(func.count())
            .select_from(ScreenshotJob)
            .where(
                ScreenshotJob.actor_id == principal.user_id,
                ScreenshotJob.created_at >= now - timedelta(hours=1),
            )
        )
        or 0
    )
    running = (
        session.scalar(
            select(func.count())
            .select_from(ScreenshotJob)
            .where(
                ScreenshotJob.actor_id == principal.user_id,
                ScreenshotJob.state.in_(ACTIVE_STATES),
            )
        )
        or 0
    )
    if count >= 20 or running >= 2 or product_running >= 4:
        raise ScreenshotError("Screenshot limit reached; retry later", 429)
    scope = _scope_for_group(session, group)
    group = _group(session, principal, group_id)
    inputs = _snapshot(session, group, scope, request)
    assert scope.active_execution_id is not None
    row = ScreenshotJob(
        id=request_id,
        actor_id=principal.user_id,
        product_id=group.product_id,
        group_id=group_id,
        scope_id=scope.id,
        execution_id=scope.active_execution_id,
        membership_stamp=membership_stamp(session, principal.user_id, group.product_id),
        state="queued",
        request=request.model_dump(mode="json"),
        inputs=inputs,
        input_digest=hashlib.sha256(encode_inputs(inputs)).hexdigest(),
        image=None,
        image_digest=None,
        error_code=None,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(days=7),
    )
    session.add(row)
    session.flush()
    return row


def authority_current(session: Session, row: ScreenshotJob) -> bool:
    scope = session.get(LocalizationScope, row.scope_id)
    product = session.get(Product, row.product_id)
    return bool(
        product
        and product.is_active
        and product.deleted_at is None
        and scope
        and scope.product_id == row.product_id
        and scope.current_revision_id == product.active_revision_id
        and scope.active_execution_id == row.execution_id
        and row.membership_stamp == membership_stamp(session, row.actor_id, row.product_id)
        and row.membership_stamp != "unavailable"
    )


def get_capture(
    session: Session, principal: Principal, group_id: UUID, job_id: UUID
) -> ScreenshotJob:
    _group(session, principal, group_id)
    row = session.scalar(
        select(ScreenshotJob)
        .where(
            ScreenshotJob.id == job_id,
            ScreenshotJob.group_id == group_id,
        )
        .with_for_update()
    )
    if row is None:
        raise ScreenshotError("Screenshot unavailable", 404)
    if row.expires_at <= datetime.now(UTC):
        row.state, row.image, row.inputs = "expired", None, {}
        row.location = None
    elif not authority_current(session, row):
        row.state, row.image, row.error_code = "failed", None, "source_or_access_changed"
        row.location = None
    return row
