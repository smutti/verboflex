#!/usr/bin/env python3
"""Fail-closed Phase 5 source, review, and sanitized evidence validators."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / ".planning/phases/05-review-workspace-and-comments"
MANIFEST = ROOT / "tools/phase5_source_manifest.txt"
BACKEND = ROOT / "backend"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
LAYERS = (
    "manifest-and-gate-controls",
    "migration-round-trip",
    "backend-tests-coverage",
    "backend-types-lint-format",
    "openapi-client-drift",
    "frontend-unit-accessibility-coverage",
    "frontend-types-lint-format-build",
    "phase5-mutations",
    "playwright-review-notifications",
    "built-stack-smoke",
)

REQUIREMENT_OWNERS = {
    **dict.fromkeys(("REVW-01", "REVW-02", "REVW-08"), "05-02"),
    **dict.fromkeys(("REVW-03", "REVW-04", "REVW-05", "REVW-06"), "05-03"),
    "REVW-07": "05-18",
    "COMM-01": "05-04",
    "COMM-02": "05-04",
    "COMM-03": "05-04",
    "COMM-04": "05-02",
    "COMM-05": "05-04",
    "COMM-06": "05-05",
    "NOTF-01": "05-05",
    "NOTF-02": "05-06",
    "NOTF-03": "05-06",
    "NOTF-04": "05-15",
    "NOTF-05": "05-10",
    "UI-02": "05-08",
}
DECISION_OWNERS = {
    **dict.fromkeys(("D-01", "D-02", "D-03", "D-04", "D-05"), "05-02"),
    **dict.fromkeys(("D-06", "D-07", "D-08", "D-09", "D-10"), "05-03"),
    **dict.fromkeys(("D-11", "D-12", "D-15"), "05-04"),
    **dict.fromkeys(("D-13", "D-14"), "05-05"),
    **dict.fromkeys(("D-16", "D-17", "D-21"), "05-06"),
    "D-18": "05-10",
    "D-19": "05-14",
    "D-20": "05-15",
}
EDGE_OWNERS = {
    "EDGE-REVW-01-empty": "05-02",
    "EDGE-REVW-01-unicode": "05-02",
    "EDGE-REVW-02-separate-authority": "05-02",
    "EDGE-REVW-03-versioned-draft": "05-03",
    "EDGE-REVW-04-versioned-approval": "05-03",
    "EDGE-REVW-05-optional-rejection": "05-03",
    "EDGE-REVW-06-append-only-history": "05-03",
    "EDGE-REVW-07-viewer-denial": "05-18",
    "EDGE-REVW-08-unsent-projection": "05-02",
    "EDGE-COMM-01-stable-create": "05-04",
    "EDGE-COMM-02-stable-pages": "05-04",
    "EDGE-COMM-03-versioned-author": "05-04",
    "EDGE-COMM-04-exact-count": "05-02",
    "EDGE-COMM-05-persistent-history": "05-04",
    "EDGE-COMM-06-empty-identity": "05-05",
    "EDGE-COMM-06-utf16": "05-05",
    "EDGE-NOTF-01-explicit-adjacency": "05-05",
    "EDGE-NOTF-01-empty-self": "05-05",
    "EDGE-NOTF-01-deduplicated-identities": "05-05",
    "EDGE-NOTF-02-own-only": "05-06",
    "EDGE-NOTF-02-empty-count": "05-06",
    "EDGE-NOTF-02-stable-order": "05-06",
    "EDGE-NOTF-03-own-item-origin": "05-06",
    "EDGE-NOTF-03-generic-unavailable": "05-06",
    "EDGE-NOTF-03-idempotent-order": "05-06",
    "EDGE-NOTF-04-read-after-focus": "05-15",
    "EDGE-NOTF-05-exact-nonnegative": "05-10",
    "EDGE-NOTF-05-visual-cap-only": "05-10",
    "EDGE-UI-02-eight-categories": "05-08",
}
UI_CATEGORY_OWNERS = {
    "empty": "05-08",
    "loading": "05-08",
    "error": "05-08",
    "populated": "05-08",
    "partial": "05-08",
    "overflow": "05-08",
    "zero-one-many": "05-10",
    "long-text": "05-09",
}
AUTHORITY_OWNERS = {"central-translation-group-access": "05-18"}
COUNTS = {
    "REQUIREMENT": 20,
    "DECISION": 21,
    "EDGE": 29,
    "UI_CATEGORY": 8,
    "PROHIBITION": 9,
    "AUTHORITY": 1,
}
SEVERITIES = {"low": 0, "medium": 1, "high": 2, "critical": 3}
RESOLUTIONS = {"open", "unresolved", "resolved"}
EVIDENCE_STATUSES = {"passed", "failed", "partial", "human_needed"}
HUMAN_EVIDENCE_IDS = {"H-05-01", "H-05-02"}


def _load_tool(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / f"tools/{name}.py")
    if spec is None or spec.loader is None:
        raise ValueError("closeout dependency unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_phase4_gate = _load_tool("phase4_gate")
_phase4_closeout = _load_tool("verify_phase4_closeout")
Phase4Gate = _phase4_gate.Gate
require_clean_source = _phase4_gate.require_clean_source
source_digest = _phase4_closeout.source_digest


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys in closeout evidence."""


