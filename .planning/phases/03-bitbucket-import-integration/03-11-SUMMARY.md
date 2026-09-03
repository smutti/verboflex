---
phase: 03-bitbucket-import-integration
plan: 11
subsystem: generated-api-client
tags: [fastapi, openapi, typescript, hey-api, vitest, tdd]

requires:
  - phase: 03-bitbucket-import-integration
    plan: 04
    provides: Generated Bitbucket capability profile and deterministic client workflow
  - phase: 03-bitbucket-import-integration
    plan: 10
    provides: Canonical five-operation import API and product freshness projection
provides:
  - Exactly five generated administrator import operations with bearer-only VerboFlex transport
  - Closed generated import, reconciliation, capability, and product-freshness types
  - Deterministic FastAPI OpenAPI export and pinned client generation proof
affects: [03-12, 03-13, phase-05, phase-06, admin-import-ui]

actuals:
  tokens: 17376
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - FastAPI OpenAPI remains the sole source for generated browser operations and types
    - Runtime fetch spies prove method, path, query, body, bearer, and destination authority
    - Exact operation allowlists and recursive field audits reject provider or internal surface growth

key-files:
  created: []
  modified:
    - backend/tests/api/test_openapi_contract.py
    - frontend/src/api/admin-client-contract.test.ts
    - frontend/src/api/client/index.ts
    - frontend/src/api/client/sdk.gen.ts
    - frontend/src/api/client/types.gen.ts
    - frontend/src/features/admin/previews/ProductPreviewPage.test.tsx
    - frontend/src/features/admin/products/ProductConfiguration.test.tsx
    - frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx
    - frontend/src/router.test.tsx

key-decisions:
  - "Keep exactly five Phase 3 import operations generated from canonical FastAPI OpenAPI; every provider mutation remains structurally absent."
  - "Prove browser authority at runtime with an in-memory bearer and an exact VerboFlex-origin request recording client."
  - "Treat affected_mapping_count as a required server-owned product field in every typed frontend fixture."

patterns-established:
  - "Generated authority proof: backend schema freeze plus frontend runtime request spy plus byte-stable regeneration."
  - "Closed import surface: exact operation/type inventories and recursive forbidden-field scans fail on unapproved additions."

requirements-completed: [BITB-02, BITB-05, BITB-06]

coverage:
  - id: D1
    description: Canonical OpenAPI exposes exactly five unique bearer-protected import operations with frozen response codes, parameter placement, required fields, literals, and bounds.
    requirement: BITB-02
    verification:
      - kind: integration
        ref: backend/tests/api/test_openapi_contract.py#test_import_operation_surface_is_exact_unique_and_bearer_protected
        status: pass
      - kind: integration
        ref: backend/tests/api/test_openapi_contract.py#test_import_schema_literals_requirements_and_bounds_are_frozen
        status: pass
    human_judgment: false
  - id: D2
    description: The generated client sends list, start, status, comparison, and confirmation requests only to exact VerboFlex routes with correct query/body placement and bearer authority.
    requirement: BITB-05
    verification:
      - kind: unit
        ref: frontend/src/api/admin-client-contract.test.ts#calls-exactly-five-generated-import-operations-through-VerboFlex-bearer-routes
        status: pass
    human_judgment: false
  - id: D3
    description: Generated import and product types are closed, provider-mutation and sensitive fields remain absent, and a second pinned generation produces no drift.
    requirement: BITB-06
    verification:
      - kind: unit
        ref: frontend/src/api/admin-client-contract.test.ts#generates-closed-import-and-product-types-without-provider-mutation-surface
        status: pass
      - kind: other
        ref: cd frontend && npm run api:check
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-09-03
status: complete
---

# Phase 03 Plan 11: Canonical Generated Import Client Summary

**Five server-derived administrator import operations now carry closed reconciliation and freshness types through a deterministic TypeScript client with exact runtime transport proofs.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-09-03T10:21:10Z
- **Completed:** 2026-09-03T10:30:00Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Froze the canonical backend contract for exactly five import operations, including unique IDs, bearer protection, response codes, parameter/body placement, closed literals, required fields, bounds, and recursive secret exclusions.
- Regenerated the client only through the checked-in FastAPI exporter and pinned `@hey-api/openapi-ts` configuration, adding rewrite comparison/confirmation and the required product freshness field.
- Added runtime request spies proving all five operations remain on the configured VerboFlex origin with in-memory bearer authority, exact paths, opaque cursor encoding, and confirmation-only JSON body placement.
- Proved the generated surface excludes attempt history, task identity, provider diagnostics, raw sources, unsafe provider URLs, and every branch/commit/pull-request mutation.
- Repeated canonical generation with no byte drift and retained successful TypeScript, build, lint, format, backend, and frontend contract gates.

## Task Commits

1. **Task 1 RED: canonical import operation and schema contract** - `3f1a53b` (test)
2. **Task 2 RED: generated runtime and type contract** - `866046a` (test)
3. **Task 2 GREEN: pinned canonical TypeScript generation** - `64c3e39` (feat)

## Files Created/Modified

