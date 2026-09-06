#!/usr/bin/env python3
"""Strict, content-free Phase 4 evidence validation; no verdict inference."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / ".planning/phases/04-localization-import-search-and-constraints"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


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
    optional = {"phase", "created", "updated", "reviewer", "score", "scope", "checked_at"}
    if not required <= data.keys() or data.keys() - required - optional:
        raise ValueError("missing or unknown fields")
    if not isinstance(data["source_digest"], str) or not DIGEST.fullmatch(data["source_digest"]):
        raise ValueError("invalid source digest")
    field, expected = ("verdict", "SECURED") if kind == "security" else ("status", "passed")
    if data[field] != expected:
        raise ValueError("non-passing verdict")
    if kind == "evidence":
        for field in ("gauntlet_exit", "smoke_exit"):
            if type(data[field]) is not int or data[field] != 0:
                raise ValueError("nonzero or inexact delivery result")
    if kind in {"review", "security"}:
        headers = None
        tables = 0
        for line in body.splitlines():
            if not line.strip().startswith("|"):
                headers = None
                continue
            cells = [
                re.sub(r"[*`]", "", c).strip().casefold()
                for c in line.strip().strip("|").split("|")
            ]
            if "severity" in cells:
                if "resolution" not in cells:
                    raise ValueError("missing resolution column")
                headers = cells
                tables += 1
                continue
            if headers is None or all(re.fullmatch(r"[: -]+", c) for c in cells):
                continue
            if len(cells) != len(headers):
                raise ValueError("malformed finding row")
            finding = dict(zip(headers, cells, strict=True))
            severity = finding["severity"]
            if severity not in {"critical", "high", "medium", "low", "info", "none"}:
                raise ValueError("unknown severity")
            if severity in {"critical", "high"} and finding["resolution"] != "resolved":
                raise ValueError("unresolved severe finding")
        if not tables:
            raise ValueError("missing structured findings table")
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
    for name in sorted(n for n in names if n):
        path = ROOT / name
        digest.update(name.encode() + b"\0" + path.read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-code-review", type=Path)
    parser.add_argument("--check-security", type=Path)
    parser.add_argument("--check-all", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--digest", action="store_true")
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
    if args.check_code_review:
        paths.append((args.check_code_review, "review"))
    if args.check_security:
        paths.append((args.check_security, "security"))
    if args.check_all:
        from phase4_inventory import validate_manifest

        validate_manifest()
        paths = [
            (ROOT / "docs/reviews/phase-04-code-review.md", "review"),
            (PHASE / "04-REVIEW.md", "review"),
            (PHASE / "04-SECURITY.md", "security"),
            (PHASE / "04-VERIFICATION.md", "verification"),
            (ROOT / "docs/evidence/phase-04.md", "evidence"),
        ]
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
                {"status": "failed", "reason": "invalid, missing, stale or non-passing evidence"}
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