def _unique_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise ValueError("duplicate or invalid evidence field")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping
)


def _frontmatter(document: str) -> tuple[dict[str, Any], str]:
    if not document.startswith("---\n") or "\n---\n" not in document[4:]:
        raise ValueError("missing evidence frontmatter")
    raw, body = document[4:].split("\n---\n", 1)
    try:
        data = yaml.load(raw, Loader=UniqueLoader)
    except (yaml.YAMLError, TypeError) as error:
        raise ValueError("malformed evidence frontmatter") from error
    if not isinstance(data, dict):
        raise ValueError("evidence frontmatter must be a mapping")  # noqa: TRY004
    return data, body


class Gate(Phase4Gate):
    """Phase 5 gate reuses the audited isolated-service lifecycle."""

    def browser(self) -> None:
        import urllib.request

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        stream = (self.directory / "preview.log").open("wb")
        process = subprocess.Popen(
            [
                "node",
                "node_modules/vite/bin/vite.js",
                "preview",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--strictPort",
            ],
            cwd=ROOT / "frontend",
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        stream.close()
        self.processes.append(process)
        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(
                    url + "/notifications", timeout=2
                ) as response:
                    if response.status != 200:
                        raise ValueError("built SPA returned a non-success status")
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise ValueError("built SPA readiness timeout") from None
                time.sleep(0.25)
        self.environment.update(
            PLAYWRIGHT_BASE_URL=url,
            PLAYWRIGHT_OUTPUT_DIR=str(self.directory / "playwright"),
        )
        self.command(
            "playwright-review-notifications",
            [
                "npm",
                "--prefix",
                "frontend",
                "run",
                "e2e",
                "--",
                "e2e/review-workspace.spec.ts",
                "e2e/notifications.spec.ts",
                "e2e/translations.spec.ts",
                "--workers=1",
            ],
            timeout=600,
        )


def _prohibition_owners() -> dict[str, str]:
    owners: dict[str, str] = {}
    pattern = re.compile(r'^\s+- statement: "(.*)"$', re.MULTILINE)
    for path in sorted(PHASE.glob("05-*-PLAN.md")):
        plan = path.name[:5]
        for statement in pattern.findall(path.read_text()):
            if statement in owners:
                raise ValueError("duplicate prohibition source")
            owners[statement] = plan
    return owners


def source_inventory() -> dict[str, dict[str, str]]:
    decisions = set(
        re.findall(r"\*\*(D-\d{2}):\*\*", (PHASE / "05-CONTEXT.md").read_text())
    )
    if decisions != set(DECISION_OWNERS):
        raise ValueError("decision source identity drift")
    prohibitions = _prohibition_owners()
    if len(prohibitions) != COUNTS["PROHIBITION"]:
        raise ValueError("prohibition source cardinality drift")
    inventory = {
        "REQUIREMENT": REQUIREMENT_OWNERS,
        "DECISION": DECISION_OWNERS,
        "EDGE": EDGE_OWNERS,
        "UI_CATEGORY": UI_CATEGORY_OWNERS,
        "PROHIBITION": prohibitions,
        "AUTHORITY": AUTHORITY_OWNERS,
    }
    if {kind: len(items) for kind, items in inventory.items()} != COUNTS:
        raise ValueError("source contract cardinality drift")
    return inventory


def read_manifest(path: Path = MANIFEST) -> list[dict[str, Any]]:
    try:
        return [
            json.loads(line)
            for line in path.read_text().splitlines()
            if line and not line.startswith("#")
        ]
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("invalid source manifest") from error


def _validate_python_test(path: Path, symbol: str) -> None:
    tree = ast.parse(path.read_text())
    tests = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    selected = [node for node in tests if not symbol or node.name == symbol]
    if not selected:
        raise ValueError("missing behavioral test symbol")
    if not any(
        isinstance(node, ast.Assert)
        or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "raises"
        )
        for test in selected
        for node in ast.walk(test)
    ):
        raise ValueError("non-behavioral test selector")


