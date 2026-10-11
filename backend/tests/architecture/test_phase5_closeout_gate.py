"""Fail-closed contract for the final Phase 5 evidence gauntlet."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GATE_PATH = ROOT / "tools/phase5_gate.py"


def gate():
    spec = importlib.util.spec_from_file_location("phase5_closeout_gate", GATE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verification_document(
    *,
    status: str = "human_needed",
    digest: str = "sha256:" + "a" * 64,
    human_evidence: list[dict[str, str]] | None = None,
    phase4_provider_uat: str = "open",
) -> str:
    evidence = human_evidence or []
    return (
        "---\n"
        "phase: 05-review-workspace-and-comments\n"
        f"status: {status}\n"
        f"source_digest: {digest}\n"
        "automated_gauntlet: passed\n"
        "review_gate: passed\n"
        f"phase4_provider_uat: {phase4_provider_uat}\n"
        f"human_evidence: {json.dumps(evidence)}\n"
        "---\n\n# Phase 5 Verification\n"
    )


def human_record(identity: str, *, digest: str = "sha256:" + "a" * 64) -> dict[str, str]:
    return {
        "id": identity,
        "tester": "Human tester",
        "timestamp": "2026-09-10T20:00:00+00:00",
        "environment": "Native browser and local built stack",
        "source_digest": digest,
        "outcome": "passed",
        "observation": "Required behavior was observed without a failure.",
    }


def test_gauntlet_declares_one_exact_ordered_fail_closed_layer_set() -> None:
    module = gate()
    assert module.LAYERS == (
        "manifest-and-gate-controls",
        "migration-round-trip",
        "backend-tests-coverage",
        "backend-types-lint-format",
        "openapi-client-drift",
        "frontend-unit-accessibility-coverage",
        "frontend-types-lint-format-build",
        "phase5-mutations",
        "playwright-review-notifications",
        "built-stack-smoke",
    )


@pytest.mark.parametrize("mode", ["pass", "command-failure", "source-drift", "cleanup-failure"])
def test_gauntlet_certifies_only_complete_stable_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    module = gate()
    calls: list[str] = []

    class ControlledGate:
        directory = tmp_path
        records: list[dict[str, object]] = []

        def start_infrastructure(self) -> None:
            calls.append("infrastructure")

        def command(self, label: str, _command: list[str], **_kwargs: object) -> bytes:
            calls.append(label)
            if mode == "command-failure" and label == module.LAYERS[1]:
                raise ValueError("failed command")
            return b"passed"

        def browser(self) -> None:
            self.command("playwright-review-notifications", ["playwright"])

        def cleanup(self) -> None:
            calls.append("cleanup")
            if mode == "cleanup-failure":
                raise ValueError("failed cleanup")

    digests = iter(
        [
            "sha256:" + "a" * 64,
            "sha256:" + ("b" if mode == "source-drift" else "a") * 64,
        ]
    )
    monkeypatch.setattr(module, "Gate", ControlledGate)
    monkeypatch.setattr(module, "source_digest", lambda: next(digests))
    monkeypatch.setattr(module, "require_clean_source", lambda: None)

    if mode == "pass":
        result = module.run_gauntlet()
        assert result["status"] == "passed"
        assert result["source_digest"] == "sha256:" + "a" * 64
        assert result["sections"] == list(module.LAYERS)
        assert (tmp_path / "result.json").is_file()
    else:
        with pytest.raises((ValueError, RuntimeError)):
            module.run_gauntlet()
        assert not (tmp_path / "result.json").exists()
    assert calls[0] == "infrastructure"
    assert calls[-1] == "cleanup"


def test_human_needed_is_the_only_valid_status_without_both_human_records() -> None:
    module = gate()
    result = module.validate_verification_document(verification_document())
    assert result["status"] == "human_needed"
    assert result["human_evidence"] == []

    with pytest.raises(ValueError, match="human evidence"):
        module.validate_verification_document(verification_document(status="passed"))


def test_passed_requires_both_complete_same_digest_human_records() -> None:
    module = gate()
    digest = "sha256:" + "a" * 64
    records = [human_record("H-05-01", digest=digest), human_record("H-05-02", digest=digest)]
    result = module.validate_verification_document(
        verification_document(status="passed", digest=digest, human_evidence=records),
        require_status="passed",
        require_human=("H-05-01", "H-05-02"),
    )
    assert result["status"] == "passed"
    assert {item["id"] for item in result["human_evidence"]} == {"H-05-01", "H-05-02"}

    records[1]["source_digest"] = "sha256:" + "b" * 64
    with pytest.raises(ValueError, match="digest"):
        module.validate_verification_document(
            verification_document(status="passed", digest=digest, human_evidence=records),
            require_status="passed",
            require_human=("H-05-01", "H-05-02"),
        )


@pytest.mark.parametrize("field", ["tester", "timestamp", "environment", "observation"])
def test_human_records_reject_ambiguous_or_incomplete_evidence(field: str) -> None:
    module = gate()
    records = [human_record("H-05-01"), human_record("H-05-02")]
    records[0][field] = ""
    with pytest.raises(ValueError, match="human evidence"):
        module.validate_verification_document(
            verification_document(status="passed", human_evidence=records)
        )


def test_phase4_provider_uat_must_remain_separately_open() -> None:
    module = gate()
    with pytest.raises(ValueError, match="Phase 4 provider UAT"):
        module.validate_verification_document(verification_document(phase4_provider_uat="closed"))


def test_verify_phase_cli_accepts_human_needed_but_rejects_false_pass(tmp_path: Path) -> None:
    artifact = tmp_path / "verification.md"
    current_digest = gate().source_digest()
    artifact.write_text(verification_document(digest=current_digest), encoding="utf-8")
    accepted = module_result = __import__("subprocess").run(
        [
            sys.executable,
            str(GATE_PATH),
            "verify-phase",
            "--artifact",
            str(artifact),
            "--allow-status",
            "human_needed",
        ],
        capture_output=True,
        text=True,
    )
    assert accepted.returncode == 0, module_result.stderr
    assert json.loads(accepted.stdout)["status"] == "human_needed"

    artifact.write_text(
        verification_document(status="passed", digest=current_digest), encoding="utf-8"
    )
    rejected = __import__("subprocess").run(
        [
            sys.executable,
            str(GATE_PATH),
            "verify-phase",
            "--artifact",
            str(artifact),
            "--allow-status",
            "human_needed",
        ],
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 1
    assert json.loads(rejected.stderr)["reason"] == "phase evidence failed closed"
