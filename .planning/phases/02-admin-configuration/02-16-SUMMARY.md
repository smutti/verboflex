---
phase: 02-admin-configuration
plan: 16
subsystem: frontend-admin-shell
tags: [react, react-router, shadcn, accessibility, responsive, vitest, stryker, tdd]

requires:
  - phase: 02-15
    provides: Canonical generated Phase 2 administrator API boundary
  - phase: 01-12
    provides: Authenticated application shell and server-authoritative session projection
provides:
  - Server-role-projected Administration navigation shared by desktop Sidebar and mobile Sheet
  - Fail-closed administrator loading, error, and access-denied route states with no protected-content flash
  - Reusable URL-backed product detail navigation in exact Overview, Repositories, Mappings, Preview order
affects: [02-17, 02-18, 02-19, 02-20, frontend-admin-ui]

actuals:
  tokens: 9335
  tasks: 2
  commits: 17

tech-stack:
  added: []
  patterns:
    - Server-loaded session roles project navigation visibility while backend authorization remains authoritative
    - Responsive navigation owns one destination model rendered through desktop Sidebar and mobile Sheet
    - Product detail section identity is derived from guarded route params and the current URL

key-files:
  created:
    - frontend/src/features/admin/AdminAccessDenied.tsx
    - frontend/src/features/admin/products/ProductDetailLayout.tsx
  modified:
    - frontend/src/router.tsx
    - frontend/src/router.test.tsx
    - frontend/src/components/layout/AppShell.tsx
    - frontend/src/components/layout/AppShell.test.tsx

key-decisions:
  - "Project Administration visibility only from SessionState.principal.roles while treating every UI role check as navigation projection, never mutation authority."
  - "Use one shared destination definition for exact Products, Users, and Bitbucket navigation across the desktop Sidebar and mobile Sheet."
  - "Keep product detail navigation URL-backed in exact Overview, Repositories, Mappings, Preview order; feature page data remains deferred to Plans 18 and 19."

patterns-established:
  - "Protected route states mount administrator content only after role projection and a ready route state; loading, error, and denial remain visible and bounded."
  - "Responsive shell containment is local: min-width reset, overflow clipping, break-anywhere labels, a 32px mobile inset, and reduced-motion overrides."

requirements-completed: [UI-03]

coverage:
  - id: D1
    description: Authenticated administrators see one shared Administration group and non-admin users see none.
    requirement: UI-03
    verification:
      - kind: unit
        ref: frontend/src/components/layout/AppShell.test.tsx#shows one desktop Administration group for admins and opens Users
        status: pass
      - kind: unit
        ref: frontend/src/components/layout/AppShell.test.tsx#omits Administration from desktop and mobile navigation for non-admins
        status: pass
    human_judgment: false
  - id: D2
    description: Direct administrator navigation fails closed and loading, error, and denied states never mount protected content.
    requirement: UI-03
    verification:
      - kind: unit
        ref: frontend/src/router.test.tsx#denies every direct administrator route before mounting admin requests
        status: pass
      - kind: unit
        ref: frontend/src/router.test.tsx#announces administrator loading without mounting protected content
        status: pass
      - kind: unit
        ref: frontend/src/router.test.tsx#keeps administrator load errors bounded, recoverable, and free of protected content
        status: pass
    human_judgment: false
  - id: D3
    description: The administrator shell honors 320, 768, 1024, and wide contracts, locally contains labels, closes the Sheet with focus restoration, and honors reduced motion.
    requirement: UI-03
    verification:
      - kind: unit
        ref: frontend/src/components/layout/AppShell.test.tsx#freezes the 320, 768, 1024, and wide shell containment contracts
        status: pass
      - kind: unit
        ref: frontend/src/components/layout/AppShell.test.tsx#shows the same Administration destination in the mobile Sheet
        status: pass
    human_judgment: false
  - id: D4
    description: Product detail navigation is URL-backed, ordered, singularly current, and contained at 320px.
    requirement: UI-03
    verification:
      - kind: unit
        ref: frontend/src/router.test.tsx#keeps product navigation URL-backed, ordered, singular, and locally contained
        status: pass
      - kind: unit
        ref: frontend/src/router.test.tsx#preserves the current product section when the URL has a trailing slash
        status: pass
    human_judgment: false

