---
phase: 03
slug: bitbucket-import-integration
status: validated
nyquist_compliant: false
wave_0_complete: true
gaps_found: 6
gaps_resolved: 0
manual_only: 6
created: 2026-09-03
---

# Phase 03 — Validation Strategy

> Reconstructed Nyquist contract for the completed Phase 3 implementation. The audit added six strict regression tests; all six currently expose implementation or configuration defects and remain RED.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Frameworks** | pytest 9.1.1, Vitest 4.1.11, Playwright 1.62.1, custom Bash gauntlet |
| **Config files** | `backend/pyproject.toml`, `frontend/vite.config.ts`, `frontend/playwright.config.ts` |
| **Quick run command** | `cd backend && uv run pytest tests/integration/test_bitbucket_oauth.py tests/architecture/test_phase3_gauntlet.py -x`; `cd frontend && npm test -- --run src/features/admin/imports/PublishedMappingImports.test.tsx src/features/admin/imports/RewrittenBaselineDialog.test.tsx` |
| **Full suite command** | `bash tools/phase3_gauntlet.sh` |
| **Estimated runtime** | Focused unit/integration feedback under 30 seconds; full 14-layer gauntlet 417 seconds on the audit host |

---

## Sampling Rate

- **After every task commit:** Run the focused command in that task's PLAN row.
- **After every plan wave:** Run the aggregate backend or frontend suite for the affected boundary.
- **Before `$gsd-verify-work`:** Run `bash tools/phase3_gauntlet.sh`; all 14 layers must pass on one unchanged source digest.
- **Max targeted feedback latency:** 30 seconds for unit/component/integration checks; browser and deployment checks are explicit closeout gates.

---

## Requirement Coverage

