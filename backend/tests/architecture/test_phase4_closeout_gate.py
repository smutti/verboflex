"""Adversarial contracts for the fail-closed closeout evidence boundary."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def verifier():
    spec = importlib.util.spec_from_file_location("phase4_closeout", ROOT / "tools/verify_phase4_closeout.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def document(kind="review", **changes):
    import yaml

    fields = {"source_digest": "sha256:" + "a" * 64}
    fields.update({"verdict": "SECURED"} if kind == "security" else {"status": "passed"})
    if kind == "evidence":
        fields.update(gauntlet_exit=0, smoke_exit=0)
    fields.update(changes)
    table = "\n| ID | Severity | Resolution |\n|---|---|---|\n| R1 | High | resolved |\n"
    return "---\n" + yaml.safe_dump(fields) + "---\n" + table


@pytest.mark.parametrize("kind", ["review", "security", "verification", "evidence"])
def test_exact_valid_artifacts_are_accepted(kind):
    assert verifier().validate_document(document(kind), kind)["source_digest"].startswith("sha256:")


@pytest.mark.parametrize("kind,changes", [
    ("review", {"status": "PASSED"}), ("review", {"status": "pass"}),
    ("security", {"verdict": "secured"}), ("security", {"verdict": "NOT_SECURED"}),
    ("verification", {"status": "Passed"}), ("verification", {"status": None}),
    ("evidence", {"smoke_exit": False}), ("evidence", {"gauntlet_exit": "0"}),
    ("evidence", {"smoke_exit": 1}), ("review", {"source_digest": "sha256:" + "A" * 64}),
    ("review", {"unexpected": "passed"}),
])
def test_wrong_case_type_unknown_fields_and_missing_authority_fail(kind, changes):
    with pytest.raises(ValueError):
        verifier().validate_document(document(kind, **changes), kind)


@pytest.mark.parametrize("severity", ["Critical", "critical", "HIGH", "High", "**High**"])
def test_unresolved_severe_findings_cannot_hide_in_markdown(severity):
    payload = document().replace("| High | resolved |", f"| {severity} | open |")
    with pytest.raises(ValueError):
        verifier().validate_document(payload, "review")


@pytest.mark.parametrize("payload", ["", "status: passed", "---\n[broken\n---", "---\nstatus: passed\nstatus: passed\n---", "---\nnull\n---"])
def test_malformed_and_duplicate_frontmatter_fails(payload):
    with pytest.raises(ValueError):
        verifier().validate_document(payload, "review")


def test_missing_findings_header_and_mismatched_digest_fail():
    module = verifier()
    with pytest.raises(ValueError):
        module.validate_document(document().replace("Resolution", "Disposition"), "review")
    with pytest.raises(ValueError):
        module.validate_digest_agreement([{"source_digest": "sha256:" + "a" * 64}, {"source_digest": "sha256:" + "b" * 64}])

