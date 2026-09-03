---
phase: 02-admin-configuration
plan: 27
subsystem: ui
tags: [react, react-router, playwright, responsive, accessibility, tdd]

requires:
  - phase: 02-admin-configuration/02-25
    provides: Single-candidate clone-on-first-mutation product graph semantics
  - phase: 02-admin-configuration/02-31
    provides: Canonical generated read operations for product and revision mappings
provides:
  - Routed existing-product editing from overview through a deep-linkable five-step wizard
  - Candidate restoration that never fabricates an ID or clones on a semantic no-op
  - Complete 320px pointer and keyboard wizard navigation with dirty-exit protection
  - Real FastAPI and PostgreSQL Playwright proof for published edit, refresh, Back/Forward, and mobile reflow
affects: [admin-configuration-ui, product-publication, product-reactivation, phase-02-verification]

actuals:
  tokens: 10494
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Existing-product routes hydrate effective product and owned revision mappings without mutating server state
    - Active-only products acquire one candidate only through a real changed details PATCH
    - Mobile wizard controls use literal pixel minimums where the project root font size makes rem spacing undersized

key-files:
  created: []
  modified:
    - frontend/src/router.tsx
    - frontend/src/router.test.tsx
    - frontend/src/features/admin/products/ProductWizardPage.tsx
    - frontend/src/features/admin/products/ProductOverviewPage.tsx
    - frontend/src/features/admin/products/ProductConfiguration.test.tsx
    - frontend/e2e/admin-configuration.spec.ts

key-decisions:
  - "Treat edit-route loading as read-only restoration: use the current candidate when present, otherwise show the active graph until a genuinely changed details save asks Plan 25 to create exactly one candidate."
  - "Keep the active revision identity authoritative before publication and compare complete server-returned mapping fingerprints across clone, refresh, and browser history traversal."
  - "Use Playwright ARIA snapshots, keyboard traversal, literal 44px targets, 320px overflow, and 200% reflow assertions with the existing toolchain rather than adding an accessibility dependency."

patterns-established:
  - "Read-before-write edit route: GET product plus GET owned revision mappings never induces candidate creation."
  - "Real-backend browser proof: seed only published graph prerequisites, then observe server-generated product, revision, candidate, and mapping identities through browser responses."

requirements-completed: [PROD-01, PROD-02, PROD-03, PROD-04, PROD-05, PROD-06, PROD-07, PROD-08, PROD-09, UI-03]

coverage:
  - id: D1
    description: "A published product overview opens a deep-linkable existing-product wizard, creates exactly one complete candidate only after a real changed details save, and restores that same candidate across refresh and Back/Forward without changing the active revision."
    requirement: PROD-01
    verification:
      - kind: unit
        ref: "frontend/src/router.test.tsx and frontend/src/features/admin/products/ProductConfiguration.test.tsx (49 passed)"
        status: pass
      - kind: e2e
        ref: "frontend/e2e/admin-configuration.spec.ts#published product edit preserves one complete candidate across refresh"
        status: pass
    human_judgment: false
  - id: D2
    description: "At 320x720 every wizard step is reachable forward and backward by pointer and keyboard with current-step semantics, 44px controls, bounded long text, dirty reload protection, and no horizontal overflow at narrow or 200% reflow widths."
    requirement: UI-03
    verification:
      - kind: unit
        ref: "frontend/src/features/admin/products/ProductConfiguration.test.tsx (mobile navigation and validation assertions)"
        status: pass
      - kind: automated_ui
        ref: "frontend/e2e/admin-configuration.spec.ts#mobile five-step wizard remains reachable at 320 pixels"
        status: pass
    human_judgment: false

duration: 33m
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 27: Routed Published Edit and Complete Mobile Wizard Summary

**Published products now enter a deep-linkable five-step editor that restores one server-owned candidate and remains fully operable by pointer and keyboard at 320px.**

## Performance

- **Duration:** 33m
- **Started:** 2026-08-29T19:08:39Z
- **Completed:** 2026-08-29T19:41:35Z
- **Tasks:** 2
- **Files modified:** 6 implementation and test files
- **Actual estimate scale:** 10,494 tokens (41,975 realized diff characters / 4)

## Accomplishments

- Added `/admin/products/:productId/edit` and an overview `Edit draft` action, with generated-client loading of the effective product and its owned active-or-candidate revision mappings.
- Preserved Plan 25 single-candidate semantics: deep-link and refresh are read-only, an existing candidate is reused, and an active-only product creates one candidate only when details genuinely change.
- Completed mobile steps 1→2→3→4→5 and 5→1 with persistent Back/Next controls, announced invalid repository state, pointer and keyboard operation, long-text wrapping, and literal 44px targets.
- Proved the full route against real FastAPI/PostgreSQL processes, including complete mapping clone equivalence, unchanged active identity, refresh and browser history restoration, dirty reload cancel/confirm, 320px overflow, and 200% reflow.

## Task Commits

The RED/GREEN gates were committed in order for both tasks:

1. **Task 1 RED: routed edit and mobile navigation specification** — `b92c474` (test)
2. **Task 1 GREEN: existing-product route and complete mobile wizard** — `ee778df` (feat)
3. **Task 2 RED: real-browser published edit and mobile journey specification** — `dc04a7e` (test)
4. **Task 2 GREEN: real-backend E2E proof and 44px target correction** — `57b06cf` (test/fix)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 1 RED:** the focused Vitest run had 46 passing tests and exactly 3 intended failures: the edit route fell through to `/admin/users`, the mobile wizard navigation was absent, and overview lacked `Edit draft`.
- **Task 1 GREEN:** the same focused command passed 49/49, with lint and typecheck also passing.
- **Task 2 RED:** the two required named Playwright scenarios failed explicitly because the real-backend journeys had not yet been implemented.
- **Task 2 GREEN:** the final real-process focused command passed 2/2. Intermediate RED-to-GREEN runs additionally exposed and closed the 38.5px control target defect before the final pass.

