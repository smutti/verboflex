---
phase: 04-localization-import-search-and-constraints
plan: 09
subsystem: admin-preview-ui
tags: [react, typescript, shadcn, openapi, base-language, accessibility]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [26]
    provides: language-bound preview confirmation and active-revalidation API authority
provides:
  - deterministic sole-language selection and explicit multi-language choice from exact preview candidates
  - generated-client confirmation bodies carrying the selected base language
  - stale, foreign, rejected, and missing-language publication gates with bounded focused feedback
affects: [publication, reactivation, constraints, admin-preview, generated-client]
actuals:
  tokens: 9719
  tasks: 3
  commits: 6
tech-stack:
  added: []
  patterns:
    - candidate-scoped shadcn Select values are the only browser language authority
    - confirmation identity and generation fences include the selected base language
    - backend confirmation projections must exactly match submitted preview authority before enabling publication
key-files:
  created: []
  modified:
    - backend/tests/api/test_openapi_contract.py
    - frontend/src/api/admin-client-contract.test.ts
    - frontend/src/api/client/types.gen.ts
    - frontend/src/features/admin/previews/ProductPreviewPage.tsx
    - frontend/src/features/admin/previews/ProductPreviewPage.test.tsx
key-decisions:
  - "The browser never infers a base language for multiple detections: it auto-selects only one sole exact option and otherwise requires an explicit candidate-scoped choice."
  - "A confirmation becomes local authority only when the generated response matches job, mapping, digest, candidate, candidate version, and base language exactly."
  - "Language and candidate changes increment the confirmation generation, clear local confirmation, and silently discard superseded responses."
patterns-established:
  - "Selection authority: render only server-detected candidate languages through a labeled owned Select; never accept free text."
  - "Publication gate: preserve candidate/language selection on bounded errors while focusing the owning alert and keeping publication disabled."
requirements-completed: [FMT-07, FMT-08]
coverage:
  - id: D1
    description: The canonical OpenAPI and generated browser client require a bounded base-language field without exposing source, provider, or credential data.
    requirement: FMT-07
    verification:
      - kind: unit
        ref: backend/tests/api/test_openapi_contract.py#test_admin_preview_base_language_openapi_is_exact_bounded_and_authorized
        status: pass
      - kind: unit
        ref: frontend/src/api/admin-client-contract.test.ts#confirms one exact base language through the generated bearer client
        status: pass
      - kind: other
        ref: npm --prefix frontend run api:check
        status: pass
    human_judgment: false
  - id: D2
    description: One detected language is visibly selected, multiple languages require an explicit exact option, and absent languages render a bounded blocker.
    requirement: FMT-07
    verification:
      - kind: automated_ui
        ref: frontend/src/features/admin/previews/ProductPreviewPage.test.tsx#single, multiple, and absent base-language cases
        status: pass
    human_judgment: false
  - id: D3
    description: Base-language selection explains constraint inheritance and remains publication-safe across rejected, stale, duplicate, changed, and foreign confirmation results.
    requirement: FMT-08
    verification:
      - kind: automated_ui
        ref: frontend/src/features/admin/previews/ProductPreviewPage.test.tsx#base-language focus, invalidation, stale, and server-authority cases
        status: pass
      - kind: other
        ref: npm --prefix frontend run build
        status: pass
    human_judgment: false
duration: 18min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 09: Exact Base-Language Preview Selection Summary

**The existing Preview surface now selects only exact detected base languages, sends them through the generated bearer client, and waits for a matching backend projection before enabling publication or reactivation.**

## Performance

- **Duration:** 18 minutes
- **Started:** 2026-09-05T10:42:06Z
- **Completed:** 2026-09-05T10:59:29Z
- **Tasks:** 3
- **Files modified:** 5 implementation, generated-contract, and test files, plus GSD tracking artifacts

## Accomplishments

- Froze the required, nullable, bounded base-language confirmation contract with OAuth2, conflict-response, and recursive disclosure assertions, then proved deterministic OpenAPI export.
- Regenerated the typed client and proved exact once-only language serialization through in-memory bearer configuration with no handwritten transport types.
- Added a visible candidate-scoped Base language Select with sole-option defaulting, explicit multi-option choice, a bounded absent-language blocker, inheritance guidance, 44px/reduced-motion behavior, and no free-text path.
- Made confirmation and publication fail closed for rejected, stale, duplicate, changed, or foreign projections while preserving selection and focusing bounded feedback.
- Applied the same exact request and response authority checks to normal publication and active-revision recovery.

## Task Commits

Each TDD stage was committed atomically:

1. **Task 1 contract assertions and deterministic export proof** - `c6d29f8` (test)
2. **Task 2 RED: generated base-language client contract** - `561adc3` (test)
3. **Task 2 GREEN: regenerated typed client and compatible consumers** - `86d60a7` (feat)
4. **Task 3 RED: one/many/none/stale/foreign UI cases** - `d070f49` (test)
5. **Task 3 GREEN: exact selection and publication gating** - `ad3a4ac` (feat)

**Plan metadata:** committed in the final documentation commit.

## Files Created/Modified

