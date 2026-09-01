---
phase: 02-admin-configuration
plan: 45
subsystem: ui
tags: [react, react-router, typescript, vitest, playwright, accessibility]

requires:
  - phase: 02-admin-configuration
    provides: "Plan 02-44 exact preview branch resolution and the current routed admin baseline"
provides:
  - "One application-scoped React Router dirty-form transaction owner"
  - "Router-native product and mapping protection for Link, PUSH, POP, and beforeunload"
  - "Exact mapping draft fingerprints plus desktop and 320px focus-safe browser evidence"
affects: [02-46, admin-navigation, product-configuration, mapping-configuration]

actuals:
  tokens: 16352
  tasks: 3
  commits: 7

tech-stack:
  added: []
  patterns:
    - "Application-scoped dirty-form registry feeding exactly one React Router blocker"
    - "First-pending router transaction capture with single-use proceed/reset authority"
    - "Exact saved-draft fingerprints with set-semantic allowed-target normalization"

key-files:
  created:
    - frontend/src/components/navigation/DirtyFormNavigationGuard.tsx
    - frontend/src/components/navigation/DirtyFormNavigationGuard.test.tsx
  modified:
    - frontend/src/main.tsx
    - frontend/src/router.tsx
    - frontend/src/components/layout/AppShell.tsx
    - frontend/src/features/admin/products/ProductWizardPage.tsx
    - frontend/src/features/admin/mappings/ProductMappingsPage.tsx
    - frontend/e2e/admin-configuration.spec.ts

key-decisions:
  - "Aggregate form IDs in one provider and keep useBlocker exclusively at the application router boundary, including nested product and mapping consumers."
  - "Continue or reset only the first captured React Router transaction; dialog code never reconstructs a destination path."
  - "Mapping dirtiness compares only persisted user-editable fields, sorts and deduplicates allowed targets, and excludes pending topology, loading, version, error, and exact-branch support state."
  - "Keep the mobile Sheet mounted until the authoritative router location commits so cancellation can restore focus to its initiating Link."

patterns-established:
  - "Dirty consumer pattern: register a stable form ID plus an exact saved-versus-current boolean with useDirtyFormNavigationGuard."
  - "Responsive navigation pattern: record intended destination on Link activation and close transient navigation only after location identity matches."

requirements-completed: [UI-03]

coverage:
  - id: D1
    description: "One singleton guard blocks dirty Link, PUSH, and POP transitions, handles beforeunload, and consumes the captured decision exactly once."
    requirement: UI-03
    verification:
      - kind: unit
        ref: "frontend/src/components/navigation/DirtyFormNavigationGuard.test.tsx#router dirty-form transaction contract"
        status: pass
      - kind: integration
        ref: "frontend/src/main.test.ts and frontend/src/router.test.tsx#data-router singleton bootstrap"
        status: pass
    human_judgment: false
  - id: D2
    description: "Dirty product details preserve Name, Description, route, and initiating desktop or mobile focus until explicit discard."
    requirement: UI-03
    verification:
      - kind: integration
        ref: "frontend/src/features/admin/products/ProductConfiguration.test.tsx#routed product dirty-form tests"
        status: pass
      - kind: e2e
        ref: "frontend/e2e/admin-configuration.spec.ts#dirty product and mapping routes require discard before navigation"
        status: pass
    human_judgment: false
  - id: D3
    description: "Direct and separate mapping drafts use exact clean baselines and retain values and Sheet focus across canceled desktop, Back, reload, and 320px navigation."
    requirement: UI-03
    verification:
      - kind: integration
        ref: "frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx#mapping dirty navigation and failure matrix"
        status: pass
      - kind: e2e
        ref: "frontend/e2e/admin-configuration.spec.ts#dirty mobile mapping navigation restores focus after cancel"
        status: pass
    human_judgment: false

duration: 26min
completed: 2026-09-01
status: complete
---

# Phase 02 Plan 45: Router-Native Dirty Form Protection Summary

**A single React Router transaction owner now protects exact product and mapping drafts across shell links, product sections, programmatic navigation, browser history, reload, and the 320px navigation Sheet.**

## Performance

- **Duration:** 26 min
- **Started:** 2026-09-01T15:03:40Z
- **Completed:** 2026-09-01T15:29:53Z
- **Tasks:** 3
- **Files modified:** 13

## Accomplishments

- Replaced the BrowserRouter bootstrap with one stable data router containing one application-scoped dirty registry, one blocker, the exact discard Alert Dialog, and aggregate beforeunload protection.
- Registered product details and exact direct/separate mapping drafts without retaining the post-transition `popstate`/`history.forward` repair path.
- Preserved values and connected-trigger focus after Keep editing or Escape, delayed mobile Sheet closure until route commit, and proved stored-destination isolation plus single-use discard in a real browser.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1 RED: singleton router transaction contract** - `a9ecf19` (`test`)
2. **Task 1 GREEN: shared router dirty-form blocker** - `4ae37c6` (`feat`)
3. **Task 2 RED: routed product and Sheet focus contract** - `7d2a864` (`test`)
4. **Task 2 GREEN: product registration and authoritative Sheet closure** - `8f902b7` (`feat`)
5. **Task 3 RED: mapping and real-browser navigation contract** - `130845a` (`test`)
6. **Task 3 GREEN: exact mapping draft registration** - `d37b271` (`feat`)
7. **Task 3 regression matrix: separate sides and recoverable failures** - `b90d3a4` (`test`)

