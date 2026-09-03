#!/usr/bin/env python3
"""Fail-closed targeted mutation proof for Phase 3 import authority."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
TEST_SELECTION = ("tests/integration/test_import_jobs.py",)
TEST_EXPRESSION = " or ".join(
    (
        "test_current_capability_and_branch_resolution_are_fresh_for_every_execution",
        "test_retry_replaces_current_projection_and_retains_the_previous_baseline",
        "test_current_capability_generation_is_revalidated_before_completion",
        "test_terminal_completion_requires_the_persisted_execution_generation",
        "test_late_worker_completion_cannot_overwrite_a_newer_retry",
        "test_classify_incomplete_or_forged_comparison_has_no_confirmation_authority",
        "test_rewrite_confirmation_rejects_stale_identity_without_pointer_change",
        "test_public_contract_maps_provider_failures_to_closed_fixed_errors",
    )
)


class MutationProofError(RuntimeError):
    """Raised when one reviewed import mutant is not proven killed."""


@dataclass(frozen=True, slots=True)
class Mutation:
    label: str
    relative_path: str
    original: str
    replacement: str


MUTATIONS = (
    Mutation(
        "capability:accepts-wrong-scope-profile",
        "src/verboflex/services/import_jobs.py",
        "        or connection.scope_profile != PULLREQUEST_WRITE_SCOPE\n"
        "        or connection.provider_expires_at is None\n",
        "        or connection.scope_profile == PULLREQUEST_WRITE_SCOPE\n"
        "        or connection.provider_expires_at is None\n",
    ),
    Mutation(
        "state:increments-retry-on-success",
        "src/verboflex/services/import_jobs.py",
        '            if current_execution.state == "failed":\n'
        "                job.retry_count += 1\n",
        '            if current_execution.state != "failed":\n'
        "                job.retry_count += 1\n",
    ),
    Mutation(
        "provenance:terminal-write-ignores-connection-generation",
        "src/verboflex/services/import_jobs.py",
        "                ImportExecution.sequence == identity.sequence,\n"
        "                ImportExecution.connection_generation "
        "== identity.connection_generation,\n",
        "                ImportExecution.sequence == identity.sequence,\n"
        "                ImportExecution.connection_generation >= 0,\n",
    ),
    Mutation(
        "ancestry:accepts-incomplete-comparison",
        "src/verboflex/services/import_jobs.py",
        "                ancestry.complete is not True\n"
        "                or ancestry.old_commit_hash != source.active_commit_hash\n",
        "                ancestry.complete is False\n"
        "                or ancestry.old_commit_hash != source.active_commit_hash\n",
    ),
    Mutation(
        "rewrite:inverts-confirmation-digest-authority",
        "src/verboflex/services/import_jobs.py",
        "            proposal.proposed_execution_id != proposed_execution_id\n"
        "            or proposal.digest != proposal_digest\n",
        "            proposal.proposed_execution_id != proposed_execution_id\n"
        "            or proposal.digest == proposal_digest\n",
    ),
    Mutation(
        "error:collapses-provider-failure-category",
        "src/verboflex/services/import_jobs.py",
        "            failure_category=_provider_failure_category(error.kind),\n",
        '            failure_category="provider_unavailable",\n',
    ),
)


def replace_once(path: Path, original: str, replacement: str) -> None:
    """Apply exactly one mutation or fail closed on source drift."""
    source = path.read_text(encoding="utf-8")
    count = source.count(original)
    if count != 1:
        raise MutationProofError(
            f"mutation subject drifted for {path}: expected 1 occurrence, found {count}"
        )
    if original == replacement:
        raise MutationProofError("mutation replacement must change the subject")
    path.write_text(source.replace(original, replacement, 1), encoding="utf-8")


def copy_backend(destination: Path) -> Path:
    """Copy backend sources without caches, reports, or its virtual environment."""
    target = destination / "backend"
    ignored = shutil.ignore_patterns(
        ".coverage",
        ".hypothesis",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "coverage*.xml",
        "htmlcov",
        "mutants",
    )
    shutil.copytree(BACKEND_ROOT, target, ignore=ignored)
    return target


def run_suite(backend: Path) -> subprocess.CompletedProcess[str]:
    """Run the bounded import authority selection in one isolated source copy."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(backend / "src")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *TEST_SELECTION,
            "-k",
            TEST_EXPRESSION,
            "-x",
        ],
        cwd=backend,
        env=environment,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )


def prove_mutations() -> None:
    """Require a green baseline and an assertion failure for every mutant."""
    with tempfile.TemporaryDirectory(prefix="verboflex-import-mutants-") as temp_dir:
        workspace = Path(temp_dir)
        baseline = run_suite(copy_backend(workspace / "baseline"))
        if baseline.returncode != 0:
            raise MutationProofError(
                "mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        print("baseline: PASS")

        killed = 0
        for index, mutation in enumerate(MUTATIONS, start=1):
            mutant_backend = copy_backend(workspace / f"mutant-{index}")
            replace_once(
                mutant_backend / mutation.relative_path,
                mutation.original,
                mutation.replacement,
            )
            result = run_suite(mutant_backend)
            combined = result.stdout + result.stderr
            if result.returncode == 0:
                raise MutationProofError(f"surviving mutant: {mutation.label}")
            if "failed" not in combined.casefold() and "error" not in combined.casefold():
                raise MutationProofError(
                    f"mutant did not reach an assertion failure: {mutation.label}\n{combined}"
                )
            killed += 1
            print(f"{mutation.label}: KILLED")

        if killed != len(MUTATIONS):
            raise MutationProofError("mutation count mismatch")
        print(f"mutation score: {killed}/{len(MUTATIONS)} killed")


def self_test() -> None:
    """Prove source drift and an equivalent replacement reach failure paths."""
    with tempfile.TemporaryDirectory(prefix="verboflex-import-control-") as temp_dir:
        control = Path(temp_dir) / "control.py"
        control.write_text("state = 'running'\n", encoding="utf-8")
        for original, replacement in (
            ("missing = True", "missing = False"),
            ("state = 'running'", "state = 'running'"),
        ):
            try:
                replace_once(control, original, replacement)
            except MutationProofError:
                continue
            raise MutationProofError("mutation checker negative control unexpectedly passed")
    print("mutation checker negative control: PASS")


def main() -> int:
    """Run the negative control or the complete mutation proof."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.self_test:
            self_test()
        else:
            prove_mutations()
    except (MutationProofError, OSError, subprocess.SubprocessError) as error:
        print(f"mutation proof failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
