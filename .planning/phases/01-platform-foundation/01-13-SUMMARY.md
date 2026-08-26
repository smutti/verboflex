---
phase: 01-platform-foundation
plan: 13
subsystem: authenticated-shell
tags: [react, shadcn, playwright, responsive, accessibility, cors, tdd]

requires:
  - phase: 01-platform-foundation/01-09
    provides: Generated authenticated client operations and memory-only session authority
  - phase: 01-platform-foundation/01-12
    provides: Fail-closed login and mandatory-password-change routes
provides:
  - Server-authoritative identity and human role labels in the ordinary workspace
  - Bounded real service-state projection with safe failure and retry behavior
  - Quiet responsive desktop sidebar and tablet/mobile shadcn sheet navigation
  - Real Docker/Playwright auth, refresh, storage, responsive, and logout evidence
affects: [phase-1-gauntlet, phase-1-ui-review, admin-shell]

actuals:
  tokens: 9209
  tasks: 2
  commits: 29

tech-stack:
  added:
    - "@playwright/test@1.62.1 (approved development dependency)"
  patterns:
    - Generated me/status/logout operations remain the sole authenticated browser boundary
    - Server role enums are projected to fixed human labels without client authorization logic
    - Desktop navigation begins at 1024px; tablet and mobile use the official shadcn Sheet
    - Browser E2E artifacts are written outside the repository under /tmp

key-files:
  created:
    - frontend/src/components/layout/AppShell.tsx
    - frontend/src/components/layout/ServiceStatus.tsx
    - frontend/src/pages/Dashboard.tsx
    - frontend/src/components/layout/AppShell.test.tsx
    - frontend/e2e/auth-shell.spec.ts
    - frontend/playwright.config.ts
    - backend/tests/api/test_cors.py
    - docker/frontend.nginx.conf
  modified:
    - frontend/src/App.tsx
    - frontend/src/App.test.tsx
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/vite.config.ts
    - backend/src/verboflex/main.py
    - backend/alembic/env.py
    - docker-compose.yml
    - docker/backend.Dockerfile
    - docker/frontend.Dockerfile

key-decisions:
  - "Identity, roles, and status are rendered only from authenticated generated operations; the shell never decodes bearer claims or invents service availability."
  - "The 768px tablet width uses sheet navigation, while the fixed sidebar is reserved for 1024px and wider."
  - "Credentialed CORS echoes only an exact configured origin; it never uses a wildcard or changes the OpenAPI surface."

patterns-established:
  - "Authenticated shell states use exact visible text, accessible landmarks, labelled icon controls, tooltips, bounded radii, and min-width containment."
  - "Real-browser auth checks reset a disposable admin through stdin, exercise forced replacement, and assert that Web Storage remains empty."

requirements-completed: [PLAT-02, AUTH-04, UI-01]

coverage:
  - id: D12
    description: "Ordinary users see only server identity, human role labels, neutral workspace copy, and the current workspace navigation."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "frontend/src/components/layout/AppShell.test.tsx#authenticated application shell"
        status: pass
      - kind: e2e
        ref: "frontend/e2e/auth-shell.spec.ts#auth shell completes forced change, refresh, responsive navigation, and logout"
        status: pass
    human_judgment: false
  - id: D13
    description: "Real service states are explicit text; loading, sanitized failure, retry, and logout remain bounded and accessible."
    requirement: AUTH-04
    verification:
      - kind: unit
        ref: "frontend/src/components/layout/AppShell.test.tsx#renders every server service enum as an explicit text label"
        status: pass
      - kind: e2e
        ref: "frontend/e2e/auth-shell.spec.ts#service labels and refresh"
        status: pass
    human_judgment: false
  - id: D14
    description: "Desktop, tablet, and mobile shell layout, hierarchy, focus, sheet navigation, and overflow match the approved visual contract."
    requirement: UI-01
    verification:
      - kind: e2e
        ref: "frontend/e2e/auth-shell.spec.ts#1440, 768, and 375 viewport loop"
        status: pass
      - kind: manual
        ref: "In-app browser visual check"
        status: pass
    human_judgment: true

duration: 35min
completed: 2026-08-25
status: complete
---

# Phase 1 Plan 13: Authenticated Shell and Browser Evidence Summary

**The modern authenticated shell, full real auth path, responsive layouts, and final manual browser inspection are green.**

## Performance

- **Active duration:** 35 min
- **Started:** 2026-08-24T20:07:26Z
- **Completed:** 2026-08-25
- **Tasks implemented:** 2
- **Files created/modified:** 18
- **Implementation/test commits:** 28

## Accomplishments