duration: 37min
completed: 2026-08-28
status: complete
---

# Phase 02 Plan 16: Responsive Administrator Shell Summary

**A server-role-projected administrator shell now provides fail-closed route states, accessible responsive navigation, and reusable URL-backed product sections without granting client-side authority.**

## Performance

- **Active duration:** 37 min
- **Started:** 2026-08-28T07:21:33Z
- **Completed:** 2026-08-28T07:58:26Z
- **Tasks:** 2
- **Files changed:** 6 production/test files

## Accomplishments

- Added one Administration destination model with exact Products, Users, and Bitbucket links, rendered consistently in the desktop Sidebar and mobile Sheet only for server-loaded administrators.
- Added exact access-denied, loading, and recoverable error route states with visible/live semantics and no protected-content mount or request before authority is ready.
- Locked local containment at 320, 768, 1024, and wide layouts, including long labels, mobile Sheet width, close-and-focus restoration, and reduced-motion behavior.
- Added a reusable `ProductDetailLayout` whose URL-backed navigation remains in exact Overview, Repositories, Mappings, Preview order with exactly one current item, including unknown and trailing-slash paths.
- Preserved the existing shadcn registry/theme and all dependency manifests.

## Task Commits

1. **Task 1: Open one guarded administrator route from shared navigation**
   - `574314d` — RED administrator shell tracer tests
   - `ba9c7e9` — guarded administrator navigation tracer
   - `20affd7` — workspace shell content separation
   - `efc4988` — tracer test formatting
2. **Task 2: Lock responsive, accessibility, and route-state contracts**
   - `6cfd325` — RED responsive administrator shell contract tests
   - `c5cb401` — responsive administrator route shell implementation
   - `70f27ed` — contract test formatting
   - `936a2cf` — isolated product route resolution
   - `4cfbb03` — administrator authority and route fallback coverage
   - `a0ae6fe` — simplified product path authority
   - `436eded` — product layout route-parameter exercise
   - `dab9f91` — guarded product route parameter binding
   - `f62774e` — trailing-slash navigation proof
   - `e3a852c` — singular primary administrator destination proof
   - `4f1d984` — exact administrator destination-state proof
   - `028eceb` — simplified Sheet/tooltip transition state
   - `eb8e6eb` — removed redundant tooltip state

## Files Created/Modified

- `frontend/src/features/admin/AdminAccessDenied.tsx` — exact bounded access-denied state with focus handling.
- `frontend/src/features/admin/products/ProductDetailLayout.tsx` — reusable guarded product section shell and outlet.
- `frontend/src/router.tsx` — role projection, guarded administrator routes, and visible loading/error states.
- `frontend/src/router.test.tsx` — authority, no-flash, product routing, fallback, and containment contracts.
- `frontend/src/components/layout/AppShell.tsx` — shared responsive Administration navigation and local containment.
- `frontend/src/components/layout/AppShell.test.tsx` — desktop/mobile, breakpoint, focus, reduced-motion, role, and current-route contracts.

## Decisions Made

- Client roles control only whether administrator navigation is projected; protected mutation authority remains entirely backend-enforced.
- The desktop Sidebar and mobile Sheet consume one exact destination list to prevent responsive information-architecture drift.
- Unknown product-detail sections select Overview as the sole current local destination without fabricating a feature page; Plans 18 and 19 supply the page data.

## Verification

- Exact Task 2 and plan command: **35/35 focused Vitest tests passed**.
- Fresh randomized frontend suite (`--sequence.shuffle --sequence.seed=21616`): **93/93 tests passed**.
- Responsive/accessibility contracts: desktop/mobile Administration parity, 320/768/1024/wide containment, long-label wrapping, Sheet close/focus restoration, reduced motion, visible live states, no protected flash, and singular `aria-current` all passed in the focused suite.
- Frontend static/build: TypeScript, ESLint, Prettier, canonical API drift, dependency-tree resolution, and Vite production build passed; **1,949 modules transformed**.
- Changed-production-line and branch coverage against `93cfe37`: **40/40 lines, 100%**, with no missing changed line.
- Targeted mutation proof: **35/35 non-equivalent mutants killed, 100%** across product routing, route-state/authority, active navigation, shell visibility, and role projection.
- Backend randomized suite with isolated PostgreSQL, Redis, and a live Celery worker: **698/698 tests passed**.
- Focused migrations, architecture, OpenAPI, and worker smoke: **25/25 passed**.
- Backend static/supply chain: Ruff check/format, MyPy for **81 source files**, `uv lock --check`, `pip-audit`, and license inventory passed. Existing complexity inventory was unchanged.
- Supply chain and secrets: production `npm audit --omit=dev` reported **0 vulnerabilities**; changed-file secret scan found **0 findings**, and the AWS-key negative control was detected. The already-recorded development-only `qs` moderate advisory remains unchanged.
- Local frontend production build passed. The broader container smoke exposed the pre-existing Plan 02-15 Docker build-context defect documented below.

