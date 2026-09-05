# Phase 04 Deferred Items

## Discovered during Plan 04-08

- [ ] Default `cd backend && uv run pytest -q` collection collides on the duplicate
  `test_android_xml.py`, `test_ios_strings.py`, `test_json.py`, and `test_qt_ts.py`
  basenames under `tests/unit/localization/importing/` and
  `tests/unit/localization/preview/`. Plan 04-08 verified the full backend corpus by
  running the non-preview suite and preview suite separately; test-package collection
  structure belongs to the Phase 4 parser/quality-gate scope.
- [ ] `cd backend && uv run mypy src` reports 12 pre-existing errors in the Phase 4
  parser modules (`android_xml.py`, `ios_strings.py`, `json.py`, `qt_ts.py`, and
  `registry.py`). The Plan 04-08 mapping model passes focused mypy verification; parser
  type cleanup belongs to the parser/quality-gate scope.
