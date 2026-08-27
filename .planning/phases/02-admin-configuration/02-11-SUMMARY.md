---
phase: 02-admin-configuration
plan: 11
subsystem: background-jobs-api
tags: [fastapi, postgresql, celery, redis, openapi, tdd, mutation-testing]

requires:
  - phase: 02-10
    provides: Atomic candidate publication authority and mapping validation
provides:
  - Durable PostgreSQL-authoritative preview attempts exposed through closed admin APIs
  - UUID-only Celery execution with bounded runtime and conditional terminal writes
  - Complete pre-detector identity and explicit current-versus-historical projection
  - Canonical OpenAPI schema and generated TypeScript preview-job client
affects: [02-12, 02-13, 02-14, 02-15, preview-detectors, admin-configuration]

actuals:
  tokens: 62252
  tasks: 2
  commits: 11

tech-stack:
  added: []
  patterns:
    - PostgreSQL is the public authority for asynchronous job state; Celery carries only a UUID
    - Terminal writes require the complete immutable started identity and live authority
    - Closed request, status, result, and error vocabularies reject noncanonical or secret-bearing data

key-files:
  created:
    - backend/alembic/versions/0006_preview_jobs.py
    - backend/src/verboflex/models/preview_job.py
    - backend/src/verboflex/schemas/previews.py
    - backend/src/verboflex/services/preview_jobs.py
    - backend/src/verboflex/api/v1/routes/admin_previews.py
    - backend/src/verboflex/worker/preview_tasks.py
    - backend/tests/integration/test_preview_jobs.py
    - tools/verify_preview_job_mutants.py
  modified:
    - backend/src/verboflex/models/__init__.py
    - backend/src/verboflex/api/v1/router.py
    - backend/src/verboflex/worker/celery_app.py
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json
    - frontend/src/api/client/types.gen.ts
    - frontend/src/api/client/sdk.gen.ts

key-decisions:
  - "A preview is current only when candidate UUID/version, mapping topology and sides, branches, commits, connection generation, detector/layout versions, digest, and latest attempt all still match live authority."
  - "Successful stale attempts remain inspectable as historical results but can never regain current authority or overwrite a newer attempt."
  - "The pre-detector result is limited to detector_version, digest, and an empty layout_candidates list; detector plans expand that schema deliberately."
  - "Source bytes, credentials, provider bodies, Celery results, canonical rows, and confirmation shortcuts are rejected at both request and persistence boundaries."

patterns-established:
  - "Durable async boundary: commit complete identity, enqueue only the job UUID, and read public status only from PostgreSQL."
  - "Attempt authority: re-check live candidate, connection, mapping, repository sides, digest, and attempt under lock before terminal persistence."
  - "Historical projection: retain successful stale output with is_current=false instead of deleting or presenting it as authoritative."

requirements-completed: [PROD-08, BITB-04]

coverage:
  - id: D1
    description: Durable API-to-PostgreSQL-to-Celery preview skeleton with bounded states, retries, timeouts, and UUID-only transport
    requirement: PROD-08
    verification:
      - kind: integration
        ref: backend/tests/integration/test_preview_jobs.py#test_admin_job_runs_api_to_distinct_worker_and_persists_terminal_state
        status: pass
      - kind: integration
        ref: uv run pytest --randomly-seed=211 -q (488 passed with disposable PostgreSQL 18, Redis 7, and a real Celery worker)
        status: pass
    human_judgment: false
  - id: D2
    description: Complete commit-bound Bitbucket-side identity with race-safe currentness and closed source-free schemas
    requirement: BITB-04
    verification:
      - kind: integration
        ref: backend/tests/integration/test_preview_jobs.py (29 passed)
        status: pass
      - kind: other
        ref: tools/verify_preview_job_mutants.py (9/9 killed; negative control passed)
        status: pass
      - kind: other
        ref: diff-cover against 0cdf584 (94/94 changed production lines and branches)
        status: pass
    human_judgment: false

duration: 2h 14m
completed: 2026-08-27
status: complete
---

# Phase 2 Plan 11: Durable Preview Job Skeleton Summary

**PostgreSQL-authoritative preview attempts now cross a UUID-only Celery boundary, retain inspectable historical results, and expose a closed currentness-aware API and generated client.**

## Performance

- **Duration:** 2h 14m
- **Started:** 2026-08-27T16:10:55Z
- **Completed:** 2026-08-27T18:24:26Z
- **Tasks:** 2
- **Files modified:** 18

## Accomplishments

