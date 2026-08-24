---
phase: 01-platform-foundation
plan: 12
subsystem: authentication-ui
tags: [react-router, react-hook-form, shadcn, accessibility, tdd]

requires:
  - phase: 01-platform-foundation/01-09
    provides: Generated login/password-change API actions and in-memory session authority
  - phase: 01-platform-foundation/01-10
    provides: Project-owned modern shadcn form, input, button, alert, and skeleton primitives
  - phase: 01-platform-foundation/01-11
    provides: Approved Phase 1 visual theme and focus treatment
provides:
  - Fail-closed routes for checking, signed-out, password-change-only, and authenticated session states
  - Accessible non-enumerating internal login form
  - Accessible mandatory password-replacement form with validation and duplicate-submit protection
  - Production bootstrap through the server-backed session state machine
affects: [authenticated-shell, dashboard, phase-1-gauntlet]

actuals:
  tokens: 10271
  tasks: 2
  commits: 48

tech-stack:
  added:
    - react-router-dom@7.18.2
    - "@testing-library/user-event@14.6.6 (development)"
  patterns:
    - Declarative route containment selected only by the discriminated server-backed session state
    - React Hook Form over project-owned modern shadcn primitives
    - Generic credential errors and one in-flight action per authentication form

key-files:
  created:
    - frontend/src/router.tsx
    - frontend/src/router.test.tsx
    - frontend/src/features/auth/LoginPage.tsx
    - frontend/src/features/auth/LoginPage.test.tsx
    - frontend/src/features/auth/ChangePasswordPage.tsx
    - frontend/src/features/auth/ChangePasswordPage.test.tsx
    - frontend/src/main.test.ts
  modified:
    - frontend/src/features/auth/session.tsx
    - frontend/src/features/auth/session.test.tsx
    - frontend/src/main.tsx
    - frontend/package.json
    - frontend/package-lock.json

key-decisions:
  - "Route authority is a pure projection of SessionState; URLs, roles, and client-controlled values never grant access."
  - "Generated-client failures become sanitized rejected session actions so pages can announce one generic response without backend diagnostics."
  - "A successful forced password change clears authority and routes to signed-out login, matching the existing session contract."

patterns-established:
  - "Route guard matrix: every non-approved direct URL is replaced with the sole route allowed by the current session state."
  - "Authentication form boundary: visible labels, programmatic associations, exact copy, logical tab order, aria-busy disabled submission, and no credential storage/logging."

requirements-completed: [PLAT-02, AUTH-01, UI-01]

coverage:
  - id: D1
    description: "Checking, signed-out, restricted, and authenticated authority can render only their approved routes, including direct navigation."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "frontend/src/router.test.tsx#session routes"
        status: pass
      - kind: integration
        ref: "frontend/src/router.test.tsx#returns a successful required-password change to signed-out login"
        status: pass
    human_judgment: false
  - id: D2
    description: "The login form is labelled, keyboard-operable, non-enumerating, session-backed, and duplicate-submit safe."
    requirement: AUTH-01
    verification:
      - kind: unit
        ref: "frontend/src/features/auth/LoginPage.test.tsx#login page"
        status: pass
      - kind: other
        ref: "Known-bad email-label and keyboard-order accessibility controls"
        status: pass
    human_judgment: false
  - id: D3
    description: "Temporary credentials are confined to an accessible password-replacement form whose requirements, failures, and completion are announced safely."
    requirement: UI-01
    verification:
      - kind: unit
        ref: "frontend/src/features/auth/ChangePasswordPage.test.tsx#required password change page"
        status: pass
      - kind: integration
        ref: "frontend/src/features/auth/session.test.tsx#failed password replacement remains restricted"
        status: pass
      - kind: other
        ref: "Known-bad alert-role and keyboard-order accessibility controls"
        status: pass
    human_judgment: false

duration: 24min
completed: 2026-08-24
status: complete
---

# Phase 1 Plan 12: Login and Mandatory Password Change Summary

**Server-backed session routing now confines users to accessible login, mandatory password replacement, or ordinary application routes with no direct-navigation bypass.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-08-24T19:36:25Z
- **Completed:** 2026-08-24T20:00:12Z
- **Tasks:** 2
- **Files modified:** 12
- **TDD commits:** 48

## Accomplishments

- Added an exhaustive route-state/direct-navigation matrix. Signed-out authority reaches only `/login`, temporary authority reaches only `/change-password`, authenticated authority reaches `/`, and session checking renders the approved live loading state.
- Added the exact login and forced-password-change copy with project-owned modern shadcn components, programmatic associations, logical keyboard order, generic error feedback, and disabled/`aria-busy` one-in-flight submission.
- Connected both forms only to existing session actions, converted generated-client failures into diagnostic-free action rejection, and proved the complete login → restricted change → signed-out login transition.
- Replaced the unprotected production `App` entry with `BrowserRouter` → `SessionProvider` → `AppRouter`, so the tested authority boundary is the actual application bootstrap.

## Per-Behavior TDD Commits

### Task 1: Route session states without bypass

