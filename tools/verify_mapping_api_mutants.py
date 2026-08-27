#!/usr/bin/env python3
"""Fail-closed targeted mutation proof for candidate mapping administration."""

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
    "tests/unit/services/test_mappings.py",
    "tests/api/test_admin_mappings.py",
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
        "admin-guard-to-product-manager-reviewer",
        "src/verboflex/api/v1/routes/admin_mappings.py",
        "AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]",
        "AdminPrincipal = Annotated[Principal, Depends(\n"
        "    require_roles(RoleName.PRODUCT_MANAGER_REVIEWER)\n"
        ")]",
    ),
    Mutation(
        "write-schema-allows-manual-controls",
        "src/verboflex/schemas/admin_mappings.py",
        "class AdminDirectMappingWriteRequest(BaseModel):\n"
        '    """Create or replace one direct mapping under candidate-version authority."""\n\n'
        '    model_config = ConfigDict(extra="forbid")',
        "class AdminDirectMappingWriteRequest(BaseModel):\n"
        '    """Create or replace one direct mapping under candidate-version authority."""\n\n'
        '    model_config = ConfigDict(extra="ignore")',
    ),
    Mutation(
        "cursor-canonical-comparison-inverted",
        "src/verboflex/services/mappings.py",
        "if _encode_cursor(position) != cursor:",
        "if _encode_cursor(position) == cursor:",
    ),
    Mutation(
        "separate-topology-rank-precedes-direct",
        "src/verboflex/services/mappings.py",
        "        else_=1,",
        "        else_=-1,",
    ),
    Mutation(
        "primary-branch-order-descending",
        "src/verboflex/services/mappings.py",
        "                    primary_side.repository_id,\n"
        "                    primary_branch,\n"
        "                    translations_side.repository_id.asc().nulls_last(),",
        "                    primary_side.repository_id,\n"
        "                    primary_branch.desc(),\n"
        "                    translations_side.repository_id.asc().nulls_last(),",
    ),
    Mutation(
        "pagination-lookahead-removed",
        "src/verboflex/services/mappings.py",
        ").limit(limit + 1)",
        ").limit(limit)",
    ),
    Mutation(
        "cursor-candidate-binding-inverted",
        "src/verboflex/services/mappings.py",
        "position is not None and position.revision_id != candidate.id",
        "position is not None and position.revision_id == candidate.id",
    ),
    Mutation(
        "normalized-target-noop-inverted",
        "src/verboflex/services/mappings.py",
        "and current.allowed_target_branches == targets",
        "and current.allowed_target_branches != targets",
    ),
    Mutation(
        "target-conflict-projected-to-wrong-field",
        "src/verboflex/api/v1/routes/admin_mappings.py",
        'return _conflict("Target branch unavailable", "allowed_target_branches")',
        'return _conflict("Target branch unavailable", "source_branch")',
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
        "coverage*.xml",
        "mutants",
    )
    shutil.copytree(BACKEND_ROOT, target, ignore=ignored)
    return target


def run_suite(backend: Path) -> subprocess.CompletedProcess[str]:
    """Run the exact mapping selection in the current locked environment."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(backend / "src")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *TEST_SELECTION, "-x"],
        cwd=backend,
        env=environment,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )


def prove_mutations() -> None:
    """Require one green baseline and one assertion failure per reviewed mutant."""
    with tempfile.TemporaryDirectory(prefix="verboflex-mapping-mutants-") as temp_dir:
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
    with tempfile.TemporaryDirectory(prefix="verboflex-mapping-mutant-control-") as temp_dir:
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
