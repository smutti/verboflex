---
phase: 04-localization-import-search-and-constraints
plan: 15
subsystem: generated-translation-api-contract
tags: [fastapi, openapi, typescript, hey-api, oauth2, contract-testing]

requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [09, 12, 13, 25]
    provides: canonical translation projections, parser outcomes, read routes, and role-gated constraint mutations
provides:
  - exact five-operation Phase 4 translation OpenAPI inventory
  - deterministic generated TypeScript translation and parser-outcome client
  - runtime, type, drift, and recursive sensitive-field contract evidence
affects: [translation-review-ui, constraint-ui, import-diagnostics, generated-client, api-drift-gates]

actuals:
  tokens: 79444
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - FastAPI OpenAPI remains the sole browser wire-contract authority
    - exact-pinned @hey-api/openapi-ts regeneration with fail-on-diff verification
    - runtime request recording paired with compile-time generated-type assertions

key-files:
  created: []
  modified:
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json
    - frontend/src/api/admin-client-contract.test.ts
    - frontend/src/api/client/index.ts
    - frontend/src/api/client/sdk.gen.ts
    - frontend/src/api/client/types.gen.ts

key-decisions:
  - "The generated browser surface contains exactly listTranslationOptions, searchTranslations, getTranslationGroup, putTranslationConstraint, and deleteTranslationConstraint for Phase 4 translations."
  - "FastAPI exports and the pinned generator own every transport type; generated files are never edited by hand and api:check is the drift authority."
  - "Recursive contract tests reject credentials, provider or source bodies, parser exceptions, SQL, queue, staging, and correlation internals from public translation and parser-outcome schemas."
  - "Null versus zero, closed state/source/status enums, selector version and kind, provenance, deletion, bounds, and optimistic versions stay explicit in generated TypeScript."

patterns-established:
  - "Generated-client freeze: assert exact OpenAPI operation maps, generated barrel exports, runtime request behavior, and type aliases together."
  - "Public-schema privacy: recursively traverse reachable properties and fail on internal trust-boundary vocabulary."

requirements-completed: [SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, SRCH-07, SRCH-08, CONS-01, CONS-02, CONS-03, CONS-04, CONS-05]

coverage:
  - id: D1
    description: "The backend and generated browser client expose exactly three translation reads and two role-gated constraint mutations with stable unique operation IDs and OAuth2 bearer security."
    requirement: SRCH-07
    verification:
      - kind: integration
        ref: "backend/tests/api/test_openapi_contract.py#test_translation_operation_surface_is_exact_unique_and_bearer_protected"
        status: pass
      - kind: unit
        ref: "frontend/src/api/admin-client-contract.test.ts — exact five-operation runtime and export assertions"
        status: pass
    human_judgment: false
  - id: D2
    description: "Search options, filters, opaque cursor and path values, grouped selectors, deletion, provenance, counts, and nullability retain their bounded canonical wire shapes."
    requirement: SRCH-01
    verification:
      - kind: integration
        ref: "backend/tests/api/test_openapi_contract.py#test_translation_schemas_are_closed_bounded_and_non_leaking"
        status: pass
      - kind: unit
        ref: "frontend/src/api/admin-client-contract.test.ts — translation query, detail, and generated-type assertions"
        status: pass
    human_judgment: false
  - id: D3
    description: "Constraint request bodies preserve exact maximum and expected-version integers while responses retain actual, effective, source, status, counts, eligibility, and nullable version semantics."
    requirement: CONS-05
    verification:
      - kind: integration
        ref: "backend/tests/api/test_translation_constraints.py and backend/tests/integration/test_translation_constraints.py"
        status: pass
      - kind: unit
        ref: "frontend/src/api/admin-client-contract.test.ts — PUT and DELETE body, encoding, and type assertions"
        status: pass
    human_judgment: false
  - id: D4
    description: "Import dataset status and bounded parser issues are generated alongside translations without leaking private source or exception material."
    verification:
      - kind: integration
        ref: "backend/tests/api/test_openapi_contract.py — import schema and recursive non-leak assertions"
        status: pass
      - kind: unit
        ref: "frontend/src/api/admin-client-contract.test.ts — parser outcome export and forbidden-field assertions"
        status: pass
    human_judgment: false
  - id: D5
    description: "Canonical schema export and @hey-api/openapi-ts generation are deterministic, checked in, type-safe, lint-clean, and production-buildable."
    requirement: SRCH-08
    verification:
      - kind: other
        ref: "npm --prefix frontend run api:check && npm --prefix frontend run typecheck && npm --prefix frontend run lint && npm --prefix frontend run build"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 15: Generated Translation API Contract Summary

