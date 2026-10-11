#!/usr/bin/env python3
"""Strict, content-free Phase 4 evidence validation; no verdict inference."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / ".planning/phases/04-localization-import-search-and-constraints"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
SECURITY_IDS = {*(f"T-04-{number:02d}" for number in range(1, 78)), "T-04-SC"}


def planned_security_register():
    planned = {}
    for plan in PHASE.glob("04-*-PLAN.md"):
        for line in plan.read_text().splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not cells[0].startswith("T-04-"):
                continue
            if len(cells) != 6:
                raise ValueError("malformed planned security threat")
            identifier, severity, disposition = cells[0], cells[3], cells[4]
            if severity not in {"critical", "high", "medium", "low", "info"} or disposition not in {
                "mitigate",
                "accept",
                "transfer",
                "avoid",
            }:
                raise ValueError("invalid planned security metadata")
            metadata = (severity, disposition)
            if identifier in planned and planned[identifier] != metadata:
                raise ValueError("conflicting planned security metadata")
            planned[identifier] = metadata
    if planned.keys() != SECURITY_IDS:
        raise ValueError("planned security inventory drift")
    return planned


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise ValueError("duplicate or invalid field")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def frontmatter(document):
    if not document.startswith("---\n") or "\n---\n" not in document[4:]:
        raise ValueError("missing frontmatter")
    raw, body = document[4:].split("\n---\n", 1)
    try:
        data = yaml.load(raw, Loader=UniqueLoader)
    except (yaml.YAMLError, TypeError) as error:
        raise ValueError("malformed frontmatter") from error
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data, body


def validate_document(document, kind):
    data, body = frontmatter(document)
    required = {"source_digest", "verdict" if kind == "security" else "status"}
    if kind == "evidence":
        required |= {"gauntlet_exit", "smoke_exit"}
    optional = {
        "phase",
        "created",
        "updated",
        "reviewer",
        "score",
        "scope",
        "checked_at",
    }
    if kind == "review":
        optional |= {
            "reviewed",
            "depth",
            "files_reviewed",
            "files_reviewed_list",
            "findings",
        }
    if not required <= data.keys() or data.keys() - required - optional:
        raise ValueError("missing or unknown fields")
    if not isinstance(data["source_digest"], str) or not DIGEST.fullmatch(data["source_digest"]):
        raise ValueError("invalid source digest")
    field, expected = ("verdict", "SECURED") if kind == "security" else ("status", "passed")
    if data[field] != expected:
        raise ValueError("non-passing verdict")
    if kind == "review":
        if "reviewed" in data:
            reviewed = data["reviewed"]
            if isinstance(reviewed, str):
                try:
                    reviewed = datetime.fromisoformat(reviewed)
                except ValueError as error:
                    raise ValueError("invalid review timestamp") from error
            if not isinstance(reviewed, datetime) or reviewed.tzinfo is None:
                raise ValueError("invalid review timestamp")
        if "depth" in data and data["depth"] not in ("quick", "standard", "deep"):
            raise ValueError("invalid review depth")
        if "files_reviewed" in data and (
            type(data["files_reviewed"]) is not int or data["files_reviewed"] < 0
        ):
            raise ValueError("invalid reviewed file count")
        if "files_reviewed_list" in data:
            paths = data["files_reviewed_list"]
            if (
                not isinstance(paths, list)
                or any(not isinstance(path, str) or not path.strip() for path in paths)
                or len(set(paths)) != len(paths)
            ):
                raise ValueError("invalid reviewed file list")
            if "files_reviewed" in data and data["files_reviewed"] != len(paths):
                raise ValueError("review scope count mismatch")
        if "findings" in data:
            counts = data["findings"]
            if not isinstance(counts, dict) or counts.keys() != {
                "critical",
                "warning",
                "info",
                "total",
            }:
                raise ValueError("invalid review finding counts")
            if any(type(count) is not int or count < 0 for count in counts.values()):
                raise ValueError("invalid review finding count")
            if counts["total"] != sum(counts[key] for key in ("critical", "warning", "info")):
                raise ValueError("review finding count mismatch")
    if kind == "evidence":
        for field in ("gauntlet_exit", "smoke_exit"):
            if type(data[field]) is not int or data[field] != 0:
                raise ValueError("nonzero or inexact delivery result")
    if kind in {"review", "security"}:
        planned = planned_security_register() if kind == "security" else {}
        headers = None
        tables = 0
        seen_threats = set()
        for line in body.splitlines():
            if not line.strip().startswith("|"):
                headers = None
                continue
            raw_cells = [re.sub(r"[*`]", "", c).strip() for c in line.strip().strip("|").split("|")]
            cells = [cell.casefold() for cell in raw_cells]
            if "severity" in cells:
                if "resolution" not in cells:
                    raise ValueError("missing resolution column")
                if kind == "security" and not {
                    "id",
                    "severity",
                    "disposition",
                    "evidence",
                    "resolution",
                } <= set(cells):
                    raise ValueError("missing security threat columns")
                headers = cells
                tables += 1
                continue
            if headers is None or all(re.fullmatch(r"[: -]+", c) for c in cells):
                continue
            if len(cells) != len(headers):
                raise ValueError("malformed finding row")
            finding = dict(zip(headers, cells, strict=True))
            if kind == "security":
                identifier = raw_cells[headers.index("id")]
                if identifier not in SECURITY_IDS or identifier in seen_threats:
                    raise ValueError("unknown or duplicate security threat")
                seen_threats.add(identifier)
                disposition = {"mitigated": "mitigate", "accepted": "accept"}.get(
                    finding["disposition"], finding["disposition"]
                )
                if (finding["severity"], disposition) != planned[identifier]:
                    raise ValueError("security metadata differs from planned register")
            severity = finding["severity"]
            if severity not in {"critical", "high", "medium", "low", "info", "none"}:
                raise ValueError("unknown severity")
            if severity in {"critical", "high"} and finding["resolution"] != "resolved":
                raise ValueError("unresolved severe finding")
            if kind == "security" and severity in {"critical", "high"}:
                if finding.get("disposition") not in {"mitigate", "mitigated"}:
                    raise ValueError("severe security threat cannot be waived")
                if finding.get("evidence", "") in {"", "none", "pending", "n/a", "-"}:
                    raise ValueError("missing mitigation proof")
        if not tables:
            raise ValueError("missing structured findings table")
        if kind == "security" and seen_threats != planned.keys():
            raise ValueError("incomplete security threat inventory")
    return data


def validate_digest_agreement(documents):
    digests = {d.get("source_digest") for d in documents}
    if len(digests) != 1 or not DIGEST.fullmatch(next(iter(digests)) or ""):
        raise ValueError("source digest disagreement")


def source_digest():
    # Include delivery code, tests, build/config, all tools and lock identities.
    # Exclude review/evidence and planning metadata to avoid a self-referential digest.
    names = (
        subprocess.check_output(
            [
                "git",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
                "backend",
                "frontend",
                "tools",
                "docker-compose.yml",
                ".env.example",
                "AGENTS.md",
            ],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    digest = hashlib.sha256()
    for name in sorted({n for n in names if n}):
        path = ROOT / name
        digest.update(name.encode() + b"\0" + path.read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-code-review", action="store_true")
    parser.add_argument("--check-security", action="store_true")
    parser.add_argument("--check-all", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--digest", action="store_true")
    parser.add_argument("--manifest", type=Path, default=ROOT / "tools/phase4_source_manifest.txt")
    parser.add_argument("--evidence", type=Path, default=ROOT / "docs/evidence/phase-04.md")
    parser.add_argument(
        "--code-review",
        type=Path,
        default=ROOT / "docs/reviews/phase-04-code-review.md",
    )
    parser.add_argument(
        "--security-review",
        type=Path,
        default=ROOT / "docs/reviews/phase-04-security-review.md",
    )
    parser.add_argument("--review-ledger", type=Path, default=PHASE / "04-REVIEW.md")
    parser.add_argument("--verification", type=Path, default=PHASE / "04-VERIFICATION.md")
    args = parser.parse_args()
    if args.self_test:
        return subprocess.call(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/architecture/test_phase4_closeout_gate.py",
                "-q",
            ],
            cwd=ROOT / "backend",
        )
    if args.digest:
        print(source_digest())
        return 0
    paths = []
    if args.check_all or args.check_code_review or args.check_security:
        from phase4_inventory import validate_manifest

        rows = [
            json.loads(line)
            for line in args.manifest.read_text().splitlines()
            if line and not line.startswith("#")
        ]
        validate_manifest(rows)
        paths = [
            (args.code_review, "review"),
            (args.review_ledger, "review"),
            (args.evidence, "evidence"),
        ]
        if args.check_all or args.check_security:
            paths.append((args.security_review, "security"))
        if args.check_all:
            paths.append((args.verification, "verification"))
    if not paths:
        raise ValueError("select a validation mode")
    documents = [validate_document(path.read_text(), kind) for path, kind in paths]
    validate_digest_agreement(documents)
    if documents[0]["source_digest"] != source_digest():
        raise ValueError("evidence is stale for current source")
    print(
        json.dumps(
            {
                "status": "passed",
                "artifacts": len(paths),
                "source_digest": documents[0]["source_digest"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError, OSError:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "invalid, missing, stale or non-passing evidence",
                }
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