| Requirement | Coverage before audit | Audit result |
|-------------|-----------------------|--------------|
| BITB-02 | OAuth capability, five-operation API, generated client, UI, provider boundary, smoke and exact capability matrix | PARTIAL — WR-01, WR-02, WR-04 and WR-10 regressions are RED |
| BITB-05 | Commit/file provenance, ancestry, reconciliation, concurrency and retained-baseline behavior | PARTIAL — WR-02, WR-03, WR-04 and WR-09 regressions are RED |
| BITB-06 | Closed provider failures, diagnostics, retry, responsive UI and operational recovery | PARTIAL — WR-01, WR-02, WR-03, WR-04, WR-09 and WR-10 regressions are RED |

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | BITB-02/05/06 | T-03-01–04, SC | Admin-only UUID import, immutable metadata, GET-only provider flow | integration + component | `cd backend && uv run pytest tests/integration/test_import_jobs.py -x -k "direct_import_tracer or concurrent_start" && cd ../frontend && npm run api:check && npm test -- --run src/features/admin/mappings/ProductMappingsPage.test.tsx` | ✅ | ✅ green |
| 03-02-01 | 02 | 2 | BITB-02/05/06 | T-03-05–07, SC | Reversible schema and immutable execution provenance | migration + integration | `cd backend && uv run pytest tests/integration/test_migrations.py tests/integration/test_import_jobs.py -x -k "import_schema or immutable_source_reference"` | ✅ | ✅ green |
| 03-02-02 | 02 | 2 | BITB-02/05/06 | T-03-05–07, SC | Authorization, ownership, empty and dispatch failures close safely | integration + contract | `cd backend && uv run pytest tests/integration/test_import_jobs.py tests/api/test_openapi_contract.py -x -k "import and (authorization or ownership or empty or enqueue or public_contract)"` | ✅ | ✅ green |
| 03-03-01 | 03 | 2 | BITB-02/06 | T-03-08–10, SC | Exact OAuth capability and bounded access-token lifetime | integration | `cd backend && uv run pytest tests/integration/test_bitbucket_oauth.py -x` | ✅ | ❌ red — WR-01 |
| 03-03-02 | 03 | 2 | BITB-02/06 | T-03-08–10, SC | Closed capability readiness without secret/provider leakage | API | `cd backend && uv run pytest tests/api/test_admin_bitbucket.py -x -k "capability or reauthorization or forbidden"` | ✅ | ✅ green |
| 03-04-01 | 04 | 3 | BITB-02/06 | T-03-11–13, SC | Generated capability transport remains exact and closed | contract | `cd frontend && npm run api:generate && npm test -- --run src/api/admin-client-contract.test.ts && npm run api:check` | ✅ | ✅ green |
| 03-04-02 | 04 | 3 | BITB-02/06 | T-03-11–13, SC | Accessible reauthorization UI follows server authority | component | `cd frontend && npm test -- --run src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx` | ✅ | ✅ green |
| 03-05-01 | 05 | 3 | BITB-02/06 | T-03-14–17, SC | Provider failures stop after one bounded request | integration | `cd backend && uv run pytest tests/integration/test_bitbucket_http_adapter.py tests/integration/test_bitbucket_discovery.py -x -k "rate_limited or one_attempt or generation or redirect or continuation or budget"` | ✅ | ✅ green |
| 03-05-02 | 05 | 3 | BITB-02/06 | T-03-14–17, SC | Provider operation surface is allowlisted and GET-only | integration + architecture | `cd backend && uv run pytest tests/integration/test_bitbucket_http_adapter.py tests/architecture/test_provider_boundaries.py -x` | ✅ | ✅ green |
| 03-06-01 | 06 | 4 | BITB-06 | T-03-18–20, SC | Diagnostics are typed, bounded and secret-free | integration | `cd backend && uv run pytest tests/integration/test_bitbucket_diagnostics.py -x` | ✅ | ✅ green |
| 03-06-02 | 06 | 4 | BITB-06 | T-03-18–20, SC | One terminal diagnostic per closed provider failure | integration | `cd backend && uv run pytest tests/integration/test_bitbucket_diagnostics.py tests/integration/test_import_jobs.py -x -k "diagnostic or sanitized_error"` | ✅ | ✅ green |
| 03-07-01 | 07 | 5 | BITB-02/05/06 | T-03-21–24, SC | Retry and late-worker transitions preserve the valid baseline | integration | `cd backend && uv run pytest tests/integration/test_import_jobs.py -x -k "transition or retry or retained_baseline or same_commit or current_capability or concurrency or late_worker"` | ✅ | ✅ green |
| 03-07-02 | 07 | 5 | BITB-02/05/06 | T-03-21–24, SC | Separate baselines are atomic; watchdog terminalization is bounded | integration + architecture | `cd backend && uv run pytest tests/integration/test_import_jobs.py tests/architecture/test_background_boundaries.py -x -k "separate or source_order or worker_loss or watchdog or background_boundary"` | ✅ | ✅ green |
| 03-08-01 | 08 | 6 | BITB-05/06 | T-03-25–27, SC | Exact ancestry and complete bounded diffstat | integration | `cd backend && uv run pytest tests/integration/test_bitbucket_http_adapter.py tests/integration/test_bitbucket_discovery.py -x -k "ancestry or diffstat or equal_commit or continuation or budget"` | ✅ | ✅ green |
| 03-08-02 | 08 | 6 | BITB-05/06 | T-03-25–27, SC | Direct and separate source movement classify atomically | integration | `cd backend && uv run pytest tests/integration/test_import_jobs.py -x -k "classify or fast_forward or rewrite_delta or zero_delta or separate"` | ✅ | ✅ green |
| 03-09-01 | 09 | 7 | BITB-05/06 | T-03-28–31, SC | Complete current rewrite proposal is ownership-safe | integration + migration | `cd backend && uv run pytest tests/integration/test_import_jobs.py tests/integration/test_migrations.py -x -k "rewrite_proposal or rewrite_migration or zero_delta or incomplete"` | ✅ | ✅ green |
| 03-09-02 | 09 | 7 | BITB-05/06 | T-03-28–31, SC | Exact fresh proposal confirms one baseline atomically | integration | `cd backend && uv run pytest tests/integration/test_import_jobs.py -x -k "rewrite_comparison or rewrite_confirmation or current_baseline or stale_proposal or separate"` | ✅ | ✅ green |
| 03-10-01 | 10 | 8 | BITB-02/05/06 | T-03-32–35, SC | Five admin import operations are closed and authorized | integration + contract | `cd backend && uv run pytest tests/integration/test_import_jobs.py -x -k "public_contract or authorization or cursor or rewrite"` | ✅ | ✅ green |
| 03-10-02 | 10 | 8 | BITB-02/05/06 | T-03-32–35, SC | Product-local affected counts are complete and constant-query | API | `cd backend && uv run pytest tests/api/test_admin_products.py -x -k "affected_mapping_count or query_count"` | ✅ | ✅ green |
| 03-11-01 | 11 | 9 | BITB-02/05/06 | T-03-36–38, SC | OpenAPI operation and schema equality is frozen | contract | `cd backend && uv run pytest tests/api/test_openapi_contract.py -x -k "import or bitbucket_capability or affected_mapping"` | ✅ | ✅ green |
| 03-11-02 | 11 | 9 | BITB-02/05/06 | T-03-36–38, SC | Generated client uses exact bearer routes without drift | contract | `cd frontend && npm run api:generate && npm test -- --run src/api/admin-client-contract.test.ts && npm run api:check` | ✅ | ✅ green |
| 03-12-01 | 12 | 10 | BITB-02/05/06 | T-03-39–42, SC | Polling is bounded, identity-fenced and terminal-aware | component | `cd frontend && npm test -- --run src/features/admin/imports/useImportPolling.test.ts` | ✅ | ✅ green |
| 03-12-02 | 12 | 10 | BITB-02/05/06 | T-03-39–42, SC | Cursor/state UI rejects obsolete loads and mutations | component | `cd frontend && npm test -- --run src/features/admin/imports/PublishedMappingImports.test.tsx src/features/admin/mappings/ProductMappingsPage.test.tsx` | ✅ | ❌ red — WR-02 |
| 03-13-01 | 13 | 11 | BITB-02/05/06 | T-03-43–46, SC | Rewrite confirmation is live-identity fenced and separates commit success from refresh | component | `cd frontend && npm test -- --run src/features/admin/imports/RewrittenBaselineDialog.test.tsx src/features/admin/imports/PublishedMappingImports.test.tsx` | ✅ | ❌ red — WR-03 and WR-09 |
| 03-13-02 | 13 | 11 | BITB-02/05/06 | T-03-43–46, SC | Product freshness and responsive error focus work in a real viewport | component + browser | `cd frontend && npm test -- --run src/features/admin/products/ProductConfiguration.test.tsx src/features/admin/imports/RewrittenBaselineDialog.test.tsx && npx playwright test e2e/admin-configuration.spec.ts --grep "UI3-C23|UI3-C24|UI3-C26|initial import|fast-forward|manual retry|rewritten baseline|mobile import failure"` | ✅ | ❌ red — WR-10 |
| 03-14-01 | 14 | 12 | BITB-02/05/06 | T-03-47–49, SC | Disposable deployment proves import/recovery with zero provider writes | deployment smoke | `bash tools/phase3_smoke.sh --mock-provider` | ✅ | ✅ green |
| 03-14-02 | 14 | 12 | BITB-02/05/06 | T-03-47–49, SC | Supplemental live mode is bounded, optional and read-only | architecture + smoke | `bash tools/phase3_smoke.sh --self-test-live-mode && env -u VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID -u VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET -u VERBOFLEX_BITBUCKET_LIVE_WORKSPACE -u VERBOFLEX_BITBUCKET_LIVE_REPOSITORY bash tools/phase3_smoke.sh --live-provider-read-only --skip-if-unconfigured` | ✅ | ✅ green |
| 03-15-01 | 15 | 13 | BITB-02/05/06 | T-03-50–53, SC | Semantic, UI, API and provider boundaries reconcile exactly | architecture | `cd backend && uv run pytest tests/architecture/test_phase3_scope.py tests/architecture/test_provider_boundaries.py tests/architecture/test_background_boundaries.py -x` | ✅ | ✅ green |
| 03-15-02 | 15 | 13 | BITB-02/05/06 | T-03-50–53, SC | Mutation proof and source digest include every executable test input | gauntlet + architecture | `cd backend && uv run pytest tests/architecture/test_phase3_gauntlet.py -x && cd .. && bash tools/phase3_gauntlet.sh` | ✅ | ❌ red — WR-04 |
| 03-16-01 | 16 | 14 | BITB-02/05/06 | T-03-54–57, SC | Final gauntlet and source digest close without drift | full gauntlet | `bash tools/phase3_gauntlet.sh` | ✅ | ⚠️ blocked by RED regressions |
| 03-16-02 | 16 | 14 | BITB-02/05/06 | T-03-54–57, SC | Fresh ASVS review binds to the exact tested digest | review integrity | `VERBOFLEX_SOURCE_MANIFEST=tools/phase3_source_manifest.txt VERBOFLEX_REVIEW_PATH=docs/reviews/phase-03-code-security.md tools/source_state.sh --verify-review-source` | ✅ | ⚠️ invalidated until fixes and fresh review |
| 03-16-03 | 16 | 14 | BITB-02/05/06 | T-03-54–57, SC | Independent verifier, evidence and review share one digest | closeout integrity | `rg -q '^status: passed$' .planning/phases/03-bitbucket-import-integration/03-VERIFICATION.md && VERBOFLEX_SOURCE_MANIFEST=tools/phase3_source_manifest.txt VERBOFLEX_REVIEW_PATH=docs/reviews/phase-03-code-security.md tools/source_state.sh --verify-review-source` | ✅ | ⚠️ invalidated until fixes and fresh verification |