- `backend/tests/api/test_openapi_contract.py` - Exact request, response, security, conflict, bounds, and disclosure contract assertions.
- `frontend/src/api/admin-client-contract.test.ts` - Runtime and type proof for exact language serialization through the generated bearer client.
- `frontend/src/api/client/types.gen.ts` - Generator-owned base-language request and response fields for normal and active confirmation.
- `frontend/src/features/admin/previews/ProductPreviewPage.tsx` - Shared labeled Select, inheritance guidance, confirmation generation fencing, exact backend projection checks, and bounded focused errors.
- `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx` - Single/multiple/absent language, accessibility/DOM, rejection, stale, duplicate, foreign-response, publication, and active-recovery coverage.

`frontend/openapi.json`, `frontend/src/api/client/index.ts`, and `frontend/src/api/client/sdk.gen.ts` were regenerated and verified byte-stable; Plan 04-26 had already supplied their current operation shape, so they required no tracked diff.

## Decisions Made

- Auto-select only when the exact selected candidate contains one language. Preserve an empty controlled Select for multiple languages so order and common codes such as `en` never become implicit authority.
- Treat the selected language as part of confirmation identity and request generation, not as display-only state.
- Accept confirmation only from an exact generated backend projection covering the complete job/candidate/digest/language identity; any mismatch remains a bounded failure.
- Explain that translations without their own maximum-length override inherit the base-language limit directly below the labeled selector.

## Deviations from Plan

### Execution Adjustments

**1. Historical RED proof for an already-current dependency contract**

- **Found during:** Task 1 RED
- **Issue:** Plan 04-09 depends on Plan 04-26, whose committed backend and canonical OpenAPI already contained the base-language schema. The new assertion therefore could not fail against live HEAD before its test was added.
- **Adjustment:** Ran the exact helper against the repository's historical pre-base-language OpenAPI from before Plan 04-26 and recorded the intended assertion failure, then proved the live schema passed and exported byte-identically twice.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`
- **Verification:** Focused contract test passed; two exports shared SHA-256 `9d1c49915f3053fe39769aeef13d77a55d96ae303ed52eec8b174287746044e2` and compared byte-equal.
- **Committed in:** `c6d29f8`

### Auto-fixed Issues

**2. [Rule 3 - Blocking] Updated existing generated-client consumers for the newly required field**

- **Found during:** Task 2 GREEN typecheck
- **Issue:** Regenerating the required base-language field correctly made existing Preview confirmation calls and response fixtures fail TypeScript compilation before Task 3 could wire selection.
- **Fix:** Added nullable compatibility requests and authoritative response fields in the generated-client commit; Task 3 then replaced the compatibility request values with exact selected languages in both normal and active flows.
- **Files modified:** `frontend/src/features/admin/previews/ProductPreviewPage.tsx`, `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx`, `frontend/src/api/admin-client-contract.test.ts`
- **Verification:** Generated-client contract, component suite, API drift, and TypeScript all pass.
- **Committed in:** `86d60a7`, completed by `ad3a4ac`

**Total deviations:** 2 documented adjustments (1 dependency/TDD overlap, 1 Rule 3 compatibility fix). Neither introduced a new architecture or transport path.

## TDD Gate Compliance

- Task 1's assertion failed against the historical pre-Plan-04-26 schema, while the dependency-provided GREEN implementation passed at current HEAD; `c6d29f8` commits the durable contract gate.
- Task 2 RED `561adc3` failed because the stale generated type lacked `base_language`; GREEN `86d60a7` regenerated it and passed the focused runtime/type contract.
- Task 3 RED `d070f49` failed in the new selector and publication-authority cases; GREEN `ad3a4ac` passed all 58 preview component tests.
- No standalone REFACTOR commit was needed; shared helpers and the shared `BaseLanguageSelect` were part of the minimal GREEN implementation and all adjacent checks remained green.

## Verification

- Backend focused OpenAPI contract: **1 passed, 17 deselected**.
- Deterministic OpenAPI export: two byte-equal files with SHA-256 `9d1c49915f3053fe39769aeef13d77a55d96ae303ed52eec8b174287746044e2`.
- Generated administrator client contract: **16 passed**.
- Product Preview component/DOM suite: **58 passed**, including visible labels, invalid state, 44px target, constrained width, reduced-motion, inheritance copy, focus recovery, stale responses, and server authority.
- Generated API drift: `api:check` passed with no tracked diff.
- TypeScript and ESLint: passed with zero errors or warnings.
- Prettier: all checked frontend files matched project style.
- Production Vite build: passed, transforming 1,978 modules.
- Git whitespace and unintended deletion checks: passed.

## Issues Encountered

- Radix Select requires pointer-capture, resize-observer, and scroll shims under jsdom. The component test now uses the same bounded shims already established by other project Select tests.
- Vite retains its pre-existing non-blocking advisory for a JavaScript chunk larger than 500 kB; no dependency or bundling configuration changed in this plan.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None beyond the plan's declared server-projection-to-browser-selection boundary. Generated types, exact candidate membership, bearer-only calls, full projection matching, generation fencing, and bounded disclosure tests cover that boundary.

## Next Phase Readiness

- Constraint editing can consume the confirmed mapping base language without inventing browser-side defaults.
- Publication and active-revision recovery both carry exact language authority through generated client operations.
- No unresolved blocker or manual setup remains for this plan.

## Self-Check: PASSED

- All 5 tracked implementation, generated-contract, and test files exist.
- Task commits `c6d29f8`, `561adc3`, `86d60a7`, `d070f49`, and `ad3a4ac` are present in repository history.
- The canonical summary exists and records complete FMT-07/FMT-08 automated coverage.