def _validate_test_selector(selector: object) -> None:
    if not isinstance(selector, str) or not selector:
        raise ValueError("invalid test selector")
    raw_path, separator, symbol = selector.partition("::")
    if not separator or not symbol:
        raise ValueError("test selector must name behavior")
    path = ROOT / raw_path
    if not path.is_file() or "/tests/architecture/" in f"/{raw_path}":
        raise ValueError("missing or inventory-only test evidence")
    if path.suffix == ".py":
        _validate_python_test(path, symbol)
    elif path.suffix in {".ts", ".tsx"}:
        text = path.read_text()
        if symbol not in text or "expect(" not in text:
            raise ValueError("missing behavioral browser test symbol")
    else:
        raise ValueError("unsupported test evidence")


def validate_manifest(rows: list[dict[str, Any]] | None = None) -> dict[str, int]:
    rows = read_manifest() if rows is None else rows
    expected = source_inventory()
    actual = {kind: set() for kind in COUNTS}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "kind",
            "id",
            "plan",
            "tests",
            "delivery",
        }:
            raise ValueError("invalid manifest fields")
        kind = row["kind"]
        identity = row["id"]
        if (
            kind not in actual
            or not isinstance(identity, str)
            or identity in actual[kind]
            or identity not in expected[kind]
        ):
            raise ValueError("duplicate or unknown source obligation")
        if row["plan"] != expected[kind][identity]:
            raise ValueError("source obligation owner drift")
        if not isinstance(row["tests"], list) or not row["tests"]:
            raise ValueError("missing behavioral evidence")
        if not isinstance(row["delivery"], list) or not row["delivery"]:
            raise ValueError("missing delivery evidence")
        for selector in row["tests"]:
            _validate_test_selector(selector)
        for delivery in row["delivery"]:
            if (
                not isinstance(delivery, str)
                or "/tests/" in f"/{delivery}"
                or not (ROOT / delivery).is_file()
            ):
                raise ValueError("missing delivery source")
        actual[kind].add(identity)
    if any(actual[kind] != set(expected[kind]) for kind in COUNTS):
        raise ValueError("manifest/source identity disagreement")
    return COUNTS.copy()


def _normalized_token(value: object, *, field: str, allowed: set[str]) -> str:
    if not isinstance(value, str):
        raise ValueError(f"invalid {field}")  # noqa: TRY004
    token = value.strip().lower()
    if token not in allowed:
        raise ValueError(f"unknown {field}")
    return token