- Added the neutral full-width workspace with exact approved identity, email, Administrator/Product manager / reviewer/Translator/Viewer labels, `Workspace overview`, and configuration-ready empty copy. No product, repository, review, or pull-request action exists.
- Added authenticated generated status loading, exact API/database/Redis/worker text labels, checked timestamp, sanitized error, retry, and logout. Failures never fabricate `online` or expose diagnostics.
- Added quiet fixed desktop navigation and an accessible official shadcn Sheet on tablet/mobile, with labelled and tooled icon controls, keyboard focus treatment, no overflow at 1440/768/375, no gradients/nested cards, and at most 8px visible radius.
- Proved the real disposable-admin flow through the isolated Docker stack: temporary login, forced password replacement, fresh ordinary login, status, memory-cookie refresh after reload, empty local/session storage, responsive checks, and logout.

## Per-Behavior TDD Commits

### Task 1: Identity, status, neutral content, and logout

1. Identity, roles, and empty copy: RED `9f0a455`; GREEN `5e941b1`.
2. Authenticated status loading: RED `35694f4`; GREEN `d8ebd8b`.
3. Bounded status enums and exact labels: RED `e247d76`; GREEN `03a4f23`.
4. Sanitized error and retry: RED `86bd69d`; GREEN `9cd4922`.
5. Exact session-backed logout: RED `6d68ff7`; GREEN `0fea799`.
6. Production authenticated entry: RED `8995ae9`, `0978688`; GREEN `1c97adf`.
7. Desktop current-workspace-only navigation: RED `8516b73`; GREEN `9d97403`.
8. Mobile labelled Sheet and tooltip: RED `c49b623`, test support `036f7cb`; GREEN `466b075`.

### Task 2: Real auth, responsive, storage, and deployment behavior

1. Real browser contract: RED `b48ad9d` on direct `/login` Nginx 404; GREEN route fallback `83b5d2c`.
2. Credentialed browser delivery: endpoint returned 200 but the browser rejected it without CORS. Focused CORS RED `c752684` observed 405/no headers; GREEN `2545c2a` echoes only the configured origin with credentials and rejects hostile preflight without allowlist/diagnostic leakage.
3. Responsive tablet behavior: the E2E reached forced change, reload, status, and storage before failing because 768px exposed the desktop sidebar. GREEN `513e7e1` reserves the sidebar for 1024px and opens the labelled Sheet at 768/375.
4. Test-runner isolation: full Vitest discovery tried to collect the Playwright spec; `12cbc0e` confines Vitest to `src/**/*.test.{ts,tsx}` without weakening either suite.

## Automated Evidence

- Exact plan fast gate: AppShell **8 passed**, TypeScript build/typecheck passed, production Vite build passed.
- Real Playwright gate against the rebuilt final Docker frontend: **1 passed in 7.6s**. It covers ordinary login, mandatory replacement, second login, exact identity/role/copy/status, reload refresh, Web Storage absence, 1440/768/375, overflow, max radius, no gradients/nested sections/future actions, tablet/mobile sheet, and logout.
- Full frontend regression: **10 files, 57 tests passed**; ESLint 0 warnings; TypeScript 0 errors; OpenAPI/client drift 0; npm audit 0 vulnerabilities.
- Focused CORS contract: **2 passed**; exact configured origin and `Access-Control-Allow-Credentials: true`, no wildcard, hostile preflight denied, and no configured origin/traceback leaked.
- Full backend regression with plan-owned PostgreSQL/Redis and a distinct solo Celery process: **208 passed**; strict mypy clean across 58 files; Ruff check/format clean across 61 files; pip-audit found no known vulnerabilities.
- Isolated application stack `verboflex_phase01_plan13`: PostgreSQL, Redis, backend, worker, and frontend are all healthy; Alembic upgraded to head and the disposable admin was created/reset only through stdin.

## In-App Browser Visual Evidence

- The required browser skill and complete browser-client documentation were read before browser actions.
- `/login` was manually inspected through the in-app browser at 1440, 768, and 375 pixels. It is a quiet single panel with exact labels/button, no marketing treatment, no horizontal overflow (`bodyWidth` exactly matched each viewport), and a 333px panel at the 375px viewport.
- Visible focus uses the approved teal 2px treatment with 2px offset. Screenshots were inspected through the browser runtime and were not committed.
- Under the user's action-time confirmation, the disposable temporary login reached `/change-password`; the user personally pressed the final `Set new password` action. The observed redirect returned to `/login`, and the fresh ordinary login succeeded.
- The authenticated dashboard was manually inspected at 1440x900, 768x900, and 375x812. Identity `phase13@example.com`, role `Administrator`, workspace content, service status, desktop/sidebar and tablet/mobile sheet hierarchy were visible with no overflow, overlap, or clipped text. The temporary viewport override was reset.
- A second manual logout was not repeated because the already-green Playwright scenario exercises the real logout and storage outcome; isolated-stack cleanup immediately invalidated the disposable session and removed all data.
- No cookie or Web Storage inspection was performed through the manual browser. The authorized repository Playwright test alone performs the planned Web Storage assertion.

## Security and API Evidence

