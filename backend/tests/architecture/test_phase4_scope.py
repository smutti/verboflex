"""Phase 4 exact source inventory and executable boundary negative controls."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def inventory():
    spec = importlib.util.spec_from_file_location("phase4_inventory", ROOT / "tools/phase4_inventory.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_phase4_source_inventory_is_exact():
    module = inventory()
    assert module.validate_manifest() == {"PLAN": 27, "GOAL": 1, "REQ": 20, "DECISION": 23, "EDGE": 52, "EDGE_ASSUMPTION": 0, "PROHIBITION": 2, "UI_CATEGORY": 8, "UI_INSTANCE": 50, "UI_AXIS": 3}


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


@pytest.mark.parametrize("path,source", [
    ("backend/src/verboflex/services/example.py", "from verboflex.localization.importing.android_xml import parse_android_xml"),
    ("backend/src/verboflex/api/v1/routes/example.py", "from verboflex.localization.importing.registry import parse_mapping\nparse_mapping(data)"),
    ("frontend/src/features/translations/example.ts", "localStorage.setItem('content', JSON.stringify(rows))"),
    ("frontend/src/features/translations/example.ts", "fetch('/api/v1/translations')"),
    ("frontend/src/features/translations/example.tsx", "const x = <div dangerouslySetInnerHTML={{__html: value}} />"),
    ("frontend/src/features/translations/example.ts", "const count = new Intl.Segmenter()"),
])
def test_seeded_boundary_shortcuts_fail(path, source):
    with pytest.raises(ValueError):
        inventory().validate_boundaries({path: source})


def test_no_deferred_phase4_operations():
    from verboflex.main import create_app

    module = inventory()
    paths = create_app().openapi()["paths"]
    module.validate_routes(paths)
    for path in ("/api/v1/translations/{id}", "/api/v1/translations/{id}/comments", "/api/v1/translations/{id}/approve", "/api/v1/translations/{id}/write-back"):
        with pytest.raises(ValueError):
            module.validate_routes({**paths, path: {"patch": {"operationId": "editTranslation"}}})


def test_browser_persistence_allowlist():
    inventory().validate_boundaries()


def test_api_routes_do_not_run_repository_work():
    inventory().validate_boundaries()


def test_generated_contract_is_current():
    import json
    from verboflex.main import create_app

    assert json.loads((ROOT / "frontend/openapi.json").read_text()) == create_app().openapi()
