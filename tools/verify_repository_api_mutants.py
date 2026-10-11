#!/usr/bin/env python3
"""Fail-closed targeted mutation proof for the repository registry API."""

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
TEST_SELECTION = (
    "tests/integration/test_repository_registry.py",
    "tests/api/test_admin_repositories.py",
)


class MutationProofError(RuntimeError):
    """Raised whenever the proof cannot establish one exact killed mutant."""


@dataclass(frozen=True, slots=True)
class Mutation:
    label: str
    relative_path: str
    original: str
    replacement: str


MUTATIONS = (
    Mutation(
        "admin-guard-to-viewer",
        "src/verboflex/api/v1/routes/admin_repositories.py",
        "AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]",
        "AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.VIEWER))]",
    ),
    Mutation(
        "duplicate-conflict-handler-disabled",
        "src/verboflex/api/v1/routes/admin_repositories.py",
        "except RepositoryConflict as error:",
        "except RepositoryNotFound as error:",
    ),
    Mutation(
        "create-schema-allows-extra-fields",
        "src/verboflex/schemas/admin_repositories.py",
        "class AdminRepositoryCreateRequest(BaseModel):\n"
        '    """Register one provider identity without credentials or product settings."""\n\n'
        '    model_config = ConfigDict(extra="forbid")',
        "class AdminRepositoryCreateRequest(BaseModel):\n"
        '    """Register one provider identity without credentials or product settings."""\n\n'
        '    model_config = ConfigDict(extra="ignore")',
    ),
    Mutation(
        "cursor-canonical-comparison-inverted",
        "src/verboflex/services/repositories.py",
        "if _encode_cursor(position) != cursor:",
        "if _encode_cursor(position) == cursor:",
    ),
    Mutation(
        "collection-order-workspace-first",
        "src/verboflex/services/repositories.py",
        "statement.order_by(\n"
        "                    sort_key,\n"
        "                    Repository.workspace,",
        "statement.order_by(\n"
        "                    Repository.workspace,\n"
        "                    sort_key,",
    ),
    Mutation(
        "existing-uuid-selection-inverted",
        "src/verboflex/services/repositories.py",
        "if repository is None:",
        "if repository is not None:",
    ),
)


def replace_once(path: Path, original: str, replacement: str) -> None:
    """Apply exactly one reviewed mutation or fail before running tests."""
    source = path.read_text()
    occurrence_count = source.count(original)
    if occurrence_count != 1:
        raise MutationProofError(
            f"mutation subject drifted for {path}: expected 1 occurrence, found {occurrence_count}"
        )
    if original == replacement:
        raise MutationProofError("mutation replacement must change the subject")
    path.write_text(source.replace(original, replacement, 1))


def copy_backend(destination: Path) -> Path:
    """Create one isolated backend without caches or the project virtualenv."""
    target = destination / "backend"
    ignored = shutil.ignore_patterns(
        ".coverage",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "coverage-02-03.xml",
        "coverage.xml",
        "mutants",
    )
    shutil.copytree(BACKEND_ROOT, target, ignore=ignored)
    return target


def run_suite(backend: Path) -> subprocess.CompletedProcess[str]:
    """Run the exact plan-level repository selection in the current environment."""
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
    """Require one green baseline and one assertion failure per reviewed mutant."""
    with tempfile.TemporaryDirectory(prefix="verboflex-repository-mutants-") as temp_dir:
        workspace = Path(temp_dir)
        baseline_backend = copy_backend(workspace / "baseline")
        baseline = run_suite(baseline_backend)
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
            if result.returncode == 0:
                raise MutationProofError(f"surviving mutant: {mutation.label}")
            if "failed" not in (result.stdout + result.stderr).lower():
                raise MutationProofError(
                    f"mutant did not reach an assertion failure: {mutation.label}\n"
                    + result.stdout
                    + result.stderr
                )
            killed += 1
            print(f"{mutation.label}: KILLED")

        if killed != len(MUTATIONS):
            raise MutationProofError("mutation count mismatch")
        print(f"mutation score: {killed}/{len(MUTATIONS)} killed")


def self_test() -> None:
    """Prove a drifted subject reaches the checker's failure path."""
    with tempfile.TemporaryDirectory(prefix="verboflex-repository-mutant-control-") as temp_dir:
        control = Path(temp_dir) / "control.py"
        control.write_text("approved = True\n")
        try:
            replace_once(control, "approved = False", "approved = True")
        except MutationProofError:
            print("mutation checker negative control: PASS")
            return
    raise MutationProofError("mutation checker negative control unexpectedly passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    arguments = parser.parse_args()
    if arguments.self_test:
        self_test()
    else:
        prove_mutations()


if __name__ == "__main__":
    main()