## TDD Gate Compliance

- Task 1 followed RED in `574314d`, GREEN in `ba9c7e9`, and REFACTOR in `20affd7` with the exact focused command at each gate.
- Task 2 followed RED in `6cfd325`, GREEN in `c5cb401`, and successive behavior-preserving refactors through `eb8e6eb`; the exact focused command remained unchanged and passed on the final source.
- The final log contains both required `test(02-16)` RED commits before the corresponding `feat(02-16)` implementation commits.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical regression armor] Closed route-authority and active-navigation mutation gaps**
- **Found during:** Task 2 changed-line coverage and mutation testing
- **Issue:** Initial tests did not distinguish trailing-slash product paths or exact versus nested administrator destinations strongly enough.
- **Fix:** Added URL fallback/trailing-slash and singular `aria-current` proofs, then simplified route resolution around guarded parameters.
- **Files modified:** `frontend/src/router.test.tsx`, `frontend/src/components/layout/AppShell.test.tsx`, `frontend/src/features/admin/products/ProductDetailLayout.tsx`
- **Commits:** `4cfbb03`, `dab9f91`, `f62774e`, `e3a852c`, `4f1d984`

**2. [Rule 1 - Redundant state] Removed unnecessary Sheet/tooltip synchronization**
- **Found during:** Task 2 mutation testing
- **Issue:** Duplicate tooltip/open state transitions created behaviorally redundant branches around the mobile navigation trigger.
- **Fix:** Let the Sheet and Tooltip primitives own their respective transitions while retaining the tested close-and-focus behavior and reduced-motion contract.
- **Files modified:** `frontend/src/components/layout/AppShell.tsx`
- **Commits:** `028eceb`, `eb8e6eb`

## Issues Encountered

- The first changed-line coverage run reported **92%**, then **97%**; focused authority and route-fallback proofs closed the final changed branches to **100%**.
- The first focused product mutation run killed **9/10** mutants; the trailing-slash contract closed the survivor and the fresh run killed **10/10**.
- `tools/real_smoke.sh --browser-only` exposed a pre-existing Plan 02-15 container defect: `docker/frontend.Dockerfile` does not copy `frontend/openapi.json`, so the Plan 02-15 generated-client contract import fails only inside the Docker typecheck. This is outside the Plan 02-16 diff, is recorded in `deferred-items.md` and `.planning/WINDOWS.md`, and must be repaired before Phase 2 closes.

## Known Stubs

None. The six changed implementation/test files contain no TODO, FIXME, placeholder, skipped test, or unwired data source. Product feature pages intentionally remain owned by Plans 18 and 19 rather than being represented by stubs here.

## User Setup Required

None - no external service configuration or dependency installation required.

## Next Phase Readiness

- Plan 02-17 can build administrator feature foundations on one guarded, responsive route shell.
- Plans 02-18 and 02-19 can plug product, repository, mapping, and preview pages into the already-ordered `ProductDetailLayout` routes.
- The Plan 02-15 Docker build-context debt does not invalidate the Plan 02-16 UI contract, but it remains an explicit Phase 2 close gate.

## Self-Check: PASSED

- All six planned source/test files exist; all 17 task commits are present in repository history.
- The exact plan verification, fresh frontend/backend suites, changed-line coverage, mutation proof, static checks, API drift, supply-chain checks, and secret scan passed on the final source state.
- Only the documented pre-existing container smoke defect remains open; the known untracked `.gsd/`, `.planning/milestone.lock`, and `graphify-out/` paths were not modified or staged.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-28*
