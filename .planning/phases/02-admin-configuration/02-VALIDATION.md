---
phase: 02-admin-configuration
status: planned
nyquist_compliant: true
wave_0_complete: false
focused_latency_max_seconds: 60
updated: 2026-08-26
---

# Phase 2 Validation Strategy

Every production-code task creates its RED test file inline as its first action. There are no missing Wave 0 test-scaffold prerequisites. `wave_0_complete: false` means execution has not started; it does not mean the listed test files must pre-exist. Every TDD row uses the task's exact command unchanged for RED, GREEN, and REFACTOR and retains separate evidence. Focused commands target less than 60 seconds. Playwright, Compose, mutation, full review, and the final gauntlet are completion/wave gates and never run inside a focused RED/GREEN loop.

## Exact Focused Task Map

| ID | Plan/task | Wave | Requirement | Threat | Evidence created inline | Exact command | Pre-execution state |
|---|---|---:|---|---|---|---|---|
| TDD-01 | 02-01/T1 | 1 | AUTH-02, AUTH-03 | T-02-01, T-02-07 | guarded user create/list and one-time secret API | `cd backend && uv run pytest -q tests/api/test_admin_users.py -x` | planned inline |
| TDD-02 | 02-01/T2 | 1 | AUTH-02, AUTH-03 | T-02-01, T-02-02, T-02-07 | stable role order/no-op, fresh reset/reactivation secrets, endpoint denial/status/one-time response and last-admin concurrency | `cd backend && uv run pytest -q tests/unit/services/test_admin_users.py tests/integration/test_admin_user_concurrency.py tests/api/test_admin_users.py tests/api/test_openapi_contract.py -x` | planned inline after T1 |
| TDD-03 | 02-02/T2 | 2 | PROD-01 | T-02-02 | A-01 and immutable candidate domain | `cd backend && uv run pytest -q tests/unit/test_product_names.py -x` | planned inline after satisfied D-20 checkpoint |
| TDD-04 | 02-02/T3 | 2 | PROD-01 | T-02-01, T-02-02 | product identical-save no-op plus empty/default/max 50/100/invalid-cursor/stable-order collection API | `cd backend && uv run pytest -q tests/api/test_admin_products.py -x` | planned inline after T2 |
| TDD-05 | 02-03/T2 | 3 | PROD-02 | T-02-02 | normalized registry registration race: one 201, one bounded 409, one row; existing-UUID selection remains separate | `cd backend && uv run pytest -q tests/integration/test_repository_registry.py -x` | planned inline after satisfied D-07 checkpoint |
| TDD-06 | 02-03/T3 | 3 | PROD-02 | T-02-01, T-02-02 | closed register/list/get API with duplicate 409 and empty/default/max 50/100/invalid-cursor/stable fallback order | `cd backend && uv run pytest -q tests/api/test_admin_repositories.py -x` | planned inline after T2 |
| TDD-07 | 02-04/T2 | 4 | BITB-01 | T-02-03, T-02-07, T-02-SC | 32-byte state, digest-only Redis TTL 600, complete binding, atomic consume, fixed redirect and replay/tamper/open-redirect negatives | `cd backend && uv run pytest -q tests/integration/test_bitbucket_oauth.py::test_connects_single_encrypted_repository_scope_generation -x` | planned inline after package checkpoint |
| TDD-08 | 02-04/T3 | 4 | BITB-01 | T-02-03, T-02-07 | encryption tamper/schema/log/metadata | `cd backend && uv run pytest -q tests/integration/test_bitbucket_oauth.py -x` | planned inline after T2 |
| TDD-09 | 02-05/T1 | 5 | BITB-01 | T-02-03, T-02-07 | reconnect/refresh/local revoke concurrency | `cd backend && uv run pytest -q tests/integration/test_bitbucket_oauth.py -x` | planned inline |
| TDD-10 | 02-05/T2 | 5 | BITB-01 | T-02-01, T-02-07 | lifecycle API and OpenAPI secret negatives | `cd backend && uv run pytest -q tests/api/test_admin_bitbucket.py tests/api/test_openapi_contract.py -x` | planned inline after T1 |
| TDD-11 | 02-06/T1 | 6 | BITB-03, BITB-04 | T-02-03, T-02-04, T-02-07, T-02-SC | safe HTTP metadata tracer | `cd backend && uv run pytest -q tests/integration/test_bitbucket_http_adapter.py::test_reads_metadata_only_through_validated_current_generation -x` | planned inline |
| TDD-12 | 02-06/T2 | 6 | BITB-03, BITB-04 | T-02-03, T-02-04 | stale generation and no-mutation architecture | `cd backend && uv run pytest -q tests/integration/test_bitbucket_http_adapter.py tests/architecture/test_provider_boundaries.py -x` | planned inline after T1 |
| TDD-13 | 02-07/T1 | 7 | BITB-03, BITB-04 | T-02-04, T-02-07 | provider pagelen 100/order/exact names plus public default/max 50/100 and invalid opaque cursor | `cd backend && uv run pytest -q tests/integration/test_bitbucket_discovery.py::test_lists_exact_branches_with_validated_opaque_pagination tests/api/test_admin_discovery.py -x` | planned inline |
| TDD-14 | 02-07/T2 | 7 | BITB-04 | T-02-04, T-02-05 | commit/tree/raw A-03 boundaries | `cd backend && uv run pytest -q tests/integration/test_bitbucket_discovery.py tests/api/test_openapi_contract.py -x` | planned inline after T1 |
| TDD-15 | 02-08/T2 | 8 | PROD-03–PROD-06, PROD-09 | T-02-02, T-02-04 | direct mapping identity/branch plus normalized target-set/default-membership/no-op invariants | `cd backend && uv run pytest -q tests/unit/services/test_mappings.py -x` | planned inline after satisfied D-12 checkpoint |
| TDD-16 | 02-08/T3 | 8 | PROD-03–PROD-06, PROD-09 | T-02-01, T-02-02 | mapping empty/default/max 50/100/invalid-cursor API; exact `(topology_rank, primary_repository_uuid, primary_source_branch COLLATE "C", translations_repository_uuid NULLS LAST, translations_source_branch COLLATE "C" NULLS LAST, mapping_uuid)` collision/cursor order with `direct=0,separate=1`, Direct/Keys primary projection and null Direct translations; conflicts/no-op; negative delete route/OpenAPI | `cd backend && uv run pytest -q tests/api/test_admin_mappings.py -x` | planned inline after T2 |
| TDD-17 | 02-09/T1 | 9 | PROD-03–PROD-06, PROD-09 | T-02-02, T-02-04 | separate-side unit/API | `cd backend && uv run pytest -q tests/unit/services/test_mappings.py tests/api/test_admin_mappings.py -x` | planned inline |
| TDD-18 | 02-09/T2 | 9 | PROD-05 | T-02-02 | empty-input and populated repository+target grouping properties | `cd backend && uv run pytest -q tests/unit/services/test_pr_grouping.py tests/unit/services/test_mappings.py -x` | planned inline after T1 |
| TDD-19 | 02-10/T1 | 10 | PROD-01, PROD-08 | T-02-02, T-02-06 | Product-lock publication concurrency | `cd backend && uv run pytest -q tests/integration/test_product_publication.py -x` | planned inline |
| TDD-20 | 02-10/T2 | 10 | PROD-01, PROD-08 | T-02-01, T-02-06 | lifecycle publication API conflicts | `cd backend && uv run pytest -q tests/api/test_admin_products.py -x` | planned inline after T1 |
| TDD-21 | 02-11/T1 | 11 | PROD-08, BITB-04 | T-02-05, T-02-06 | API→PostgreSQL→Celery durable job | `cd backend && uv run pytest -q tests/integration/test_preview_jobs.py::test_admin_job_runs_api_to_distinct_worker_and_persists_terminal_state -x` | planned inline |
| TDD-22 | 02-11/T2 | 11 | PROD-08 | T-02-06, T-02-07 | attempts/races/closed schemas | `cd backend && uv run pytest -q tests/integration/test_preview_jobs.py -x` | planned inline after T1 |
| TDD-23 | 02-12/T1 | 12 | PROD-08, PROD-09, BITB-04 | T-02-04, T-02-05, T-02-SC | Android fixture and durable tracer | `cd backend && uv run pytest -q tests/unit/localization/preview/test_android_xml.py tests/integration/test_preview_jobs.py::test_android_preview_completes_read_only -x` | planned inline |
| TDD-24 | 02-12/T2 | 12 | PROD-08, PROD-09 | T-02-05 | Android A-02/A-03 boundaries | `cd backend && uv run pytest -q tests/unit/localization/preview/test_android_xml.py tests/integration/test_preview_jobs.py -x` | planned inline after T1 |
| TDD-25 | 02-13/T1 | 13 | PROD-09 | T-02-05, T-02-06 | Qt and duplicate-aware JSON matrices | `cd backend && uv run pytest -q tests/unit/localization/preview/test_qt_ts.py tests/unit/localization/preview/test_json.py -x` | planned inline |
| TDD-26 | 02-13/T2 | 13 | PROD-09 | T-02-05, T-02-06, T-02-07 | iOS lexer and four-format integration | `cd backend && uv run pytest -q tests/unit/localization/preview/test_ios_strings.py tests/integration/test_preview_jobs.py::test_all_four_formats_return_separate_exact_layout_candidates -x` | planned inline after T1 |
| TDD-27 | 02-14/T1 | 14 | PROD-08, PROD-09 | T-02-05, T-02-06, T-02-07 | digest/confirmation/stale matrix | `cd backend && uv run pytest -q tests/integration/test_preview_jobs.py -x` | planned inline |
| TDD-28 | 02-14/T2 | 14 | PROD-01, PROD-08 | T-02-02, T-02-06 | confirmed publication concurrency | `cd backend && uv run pytest -q tests/integration/test_product_publication.py tests/integration/test_preview_jobs.py -x` | planned inline after T1 |
| TDD-29 | 02-15/T1 | 15 | UI-03 | T-02-01, T-02-07 | generated admin client contract; canonical generation with immutable package manifests/dependency graph/lockfile | `cd frontend && npm test -- --run src/api/admin-client-contract.test.ts && npm run api:generate && git diff --quiet -- package.json package-lock.json` | planned inline |
| AUTO-01 | 02-15/T2 | 15 | UI-03 | T-02-07 | deterministic API drift with canonical regeneration and zero package.json/package-lock drift | `cd frontend && npm run api:check && git diff --quiet -- package.json package-lock.json && npm test -- --run src/api/admin-client-contract.test.ts` | planned after T1 outputs exist |
| TDD-30 | 02-16/T1 | 16 | UI-03 | T-02-01, T-02-07 | guarded routes/navigation | `cd frontend && npm test -- --run src/router.test.tsx src/components/layout/AppShell.test.tsx` | planned inline |
| TDD-31 | 02-16/T2 | 16 | UI-03 | T-02-01, T-02-07 | responsive/accessibility route states and exact URL-backed product subnavigation | `cd frontend && npm test -- --run src/router.test.tsx src/components/layout/AppShell.test.tsx` | planned inline after T1 |
| TDD-32 | 02-17/T1 | 17 | AUTH-02, AUTH-03, UI-03 | T-02-01, T-02-07 | user list/add/edit UI | `cd frontend && npm test -- --run src/features/admin/users/UsersPage.test.tsx` | planned inline |
| TDD-33 | 02-17/T2 | 17 | AUTH-02, AUTH-03, UI-03 | T-02-01, T-02-07 | one-time secret/lifecycle UI | `cd frontend && npm test -- --run src/features/admin/users/UsersPage.test.tsx` | planned inline after T1 |
| TDD-34 | 02-18/T1 | 18 | PROD-01, UI-03 | T-02-02 | four-state/filter/paginated/API-order/responsive Product collection, Overview deactivate and five-step candidate UI | `cd frontend && npm test -- --run src/features/admin/products/ProductConfiguration.test.tsx` | planned inline |
| TDD-35 | 02-18/T2 | 18 | PROD-02–PROD-07, PROD-09, UI-03 | T-02-02, T-02-04 | repository/mapping responsive UI | `cd frontend && npm test -- --run src/features/admin/products/ProductConfiguration.test.tsx` | planned inline after T1 |
| TDD-36 | 02-19/T1 | 19 | BITB-01, UI-03 | T-02-03, T-02-07 | OAuth status/redirect/secret UI | `cd frontend && npm test -- --run src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx` | planned inline |
| TDD-37 | 02-19/T2 | 19 | PROD-08, PROD-09, UI-03 | T-02-05, T-02-06, T-02-07 | polling/candidate/confirmation UI | `cd frontend && npm test -- --run src/features/admin/previews/usePreviewPolling.test.ts src/features/admin/previews/ProductPreviewPage.test.tsx` | planned inline after T1 |