**FastAPI's complete Phase 4 translation contract now deterministically generates five bearer-protected TypeScript operations with exact bounded types and recursive privacy guarantees.**

## Performance

- **Duration:** 12min
- **Started:** 2026-09-05T14:54:08Z
- **Completed:** 2026-09-05T15:05:57Z
- **Tasks:** 2
- **Files created or modified:** 9

## Accomplishments

- Froze the exact three-read/two-mutation operation inventory, security, status codes, request bodies, query parameters, schema bounds, enums, UUIDs, and nullability in the live FastAPI OpenAPI suite.
- Exported the canonical schema and generated `listTranslationOptions`, `searchTranslations`, `getTranslationGroup`, `putTranslationConstraint`, and `deleteTranslationConstraint` through the pinned client and barrel.
- Added runtime request recording for reserved-character encoding, bearer-header placement, and mutation bodies together with compile-time assertions for grouped selectors, provenance, deletion, constraints, and parser outcomes.
- Closed the intentionally deferred Plan 04-12 and Plan 04-25 checked-in schema/export gates; the full OpenAPI contract and deterministic client drift check now pass.

## TDD Gate Compliance

- **Task 1 contract freeze — `03ff2e7`:** the pre-change suite exposed the five dependent operations and stale checked-in schema as its two expected failures; the committed exact live-schema inventory passed while frontend export remained owned by Task 2.
- **Task 2 RED — `c1f7588`:** the focused client contract failed because the stale generated module had no translation functions or paths.
- **Task 2 GREEN — `1fb8a1e`:** exact schema export and @hey-api/openapi-ts 0.99.0 generation supplied all operations, public types, parser outcomes, and barrel exports.
- **Task 2 REFACTOR — `5bd9d47`:** consolidated the suite under a phase-neutral generated-client boundary and tightened provenance nullability without touching generator-owned output.

## Task Commits

1. **Freeze the backend Phase 4 operation and schema inventory** - `03ff2e7` (test)
2. **RED: Add failing generated translation client contract** - `c1f7588` (test)
3. **GREEN: Generate the canonical Phase 4 translation client** - `1fb8a1e` (feat)
4. **REFACTOR: Tighten generated client assertions** - `5bd9d47` (refactor)

## Files Created/Modified

- `backend/tests/api/test_openapi_contract.py` - Exact five-operation, security, parameter, response, schema-bound, and recursive non-leak inventory.
- `frontend/openapi.json` - Canonical complete Phase 4 FastAPI export, including translations, constraints, and parser outcomes.
- `frontend/src/api/client/index.ts` - Generator-owned barrel for the five translation functions and all associated public types.
- `frontend/src/api/client/sdk.gen.ts` - Generator-owned GET/GET/GET/PUT/DELETE request implementations with bearer security.
- `frontend/src/api/client/types.gen.ts` - Generator-owned bounded translation, constraint, selector, provenance, deletion, and parser-outcome types.
- `frontend/src/api/admin-client-contract.test.ts` - Runtime encoding/auth and compile-time operation/type/security drift assertions.
- `frontend/src/features/admin/imports/PublishedMappingImports.test.tsx` - Canonical default parser-outcome fields in the shared import fixture.
- `frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx` - Canonical default parser-outcome fields in the rewrite fixture.
- `frontend/src/features/admin/imports/useImportPolling.test.ts` - Canonical default parser-outcome fields in the polling fixture.

## Decisions Made

