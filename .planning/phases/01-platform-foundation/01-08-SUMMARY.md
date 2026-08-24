---
phase: 01-platform-foundation
plan: 08
subsystem: api-infrastructure
tags: [fastapi, rate-limits, redis, celery, service-status, tdd]

requires:
  - phase: 01-platform-foundation/01-07
    provides: Internal OAuth2 authority, refresh lifecycle, PostgreSQL principals, and Redis-authenticated action limits
provides:
  - Exact bounded rate policies for anonymous health, protected reads, and sensitive auth actions
  - Authenticated non-leaking database, Redis, and Celery worker service status
  - JSON-only non-eager Celery application with a real Redis/out-of-process execution proof
affects: [frontend-status, background-imports, pull-request-jobs, deployment-smoke, security-audit]

actuals:
  tokens: 12133
  tasks: 3
  commits: 33

tech-stack:
  added: []
  patterns:
    - Redis-authoritative limits with policy-specific bounded local fallback only for safe reads
    - Server-principal and validated peer-derived limiter keys that never trust forwarded headers implicitly
    - Concurrent independently timeout-bounded probes projected onto non-leaking public enums
    - Named JSON-only Celery tasks executed by a distinct non-eager worker process

key-files:
  created:
    - backend/src/verboflex/services/system_status.py
    - backend/src/verboflex/worker/__init__.py
    - backend/src/verboflex/worker/celery_app.py
    - backend/src/verboflex/worker/tasks.py
    - backend/tests/api/test_rate_limits.py
    - backend/tests/api/test_system_status.py
    - backend/tests/architecture/test_background_boundaries.py
    - backend/tests/worker/test_smoke_task.py
  modified:
    - backend/src/verboflex/auth/rate_limits.py
    - backend/src/verboflex/api/v1/routes/auth.py
    - backend/src/verboflex/api/v1/routes/health.py
    - backend/src/verboflex/api/v1/routes/users.py
    - backend/src/verboflex/api/v1/routes/system.py

key-decisions:
  - "Anonymous health uses a 60/minute bounded process-local limit; ordinary authenticated reads use Redis at 120/minute with a cardinality-bounded local outage fallback; sensitive auth actions remain Redis fail-closed."
  - "Rate-limit identity comes only from normalized authenticated authority or the syntactically validated server-observed peer; forwarded IP headers remain untrusted until an explicit trusted-proxy policy exists."
  - "Public status exposes only online, unavailable, or pending plus a UTC timestamp; each database, Redis, and worker probe has an independent timeout and no diagnostic payload crosses the API boundary."
  - "Celery uses JSON serializers, Redis broker/results, named tasks, and production eager=false; task bodies remain outside every FastAPI route module."

patterns-established:
  - "Before-work limiting: resolve server authority, consume the exact rate bucket, and reject N+1 before endpoint or probe work."
  - "Operational projection: keep raw dependency diagnostics behind a timeout-bounded service seam and return only approved enums."
  - "Background boundary: producers address named tasks through Redis while a distinct worker process imports and runs task bodies."

requirements-completed: [PLAT-03, PLAT-06, AUTH-01]

coverage:
  - id: D1
    description: Every implemented Phase 1 endpoint has its exact inclusive rate boundary, reset behavior, stable 429 metadata, safe key derivation, and outage disposition.
    requirement: PLAT-03
    verification:
      - kind: integration
        ref: backend/tests/api/test_rate_limits.py and backend/tests/auth/test_login.py, test_refresh.py, test_logout.py, test_password_change.py
        status: pass
    human_judgment: false
  - id: D2
    description: An ordinary authenticated user receives a timeout-bounded non-leaking database, Redis, and worker status projection while missing or restricted authority is denied.
    requirement: PLAT-03
    verification:
      - kind: integration
        ref: backend/tests/api/test_system_status.py
        status: pass
    human_judgment: false
  - id: D3
    description: The named sample task returns 5 for 2+3 through Redis and a distinct Celery worker, never through an HTTP route or eager production execution.
    requirement: PLAT-06
    verification:
      - kind: integration
        ref: backend/tests/worker/test_smoke_task.py and backend/tests/architecture/test_background_boundaries.py
        status: pass
    human_judgment: false
  - id: D4
    description: Existing login, refresh, logout, and password-change authority contracts preserve their exact Redis failure and rate-limit behavior.
    requirement: AUTH-01
    verification:
      - kind: integration
        ref: backend/tests/auth/test_login.py, test_refresh.py, test_logout.py, and test_password_change.py
        status: pass
    human_judgment: false

duration: 33min
completed: 2026-08-24
status: complete
---

# Phase 1 Plan 08: Bounded Operations and Celery Execution Summary

