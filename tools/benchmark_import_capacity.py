"""Disposable-Postgres benchmark of the real parser/staging/activation path.

Run from backend: uv run python ../tools/benchmark_import_capacity.py --values 50000
Never targets the user's product/database; reuses the existing isolated test harness.
"""

import argparse
import gc
import hashlib
import importlib.util
import json
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


def main() -> int:
    args = argparse.ArgumentParser()
    args.add_argument("--values", type=int, choices=(500, 2000, 50000), default=50000)
    count = args.parse_args().values
    harness = _load(
        "capacity_activation_harness",
        "backend/tests/integration/test_translation_import_activation.py",
    )
    fixtures = _load(
        "capacity_inputs", "backend/tests/unit/localization/importing/test_mapping_capacity.py"
    )
    from verboflex.services.translation_imports import stage_translation_parse
    from verboflex.models.translation import TranslationValue

    fixture = harness.activation_session_factory.__wrapped__()
    factory = next(fixture)
    try:
        clean = harness.clean_activation_database.__wrapped__(factory)
        next(clean)
        identity, repository_id = harness._seed_running_direct_import(factory)
        started = time.monotonic()
        inputs = fixtures.mapping_inputs(count)
        result = fixtures.parse_canonical_mapping(inputs)
        assert not result.issues and len(result.values) == count
        references = tuple(harness._reference(repository_id, path=source.path) for source in inputs)
        references = tuple(
            harness.replace(
                ref,
                position=i,
                size_bytes=len(inputs[i].content),
                sha256=hashlib.sha256(inputs[i].content).hexdigest(),
            )
            for i, ref in enumerate(references)
        )
        manifest = stage_translation_parse(
            factory, identity=identity, references=references, result=result
        )
        assert manifest is not None and manifest.value_count == count
        del result, inputs
        gc.collect()
        staged = time.monotonic()
        print(
            json.dumps({"event": "staged", "values": count, "seconds": staged - started}),
            flush=True,
        )
        assert harness.import_jobs.finish_import_execution(
            factory,
            identity=identity,
            references=references,
            canonical_manifest_digest=manifest.digest,
        )
        with factory() as session:
            actual = session.scalar(select(func.count()).select_from(TranslationValue))
            assert actual == count
        elapsed = time.monotonic() - started
        # macOS reports bytes; Linux reports KiB.
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
            1048576 if sys.platform == "darwin" else 1024
        )
        print(
            json.dumps(
                {
                    "values": actual,
                    "seconds": elapsed,
                    "peak_rss_mib": rss,
                    "within_targets": elapsed <= 240 and rss <= 512,
                }
            ),
            flush=True,
        )
        return 0 if elapsed <= 240 and rss <= 512 else 1
    finally:
        fixture.close()


if __name__ == "__main__":
    raise SystemExit(main())
