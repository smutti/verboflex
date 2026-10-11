"""Behavioral gate oracles: actual deployment inputs and nonempty E2E proof."""

import importlib.util
import json
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("phase6_gate", ROOT / "tools/phase6_gate.py")
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def test_smoke_fixtures_have_genuine_detectable_layouts():
    from verboflex.localization.preview.registry import detect_preview_layouts
    from verboflex.services.repository_discovery import RepositorySourceFile

    spec = importlib.util.spec_from_file_location("phase6_smoke", ROOT / "tools/phase6_smoke.py")
    assert spec and spec.loader
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    for name in (*smoke.FORMATS, "keys"):
        files = tuple(
            RepositorySourceFile(path, data) for path, data in smoke.fixture_files(name).items()
        )
        candidates = detect_preview_layouts(files, repository_side="direct").candidates
        assert len(candidates) == 1, name
        assert len(candidates[0].files) == len(files)


@pytest.mark.parametrize("invalid", ["empty", "no_metadata", "mutation"])
def test_provider_audit_requires_real_reads_and_rejects_mutation(tmp_path, invalid):
    spec = importlib.util.spec_from_file_location("phase6_smoke", ROOT / "tools/phase6_smoke.py")
    assert spec and spec.loader
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    rows = [
        {
            "category": "oauth-token-exchange",
            "method": "POST",
            "resource_family": "oauth-token",
            "status": 200,
        }
    ]
    rows.extend(
        {"category": "resource", "method": "GET", "resource_family": name, "status": 200}
        for name in ("source-read", "source-metadata", "branch-read")
    )
    path = tmp_path / "audit.jsonl"
    path.write_text("\n".join(map(json.dumps, rows)))
    smoke.audit(str(path))
    if invalid == "empty":
        rows = []
    elif invalid == "no_metadata":
        rows = [row for row in rows if row["resource_family"] != "source-metadata"]
    else:
        rows[-1]["method"] = "POST"
    path.write_text("\n".join(map(json.dumps, rows)))
    with pytest.raises(AssertionError):
        smoke.audit(str(path))


def test_digest_includes_deployment_inputs_and_excludes_evidence(tmp_path):
    for name in (
        "backend/src/a.py",
        "docker/backend.Dockerfile",
        "docker-compose.smoke.yml",
        ".dockerignore",
        "frontend/package-lock.json",
        "tools/phase6_smoke.py",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original")
    baseline = gate.source_digest(tmp_path)
    for name in (
        "docker/backend.Dockerfile",
        "docker-compose.smoke.yml",
        ".dockerignore",
        "frontend/package-lock.json",
        "tools/phase6_smoke.py",
    ):
        path = tmp_path / name
        path.write_text("changed")
        assert gate.source_digest(tmp_path) != baseline, name
        path.write_text("original")
    (tmp_path / ".planning").mkdir()
    (tmp_path / ".planning/result.json").write_text("evidence")
    assert gate.source_digest(tmp_path) == baseline


def proof():
    return {
        "source_digest": "a" * 64,
        "stages": {"tests": "pass", "ruff": "pass", "mypy": "pass", "smoke": "pass"},
        "tests": 1,
        "skipped": 0,
        "smoke": {
            "formats": 4,
            "approved_groups": 8,
            "prepared_files": 5,
            "revalidated": True,
            "localization_unchanged": True,
            "stale_direct": True,
            "stale_keys": True,
            "tampered_file": True,
            "mixed_markup": True,
            "duplicate_snapshot": True,
            "resource_mutations": 0,
            "cleanup": True,
        },
    }


def test_complete_evidence_is_accepted():
    gate.validate_evidence(proof(), "a" * 64)


def test_timeout_allows_child_cleanup_trap(tmp_path):
    marker = tmp_path / "cleaned"
    script = tmp_path / "child.sh"
    script.write_text("trap 'printf done > cleaned; exit 0' TERM\nwhile :; do sleep 0.05; done\n")
    with tempfile.TemporaryFile(mode="w+") as log:
        assert (
            gate.run_stage(["bash", str(script)], cwd=tmp_path, log=log, timeout=0.2, grace=2)
            == 124
        )
    assert marker.read_text() == "done"


@pytest.mark.parametrize(
    "mutation", ["digest", "empty", "skipped", "no_provider", "write", "stale", "cleanup", "stage"]
)
def test_incomplete_or_stale_evidence_is_rejected(mutation):
    data = deepcopy(proof())
    if mutation == "digest":
        data["source_digest"] = "b" * 64
    elif mutation == "empty":
        data["tests"] = 0
    elif mutation == "skipped":
        data["skipped"] = 1
    elif mutation == "no_provider":
        data["smoke"]["prepared_files"] = 0
    elif mutation == "write":
        data["smoke"]["resource_mutations"] = 1
    elif mutation == "stale":
        data["smoke"]["stale_keys"] = False
    elif mutation == "cleanup":
        data["smoke"]["cleanup"] = False
    else:
        data["stages"]["mypy"] = "fail"
    with pytest.raises(ValueError):
        gate.validate_evidence(data, "a" * 64)
