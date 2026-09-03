#!/usr/bin/env python3
"""Fail-closed targeted mutation proof for strict iOS preview detection."""

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
    "tests/unit/localization/preview/test_ios_strings.py",
    "tests/integration/test_preview_jobs.py::test_all_four_formats_return_separate_exact_layout_candidates",
)


class MutationProofError(RuntimeError):
    """Raised when one reviewed iOS preview mutant is not proven killed."""


@dataclass(frozen=True, slots=True)
class Mutation:
    label: str
    relative_path: str
    original: str
    replacement: str


MUTATIONS = (
    Mutation(
        "utf32-bom-is-treated-as-utf16",
        "src/verboflex/localization/preview/ios_strings.py",
        "    if content.startswith(_UTF32_BOMS):\n"
        '        raise ValueError("unsupported iOS strings encoding")',
        '    if content.startswith(_UTF32_BOMS):\n        return content.decode("utf-32")',
    ),
    Mutation(
        "invalid-utf8-is-replaced",
        "src/verboflex/localization/preview/ios_strings.py",
        '        text = raw.decode(encoding, errors="strict")',
        '        text = raw.decode(encoding, errors="replace")',
    ),
    Mutation(
        "bomless-utf16-is-accepted",
        "src/verboflex/localization/preview/ios_strings.py",
        '        text = raw.decode(encoding, errors="strict")',
        "        text = (\n"
        '            raw.decode("utf-16-le")\n'
        '            if encoding == "utf-8" and b"\\x00" in raw\n'
        '            else raw.decode(encoding, errors="strict")\n'
        "        )",
    ),
    Mutation(
        "duplicate-decoded-key-overwrites",
        "src/verboflex/localization/preview/ios_strings.py",
        "            if not key or key in keys:",
        "            if not key:",
    ),
    Mutation(
        "unknown-escape-is-accepted",
        "src/verboflex/localization/preview/ios_strings.py",
        '    "t": "\\t",\n}',
        '    "t": "\\t",\n    "q": "q",\n}',
    ),
    Mutation(
        "semicolon-is-not-required",
        "src/verboflex/localization/preview/ios_strings.py",
        '            self._expect(";")',
        "            self._position += 0",
    ),
    Mutation(
        "empty-document-is-accepted",
        "src/verboflex/localization/preview/ios_strings.py",
        "                if not entries:\n"
        '                    raise ValueError("empty iOS strings document")',
        "                if not entries:\n"
        "                    empty_span = SourceSpan(self._position, self._position)\n"
        "                    return (\n"
        "                        IosStringsEntry(\n"
        '                            key="placeholder", value="",\n'
        "                            key_span=empty_span, value_span=empty_span,\n"
        "                            entry_span=empty_span,\n"
        "                        ),\n"
        "                    )",
    ),
    Mutation(
        "isolated-high-surrogate-is-accepted",
        "src/verboflex/localization/preview/ios_strings.py",
        '            raise ValueError("isolated iOS strings high surrogate")',
        "            return chr(code_unit)",
    ),
    Mutation(
        "multiple-lproj-locales-are-guessed",
        "src/verboflex/localization/preview/ios_strings.py",
        "    if len(locale_components) != 1:",
        "    if len(locale_components) < 1:",
    ),
    Mutation(
        "invalid-peer-file-does-not-block-layout",
        "src/verboflex/localization/preview/ios_strings.py",
        "        if layout_identity in invalid_layouts:\n            continue",
        "        if False:\n            continue",
    ),
    Mutation(
        "ios-detector-is-omitted-from-registry",
        "src/verboflex/localization/preview/registry.py",
        "        *detect_ios_strings_layouts("
        "bounded_files, repository_side=repository_side).candidates,\n",
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
    """Run the exact iOS and durable four-format contracts in isolation."""
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
    """Require one green baseline and an assertion failure for every mutant."""
    with tempfile.TemporaryDirectory(prefix="verboflex-ios-preview-mutants-") as temp_dir:
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
    with tempfile.TemporaryDirectory(prefix="verboflex-ios-preview-control-") as temp_dir:
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
