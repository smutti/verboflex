---
phase: 02-admin-configuration
plan: 17
subsystem: frontend-admin-users
tags: [react, shadcn, accessibility, secrets, generated-client, vitest, stryker, tdd]

requires:
  - phase: 02-15
    provides: Canonical generated Phase 2 administrator API operations and types
  - phase: 02-16
    provides: Guarded responsive administrator route shell and server-projected identity
provides:
  - Complete administrator user list, filtering, cursor pagination, add, and edit workflow
  - Named reset, deactivate, and reactivate confirmations backed only by generated operations
  - One-time temporary-password boundary with explicit acknowledgement and synchronous state clearing
affects: [02-18, 02-19, 02-20, frontend-admin-ui, authentication]

actuals:
  tokens: 25606
  tasks: 2
  commits: 17

tech-stack:
  added: []
  patterns:
    - Official shadcn primitives remain project-owned while generated API types and operations own the wire boundary
    - One-time credentials live only in local component state and are synchronously cleared before acknowledgement closes the dialog
    - User rows change only from backend responses; pending, conflict, and rejected requests never project optimistic authority

key-files:
  created:
    - frontend/src/components/ui/alert-dialog.tsx
    - frontend/src/components/ui/checkbox.tsx
    - frontend/src/components/ui/dialog.tsx
    - frontend/src/components/ui/select.tsx
    - frontend/src/components/ui/table.tsx
    - frontend/src/features/admin/users/TemporaryPasswordDialog.tsx
    - frontend/src/features/admin/users/UserDialog.tsx
    - frontend/src/features/admin/users/UsersPage.tsx
    - frontend/src/features/admin/users/UsersPage.test.tsx
    - frontend/src/features/admin/users/userRoles.ts
  modified:
    - frontend/src/router.tsx

key-decisions:
  - "Keep generated administrator user operations authoritative; the UI neither defines handwritten wire types nor infers successful state before a backend response."
  - "Contain temporary plaintext in TemporaryPasswordDialog local state, permit clipboard access only from an explicit click, and synchronously clear the secret before notifying the owner to close."
  - "Use named confirmation dialogs for reset, deactivate, and reactivate; preserve the owning dialog, row, and focus when the server denies authority."

patterns-established:
  - "All user mutations use bounded pending and error vocabularies, disable duplicate submission, and replace displayed data only with returned server records."
  - "Administrator role self-removal is visibly disabled in the UI while backend authorization remains the security boundary."

requirements-completed: [AUTH-02, AUTH-03, UI-03]

coverage:
  - id: D1
    description: Administrators can list, filter, paginate, add, and edit internal users without client-side ordering or optimistic values.
    requirement: UI-03
    verification:
      - kind: unit
        ref: frontend/src/features/admin/users/UsersPage.test.tsx#preserves API order and cursor pagination without client re-sorting or de-duplicating
        status: pass
      - kind: unit
        ref: frontend/src/features/admin/users/UsersPage.test.tsx#updates a row only from the backend response
        status: pass
    human_judgment: false
  - id: D2
    description: User creation, reset, and reactivation expose plaintext only in the exact non-dismissible one-time acknowledgement dialog.
    requirement: AUTH-02
    verification:
      - kind: unit
        ref: frontend/src/features/admin/users/UsersPage.test.tsx#reveals a created credential only in a non-dismissible acknowledgement dialog
        status: pass
      - kind: unit
        ref: frontend/src/features/admin/users/UsersPage.test.tsx#zeroes the temporary password before notifying its acknowledgement owner
        status: pass
    human_judgment: false
  - id: D3
    description: Clipboard, live-region, URL, storage, request-log, and later-render paths never receive temporary plaintext implicitly.
    requirement: AUTH-03
    verification:
      - kind: unit
        ref: frontend/src/features/admin/users/UsersPage.test.tsx#reveals a created credential only in a non-dismissible acknowledgement dialog
        status: pass
      - kind: unit
        ref: frontend/src/features/auth/storage-guard.test.ts#browser credential persistence guard
        status: pass
    human_judgment: false
  - id: D4
    description: Reset, deactivate, and reactivate require named confirmation and preserve server-authoritative row/dialog state on denial.
    requirement: UI-03
    verification:
      - kind: unit
        ref: frontend/src/features/admin/users/UsersPage.test.tsx#Reset password requires named confirmation and opens the one-time credential boundary
        status: pass
      - kind: unit
        ref: frontend/src/features/admin/users/UsersPage.test.tsx#keeps the named deactivate dialog and active row intact on server denial
        status: pass
    human_judgment: false

duration: 42min
completed: 2026-08-28
status: complete
---

# Phase 02 Plan 17: Secret-Safe Administrator Users Summary

**The guarded Users route now provides server-authoritative internal-user administration and a one-time temporary-password boundary that clears plaintext before explicit acknowledgement closes it.**