*Status: ✅ green · ❌ red · ⚠️ blocked by an upstream RED regression*

---

## Wave 0 Requirements

- [x] `backend/tests/integration/test_bitbucket_oauth.py` — WR-01 lifetime boundary regressions.
- [x] `backend/tests/architecture/test_phase3_gauntlet.py` — WR-04 executable-registry manifest and digest negative controls.
- [x] `frontend/src/features/admin/imports/PublishedMappingImports.test.tsx` — WR-02 stale start response regression.
- [x] `frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx` — WR-03 and WR-09 confirmation regressions.
- [x] `frontend/e2e/admin-configuration.spec.ts` — WR-10 real mobile viewport focus regression.
- [x] Existing pytest, Vitest and Playwright infrastructure runs the new tests without fixture, import, syntax, lint, format or type errors.

No test infrastructure is missing. The six tests fail only at the intended production/configuration assertions.

---

## Manual-Only Verifications

The workflow classifies implementation escalations as manual-only until production fixes make their automated regressions green. These are not subjective checks: each row already has a deterministic RED test.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Oversized OAuth lifetimes fail through `OAuthConnectionUnavailable` | BITB-02/06 | Production leaks `OverflowError` | Run the WR-01 pytest cases in `test_bitbucket_oauth.py` |
| Product A's deferred start response cannot affect product B | BITB-02/05/06 | Mutation lacks live product/generation fencing | Run the WR-02 `PublishedMappingImports` test |
| Obsolete rewrite confirmation has no callbacks or UI side effects | BITB-05/06 | Confirmation compares stale closure values | Run the WR-03 dialog test |
| Committed confirmation stays successful when collection refresh fails | BITB-05/06 | UI conflates mutation success with refresh failure | Run the WR-09 dialog test |
| Executable JSON registry participates in the canonical digest | BITB-02/05/06 | Manifest omits the registry path | Run the WR-04 architecture tests |
| Mobile import failure focuses the visible mobile alert | BITB-02/06 | Ref targets the hidden desktop duplicate | Run the WR-10 Playwright test at 320×720 |