- Added a migrated durable preview-attempt model and a real admin API → PostgreSQL → Celery → PostgreSQL tracer with soft 60-second and hard 75-second execution limits.
- Bound every attempt to candidate UUID/version, mapping topology, exact repository roles/branches/commits, Bitbucket connection generation, detector/layout identity, digest, and attempt number.
- Made terminal writes conditional on the complete started identity and live authority, while preserving successful stale results as inspectable records with `is_current=false`.
- Closed request, status, result, and error schemas against source bytes, credentials, provider bodies, raw Celery data, canonical translation rows, and confirmation shortcuts.
- Synchronized the canonical OpenAPI document and generated TypeScript client for preview creation and status inspection.

## Task Commits

Each TDD gate and follow-up proof was committed atomically:

1. **Task 1 RED: durable worker tracer** — `756aab8`
2. **Task 1 GREEN: durable preview job tracer** — `0d514c8`
3. **Task 2 RED: race and schema contracts** — `0cdf584`
4. **Task 2 GREEN: complete attempt authority** — `4207730`
5. **Task 2 evidence armor: race/schema mutation proof** — `86a4cbc`
6. **Task 2 evidence armor: currentness branch coverage** — `2cca22d`
7. **Task 2 REFACTOR: decomposed authority checks** — `c7c2f60`
8. **Contract proof: preview OpenAPI and broker isolation** — `228d8cc`
9. **Generated contract: canonical schema and TypeScript client** — `b4fdd72`
10. **Randomized isolation: dedicated Celery test transport** — `1a106a0`
11. **Secret gate maintenance: exact audited fixtures** — `b544d81`

## Files Created/Modified

- `backend/alembic/versions/0006_preview_jobs.py` — Creates the durable preview-attempt table, constraints, and indexes.
- `backend/src/verboflex/models/preview_job.py` — Declares attempt identity, state, result, and timestamps.
- `backend/src/verboflex/services/preview_jobs.py` — Owns idempotency, currentness, state transitions, and conditional terminal persistence.
- `backend/src/verboflex/schemas/previews.py` — Defines closed create/status/result/error contracts.
- `backend/src/verboflex/api/v1/routes/admin_previews.py` — Exposes administrator-only create and inspect operations.
- `backend/src/verboflex/worker/preview_tasks.py` — Loads one durable UUID and runs the bounded processor seam.
- `backend/tests/integration/test_preview_jobs.py` — Proves the tracer, retries, stale races, forbidden data, and currentness outcomes.
- `backend/tests/api/test_openapi_contract.py` — Freezes the preview surface, bearer authority, error responses, fields, and forbidden vocabulary.
- `frontend/openapi.json` and `frontend/src/api/client/` — Canonical generated browser contract.
- `tools/verify_preview_job_mutants.py` — Kills nine targeted authority/schema mutants and includes a negative control.
- `tools/gauntlet.sh` — Tracks deterministic secret-scanner false positives by exact path, line, type, and hash.

## Decisions Made

- Public status is derived exclusively from durable PostgreSQL rows; Celery result state is never exposed or trusted.
- Idempotency reuses the latest nonterminal/nonfailed digest, while a terminal failure permits a higher attempt number for the same complete identity.
- A completed job may remain inspectable after authority changes, but `is_current` is recomputed from live candidate, mapping, connection, and latest-attempt state.
- Format candidates remain an intentionally empty closed list until Plan 02-12 introduces the first detector contract.

## TDD Gate Compliance

- Task 1 RED failed before implementation (`756aab8`), GREEN passed after implementation (`0d514c8`), and its unchanged tracer verification was approved before expansion.
- Task 2 RED failed on forbidden persistence, missing currentness metadata, incomplete terminal identity, and absent explicit model export (`0cdf584`).
- Task 2 GREEN passed the unchanged command with 14 tests (`4207730`); the final exact command passes 29 tests after evidence armor and refactor.
- The REFACTOR gate preserves behavior, removes grade C/D complexity from changed production files, retains 100% changed-line branch coverage, and kills all nine targeted mutants.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added non-vacuous race, schema, branch, and mutation proof**
- **Found during:** Task 2 coverage and mutation gates
- **Issue:** The minimal GREEN did not independently exercise every currentness failure branch or prove that authority/schema mutations would be detected.
- **Fix:** Added negative request/persistence cases, stale authority cases, enqueue recovery, complete branch coverage, and a nine-mutant fail-closed verifier.
- **Files modified:** `backend/tests/integration/test_preview_jobs.py`, `tools/verify_preview_job_mutants.py`
- **Verification:** 29 focused tests, 94/94 changed production lines/branches, 9/9 mutants killed, negative control passed.
- **Committed in:** `86a4cbc`, `2cca22d`

