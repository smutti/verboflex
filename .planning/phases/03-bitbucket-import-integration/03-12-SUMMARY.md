---
phase: 03-bitbucket-import-integration
plan: 12
subsystem: admin-import-ui
tags: [react, typescript, vitest, pagination, polling, accessibility, tdd]

requires:
  - phase: 03-bitbucket-import-integration
    plan: 11
    provides: Generated closed import list, start, and status operations and types
provides:
  - Identity-safe import polling with exact 2s/5s/90s bounds and manual recovery
  - Cursor-complete published mapping collection with deterministic order and deduplication
  - Responsive desktop table and mobile articles with server-projected actions and row-local errors
  - Stable executable coverage for UI3-C02, C03, C06, C07, C09, C11, C14, C18, C19, C21, C22, and C25
affects: [03-13, 03-15, admin-import-ui, rewritten-baseline-review]

actuals:
  tokens: 21659
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - Complete bounded cursor chains are committed to React state atomically after every page succeeds
    - One polling bridge per logical import feeds both responsive presentations without duplicate status requests
    - Generated action literals, not browser-derived state or capability guesses, select row affordances

key-files:
  created:
    - frontend/src/features/admin/imports/PublishedMappingImports.tsx
    - frontend/src/features/admin/imports/PublishedMappingImports.test.tsx
  modified:
    - frontend/src/features/admin/imports/useImportPolling.ts
    - frontend/src/features/admin/imports/useImportPolling.test.ts
    - frontend/src/features/admin/mappings/ProductMappingsPage.tsx
    - frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx
    - frontend/src/features/admin/products/ProductConfiguration.test.tsx

key-decisions:
  - "Publish a cursor-loaded collection only after the complete bounded server chain succeeds; repeated, empty, over-budget, mixed-revision, or superseded chains expose no partial authority."
  - "Run exactly one polling hook per logical import and project its result into both desktop and mobile layouts so responsive duplication never duplicates API observation."
  - "Treat the generated action literal as the sole browser affordance authority and retain server state until a fresh complete projection follows an accepted mutation."

patterns-established:
  - "Atomic cursor collection: preserve server order, keep the first mapping identity, and fence the full chain with abort plus generation identity."
  - "Responsive polling bridge: one hook owns status observation while table and article views remain presentation-only projections."
  - "Bounded error projection: render closed category copy locally and never interpolate generated provider prose or raw diagnostics."

requirements-completed: [BITB-02, BITB-05, BITB-06]

coverage:
  - id: D1
    description: One logical import is observed with exact polling boundaries, complete identity fencing, terminal stops, transition-only announcements, and explicit manual refresh.
    requirement: BITB-05
    verification:
      - kind: unit
        ref: frontend/src/features/admin/imports/useImportPolling.test.ts#bounded-published-import-polling
        status: pass
    human_judgment: false
  - id: D2
    description: Every opaque cursor page is exhausted in server order with first-occurrence deduplication, repeated-cursor rejection, and obsolete-chain suppression.
    requirement: BITB-02
    verification:
      - kind: unit
        ref: frontend/src/features/admin/imports/PublishedMappingImports.test.tsx#UI3-C14-accumulates-every-cursor-page
        status: pass
      - kind: unit
        ref: frontend/src/features/admin/imports/PublishedMappingImports.test.tsx#discards-an-obsolete-page-chain
        status: pass
    human_judgment: false
  - id: D3
    description: The responsive collection renders all seven closed states, exact generated actions, atomic separate baselines, retained stale baselines, local bounded errors, overflow containment, and 44px controls.
    requirement: BITB-06
    verification:
      - kind: automated_ui
        ref: frontend/src/features/admin/imports/PublishedMappingImports.test.tsx#UI3-C02-C03-C06-C11-C14-C18-C19-C21-C22-C25
        status: pass
      - kind: integration
        ref: frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx#UI3-C09
        status: pass
    human_judgment: false
  - id: D4
    description: Duplicate row activation sends one generated mutation, retains the current server projection, reloads the full collection, and starts bounded status observation without provider retry.
    requirement: BITB-05
    verification:
      - kind: integration
        ref: frontend/src/features/admin/imports/PublishedMappingImports.test.tsx#submits-one-generated-mutation
        status: pass
      - kind: integration
        ref: frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx#runs-one-published-direct-import
        status: pass
    human_judgment: false

