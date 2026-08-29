---
phase: 02-admin-configuration
plan: 34
subsystem: admin-ui
tags: [react, typescript, cursor-pagination, playwright, product-lifecycle, tdd]

requires:
  - phase: 02-admin-configuration/02-28
    provides: Dependency-free cursor collection with stable-ID deduplication and generation isolation
  - phase: 02-admin-configuration/02-32
    provides: Product-first candidate/active revision selection and unchanged-revision reactivation
  - phase: 02-admin-configuration/02-33
    provides: Role-aware guarded administration shell used by the browser journey
provides:
  - Terminal-cursor mapping readiness for candidate publication and active reactivation
  - Partial page failure state with bounded count, exact-cursor retry, and no premature preview or lifecycle mutation
  - Current-source real-backend proof that mapping 51 changes publication and reactivation eligibility
affects: [phase-02-verification, admin-preview, product-lifecycle, cursor-pagination]

actuals:
  tokens: 9928
  tasks: 2
  commits: 6

tech-stack:
  added: []
  patterns:
    - Existing cursor collection owns the only ordered/deduplicated mapping accumulator
    - Terminal next_cursor absence is a prerequisite for validation and lifecycle authority
    - Disposable current-source browser fixtures exercise boundary pagination without shared database residue

key-files:
  created:
    - .planning/phases/02-admin-configuration/02-34-SUMMARY.md
  modified:
    - frontend/src/features/admin/previews/ProductPreviewPage.tsx
    - frontend/src/features/admin/previews/ProductPreviewPage.test.tsx
    - frontend/e2e/admin-configuration.spec.ts

key-decisions: []

patterns-established:
  - "Complete mapping readiness: a loaded first page is partial until the existing cursor collector observes next_cursor absent."
  - "Generation safety: query identity includes product and revision identity, so superseded pages and polling completions cannot authorize the next screen."
  - "Boundary lifecycle proof: seed blocked and ready 51-mapping graphs instead of weakening published-revision immutability."

requirements-completed: [PROD-08, PROD-09, UI-03]

coverage:
  - id: D1
    description: Preview validation, publication, and reactivation remain unavailable until every revision mapping page is collected.
    requirement: PROD-08
    verification:
      - kind: unit
        ref: frontend/src/features/admin/previews/ProductPreviewPage.test.tsx#0/1/50/51 terminal cursor matrix
        status: pass
      - kind: e2e
        ref: frontend/e2e/admin-configuration.spec.ts#51st mapping preview readiness consumes terminal cursor before lifecycle authority
        status: pass
    human_judgment: false
  - id: D2
    description: A failed second page exposes 50 loaded mappings and exact retry while producing no duplicate row, preview batch, or lifecycle request.
    requirement: UI-03
    verification:
      - kind: unit
        ref: frontend/src/features/admin/previews/ProductPreviewPage.test.tsx#page-two failure and retry without duplicates
        status: pass
      - kind: e2e
        ref: npx playwright test e2e/admin-configuration.spec.ts --grep "51st mapping preview readiness"
        status: pass
    human_judgment: false
  - id: D3
    description: Mapping 51 participates in backend-current confirmation for candidate publication and in published active readiness for exact reactivation.
    requirement: PROD-09
    verification:
      - kind: integration
        ref: backend/tests/integration/test_product_publication.py and backend/tests/integration/test_preview_jobs.py
        status: pass
      - kind: e2e
        ref: frontend/e2e/admin-configuration.spec.ts#candidate 409-to-200 and active blocked-to-exact-reactivation paths
        status: pass
    human_judgment: false

duration: 23min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 34: Terminal Mapping Cursor Readiness Summary

**Preview and lifecycle authority now consumes the complete ordered revision mapping graph, including boundary item 51, through the existing cursor collection.**

## Performance

- **Duration:** 23 min
- **Started:** 2026-08-29T21:14:24Z
- **Completed:** 2026-08-29T21:37:15Z
- **Tasks:** 2
- **Files modified:** 3 implementation/test files plus this summary

## Accomplishments

- Reuses `useCursorCollection` as the single mapping accumulator, automatically consuming opaque cursors until terminal `next_cursor` absence while preserving API order and stable-ID deduplication.
- Keeps Run validation, candidate publication, and active reactivation disabled for partial collections; a page-two error reports the exact loaded count and resumes the failed cursor without duplicating mappings.
- Keys mapping collection and lifecycle completion to the current product/revision generation, so late pages, polls, or publication results from a superseded generation are ignored.
- Proves 0/1/50/51 component boundaries and a real 51-mapping backend journey where the last mapping changes candidate publication from 409 to 200 and controls active reactivation eligibility.