def verify_review_findings(
    findings: object, *, block_on: str = "high"
) -> dict[str, int | str]:
    threshold = _normalized_token(
        block_on, field="severity threshold", allowed=set(SEVERITIES)
    )
    if not isinstance(findings, list):
        raise ValueError("malformed review findings")  # noqa: TRY004
    seen: set[str] = set()
    blocking = 0
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {
            "id",
            "severity",
            "resolution",
        }:
            raise ValueError("malformed review finding")
        identity = finding["id"]
        if not isinstance(identity, str) or not identity.strip() or identity in seen:
            raise ValueError("invalid review finding identity")
        seen.add(identity)
        severity = _normalized_token(
            finding["severity"], field="severity", allowed=set(SEVERITIES)
        )
        resolution = _normalized_token(
            finding["resolution"], field="resolution", allowed=RESOLUTIONS
        )
        if resolution != "resolved" and SEVERITIES[severity] >= SEVERITIES[threshold]:
            blocking += 1
    if blocking:
        raise ValueError("review threshold blocked")
    return {
        "status": "passed",
        "finding_count": len(findings),
        "unresolved_blocking_count": 0,
    }


def read_review_findings(path: Path) -> list[dict[str, str]]:
    try:
        lines = path.read_text().splitlines()
    except OSError as error:
        raise ValueError("review artifact unavailable") from error
    findings: list[dict[str, str]] = []
    header: dict[str, int] | None = None
    for line in lines:
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        normalized = [cell.lower() for cell in cells]
        if (
            "severity" in normalized
            and ("finding" in normalized or "id" in normalized)
            and ("resolution" in normalized or "status" in normalized)
        ):
            header = {name: index for index, name in enumerate(normalized)}
            continue
        if header is None or all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        identity_index = header.get("finding", header.get("id"))
        resolution_index = header.get("resolution", header.get("status"))
        assert identity_index is not None and resolution_index is not None
        if max(identity_index, header["severity"], resolution_index) >= len(cells):
            raise ValueError("malformed review table")
        findings.append(
            {
                "id": cells[identity_index],
                "severity": cells[header["severity"]],
                "resolution": cells[resolution_index],
            }
        )
    if header is None:
        raise ValueError("review findings table missing")
    return findings


def verify_review_artifact(
    path: Path, *, block_on: str = "high"
) -> dict[str, int | str]:
    data, _body = _frontmatter(path.read_text(encoding="utf-8"))
    if data.get("phase") != "05-review-workspace-and-comments":
        raise ValueError("wrong review phase")
    if data.get("status") != "passed":
        raise ValueError("review is not passing")
    digest = data.get("source_digest")
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise ValueError("invalid review digest")
    if digest != source_digest():
        raise ValueError("review evidence is stale")
    return verify_review_findings(read_review_findings(path), block_on=block_on)


def evidence_record(
    *,
    status: str,
    source: bytes,
    output: bytes,
    started_at: str,
    completed_at: str,
    duration_seconds: float,
) -> dict[str, str | float]:
    normalized_status = _normalized_token(
        status, field="evidence status", allowed=EVIDENCE_STATUSES
    )
    try:
        started = datetime.fromisoformat(started_at)
        completed = datetime.fromisoformat(completed_at)
    except (TypeError, ValueError) as error:
        raise ValueError("invalid evidence timing") from error
    if (
        started.tzinfo is None
        or completed.tzinfo is None
        or completed < started
        or isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or not math.isfinite(duration_seconds)
        or not 0 <= duration_seconds <= 86_400
    ):
        raise ValueError("invalid evidence timing")
    return {
        "status": normalized_status,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(float(duration_seconds), 3),
    }


def _validate_human_record(record: object, *, document_digest: str) -> dict[str, str]:
    required = {
        "id",
        "tester",
        "timestamp",
        "environment",
        "source_digest",
        "outcome",
        "observation",
    }
    if not isinstance(record, dict) or set(record) != required:
        raise ValueError("malformed human evidence")
    if any(
        not isinstance(record[field], str) or not record[field].strip()
        for field in required
    ):
        raise ValueError("incomplete human evidence")
    identity = record["id"]
    if (
        identity not in HUMAN_EVIDENCE_IDS
        or record["outcome"].strip().lower() != "passed"
    ):
        raise ValueError("invalid human evidence")
    try:
        timestamp = datetime.fromisoformat(record["timestamp"])
    except ValueError as error:
        raise ValueError("invalid human evidence timestamp") from error
    if timestamp.tzinfo is None:
        raise ValueError("invalid human evidence timestamp")
    if record["source_digest"] != document_digest:
        raise ValueError("human evidence digest disagreement")
    return {field: record[field] for field in required}