- `backend/tests/api/test_openapi_contract.py` - Freezes the exact five-operation surface, closed bounded schemas, product count, and canonical generated-client agreement.
- `frontend/src/api/admin-client-contract.test.ts` - Exercises all five generated operations and rejects forbidden types, fields, destinations, and mutations.
- `frontend/src/api/client/index.ts` - Re-exports the generated rewrite operations and complete closed Phase 3 type surface.
- `frontend/src/api/client/sdk.gen.ts` - Adds generated rewrite comparison and confirmation requests on exact VerboFlex routes.
- `frontend/src/api/client/types.gen.ts` - Adds reconciliation types, bounded import errors, expanded state/action/error unions, and required product freshness.
- `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx` - Supplies the required freshness count in the canonical product fixture.
- `frontend/src/features/admin/products/ProductConfiguration.test.tsx` - Supplies the required freshness count across product lifecycle fixtures.
- `frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx` - Supplies the required freshness count in administrator summary fixtures.
- `frontend/src/router.test.tsx` - Supplies the required freshness count in routed product authority.

## Decisions Made

- Canonical FastAPI OpenAPI and the pinned generator remain the sole authority for all browser wire operations and types; generated files were not hand-edited.
- Phase 3 exposes exactly five import operations. Future source-write, branch, commit, and pull-request capabilities remain absent from the executable browser client.
- Every typed product fixture now supplies `affected_mapping_count`, preserving its required server-owned semantics instead of weakening the generated type.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test bug] Matched generated exports as exact identifiers**

- **Found during:** Task 2 GREEN backend verification
- **Issue:** A substring count treated `getAdminImportRewriteComparison` as a second occurrence of `getAdminImport`.
- **Fix:** Switched index assertions to escaped identifier-boundary matching and SDK declarations to the exact assignment signature.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`
- **Verification:** All four selected backend OpenAPI import tests pass.
- **Committed in:** `64c3e39`

**2. [Rule 3 - Blocking issue] Aligned typed product fixtures with canonical freshness**

- **Found during:** Task 2 GREEN TypeScript verification
- **Issue:** Seven pre-generation product fixtures omitted the newly generated required `affected_mapping_count` field, blocking `tsc` and the production build.
- **Fix:** Added explicit zero-count server projections to the shared and inline fixtures without changing runtime behavior.
- **Files modified:** `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx`, `frontend/src/features/admin/products/ProductConfiguration.test.tsx`, `frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx`, `frontend/src/router.test.tsx`
- **Verification:** TypeScript, production build, ESLint, Prettier, focused client tests, and 137/138 tests in the broader affected-file run pass.
- **Committed in:** `64c3e39`

---

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 3)
**Impact on plan:** Both fixes preserve the frozen server contract and generated authority. No new endpoint, dependency, provider permission, or handwritten transport was introduced.

## Issues Encountered

- An additional affected-file suite found one pre-existing Product Configuration assertion that assumes a single alert while the previously implemented published-import failure alert remains mounted beside the mapping-conflict alert. The focused Plan 03-11 verification is fully green; the unrelated assertion is recorded in `deferred-items.md` for the later Phase 3 UI/gauntlet work.
- The production build retains Vite's pre-existing informational large-chunk warning; compilation succeeds and lint has zero warnings.

## Verification

- `cd backend && uv run pytest tests/api/test_openapi_contract.py -x -k "import or bitbucket_capability or affected_mapping"` - 4 passed.
- `cd frontend && npm run api:generate && npm test -- --run src/api/admin-client-contract.test.ts && npm run api:check` - 15 passed; second generation produced zero diff.
- `cd frontend && npm run build` - TypeScript and production Vite build passed.
- `cd frontend && npm run lint && npm run format:check` - passed with zero lint warnings and no formatting drift.
- Broader changed-fixture run - 137 passed and one pre-existing cross-feature alert assertion deferred.

## TDD Gate Compliance

- Backend RED `3f1a53b` failed because the canonical schema contained rewrite operations and freshness while the generated client did not.
- Frontend RED `866046a` failed specifically on missing rewrite functions and generated surface assertions.
- GREEN `64c3e39` followed both RED commits and passed the unchanged contract tests after pinned canonical generation.
- No refactor commit was required.

## Known Stubs

None. No placeholder, TODO, FIXME, skipped test, mock transport in production code, provider shortcut, or unrun plan verification remains.

## User Setup Required

None - no external service configuration or dependency installation is required.

## Next Phase Readiness

- Plan 03-12 can consume the generated list/start/status/comparison/confirmation types without handwritten transport or wire models.
- Product overview and mapping UI can rely on the required server-owned freshness count and closed import state/action/error unions.
- Provider mutations remain structurally unavailable until the later write-back and pull-request phases.

## Self-Check: PASSED

- All nine modified source, generated, and fixture files plus this summary exist.
- RED/GREEN commits `3f1a53b`, `866046a`, and `64c3e39` are present in repository history.
- Exact plan verification, deterministic generation, build, lint, format, forbidden-surface, and bearer-route gates passed.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-03*
