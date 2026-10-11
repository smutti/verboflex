"""Same-data baseline/JIT-only/final workspace benchmark in an owned disposable DB.

Run from backend: uv run python ../tools/benchmark_translation_workspace.py --output PATH
Requires VERBOFLEX_TEST_POSTGRES_ADMIN_URL; never falls back to application configuration.
Optional --restore-dump PATH --postgres-container NAME restores an archive into the
generated database using that container's pg_restore, without printing private contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import sys
import time
from pathlib import Path

from sqlalchemy import event, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from tests.integration.test_translation_workspace_performance import (  # noqa: E402
    baseline_module,
    current,
    owned_database,
    plan_nodes,
    read_page,
    seed_historical,
    semantic,
)


def inventory(factory):
    result = {}
    with factory() as session:
        for table in (
            "products",
            "localization_scopes",
            "translation_keys",
            "translation_values",
            "translation_value_revisions",
            "translation_value_locators",
            "translation_proposals",
            "translation_proposal_values",
        ):
            result[table] = dict(
                session.execute(
                    text(
                        "SELECT count(*) AS count, "
                        "md5(coalesce(string_agg(md5(to_jsonb(row)::text), '' "
                        f"ORDER BY md5(to_jsonb(row)::text)), '')) AS digest FROM {table} AS row"
                    )
                )
                .mappings()
                .one()
            )
    return result


def sanitized_plan(plan):
    """No SQL expressions, application text, IDs or bound parameters in evidence."""
    allowed = {
        "Node Type",
        "Relation Name",
        "Index Name",
        "Subplan Name",
        "CTE Name",
        "Actual Rows",
        "Actual Loops",
        "Actual Total Time",
        "Plan Rows",
        "Rows Removed by Filter",
        "Rows Removed by Join Filter",
        "Shared Hit Blocks",
        "Shared Read Blocks",
        "Temp Read Blocks",
        "Temp Written Blocks",
    }
    return {
        "execution_ms": plan["Execution Time"],
        "planning_ms": plan["Planning Time"],
        "jit_ms": plan.get("JIT", {}).get("Timing", {}).get("Total", 0),
        "nodes": [
            {key: value for key, value in node.items() if key in allowed}
            for node in plan_nodes(plan["Plan"])
        ],
    }


def observe_run(factory, module, filters, *, jit_off=False, explain=False):
    engine = factory.kw["bind"]
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("WITH current AS"):
            if jit_off:
                connection.exec_driver_sql("SET LOCAL jit = off")
            statements.append((statement, parameters))

    event.listen(engine, "before_cursor_execute", observe)
    try:
        started = time.perf_counter()
        page = read_page(factory, module, **filters)
        elapsed = (time.perf_counter() - started) * 1000
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    plans = []
    if explain:
        with engine.connect() as connection:
            if jit_off or module is current:
                connection.exec_driver_sql("SET LOCAL jit = off")
            for statement, parameters in statements:
                plan = connection.exec_driver_sql(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters
                ).scalar_one()[0]
                plans.append(sanitized_plan(plan))
    return page, elapsed, plans


def benchmark(factory, baseline, *, measurements=7):
    with factory() as session:
        product = session.scalar(
            text(
                "SELECT id FROM products WHERE is_active AND deleted_at IS NULL ORDER BY id LIMIT 1"
            )
        )
    if product is None:
        raise RuntimeError("fixture requires an active product")
    first = read_page(factory, baseline, product_id=product)
    if not first.next_cursor:
        raise RuntimeError("fixture requires more than 50 current keys")
    language = first.visible_languages[-1]
    cases = {
        "global_first": {},
        "product_first": {"product_id": product},
        "product_continuation": {"product_id": product},
        "combined_filter": {
            "product_id": product,
            "q": first.items[-1].raw_key,
            "state": "draft",
            "language": language,
            "violation": "no_max",
        },
    }
    variants = {
        "baseline": (baseline, False),
        "jit_only": (baseline, True),
        "final": (current, False),
    }
    result = {}
    for case, filters in cases.items():
        variant_filters = {}
        expected = None
        samples = {name: [] for name in variants}
        plans = {}
        for name, (module, jit_off) in variants.items():
            selected = dict(filters)
            if case == "product_continuation":
                page, _, _ = observe_run(factory, module, selected, jit_off=jit_off)
                selected["cursor"] = page.next_cursor
            variant_filters[name] = selected
            page, _, plans[name] = observe_run(
                factory, module, selected, jit_off=jit_off, explain=True
            )
            response = semantic(page)
            if expected is None:
                expected = response
            elif response != expected:
                raise AssertionError(f"semantic mismatch for {case}/{name}")
        # Alternate order to reduce cache/thermal/time-order bias; each variant gets 1 warmup above.
        for iteration in range(measurements):
            names = list(variants)
            if iteration % 2:
                names.reverse()
            for name in names:
                module, jit_off = variants[name]
                page, elapsed, _ = observe_run(
                    factory, module, variant_filters[name], jit_off=jit_off
                )
                if semantic(page) != expected:
                    raise AssertionError("fixture changed while measuring")
                samples[name].append(elapsed)
        result[case] = {
            name: {
                "median_ms": statistics.median(samples[name]),
                "p95_ms": sorted(samples[name])[math.ceil(0.95 * measurements) - 1],
                "samples_ms": samples[name],
                "plans": plans[name],
            }
            for name in variants
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="9adf24c")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--small-smoke", action="store_true")
    parser.add_argument("--restore-dump", type=Path)
    parser.add_argument("--postgres-container")
    args = parser.parse_args()
    baseline, baseline_sha = baseline_module(args.baseline_ref)
    with owned_database(
        dump=args.restore_dump, postgres_container=args.postgres_container
    ) as factory:
        started = time.perf_counter()
        if args.restore_dump is None:
            seed_historical(factory, 1000 if args.small_smoke else 100_000)
        else:
            with factory.begin() as session:
                session.execute(text("ANALYZE"))
        setup_seconds = time.perf_counter() - started
        before = inventory(factory)
        results = benchmark(factory, baseline)
        after = inventory(factory)
        if before != after:
            raise AssertionError("benchmark mutated dataset")
        with factory() as session:
            version = session.scalar(text("SHOW server_version"))
            schema = session.scalar(text("SELECT version_num FROM alembic_version"))
        report = {
            "baseline_ref": args.baseline_ref,
            "baseline_source_sha256": baseline_sha,
            "final_source_sha256": hashlib.sha256(Path(current.__file__).read_bytes()).hexdigest(),
            "postgresql_version": version,
            "schema_head": schema,
            "environment": {
                "platform": platform.system(),
                "machine": platform.machine(),
                "logical_cpus": os.cpu_count(),
                "python": platform.python_version(),
            },
            "fixture": "restored" if args.restore_dump else "synthetic",
            "small_smoke": args.small_smoke,
            "before": before,
            "after": after,
            "fixture_seed_or_analyze_seconds": setup_seconds,
            "write_overhead": "No schema, trigger or import-write changes; zero added writes",
            "metadata_cache": "none; exact existing authority recomputed in current snapshot",
            "display_projection": "unchanged; current-scope candidates before LIMIT",
            "warmups_per_case_variant": 1,
            "measurements_per_case_variant": 7,
            "semantic_equivalence": True,
            "cases": results,
            "limitations": "Local service timings; do not explain Docker/static/HTTP stalls",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "semantic_equivalence": True,
                    "cases": {
                        case: {
                            name: {metric: values[metric] for metric in ("median_ms", "p95_ms")}
                            for name, values in variants.items()
                        }
                        for case, variants in results.items()
                    },
                }
            )
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Driver tracebacks can include DSNs or bound search text from restored data.
        print(
            json.dumps(
                {
                    "error": type(error).__name__,
                    "message": "Benchmark failed; private database details withheld",
                }
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
