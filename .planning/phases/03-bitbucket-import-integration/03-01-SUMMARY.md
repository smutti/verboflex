---
phase: 03-bitbucket-import-integration
plan: 01
subsystem: bitbucket-import
tags: [fastapi, postgresql, celery, redis, react, bitbucket, tdd]

requires:
  - phase: 02-admin-configuration
    provides: Published mapping ownership, commit-bound Bitbucket discovery, generated admin client, and client-credentials authority
provides:
  - Stable logical import UUIDs with immutable executions and ordered commit-bound source references
  - Admin-only published direct-mapping import list, start, and status operations
  - UUID-only Celery execution with one active persisted baseline
  - Server-confirmed direct-import controls in the existing product Mappings route
  - Configuration-independent local Bitbucket credential revocation
affects: [03-02, 03-05, 03-06, 03-07, 03-08, 03-09, 03-10, 03-12]

actuals:
  tokens: 81639
  tasks: 1
  commits: 4

tech-stack:
  added: []
  patterns:
    - Commit durable queued state before dispatching one logical UUID to Celery
    - Resolve configured branches once and retain only ordered commit-bound source metadata publicly
    - Keep local credential invalidation available even when provider construction fails

key-files:
  created:
    - backend/alembic/versions/0012_import_jobs.py
    - backend/src/verboflex/models/import_job.py
    - backend/src/verboflex/schemas/imports.py
    - backend/src/verboflex/services/import_jobs.py
    - backend/src/verboflex/worker/import_tasks.py
    - backend/tests/integration/test_import_jobs.py
  modified:
    - backend/src/verboflex/api/v1/routes/admin_mappings.py
    - backend/src/verboflex/api/v1/routes/admin_bitbucket.py
    - backend/src/verboflex/services/bitbucket_oauth.py
    - backend/src/verboflex/worker/celery_app.py
    - backend/tests/api/test_admin_bitbucket.py
    - frontend/openapi.json
    - frontend/src/api/client/index.ts
    - frontend/src/api/client/sdk.gen.ts
    - frontend/src/api/client/types.gen.ts
    - frontend/src/features/admin/mappings/ProductMappingsPage.tsx
    - frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx

key-decisions:
  - "One published mapping owns one stable logical import UUID; each run has a separate immutable execution identity and only the current execution may terminalize it."
  - "Redis receives only the logical import UUID; source bytes remain inside the backend worker while public responses expose ordered hashes and commit-bound metadata only."
  - "Local Bitbucket revocation is independent of provider settings and encryption-key construction so broken configuration cannot trap local credential authority."

patterns-established:
  - "Import authority: lock Product, verify the exact active revision and mapping owner, commit queued state, then dispatch one UUID."
  - "Completion fencing: finish an execution only when its logical import and current immutable execution identities still match."
  - "Recovery boundary: provider configuration is required to connect or read, but never to clear local credentials."

requirements-completed: [BITB-02, BITB-05, BITB-06]

coverage:
  - id: D1
    description: An administrator can start one direct published-mapping import and read its server-confirmed state through the generated browser contract.
    requirement: BITB-02
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py::test_direct_import_tracer_completes_commit_bound_baseline
        status: pass
      - kind: automated_ui
        ref: frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx
        status: pass
    human_judgment: false
  - id: D2
    description: The worker receives one UUID, resolves an exact commit, reads selected files, and persists ordered metadata without exposing source bytes.
    requirement: BITB-05
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py::test_direct_import_tracer_completes_commit_bound_baseline
        status: pass
    human_judgment: false
  - id: D3
    description: Concurrent starts produce one current execution and the provider resource spy observes Bitbucket GET requests only.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py::test_concurrent_start_reuses_one_logical_import_and_current_execution
        status: pass
    human_judgment: false
  - id: D4
    description: An administrator can always revoke local Bitbucket credentials even when provider settings are missing or invalid.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/api/test_admin_bitbucket.py::test_local_revoke_remains_available_without_provider_configuration
        status: pass
    human_judgment: false

duration: 1h 58m
completed: 2026-09-02
status: complete
---

# Phase 03 Plan 01: Direct Published-Mapping Import Tracer Summary

**A persisted UUID-only import now carries one published direct mapping through FastAPI, PostgreSQL, Celery, commit-bound Bitbucket reads, and the generated React client, with local revocation available during configuration failure.**

## Performance

- **Duration:** 1h 58m
- **Started:** 2026-09-02T18:16:38Z
- **Completed:** 2026-09-02T20:14:23Z
- **Tasks:** 1
- **Files modified:** 17

## Accomplishments

- Added additive logical import, immutable execution, repository-side, and ordered source-reference persistence through migration `0012_import_jobs`.
- Exposed admin-only list, start, and status operations and regenerated the canonical TypeScript client without drift.
- Mounted server-driven published direct-import rows before candidate drafts in the existing Mappings route.
- Proved concurrent starts converge on one current execution and every provider resource request remains GET-only.
- Repaired local Bitbucket revocation so invalid or absent provider configuration cannot prevent credentials from being cleared.

## Task Commits

1. **Task 1 RED: require the direct import tracer** — `99ad746` (test)
2. **Task 1 GREEN: implement the direct import tracer** — `78c452f` (feat)
3. **Checkpoint regression RED: reproduce unavailable local revoke** — `04163e1` (test)
4. **Checkpoint regression GREEN: decouple local revoke from provider settings** — `a309824` (fix)

## Files Created/Modified