**Exact endpoint blast-radius controls, authenticated non-leaking service status, and real Redis-to-worker Celery execution now complete the backend operations foundation.**

## Performance

- **Duration:** 33 min
- **Started:** 2026-08-24T17:34:47Z
- **Completed:** 2026-08-24T18:07:44Z
- **Tasks:** 3
- **Files modified:** 13
- **Task commits:** 33

## Accomplishments

- Applied exact 60/minute anonymous health and 120/minute ordinary authenticated read policies with inclusive N/N+1 boundaries, exact reset behavior, stable `Retry-After`/`X-RateLimit-Remaining` responses, bounded local fallback, and before-work rejection.
- Replaced the callable `/system/status` 501 seam with an ordinary-authenticated projection of API, database, Redis, and worker state, limited to approved enums and a UTC timestamp under independent probe timeouts.
- Added a typed-settings Celery app and named `verboflex.add` task, then proved `2 + 3 = 5` across Redis and a distinct worker process with a hard result timeout and architecture guards against HTTP-inline/eager work.
- Preserved all existing login, refresh, logout, password-change, `/users/me`, and `/health` contracts while adding safe Redis network bounds and server-observed peer validation.

## TDD Evidence

### Task 1: Exact endpoint rate policies

- **RED:** `/health` request 61 initially remained 200; `/users/me` and `/system/status` request 121 remained unbounded; Redis outage bypass/failure cases and malformed peer identity were isolated as their own failing contracts.
- **GREEN:** Health now uses a 60-second bounded local fixed window. Protected reads use Redis at 120/minute keyed by a hash of the authenticated server principal and fall back to a 2,048-key local LRU window only when Redis is unavailable. Sensitive auth actions preserve their pre-existing Redis fail-closed policy.
- **REFACTOR:** Shared ordinary-read limiting, stable 429 construction, and validated peer extraction were centralized. Untrusted `X-Forwarded-For` is ignored, exact reset occurs at `>= window`, and request N+1 stops before status probes.
- **Armor:** Endpoint tests assert N and N+1, reset at exactly 60 seconds, stable recovery headers, no raw user id in Redis keys, zero downstream probes on blocked status, local cardinality eviction, and invalid policy rejection.

### Task 2: Authenticated service status

- **RED:** The first exact authenticated `GET /api/v1/system/status` assertion observed the intentionally callable 501 response. Later REDs isolated raw/invalid probe values, timeout behavior, auth rejection, Redis socket bounds, and the static worker-pending seam.
- **GREEN:** The endpoint now returns exactly `api`, `database`, `redis`, `worker`, and `checked_at`. Database, Redis, and worker probes run concurrently, each through `asyncio.wait_for` plus dependency-specific network timeout configuration, and every exception or invalid value maps to `unavailable`.
- **Projection:** Only `online`, `unavailable`, or `pending` can leave the service boundary. Tests prove DSNs, hostnames, ports, exceptions, stack data, and task identifiers never appear.
- **Authority:** Missing bearer authority returns the shared exact 401; password-change-purpose authority returns the shared exact 403; ordinary authenticated users can read status without an admin-role requirement.

### Task 3: Real Celery/Redis execution

- **Unit RED/GREEN:** The named task callable first raised `NotImplementedError`; the minimal implementation then returned exactly 5 for arguments 2 and 3.
- **Transport RED:** With Redis reachable but no worker running, `AsyncResult.get(timeout=5)` failed meaningfully with `celery.exceptions.TimeoutError`, proving the assertion exercised transport/result behavior rather than imports, setup, or a local call.
- **Transport GREEN:** A distinct process named `verboflex-plan08@...` connected to Redis on the plan-owned test port, consumed the named task, and returned 5 in 0.20 seconds. `celery inspect ping --timeout=2` reported exactly one online node and `pong`.
- **Worker status:** The default status service now invokes a bounded Celery control ping through a non-HTTP service bridge. Live reply projects `online`; no reply/exception projects `unavailable`; injected `pending` remains a valid bounded seam state.
- **Architecture:** AST guards reject any FastAPI route importing worker modules or calling `.delay()`, `.apply_async()`, or `.run()`. Configuration guards require `task_always_eager is False` and distinct backend/worker Compose commands. Deliberate negative controls for an API worker import and eager mode both failed before restoration.

## Task Commits

