---
phase: 02-admin-configuration
plan: 33
subsystem: workspace-ui
tags: [react, typescript, authorization, routing, playwright, tdd]

requires:
  - phase: 02-admin-configuration/02-27
    provides: Separate routed administration panels and shell navigation
  - phase: 02-admin-configuration/02-32
    provides: Current Phase 2 lifecycle and browser verification baseline
provides:
  - Role-aware authenticated Workspace content for every internal role
  - Three bounded administrator-only summary reads gated by the server principal
  - Location-authoritative desktop/mobile navigation and request-negative admin denial proof
affects: [phase-02-verification, authentication, admin-authorization, workspace-navigation]

actuals:
  tokens: 12880
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - Server-principal role projection before generated admin client calls
    - Exact-root current matching alongside nested administration route matching
    - Sheet close lifecycle controls destination-heading focus after mobile navigation

key-files:
  created:
    - frontend/src/features/workspace/WorkspaceOverviewPage.tsx
    - frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx
    - .planning/phases/02-admin-configuration/02-33-SUMMARY.md
  modified:
    - frontend/src/App.tsx
    - frontend/src/App.test.tsx
    - frontend/src/components/layout/AppShell.tsx
    - frontend/src/components/layout/AppShell.test.tsx
    - frontend/src/router.test.tsx
    - frontend/e2e/admin-configuration.spec.ts

key-decisions:
  - "Workspace authorization follows the server-loaded principal directly: every role receives identity/status, while only an explicit admin role mounts the bounded aggregate loader."
  - "Navigation current state comes only from location: Workspace matches exactly `/`, while administration destinations include their nested routes."

patterns-established:
  - "Request-negative role gating: unauthorized roles never mount the component that owns admin client calls."
  - "Bounded summaries: first-page aggregate values are labelled loaded summaries, never exhaustive totals."
  - "Mobile route focus: prevent Sheet trigger restoration only for Workspace selection and focus the mounted destination heading."

requirements-completed: [AUTH-02, AUTH-03, UI-03]

coverage:
  - id: D1
    description: Every authenticated role receives stable server identity, role labels, and ordinary service status; only administrators receive bounded product, draft, user, and Bitbucket summaries.
    requirement: AUTH-03
    verification:
      - kind: unit
        ref: frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx (6 passed)
        status: pass
    human_judgment: false
  - id: D2
    description: Product managers/reviewers, translators, and viewers make zero administrator requests through Workspace errors/retries and direct admin-route denial.
    requirement: AUTH-02
    verification:
      - kind: unit
        ref: frontend/src/router.test.tsx and frontend/src/components/layout/AppShell.test.tsx (44 passed)
        status: pass
      - kind: e2e
        ref: frontend/e2e/admin-configuration.spec.ts#non-admin admin-request denial (3 passed)
        status: pass
    human_judgment: false
  - id: D3
    description: Workspace is a real root link, exactly one destination is current, and mobile selection closes the Sheet and focuses the Workspace heading at 320px.
    requirement: UI-03
    verification:
      - kind: e2e
        ref: frontend/e2e/admin-configuration.spec.ts#role-aware Workspace navigation stays location-authoritative on desktop and mobile
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 33: Role-Aware Workspace Summary

**Every authenticated role now receives a meaningful Workspace while administrator summaries remain bounded, explicitly role-gated, and request-inaccessible to ordinary users.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-08-29T20:50:34Z
- **Completed:** 2026-08-29T21:08:41Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Replaced the shared placeholder with server-derived identity, stable role labels, ordinary system status, and a clear authorized-work projection for all four internal roles.
- Added exactly three administrator-only bounded reads for products/drafts, users, and Bitbucket connection status, with truthful first-page labels, loading/error/retry states, and admin destination links.
- Replaced the inert Workspace control with a real `/` link whose current state is derived from location alongside nested administration routes.
- Proved direct `/admin/*` denial before child loaders and zero administrator requests for product managers/reviewers, translators, and viewers, including ordinary-status failure and retry paths.
- Preserved responsive containment at 320px and made mobile Workspace selection close the Sheet before focusing the destination heading.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: role-aware Workspace request matrix** - `0621c27` (test)
2. **Task 1 GREEN: role-aware Workspace overview** - `1c0bff6` (feat)
3. **Task 2 RED: route authority and request-negative browser contract** - `db8e84c` (test)
4. **Task 2 GREEN: location-authoritative Workspace navigation** - `72fe4a6` (feat)
5. **Compatibility test: authenticated App entry heading** - `f98fa91` (test)

