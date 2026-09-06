"""Adversarial contracts for the fail-closed closeout evidence boundary."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def planned_rows():
    rows = {}
    for plan in (ROOT / ".planning/phases/04-localization-import-search-and-constraints").glob(
        "04-*-PLAN.md"
    ):
        for line in plan.read_text().splitlines():
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells[0].startswith("T-04-"):
                rows[cells[0]] = cells
    return rows


def verifier():
    spec = importlib.util.spec_from_file_location(
        "phase4_closeout", ROOT / "tools/verify_phase4_closeout.py"
    )
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
    if kind == "security":
        table = "\n| ID | Severity | Disposition | Evidence | Resolution |\n|---|---|---|---|---|\n"
        for identifier, row in sorted(planned_rows().items()):
            table += (
                f"| {identifier} | {row[3].title()} | {row[4]} | "
                "tests/unit/test_auth.py::test_denied | resolved |\n"
            )
    return "---\n" + yaml.safe_dump(fields) + "---\n" + table


@pytest.mark.parametrize(
    "disposition", ["accept", "accepted", "transfer", "transferred", "avoid", ""]
)
def test_severe_security_threat_cannot_be_waived(disposition):
    with pytest.raises(ValueError):
        verifier().validate_document(
            document("security").replace("| mitigate |", f"| {disposition} |"), "security"
        )


@pytest.mark.parametrize("evidence", ["", "none", "pending", "n/a"])
def test_severe_security_threat_requires_actual_evidence(evidence):
    with pytest.raises(ValueError):
        verifier().validate_document(
            document("security").replace("tests/unit/test_auth.py::test_denied", evidence),
            "security",
        )


@pytest.mark.parametrize("kind", ["review", "security", "verification", "evidence"])
def test_exact_valid_artifacts_are_accepted(kind):
    assert verifier().validate_document(document(kind), kind)["source_digest"].startswith("sha256:")


@pytest.mark.parametrize("defect", ["missing", "duplicate", "unknown", "only-fabricated"])
def test_security_requires_all_planned_threats_exactly_once(defect):
    payload = document("security")
    row = "| T-04-01 | High | mitigate | tests/unit/test_auth.py::test_denied | resolved |\n"
    if defect == "missing":
        payload = payload.replace(row, "")
    elif defect == "duplicate":
        payload += row
    elif defect == "unknown":
        payload = payload.replace("| T-04-01 |", "| T-04-99 |")
    else:
        payload = payload.split("| T-04-01 |", 1)[0] + row.replace("T-04-01", "T1")
    with pytest.raises(ValueError):
        verifier().validate_document(payload, "security")


@pytest.mark.parametrize(
    "identifier,old,new",
    [
        ("T-04-01", "High | mitigate", "low | accept"),
        ("T-04-37", "Medium | mitigate", "Medium | accept"),
        ("T-04-25", "Medium | accept", "Medium | transfer"),
    ],
)
def test_security_metadata_cannot_downgrade_the_planned_register(identifier, old, new):
    payload = document("security")
    original = f"| {identifier} | {old} |"
    assert original in payload
    payload = payload.replace(original, f"| {identifier} | {new} |")
    if identifier == "T-04-01":
        payload = payload.replace("test_denied | resolved", "test_denied | open", 1)
    with pytest.raises(ValueError):
        verifier().validate_document(payload, "security")


@pytest.mark.parametrize("conflict", ["severity", "disposition", "consistent"])
def test_duplicate_planned_threat_metadata_must_agree(tmp_path, monkeypatch, conflict):
    rows = planned_rows()
    plan = "\n".join("| " + " | ".join(row) + " |" for row in rows.values())
    duplicate = rows["T-04-SC"].copy()
    if conflict == "severity":
        duplicate[3] = "low"
    elif conflict == "disposition":
        duplicate[4] = "accept"
    (tmp_path / "04-01-PLAN.md").write_text(plan)
    (tmp_path / "04-02-PLAN.md").write_text("| " + " | ".join(duplicate) + " |")
    module = verifier()
    monkeypatch.setattr(module, "PHASE", tmp_path)
    if conflict == "consistent":
        assert module.validate_document(document("security"), "security")["verdict"] == "SECURED"
    else:
        with pytest.raises(ValueError):
            module.validate_document(document("security"), "security")


def test_review_scope_metadata_is_typed_and_preserved():
    metadata = dict(
        reviewed="2026-09-06T10:16:26Z",
        depth="standard",
        files_reviewed=1,
        files_reviewed_list=["backend/src/verboflex/services/translation_search.py"],
        findings={"critical": 0, "warning": 0, "info": 0, "total": 0},
    )
    parsed = verifier().validate_document(document(**metadata), "review")
    assert all(parsed[key] == value for key, value in metadata.items())


@pytest.mark.parametrize(
    "changes",
    [
        {"reviewed": False},
        {"reviewed": "yesterday"},
        {"depth": []},
        {"files_reviewed": True},
        {"files_reviewed": -1},
        {"files_reviewed_list": "backend/a.py"},
        {"files_reviewed_list": [True]},
        {"findings": []},
        {"findings": {"critical": False}},
        {"findings": {"critical": -1, "warning": 0, "info": 0, "total": -1}},
    ],
)
def test_review_scope_metadata_rejects_malformed_values(changes):
    with pytest.raises(ValueError):
        verifier().validate_document(document(**changes), "review")


@pytest.mark.parametrize(
    "kind,changes",
    [
        ("review", {"status": "PASSED"}),
        ("review", {"status": "pass"}),
        ("security", {"verdict": "secured"}),
        ("security", {"verdict": "NOT_SECURED"}),
        ("verification", {"status": "Passed"}),
        ("verification", {"status": None}),
        ("evidence", {"smoke_exit": False}),
        ("evidence", {"gauntlet_exit": "0"}),
        ("evidence", {"smoke_exit": 1}),
        ("review", {"source_digest": "sha256:" + "A" * 64}),
        ("review", {"unexpected": "passed"}),
    ],
)
def test_wrong_case_type_unknown_fields_and_missing_authority_fail(kind, changes):
    with pytest.raises(ValueError):
        verifier().validate_document(document(kind, **changes), kind)


@pytest.mark.parametrize("severity", ["Critical", "critical", "HIGH", "High", "**High**"])
def test_unresolved_severe_findings_cannot_hide_in_markdown(severity):
    payload = document().replace("| High | resolved |", f"| {severity} | open |")
    with pytest.raises(ValueError):
        verifier().validate_document(payload, "review")


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "status: passed",
        "---\n[broken\n---",
        "---\nstatus: passed\nstatus: passed\n---",
        "---\nnull\n---",
    ],
)
def test_malformed_and_duplicate_frontmatter_fails(payload):
    with pytest.raises(ValueError):
        verifier().validate_document(payload, "review")


def test_missing_findings_header_and_mismatched_digest_fail():
    module = verifier()
    with pytest.raises(ValueError):
        module.validate_document(document().replace("Resolution", "Disposition"), "review")
    with pytest.raises(ValueError):
        module.validate_digest_agreement(
            [{"source_digest": "sha256:" + "a" * 64}, {"source_digest": "sha256:" + "b" * 64}]
        )


def test_plan20_cli_flags_reach_fail_closed_validation(tmp_path):
    import json
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/verify_phase4_closeout.py"),
            "--check-all",
            "--manifest",
            str(ROOT / "tools/phase4_source_manifest.txt"),
            "--evidence",
            str(tmp_path / "missing.md"),
            "--code-review",
            str(tmp_path / "missing.md"),
            "--security-review",
            str(tmp_path / "missing.md"),
            "--review-ledger",
            str(tmp_path / "missing.md"),
            "--verification",
            str(tmp_path / "missing.md"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert json.loads(result.stderr)["status"] == "failed"
