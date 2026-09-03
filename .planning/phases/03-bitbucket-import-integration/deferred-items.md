# Deferred Items

## 03-07 execution discoveries

- `backend/tests/api/test_admin_products.py::test_admin_create_and_detail_return_closed_active_and_candidate_summaries` retains a pre-Phase-3 exact OpenAPI path inventory and fails because it omits the three import routes introduced by Plan 03-01. The import plan's targeted and aggregate suites pass; update the cross-feature inventory during the Phase 3 gauntlet.
- The repository-wide Ruff format gate reports eight pre-existing unformatted files outside Plan 03-07's changed-file set. All Plan 03-07 files pass Ruff check and format verification.
- Repository-wide strict mypy reports the pre-existing `rate_limited` response-literal mismatch in `backend/src/verboflex/api/v1/routes/admin_discovery.py:196`. All production files changed by Plan 03-07 pass strict mypy.
