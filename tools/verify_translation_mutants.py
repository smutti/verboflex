#!/usr/bin/env python3
"""Deterministic, bounded semantic mutation probes with exclusive restoration."""

from __future__ import annotations

import argparse
import ast
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = str(ROOT / "backend/.venv/bin/python")


@dataclass(frozen=True)
class Mutation:
    label: str
    path: str
    original: str
    replacement: str
    command: tuple[str, ...]


def pytest(file, name):
    return (
        PYTHON,
        "-m",
        "pytest",
        "backend/tests/" + file + "::" + name,
        "-q",
        "--import-mode=importlib",
    )


PARSER = "backend/src/verboflex/localization/importing/"
SERVICES = "backend/src/verboflex/services/"
SEARCH_TEST = "integration/test_translation_search.py"
CURSOR_TEST = "test_keyset_cursor_is_bounded_tamper_proof_scope_bound_and_stale_safe"
MUTATIONS = (
    Mutation(
        "unsafe-xml",
        PARSER + "android_xml.py",
        "forbid_dtd=True,\n        forbid_entities=True,\n        forbid_external=True,",
        "forbid_dtd=False,\n        forbid_entities=False,\n        forbid_external=False,",
        pytest(
            "unit/localization/importing/test_android_xml.py",
            "test_android_hostile_fixture_inventory_fails_closed_without_network",
        ),
    ),
    Mutation(
        "input-bound",
        PARSER + "android_xml.py",
        "if len(content) > MAX_CANONICAL_FILE_BYTES:",
        "if False:",
        pytest(
            "unit/localization/importing/test_android_xml.py",
            "test_android_file_byte_limit_accepts_exact_and_rejects_one_over",
        ),
    ),
    Mutation(
        "selector-collision",
        PARSER + "core.py",
        "return hashlib.sha256(canonical_selector_bytes(selector)).hexdigest()",
        "return hashlib.sha256(b'collapsed-selector').hexdigest()",
        pytest(
            "unit/localization/importing/test_contracts.py",
            "test_selector_bytes_are_sorted_compact_typed_and_sequence_ordered",
        ),
    ),
    Mutation(
        "partial-activation",
        SERVICES + "translation_imports.py",
        "scope.active_execution_id = execution.id",
        "scope.active_execution_id = None",
        pytest(
            "integration/test_translation_import_activation.py",
            "test_activation_advances_dataset_and_baseline_to_the_same_execution",
        ),
    ),
    Mutation(
        "stale-execution",
        SERVICES + "import_jobs.py",
        'or execution.state != "running"\n        ):\n            return False\n'
        "        now = datetime.now(UTC)",
        'or execution.state != "running"\n        ):\n            return True\n'
        "        now = datetime.now(UTC)",
        pytest(
            "integration/test_translation_import_activation.py",
            "test_superseded_activation_cannot_replace_current_dataset",
        ),
    ),
    Mutation(
        "offset-pagination",
        SERVICES + "translation_search.py",
        "WHERE NOT :has_cursor OR (",
        "WHERE TRUE OR (",
        pytest(SEARCH_TEST, CURSOR_TEST),
    ),
    Mutation(
        "unbound-cursor",
        SERVICES + "translation_search.py",
        'if payload["scope"] != scope_digest:',
        "if False:",
        pytest(SEARCH_TEST, CURSOR_TEST),
    ),
    Mutation(
        "literal-wildcard",
        SERVICES + "translation_search.py",
        'return value.replace("\\\\", "\\\\\\\\").replace("%", "\\\\%").replace("_", "\\\\_")',
        "return value",
        pytest(SEARCH_TEST, "test_query_normalization_bounds_and_like_literals"),
    ),
    Mutation(
        "cross-product-scope",
        SERVICES + "translation_search.py",
        'FROM products WHERE is_active"',
        'FROM products WHERE true"',
        pytest(
            "api/test_translations.py",
            "test_options_are_server_ordered_and_exclude_inactive_datasets",
        ),
    ),
    Mutation(
        "role-bypass",
        "backend/src/verboflex/api/v1/routes/translation_constraints.py",
        "RoleName.PRODUCT_MANAGER_REVIEWER,",
        "RoleName.PRODUCT_MANAGER_REVIEWER, RoleName.VIEWER,",
        pytest(
            "api/test_translation_constraints.py",
            "test_constraint_routes_enforce_four_role_matrix_and_keep_detail_readable",
        ),
    ),
    Mutation(
        "client-length-authority",
        "frontend/src/features/translations/TranslationDetailPage.tsx",
        "Actual: {value.constraint.actual} · Maximum:",
        "Actual: {value.display_text.length} · Maximum:",
        (
            "npm",
            "--prefix",
            "frontend",
            "test",
            "--",
            "--run",
            "src/features/translations/TranslationDetailPage.test.tsx",
            "-t",
            "reads inert complete content",
        ),
    ),
    Mutation(
        "code-point-count",
        "backend/src/verboflex/localization/graphemes.py",
        "return sum(1 for _match in _GRAPHEME_PATTERN.finditer(display_text))",
        "return len(display_text)",
        pytest(
            "unit/localization/test_grapheme_count.py",
            "test_counts_uax29_extended_grapheme_clusters",
        ),
    ),
)


