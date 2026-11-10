"""Exact Qt context/source/disambiguation selection in the shared capture pipeline."""

import json
from typing import Any, cast

from sqlalchemy.orm import Session

from verboflex.localization.qt_capture import QtManifest
from verboflex.models.import_job import ImportExecution
from verboflex.models.translation import LocalizationScope, TranslationValue
from verboflex.schemas.screenshots import (
    CodeContextResponse,
    QtCaptureTarget,
    ScreenScenario,
    ScreenshotRequest,
)
from verboflex.services.screenshots import MAX_INPUT_BYTES, ScreenshotError, encode_inputs
from verboflex.services.translation_search import TranslationGroupDetail


def qt_context(
    session: Session, group: TranslationGroupDetail, data: dict[str, Any]
) -> CodeContextResponse:
    manifest = QtManifest.model_validate(data["manifest"])
    targets = []
    for item in group.values:
        value = session.get_one(TranslationValue, item.id)
        if value.is_deleted or value.selector_kind != "scalar":
            continue
        fields = json.loads(value.selector_bytes)["fields"]
        if fields.get("identity_kind") != "source":
            continue
        scenarios = [
            s.id
            for s in manifest.scenarios
            if s.source == group.raw_key
            and s.context == fields.get("context")
            and s.disambiguation == fields.get("disambiguation", "")
        ]
        if scenarios:
            targets.append(
                QtCaptureTarget(
                    value_id=value.id,
                    context=fields["context"],
                    disambiguation=fields.get("disambiguation", ""),
                    scenario_ids=scenarios,
                )
            )
    return CodeContextResponse(
        configured=bool(targets),
        engine="qt",
        qt_targets=targets,
        occurrences=[],
        previews=[],
        capture_functions=[],
        code_commit=data["commit"],
        scenarios=[
            ScreenScenario(scenario_id=s.id, label=s.label, explicit=True)
            for s in manifest.scenarios
            if any(s.id in t.scenario_ids for t in targets)
        ],
    )


def qt_snapshot(
    session: Session,
    group: TranslationGroupDetail,
    scope: LocalizationScope,
    request: ScreenshotRequest,
) -> dict[str, object]:
    data = cast(
        dict[str, Any] | None,
        session.get_one(ImportExecution, scope.active_execution_id).qt_context,
    )
    if data is None or group.is_deleted:
        raise ScreenshotError("Qt capture is unavailable", 409)
    context = qt_context(session, group, data)
    target = next(
        (
            t
            for t in context.qt_targets
            if t.value_id == request.target_value_id and request.scenario_id in t.scenario_ids
        ),
        None,
    )
    if target is None:
        raise ScreenshotError("Scenario is not registered for this exact value", 409)
    value = session.get_one(TranslationValue, target.value_id)
    selected = value.display_text
    if request.proposal_version is not None:
        pending = group.pending_change
        if (
            pending is None
            or pending.version != request.proposal_version
            or pending.reconciliation_required
            or pending.state == "rejected"
        ):
            raise ScreenshotError("Save and refresh the proposal before capturing", 409)
        selected = next(
            (v.text for v in pending.values if v.translation_value_id == value.id), selected
        )
    manifest = QtManifest.model_validate(data["manifest"])
    scenario = next(s for s in manifest.scenarios if s.id == request.scenario_id)
    # Empty Qt translations fall back to the original source at runtime.
    rendered_text = selected or scenario.source
    if len(rendered_text) > 65536:
        raise ScreenshotError("Qt capture text exceeds its limit", 409)
    payload: dict[str, object] = {
        "version": 1,
        "engine": "qt",
        "repository_id": data["repository_id"],
        "commit": data["commit"],
        "import_execution_id": str(scope.active_execution_id),
        "manifest": data["manifest"],
        "manifest_digest": data["manifest_digest"],
        "source_digest": data["source_digest"],
        "request": request.model_dump(mode="json"),
        "language": group.language,
        "base_language": group.base_language,
        "scenario": scenario.model_dump(mode="json"),
        "target_text": rendered_text,
    }
    if len(encode_inputs(payload)) > MAX_INPUT_BYTES:
        raise ScreenshotError("Qt capture bundle exceeds its limit")
    return payload