- Treat the live FastAPI schema as the only transport source, including imported parser outcomes and constraint projections; no parallel handwritten frontend DTO or fetch wrapper is permitted.
- Keep exactly five translation operation IDs and prove every one is exported once, bearer protected, and callable through the generated runtime.
- Preserve opaque identifiers and reserved query/path characters through generated encoding instead of adding client-owned normalization.
- Scan public schemas structurally rather than by serialized substring so nested sensitive properties cannot evade the trust-boundary test.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking compatibility] Aligned legacy import-response test fixtures with canonical parser outcomes**
- **Found during:** Task 2 GREEN type verification
- **Issue:** Three existing import UI test builders returned the pre-Plan-04-12 response shape and omitted required `dataset_status`, `parser_issues`, and `parser_issue_remaining_count` fields after regeneration.
- **Fix:** Added neutral canonical defaults to the three test-only builders; no production transport or UI fallback was introduced.
- **Files modified:** `frontend/src/features/admin/imports/PublishedMappingImports.test.tsx`, `frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx`, `frontend/src/features/admin/imports/useImportPolling.test.ts`
- **Verification:** TypeScript, the focused client suite, and all three adjacent import UI suites pass.
- **Committed in:** `1fb8a1e`

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking compatibility issue).
**Impact on plan:** The change only updates test fixtures to the canonical generated response and closes the dependent parser-outcome contract; product scope did not expand.

## Issues Encountered

- The expected client RED reported both missing runtime functions and an empty translation operation map, directly proving the stale generated artifacts before export.
- The first broad mypy invocation omitted an explicit target and printed usage; rerunning it against `backend/src/verboflex` passed all 103 source files.
- Vite repeated the pre-existing non-blocking chunk-size advisory already recorded in Plan 04-09; the production build completed successfully and this plan did not change bundling configuration.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. Empty parser-issue arrays and request-recording arrays are intentional test fixtures, not production placeholders or unwired UI data.

## Verification

- Backend OpenAPI, translation API, constraint API, search integration, constraint integration, activation, and import-job slice - 188 passed.
- Exact backend OpenAPI contract alone - 20 passed, including the formerly deferred schema/export assertions.
- Frontend generated-client and adjacent import fixtures - 67 passed across 4 files.
- `npm --prefix frontend run api:check` - deterministic exact-pinned schema export and client regeneration passed with no diff.
- Frontend TypeScript, ESLint, Prettier, and production Vite build - passed.
- Backend Ruff lint/format and strict mypy over 103 source files - passed.
- `detect-secrets-hook --no-verify` over every authored/generated file in the plan - passed with no findings.
- Stub scan found no production placeholder, TODO, FIXME, empty-data source, or handwritten translation transport.

## Threat Review

- T-04-45 is mitigated by exact operation-set equality, pinned deterministic generation, single-export checks, and `api:check` drift-detection evidence.
- T-04-46 is mitigated by recursively rejecting credentials, provider/source bodies, parser exceptions, SQL, queue, staging, and correlation internals from public schemas, plus a secret scan over all changed files.
- T-04-47 is mitigated by exact OAuth2 bearer inventory and the existing complete role/currentness mutation API tests included in the 188-test gate.
- No network endpoint, authentication path, file-access behavior, or database trust boundary beyond the plan's declared generated-client surface was introduced.

## Next Phase Readiness

- Translation review and constraint UI plans can import every Phase 4 operation and type from the canonical generated barrel without handwritten transport code.
- Import diagnostics can consume generated dataset status and bounded parser issues with the same drift guarantees.
- The Plan 04-12 and Plan 04-25 schema/export deferrals are resolved; no Plan 04-15 blocker remains.

## Self-Check: PASSED

- All nine implementation/test artifacts and this summary exist.
- Commits `03ff2e7`, `c1f7588`, `1fb8a1e`, and `5bd9d47` resolve in repository history.
- The implementation commit range contains no tracked-file deletions.
- Required frontmatter, all 13 requirement IDs, TDD evidence, deviation status, verification evidence, threat review, and stub disclosure are present.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-05*