1. Session checking: RED `dc6ed78`; GREEN `e6b1a5c`.
2. Signed-out `/login`: RED `41ac8ed`; GREEN `f57a617`.
3. Signed-out direct-navigation containment: RED `56d55e8`; GREEN `c3a6491`.
4. Restricted `/change-password`: RED `ad5f0b0`; GREEN `acd80c5`.
5. Restricted direct-navigation matrix: RED `34709a3`; GREEN `a40cb25`.
6. Authenticated `/`: RED `0990b1e`; GREEN `e31b202`.
7. Authenticated redirect matrix: RED `a982942`; GREEN `5d00991`.
8. Complete login/change/return transition: RED `e10bdef`; GREEN `2252656`.
9. Production session/router bootstrap: RED `445ed1b`; GREEN `23363bc`.

### Task 2: Submit accessible login and change-password forms

1. Login structure/copy/labels: RED `6600dc9`; GREEN `3e717f2`.
2. Login session submission: RED `aad15b6`; GREEN `45d1bc4`.
3. Non-enumerating login error: RED `c058ef6`; GREEN `7d16989`.
4. Invalid-login session signal: RED `d2b4068`; GREEN `c4ee00c`.
5. Login duplicate-submit guard: RED `02bf4db`; GREEN `f4340ab`.
6. Login keyboard-order armor: `a990efc`, proved by a killed throwaway mutant.
7. Password form structure/copy/labels: RED `2420ee7`; GREEN `d451f8b`.
8. Password length announcement/association: RED `b514011`; GREEN `11c7450`.
9. Confirmation mismatch: RED `f77c3d9`; GREEN `95f4fa1`.
10. Current-password reuse rejection: RED `ed7b4af`; GREEN `6dbdfbe`.
11. Restricted session submission: RED `07ec229`; GREEN `5016def`.
12. Sanitized password-change error: RED `b63d4ad`; GREEN `5776843`.
13. Rejected password-action session signal: RED `5d31853`; GREEN `f57fdb9`.
14. Password-change duplicate-submit guard: RED `a72e549`; GREEN `7cbbd65`.
15. Password-change keyboard-order armor: `161f9f0`, proved by a killed throwaway mutant.

### Approved dependency boundary

- `ea9f320` adds the exact runtime router; `6cb5364` adds the exact user-event test driver.
- Authorization was not inferred. `01-SPEC.md:85` explicitly allowlists `react-router-dom`; `01-SPEC.md:100` explicitly allowlists `@testing-library/user-event`; `01-RESEARCH.md:148` audits `react-router-dom` at **7.18.2** from `github.com/remix-run/react-router`; and `01-RESEARCH.md:177` audits `@testing-library/user-event` at **14.6.6** from `github.com/testing-library/user-event`.
- Approval provenance is the append-only `01-SPEC.md:467` record of the user's exact statement: “Approvo la SPEC Phase 1 e l’audit delle dipendenze.” It explicitly authorizes the audited grouped dependency installations and TDD execution loop.
- Registry/lock evidence: `react-router-dom-7.18.2.tgz` is locked with `sha512-AIKJ/jgGlFb3EbfCXk5Gzshiwt+l3mqbCrNjmEWMMjqQxNJ3svBa6bgzFyCC2Sw3RA0VWF1kg3uQf2OFhxb8hw==`; `user-event-14.6.6.tgz` is locked with `sha512-Jbs9FpkkIDw8FgSc6kOVsOv8JuuqGAL7J4X1oot77JxAoDlkNn2GRkd0aYRVuQ+pVQAiHWVkE4rX/dkF5fBiCw==`. Both resolve from `https://registry.npmjs.org/` and their official source/publisher rows match the approved audit.

## Files Created/Modified

- `frontend/src/router.tsx` / `router.test.tsx` — State-selected routes, wildcard containment, approved loading state, full authority matrix, and integrated transition.
- `frontend/src/features/auth/LoginPage.tsx` / `LoginPage.test.tsx` — Exact accessible login behavior and user-event evidence.
- `frontend/src/features/auth/ChangePasswordPage.tsx` / `ChangePasswordPage.test.tsx` — Exact accessible password replacement, validation, action feedback, and user-event evidence.
- `frontend/src/features/auth/session.tsx` / `session.test.tsx` — Diagnostic-free rejection for failed generated login/password actions while retaining the authoritative session state.
- `frontend/src/main.tsx` / `main.test.ts` — Protected production bootstrap and drift contract.
- `frontend/package.json` / `package-lock.json` — Exact approved direct dependencies plus registry integrity.

## Decisions Made

- Used the approved built-in declarative React Router seam and no additional router package or client-side authority store.
- Kept state selection exhaustive over the existing discriminated `SessionState`; the router does not decode tokens, parse roles, or inspect any persistent browser value.
- Preserved generic failure copy at the UI boundary for validation-shaped, generated-client, and network failures. No backend reason or account-existence signal reaches the user.
- Kept passwords inside uncontrolled browser form/session-action lifetimes only; no log, browser storage, URL, or application state receives credential values.

## TDD, Accessibility, and Threat Evidence

