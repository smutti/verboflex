# Phase 04 Deferred Items

## Discovered during Plan 04-08

- [x] Default `cd backend && uv run pytest -q` collection collides on the duplicate
  `test_android_xml.py`, `test_ios_strings.py`, `test_json.py`, and `test_qt_ts.py`
  basenames under `tests/unit/localization/importing/` and
  `tests/unit/localization/preview/`. Plan 04-08 verified the full backend corpus by
  running the non-preview suite and preview suite separately; test-package collection
  structure belongs to the Phase 4 parser/quality-gate scope. Resolved by Plan19
  importlib collection: fresh full suite passes all 1,577 tests without split runs.
- [x] `cd backend && uv run mypy src` reports 12 pre-existing errors in the Phase 4
  parser modules (`android_xml.py`, `ios_strings.py`, `json.py`, `qt_ts.py`, and
  `registry.py`). The Plan 04-08 mapping model passes focused mypy verification; parser
  type cleanup belongs to the parser/quality-gate scope. Resolved by Plan19:
  fresh strict mypy passes all 103 source modules.

## Discovered during Plan 04-10

- [x] The split broad backend regression reports stale Phase 2 architecture assertions
  in `test_phase2_scope.py` and `test_phase2_gap_closure.py`: both still require
  translation model modules to be absent even though Phase 4 now deliberately owns the
  canonical translation schema. Update those historical guards in the Phase 4 quality
  gate without weakening their remaining Phase 2 boundaries. Plan19 explicitly
  admits the canonical models and retains all unrelated forbidden surfaces; full suite passes.
- [x] The broad backend worker smoke tests require a live Redis/Celery worker at
  `127.0.0.1:56379`; that external service was not running during Plan 04-10. The
  focused migration/model gates are independent of the worker and passed. Plan19
  now starts an isolated Redis and real Celery worker with bounded health and cleanup;
  all worker tests run in the passing full suite, without environmental skips.

## Discovered during Plan 04-13

- [x] The exact OpenAPI operation-set and checked-in schema-export assertions now
  detect the three planned translation read operations plus the two constraint
  mutation operations. Plan 04-15 explicitly owns freezing that final operation
  inventory and regenerating the frontend client after all dependent Phase 4 backend
  schema writers finish. Resolved in Plan 04-15: the full 20-test OpenAPI contract and
  deterministic `api:check` export/generation gate now pass.
- [x] Package-wide `ruff format --check backend` still reports only the pre-existing
  formatting drift in migrations `0011_active_revision_revalidations.py` and
  `0012_import_jobs.py`; all Plan 04-13 files pass focused format, lint, and strict
  typing checks. Resolved by Plan19 prerequisite formatting; the final source,
  test and migration format gate passes all 216 files.

## Observed during Plan 04-17

- [ ] The existing `qs` / `typed-rest-client` development dependency chain still
  reports two moderate advisories; the required high-severity audit passes and the
  newly approved TanStack packages have no reported vulnerabilities. Dependency
  remediation remains outside the result-list scope.
- [ ] Vite still reports its existing greater-than-500-kB chunk advisory; the
  production build passes. Bundling changes remain outside the result-list scope.
