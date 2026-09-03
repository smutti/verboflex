---
phase: 03-bitbucket-import-integration
plan: 10
subsystem: bitbucket-import-api
tags: [fastapi, sqlalchemy, postgres, openapi, bitbucket, tdd]

requires:
  - phase: 03-bitbucket-import-integration
    plan: 09
    provides: Durable current rewrite proposals and atomic baseline confirmation
provides:
  - Exactly five administrator-only published-import operations with closed bounded projections
  - Product-local affected mapping counts computed over the complete active revision
  - Canonical OpenAPI authority for import, reconciliation, and product freshness consumers
affects: [03-11, 03-12, 03-13, phase-05, phase-06, admin-product-overview]

actuals:
  tokens: 67369
  tasks: 2
  commits: 6

tech-stack:
  added: []
  patterns:
    - Active-revision freshness is computed by a correlated PostgreSQL aggregate in the product projection
    - Public import authority is frozen through exact operation, response, error, and recursive forbidden-field tests
    - Product list, detail, creation, update, and lifecycle responses share one server-owned response mapper

key-files:
  created: []
  modified:
    - backend/src/verboflex/services/import_jobs.py
    - backend/src/verboflex/services/products.py
    - backend/src/verboflex/schemas/imports.py
    - backend/src/verboflex/schemas/admin_products.py
    - backend/src/verboflex/api/v1/routes/admin_mappings.py
    - backend/src/verboflex/api/v1/routes/admin_products.py
    - backend/tests/integration/test_import_jobs.py
    - backend/tests/api/test_admin_products.py
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json
    - frontend/src/api/admin-client-contract.test.ts

key-decisions:
  - "Count a mapping as affected only when it belongs to the product's active revision, retains an active baseline, and its current logical import state is import_failed."
  - "Embed one correlated count subquery in the product projection so collection query count stays constant and the browser cannot derive authority from paginated import rows."
  - "Keep the canonical OpenAPI document current in Plan 03-10 while deferring generated TypeScript client regeneration to Plan 03-11."

patterns-established:
  - "Freshness predicate: active revision mapping plus active baseline plus current import_failed state."
  - "Aggregate projection: list and detail load Product plus affected_mapping_count in the same root SELECT, followed only by constant select-in revision loads."

requirements-completed: [BITB-02, BITB-05, BITB-06]

coverage:
  - id: D1
    description: Exactly five administrator-only import operations expose current server-owned list, start, status, rewrite-comparison, and rewrite-confirmation authority through closed bounded schemas.
    requirement: BITB-02
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py#public_contract-or-authorization-or-cursor-or-rewrite
        status: pass
      - kind: integration
        ref: backend/tests/api/test_openapi_contract.py#import-operation-surface
        status: pass
    human_judgment: false
  - id: D2
    description: Product collection, detail, and lifecycle responses report exact zero, one, or multiple affected active mappings while excluding current, no-baseline, candidate, and historical mappings.
    requirement: BITB-05
    verification:
      - kind: integration
        ref: backend/tests/api/test_admin_products.py#test_affected_mapping_count_is_product_local_complete_and_response_consistent
        status: pass
    human_judgment: false
  - id: D3
    description: Product freshness is computed by PostgreSQL with constant query count and no provider call, per-row query expansion, or browser-derived authority.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/api/test_admin_products.py#test_affected_mapping_query_count_is_constant_across_product_page_sizes
        status: pass
      - kind: unit
        ref: frontend/src/api/admin-client-contract.test.ts#freezes-every-Phase-3-admin-operation-ID
        status: pass
    human_judgment: false

duration: 1h 22m
completed: 2026-09-03
status: complete
---

# Phase 03 Plan 10: Published Import API and Product Freshness Summary

**Five closed administrator import operations now share one canonical contract, while every product response receives a complete database-owned count of failed refreshes that retain a usable baseline.**

## Performance

- **Duration:** 1h 22m
- **Started:** 2026-09-03T08:54:41Z
- **Completed:** 2026-09-03T10:16:27Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Froze exactly five administrator-only import operations with active-revision ownership, bounded pagination, one logical import identity, closed capability/error/action vocabulary, and secret-free rewrite comparison and confirmation.
- Added `affected_mapping_count` to every product response using the exact active-revision, retained-baseline, current-failure predicate.
- Proved zero, one, and multiple counts while excluding failed first imports, current imports, candidate mappings, and historical mappings.
- Kept product collection query count constant across page sizes by embedding the aggregate in the root PostgreSQL query rather than loading import rows per product.
- Regenerated the canonical OpenAPI document deterministically and aligned backend/frontend operation inventories with the complete Phase 3 surface.

## Task Commits

Each TDD task was committed atomically:

1. **Task 1 RED: initial five-operation public import contract** - `1ed2179` (test)
2. **Task 1 RED expansion: closed state and error projections** - `c3475ed` (test)
3. **Task 1 GREEN: server-authorized import API** - `66f03c5` (feat)
4. **Task 2 RED: product freshness and query-count contracts** - `8084f72` (test)
5. **Task 2 GREEN: database aggregate and product projection** - `16b8e1d` (feat)
6. **Task 2 contract repair: generated schema consumer inventory** - `90a902d` (fix)

## Files Created/Modified

