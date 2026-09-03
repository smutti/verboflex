#!/usr/bin/env python3
"""Fail-closed targeted mutation proof for the Phase 2 product API slice."""

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
    "tests/unit/test_product_names.py",
    "tests/api/test_admin_products.py",
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
        "candidate-product-lock-bypassed",
        "src/verboflex/services/products.py",
        "        select(Product).where(Product.id == product_id).with_for_update()",
        "        select(Product).where(Product.id == product_id)",
    ),
    Mutation(
        "candidate-clones-only-first-mapping",
        "src/verboflex/services/products.py",
        "    for active_mapping in active_mappings:",
        "    for active_mapping in active_mappings[:1]:",
    ),
    Mutation(
        "candidate-clones-only-first-side",
        "src/verboflex/services/products.py",
        "                    for side in active_mapping.sides",
        "                    for side in active_mapping.sides[:1]",
    ),
    Mutation(
        "candidate-clones-only-first-target",
        "src/verboflex/services/products.py",
        "                    for target in active_mapping.allowed_targets",
        "                    for target in active_mapping.allowed_targets[:1]",
    ),
    Mutation(
        "candidate-reuses-active-mapping-id",
        "src/verboflex/services/products.py",
        "    mapping_id_map = {mapping.id: uuid4() for mapping in active_mappings}",
        "    mapping_id_map = {mapping.id: mapping.id for mapping in active_mappings}",
    ),
    Mutation(
        "candidate-layout-selection-cleared",
        "src/verboflex/services/products.py",
        "                selected_layout_version=active_mapping.selected_layout_version,",
        "                selected_layout_version=None,",
    ),
    Mutation(
        "candidate-confirmation-digest-retained",
        "src/verboflex/services/products.py",
        "                confirmed_preview_digest=None,",
        "                confirmed_preview_digest=active_mapping.confirmed_preview_digest,",
    ),
    Mutation(
        "candidate-edit-identity-not-isolated",
        "src/verboflex/services/products.py",
        "        display_name=display_name,\n"
        "        name_key=name_key,\n"
        "        description=description,\n"
        "        version=active.version + 1,",
        "        display_name=active.display_name,\n        name_key=active.name_key,\n"
        "        description=description,\n        version=active.version + 1,",
    ),
    Mutation(
        "candidate-version-or-to-and",
        "src/verboflex/services/products.py",
        "if candidate.is_published or candidate.version != expected_version:",
        "if candidate.is_published and candidate.version != expected_version:",
    ),
    Mutation(
        "candidate-equality-and-to-or",
        "src/verboflex/services/products.py",
        "and revision.description == description",
        "or revision.description == description",
    ),
    Mutation(
        "collection-order-id-first",
        "src/verboflex/services/products.py",
        "statement.order_by(Product.name_key, Product.id).limit(limit + 1)",
        "statement.order_by(Product.id, Product.name_key).limit(limit + 1)",
    ),
    Mutation(
        "cursor-filter-binding-or-to-and",
        "src/verboflex/services/products.py",
        'or payload["status"] != status',
        'and payload["status"] != status',
    ),
    Mutation(
        "admin-guard-to-viewer",
        "src/verboflex/api/v1/routes/admin_products.py",
        "AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]",
        "AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.VIEWER))]",
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
    """Create one clean isolated backend without caches or the project virtualenv."""
    target = destination / "backend"
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
    shutil.copytree(BACKEND_ROOT, target, ignore=ignored)
    return target


def run_suite(backend: Path) -> subprocess.CompletedProcess[str]:
    """Run the exact plan-level product selection in the current Python environment."""
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
    """Require a green baseline and one red run for every exact reviewed mutant."""
    with tempfile.TemporaryDirectory(prefix="verboflex-product-mutants-") as temp_dir:
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
    """Prove a drifted mutation subject reaches the checker's failure path."""
    with tempfile.TemporaryDirectory(prefix="verboflex-product-mutant-control-") as temp_dir:
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
