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
        "confirmation-completeness-bypassed",
        "src/verboflex/services/preview_jobs.py",
        "    if _mapping_has_complete_confirmation(mapping):",
        "    if True:",
    ),
    Mutation(
        "confirmation-job-state-inverted",
        "src/verboflex/services/preview_jobs.py",
        '        and row.revision_scope == "candidate"\n'
        '        and row.state == "succeeded"',
        '        and row.revision_scope == "candidate"\n'
        '        and row.state != "succeeded"',
    ),
    Mutation(
        "latest-confirmation-job-bypassed",
        "src/verboflex/services/preview_jobs.py",
        "    return latest_attempt == row.attempt and latest_mapping_job_id == row.id",
        "    return True",
    ),
    Mutation(
        "complete-confirmation-identity-bypassed",
        "src/verboflex/services/preview_jobs.py",
        "        and _current_identity_matches(row, revision, mapping, connection)\n"
        "                and _confirmed_layout_matches(row, mapping)",
        "        and True\n                and _confirmed_layout_matches(row, mapping)",
    ),
    Mutation(
        "confirmed-digest-bypassed",
        "src/verboflex/services/preview_jobs.py",
        '    if result["digest"] != mapping.confirmed_preview_digest:\n        return False',
        '    if False and result["digest"] != mapping.confirmed_preview_digest:\n'
        "        return False",
    ),
    Mutation(
        "selected-layout-bypassed",
        "src/verboflex/services/preview_jobs.py",
        '    return len(matches) == 1 and matches[0]["repository_side"] == expected_side',
        "    return True",
    ),
    Mutation(
        "candidate-identity-check-inverted",
        "src/verboflex/services/publication.py",
        "            if product.candidate_revision_id != candidate_revision_id:\n"
        '                raise PublicationConflict("revision conflict")',
        "            if product.candidate_revision_id == candidate_revision_id:\n"
        '                raise PublicationConflict("revision conflict")',
    ),
    Mutation(
        "candidate-version-check-inverted",
        "src/verboflex/services/publication.py",
        "                or candidate.version != expected_candidate_version",
        "                or candidate.version == expected_candidate_version",
    ),
    Mutation(
        "publication-product-lock-bypassed",
        "src/verboflex/services/publication.py",
        "        select(Product).where(Product.id == product_id).with_for_update()",
        "        select(Product).where(Product.id == product_id)",
    ),
    Mutation(
        "candidate-ownership-check-inverted",
        "src/verboflex/services/publication.py",
        "                candidate.product_id != product.id",
        "                candidate.product_id == product.id",
    ),
    Mutation(
        "canonical-candidate-identity-bypassed",
        "src/verboflex/services/publication.py",
        "    if canonical_identity != (candidate.display_name, candidate.name_key):",
        "    if False and canonical_identity != (candidate.display_name, candidate.name_key):",
    ),
    Mutation(
        "publish-name-conflict-misclassified",
        "src/verboflex/services/publication.py",
        "    if conflicting_product_id is not None:\n"
        '        raise PublicationConflict("identity conflict")',
        "    if conflicting_product_id is not None:\n"
        '        raise PublicationConflict("revision conflict")',
    ),
    Mutation(
        "candidate-publication-metadata-skipped",
        "src/verboflex/services/publication.py",
        "            candidate.is_published = True",
        "            candidate.is_published = candidate.is_published",
    ),
    Mutation(
        "candidate-display-name-promotion-skipped",
        "src/verboflex/services/publication.py",
        "    product.display_name = candidate.display_name",
        "    product.display_name = product.display_name",
    ),
    Mutation(
        "candidate-name-key-promotion-skipped",
        "src/verboflex/services/publication.py",
        "    product.name_key = candidate.name_key",
        "    product.name_key = product.name_key",
    ),
    Mutation(
        "publication-active-pointer-promotion-skipped",
        "src/verboflex/services/publication.py",
        "            product.active_revision_id = candidate.id",
        "            product.active_revision_id = product.active_revision_id",
    ),
    Mutation(
        "publication-candidate-clear-skipped",
        "src/verboflex/services/publication.py",
        "            product.candidate_revision_id = None",
        "            product.candidate_revision_id = candidate.id",
    ),
    Mutation(
        "publication-activation-skipped",
        "src/verboflex/services/publication.py",
        "            product.is_active = True\n            session.flush()",
        "            product.is_active = product.is_active\n            session.flush()",
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
