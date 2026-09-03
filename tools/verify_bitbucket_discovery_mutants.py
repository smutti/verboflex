#!/usr/bin/env python3
"""Fail-closed targeted mutation proof for commit-bound Bitbucket discovery."""

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
COVERAGE_SOURCE = (
    REPOSITORY_ROOT / ".planning" / "phases" / "02-admin-configuration" / "COVERAGE.md"
)
TEST_SELECTION = (
    "tests/integration/test_bitbucket_discovery.py",
    "tests/architecture/test_provider_boundaries.py",
)


class MutationProofError(RuntimeError):
    """The checker could not establish one exact killed mutation."""


@dataclass(frozen=True, slots=True)
class Mutation:
    """One reviewed transformation representing a discovery-boundary defect."""

    label: str
    relative_path: str
    original: str
    replacement: str


MUTATIONS = (
    Mutation(
        "page-budget-increased",
        "src/verboflex/services/repository_discovery.py",
        "    max_pages=50,",
        "    max_pages=51,",
    ),
    Mutation(
        "entry-budget-increased",
        "src/verboflex/services/repository_discovery.py",
        "    max_entries=5_000,",
        "    max_entries=5_001,",
    ),
    Mutation(
        "depth-budget-increased",
        "src/verboflex/services/repository_discovery.py",
        "    max_depth=12,",
        "    max_depth=13,",
    ),
    Mutation(
        "candidate-budget-increased",
        "src/verboflex/services/repository_discovery.py",
        "    max_candidate_files=500,",
        "    max_candidate_files=501,",
    ),
    Mutation(
        "single-file-budget-increased",
        "src/verboflex/services/repository_discovery.py",
        "    max_file_bytes=1_048_576,",
        "    max_file_bytes=1_048_577,",
    ),
    Mutation(
        "aggregate-budget-increased",
        "src/verboflex/services/repository_discovery.py",
        "    max_total_bytes=20_971_520,",
        "    max_total_bytes=20_971_521,",
    ),
    Mutation(
        "ios-source-candidate-dropped",
        "src/verboflex/services/repository_discovery.py",
        '_CANDIDATE_SUFFIXES = (".xml", ".ts", ".json", ".strings")',
        '_CANDIDATE_SUFFIXES = (".xml", ".ts", ".json", ".txt")',
    ),
    Mutation(
        "duplicate-path-rejection-disabled",
        "src/verboflex/services/repository_discovery.py",
        "                if path in seen_paths:",
        "                if False:",
    ),
    Mutation(
        "resolved-branch-name-check-disabled",
        "src/verboflex/services/repository_discovery.py",
        "    if resolved.name != branch:",
        "    if False:",
    ),
    Mutation(
        "cross-resource-continuation-enabled",
        "src/verboflex/integrations/bitbucket/client.py",
        "        if urlsplit(validate_bitbucket_api_url(url)).path != urlsplit(source_url).path:",
        "        if False:",
    ),
    Mutation(
        "compressed-content-enabled",
        "src/verboflex/integrations/bitbucket/client.py",
        '                if content_encoding not in {None, "identity"}:',
        "                if False:",
    ),
    Mutation(
        "exact-byte-boundary-rejected",
        "src/verboflex/integrations/bitbucket/client.py",
        "        if next_count > max_bytes:",
        "        if next_count >= max_bytes:",
    ),
    Mutation(
        "encoded-traversal-check-disabled",
        "src/verboflex/integrations/bitbucket/urls.py",
        "        or not _source_path_is_safe(parsed.path)",
        "        or False",
    ),
    Mutation(
        "tree-read-uses-mutable-branch",
        "src/verboflex/services/repository_discovery.py",
        "                commit_hash=resolved.commit_hash,\n"
        "                directory_path=directory_path,",
        "                commit_hash=branch,\n                directory_path=directory_path,",
    ),
)


def replace_once(path: Path, original: str, replacement: str) -> None:
    """Apply one reviewed transformation or fail before invoking pytest."""
    source = path.read_text()
    occurrence_count = source.count(original)
    if occurrence_count != 1:
        raise MutationProofError(
            f"mutation subject drifted for {path}: expected 1 occurrence, found {occurrence_count}"
        )
    if original == replacement:
        raise MutationProofError("mutation replacement must change the subject")
    path.write_text(source.replace(original, replacement, 1))


def copy_workspace(destination: Path) -> Path:
    """Copy the backend and reviewed capability manifest into an isolated workspace."""
    backend = destination / "backend"
    ignored = shutil.ignore_patterns(
        ".coverage",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "coverage.xml",
        "mutants",
    )
    shutil.copytree(BACKEND_ROOT, backend, ignore=ignored)
    coverage_target = (
        destination / ".planning" / "phases" / "02-admin-configuration" / "COVERAGE.md"
    )
    coverage_target.parent.mkdir(parents=True)
    shutil.copy2(COVERAGE_SOURCE, coverage_target)
    return backend


def run_suite(backend: Path) -> subprocess.CompletedProcess[str]:
    """Run the exact discovery mutation selection in one isolated workspace."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(backend / "src")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *TEST_SELECTION, "-x"],
        cwd=backend,
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def prove_mutations() -> None:
    """Require a green baseline and one assertion failure per reviewed mutant."""
    with tempfile.TemporaryDirectory(prefix="verboflex-discovery-mutants-") as temp_dir:
        workspace = Path(temp_dir)
        baseline = run_suite(copy_workspace(workspace / "baseline"))
        if baseline.returncode != 0:
            raise MutationProofError(
                "mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        print("baseline: PASS")

        killed = 0
        for index, mutation in enumerate(MUTATIONS, start=1):
            mutant_backend = copy_workspace(workspace / f"mutant-{index}")
            replace_once(
                mutant_backend / mutation.relative_path,
                mutation.original,
                mutation.replacement,
            )
            result = run_suite(mutant_backend)
            combined_output = result.stdout + result.stderr
            if result.returncode == 0:
                raise MutationProofError(f"surviving mutant: {mutation.label}")
            if "failed" not in combined_output.casefold():
                raise MutationProofError(
                    f"mutant did not reach an assertion failure: {mutation.label}\n"
                    + combined_output
                )
            killed += 1
            print(f"{mutation.label}: KILLED")

        if killed != len(MUTATIONS):
            raise MutationProofError("mutation count mismatch")
        print(f"mutation score: {killed}/{len(MUTATIONS)} killed")


def self_test() -> None:
    """Prove source drift reaches the checker's own failure path."""
    with tempfile.TemporaryDirectory(prefix="verboflex-discovery-mutant-control-") as temp_dir:
        control = Path(temp_dir) / "control.py"
        control.write_text("approved = True\n")
        try:
            replace_once(control, "approved = False", "approved = True")
        except MutationProofError:
            print("mutation checker negative control: PASS")
            return
    raise MutationProofError("mutation checker negative control unexpectedly passed")


def main() -> None:
    """Run the negative control or complete targeted mutation proof."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    arguments = parser.parse_args()
    if arguments.self_test:
        self_test()
    else:
        prove_mutations()


if __name__ == "__main__":
    try:
        main()
    except MutationProofError as error:
        print(f"Bitbucket discovery mutation proof error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
