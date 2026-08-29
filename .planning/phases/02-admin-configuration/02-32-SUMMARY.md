---
phase: 02-admin-configuration
plan: 32
subsystem: admin-ui
tags: [react, typescript, playwright, postgres, product-lifecycle, tdd]

requires:
  - phase: 02-admin-configuration/02-27
    provides: Published Edit draft separation from operational lifecycle actions
  - phase: 02-admin-configuration/02-31
    provides: Read-only revision-scoped mapping API and generated frontend client
  - phase: 02-admin-configuration/02-26
    provides: Backend unchanged-active-revision reactivation authority
provides:
  - Product-first active-only preview loading through the exact active revision mapping route
  - Exact unchanged-active-revision reactivation with no candidate or provider writes
  - Current-source real-backend browser proof for successful and stale-confirmation paths
affects: [phase-02-verification, product-lifecycle, admin-preview]

actuals:
  tokens: 8613
  tasks: 2
  commits: 6

tech-stack:
  added: []
  patterns:
    - Product-first revision selection before revision-scoped dependent reads
    - Published active-only confirmation projection remains read-only in the browser
    - Disposable current-source backend fixtures for lifecycle E2E authority proofs

key-files:
  created:
    - .planning/phases/02-admin-configuration/02-32-SUMMARY.md
  modified:
    - frontend/src/features/admin/previews/ProductPreviewPage.tsx
    - frontend/src/features/admin/previews/ProductPreviewPage.test.tsx
    - frontend/e2e/admin-configuration.spec.ts

key-decisions: []

patterns-established:
  - "Active-only reactivation: load Product, select active_revision only when inactive with no candidate, then read that revision's mappings."
  - "Lifecycle isolation: reactivation sends only active_revision_id and expected_active_version; candidate publication stays on its existing path."
  - "Backend authority: UI projection gates obvious stale state while the POST rechecks the complete current-confirmation predicate."

requirements-completed: [PROD-01, PROD-02, PROD-08, PROD-09, UI-03]

coverage:
  - id: D1
    description: Inactive active-only products reactivate the exact unchanged published revision without creating a candidate.
    requirement: PROD-01
    verification:
      - kind: unit
        ref: frontend/src/features/admin/previews/ProductPreviewPage.test.tsx#active-only reactivation contract
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_product_publication.py and backend/tests/api/test_admin_products.py (41 passed)
        status: pass
    human_judgment: false
  - id: D2
    description: Active-only readiness uses published mapping confirmation projections and blocks missing or stale confirmation without a lifecycle request.
    requirement: PROD-08
    verification:
      - kind: unit
        ref: frontend/src/features/admin/previews/ProductPreviewPage.test.tsx#missing stale and failed confirmation blockers
        status: pass
      - kind: e2e
        ref: frontend/e2e/admin-configuration.spec.ts#unchanged active revision reactivation uses real backend state and blocks stale confirmation
        status: pass
    human_judgment: false
  - id: D3
    description: The browser sends the exact reactivation body and renders the backend-returned active product with the same active revision.
    requirement: UI-03
    verification:
      - kind: e2e
        ref: npx playwright test e2e/admin-configuration.spec.ts --grep "unchanged active revision reactivation" (1 passed)
        status: pass
    human_judgment: false

duration: 26min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 32: Unchanged Active Revision Reactivation Summary

**Product-first active-only preview loading now reaches the backend's exact unchanged-revision reactivation authority with zero candidate or provider writes.**

## Performance

- **Duration:** 26 min
- **Started:** 2026-08-29T20:17:03Z
- **Completed:** 2026-08-29T20:42:32Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Loads Product before mappings, chooses a candidate revision for draft publication and the active revision only for inactive active-only reactivation, then uses the revision-scoped mapping API.
- Projects published active mapping readiness without creating a draft, running candidate validation, reading provider branches, or changing the established candidate publication flow.
- Sends exactly `active_revision_id` and `expected_active_version`, preserves pending/conflict/retry semantics, and renders the backend-returned active product with the same revision identity.
- Proves successful and stale-confirmation paths against an isolated head-migrated PostgreSQL database and current backend source, including a request-negative stale fixture.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: active-only revision and lifecycle contract** - `703f601` (test)
2. **Task 1 GREEN: unchanged active revision reactivation** - `2973b5f` (feat)
3. **Task 1 REFACTOR: published mapping status isolation** - `b71a67e` (refactor)
4. **Task 2 RED: real-backend journey specification/harness** - `7c778f6` (test)
5. **Task 2 GREEN: self-seeded real-backend lifecycle proof** - `bdecb9d` (feat)

Plan metadata is committed separately with this summary and synchronized planning state.

## Files Created/Modified

- `frontend/src/features/admin/previews/ProductPreviewPage.tsx` - Selects the lifecycle revision after Product load, renders read-only published confirmation status, and calls exact reactivation authority.
- `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx` - Covers sequencing, negative requests, readiness blockers, exact body, terminal state, pending, conflict, and retry.
- `frontend/e2e/admin-configuration.spec.ts` - Seeds disposable current/stale published graphs, traces exact admin writes, and preserves prior candidate publication journeys.
- `.planning/phases/02-admin-configuration/02-32-SUMMARY.md` - Records delivery, tests, and TDD evidence.

## Decisions Made

None - followed the locked plan and existing backend/UI contracts as specified.

## TDD Gate Compliance

- **Task 1 behavioral RED:** `703f601` failed 13/13 focused tests against the candidate-only loader and unreachable reactivation action.
- **Task 1 GREEN/REFACTOR:** `2973b5f` and `b71a67e` pass 13/13 focused tests; the tracer feedback rerun also passed 13/13.
- **Task 2 harness/specification RED:** `7c778f6` failed 1/1 because the required real fixture ID was absent. This was explicitly a harness-setup RED; application behavior was already GREEN from Task 1.
- **Task 2 GREEN:** `bdecb9d` self-seeds current and stale published graphs and passes the named current-source real-backend journey 1/1. Existing lifecycle and candidate-publication regressions pass with it, 3/3.

## Verification

- `npm test -- --run src/features/admin/previews/ProductPreviewPage.test.tsx` - 13 passed.
- `npx playwright test e2e/admin-configuration.spec.ts --grep "unchanged active revision reactivation"` - 1 passed against current backend source and isolated PostgreSQL/Redis.
- Lifecycle, Bitbucket/candidate publication, and named reactivation Playwright selection - 3 passed.
- `uv run pytest -q tests/integration/test_product_publication.py tests/api/test_admin_products.py` - 41 passed.
- Frontend typecheck, lint, format check, production build, and `api:check` - passed.

## Deviations from Plan

None - plan behavior and owned-file scope were preserved exactly.

## Issues Encountered

- The already-running shared Compose backend image stopped at migration `0007`, before the current reactivation support stack. Verification used a disposable database migrated through `0010`, an isolated Redis, current backend source, and a production Vite build. The temporary services were stopped, the isolated database was dropped, and the original frontend container was restored healthy on port 8080.
- A development Vite run triggered duplicate session restoration under React Strict Mode. The required browser proof was rerun against the production build, matching deployed React effect semantics.
- The roadmap SDK advanced Plan 32 and the total count but retained the prior gap subtotal; the same metadata update corrected that derived value from 12/18 to 13/18 without a second advance.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CR-06 is closed with unit, backend publication, and real-browser authority evidence.
- Candidate publication and Plan 27 Edit draft separation remain intact.
- No blockers or checkpoints remain.

## Self-Check: PASSED

- All implementation and summary files exist.
- All five task/TDD commits are present in git history.
- Every recorded verification command completed successfully.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
