"""Disposable-Postgres benchmark of the real parser/staging/activation path.

Run: backend/.venv/bin/python tools/benchmark_import_capacity.py --output /tmp/vf-import
Always creates owned containers and a fresh database. No provider requests or Celery.
"""

import argparse
import gc
import hashlib
import importlib.util
import json
import os
import resource
import sys
import time
from pathlib import Path

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def benchmark(count: int, *, refresh: bool, observations: list[dict]) -> None:
    harness = _load(
        "capacity_activation_harness",
        "backend/tests/integration/test_translation_import_activation.py",
    )
    fixtures = _load(
        "capacity_inputs",
        "backend/tests/unit/localization/importing/test_mapping_capacity.py",
    )
    from verboflex.models.translation import TranslationKey, TranslationValue
    from verboflex.services.translation_imports import stage_translation_parse

    fixture = harness.activation_session_factory.__wrapped__()
    factory = next(fixture)
    try:
        clean = harness.clean_activation_database.__wrapped__(factory)
        next(clean)
        identity, repository_id = harness._seed_running_direct_import(factory)
        for operation in ["import", "refresh"] if refresh else ["import"]:
            started = time.monotonic()
            if operation == "refresh":
                identity = harness._start_refresh_execution(factory, identity)
            inputs = fixtures.mapping_inputs(count)
            if operation == "refresh":
                # Replace 10% of keys (hard deletion + addition), modify another 10%.
                from dataclasses import replace
                from xml.etree import ElementTree as ET

                changed = []
                for source in inputs:
                    root = ET.fromstring(source.content)
                    for node in root:
                        index = int(node.attrib["name"][3:])
                        if index % 10 == 0:
                            node.set("name", f"newkey{index}")
                        elif index % 10 == 1:
                            node.text = f"Updated {index}"
                    changed.append(replace(source, content=ET.tostring(root)))
                inputs = tuple(changed)
                del changed, root
            result = fixtures.parse_canonical_mapping(inputs)
            assert not result.issues and len(result.values) == count
            parsed = time.monotonic()
            references = tuple(
                harness.replace(
                    harness._reference(
                        repository_id,
                        path=source.path,
                        commit_hash=("a" if operation == "import" else "b") * 40,
                    ),
                    position=i,
                    size_bytes=len(source.content),
                    sha256=hashlib.sha256(source.content).hexdigest(),
                )
                for i, source in enumerate(inputs)
            )
            manifest = stage_translation_parse(
                factory, identity=identity, references=references, result=result
            )
            assert manifest is not None and manifest.value_count == count
            del result, inputs
            gc.collect()
            staged = time.monotonic()
            print(
                json.dumps(
                    {
                        "event": "staged",
                        "operation": operation,
                        "values": count,
                        "seconds": staged - started,
                    }
                ),
                flush=True,
            )
            assert harness.import_jobs.finish_import_execution(
                factory,
                identity=identity,
                references=references,
                canonical_manifest_digest=manifest.digest,
            )
            finished = time.monotonic()
            with factory() as session:
                actual = session.scalar(
                    select(func.count()).select_from(TranslationValue)
                )
                assert actual == count
                if operation == "refresh":
                    assert (
                        session.scalar(
                            select(func.count())
                            .select_from(TranslationKey)
                            .where(TranslationKey.raw_key == "key0")
                        )
                        == 0
                    )
                    assert (
                        session.scalar(
                            select(func.count())
                            .select_from(TranslationKey)
                            .where(TranslationKey.raw_key.like("newkey%"))
                        )
                        == count // 10
                    )
                    assert (
                        session.scalar(
                            select(func.count())
                            .select_from(TranslationValue)
                            .where(TranslationValue.display_text.like("Updated %"))
                        )
                        == count // 10
                    )
            # macOS reports bytes; Linux reports KiB. High-water mark is cumulative.
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
                1048576 if sys.platform == "darwin" else 1024
            )
            elapsed = finished - started
            observation = {
                "operation": operation,
                "values": actual,
                "seconds": elapsed,
                "parse_seconds": parsed - started,
                "stage_seconds": staged - parsed,
                "activation_seconds": finished - staged,
                "peak_rss_mib": rss,
                "within_targets": elapsed <= 240 and rss <= 512,
            }
            observations.append(observation)
            print(json.dumps(observation), flush=True)
    finally:
        fixture.close()


def main() -> int:
    from load_translation_capacity import Lab, capture

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--values", type=int, choices=(500, 2000, 50000, 100000), default=50000
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    lab = Lab(args.output)
    report = {
        "source_commit": capture(["git", "rev-parse", "HEAD"], cwd=ROOT),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "postgres_limits": {"cpus": 4, "memory_gib": 6, "statement_timeout_ms": 15000},
        "target": "each operation <= 240 seconds, process peak RSS <= 512 MiB",
        "scope": "Android XML parser, staging and activation; no network/Celery; fresh database",
        "cleanup": False,
    }
    try:
        lab.infrastructure()
        report["operations"] = []
        benchmark(args.values, refresh=args.refresh, observations=report["operations"])
        return 0 if all(x["within_targets"] for x in report["operations"]) else 2
    except BaseException as error:
        report["error"] = type(error).__name__
        report["sqlstate"] = getattr(getattr(error, "orig", None), "sqlstate", None)
        raise
    finally:
        lab.close()
        report["cleanup"] = True
        (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    import signal

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(130))
    raise SystemExit(main())