## Performance

- **Active duration:** 42 min
- **Started:** 2026-08-28T09:49:31Z
- **Completed:** 2026-08-28T10:31:21Z
- **Tasks:** 2
- **Files changed:** 11 production/test files

## Accomplishments

- Replaced the administrator Users placeholder with responsive loading, bounded error, empty, filtered, populated, and cursor-pagination states that preserve API order.
- Added accessible Add/Edit dialogs with exact additive roles, required-field focus, immutable email, self-admin protection, duplicate-submit prevention, and server-owned success values.
- Added named reset, deactivate, and reactivate confirmations with sanitized denial copy, focus restoration, and no optimistic row changes.
- Added the exact `Temporary password created` boundary: no outside/Escape dismissal, explicit user-gesture copy, secret-free live status, and `I saved the password` zeroization before close.
- Installed only the official project-owned shadcn primitives required by the plan; all package and registry manifests remained byte-identical.

## Task Commits

1. **Task 1: List, add, and edit one user through generated operations**
   - `e394a70` — RED administrator Users tracer
   - `81973f9` — server-owned list order proof
   - `bd963a0` — official component test harness support
   - `71dfa0b` — generated-operation fixture typing
   - `276c84b` — GREEN Users route, list, add, and edit implementation
2. **Task 2: Complete one-time credential, reset, deactivate, and reactivate UX**
   - `0063d9b` — RED lifecycle and secret-containment contracts
   - `e2d3538` — GREEN secure lifecycle controls and one-time dialog
   - `2718596` — lifecycle focus restoration and sanitized failure paths
   - `e62c109` — explicit lifecycle result branches
   - `db1c837` — zeroization ordering and lifecycle mutation proofs
   - `f219de8` — exhaustive lifecycle outcome vocabulary
   - `f958adc` — retry cleanup and duplicate-safety proof
   - `a853436` — synchronous secret-clear callback refactor
   - `73b3ff5` — mutation-safe empty-secret construction
   - `1010a15` — classified Stryker/React serialization limitation
   - `b09613e` — pending-contract and keyed edit invariant refactor
   - `714ee61` — full-plan validation, failure, and stale-authority coverage

## Files Created/Modified

- `frontend/src/features/admin/users/UsersPage.tsx` — Full generated-operation Users screen and lifecycle orchestration.
- `frontend/src/features/admin/users/UserDialog.tsx` — Accessible add/edit form with fixed roles, focus ownership, pending, and sanitized errors.
- `frontend/src/features/admin/users/TemporaryPasswordDialog.tsx` — Local-only temporary secret display, user-triggered clipboard, and pre-close zeroization.
- `frontend/src/features/admin/users/UsersPage.test.tsx` — 34 focused behavior, accessibility, negative-secret, authority, and regression tests.
- `frontend/src/features/admin/users/userRoles.ts` — Exact visible labels and create defaults for the generated role vocabulary.
- `frontend/src/components/ui/{alert-dialog,checkbox,dialog,select,table}.tsx` — Official project-owned shadcn primitives.
- `frontend/src/router.tsx` — Connects the guarded administrator route to `UsersPage` with in-memory access authority and current principal ID.

## Decisions Made

- Generated client functions and generated request/response types remain the only HTTP boundary for the page.
- Temporary plaintext is not placed in URL state, browser storage, cache, global state, toast, generic error, request payload, or live-region text.
- Acknowledgement zeroization belongs to `TemporaryPasswordDialog`; `flushSync` makes clearing observable before the parent unmount callback.
- Named lifecycle dialogs remain open and focused on bounded denial; successful visible state is sourced only from the returned user record.

## Verification

- Exact Task 2 and plan command: **34/34 focused Vitest tests passed** on the final source.
- Fresh randomized frontend suite (`--sequence.shuffle --sequence.seed=21717`): **127/127 tests passed**.
- Frontend static/build: TypeScript, ESLint, Prettier, canonical API drift, dependency-tree resolution, and Vite production build passed; **1,959 modules transformed**.
- Full-plan changed handwritten production-line and branch coverage against `e394a70^`: **221/221, 100%**. Only the five official shadcn component sources were excluded from the differential metric.
- Targeted secret/lifecycle mutation proof: **60/60 executed mutants killed, 100%**, with zero survivors, timeouts, no-coverage results, or errors. One `flushSync` call-expression mutant is narrowly ignored because Stryker cannot serialize the React failure; the direct zeroization-ordering test independently proves that removal fails the contract.
- Backend randomized regression with PostgreSQL 18, disposable Redis 7, and a live Celery solo worker: **698/698 tests passed**.
- Focused architecture, reversible migrations, canonical OpenAPI, and live worker smoke: **25/25 passed**.
- Backend static/supply chain: Ruff check/format, MyPy for **81 source files**, `uv lock --check`, `pip-audit`, and the license inventory passed.
- Supply chain and secrets: production `npm audit --omit=dev` reported **0 vulnerabilities**; the audited repository secret policy and its negative control passed. The existing development-only `qs` moderate advisory remains unchanged.
- Real-smoke preflight passed. The previously recorded frontend-container OpenAPI copy defect remains the Phase 2 close gate described below.