duration: 29min
completed: 2026-09-03
status: complete
---

# Phase 03 Plan 12: Cursor-Complete Published Import UI Summary

**Every published mapping is now loaded through one bounded server-ordered cursor chain and rendered as a responsive, identity-safe import surface with exact polling, recovery, and generated action authority.**

## Performance

- **Duration:** 29 min
- **Started:** 2026-09-03T10:36:35Z
- **Completed:** 2026-09-03T11:05:38Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added exact 2-second then 5-second polling through the 90-second cutoff, including full import identity fencing, terminal-state stops, stale/unmounted response suppression, transition-only announcements, and manual status refresh.
- Replaced the one-page mapping tracer with an atomic cursor-complete collection that validates non-empty cursors, rejects repetition and page-budget exhaustion, preserves server order, keeps the first duplicate identity, and discards superseded chains.
- Extracted published imports from draft mapping editing into a dedicated component using only generated VerboFlex operations and types, with one guarded start request and no optimistic import state.
- Rendered all seven states and five server-projected actions, complete direct or Keys/Translations baselines, retries, timestamps, bounded row-local error copy, local opaque-value overflow, semantic desktop tables, and stacked mobile articles.
- Proved all 12 assigned stable UI consideration identities exactly once and passed the complete 347-test frontend regression, production build, TypeScript, ESLint, and Prettier gates.

## Task Commits

1. **Task 1 RED: bounded logical import polling contract** - `68ee1d8` (test)
2. **Task 1 GREEN: identity-safe bounded status observation** - `e7ed634` (feat)
3. **Task 2 RED: cursor-complete responsive collection contract** - `b68422a` (test)
4. **Task 2 GREEN: generated published import collection** - `bedd528` (feat)
5. **Task 2 REFACTOR: project formatting alignment** - `5d41a41` (style)

## Files Created/Modified

- `frontend/src/features/admin/imports/useImportPolling.ts` - Observes one exact import execution through bounded generated status reads and exposes paused manual recovery.
- `frontend/src/features/admin/imports/useImportPolling.test.ts` - Freezes timer edges, identity replacement, announcements, terminal stops, failure pause, and unmount behavior.
- `frontend/src/features/admin/imports/PublishedMappingImports.tsx` - Loads complete published-import chains and renders guarded responsive actions, polling projections, baselines, and fixed local errors.
- `frontend/src/features/admin/imports/PublishedMappingImports.test.tsx` - Covers pagination, deduplication, stale chains, every state/action, responsive/accessibility behavior, duplicate mutation guards, and sensitive-prose exclusion.
- `frontend/src/features/admin/mappings/ProductMappingsPage.tsx` - Mounts the dedicated published-import section before candidate mapping content.
- `frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx` - Verifies mounted ordering, bounded page errors, one generated mutation, and fresh server projection behavior.
- `frontend/src/features/admin/products/ProductConfiguration.test.tsx` - Supplies the empty published-import projection required by the full wizard regression harness.

## Decisions Made

- A partial cursor chain never becomes visible authority. React replaces the collection only when all pages finish under the same request generation and active revision.
- Deduplication retains the first server occurrence of a mapping ID, preserving deterministic page and item order without browser sorting.
- Each logical import mounts one polling bridge; both responsive renderings consume its projection so only one status request sequence exists per row.
- Import initiation is selected only by the generated `action` literal, synchronously guarded by ref and state, and followed by a complete fresh list projection. The generated mutation response is not used optimistically.
- Error text is selected from the closed generated category and fixed application copy. The server error message, provider body, URL, source content, token, and full commit are never announced.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Regression] Updated the mounted tracer fixture to the current generated action contract**

