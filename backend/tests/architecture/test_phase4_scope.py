"""Phase 4 exact source inventory and executable boundary negative controls."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def inventory():
    spec = importlib.util.spec_from_file_location(
        "phase4_inventory", ROOT / "tools/phase4_inventory.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_phase4_source_inventory_is_exact():
    module = inventory()
    assert module.validate_manifest() == {
        "PLAN": 27,
        "GOAL": 1,
        "REQ": 20,
        "DECISION": 23,
        "EDGE": 52,
        "EDGE_ASSUMPTION": 0,
        "PROHIBITION": 2,
        "UI_CATEGORY": 8,
        "UI_INSTANCE": 50,
        "UI_AXIS": 3,
    }


def test_source_inventory_rejects_new_flagged_assumption(tmp_path, monkeypatch):
    import shutil

    import yaml

    module = inventory()
    phase = tmp_path / "phase"
    shutil.copytree(module.PHASE, phase)
    plan = phase / "04-01-PLAN.md"
    parts = plan.read_text().split("---", 2)
    front = yaml.safe_load(parts[1])
    front["must_haves"]["assumptions"] = [{"statement": "Unproven edge", "flagged": True}]
    plan.write_text("---\n" + yaml.safe_dump(front) + "---" + parts[2])
    monkeypatch.setattr(module, "PHASE", phase)
    with pytest.raises(ValueError, match="assumption"):
        module.source_inventory()


@pytest.mark.parametrize("change", ["missing", "duplicate", "extra", "unreachable"])
def test_manifest_rejects_missing_duplicate_extra_or_unreachable_evidence(change):
    module = inventory()
    rows = module.read_manifest()
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows.append(dict(rows[0]))
    elif change == "extra":
        rows.append({**rows[0], "id": "unknown"})
    else:
        rows[0] = {**rows[0], "tests": ["backend/tests/absent.py::test_invented"]}
    with pytest.raises(ValueError):
        module.validate_manifest(rows)


def test_imports_cross_registry_boundary():
    inventory().validate_boundaries()


def test_shared_moko_writer_can_inspect_without_bypassing_canonical_imports():
    inventory().validate_boundaries(
        {
            "backend/src/verboflex/localization/writing/parsing.py": (
                "from verboflex.localization.importing.android_xml "
                "import AndroidXmlInspection, inspect_android_xml"
            )
        }
    )


@pytest.mark.parametrize(
    "path,names",
    [
        ("localization/writing/parsing.py", "inspect_android_xml, parse_android_xml"),
        ("localization/writing/other.py", "inspect_android_xml"),
        ("api/v1/routes/example.py", "inspect_android_xml"),
    ],
)
def test_shared_moko_inspection_exception_stays_scoped_to_writer(path, names):
    with pytest.raises(ValueError, match="parser boundary bypass"):
        inventory().validate_boundaries(
            {
                f"backend/src/verboflex/{path}": (
                    f"from verboflex.localization.importing.android_xml import {names}"
                )
            }
        )


def test_phase5_editor_may_preview_graphemes_without_becoming_content_authority():
    inventory().validate_boundaries(
        {
            "frontend/src/features/translations/TranslationEditor.tsx": (
                "const preview = Array.from(new Intl.Segmenter(undefined, "
                '{ granularity: "grapheme" }).segment(text)).length'
            )
        }
    )


def test_grapheme_preview_allowlist_is_exact():
    with pytest.raises(ValueError, match="client content authority"):
        inventory().validate_boundaries(
            {
                "frontend/src/features/translations/OtherEditor.tsx": (
                    "const preview = new Intl.Segmenter(undefined, "
                    '{ granularity: "grapheme" }).segment(text)'
                )
            }
        )


@pytest.mark.parametrize(
    "path,source",
    [
        (
            "backend/src/verboflex/services/example.py",
            "from verboflex.localization.importing.android_xml import parse_android_xml",
        ),
        (
            "backend/src/verboflex/api/v1/routes/example.py",
            "from verboflex.localization.importing.registry import parse_mapping\n"
            "parse_mapping(data)",
        ),
        (
            "frontend/src/features/translations/example.ts",
            "localStorage.setItem('content', JSON.stringify(rows))",
        ),
        ("frontend/src/features/translations/example.ts", "fetch('/api/v1/translations')"),
        (
            "frontend/src/features/translations/example.tsx",
            "const x = <div dangerouslySetInnerHTML={{__html: value}} />",
        ),
        ("frontend/src/features/translations/example.ts", "const count = new Intl.Segmenter()"),
    ],
)
def test_seeded_boundary_shortcuts_fail(path, source):
    with pytest.raises(ValueError):
        inventory().validate_boundaries({path: source})


def test_no_deferred_phase4_operations():
    from verboflex.main import create_app

    module = inventory()
    assert module.TRANSLATION_ROUTE_INVENTORY == {
        ("/api/v1/translations/keys", "get"): "searchTranslationKeys",
        ("/api/v1/translations/{group_id}/code-context", "get"): "getTranslationCodeContext",
        ("/api/v1/translations/{group_id}/screenshots", "get"): "listTranslationScreenshots",
        (
            "/api/v1/translations/{group_id}/screenshots/{job_id}",
            "put",
        ): "requestTranslationScreenshot",
        ("/api/v1/translations/{group_id}/screenshots/{job_id}", "get"): "getTranslationScreenshot",
        (
            "/api/v1/translations/{group_id}/screenshots/{job_id}",
            "delete",
        ): "cancelTranslationScreenshot",
        (
            "/api/v1/translations/{group_id}/screenshots/{job_id}/image",
            "get",
        ): "getTranslationScreenshotImage",
        ("/api/v1/translations/options", "get"): "listTranslationOptions",
        ("/api/v1/translations", "get"): "searchTranslations",
        ("/api/v1/translations/{translation_group_id}", "get"): "getTranslationGroup",
        (
            "/api/v1/translations/{translation_group_id}/constraints/{language}",
            "put",
        ): "putTranslationConstraint",
        (
            "/api/v1/translations/{translation_group_id}/constraints/{language}",
            "delete",
        ): "deleteTranslationConstraint",
        (
            "/api/v1/translations/{translation_group_id}/proposal",
            "put",
        ): "saveTranslationProposal",
        (
            "/api/v1/translations/{translation_group_id}/proposal/state",
            "post",
        ): "transitionTranslationProposal",
        (
            "/api/v1/translations/{translation_group_id}/activity",
            "get",
        ): "listTranslationReviewActivity",
        (
            "/api/v1/translations/{translation_group_id}/comments",
            "get",
        ): "listTranslationComments",
        (
            "/api/v1/translations/{translation_group_id}/comments",
            "post",
        ): "createTranslationComment",
        (
            "/api/v1/translations/{translation_group_id}/comments/anchor",
            "get",
        ): "getTranslationCommentAnchor",
        (
            "/api/v1/translations/{translation_group_id}/comments/{comment_id}",
            "put",
        ): "updateTranslationComment",
        (
            "/api/v1/translations/{translation_group_id}/comments/{comment_id}",
            "delete",
        ): "deleteTranslationComment",
        (
            "/api/v1/translations/{translation_group_id}/comments/{comment_id}/versions",
            "get",
        ): "listTranslationCommentVersions",
    }
    paths = create_app().openapi()["paths"]
    module.validate_routes(paths)
    for path in (
        "/api/v1/translations/{id}",
        "/api/v1/translations/{id}/comments",
        "/api/v1/translations/{id}/approve",
        "/api/v1/translations/{id}/write-back",
    ):
        with pytest.raises(ValueError):
            module.validate_routes({**paths, path: {"patch": {"operationId": "editTranslation"}}})
    comment_path = "/api/v1/translations/{translation_group_id}/comments"
    renamed_comment = {
        **paths,
        comment_path: {
            **paths[comment_path],
            "get": {
                **paths[comment_path]["get"],
                "operationId": "listCommentsWithoutFrozenAuthority",
            },
        },
    }
    with pytest.raises(ValueError):
        module.validate_routes(renamed_comment)


def test_browser_persistence_allowlist():
    inventory().validate_boundaries()


def test_api_routes_do_not_run_repository_work():
    inventory().validate_boundaries()


def test_generated_contract_is_current():
    import json

    from verboflex.main import create_app

    assert json.loads((ROOT / "frontend/openapi.json").read_text()) == create_app().openapi()


def test_api_coverage_detector_stays_exactly_false():
    """The recorded GSD verdict is valid only for the exact unchanged plan inputs."""
    report = inventory().verify_api_scope_receipt()
    assert report["detected"] is False
    assert report["passed"] is True
    assert report["block"] is False
    assert report["coverage_present"] is False


@pytest.mark.parametrize("change", ["changed-plan", "new-plan", "nested-plan", "coverage"])
def test_api_scope_receipt_rejects_changed_inputs(tmp_path, change):
    import shutil

    module = inventory()
    for path in module.PHASE.glob("*-PLAN.md"):
        shutil.copy2(path, tmp_path / path.name)
    if change == "changed-plan":
        path = tmp_path / "04-01-PLAN.md"
        path.write_text(path.read_text() + "\nIntegrate the Stripe API.\n")
    elif change == "new-plan":
        (tmp_path / "04-99-PLAN.md").write_text("Integrate the Stripe API.\n")
    elif change == "nested-plan":
        (tmp_path / "plans").mkdir()
        (tmp_path / "plans/PLAN.md").write_text("Integrate the Stripe API.\n")
    else:
        (tmp_path / "COVERAGE.md").write_text("New coverage declaration.\n")
    with pytest.raises(ValueError, match="API (scope|coverage)"):
        module.verify_api_scope_receipt(tmp_path)