---

## Audit Evidence

### Pre-gap canonical run

The unmodified merged source completed `bash tools/phase3_gauntlet.sh` on 2026-09-03:

- 14/14 layers passed in 417 seconds.
- Backend: 952/952 tests; 95% aggregate coverage.
- Frontend: 356/356 tests; 83.5% statement coverage.
- Mutation proof: 6/6 backend and 25/25 frontend mutants killed.
- Architecture/provider audit: 116/116 tests.
- Deployment smoke: 59 provider resource GETs, 0 provider resource writes.
- API capability matrix: 56/56 rows accounted for.
- Source digest: `e5d23977e946a9ec98ad57d1fd9893c2cec7a1d364f73c54862ef68ba668c51c`.

### Nyquist gap run

| Suite | Result |
|-------|--------|
| OAuth lifetime boundary | 1 passed, 2 failed |
| Manifest coverage and digest negative control | 1 passed, 1 failed |
| Focused import/reconciliation Vitest | 23 passed, 3 failed |
| Mobile Playwright regression | 1 failed |
| Ruff check/format, TypeScript typecheck, ESLint, Prettier, `git diff --check` | passed |

The six failures reproduce WR-01, WR-02, WR-03, WR-04, WR-09 and WR-10. The auditor performed no implementation, manifest, configuration or planning mutation.

## Validation Audit 2026-09-03

| Metric | Count |
|--------|-------|
| Phase requirements | 3 |
| Planned tasks | 32 |
| Tasks with automated commands | 32 |
| Root tasks green | 27 |
| Root tasks partial/RED | 5 |
| Regression gaps found | 6 |
| Gaps resolved | 0 |
| Implementation/configuration escalations | 6 |

---

## Validation Sign-Off

- [x] All tasks have an `<automated>` verify command.
- [x] Sampling continuity: no consecutive task lacks automated verification.
- [x] Wave 0 contains a deterministic test for every discovered gap.
- [x] No watch-mode flag is used.
- [x] Targeted feedback latency is under 30 seconds outside explicit browser/deployment gates.
- [ ] All regression tests are green.
- [ ] `nyquist_compliant: true` is set in frontmatter.

**Approval:** validated partial on 2026-09-03; production/configuration remediation and fresh digest-bound closeout are required.
