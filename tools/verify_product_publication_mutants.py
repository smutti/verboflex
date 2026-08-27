#!/usr/bin/env python3
"""Fail-closed targeted mutation proof for product publication lifecycle."""

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
    "tests/integration/test_product_publication.py",
    "tests/api/test_admin_products.py",
)


class MutationProofError(RuntimeError):
    """Raised when one reviewed publication mutant is not proven killed."""


@dataclass(frozen=True, slots=True)
class Mutation:
    label: str
    relative_path: str
    original: str
    replacement: str


MUTATIONS = (
    Mutation(
        "preview-default-fails-open",
        "src/verboflex/services/publication.py",
        '    """Block publication until Plan 14 supplies current digest confirmation."""\n'
        "    return False",
        '    """Block publication until Plan 14 supplies current digest confirmation."""\n'
        "    return True",
    ),
    Mutation(
        "candidate-identity-check-inverted",
        "src/verboflex/services/publication.py",
        "        if product.candidate_revision_id != candidate_revision_id:\n"
        '            raise PublicationConflict("revision conflict")',
        "        if product.candidate_revision_id == candidate_revision_id:\n"
        '            raise PublicationConflict("revision conflict")',
    ),
    Mutation(
        "candidate-version-check-inverted",
        "src/verboflex/services/publication.py",
        "        if candidate.is_published or candidate.version != expected_candidate_version:\n"
        '            raise PublicationConflict("revision conflict")',
        "        if candidate.is_published or candidate.version == expected_candidate_version:\n"
        '            raise PublicationConflict("revision conflict")',
    ),
    Mutation(
        "eligibility-blockers-bypassed",
        "src/verboflex/services/publication.py",
        "    if blockers:\n        raise PublicationBlocked(blockers)",
        "    if not blockers:\n        raise PublicationBlocked(blockers)",
    ),
    Mutation(
        "deactivation-keeps-product-active",
        "src/verboflex/services/publication.py",
        "        product.is_active = False\n        session.flush()",
        "        product.is_active = True\n        session.flush()",
    ),
    Mutation(
        "reactivation-skips-eligibility",
        "src/verboflex/services/publication.py",
        "        _require_eligible(\n"
        "            session,\n"
        "            revision=active,\n"
        "            confirmation_predicate=confirmation_predicate,\n"
        "        )\n"
        "        product.is_active = True",
        "        product.is_active = True",
    ),
    Mutation(
        "admin-guard-replaced-by-viewer",
        "src/verboflex/api/v1/routes/admin_products.py",
        "AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]",
        "AdminPrincipal = Annotated[Principal, Depends(require_roles(RoleName.VIEWER))]",
    ),
    Mutation(
        "publish-schema-accepts-extra-fields",
        "src/verboflex/schemas/admin_products.py",
        "class AdminProductPublishRequest(BaseModel):\n"
        '    """Publish one exact candidate under optimistic version authority."""\n\n'
        '    model_config = ConfigDict(extra="forbid")',
        "class AdminProductPublishRequest(BaseModel):\n"
        '    """Publish one exact candidate under optimistic version authority."""\n\n'
        '    model_config = ConfigDict(extra="ignore")',
    ),
    Mutation(
        "blocked-publication-loses-stable-detail",
        "src/verboflex/api/v1/routes/admin_products.py",
        '                "detail": "Product publication blocked",',
        '                "detail": "Product lifecycle conflict",',
    ),
    Mutation(
        "preview-blocker-misclassified",
        "src/verboflex/services/publication.py",
        "            found.add(PublicationBlocker.PREVIEW_CONFIRMATION_REQUIRED)",
        "            found.add(PublicationBlocker.LAYOUT_REQUIRED)",
    ),
)


def replace_once(path: Path, original: str, replacement: str) -> None:
    """Apply one exact mutation or fail closed on source drift."""
    source = path.read_text()
    count = source.count(original)
    if count != 1:
        raise MutationProofError(
            f"mutation subject drifted for {path}: expected 1 occurrence, found {count}"
        )
    if original == replacement:
        raise MutationProofError("mutation replacement must change the subject")
    path.write_text(source.replace(original, replacement, 1))


def copy_backend(destination: Path) -> Path:
    """Copy the backend without caches, coverage output, or its virtualenv."""
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
    """Run the locked publication selection against one isolated source copy."""
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
    """Require a green baseline and an assertion failure for every mutant."""
    with tempfile.TemporaryDirectory(prefix="verboflex-publication-mutants-") as temp_dir:
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
            if "failed" not in combined.casefold():
                raise MutationProofError(
                    f"mutant did not reach an assertion failure: {mutation.label}\n{combined}"
                )
            killed += 1
            print(f"{mutation.label}: KILLED")

        if killed != len(MUTATIONS):
            raise MutationProofError("mutation count mismatch")
        print(f"mutation score: {killed}/{len(MUTATIONS)} killed")


def self_test() -> None:
    """Prove source drift reaches the checker's failure path."""
    with tempfile.TemporaryDirectory(prefix="verboflex-publication-control-") as temp_dir:
        control = Path(temp_dir) / "control.py"
        control.write_text("approved = True\n")
        try:
            replace_once(control, "missing = True", "missing = False")
        except MutationProofError:
            print("mutation checker negative control: PASS")
            return
    raise MutationProofError("mutation checker negative control unexpectedly passed")


def main() -> int:
    """Run a negative control or the complete mutation proof."""
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
