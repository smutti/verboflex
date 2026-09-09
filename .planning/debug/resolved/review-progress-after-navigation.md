---
status: resolved
trigger: "non si apre"
created: 2026-09-06T19:03:26Z
updated: 2026-09-06T19:53:07Z
mode: find-and-fix
---

# Review progress is lost after leaving the page

## Symptoms

Expected: a validation started from the Review/Preview area continues in the
background and its current state is restored after navigating away and back.
Actual: the worker continues, but the Review/Preview UI stops updating after
navigation and returns to the initial "Validation has not run" state.
Error message: none; this is a page-lifecycle and state-recovery defect.
Timeline: observed while validating a mapping after the Phase 4 local rebuild.
Reproduction: start validation, navigate away before completion, then return to
the Preview page.

## Current Focus

hypothesis: Confirmed and fixed: session storage was insufficient because it is
owned by one browser session. PostgreSQL must remain the sole recovery authority.
test: Clear browser storage and mount both candidate and active-revision preview
pages while a durable exact mapping job already exists.
expecting: The page reloads the exact latest durable job without creating a
duplicate validation.
next_action: Native user smoke test in the rebuilt local application.

## Evidence

- Docker reports frontend/backend/worker healthy with host bindings 127.0.0.1:8080 and 127.0.0.1:8000.
- GET `/` through both localhost and 127.0.0.1 returns HTTP 200; backend health returns HTTP 200.
- Nginx served the current CSS and JS bundles to Safari. Backend logs then record a successful token request and 200 responses for current user, Products, Users, Bitbucket and system status.
- The in-app browser independently renders the VerboFlex login form at `http://localhost:8080/login`.
- No frontend/backend error appears in the recent logs. Native Safari inspection is unavailable because computer-use permissions are not granted.
- `MappingPreview` stores the current preview in component-local `useState`; a remount initializes it to `null`.
- `usePreviewPolling` owns a page-local timeout and marks itself unmounted during cleanup, so navigation stops all subsequent status requests.
- Preview polling automatically stops after 90 seconds even if the page remains open.
- The API exposes creation and lookup by `job_id`, but no endpoint that returns the current/latest preview job for a product mapping.
- Preview creation persists the row before enqueueing a Celery task containing only its UUID, so computation is independent from the browser after submission.
- Recent local rows reached a terminal `failed` state in about 20–26 seconds; the worker received and completed each task. Their failure was `repository_scan_limit_reached`, which is separate from the lost UI progress.
- RED: both candidate and active-revision remount tests initially returned to "Validation has not run".
- GREEN: four recovery scenarios now pass, including leaving before and after the create response is received.
- Full frontend verification passes: 607 tests, TypeScript typecheck, ESLint, Prettier, and production build.
- The rebuilt local frontend serves bundle `index-Hmeexq1Q.js`; frontend, backend, worker, Redis, and PostgreSQL are healthy.
- User retest still reproduces the original symptom, proving session-scoped recovery is insufficient.
- RED: both authenticated latest-job routes initially returned the framework 404, and both fresh-browser frontend regressions rendered "Validation has not run".
- GREEN: the backend integration and OpenAPI contracts pass for both candidate and active-revalidation discovery; all 78 preview-page tests pass.
- Relevant backend suite passes: 108 tests. Full frontend suite passes: 609 tests, with TypeScript, ESLint, Prettier, and production build green.
- Backend and frontend containers were rebuilt while preserving the existing local Bitbucket credentials. The new OpenAPI operation IDs are served, the frontend bundle is `index-BxfDeowo.js`, and every application container is healthy.

## Eliminated

- hypothesis: Docker services are stopped or unhealthy
  evidence: All application containers are running and healthy.
- hypothesis: Port 8080 is not listening or the frontend bundle is unavailable
  evidence: Host HTTP requests and Safari asset requests return 200.
- hypothesis: Navigating away stops or cancels the Celery task
  evidence: The backend persists and enqueues the job independently; local task and database timestamps show completion in the worker.

## Resolution

root_cause: The Review/Preview page used component-local polling and component-local job identity. Navigating away discarded that pointer. The first fix moved the pointer to session storage, but a new tab/session or missing storage still had no way to discover the durable PostgreSQL job.
fix: Add administrator-only endpoints that return the newest job for the exact live product, revision, revision version, mapping, and scope. On every Preview mount, use those endpoints as the authoritative initial state, validate the returned identity, and then resume the existing job-ID polling. Remove browser storage from the recovery contract.
verification: Two backend TDD regressions and two fresh-browser frontend regressions cover candidate and active-revision recovery. Relevant backend tests (108) and the full frontend suite (609), typecheck, lint, format, build, container health, served OpenAPI, and HTTP asset smoke checks pass.
files_changed: frontend/src/features/admin/previews/ProductPreviewPage.tsx, frontend/src/features/admin/previews/ProductPreviewPage.test.tsx, frontend/src/api/admin-client-contract.test.ts, frontend/openapi.json, frontend/src/api/client/index.ts, frontend/src/api/client/sdk.gen.ts, frontend/src/api/client/types.gen.ts, backend/src/verboflex/services/preview_jobs.py, backend/src/verboflex/api/v1/routes/admin_previews.py, backend/tests/integration/test_preview_jobs.py, backend/tests/api/test_openapi_contract.py, .planning/debug/resolved/review-progress-after-navigation.md