1. **Task 1 rate RED/GREEN/refactor:** `ea8d0dd`, `0906723`, `bb0d58d`, `722a8da`, `315735e`, `7446b7d`, `f9d3708`, `fccc57b`, `4e06604`, `cceef61`, `a404b2b`, `af11f6b`, `68a58e1`, `4075fdc`
2. **Task 2 status RED/GREEN/armor:** `a871ece`, `9f86874`, `a1eb0c7`, `ca25637`, `e8f2b05`, `d90f24d`, `e55a24c`, `105dbb7`, `1fbde48`, `ef5ab0d`
3. **Task 3 worker RED/GREEN/architecture:** `796412c`, `04f7ee4`, `27b8af9`, `767d511`, `6dbf33e`, `ca8d112`, `ef9c9fc`, `36e138e`, `d68a1c7`

## Files Created/Modified

- `backend/src/verboflex/auth/rate_limits.py` - exact Redis/local policies, bounded local windows, safe peer validation, stable exhaustion response, and Redis socket bounds.
- `backend/src/verboflex/api/v1/routes/auth.py` - server-observed validated peer identity for sensitive auth limits.
- `backend/src/verboflex/api/v1/routes/health.py` - constant health response behind the exact anonymous limiter.
- `backend/src/verboflex/api/v1/routes/users.py` - protected identity read behind Redis-first ordinary limiting.
- `backend/src/verboflex/api/v1/routes/system.py` - exact authenticated status response behind before-probe limiting.
- `backend/src/verboflex/services/system_status.py` - independent timeout aggregation, safe enum projection, and non-HTTP worker bridge.
- `backend/src/verboflex/worker/celery_app.py` - typed Redis broker/backend configuration, JSON-only non-eager execution, and bounded worker ping.
- `backend/src/verboflex/worker/tasks.py` - deterministic named `verboflex.add` task.
- `backend/tests/api/test_rate_limits.py` - endpoint boundaries, reset, key safety, outage, ordering, and cardinality armor.
- `backend/tests/api/test_system_status.py` - exact projection, state transitions, timeout, leak, auth, and wiring contracts.
- `backend/tests/worker/test_smoke_task.py` - pure task, live transport/result, worker online, and no-reply status proof.
- `backend/tests/architecture/test_background_boundaries.py` - API/worker import-call, eager-mode, and process-command constraints.

## Decisions Made

- Health remains independent of Redis and service readiness, with its exact constant body preserved behind a bounded local limiter.
- Redis failure does not disable safe ordinary diagnostics, but it never relaxes login, refresh, logout, or password-change policies beyond their previously approved endpoint-specific dispositions.
- Operational readiness is an enum projection, not a diagnostics endpoint; Celery inspect dictionaries, broker URLs, task ids, database details, and exception strings stay internal.
- Worker discovery lives behind the service layer so FastAPI routes do not import worker/task modules, preserving a one-way HTTP-to-service architecture boundary.

## Mutation and Coverage Evidence

- Thresholded scoped coverage: **99 passed**, **197/197 statements**, **20/20 branches**, **100%** across every plan-owned route, limiter, status-service, Celery app, and task module.
- Full randomized backend regression: **202 passed**. Frontend regression: **4 passed**; production Vite build succeeded.
- Material one-off mutation `current.attempts <= limit` to `< limit` was killed by the exact health boundary test at request 60.
- Material one-off mutation from live worker `online` to `unavailable` was killed by the real Celery worker probe test.
- Earlier focused mutations removing the independent status timeout and altering exact reset/untrusted-forwarded-IP behavior were killed before their armor commits. No selected material boundary mutation survived; internal exception-message rewrites were not promoted into public-contract assertions.

## Final Evidence

- Plan/auth focused suite - **65 passed**.
- Worker plus architecture plan command - **6 passed** before status aggregation; final combined worker/status/architecture suite - **14 passed**.
- Full backend suite - **202 passed**.
- Scoped statement/branch coverage - **100%** over 197 statements and 20 branches.
- `uv run ruff check src tests` and `uv run ruff format --check src tests` - pass; 56 files formatted.
- `uv run mypy src tests` - no issues across 56 source files; untyped Celery is isolated behind two narrow boundary suppressions.
- `uv run radon cc ...` - average A (2.25); highest block is `BoundedLocalRateLimiter.check` at B7.
- `npm run api:check` - generated OpenAPI/client is drift-free.
- `npm test -- --run` and `npm run build` - 4 frontend tests pass and the production bundle builds.
- `docker compose config --quiet` - deployment definition parses cleanly with distinct API/worker commands.
- `uv run pip-audit` - no known vulnerabilities; the local non-PyPI application package is intentionally skipped.
- `uv run pip-licenses --summary` - dependency inventory completed; this plan added no dependency.
- `detect-secrets` - zero findings in plan-owned production files.
- Source/stub/leak scan - no TODO, FIXME, 501, `NotImplemented`, raw broker/DSN/port, stack, or task-id surface in plan-owned production status code.
- Cleanup - the distinct local worker exited cleanly and plan-owned Redis/PostgreSQL containers were stopped and auto-removed; no matching process or container remains.