- `backend/src/verboflex/services/import_jobs.py` - Owns active-revision list/status/start and current rewrite comparison/confirmation authority.
- `backend/src/verboflex/schemas/imports.py` - Defines strict bounded import, cursor, baseline, action, error, and rewrite schemas.
- `backend/src/verboflex/api/v1/routes/admin_mappings.py` - Exposes exactly five bearer-protected administrator operations.
- `backend/src/verboflex/services/products.py` - Computes the complete active-revision affected count in the product projection.
- `backend/src/verboflex/schemas/admin_products.py` - Adds the required nonnegative count to the closed product response.
- `backend/src/verboflex/api/v1/routes/admin_products.py` - Maps the server-owned count through the common product response path.
- `backend/tests/integration/test_import_jobs.py` - Covers authorization, pagination, currentness, conflicts, rewrite evidence, and forbidden public data.
- `backend/tests/api/test_admin_products.py` - Covers zero/one/many counts, ownership exclusions, response consistency, and constant query count.
- `backend/tests/api/test_openapi_contract.py` - Freezes all five import operations, their error schemas, and the new product field.
- `frontend/openapi.json` - Stores the deterministic canonical FastAPI contract consumed by generation.
- `frontend/src/api/admin-client-contract.test.ts` - Freezes the complete Phase 3 administrator operation inventory.

## Decisions Made

- `ImportJob.state == "import_failed"` is the current logical failure authority; immutable execution history is not scanned to infer freshness.
- A failed import counts only when `active_baseline_execution_id` is non-null, distinguishing a potentially stale usable baseline from a first import that produced no baseline.
- Product inactivity does not erase freshness metadata: lifecycle responses retain the count while the active revision pointer and baseline remain recorded.
- The OpenAPI input is canonical now; TypeScript SDK/type regeneration remains the explicit responsibility of Plan 03-11.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Completed the backend OpenAPI inventory for the Task 1 operations**
- **Found during:** Task 2 full contract verification
- **Issue:** The existing exact surface test omitted rewrite comparison and confirmation, treated bounded import-domain errors as generic errors, and still expected unsupported list response codes.
- **Fix:** Added both operations and their recursive schema set, separated import-domain error projections from generic errors, corrected the list response set, and regenerated `frontend/openapi.json`.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`, `backend/tests/api/test_admin_products.py`, `frontend/openapi.json`
- **Verification:** Backend OpenAPI suite passes 14/14 and two schema exports are byte-identical.
- **Committed in:** `16b8e1d`

**2. [Rule 3 - Blocking] Aligned the frontend operation freeze with the canonical Phase 3 schema**
- **Found during:** Post-GREEN generated-schema consumer verification
- **Issue:** The frontend contract inventory still identified itself as Phase 2 and rejected the two approved reconciliation operations present in canonical OpenAPI.
- **Fix:** Renamed the inventory to Phase 3 and added the exact comparison and confirmation method/path/operation-ID pairs.
- **Files modified:** `frontend/src/api/admin-client-contract.test.ts`
- **Verification:** Frontend contract tests pass 13/13; TypeScript, ESLint, and Prettier checks pass.
- **Committed in:** `90a902d`

---

**Total deviations:** 2 auto-fixed (2 Rule 3 blocking issues)
**Impact on plan:** Both repairs close contract drift created by the approved Task 1 surface; neither adds an operation or provider capability beyond the plan.

## Issues Encountered

- The RED fixture initially reused globally unique product names and preview digests, then allowed SQLAlchemy to flush cyclic import rows in the wrong order. The fixture was corrected before the RED commit so the committed failure was exclusively the missing product field and aggregate query.
- Context7 was unavailable both as MCP and local `ctx7`; no dependency or unfamiliar API was introduced, and SQLAlchemy behavior was verified against the installed runtime through executable PostgreSQL tests and strict typing.

## Verification

- Full plan backend aggregate: 97/97 passed across import integration, product API, and OpenAPI contract suites.
- Task 1 plan selector: 28/28 passed for public contract, authorization, cursor, and rewrite cases.
- Task 2 plan selector: 2/2 passed for affected counts and query-count proof.
- Frontend generated-schema consumer contract: 13/13 passed.
- Ruff lint and formatting: passed for all Task 1 and Task 2 backend sources/tests.
- Strict mypy: passed for all six import/product service, schema, and route modules.
- TypeScript, ESLint, Prettier, and deterministic OpenAPI export checks: passed.

## TDD Gate Compliance

- Task 1 RED commits `1ed2179` and `c3475ed` preceded GREEN `66f03c5`; the user explicitly approved its tracer checkpoint.
- Task 2 RED `8084f72` failed on the absent `affected_mapping_count` field and absent `import_jobs` aggregate before GREEN `16b8e1d` passed the unchanged tests.
- No refactor commit was required after the complete backend, frontend, formatting, and strict type gates.

## Known Stubs

None. No placeholder, TODO, FIXME, skipped test, mock product authority, or unrun plan verification remains.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-11 can deterministically generate TypeScript types and operations from the canonical five-operation import and product-freshness contract.
- Product Overview and mapping UI work can consume a server-owned count without loading or counting import pages.
- Provider writes remain unavailable; later branch, commit, and pull-request execution boundaries are unchanged.

## Self-Check: PASSED

- All eleven implementation, schema, generated-contract, and test artifacts plus this summary exist.
- RED/GREEN/fix commits `1ed2179`, `c3475ed`, `66f03c5`, `8084f72`, `16b8e1d`, and `90a902d` are present in repository history.
- Summary status, actuals, requirements, coverage, TDD order, verification evidence, deviation record, threat-boundary disposition, and stub inventory are complete.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-03*