- `backend/alembic/versions/0012_import_jobs.py` — Adds reversible logical import, immutable execution, side, reference, and baseline schema.
- `backend/src/verboflex/models/import_job.py` — Defines the durable import identity graph and named constraints.
- `backend/src/verboflex/services/import_jobs.py` — Owns mapping authorization, concurrency, dispatch, commit-bound discovery, and fenced completion.
- `backend/src/verboflex/worker/import_tasks.py` — Constructs provider dependencies inside a UUID-only Celery task.
- `backend/src/verboflex/api/v1/routes/admin_mappings.py` — Projects closed published-import list, start, and status operations.
- `frontend/src/features/admin/mappings/ProductMappingsPage.tsx` — Renders and refreshes direct published-mapping imports from server authority.
- `backend/src/verboflex/services/bitbucket_oauth.py` — Provides configuration-independent local credential invalidation.
- `backend/src/verboflex/api/v1/routes/admin_bitbucket.py` — Uses the local invalidation path when provider configuration is unavailable.

## Decisions Made

- Kept one stable logical import identity per published mapping while retaining immutable per-run execution identities for later retry and reconciliation plans.
- Persisted only exact commit, ordered path, size, and SHA-256 metadata at the public boundary; raw source bytes remain worker-local.
- Kept provider resource access read-only and made revocation a purely local operation that does not depend on provider availability.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Restored the local Docker runtime prerequisites**
- **Found during:** Failed tracer human verification.
- **Issue:** The running backend and worker predated the Phase 2 provider environment contract, and PostgreSQL was still at migration `0007_preview_confirmations`.
- **Fix:** Rebuilt backend, worker, and frontend with the existing protected local client credentials plus an in-memory runtime keyring, then applied versioned migrations through `0012_import_jobs`.
- **Files modified:** None; this was local runtime state only.
- **Verification:** All five core containers are healthy, backend/worker each expose the three required variable names, runtime provider construction succeeds, and `alembic_version` is `0012_import_jobs`.
- **Committed in:** Not applicable — runtime repair only.

**2. [Rule 1 - Bug] Allowed local credential revocation without provider configuration**
- **Found during:** Failed tracer human verification.
- **Issue:** `POST /api/v1/admin/bitbucket/revoke` required a fully configured OAuth service, so absent or invalid settings returned 503 before local ciphertext could be cleared.
- **Fix:** Extracted the locked, audited local invalidation boundary from provider construction and retained the configured service path as a delegate.
- **Files modified:** `backend/src/verboflex/services/bitbucket_oauth.py`, `backend/src/verboflex/api/v1/routes/admin_bitbucket.py`, `backend/tests/api/test_admin_bitbucket.py`
- **Verification:** The new regression failed with 503 before implementation and now passes with a bounded `Disconnected` projection and cleared ciphertext; all 16 Bitbucket API/service tests pass.
- **Committed in:** `04163e1`, `a309824`

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug, 1 Rule 3 blocking runtime repair)
**Impact on plan:** Both repairs were necessary to make the planned tracer usable in the actual Docker environment. No provider resource write, dependency, lockfile, or public credential surface was added.

## Verification

- Direct import tracer: **2/2 passed** (`direct_import_tracer` and `concurrent_start`).
- Bitbucket lifecycle regression: **16/16 passed** across API and service integration suites.
- Frontend route coverage: **29/29 passed** across Mappings and Bitbucket pages.
- Generated client: `npm run api:check` regenerated deterministically with zero drift.
- Static checks: Ruff passed; mypy passed the two changed backend production modules.
- Docker: frontend, backend, worker, PostgreSQL, and Redis are healthy; schema is at `0012_import_jobs`.
- Live credential validation: token acquisition succeeded with exact `repository` scope; no provider resource read or write was performed by that check.

## TDD Gate Compliance

- Original tracer RED `99ad746` precedes GREEN `78c452f`.
- Failed checkpoint regression RED `04163e1` precedes GREEN `a309824`.
- Both RED runs failed for missing behavior rather than fixture, import, migration, or syntax errors.

## Issues Encountered

- The browser-control session had no authenticated local tab, so production UI behavior was verified through the real rebuilt bundle, generated-client drift checks, focused React tests, API integration tests, container health, and runtime configuration checks rather than by reusing the user's login session.
- Vite retained the pre-existing non-blocking chunk-size warning; no dependency or bundling policy changed in this plan.

## User Setup Required

- The current containers are configured and healthy. Future container recreation must again provide the three secret variables documented in `02-USER-SETUP.md`; values remain outside repository files and command output.
- The existing protected local consumer credentials were validated with exact `repository` scope. No new external credential or permission is required for this plan.

## Known Stubs

None. Select placeholders found by the scan are existing user-input hints backed by live generated API data, not unwired feature stubs.

## Authentication Gates

None. The existing local administrator session was not reused or inspected.

## Next Phase Readiness

- Plan 03-02 can harden the tracer schema and negative invariants against the now-proven vertical path.
- Plans 03-05 through 03-10 can extend provider diagnostics, retry, rewrite detection, and aggregation without replacing the stable logical UUID.
- The local Docker stack is on the current image and database migration; Bitbucket token material remains absent from the database until an administrator explicitly connects.

## Self-Check: PASSED

- All 17 created or modified implementation artifacts exist.
- Commits `99ad746`, `78c452f`, `04163e1`, and `a309824` exist in branch history.
- Every mandatory plan verification and the failed-checkpoint regression suite passed after Docker repair.
- The tracked implementation tree is clean; only orchestrator-managed state and explicitly preserved untracked workspace artifacts remain.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-02*