def validate_verification_document(
    document: str,
    *,
    allow_status: tuple[str, ...] = ("human_needed", "passed"),
    require_status: str | None = None,
    require_human: tuple[str, ...] = (),
) -> dict[str, Any]:
    data, _body = _frontmatter(document)
    required = {
        "phase",
        "status",
        "source_digest",
        "automated_gauntlet",
        "review_gate",
        "phase4_provider_uat",
        "human_evidence",
    }
    optional = {"verified_at", "gauntlet_evidence"}
    if not required <= set(data) or set(data) - required - optional:
        raise ValueError("missing or unknown verification fields")
    if data["phase"] != "05-review-workspace-and-comments":
        raise ValueError("wrong verification phase")
    status = _normalized_token(
        data["status"], field="verification status", allowed={"human_needed", "passed"}
    )
    if require_status is not None and status != require_status:
        raise ValueError("required verification status not present")
    if status not in set(allow_status):
        raise ValueError("verification status not allowed")
    digest = data["source_digest"]
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise ValueError("invalid verification digest")
    if data["automated_gauntlet"] != "passed" or data["review_gate"] != "passed":
        raise ValueError("automated verification evidence is not passing")
    if data["phase4_provider_uat"] != "open":
        raise ValueError("Phase 4 provider UAT must remain separately open")
    raw_records = data["human_evidence"]
    if not isinstance(raw_records, list):
        raise ValueError("malformed human evidence")  # noqa: TRY004
    records = [
        _validate_human_record(item, document_digest=digest) for item in raw_records
    ]
    identities = [item["id"] for item in records]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate human evidence")
    required_ids = set(require_human)
    if not required_ids <= HUMAN_EVIDENCE_IDS or not required_ids <= set(identities):
        raise ValueError("required human evidence is absent")
    if status == "passed" and set(identities) != HUMAN_EVIDENCE_IDS:
        raise ValueError("passed status requires complete human evidence")
    if status == "human_needed" and set(identities) == HUMAN_EVIDENCE_IDS:
        raise ValueError("human_needed cannot retain complete passing evidence")
    return {**data, "status": status, "human_evidence": records}


def _run_layers(gate: Gate) -> None:
    for layer in LAYERS:
        if layer == "manifest-and-gate-controls":
            gate.command(
                layer,
                [
                    "uv",
                    "run",
                    "pytest",
                    "tests/architecture/test_phase5_mutation_verifier.py",
                    "tests/architecture/test_phase5_closeout_gate.py",
                    "-q",
                ],
                cwd=BACKEND,
            )
            gate.command(
                "source-manifest",
                [
                    str(BACKEND / ".venv/bin/python"),
                    "tools/phase5_gate.py",
                    "verify-manifest",
                ],
            )
        elif layer == "migration-round-trip":
            gate.command(
                layer,
                [
                    "uv",
                    "run",
                    "pytest",
                    "tests/integration/test_review_workspace_schema.py",
                    "tests/integration/test_migrations.py",
                    "-q",
                    "--randomly-seed=517",
                ],
                cwd=BACKEND,
                timeout=1200,
            )
        elif layer == "backend-tests-coverage":
            coverage_path = gate.directory / "backend-coverage.xml"
            gate.command(
                layer,
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "--randomly-seed=517",
                    "--junitxml=" + str(gate.directory / "backend.xml"),
                    "--cov=verboflex",
                    "--cov-branch",
                    "--cov-report=term-missing",
                    "--cov-report=xml:" + str(coverage_path),
                    "--cov-fail-under=0",
                ],
                cwd=BACKEND,
                timeout=1800,
            )
        elif layer == "backend-types-lint-format":
            for command in (
                ["mypy", "src"],
                ["ruff", "check", "src", "tests"],
                ["ruff", "format", "--check", "src", "tests", "alembic"],
            ):
                gate.command(
                    layer
                    + "-"
                    + command[0]
                    + ("-format" if "format" in command else ""),
                    ["uv", "run", *command],
                    cwd=BACKEND,
                )
        elif layer == "openapi-client-drift":
            gate.command(
                layer,
                [
                    "uv",
                    "run",
                    "pytest",
                    "tests/api/test_openapi_contract.py",
                    "tests/api/test_translation_error_union.py",
                    "-q",
                ],
                cwd=BACKEND,
            )
            gate.command(
                layer + "-generated",
                ["npm", "--prefix", "frontend", "run", "api:check"],
            )
        elif layer == "frontend-unit-accessibility-coverage":
            coverage_directory = gate.directory / "frontend-coverage"
            gate.command(
                layer,
                [
                    "npm",
                    "--prefix",
                    "frontend",
                    "run",
                    "test:coverage",
                    "--",
                    "--coverage.reportsDirectory=" + str(coverage_directory),
                    "--coverage.reporter=text",
                    "--coverage.reporter=cobertura",
                ],
                timeout=1200,
            )
        elif layer == "frontend-types-lint-format-build":
            for command in ("typecheck", "lint", "format:check", "build"):
                gate.command(
                    layer + "-" + command,
                    ["npm", "--prefix", "frontend", "run", command],
                )
        elif layer == "phase5-mutations":
            gate.command(
                layer,
                [str(BACKEND / ".venv/bin/python"), "tools/verify_phase5_mutants.py"],
                timeout=2400,
            )
        elif layer == "playwright-review-notifications":
            gate.browser()
        elif layer == "built-stack-smoke":
            gate.command(layer, ["bash", "tools/phase5_smoke.sh"], timeout=2400)