No optional REFACTOR commit was necessary; the production seams were already isolated and the unchanged focused gates remained green after each GREEN commit.

## Files Created/Modified

- `frontend/src/components/navigation/DirtyFormNavigationGuard.tsx` - Owns the singleton dirty registry, router blocker transaction, exact Alert Dialog, focus restoration, and beforeunload handler.
- `frontend/src/components/navigation/DirtyFormNavigationGuard.test.tsx` - Proves clean/dirty PUSH and POP, Keep editing, Escape, discard-once, stale intent isolation, focus, and beforeunload.
- `frontend/src/main.tsx`, `frontend/src/router.tsx` - Construct and render one browser data router with guard, session authority, and application routes in order.
- `frontend/src/components/layout/AppShell.tsx` - Keeps a mobile navigation destination pending until the router location commits.
- `frontend/src/features/admin/products/ProductWizardPage.tsx` - Registers the saved Name/Description comparison and removes post-navigation history repair.
- `frontend/src/features/admin/mappings/ProductMappingsPage.tsx` - Registers an exact blank or server-returned mapping baseline with normalized target-set semantics.
- `frontend/e2e/admin-configuration.spec.ts` - Exercises product and mapping Links, Back, reload, stale intent, exact decisions, Escape, discard, 320x720 focus, and overflow.
- Six colocated bootstrap, router, shell, product, mapping, and guard test files were adapted to real data routers without weakening their existing authority and race assertions.

## Verification

- Six focused Vitest files — **106 passed**.
- Two named Playwright scenarios — **2 passed** against the rebuilt production frontend image.
- `npm run typecheck` — passed.
- `npm run lint` — passed with zero warnings.
- `npm run build` — passed; the existing Vite chunk-size advisory remains non-blocking.
- Package manifest, lockfile, OpenAPI, backend, Compose, generated client, schema, and migration diffs — none.
- Static prohibition probe found one production `useBlocker` call and no `popstate`, `history.forward`, or `window.confirm` in ProductWizardPage.

## TDD Gate Compliance

- **Task 1 RED:** 6 intended behavioral failures and 1 clean-navigation control pass; dirty Link/PUSH/POP, exact decision UI, focus, and beforeunload were absent. GREEN passed 7/7 guard tests plus bootstrap assertions.
- **Task 2 RED:** 4 intended failures among 84 assertions; Name, Description, Back, and mobile Sheet cancellation bypassed or removed the focus target. GREEN passed the full product/shell/router slice.
- **Task 3 RED:** mapping Vitest produced 3 intended failures with 11 existing tests passing. An isolated image built from RED commit `130845a` also reproduced both named Playwright failures at the missing mapping discard dialog, including mobile. GREEN passed 59 focused unit/integration assertions and both browser scenarios; the final matrix raised the overall focused total to 106.
- RED commits precede their corresponding GREEN commits. No import, syntax, package, or unrelated-suite failure was accepted as a behavioral RED gate.

## Decisions Made

- A dirty consumer supplies state only; the application provider remains the sole owner of router transaction authority and UI decisions.
- The first blocked router transaction captures `proceed`, `reset`, location identity, monotonic token, and connected trigger once; later attempts cannot replace or replay it.
- Mapping fingerprints preserve exact repository and branch strings while applying set semantics only to allowed targets.
- Canceling topology is clean because pending choice is presentation state; confirming it is dirty because it clears persisted mapping selections.

## Deviations from Plan

None - plan executed within the declared frontend-only scope. The additional post-GREEN regression commit strengthens the planned direct/separate failure matrix without changing production behavior.

## Issues Encountered

- The local port 8080 initially served a stale frontend image. The frontend image was rebuilt without changing dependencies or configuration, after which the focused browser tests exercised the current data-router implementation.
- The first Back assertion used a cross-document `page.goto` history entry. It was corrected to create same-document history through the visible ProductDetailLayout `Mappings` Link, matching the router-owned POP contract.

## Known Stubs

None. Existing Select placeholder copy is functional form guidance and does not represent unwired data or deferred behavior.

## User Setup Required

None - no external service configuration or credential change is required.

## Next Phase Readiness

- CR-15 is behaviorally closed with ordered RED/GREEN commits, exact UI copy, value/focus preservation, one-use transactions, and responsive browser evidence.
- Plan 02-46 can perform the structured semantic audit, fresh review, and independent Phase 2 verifier closeout. WR-03 through WR-08 remain outside this plan and are not claimed closed here.

## Self-Check: PASSED

- All 13 implementation/test paths and this summary exist.
- Commits `a9ecf19`, `4ae37c6`, `7d2a864`, `8f902b7`, `130845a`, `d37b271`, and `b90d3a4` are present in repository history.
- Coverage evidence is green, no prohibited scope changed, and no goal-blocking stub remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-09-01*