## Acceptance Evidence

- Required focused Vitest command: **49 passed** across 2 files.
- Required focused real-backend Playwright command: **2 passed** against isolated FastAPI, PostgreSQL, Redis, and production frontend processes.
- Published edit assertion: server-generated candidate ID remained identical across refresh and browser Back/Forward; complete mapping fingerprints matched the published graph; active revision ID never changed; exactly one product PATCH occurred.
- Mobile assertion: steps 1→2→3→4→5→1 passed using both Enter and pointer clicks; ARIA navigation snapshot and current-step copy passed; both controls measured at least 44 CSS pixels.
- Dirty-exit assertion: dismissing `beforeunload` retained the route and unsaved value; accepting it reloaded the route and restored the saved candidate.
- Responsive assertion: no body/document overflow at 320x720 or the 640px/200% reflow equivalent, including intentionally long product, repository, branch, and target values.
- Frontend static/build gates: TypeScript, ESLint, Prettier, and Vite production build passed.
- No generated API file, backend source, schema, candidate ID, layout, or branch behavior was fabricated or changed.

## Files Created/Modified

- `frontend/src/router.tsx` — adds the explicit existing-product edit route.
- `frontend/src/router.test.tsx` — proves the guarded router resolves that route to the wizard.
- `frontend/src/features/admin/products/ProductOverviewPage.tsx` — links overview to the product-specific editor.
- `frontend/src/features/admin/products/ProductWizardPage.tsx` — loads owned server state, preserves one-candidate semantics, completes mobile navigation, and enforces literal 44px controls.
- `frontend/src/features/admin/products/ProductConfiguration.test.tsx` — covers candidate restoration, mutation-only cloning, mobile forward/back navigation, validation, and dirty behavior.
- `frontend/e2e/admin-configuration.spec.ts` — adds the two named real-process published-edit and mobile journeys.

## Decisions Made

- Deep-linking an active-only published product does not manufacture a candidate. The edit page hydrates the immutable active graph, and Plan 25 creates a candidate only after a genuinely mutating details save.
- Once a candidate exists, every deep-link, refresh, and history restoration uses that same server-returned candidate ID; the UI never guesses or fabricates revision identity.
- The overview continues to display the published product name while the candidate may carry changed details, preserving active/candidate identity separation until publication.
- Browser accessibility verification uses the project-owned Playwright stack: ARIA snapshots, focus and Enter activation, current-step semantics, exact target dimensions, narrow overflow, and zoom-equivalent reflow.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Enforced literal 44px mobile navigation targets**
- **Found during:** Task 2 real-browser GREEN verification
- **Issue:** `min-h-11` is rem-based and rendered at 38.5px under the project's root font size, below the locked 44px pointer target.
- **Fix:** Replaced the two rem-derived minimums with `min-h-[44px]`.
- **Files modified:** `frontend/src/features/admin/products/ProductWizardPage.tsx`
- **Verification:** Playwright measures every mobile wizard navigation button at or above 44 CSS pixels; the focused journeys pass 2/2.
- **Committed in:** `57b06cf`

### Contract Clarification

- The plan behavior line could be read as requiring candidate creation during direct edit-route loading. Per the authoritative Plan 25 contract, loading is read-only: an existing candidate is restored, while an active-only product creates exactly one candidate only through a real mutating details save. The E2E seed begins active-only, performs that mutation, then proves the returned candidate survives refresh and Back/Forward. No backend change or semantic no-op clone was introduced.

---

**Total deviations:** 1 auto-fixed Rule 1 bug plus 1 documented contract clarification.
**Impact on plan:** The fix enforces the locked UI target, and the clarification preserves the already-implemented immutable-published-graph and single-candidate invariants without scope expansion.

## Issues Encountered

- The project has no axe-core dependency. The required accessibility and reflow properties were verified through native Playwright ARIA snapshots, semantic locators, keyboard activation, focus, exact target measurement, 320px overflow, and 200% reflow assertions without adding an unplanned package.
- Vite emits the existing advisory that the main JavaScript chunk exceeds 500 kB; the production build succeeds and this plan does not change bundle architecture.

## Authentication Gates

None. The isolated test administrator was bootstrapped and exercised only inside the task-owned real-process verification stack; seeded password material was asserted absent from browser text, URL, history, and web storage.

## Known Stubs

None.

## User Setup Required

None - no external configuration, migration, dependency, or credential change is required.

## Next Phase Readiness

- Published-product editing and all five mobile steps are now reachable from real routes and generated backend contracts.
- Product publication and reactivation retain their preview/confirmation gates, active graph immutability, exact branch semantics, and one-candidate invariant.
- No Plan 02-27 checkpoint, backend expansion, or unresolved blocker remains.

## Self-Check: PASSED

- All six declared implementation/test files and this summary exist.
- Both RED commits precede their corresponding GREEN commits, and all four Plan 02-27 task commits are reachable from the current branch.
- Focused Vitest, real-backend Playwright, typecheck, lint, formatting, production build, accessibility, keyboard, 320px overflow, and 200% reflow verification pass.
- No tracked deletion, skipped test, unrun plan verification, known stub, dependency change, generated-contract drift, backend mutation, fabricated identity, or unmodeled threat surface remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