def run_gauntlet() -> dict[str, Any]:
    require_clean_source()
    digest = source_digest()
    gate = Gate()
    try:
        gate.start_infrastructure()
        _run_layers(gate)
        if source_digest() != digest:
            raise ValueError("source changed during Phase 5 gauntlet")
    except BaseException:
        gate.cleanup()
        raise
    gate.cleanup()
    result = {
        "status": "passed",
        "source_digest": digest,
        "sections": list(LAYERS),
        "records": gate.records,
    }
    (gate.directory / "result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "source_digest": digest,
                "evidence": str(gate.directory),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run")
    manifest_parser = subparsers.add_parser("verify-manifest")
    manifest_parser.add_argument("--manifest", type=Path, default=MANIFEST)
    review_parser = subparsers.add_parser("verify-review")
    review_parser.add_argument("--artifact", type=Path, required=True)
    review_parser.add_argument("--block-on", default="high")
    phase_parser = subparsers.add_parser("verify-phase")
    phase_parser.add_argument("--artifact", type=Path, required=True)
    phase_parser.add_argument("--allow-status", action="append", default=[])
    phase_parser.add_argument("--require-status")
    phase_parser.add_argument("--require-human", default="")
    phase_parser.add_argument("--same-digest", action="store_true")
    args = parser.parse_args()
    if args.command == "run":
        run_gauntlet()
        return 0
    if args.command == "verify-manifest":
        result = validate_manifest(read_manifest(args.manifest))
    elif args.command == "verify-review":
        result = verify_review_artifact(args.artifact, block_on=args.block_on)
    else:
        allowed = tuple(args.allow_status) or ("human_needed", "passed")
        required_human = tuple(item for item in args.require_human.split(",") if item)
        result = validate_verification_document(
            args.artifact.read_text(encoding="utf-8"),
            allow_status=allowed,
            require_status=args.require_status,
            require_human=required_human,
        )
        if args.same_digest and result["source_digest"] != source_digest():
            raise ValueError("verification evidence is stale")
        result = {
            "status": result["status"],
            "source_digest": result["source_digest"],
            "human_evidence_count": len(result["human_evidence"]),
        }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError, OSError, subprocess.SubprocessError:
        reason = (
            "phase evidence failed closed"
            if len(sys.argv) > 1 and sys.argv[1] == "verify-phase"
            else "gauntlet failed closed"
            if len(sys.argv) > 1 and sys.argv[1] == "run"
            else "review evidence failed closed"
        )
        print(
            json.dumps({"status": "failed", "reason": reason}),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