Plan metadata is committed separately with this summary and synchronized planning state.

## Files Created/Modified

- `frontend/src/features/workspace/WorkspaceOverviewPage.tsx` - Renders role-aware identity/status content and owns the admin-only bounded summary loader.
- `frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx` - Covers every role, exact admin requests, populated/loading/error/retry states, and request-negative ordinary paths.
- `frontend/src/App.tsx` - Passes the authenticated session authority into Workspace.
- `frontend/src/App.test.tsx` - Keeps the authenticated entry assertion aligned with the delivered Workspace heading.
- `frontend/src/components/layout/AppShell.tsx` - Provides exact-root Workspace navigation, nested admin matching, and mobile destination focus.
- `frontend/src/components/layout/AppShell.test.tsx` - Covers desktop/mobile current-state, Sheet close/focus, and responsive containment.
- `frontend/src/router.test.tsx` - Covers direct denial for every non-admin role before admin children mount.
- `frontend/e2e/admin-configuration.spec.ts` - Traces zero non-admin admin requests and verifies keyboard/focus/current-state behavior at desktop and 320px.

## Decisions Made

- The server-loaded principal is the only browser role authority; the admin summary component is not mounted for ordinary roles.
- Workspace matches `aria-current="page"` only at the exact root, while each administration destination owns its nested subtree.
- The Sheet's close-auto-focus lifecycle focuses Workspace content only after root selection; Escape and other navigation retain trigger restoration.

## TDD Gate Compliance

- **Task 1 RED:** `0621c27` failed 6/6 focused tests because the placeholder exposed neither role-aware content nor bounded admin summaries.
- **Task 1 GREEN:** `1c0bff6` passed 6/6 focused tests; the tracer feedback rerun also passed 6/6.
- **Task 2 RED:** `db8e84c` produced 6 intended Vitest failures out of 44 and one intended Playwright current-state failure out of four; all three request-negative non-admin browser cases already passed.
- **Task 2 GREEN:** `72fe4a6` passes 44/44 focused Vitest tests and 4/4 named Playwright journeys.

## Verification

- `npm test -- --run src/features/workspace/WorkspaceOverviewPage.test.tsx` - 6 passed.
- `npm test -- --run src/router.test.tsx src/components/layout/AppShell.test.tsx` - 44 passed.
- Combined Plan 33 focused Vitest selection - 50 passed.
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:4173 npx playwright test e2e/admin-configuration.spec.ts --grep "role-aware Workspace|non-admin admin-request denial"` - 4 passed against current source.
- Full frontend Vitest suite - 221 passed across 20 files.
- Frontend typecheck, lint, format check, production build, and generated `api:check` drift gate - passed.
- Keyboard focus, exact-one `aria-current`, Sheet close, 320px containment, and three per-role zero-admin request traces - passed in the named browser journeys.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated the authenticated App entry assertion after retiring the placeholder heading**
- **Found during:** Full frontend verification after Task 2
- **Issue:** `frontend/src/App.test.tsx` still expected the removed `Workspace overview` placeholder and caused the otherwise-green full suite to fail.
- **Fix:** Aligned the existing App entry test with the delivered `Workspace` heading; no production behavior changed.
- **Files modified:** `frontend/src/App.test.tsx`
- **Commit:** `f98fa91`

## Issues Encountered

- Port 8080 was owned by the pre-existing Docker frontend and served stale source during the first browser rerun. All recorded GREEN browser evidence used an isolated current-source Vite server at `127.0.0.1:4173`; it was stopped after verification.
- React Strict Mode issues two development effect probes. The non-admin browser mock therefore fails both initial ordinary-status probes before allowing the explicit user retry, while continuing to trace zero administrator requests.
- The roadmap SDK advanced the total to 34/38 and checked Plan 33 but retained the prior gap subtotal; the same metadata update corrected that derived subtotal from 13/18 to 14/18 without a second plan advance.

## Known Stubs

None.

## User Setup Required

None - no dependency or external-service changes were introduced.

## Next Phase Readiness

- WR-01 and the Workspace role-leak gap are closed for all four internal roles.
- AUTH-02 direct-route denial remains request-negative before admin children or loaders mount.
- No blockers or checkpoints remain.

## Self-Check: PASSED

- All implementation, test, and summary files exist.
- All five task/TDD commits are present in git history in RED-before-GREEN order.
- Every recorded verification command completed successfully.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
