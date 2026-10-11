#!/usr/bin/env python3
"""Fail-closed targeted mutation proof for strict Android preview detection."""

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
TEST_SELECTION = ("tests/unit/localization/preview/test_android_xml.py",)


class MutationProofError(RuntimeError):
    """Raised when one reviewed Android preview mutant is not proven killed."""


@dataclass(frozen=True, slots=True)
class Mutation:
    label: str
    relative_path: str
    original: str
    replacement: str


MUTATIONS = (
    Mutation(
        "per-file-limit-rejects-exact-boundary",
        "src/verboflex/localization/preview/android_xml.py",
        "byte_count > SOURCE_DISCOVERY_BUDGET.max_file_bytes",
        "byte_count >= SOURCE_DISCOVERY_BUDGET.max_file_bytes",
    ),
    Mutation(
        "aggregate-limit-rejects-exact-boundary",
        "src/verboflex/localization/preview/android_xml.py",
        "total_bytes > SOURCE_DISCOVERY_BUDGET.max_total_bytes",
        "total_bytes >= SOURCE_DISCOVERY_BUDGET.max_total_bytes",
    ),
    Mutation(
        "unsupported-qualifier-is-ignored",
        "src/verboflex/localization/preview/android_xml.py",
        "    if _ANDROID_PATH.fullmatch(file.path) is None:\n"
        "        return layout_identity, None, byte_count",
        "    if _ANDROID_PATH.fullmatch(file.path) is None:\n        return None",
    ),
    Mutation(
        "duplicate-string-name-overwrites",
        "src/verboflex/localization/preview/android_xml.py",
        '        if key in values:\n            raise ValueError("unsupported Android XML")',
        '        if False:\n            raise ValueError("unsupported Android XML")',
    ),
    Mutation(
        "child-markup-is-accepted",
        "src/verboflex/localization/preview/android_xml.py",
        "        or len(child) != 0\n",
        "        or False\n",
    ),
    Mutation(
        "invalid-utf8-is-replaced",
        "src/verboflex/localization/preview/android_xml.py",
        '        text = raw.decode("utf-8", errors="strict")',
        '        text = raw.decode("utf-8", errors="replace")',
    ),
    Mutation(
        "dtd-and-entities-are-enabled",
        "src/verboflex/localization/preview/android_xml.py",
        "            forbid_dtd=True,\n            forbid_entities=True,",
        "            forbid_dtd=False,\n            forbid_entities=False,",
    ),
    Mutation(
        "language-limit-rejects-exact-boundary",
        "src/verboflex/localization/preview/core.py",
        "    _require_candidate(len(ordered_languages) <= MAX_PREVIEW_LANGUAGES)",
        "    _require_candidate(len(ordered_languages) < MAX_PREVIEW_LANGUAGES)",
    ),
    Mutation(
        "per-language-sample-cap-is-removed",
        "src/verboflex/localization/preview/core.py",
        "        for key in sorted(translations)[:MAX_SAMPLES_PER_LANGUAGE]:",
        "        for key in sorted(translations):",
    ),
    Mutation(
        "global-sample-cap-allows-one-extra",
        "src/verboflex/localization/preview/core.py",
        "            if len(samples) == MAX_TOTAL_SAMPLES:",
        "            if len(samples) > MAX_TOTAL_SAMPLES:",
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
    """Copy the backend without generated artifacts or its virtual environment."""
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
    """Run the locked Android boundary suite against one isolated source copy."""
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
    with tempfile.TemporaryDirectory(prefix="verboflex-android-preview-mutants-") as temp_dir:
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
    with tempfile.TemporaryDirectory(prefix="verboflex-android-preview-control-") as temp_dir:
        control = Path(temp_dir) / "control.py"
        control.write_text("strict = True\n")
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