- Every user-observable behavior was collected RED before its minimal GREEN. The route matrix grew one authority/navigation behavior at a time; form structure, submission, error, duplicate, and transition behaviors followed separately.
- User-event drives actual typing, clicks, and Tab navigation. Login order is Email → Password → submit; password-change order is Current → New → Confirm → submit.
- Four bounded negative controls were killed: login email `htmlFor` disconnected; login keyboard target removed; password validation `role=alert` removed; new-password keyboard target removed. Every source mutant was restored before the fresh final suite.
- **T-12-01:** high-severity elevation is mitigated by server-derived session state and wildcard route replacement. **T-12-02:** high-severity disclosure is mitigated by generic feedback plus the existing credential storage guard. **T-12-03:** medium denial-of-service is mitigated by disabled/`aria-busy` one-in-flight buttons, with deferred-promise duplicate-click tests.
- `old-coder-api` is not applicable: no HTTP path, method, schema, status, authorization dependency, or generated contract changed. Forms call the existing generated session actions.

## Final Gate Evidence

- Focused auth/router/bootstrap: **4 files, 27 tests passed**.
- Final full frontend suite: **9 files, 51 tests passed**.
- Randomized suite health, seed `1212`: **9 files, 51 tests passed**.
- Credential storage/static guard: **1 file, 3 tests passed**.
- TypeScript: 0 errors.
- ESLint: 0 errors and 0 warnings.
- Production build: Vite completed successfully; 154 modules transformed, CSS 47.92 kB and JS 317.82 kB before gzip.
- Generated API drift check: passed with no OpenAPI or client diff.
- Dependency audit: 0 vulnerabilities at `high` threshold (0 vulnerabilities total).
- Repository hygiene: `git diff --check` clean; only the pre-existing untracked `.planning/milestone.lock` remains and was not modified or staged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed the two already-approved missing direct dependencies**

- **Found during:** Task 1 router and Task 2 user-event setup.
- **Issue:** The approved SPEC required React Router and user-event, but the scaffold had not installed either direct dependency yet.
- **Fix:** Rechecked the exact SPEC/audit rows and approval provenance, then installed only the pinned versions documented above. No lifecycle-script approval or new package was inferred.
- **Files modified:** `frontend/package.json`, `frontend/package-lock.json`.
- **Verification:** Focused/full/shuffled tests, build, registry lock integrity, and `npm audit` pass.
- **Committed in:** `ea9f320`, `6cb5364`.

**2. [Rule 2 - Missing Critical] Made generated-client failures observable only as sanitized session-action rejection**

- **Found during:** Task 2 error behavior.
- **Issue:** The existing session actions consumed generated-client error results without rejecting, so forms could neither announce a generic failure nor distinguish success while preserving authority.
- **Fix:** Reject with the fixed diagnostic-free `Session action failed` boundary and retain signed-out/restricted state; tests prove backend diagnostics are absent.
- **Files modified:** `frontend/src/features/auth/session.tsx`, `frontend/src/features/auth/session.test.tsx`.
- **Verification:** Session, form, integrated route, storage, and full suites pass.
- **Committed in:** `c4ee00c`, `f57fdb9`.

**3. [Rule 3 - Blocking] Wired the tested guard into the production entry point**

- **Found during:** Task 1 integration completion.
- **Issue:** The six-file plan surface did not include `main.tsx`; leaving its direct `<App />` render would bypass the implemented router in the shipped bundle.
- **Fix:** Added a failing bootstrap contract, then mounted `BrowserRouter` → `SessionProvider` → `AppRouter` in production.
- **Files modified:** `frontend/src/main.tsx`, `frontend/src/main.test.ts`.
- **Verification:** Bootstrap/route integration, full tests, typecheck, lint, and production build pass.
- **Committed in:** `445ed1b`, `23363bc`.

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 missing critical)
**Impact on plan:** All changes were required to make the approved auth behavior real and failure-safe; no new HTTP surface, authority source, credential persistence, or feature scope was introduced.

## Issues Encountered

- npm reported the already-known optional `fsevents@2.3.3` script as not allowed/executed; it remains an optional locked transitive and every required command passes.
- No implementation blocker or human checkpoint remained after confirming the exact pre-approved dependency rows.

## Known Stubs

None.

## User Setup Required

None - no external identity provider, secret, browser storage, or manual route configuration is required.

## Next Phase Readiness

- Plan 01-13 can replace the authenticated ordinary route body with the approved dashboard shell; auth containment and production bootstrap are already in place.
- Plan 01-14 can run the final frontend/backend evidence gauntlet over this surface without adding auth behavior.
- No blocker remains.

## Self-Check: PASSED

- All required artifacts exist and no stub remains.
- All 48 implementation/TDD commits exist on `codex/phase-1-platform-foundation`.
- The final source state passes focused/full/shuffled tests, storage guard, typecheck, lint, production build, API drift, dependency audit, and known-bad accessibility controls.
- `.planning/milestone.lock` remains untouched and uncommitted.

---
*Phase: 01-platform-foundation*
*Completed: 2026-08-24*

## PLAN COMPLETE