## TDD Gate Compliance

- Task 1 began with the RED commit `e394a70`; the unchanged focused command passed after the GREEN implementation in `276c84b`.
- Task 2 began with six new failing lifecycle/secret tests in `0063d9b` while the 11 Task 1 tests stayed green; the unchanged command passed 17/17 after `e2d3538`.
- Refactor and evidence commits retained the identical focused command, ending at 34/34 with complete differential coverage and mutation evidence.
- Both mandatory `test(02-17)` RED commits precede their corresponding `feat(02-17)` GREEN commits.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical regression armor] Closed lifecycle focus, retry, and denial gaps**
- **Found during:** Task 2 changed-line coverage and mutation testing
- **Issue:** Initial behavior tests did not distinguish focus restoration, stale-error removal, generic versus conflict denials, or all server-owned lifecycle outcomes.
- **Fix:** Added bounded negative tests and simplified lifecycle state branches around an exhaustive error vocabulary.
- **Files modified:** `frontend/src/features/admin/users/UsersPage.tsx`, `frontend/src/features/admin/users/UsersPage.test.tsx`, `frontend/src/features/admin/users/TemporaryPasswordDialog.tsx`
- **Commits:** `2718596`, `e62c109`, `db1c837`, `f219de8`, `f958adc`

**2. [Rule 3 - Blocking test-tool issue] Classified Stryker's React `flushSync` serialization crash**
- **Found during:** Task 2 mutation gate
- **Issue:** Removing the synchronous state-clear call made the ordering assertion fail with a React object that Stryker's Vitest runner could not stringify, reporting a runner error instead of a killed mutant.
- **Fix:** Kept synchronous clearing, removed mutable literal/callback instrumentation points, and narrowly ignored only the call-expression mutation with its direct ordering test retained.
- **Files modified:** `frontend/src/features/admin/users/TemporaryPasswordDialog.tsx`
- **Commits:** `a853436`, `73b3ff5`, `1010a15`

**3. [Rule 2 - Missing critical regression armor] Closed whole-plan validation and authority-race coverage**
- **Found during:** Final full-plan differential coverage audit
- **Issue:** Reachable Task 1 paths for required fields, generic failures, cancel, unknown server roles, undefined generated responses, and superseded/unmounted loads lacked explicit proofs.
- **Fix:** Added focused tests, reset the list mock between cases, and aligned two internal branches with the approved pending/keyed-dialog contract.
- **Files modified:** `frontend/src/features/admin/users/UserDialog.tsx`, `frontend/src/features/admin/users/UsersPage.tsx`, `frontend/src/features/admin/users/UsersPage.test.tsx`
- **Commits:** `b09613e`, `714ee61`

## Issues Encountered

- The first full-plan differential coverage audit reported **88%**; reachable validation, failure, cancellation, and stale-authority tests raised the final measure to **100%** without broad exclusions.
- The official `alert-dialog` install initially rewrote the existing Button source mechanically; Prettier restored a byte-identical file, and `package.json`, `package-lock.json`, and `components.json` remained unchanged.
- `tools/real_smoke.sh --browser-only` remains blocked by the pre-existing Plan 02-15 container defect: `docker/frontend.Dockerfile` does not copy `frontend/openapi.json`, so generated-client contract import fails only in the Docker typecheck. It remains recorded in `deferred-items.md` and `.planning/WINDOWS.md` and must be repaired before Phase 2 closes.

## Known Stubs

None. The changed implementation and test files contain no TODO, FIXME, coming-soon copy, skipped test, or unwired data source. The word `placeholder` appears only in the official shadcn Select data-state selector and is not a product stub.

## User Setup Required

None - no external service configuration or dependency change is required.

## Next Phase Readiness

- Plan 02-18 can build product/repository/mapping administration on the same guarded shell and generated-client boundary.
- Plan 02-19 can connect preview/confirmation flows without changing the Users secret boundary.
- The carried frontend-container OpenAPI copy defect does not invalidate Plan 02-17 behavior, but remains an explicit Phase 2 close gate.

## Self-Check: PASSED

- All 12 summary, production, component, test, and route artifacts exist; all 17 task commits are present in repository history.
- The exact plan verification, fresh frontend/backend suites, full-plan coverage, mutation proof, static checks, API drift, build, supply-chain, and audited secret gates passed on the final source state.
- Only the documented pre-existing container smoke defect remains open; `.gsd/`, `.planning/milestone.lock`, and `graphify-out/` were not modified or staged.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-28*
