"""Run a closed inventory of behavioral safeguards; never expose private test output."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from verify_phase5_mutants import _remove_bytecode, mutation_lock, stop

ROOT = Path(__file__).resolve().parents[1]
PYTHON = str(ROOT / "backend/.venv/bin/python")
MAX_PRIVATE_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 70


@dataclass(frozen=True, slots=True)
class Mutation:
    name: str
    path: str
    original: str
    replacement: str
    test: str
    engine: str
    assertion: str


WRITES = "backend/src/verboflex/integrations/bitbucket/writes.py"
MUTATIONS = (
    Mutation(
        "approved-aggregate",
        "backend/src/verboflex/services/writeback_authority.py",
        '            or proposal.state != "approved"\n',
        "",
        "backend/tests/integration/test_submission_review_jobs.py::"
        "test_non_complete_approved_selection_never_creates_intent[draft]",
        "pytest",
        r"DID NOT RAISE.*WritebackRejected",
    ),
    Mutation(
        "review-role",
        "backend/src/verboflex/services/submission_reviews.py",
        "if action and REVIEW_ROLES.isdisjoint(roles):",
        "if False:",
        "backend/tests/api/test_submission_reviews.py::"
        "test_read_only_roles_can_read_but_cannot_request_review[viewer]",
        "pytest",
        r"assert 202 == 403",
    ),
    Mutation(
        "commit-parent-cas",
        WRITES,
        '                    "parents": intent.branch.parent,\n',
        "",
        "backend/tests/architecture/test_phase7_mutants.py::"
        "test_commit_send_binds_expected_parent_for_provider_cas",
        "pytest",
        r'assert provider\.fields\.get\("parents"\) == PARENT',
    ),
    Mutation(
        "missing-branch-unknown",
        WRITES,
        "            if existing is None:\n"
        '                return WriteOutcome("unknown", "branch_missing")\n'
        "            if existing.commit_hash == intent.branch.parent:",
        "            if existing is None:\n"
        '                return WriteOutcome("not_sent", "branch_missing")\n'
        "            if existing.commit_hash == intent.branch.parent:",
        "backend/tests/integration/test_bitbucket_write_adapter.py::"
        "test_commit_lost_reply_is_read_only_reconciled_and_never_recreated_when_missing",
        "pytest",
        r'assert missing\.state == "unknown"',
    ),
    Mutation(
        "unknown-pr-no-repost",
        WRITES,
        "            if not matches:\n"
        '                return WriteOutcome("unknown", "pull_request_not_observed")',
        "            if not matches:\n"
        "                return await self.create_pull_request(session, intent=intent)",
        "backend/tests/integration/test_bitbucket_pr_adapter.py::"
        "test_reconcile_lost_or_late_original_send_never_creates_a_second_pr[delayed]",
        "pytest",
        r"assert len\(provider\.posts\) == 1",
    ),
    Mutation(
        "newer-proposal-preserved",
        "backend/src/verboflex/services/submission_jobs.py",
        '                row.pr_target_commit, row.stage = receipt.target_commit, "complete"',
        '                row.pr_target_commit, row.stage = receipt.target_commit, "complete"\n'
        "                from verboflex.models.review import TranslationProposal\n"
        "                for item in load_change_set_bundle(session, row.id)"
        ".proof.selection.proposals:\n"
        '                    session.get(TranslationProposal, item.proposal_id).state = "approved"',
        "backend/tests/integration/test_submission_jobs.py::"
        "test_newer_proposal_after_pr_response_survives_old_completion",
        "pytest",
        r'assert proposal\.version == seed\.version \+ 1 and proposal\.state == "draft"',
    ),
    Mutation(
        "frontend-safe-href",
        "frontend/src/features/change-sets/safePullRequestUrl.ts",
        "return pr_url === expected ? pr_url : null;",
        "return pr_url;",
        "frontend/src/features/change-sets/safePullRequestUrl.test.ts::"
        "rejects unsafe or ambiguous URL javascript:alert(1)",
        "vitest",
        r"expected 'javascript:alert\(1\)' to be null",
    ),
)


def command_for(mutation: Mutation, report: Path) -> tuple[str, ...]:
    if mutation.engine == "pytest":
        return (
            PYTHON,
            "-m",
            "pytest",
            mutation.test,
            "-q",
            "--tb=short",
            "--import-mode=importlib",
            f"--junitxml={report}",
        )
    if mutation.engine == "vitest":
        path, title = mutation.test.split("::", 1)
        return (
            "npm",
            "--prefix",
            "frontend",
            "test",
            "--",
            "--run",
            path.removeprefix("frontend/"),
            "-t",
            "^" + re.escape(title) + "$",
            "--reporter=json",
            f"--outputFile={report}",
        )
    raise ValueError("unknown mutation engine")


def execute(command: tuple[str, ...], root: Path, timeout: float) -> int:
    """Bound output on private disk and always reap the owned child process group."""
    with tempfile.TemporaryFile() as output:
        child = subprocess.Popen(
            command, cwd=root, stdout=output, stderr=output, start_new_session=True
        )
        deadline = time.monotonic() + timeout
        try:
            while child.poll() is None:
                if (
                    time.monotonic() >= deadline
                    or os.fstat(output.fileno()).st_size > MAX_PRIVATE_BYTES
                ):
                    raise ValueError("mutation command exceeded its budget")
                time.sleep(0.02)
            if os.fstat(output.fileno()).st_size > MAX_PRIVATE_BYTES:
                raise ValueError("mutation output exceeded its budget")
            return child.returncode
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)


def validate_report(mutation: Mutation, report: Path, code: int, *, killed: bool) -> None:
    if code != int(killed):
        raise ValueError("behavioral result rejected")
    try:
        if report.stat().st_size > MAX_PRIVATE_BYTES:
            raise ValueError("mutation report exceeded its budget")
        raw = report.read_bytes()
        title = mutation.test.split("::", 1)[1]
        if mutation.engine == "pytest":
            if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
                raise ValueError("mutation XML declarations rejected")
            tree = ET.fromstring(raw)
            cases = list(tree.iter("testcase"))
            if (
                len(cases) != 1
                or cases[0].get("name") != title
                or list(tree.iter("error"))
                or list(tree.iter("skipped"))
            ):
                raise ValueError("named call-phase result required")
            failures = list(tree.iter("failure"))
            if len(failures) != int(killed):
                raise ValueError("unexpected behavioral result count")
            detail = "" if not failures else "".join(failures[0].itertext())
            if killed and not (
                failures[0].get("message", "").startswith("assert ")
                or "AssertionError" in detail
                or "DID NOT RAISE" in detail
            ):
                raise ValueError("non-assertion failure rejected")
        elif mutation.engine == "vitest":
            data = json.loads(raw)
            suites = data.get("testResults", [])
            if (
                len(suites) != 1
                or data.get("success") is not (not killed)
                or data.get("numFailedTests") != int(killed)
                or data.get("numPassedTests") != int(not killed)
                or data.get("numRuntimeErrorTestSuites", 0) != 0
                or suites[0].get("message")
            ):
                raise ValueError("unexpected frontend result counts")
            cases = suites[0].get("assertionResults", [])
            selected = [case for case in cases if case.get("fullName") == title]
            if (
                len(selected) != 1
                or selected[0].get("status") != ("failed" if killed else "passed")
                or any(
                    case.get("status") not in {"pending", "todo", "skipped"}
                    for case in cases
                    if case is not selected[0]
                )
                or suites[0].get("testExecError")
            ):
                raise ValueError("exact frontend assertion required")
            detail = "\n".join(selected[0].get("failureMessages") or [])
            if killed and "AssertionError" not in detail:
                raise ValueError("non-assertion frontend failure rejected")
        else:
            raise ValueError("unknown report engine")
        if killed and not re.search(mutation.assertion, detail):
            raise ValueError("intended behavioral assertion did not fail")
    except (OSError, ET.ParseError, KeyError, TypeError, AttributeError) as error:
        raise ValueError("mutation report rejected") from error


def run_probe(mutation: Mutation, root: Path, timeout: float, *, killed: bool) -> None:
    with tempfile.TemporaryDirectory(prefix="verboflex-phase7-mutant-") as directory:
        report = Path(directory) / ("report.xml" if mutation.engine == "pytest" else "report.json")
        report.touch(mode=0o600)
        code = execute(command_for(mutation, report), root, timeout)
        validate_report(mutation, report, code, killed=killed)


def run_mutation(
    mutation: Mutation, *, root: Path = ROOT, timeout: float = TIMEOUT_SECONDS
) -> dict[str, object]:
    started = time.monotonic()
    path = root / mutation.path
    original = path.read_bytes()
    source = original.decode("utf-8")
    if not mutation.original or source.count(mutation.original) != 1:
        raise ValueError("mutation target identity drift")
    changed = source.replace(mutation.original, mutation.replacement, 1)
    if path.suffix == ".py":
        ast.parse(changed)
    run_probe(mutation, root, timeout, killed=False)
    if path.read_bytes() != original:
        raise ValueError("source changed during baseline")
    try:
        path.write_text(changed, encoding="utf-8")
        _remove_bytecode(path)
        run_probe(mutation, root, timeout, killed=True)
    finally:
        path.write_bytes(original)
        _remove_bytecode(path)
        if path.read_bytes() != original:
            raise ValueError("source restoration failed")
    return {
        "name": mutation.name,
        "status": "killed",
        "test": mutation.test,
        "duration_seconds": round(time.monotonic() - started, 3),
    }


def source_digest(root: Path) -> dict[str, str]:
    return {
        path: hashlib.sha256((root / path).read_bytes()).hexdigest()
        for path in sorted({m.path for m in MUTATIONS})
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        print(json.dumps([{"name": m.name, "test": m.test} for m in MUTATIONS]))
        return 0
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    with mutation_lock(ROOT):
        if len(MUTATIONS) != 7 or len({m.name for m in MUTATIONS}) != 7:
            raise ValueError("mutation inventory rejected")
        original = source_digest(ROOT)
        results = [run_mutation(m) for m in MUTATIONS]
        if source_digest(ROOT) != original:
            raise ValueError("source inventory restoration failed")
    print(
        "phase7 mutants evidence: "
        + json.dumps(
            {
                "status": "pass",
                "killed": len(results),
                "survived": 0,
                "source_restored": True,
                "mutants": results,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt, OSError, ValueError, SyntaxError:
        print(
            "phase7 mutants evidence: "
            + json.dumps(
                {
                    "status": "failed",
                    "source_restored": False,
                    "reason": "mutation verification failed closed",
                }
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
