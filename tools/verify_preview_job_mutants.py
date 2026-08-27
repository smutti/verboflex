#!/usr/bin/env python3
"""Fail-closed targeted mutation proof for durable preview-job authority."""

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
TEST_SELECTION = ("tests/integration/test_preview_jobs.py",)


class MutationProofError(RuntimeError):
    """Raised when one reviewed preview-job mutant is not proven killed."""


@dataclass(frozen=True, slots=True)
class Mutation:
    label: str
    relative_path: str
    original: str
    replacement: str


MUTATIONS = (
    Mutation(
        "result-envelope-allows-extra-fields",
        "src/verboflex/services/preview_jobs.py",
        "    if set(raw_result) != _SKELETON_RESULT_FIELDS:\n"
        '        raise ValueError("preview result rejected")',
        "    if not _SKELETON_RESULT_FIELDS.issubset(raw_result):\n"
        '        raise ValueError("preview result rejected")',
    ),
    Mutation(
        "result-envelope-accepts-wrong-digest",
        "src/verboflex/services/preview_jobs.py",
        "        or digest != identity.input_digest\n",
        "        or digest == identity.input_digest\n",
    ),
    Mutation(
        "persisted-error-vocabulary-bypassed",
        "src/verboflex/services/preview_jobs.py",
        "    if row.error_code is not None and row.error_code not in _PREVIEW_ERROR_CODES:\n"
        '        raise PreviewJobConflict("persisted preview error rejected")',
        "    if False and row.error_code is not None:\n"
        '        raise PreviewJobConflict("persisted preview error rejected")',
    ),
    Mutation(
        "started-identity-comparison-inverted",
        "src/verboflex/services/preview_jobs.py",
        "        return _identity(row) == identity\n",
        "        return _identity(row) != identity\n",
    ),
    Mutation(
        "status-currentness-inverted",
        "src/verboflex/services/preview_jobs.py",
        "            is_current=_current_failure_code(session, row, for_update=False) is None,\n",
        "            is_current=_current_failure_code(\n"
        "                session, row, for_update=False\n"
        "            )\n"
        "            is not None,\n",
    ),
    Mutation(
        "terminal-write-checks-attempt-only",
        "src/verboflex/services/preview_jobs.py",
        '        if row is None or row.state != "running" or not '
        "_matches_started_identity(row, identity):\n",
        '        if row is None or row.state != "running" or row.attempt != identity.attempt:\n',
    ),
    Mutation(
        "mapping-identity-drift-ignored",
        "src/verboflex/services/preview_jobs.py",
        "    if (\n"
        "        row.topology != mapping.topology\n"
        "        or row.detector_version != PREVIEW_DETECTOR_VERSION\n"
        "        or row.layout_identity != PREVIEW_LAYOUT_IDENTITY\n"
        "        or row.repository_sides != current_sides\n"
        "        or row.input_digest != current_digest\n"
        "    ):\n"
        '        return "stale_identity"',
        "    if False and (\n"
        "        row.topology != mapping.topology\n"
        "        or row.detector_version != PREVIEW_DETECTOR_VERSION\n"
        "        or row.layout_identity != PREVIEW_LAYOUT_IDENTITY\n"
        "        or row.repository_sides != current_sides\n"
        "        or row.input_digest != current_digest\n"
        "    ):\n"
        '        return "stale_identity"',
    ),
    Mutation(
        "create-schema-accepts-extra-fields",
        "src/verboflex/schemas/previews.py",
        "class AdminPreviewJobCreateRequest(BaseModel):\n"
        '    """Candidate compare value plus exact resolved commits, with no source bytes."""\n\n'
        '    model_config = ConfigDict(extra="forbid")',
        "class AdminPreviewJobCreateRequest(BaseModel):\n"
        '    """Candidate compare value plus exact resolved commits, with no source bytes."""\n\n'
        '    model_config = ConfigDict(extra="ignore")',
    ),
    Mutation(
        "preview-model-not-explicitly-exported",
        "src/verboflex/models/__init__.py",
        "from verboflex.models.preview_job import PreviewJob\n",
        "",
    ),
)


def replace_once(path: Path, original: str, replacement: str) -> None:
    """Apply exactly one mutation or fail closed on source drift."""
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
    """Copy the backend without caches, generated coverage, or its virtualenv."""
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
    """Run the locked preview selection against one isolated source copy."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(backend / "src")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *TEST_SELECTION, "-x"],
        cwd=backend,
        env=environment,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def prove_mutations() -> None:
    """Require a green baseline and an assertion failure for every mutant."""
    with tempfile.TemporaryDirectory(prefix="verboflex-preview-job-mutants-") as temp_dir:
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
    """Prove source drift reaches the checker's failure path."""
    with tempfile.TemporaryDirectory(prefix="verboflex-preview-job-control-") as temp_dir:
        control = Path(temp_dir) / "control.py"
        control.write_text("is_current = True\n")
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
