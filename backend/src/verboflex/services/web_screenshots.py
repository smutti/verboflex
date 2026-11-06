"""Exact nested-value selection using atomically activated web context."""

import copy
import json
from typing import Any, cast

from sqlalchemy.orm import Session

from verboflex.localization.code_keys.catalog import CodeOccurrence
from verboflex.localization.web.context import set_catalog_value
from verboflex.localization.web.contracts import WebManifest, WebUsageIndex
from verboflex.localization.web.messages import WebMessageInvalid
from verboflex.models.import_job import ImportExecution
from verboflex.models.translation import LocalizationScope, TranslationValue
from verboflex.schemas.screenshots import (
    CodeContextResponse,
    ScreenScenario,
    ScreenshotRequest,
    WebCaptureTarget,
)
from verboflex.services.screenshots import MAX_INPUT_BYTES, ScreenshotError, encode_inputs
from verboflex.services.translation_search import TranslationGroupDetail
from verboflex.services.web_messages import validate_replacements


def web_context(
    session: Session, group: TranslationGroupDetail, data: dict[str, Any]
) -> CodeContextResponse:
    manifest = WebManifest.model_validate(data["manifest"])
    addresses = {tuple(path): key for key, path in data["addresses"].items()}
    targets = []
    for item in group.values:
        value = session.get_one(TranslationValue, item.id)
        if value.is_deleted or value.selector_kind != "json_path":
            continue
        path = (*json.loads(value.selector_bytes)["fields"]["parents"], group.raw_key)
        key = addresses.get(path)
        if key is None:
            continue
        scenarios = [
            s.id for s in manifest.scenarios if key in {target.key for target in s.targets}
        ]
        if scenarios and not data["capture_blocked"]:
            targets.append(
                WebCaptureTarget(
                    value_id=value.id, runtime_key=key, json_path=list(path), scenario_ids=scenarios
                )
            )
    keys = {target.runtime_key for target in targets}
    usages = WebUsageIndex.model_validate(data["usages"])
    occurrences = [
        CodeOccurrence(
            key=o.key, path=o.path, line=o.line, column=1, symbol=o.kind, function=None, kind="call"
        )
        for o in usages.occurrences
        if o.key in keys and o.key is not None
    ]
    return CodeContextResponse(
        configured=True,
        engine="web",
        web_targets=targets,
        previews=[],
        capture_functions=[],
        code_commit=data["commit"],
        diagnostics=data["diagnostics"][:100],
        occurrences=occurrences[:100],
        occurrences_truncated=len(occurrences) > 100,
        scenarios=[
            ScreenScenario(scenario_id=s.id, label=s.label, explicit=True)
            for s in manifest.scenarios
            if any(s.id in t.scenario_ids for t in targets)
        ],
    )


def web_snapshot(
    session: Session,
    group: TranslationGroupDetail,
    scope: LocalizationScope,
    request: ScreenshotRequest,
) -> dict[str, object]:
    data = cast(
        dict[str, Any] | None,
        session.get_one(ImportExecution, scope.active_execution_id).web_context,
    )
    if data is None or group.is_deleted:
        raise ScreenshotError("Web capture is unavailable", 409)
    context = web_context(session, group, data)
    target = next(
        (
            t
            for t in context.web_targets
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
    try:
        validate_replacements(session, {value.id: selected})
    except WebMessageInvalid as error:
        raise ScreenshotError(str(error), 409) from error
    catalogs = copy.deepcopy(data["catalogs"])
    assert isinstance(catalogs, dict)
    set_catalog_value(catalogs[group.language], tuple(target.json_path), selected)
    manifest = WebManifest.model_validate(data["manifest"])
    scenario = next(s for s in manifest.scenarios if s.id == request.scenario_id)
    # Give the runner precisely one reviewed DOM target. Other group drafts stay out.
    scenario = scenario.model_copy(
        update={"targets": tuple(t for t in scenario.targets if t.key == target.runtime_key)}
    )
    payload: dict[str, object] = {
        "version": 2,
        "engine": "web",
        "repository_id": data["repository_id"],
        "commit": data["commit"],
        "import_execution_id": str(scope.active_execution_id),
        "capture": data["config"],
        "manifest_digest": data["manifest_digest"],
        "source_digest": data["source_digest"],
        "sources": data["sources"],
        "request": request.model_dump(mode="json"),
        "language": group.language,
        "base_language": group.base_language,
        "target_path": target.json_path,
        "target_text": selected,
        "scenario": scenario.model_dump(mode="json"),
        "catalogs": {data["catalog_urls"][locale]: catalog for locale, catalog in catalogs.items()},
        "viewport": {"width": 1440, "height": 900}
        if request.viewport == "desktop"
        else {"width": 390, "height": 844},
    }
    if len(encode_inputs(payload)) > MAX_INPUT_BYTES:
        raise ScreenshotError("Web capture bundle exceeds its limit")
    return payload
