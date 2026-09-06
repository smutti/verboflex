#!/usr/bin/env python3
"""Cross-reference frozen coverage claims against plans and executable sources."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / ".planning/phases/04-localization-import-search-and-constraints"
COUNTS = {
    "PLAN": 27,
    "GOAL": 1,
    "REQ": 20,
    "DECISION": 23,
    "EDGE": 52,
    "EDGE_ASSUMPTION": 0,
    "PROHIBITION": 2,
    "UI_CATEGORY": 8,
    "UI_INSTANCE": 50,
    "UI_AXIS": 3,
}
UI = {
    "empty": (
        "options|no dataset|no matches|missing source|empty target|no rule|"
        "no parser issues|no revision history"
    ),
    "loading": (
        "options skeleton|search skeleton|cursor append|detail skeleton|save pending|remove pending"
    ),
    "error": (
        "search retry|cursor retry|detail retry|parser failure|save failure|"
        "remove failure|version conflict"
    ),
    "populated": (
        "five filters|result anatomy|selectors|provenance|explicit maximum|read-only review"
    ),
    "partial": (
        "mixed review|some over limit|atomic separate mapping|stale dataset|"
        "missing optional metadata|incomplete mandatory authority"
    ),
    "overflow": (
        "filter reflow|two-line excerpt|full detail wrap|selector containment|"
        "parser issue cap|action wrapping"
    ),
    "zero-one-many": (
        "result cardinality|cursor cardinality|structured values|"
        "parser issue remainder|history bound"
    ),
    "long-text": (
        "raw keys|multiline translations|product/repository names|paths|labels|mixed scripts"
    ),
}
AXES = {"network loss", "request-response without live updates", "reduced motion"}


def source_inventory():
    items = {kind: {} for kind in COUNTS}
    for path in sorted(PHASE.glob("04-*-PLAN.md")):
        text = path.read_text()
        front = yaml.safe_load(text.split("---", 2)[1])
        plan = f"04-{int(front['plan']):02}"
        items["PLAN"][plan] = plan
        for assumption in front.get("assumptions", []) + front["must_haves"].get("assumptions", []):
            if isinstance(assumption, dict) and assumption.get("flagged") is True:
                raise ValueError("flagged edge assumption requires executable coverage")
        for req in front.get("requirements", []):
            items["REQ"].setdefault(req, plan)
        for truth in front["must_haves"].get("truths", []):
            edge = re.match(r"(EDGE-[A-Z]+-\d+-[a-z-]+):", truth)
            if edge:
                if edge[1] in items["EDGE"]:
                    raise ValueError("duplicate source edge")
                items["EDGE"][edge[1]] = plan
        for prohibition in front["must_haves"].get("prohibitions", []):
            if (
                set(prohibition) != {"statement", "category", "status", "flagged"}
                or prohibition["status"] != "unverified"
                or prohibition["flagged"] is not True
            ):
                raise ValueError("prohibition recall drift")
            items["PROHIBITION"][prohibition["statement"]] = plan
    context = (PHASE / "04-CONTEXT.md").read_text()
    for decision in re.findall(r"\*\*(D-\d{2}):\*\*", context):
        items["DECISION"][decision] = "04"
    items["GOAL"]["canonical-import-search-constraints"] = "04"
    for category, instances in UI.items():
        items["UI_CATEGORY"][category] = "04"
        for instance in instances.split("|"):
            items["UI_INSTANCE"][category + ":" + instance] = "04"
    items["UI_AXIS"] = dict.fromkeys(AXES, "04")
    if {kind: len(values) for kind, values in items.items()} != COUNTS:
        raise ValueError("source contract cardinality drift")
    return items


def read_manifest():
    return [
        json.loads(line)
        for line in (ROOT / "tools/phase4_source_manifest.txt").read_text().splitlines()
        if line and not line.startswith("#")
    ]


def validate_manifest(rows=None):
    rows = read_manifest() if rows is None else rows
    expected = source_inventory()
    actual = {kind: set() for kind in COUNTS}
    for row in rows:
        if set(row) != {"kind", "id", "plan", "tests", "delivery"}:
            raise ValueError("invalid manifest fields")
        kind, identity = row["kind"], row["id"]
        if kind not in actual or identity in actual[kind]:
            raise ValueError("duplicate or unknown marker")
        actual[kind].add(identity)
        if row["plan"] not in expected["PLAN"]:
            raise ValueError("missing owning plan")
        if not row["tests"] or not row["delivery"]:
            raise ValueError("missing runnable evidence")
        for selector in row["tests"]:
            path, _, symbol = selector.partition("::")
            source = ROOT / path
            if not source.is_file():
                raise ValueError("missing test source")
            text = source.read_text()
            if source.suffix == ".py":
                functions = [
                    n
                    for n in ast.walk(ast.parse(text))
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name.startswith("test_")
                ]
                chosen = [n for n in functions if not symbol or n.name == symbol]
                if not chosen or not any(
                    isinstance(n, ast.Assert)
                    or isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "raises"
                    for f in chosen
                    for n in ast.walk(f)
                ):
                    raise ValueError("non-executable test selector")
            elif (
                not re.search(r"\b(?:it|test)(?:\.each)?[\s(]", text)
                or "expect(" not in text
                or symbol
                and symbol not in text
            ):
                raise ValueError("non-executable browser test")
            if "inventory covers 50" in symbol:
                raise ValueError("inventory cannot prove UI behavior")
        for path in row["delivery"]:
            if not (ROOT / path).is_file():
                raise ValueError("missing delivery source")
    if any(actual[kind] != set(expected[kind]) for kind in COUNTS):
        raise ValueError("manifest/source identity disagreement")
    return COUNTS.copy()


def validate_routes(paths):
    allowed = {
        ("/api/v1/translations/options", "get"),
        ("/api/v1/translations", "get"),
        ("/api/v1/translations/{translation_group_id}", "get"),
        ("/api/v1/translations/{translation_group_id}/constraints/{language}", "put"),
        ("/api/v1/translations/{translation_group_id}/constraints/{language}", "delete"),
    }
    actual = {
        (path, method)
        for path, item in paths.items()
        if "/translations" in path
        for method in item
        if method in {"get", "post", "put", "delete", "patch"}
    }
    if actual != allowed:
        raise ValueError("translation route scope drift")


def validate_boundaries(sources=None):
    if sources is None:
        paths = (
            list((ROOT / "backend/src/verboflex").rglob("*.py"))
            + list((ROOT / "frontend/src/features").rglob("*.ts"))
            + list((ROOT / "frontend/src/features").rglob("*.tsx"))
        )
        sources = {
            str(p.relative_to(ROOT)): p.read_text()
            for p in paths
            if not re.search(r"\.(test|spec)\.", p.name)
        }
    for path, source in sources.items():
        if path.endswith(".py"):
            tree = ast.parse(source)
            for node in ast.walk(tree):
                modules = (
                    [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else []
                )
                for module in modules:
                    if "localization.importing" in module and (
                        "/api/" in path
                        or (
                            module.rsplit(".", 1)[-1]
                            in {"android_xml", "qt_ts", "json", "ios_strings"}
                            and not path.endswith("/importing/registry.py")
                        )
                    ):
                        raise ValueError("parser boundary bypass")
                if (
                    "/api/" in path
                    and isinstance(node, ast.Name)
                    and node.id
                    in {
                        "parse_mapping",
                        "parse_canonical_mapping",
                        "process_import_job",
                        "run_import_job",
                        "activate_translation_dataset",
                    }
                ):
                    raise ValueError("repository work in HTTP")
        else:
            if re.search(
                r"dangerouslySetInnerHTML|\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(|Intl\.Segmenter|\beval\s*\(",
                source,
            ):
                raise ValueError("manual transport or client content authority")
            if re.search(r"\.setItem\s*\(", source) and not path.endswith(
                "/translationPreferences.ts"
            ):
                raise ValueError("content persistence")
            if path.endswith("/translationPreferences.ts"):
                body = re.search(r"JSON\.stringify\(\{(.*?)\}\)", source, re.S)
                if not body or set(re.findall(r"^\s*(\w+):", body[1], re.M)) != {
                    "version",
                    "productId",
                    "language",
                }:
                    raise ValueError("preference allowlist drift")
    if sources and any(p.endswith("/translation_constraints.py") for p in sources):
        route = sources.get("backend/src/verboflex/api/v1/routes/translation_constraints.py", "")
        if route and not all(
            name in route
            for name in (
                "require_roles",
                "RoleName.ADMIN",
                "RoleName.PRODUCT_MANAGER_REVIEWER",
                "ConstraintPrincipal",
            )
        ):
            raise ValueError("constraint role gate missing")


if __name__ == "__main__":
    print(json.dumps(validate_manifest(), sort_keys=True))