- **T-13-01 / spoofing:** identity, roles, and status come only from generated authenticated server responses.
- **T-13-02 / disclosure:** access authority stays in memory, refresh authority stays in the HttpOnly flow, Playwright proves both Web Storage areas remain empty, and status/CORS failures expose no diagnostics.
- **T-13-03 / elevation:** role labels are presentation only; no client-side role grants access and all backend authority checks remain unchanged.
- **API scope:** internal, existing seven-operation HTTP surface. No path, method, request/response schema, status code, or generated client contract changed.
- **old-coder-api gates:** Boring ✓; Compatibility ✓ (OpenAPI drift zero); Authentication ✓ (exact credentialed origin); Authorization ✓ (unchanged server checks); Idempotency N/A (no new action); Blast radius ✓ (existing limits unchanged); Pagination N/A; Expensive fields N/A; No implementation leakage ✓.

## Deviations from Plan

### Auto-fixed Issues

1. **[Rule 3 - Blocking] Installed the already-approved Playwright runner.** The SPEC approved Playwright but it was absent from the lockfile. `@playwright/test@1.62.1` was exact-pinned from the official Microsoft package; npm audit remains zero. Commit `b5846c8`.
2. **[Rule 3 - Blocking] Replaced the pre-auth health tracer with the authenticated shell entry.** The existing `App`/test still owned the old public-health scaffold; RED/GREEN wiring moved production to the approved session principal/status path without changing HTTP. Commits `8995ae9`, `0978688`, `1c97adf`.
3. **[Rule 3 - Blocking] Corrected PostgreSQL 18 volume layout.** PostgreSQL 18 rejected a volume mounted at the former data leaf; Compose now mounts the cluster root. Commit `a583f2c`.
4. **[Rule 3 - Blocking] Included migrations in the runtime backend image.** The deployment image lacked `alembic.ini` and migration scripts, so planned schema setup could not run. Commit `41e6bff`.
5. **[Rule 1 - Bug] Honored the container database URL in Alembic.** Migration configuration otherwise targeted localhost inside the container; the environment DSN now overrides the file safely. Commit `51ff0de`.
6. **[Rule 3 - Blocking] Added the SPA route fallback.** Nginx returned 404 for direct `/login`; the exact real-browser RED now passes through `try_files ... /index.html`. Commit `83b5d2c`.
7. **[Rule 2 - Security] Installed the exact credentialed CORS boundary.** Browser token delivery was unreadable despite a backend 200. Dedicated RED/GREEN tests prove one exact allowlisted origin, credential support, hostile rejection, no wildcard, and no diagnostic leakage; OpenAPI remains unchanged. Commits `c752684`, `2545c2a`.
8. **[Rule 1 - Bug] Moved the desktop breakpoint above tablet width.** The real 768px assertion found a sidebar instead of the approved sheet. Commit `513e7e1`.
9. **[Rule 3 - Blocking] Kept Vitest and Playwright discovery separate.** Full Vitest attempted to collect the environment-gated E2E module; explicit `src` inclusion restores the independent 57-test suite. Commit `12cbc0e`.

## Issues Encountered

- The first full backend run correctly failed because the repository integration suite expects dedicated PostgreSQL on 55432, Redis on 56379, and a real worker. Plan-owned disposable test containers were started, and the macOS Python 3.14 Celery prefork attempt segfaulted before accepting work. A distinct `--pool=solo --concurrency=1` worker then passed all 208 tests. The test-only worker and containers were stopped and auto-removed; the application checkpoint stack remains intact.
- No unapproved direct dependency, generated API drift, product/repository/review/PR functionality, credential storage, or unrelated source change was introduced.

## Human Browser Check: PASSED

- The user supplied the required action-time confirmation for the disposable local credentials and personally submitted the final password replacement.
- `/login`, `/change-password`, and `/` were observed through the in-app browser with the required hierarchy, copy, focus, status, responsive navigation, and overflow checks.
- Browser safety was preserved: no agent-side final password submission and no manual cookie or Web Storage inspection occurred.

## Cleanup

- Docker project `verboflex_phase01_plan13` was stopped and removed with both isolated PostgreSQL/Redis volumes and its network. Ports 8000 and 8080 have no listener.
- The chmod-600 credential handoff file `/tmp/verboflex-plan13-iab-credentials.json` was explicitly deleted and is not recoverable. It was never part of the repository.
- The earlier test-only PostgreSQL/Redis containers and solo Celery worker had already been stopped and removed after the full backend gate.

## Self-Check: PASSED

- All implementation and automated acceptance behavior exists and is committed.
- Every non-human plan gate is green against the final committed source state.
- The browser-safety human check passed and every plan-owned runtime/data artifact was removed.
- The only unrelated working-tree path remains the pre-existing untracked `.planning/milestone.lock`, which was never staged or modified.

## PLAN COMPLETE

---

*Phase: 01-platform-foundation*
*Completed: 2026-08-25*