## Completion and Phase Gates

These commands intentionally exceed focused-loop scope and run only after all referenced files exist.

| ID | Plan/task | Wave | Gate | Exact command | State |
|---|---|---:|---|---|---|
| E2E-01 | 02-19/T3 | 19 | assembled desktop/mobile UI, Product list states, deactivate/reactivate eligibility, and mocked provider | `cd frontend && npm run e2e -- admin-configuration.spec.ts` | planned after 02-19/T1–T2 |
| SMOKE-01 | 02-20/T1 | 20 | Docker/API/PostgreSQL/Redis/Celery/frontend/migration/mock preview | `bash tools/phase2_smoke.sh --mock-provider` | planned inline after all feature waves |
| GATE-01 | 02-20/T2 | 20 | tests/build/coverage/mutation/review/drift/audit/smoke/unchanged source | `bash tools/phase2_gauntlet.sh` | planned inline after T1 |

## Satisfied and Human Checkpoints

| Plan/task | Kind | State | Contract |
|---|---|---|---|
| 02-02/T1 | decision | already satisfied | D-20 immutable active/editable candidate and atomic publication; no new question |
| 02-03/T1 | decision | already satisfied | D-07 global normalized Repository identity; no new question |
| 02-04/T1 | human verify | blocking before installs | independently verify httpx 0.28.1, defusedxml 0.7.1 and cryptography 50.0.1 official provenance and Python/container compatibility |
| 02-08/T1 | decision | already satisfied | D-12 one mapping identity with exactly direct/separate topology; no new question |
| 02-20/T3 | human action | blocking before live smoke only | exact Bitbucket callback and exact read-only `repository` scope; mocks remain the automated phase gate |

## Nyquist Sign-off

- [x] Every implementation task has an exact automated command.
- [x] RED files are created inline; no misleading Wave 0 prerequisite remains.
- [x] No three consecutive implementation tasks lack automated evidence.
- [x] Focused Vitest commands remain unchanged through RED→GREEN→REFACTOR; Playwright is completion-only.
- [x] A-01, A-02 and A-03 boundary/property/concurrency evidence is mapped.
- [x] T-02-01 through T-02-07 and supply-chain controls are mapped.
- [x] Final migration, mutation, code-review, build/deploy, secret/dependency, API-drift and provider-spy gates are fail closed.