**2. [Rule 3 - Blocking] Reduced new preview service complexity below grade C**
- **Found during:** Task 2 static gauntlet
- **Issue:** Complete role and live-authority validation initially produced grade C/D functions.
- **Fix:** Extracted single-purpose commit, role, candidate, connection, mapping, and identity checks without changing public behavior.
- **Files modified:** `backend/src/verboflex/services/preview_jobs.py`, `tools/verify_preview_job_mutants.py`
- **Verification:** Ruff, mypy, changed-file radon, 29 tests, 100% diff coverage, and 9/9 mutants all pass.
- **Committed in:** `c7c2f60`

**3. [Rule 2 - Missing Critical] Synchronized and froze the browser-facing preview contract**
- **Found during:** Full randomized regression and OpenAPI drift gate
- **Issue:** The new operations were absent from the exact OpenAPI allowlist and canonical generated client, and the worker test could reuse a cached Redis producer under randomized execution.
- **Fix:** Added exact operation/schema/forbidden-field contracts, regenerated the client, and registered the production task entrypoint on a dedicated in-memory Celery test app.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`, `backend/tests/api/test_admin_products.py`, `backend/tests/integration/test_preview_jobs.py`, `frontend/openapi.json`, `frontend/src/api/client/`
- **Verification:** API/preview subset 53/53, OpenAPI drift check, frontend typecheck/lint/format, 75 frontend tests/build, and full backend 488/488 with an external Celery worker.
- **Committed in:** `228d8cc`, `b4fdd72`, `1a106a0`

**4. [Rule 3 - Blocking] Restored the exact global secret-audit policy**
- **Found during:** Supply-chain and secret gate
- **Issue:** Three pre-existing deterministic test fixtures were correctly detected but absent from the exact audited false-positive map, preventing the unexpected-finding negative control from running.
- **Fix:** Added only the exact path/line/type/hash identities for those non-secret test fixtures.
- **Files modified:** `tools/gauntlet.sh`
- **Verification:** Full repository secret scan passes and the injected unexpected finding is rejected.
- **Committed in:** `b544d81`

**Total deviations:** 4 auto-fixed (2 Rule 2, 2 Rule 3).
**Impact on plan:** All changes reinforce correctness, contract stability, test isolation, or fail-closed evidence; no new product behavior was added beyond the planned preview skeleton.

## Issues Encountered

- The first full randomized run exposed both stale OpenAPI allowlists and an in-process Celery worker whose message could be taken by an already-open Redis producer. Exact contract synchronization and a dedicated test app resolved the failures; the third full run passed 488/488.
- `npm audit` reports the already-tracked moderate `qs` advisory only through development-only Stryker tooling. `npm audit --audit-level=high` passes and `npm audit --omit=dev --audit-level=moderate` reports zero production vulnerabilities.

## Verification Evidence

- Exact Task 2 command: `29 passed`.
- Full backend randomized suite: `488 passed` with disposable PostgreSQL 18, Redis 7, and a real Celery worker; migration rehearsal: `3 passed`.
- Architecture and OpenAPI slice: `18 passed`; canonical API drift check passed.
- Backend static gates: Ruff clean, 115 files formatted, mypy clean across 73 source files, changed production complexity below grade C.
- Changed production coverage: `94/94`, 100% line and branch coverage against Task 2 RED.
- Mutation: negative control passed and `9/9` targeted mutants killed.
- Frontend: typecheck, lint, format, 75 randomized tests, generated API drift check, and production build passed.
- Supply chain: `uv lock --check`, `pip-audit` (no known vulnerabilities), license inventory, `npm audit --audit-level=high`, full dependency tree, and production npm audit passed.
- Secret scan: zero findings across Plan 02-11 changed files; exact global audited-policy negative control passed.

## Known Stubs

None. The empty `layout_candidates` collection is the explicit closed pre-detector result contract, not an unwired UI/data stub; Plan 02-12 deliberately expands it.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-12 can replace the deterministic processor seam with the first real detector while reusing durable identity, runtime limits, result authority, and generated client contracts.
- There are no blockers for detector expansion. The existing development-only `qs` advisory remains tracked in `deferred-items.md` and does not affect production dependencies.

## Self-Check: PASSED

- All 18 created/modified plan files exist.
- All 11 task, proof, refactor, and contract commits exist on `codex/phase-2-admin-configuration`.
- The exact Task 2 verification, full randomized backend, migration, OpenAPI, frontend, coverage, mutation, secret, and supply-chain gates are green.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-27*
