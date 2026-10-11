"""Certification must reject plausible PASS labels without complete evidence."""

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location("phase7_gate", ROOT / "tools/phase7_gate.py")
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
DIGEST = "a" * 64


def receipt():
    commands = {stage: [stage, "--checked"] for stage in gate.STAGES}
    evidence = {
        "source_digest": DIGEST,
        "source_digest_after": DIGEST,
        "stages": {
            stage: {
                "command": command,
                "exit_code": 0,
                "status": "pass",
                "source_digest": DIGEST,
                "duration_seconds": 1.0,
                "started_at": "2026-10-01T00:00:00+00:00",
                "finished_at": "2026-10-01T00:00:01+00:00",
                "output_sha256": "b" * 64,
            }
            for stage, command in commands.items()
        },
        "tests": {
            stage: {"passed": 1, "skipped": 0}
            for stage in ("backend", "harness", "frontend", "e2e", "native-cleanup")
        },
        "migration_round_trip": True,
        "mutants": {"status": "pass", "killed": 7, "survived": 0, "source_restored": True},
        "smoke": {
            "happy": {
                "groups": 5,
                "effects": {"branch": 5, "commit": 5, "pull_request": 5},
                "exact_bytes": True,
                "immutable_receipts": True,
                "localization_unchanged": True,
            },
            "faults": {
                "groups": 17,
                "effects": {"branch": 15, "commit": 14, "pull_request": 14},
                "exact_bytes": True,
                "immutable_receipts": True,
            },
            "cleanup": True,
        },
        "browser": {"backstops": 60, "native_zoom": True, "geometry": True, "keyboard": True},
    }
    evidence["smoke"]["faults"].update(dict.fromkeys(getattr(gate, "FAULTS", ()), True))
    return evidence, commands


@pytest.mark.parametrize(
    "damage",
    [
        "label_only",
        "missing_stage",
        "changed_after",
        "wrong_command",
        "failed_exit",
        "skipped",
        "zero_tests",
        "missing_migration",
        "surviving_mutant",
        "duplicate_effect",
        "cleanup",
        "native_zoom",
        "missing_geometry",
        "invalid_timing",
        "fake_output",
    ],
)
def test_plausible_pass_cannot_replace_current_executed_evidence(damage):
    evidence, commands = receipt()
    if damage == "label_only":
        evidence = {"source_digest": DIGEST, "status": "pass"}
    elif damage == "missing_stage":
        del evidence["stages"]["smoke"]
    elif damage == "changed_after":
        evidence["source_digest_after"] = "c" * 64
    elif damage == "wrong_command":
        evidence["stages"]["backend"]["command"] = ["true"]
    elif damage == "failed_exit":
        evidence["stages"]["backend"]["exit_code"] = 1
    elif damage == "skipped":
        evidence["tests"]["backend"]["skipped"] = 1
    elif damage == "zero_tests":
        evidence["tests"]["frontend"]["passed"] = 0
    elif damage == "missing_migration":
        evidence["migration_round_trip"] = False
    elif damage == "surviving_mutant":
        evidence["mutants"]["survived"] = 1
    elif damage == "duplicate_effect":
        evidence["smoke"]["faults"]["effects"]["commit"] += 1
    elif damage == "cleanup":
        evidence["smoke"]["cleanup"] = False
    elif damage == "native_zoom":
        evidence["browser"]["native_zoom"] = False
    elif damage == "missing_geometry":
        evidence["browser"]["geometry"] = False
    elif damage == "invalid_timing":
        evidence["stages"]["backend"]["duration_seconds"] = float("nan")
    else:
        evidence["stages"]["backend"]["output_sha256"] = "PASS"
    with pytest.raises(ValueError):
        gate.validate_evidence(evidence, DIGEST, commands)


def test_complete_unchanged_evidence_is_reusable():
    evidence, commands = receipt()
    gate.validate_evidence(evidence, DIGEST, commands)


@pytest.mark.parametrize("damage", ["missing", "stale", "high", "unverified"])
def test_review_and_verifier_must_share_source_and_close_blockers(damage):
    records = {
        "review": {"source_digest": DIGEST, "status": "clean", "unresolved_high": 0},
        "security": {"source_digest": DIGEST, "status": "verified", "threats_open": 0},
        "verification": {"source_digest": DIGEST, "status": "passed", "behavior_unverified": 0},
    }
    original = copy.deepcopy(records)
    if damage == "missing":
        del records["verification"]
    elif damage == "stale":
        records["verification"]["source_digest"] = "b" * 64
    elif damage == "high":
        records["review"]["unresolved_high"] = 1
    else:
        records["verification"]["behavior_unverified"] = 1
    with pytest.raises(ValueError):
        gate.validate_reviews(records, DIGEST)
    gate.validate_reviews(original, DIGEST)


@pytest.mark.parametrize("damage", ["omitted", "missing", "symbolic"])
def test_owned_inventory_cannot_omit_changed_or_missing_source(tmp_path, damage):
    paths = sorted(gate.DEPENDENCIES | {gate.MANIFEST, "backend/src/owned.py"})
    for name in paths:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture")
    manifest = {"version": 1, "base": gate.BASE, "files": paths}
    if damage == "omitted":
        manifest["files"].remove("backend/src/owned.py")
    else:
        target = tmp_path / "backend/src/owned.py"
        target.unlink()
        if damage == "symbolic":
            target.symlink_to(tmp_path / gate.MANIFEST)
    with pytest.raises(ValueError):
        gate.validate_inventory(tmp_path, manifest, {"backend/src/owned.py"})


def test_source_digest_includes_dirty_bytes_and_rejects_missing_tracked_source(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "backend/owned.py"
    source.parent.mkdir()
    source.write_text("one")
    subprocess.run(["git", "add", "backend/owned.py"], cwd=tmp_path, check=True)
    first = gate.source_digest(tmp_path)
    source.write_text("two")
    assert gate.source_digest(tmp_path) != first
    source.unlink()
    with pytest.raises(ValueError):
        gate.source_digest(tmp_path)


@pytest.mark.parametrize(
    "output", ["PASS", "0 passed", "10 passed, 1 skipped", "10 passed, 1 xfailed"]
)
def test_test_statistics_refuse_empty_or_skipped_claims(output):
    with pytest.raises(ValueError):
        gate.statistics(output)


@pytest.mark.parametrize("damage", [None, "omitted", "duplicate", "wrong_module", "skipped"])
def test_migration_evidence_binds_both_distinct_module_round_trips(tmp_path, damage):
    suite = gate.ElementTree.Element("testsuite")
    for module in ("test_submission_schema", "test_submission_review_jobs"):
        gate.ElementTree.SubElement(
            suite,
            "testcase",
            classname=f"tests.integration.{module}",
            name="test_migration_down_up_preserves_existing_imports_and_proposals",
        )
    if damage == "omitted":
        suite.remove(suite[1])
    elif damage == "duplicate":
        suite.append(copy.deepcopy(suite[0]))
    elif damage == "wrong_module":
        suite[1].set("classname", "tests.integration.unrelated")
    elif damage == "skipped":
        gate.ElementTree.SubElement(suite[1], "skipped")
    report = tmp_path / "junit.xml"
    gate.ElementTree.ElementTree(suite).write(report)
    if damage is None:
        gate.validate_backend_report(report)
    else:
        with pytest.raises(ValueError):
            gate.validate_backend_report(report)