## Security Evidence

- **T-06-01 / denial of service:** exact endpoint N/N+1 boundaries, stable reset metadata, bounded local actor cardinality, Redis-first protected keys, validated peers, and before-work ordering are executable contracts.
- **T-06-02 / information disclosure:** public status schemas and runtime validation accept only approved enums/timestamp; hostile probe strings and exceptions cannot cross the boundary.
- **T-06-03 / slow dependencies:** every probe has an independent coroutine timeout, Redis has connect/command socket timeouts, Celery inspect receives a control timeout, and the three slow probes complete within one concurrent budget.
- **T-06-04 / task tampering and inline work:** Celery accepts/results only JSON, production eager mode is false, task addressing is by stable name, and AST negative controls prevent FastAPI task imports or inline calls.
- **Identity/key safety:** login combines normalized email with a validated server-observed IP; protected reads derive identity from the resolved principal; raw email, user id, bearer token, forwarded IP, and task id are absent from limiter/status output.

## API Gate Resolution

- **Surface:** `/health` keeps its exact constant contract; `/users/me` keeps its safe identity contract; `/system/status` moves from callable 501 to the approved exact authenticated schema.
- **Authentication:** status and identity use ordinary bearer authority; password-change-purpose authority remains restricted. No role escalation or Microsoft/OIDC coupling was introduced.
- **Rate limits:** health 60/minute; ordinary identity/status reads 120/minute; login 5/minute; refresh 30/minute; logout/password change 10/minute, with each endpoint's approved Redis outage disposition preserved.
- **Compatibility:** OpenAPI/client generation reports zero drift; no new version, dependency, pagination, idempotency, or deprecation surface was introduced.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Bounded the synchronous Redis transport itself**

- **Found during:** Task 2 timeout armor.
- **Issue:** Coroutine timeout alone cannot stop a blocking synchronous Redis socket call after its worker thread is detached.
- **Fix:** Added configured connect and command socket timeouts to the shared Redis client.
- **Verification:** `test_redis_client_enforces_configured_connect_and_command_timeouts` and all auth/status suites pass.
- **Committed in:** `1fbde48`, `ef5ab0d`.

**2. [Rule 3 - Blocking] Preserved the API/worker architecture while wiring live worker status**

- **Found during:** Task 3 final architecture gate.
- **Issue:** A first worker-status wiring imported the Celery application directly from the FastAPI route, and the architecture test rejected both worker imports.
- **Fix:** Moved worker discovery behind a lazy service-layer bridge; routes now import only the status service.
- **Verification:** Final architecture suite passes; the deliberate direct-import negative control fails.
- **Committed in:** `ca8d112`.

**3. [Rule 3 - Blocking] Isolated Celery's untyped runtime boundary**

- **Found during:** Final strict mypy gate.
- **Issue:** Celery 5.6.3 does not publish `py.typed`, so strict analysis rejected the runtime import and task decorator.
- **Fix:** Added narrow, code-specific suppressions only at the untyped import/decorator boundary; application and task signatures remain typed.
- **Verification:** Strict mypy passes across 56 source files.
- **Committed in:** `36e138e`.

---

**Total deviations:** 3 auto-fixed (1 missing critical, 2 blocking)
**Impact on plan:** All fixes are within the approved dependency and architecture boundary; no scope or direct dependency was added.

## Issues Encountered

- The pure task implementation preceded the architecture-test commit, although both negative architecture controls were exercised before worker-status integration and failed exactly under injected violations. The live Redis transport behavior itself preserved strict no-worker RED before distinct-worker GREEN.
- The full-project coverage command still includes the inherited `verboflex.scripts.export_openapi` entrypoint, which Plan 01-03 explicitly left for the final Phase 1 gauntlet. The thresholded Plan 01-08 module set is 100% statements and branches; Plan 01-14/01-15 retain the global-entrypoint gate.

## User Setup Required

None - no external service configuration or dependency installation is required.

## Next Phase Readiness

- Plan 01-09 can generate the complete frontend API contract over final authenticated rate/status behavior.
- Later import and pull-request phases have a proven named-task, Redis transport, non-eager worker, timeout, and status boundary to extend.
- Phase 1 final gauntlet still owns entrypoint-wide coverage/mutation consolidation and independent verification; no Plan 01-08 blocker remains.

## Self-Check: PASSED

- All key files exist and every task has committed RED/GREEN or armor evidence.
- Every plan acceptance criterion and plan-level verification command is green.
- Real worker/Redis execution returned 5, deployment/frontend smokes passed, and all plan-owned resources were removed.

## PLAN COMPLETE

---
*Phase: 01-platform-foundation*
*Completed: 2026-08-24*