def execute(command, root, timeout):
    process = subprocess.Popen(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        process.communicate(timeout=timeout)
    except BaseException as error:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
        if isinstance(error, subprocess.TimeoutExpired):
            raise ValueError("probe timed out") from error
        raise
    return process.returncode


def run_mutation(mutation, root=ROOT, timeout=55):
    path = root / mutation.path
    original = path.read_bytes()
    text = original.decode()
    if text.count(mutation.original) != 1:
        raise ValueError("mutation target identity drift")
    modified = text.replace(mutation.original, mutation.replacement, 1)
    if path.suffix == ".py":
        try:
            ast.parse(modified)
        except SyntaxError as error:
            raise ValueError("mutation must remain syntactically valid") from error
    digest = hashlib.sha256(original).hexdigest()
    try:
        path.write_text(modified)
        # Avoid timestamp/size based .pyc reuse hiding a mutation or its restoration.
        if path.suffix == ".py":
            for cache in path.parent.glob("__pycache__/" + path.stem + ".*.pyc"):
                cache.unlink()
        returncode = execute(mutation.command, root, timeout)
        if returncode != 1:
            raise ValueError("surviving mutant or non-test failure")
    finally:
        path.write_bytes(original)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("source restoration failed")
        if path.suffix == ".py":
            for cache in path.parent.glob("__pycache__/" + path.stem + ".*.pyc"):
                cache.unlink()
    return {
        "mutant": mutation.label,
        "expected_test": list(mutation.command),
        "returncode": returncode,
        "restored_digest": digest,
    }


def stop(_signum, _frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--only", choices=[m.label for m in MUTATIONS])
    args = parser.parse_args()
    if args.list:
        for mutation in MUTATIONS:
            print(
                json.dumps(
                    {
                        "mutant": mutation.label,
                        "expected_test": mutation.command,
                        "timeout": 55,
                    }
                )
            )
        return 0
    if args.self_test:
        return subprocess.call(
            [
                PYTHON,
                "-m",
                "pytest",
                "tests/architecture/test_translation_mutation_verifier.py",
                "-q",
            ],
            cwd=ROOT / "backend",
        )
    lock_id = hashlib.sha256(str(ROOT).encode()).hexdigest()
    descriptor = os.open(
        Path(tempfile.gettempdir()) / ("verboflex-mutation-" + lock_id),
        os.O_CREAT | os.O_RDWR,
        0o600,
    )
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        for mutation in MUTATIONS:
            if args.only and args.only != mutation.label:
                continue
            if execute(mutation.command, ROOT, 55) != 0:
                raise ValueError("baseline does not pass: " + mutation.label)
            try:
                print(json.dumps(run_mutation(mutation), sort_keys=True), flush=True)
            except ValueError as error:
                raise ValueError(mutation.label + ": " + str(error)) from error
    finally:
        os.close(descriptor)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "failed", "reason": str(error)}), file=sys.stderr)
        raise SystemExit(1) from None
