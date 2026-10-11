"""Static adversaries for Phase 5 notification privacy invariants."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = ROOT.parent


def gate():
    spec = importlib.util.spec_from_file_location(
        "phase5_gate", REPOSITORY_ROOT / "tools/phase5_gate.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def mutant_runner():
    spec = importlib.util.spec_from_file_location(
        "verify_phase5_mutants", REPOSITORY_ROOT / "tools/verify_phase5_mutants.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_notification_services_never_accept_recipient_authority() -> None:
    path = ROOT / "src/verboflex/services/notifications.py"
    assert path.exists()
    tree = ast.parse(path.read_text())
    required = {
        "list_notifications",
        "list_recent_notifications",
        "get_unread_notification_count",
        "mark_notification_read",
        "mark_notification_read_by_comment",
        "stream_notification_invalidations",
    }
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in required
    }
    assert set(functions) == required
    for node in functions.values():
        arguments = {argument.arg for argument in (*node.args.args, *node.args.kwonlyargs)}
        assert "principal" in arguments
        assert not ({"recipient", "recipient_id", "recipient_user_id"} & arguments)


def test_stream_route_has_no_browser_controlled_recipient_or_channel() -> None:
    path = ROOT / "src/verboflex/api/v1/routes/notifications.py"
    tree = ast.parse(path.read_text())
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "get_notification_stream"
    }
    assert set(functions) == {"get_notification_stream"}
    node = functions["get_notification_stream"]
    arguments = {argument.arg for argument in (*node.args.args, *node.args.kwonlyargs)}
    assert "principal" in arguments
    assert not ({"recipient", "recipient_id", "recipient_user_id", "channel"} & arguments)


def test_invalidation_payload_is_closed_and_content_free() -> None:
    path = ROOT / "src/verboflex/services/notifications.py"
    tree = ast.parse(path.read_text())
    payload_classes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "NotificationInvalidation"
    ]
    assert len(payload_classes) == 1
    fields = {
        node.target.id
        for node in payload_classes[0].body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert fields == {"kind", "id"}


def test_every_notification_query_and_update_contains_principal_predicate() -> None:
    source = (ROOT / "src/verboflex/services/notifications.py").read_text()
    # Public collection methods share the owned-query helper; both mutation
    # selectors repeat the predicate at their write boundary.
    assert source.count("Notification.recipient_user_id == principal.user_id") >= 3
    assert "Notification.originating_comment_id == comment_id" in source
    assert "Notification.kind == NotificationKind.MENTION.value" in source
    assert "resolve_translation_group_access(" in source


def test_public_schema_has_no_recipient_or_comment_body_fields() -> None:
    path = ROOT / "src/verboflex/schemas/notifications.py"
    assert path.exists()
    tree = ast.parse(path.read_text())
    field_names = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        for target in (node.target,)
        if isinstance(target, ast.Name)
    }
    assert not ({"recipient", "recipient_id", "recipient_user_id", "body"} & field_names)


def test_phase5_source_manifest_is_exact_and_behavioral() -> None:
    assert gate().validate_manifest() == {
        "REQUIREMENT": 20,
        "DECISION": 21,
        "EDGE": 29,
        "UI_CATEGORY": 8,
        "PROHIBITION": 9,
        "AUTHORITY": 1,
    }


@pytest.mark.parametrize("change", ["missing", "duplicate", "unknown", "stale", "inventory-only"])
def test_phase5_manifest_rejects_silent_or_non_behavioral_coverage(change: str) -> None:
    module = gate()
    rows = module.read_manifest()
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows.append(dict(rows[0]))
    elif change == "unknown":
        rows.append({**rows[0], "id": "unowned-source-obligation"})
    elif change == "stale":
        rows[0] = {**rows[0], "tests": ["backend/tests/absent.py::test_absent"]}
    else:
        rows[0] = {
            **rows[0],
            "tests": [
                "backend/tests/architecture/test_phase5_mutation_verifier.py::"
                "test_phase5_source_manifest_is_exact_and_behavioral"
            ],
        }
    with pytest.raises(ValueError):
        module.validate_manifest(rows)


@pytest.mark.parametrize(
    ("severity", "blocked"),
    [("low", False), ("MEDIUM", False), ("High", True), ("critical", True)],
)
def test_review_threshold_orders_high_and_critical(severity: str, blocked: bool) -> None:
    findings = [{"id": "F-01", "severity": severity, "resolution": "open"}]
    if blocked:
        with pytest.raises(ValueError, match="review threshold"):
            gate().verify_review_findings(findings, block_on="high")
    else:
        assert gate().verify_review_findings(findings, block_on="high") == {
            "status": "passed",
            "finding_count": 1,
            "unresolved_blocking_count": 0,
        }


@pytest.mark.parametrize("severity", ["", "urgent", "high-ish", None, 4])
def test_review_threshold_rejects_malformed_or_unknown_severity(severity: object) -> None:
    with pytest.raises(ValueError, match="severity"):
        gate().verify_review_findings(
            [{"id": "F-01", "severity": severity, "resolution": "open"}],
            block_on="high",
        )


def test_verify_review_cli_is_case_insensitive_fail_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "review.md"
    artifact.write_text(
        "# Review\n\n| Finding | Severity | Resolution |\n"
        "|---|---|---|\n| F-01 | CRITICAL | open |\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "tools/phase5_gate.py"),
            "verify-review",
            "--artifact",
            str(artifact),
            "--block-on",
            "high",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert json.loads(result.stderr) == {
        "status": "failed",
        "reason": "review evidence failed closed",
    }


def test_evidence_record_contains_only_bounded_digest_status_and_timing() -> None:
    record = gate().evidence_record(
        status="passed",
        source=b"repository-owned source bytes",
        output=b"token recipient user comment translation provider exception",
        started_at="2026-09-10T12:00:00+00:00",
        completed_at="2026-09-10T12:00:01+00:00",
        duration_seconds=1.0,
    )
    assert set(record) == {
        "status",
        "source_sha256",
        "output_sha256",
        "started_at",
        "completed_at",
        "duration_seconds",
    }
    serialized = json.dumps(record, sort_keys=True).lower()
    for forbidden in (
        "token",
        "recipient",
        "user",
        "comment",
        "translation",
        "provider",
        "exception",
    ):
        assert forbidden not in serialized


def test_phase5_mutant_inventory_is_closed_and_behavioral() -> None:
    module = mutant_runner()
    expected = {
        "proposal-version",
        "proposal-selector-atomicity",
        "review-role-widening",
        "review-constraint-bypass",
        "resolver-bypass",
        "resolver-duplicate-lookup",
        "resolver-role-widening",
        "resolver-unavailable-distinction",
        "comment-stable-scope",
        "comment-history-role",
        "comment-history-tombstone",
        "mention-identity",
        "notification-dedupe",
        "cursor-binding",
        "cursor-signature",
        "notification-schema-widening",
        "notification-schema-field-omission",
        "anchor-bound",
        "anchor-group",
        "origin-read-recipient",
        "origin-read-kind",
        "origin-read-group",
        "premature-read",
        "content-bearing-sse",
        "stale-page",
        "logout-cache",
    }
    assert {mutation.label for mutation in module.MUTATIONS} == expected
    assert len(module.MUTATIONS) == len(expected)
    for mutation in module.MUTATIONS:
        assert mutation.command
        assert "test" in " ".join(mutation.command)
        assert mutation.original != mutation.replacement
        assert (REPOSITORY_ROOT / mutation.path).is_file()


@pytest.mark.parametrize("returncode", [0, 2, 5])
def test_mutant_kill_accepts_only_behavioral_exit_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode: int
) -> None:
    module = mutant_runner()
    source = tmp_path / "subject.py"
    original = b"VALUE = True\n"
    source.write_bytes(original)
    mutation = module.Mutation(
        "bounded-probe",
        "subject.py",
        "VALUE = True",
        "VALUE = False",
        (sys.executable, "-c", "raise SystemExit(1)"),
    )
    monkeypatch.setattr(module, "execute", lambda *_args, **_kwargs: returncode)

    with pytest.raises(ValueError, match="behavioral test exit 1"):
        module.run_mutation(mutation, root=tmp_path)
    assert source.read_bytes() == original


def test_mutant_kill_restores_exact_bytes_after_success(tmp_path: Path) -> None:
    module = mutant_runner()
    source = tmp_path / "subject.py"
    original = b"VALUE = True\r\n"
    source.write_bytes(original)
    mutation = module.Mutation(
        "bounded-probe",
        "subject.py",
        "VALUE = True",
        "VALUE = False",
        (sys.executable, "-c", "raise SystemExit(1)"),
    )

    record = module.run_mutation(mutation, root=tmp_path)

    assert source.read_bytes() == original
    assert set(record) == {"status", "source_sha256", "duration_seconds"}
    assert record["status"] == "killed"


@pytest.mark.parametrize("failure", [ValueError("timeout"), KeyboardInterrupt()])
def test_mutant_kill_restores_exact_bytes_after_failure_or_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
) -> None:
    module = mutant_runner()
    source = tmp_path / "subject.py"
    original = b"VALUE = True\n"
    source.write_bytes(original)
    mutation = module.Mutation(
        "bounded-probe",
        "subject.py",
        "VALUE = True",
        "VALUE = False",
        (sys.executable, "-c", "raise SystemExit(1)"),
    )

    def fail(*_args: object, **_kwargs: object) -> int:
        raise failure

    monkeypatch.setattr(module, "execute", fail)
    with pytest.raises(type(failure)):
        module.run_mutation(mutation, root=tmp_path)
    assert source.read_bytes() == original


def test_mutant_lock_is_exclusive_and_reusable(tmp_path: Path) -> None:
    module = mutant_runner()
    with (
        module.mutation_lock(tmp_path),
        pytest.raises(BlockingIOError),
        module.mutation_lock(tmp_path),
    ):
        pass
    with module.mutation_lock(tmp_path):
        assert os.path.exists(module.lock_path(tmp_path))