- **Found during:** Task 2 GREEN mounted-page verification
- **Issue:** The older mapping-page tracer fixture predated required `action`, `capability`, and `execution_number` fields, leaving the extracted action button without an accessible name at runtime.
- **Fix:** Added the exact generated initial and queued projections to the fixture without weakening production types or deriving authority in the component.
- **Files modified:** `frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx`
- **Verification:** The complete 17-test mapping-page suite passes.
- **Committed in:** `bedd528`

**2. [Rule 3 - Blocking regression harness] Added a bounded published-import default to product configuration tests**

- **Found during:** Task 2 full frontend regression
- **Issue:** The product wizard harness mounted the new generated collection without mocking its list operation, causing a real rejected request and a second unrelated Alert in a mapping-conflict test.
- **Fix:** Mocked the generated list operation with an empty terminal page in the shared harness setup.
- **Files modified:** `frontend/src/features/admin/products/ProductConfiguration.test.tsx`
- **Verification:** All 23 frontend test files and 347 tests pass.
- **Committed in:** `bedd528`

---

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 3)
**Impact on plan:** Both changes were limited to test fixtures directly affected by the extracted mounted component. No dependency, endpoint, provider permission, or handwritten transport was added.

## Issues Encountered

- The production build retains Vite's pre-existing informational large-chunk warning; compilation succeeds and ESLint reports zero warnings.

## Verification

- `cd frontend && npm test -- --run src/features/admin/imports/PublishedMappingImports.test.tsx src/features/admin/mappings/ProductMappingsPage.test.tsx` - 32 passed.
- `cd frontend && npm test -- --run` - 23 files and 347 tests passed.
- `cd frontend && npm run build` - TypeScript and production Vite build passed.
- `cd frontend && npm run lint` - passed with zero warnings.
- `cd frontend && npm run format:check` - passed with no formatting drift.
- Stable UI identity scan - UI3-C02, C03, C06, C07, C09, C11, C14, C18, C19, C21, C22, and C25 each occur exactly once in their assigned test source.

## TDD Gate Compliance

- Task 1 RED `68ee1d8` failed on the absent bounded polling hook; GREEN `e7ed634` implemented the generated status observer and passed 19 tests at its tracer checkpoint.
- Task 2 RED `b68422a` failed on the absent `PublishedMappingImports` module and missing extracted page behavior.
- Task 2 GREEN `bedd528` followed the unchanged RED behavior contract and passed focused, full-regression, type, lint, format, and build gates; `5d41a41` contains formatting-only cleanup.

## Known Stubs

None. Rewritten-baseline dialog loading and confirmation are explicitly owned by dependent Plan 03-13 through the typed `onReviewBaselineChange` integration seam; this plan introduces no placeholder data, TODO, FIXME, skipped test, mock production transport, or provider shortcut.

## User Setup Required

None - no external service configuration or dependency installation is required.

## Next Phase Readiness

- Plan 03-13 can attach its mapping-scoped rewritten-baseline dialog to the generated `review_baseline_change` action without changing pagination, polling, or responsive collection authority.
- Plan 03-15 can scan the exact 12 stable UI consideration identities owned by this plan.
- No blocker remains for rewritten-history reconciliation, product freshness, or the final Phase 3 gauntlet.

## Self-Check: PASSED

- All seven created or modified implementation/test files plus this summary exist.
- RED/GREEN/refactor commits `68ee1d8`, `e7ed634`, `b68422a`, `bedd528`, and `5d41a41` are present in repository history.
- Targeted and full frontend tests, TypeScript, production build, ESLint, Prettier, stale-chain, repeated-cursor, generated-operation, and stable UI identity gates passed.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-03*