## Task Commits

Each TDD gate and completed task was committed atomically:

1. **Task 1 RED: terminal mapping cursor contract** - `12abf3b` (test)
2. **Task 1 GREEN: complete mapping readiness** - `6bfdb3f` (feat)
3. **Task 2 harness/specification RED: real-backend boundary journey** - `3db4d92` (test)
4. **Task 2 GREEN: self-seeded lifecycle boundary proof** - `6ba9191` (feat)
5. **Full-suite compatibility fix: preserve generated mapping call shape** - `79cb3ce` (fix)

Plan metadata is committed separately with this summary and synchronized planning state.

## Files Created/Modified

- `frontend/src/features/admin/previews/ProductPreviewPage.tsx` - Loads revision mappings through the shared cursor collector and derives every readiness/lifecycle action from terminal collection state.
- `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx` - Covers 0/1/50/51 pages, exact cursor consumption, partial retry, deduplication, candidate/active blockers, and stale page/poll generations.
- `frontend/e2e/admin-configuration.spec.ts` - Self-seeds candidate and published 51-mapping graphs and proves retry, request-negative partial state, backend eligibility, and exact reactivation.
- `.planning/phases/02-admin-configuration/02-34-SUMMARY.md` - Records implementation, TDD, verification, and state handoff evidence.

## Decisions Made

None - the plan composed the existing cursor hook, generated revision mapping operation, and candidate/active lifecycle paths as specified.

## TDD Gate Compliance

- **Task 1 behavioral RED:** `12abf3b` ran 20 focused tests with 16 passing and four intended failures: missing second cursor for 51 mappings, missing partial/retry state, premature first-page reactivation readiness, and missing superseded-product page isolation.
- **Task 1 GREEN:** `6bfdb3f` passed 21/21 focused tests, including a late-poll generation proof; the tracer feedback rerun also passed 21/21.
- **Task 2 harness/specification RED:** `3db4d92` failed 1/1 because `E2E_MAPPING_51_PRODUCT_ID` was deliberately absent. This was a fixture specification RED, not an application-behavior RED.
- **Task 2 GREEN:** `6ba9191` replaced the placeholder with an isolated self-seed and passed the named current-source real-backend journey 1/1.

## Verification

- Focused preview component command: **21 passed**.
- Full frontend Vitest suite: **229 passed** across 20 files.
- Named current-source real-backend Playwright journey: **1 passed** after the final compatibility fix.
- Relevant backend publication, preview, and admin product tests: **105 passed**.
- Frontend typecheck, ESLint, Prettier check, production build, and `api:check`: **passed**.
- Real-backend request assertions: candidate `[null, cursor, cursor]` across one injected page-two failure and exact retry; blocked/ready active graphs each `[null, cursor]`; exactly one final browser reactivation POST.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved the established generated mapping client call contract**

- **Found during:** Overall full frontend verification
- **Issue:** Forwarding the cursor hook's abort signal widened the generated SDK mock call and broke the existing route-level integration contract, although generation guards already supplied the required stale-response isolation.
- **Fix:** Kept stale page rejection in `useCursorCollection` query/generation identity and stopped forwarding the unnecessary signal into the generated request.
- **Files modified:** `frontend/src/features/admin/previews/ProductPreviewPage.tsx`, `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx`
- **Verification:** Focused 21/21 and full frontend 229/229.
- **Committed in:** `79cb3ce`

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** The fix preserves all terminal-cursor and stale-generation requirements without expanding scope.

## Issues Encountered

- The first GREEN browser attempt used a relative `page.request` lifecycle URL, which resolved against the production Vite origin and returned 404. The journey now derives the real backend origin from the loaded Product response.
- The next fixture attempt removed both layout and confirmation at mapping 51, correctly producing `layout_required`. The final candidate fixture preserves the selected layout and removes only confirmation, isolating the intended `preview_confirmation_required` transition; the blocked published fixture remains representable through the existing selected-layout projection.
- Both current-source browser runs used uniquely named, head-migrated PostgreSQL/Redis containers plus local backend and production frontend processes. Every temporary process/container and its isolated database was removed and verified absent after each final run.

## Known Stubs

None.

## User Setup Required

None - no dependency or external service configuration is required.

## Next Phase Readiness

- CR-08/G4 is closed with component, real-backend browser, and backend authority evidence at the 50/51 boundary.
- The next gap-closure plan can rely on terminal mapping readiness and exact partial-page recovery.
- No blockers remain.

## Self-Check: PASSED

- All three implementation/test files and this summary exist.
- All five task/TDD commits are present in git history.
- Every recorded verification command completed successfully on the final code.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
