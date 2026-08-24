---
phase: 01-platform-foundation
plan: 04
subsystem: infrastructure
tags: [pydantic-settings, docker, compose, security, tdd]

requires:
  - phase: 01-platform-foundation
    plan: 03
    provides: Locked backend and frontend applications with health contracts
provides:
  - Typed fail-closed local, staging, and production settings
  - Multi-stage non-root backend and frontend container images
  - Shared five-service Compose topology with named staging and production overlays
affects: [authentication, celery, deployment, service-status]

actuals:
  tokens: 5368
  tasks: 2
  commits: 26

tech-stack:
  added: []
  patterns:
    - Validate deployment security policy while constructing immutable settings
    - Share one backend image between API and worker but keep one process per service
    - Require deploy-time credentials through overlays without shipping usable defaults

key-files:
  created:
    - backend/src/verboflex/core/config.py
    - backend/tests/core/test_config.py
    - docker/backend.Dockerfile
    - docker/frontend.Dockerfile
    - docker-compose.yml
    - docker-compose.staging.yml
    - docker-compose.prod.yml
    - .env.example
  modified:
    - .gitignore
    - .planning/WINDOWS.md

key-decisions:
  - "Staging and production reject missing, sentinel, or shorter-than-32-byte JWT secrets and reject an insecure refresh cookie before serving."
  - "CORS configuration accepts only an explicit non-empty list of exact HTTP(S) origins without paths, query strings, fragments, or credentials."
  - "API and worker reuse the same backend image but declare distinct uvicorn and Celery commands and independent health checks."
  - "Local HTTP may disable Secure only through explicit local configuration; deployment overlays default Secure to true and remain fail-closed when overridden."

patterns-established:
  - "Security settings: parse strongly typed values first, then apply cross-field environment policy in a model validator."
  - "Docker topology: provider-neutral base Compose plus named staging/production overlays, with no hosting-provider scope."

requirements-completed: [PLAT-01, PLAT-06]

coverage:
  - id: D1
    description: Staging and production fail closed for every missing, sentinel, short-secret, and insecure-cookie case
    requirement: PLAT-01
    verification:
      - kind: unit
        ref: "backend/tests/core/test_config.py"
        status: pass
      - kind: other
        ref: "deployment startup subprocess matrix"
        status: pass
    human_judgment: false
  - id: D2
    description: Local, staging, and production-oriented five-service topologies render with health checks
    requirement: PLAT-01
    verification:
      - kind: other
        ref: "docker compose config for base, staging, and production"
        status: pass
    human_judgment: false
  - id: D3
    description: API and worker share an image while retaining distinct one-process commands and lifecycle probes
    requirement: PLAT-06
    verification:
      - kind: other
        ref: "semantic Compose JSON assertion and backend image build"
        status: pass
    human_judgment: false

duration: 24 min
completed: 2026-08-24
status: complete
---

# Phase 1 Plan 4: Secure Docker and Settings Baseline Summary

**VerboFlex now has immutable typed settings that fail closed in deployed environments and a validated provider-neutral five-service Docker topology with independently managed API and worker processes.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-08-24T15:12:43Z
- **Completed:** 2026-08-24T15:36:10Z
- **Tasks:** 2
- **Files modified:** 9 before plan close-out metadata

## Accomplishments

- Added typed environment, PostgreSQL, Redis, exact-origin CORS, token lifetime, service timeout, cookie, algorithm, and secret settings with frozen cached construction.
- Proved staging and production reject absent, documented-sentinel, shorter-than-32-byte signing material and insecure refresh cookies, while local HTTP requires an explicit insecure-cookie choice.
- Added multi-stage, non-root backend and frontend images plus a shared frontend/backend/worker/PostgreSQL/Redis Compose topology and staging/production overlays without real credentials.
- Rendered and semantically inspected all three topologies, built both images, and observed healthy backend and frontend containers.

## Task Commits

Task 1 preserves one-behavior-at-a-time RED/GREEN chronology:

- **Typed local settings:** `9258d87`, `0b51a4a`, `726c425`, `d4a1d6a`
- **Non-empty and exact CORS:** `1178b6f`, `cab5d4f`, `5d83e46`, `a733337`
- **Named PostgreSQL and Redis targets:** `0d8382a`, `d649bcf`, `9a0713f`, `2428584`
- **Timing regression armor:** `4945ea2`
- **Required, non-sentinel, 32-byte deployment secret:** `6fecbc6`, `7b2ed98`, `5c00c92`, `9eb4859`, `1fbaa72`, `0712ba4`
- **Secure deployment cookie:** `5f3acec`, `cc48fc1`, `b514ed8`
- **Environment boundary:** `c1c6733`

Task 2 and final assurance commits:

- **Docker topologies and images:** `b7f041c`
- **Generated short-secret property:** `7787629`
- **Cached immutable settings guard:** `e94c5a6`

## RED/GREEN Evidence

- Every missing, sentinel, short-secret, and insecure-cookie policy began with a collected behavioral failure, followed by the minimum validator change and a focused GREEN run.
- Typed URL and timing behaviors were split into focused slices; no RED was caused by collection or import failure.
- The first exact-CORS implementation exposed a real normalized-root-path edge (`/`) during its focused run; the validator was corrected before GREEN without weakening the test.
- Four immediately-green or regression behaviors were challenged with throwaway mutants: timing constraints removed, secure-cookie polarity inverted, the 32-byte comparison disabled, and settings caching removed. All four mutants were killed, restored, and followed by green focused tests.
- Hypothesis generated printable ASCII secrets at every length through 31 bytes and proved all are rejected in staging and production.

## TDD Gate Compliance

- Meaningful tests preceded each policy implementation and RED/GREEN commits remain separately reviewable.
- Tests and implementations were not combined to manufacture a GREEN result.
- No assertion was skipped, weakened, or broadened.
- Final focused settings coverage is 100% statements and 100% branches with 31 passing cases; the full backend suite has 32 passing tests.

## Files Created/Modified

- `backend/src/verboflex/core/config.py` - Immutable typed settings and deployed-environment security policy.
- `backend/tests/core/test_config.py` - Example, matrix, boundary, property, cache, and immutability contracts.
- `.env.example` / `.gitignore` - Visibly invalid examples and ignored real environment files.
- `docker/backend.Dockerfile` - Exact-lock, non-root Python runtime used by API and worker.
- `docker/frontend.Dockerfile` - Locked Node build and nginx runtime.
- `docker-compose.yml` - Shared five-service local topology with independent lifecycle checks.
- `docker-compose.staging.yml` / `docker-compose.prod.yml` - Named fail-closed deployment overlays.
- `.planning/WINDOWS.md` - Records the intentional worker-module seam until Plan 01-08.

## Decisions Made

- Deployment signing material is measured in UTF-8 bytes, not Python characters, and must contain at least 32 bytes after sentinel screening.
- Database and Redis URLs are strongly typed and must select explicit databases; Redis database indexes must be non-negative decimal paths.
- Allowed CORS entries are origins, not arbitrary URLs, and may not contain path, query, fragment, or embedded credentials.
- Staging and production overlays expose required secret/password seams but never provide a usable fallback credential.
- API and worker share a build artifact while their commands, ports, and health semantics remain independent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Accepted normalized origin root safely**
- **Found during:** exact-CORS focused GREEN attempt
- **Issue:** Pydantic normalizes a bare origin to `/`; the first validator incorrectly treated that normalization as a user-supplied path.
- **Fix:** Allow only the normalized empty/root path while continuing to reject every non-root path, query, fragment, and credential.
- **Verification:** exact-origin focused tests and the complete 31-case settings suite pass.
- **Committed in:** `a733337`

**Total deviations:** 1 auto-fixed correctness issue. **Impact:** No scope expansion and the exact-origin security boundary remains stricter than a generic URL.

## Issues Encountered

- `mutmut` copied the target module but did not instrument decorated Pydantic validator methods under the requested module filter; it reported no relevant generated mutants. Per the assurance protocol, the layer is recorded as unavailable and replaced by four targeted manual mutation probes, all killed.
- An initial `detect-secrets --all-files` invocation traversed ignored virtual environments, caches, and mutation artifacts and therefore produced irrelevant dependency findings. The final fail-closed scan targeted the nine plan files explicitly and reported zero findings.

## Verification Results

- `uv run pytest tests/core/test_config.py --cov=verboflex.core.config --cov-branch --cov-report=term-missing --cov-fail-under=100` - 31 passed; 100% statements and branches; seed 2300786854
- `uv run pytest -q` - 32 passed
- `uv run mypy src tests` - pass across 16 files
- `uv run ruff check src tests` / `uv run ruff format --check src tests` - pass
- `uv run radon cc ...` - average B 5.17; highest method B9
- `uv run pip-audit` - no known vulnerabilities; the local project package is intentionally not registry-auditable
- Scoped `detect-secrets` scan - zero findings
- `npm run test -- --run --sequence.shuffle --sequence.seed=104` - 4 passed
- `npm run api:check`, `npm run typecheck`, `npm run build` - pass; no generated API drift
- `npm audit` - zero vulnerabilities
- Base, staging, and production `docker compose ... config` commands - pass
- Semantic Compose assertion - exactly five health-checked services; shared backend image; distinct API/worker commands; no worker port
- `docker build --check` and full image builds for both Dockerfiles - pass with no warnings
- Backend container - healthy as non-root with the exact health JSON
- Frontend container - healthy and served the built SPA
- Deployment startup matrix - staging and production reject missing/sentinel/31-byte/insecure-cookie cases and start with a strong secret plus Secure cookie

## API Gate Resolution

- **Scope:** no HTTP method, path, request, response, status, authentication, or authorization signature changed.
- **Compatibility:** pass; the existing generated OpenAPI contract remains drift-free.
- **Boundary:** settings now protect later authentication token and cookie implementations before server startup; no credential or diagnostic is exposed through HTTP.
- Pagination, idempotency, rate limiting, and deprecation gates are not applicable because this plan adds no endpoint behavior.

## Known Stubs

- `docker-compose.yml` declares the final Celery command and healthcheck target for `verboflex.worker.celery_app`; the module and executable sample task are intentionally delivered by Plan 01-08. The seam is recorded in `.planning/WINDOWS.md` and does not block this plan's render/image/lifecycle acceptance criteria.

## User Setup Required

- Local execution may copy `.env.example` to an ignored environment file.
- Staging and production operators must supply a strong `VERBOFLEX_JWT_SECRET_KEY` and non-placeholder PostgreSQL password through their deployment environment; no external provider configuration is introduced.

## Next Phase Readiness

- Plan 01-05 can build the auth schema and bootstrap CLI against stable typed database and security settings.
- Plan 01-08 owns the recorded Celery module seam and can start the already-separated worker service without changing topology.
- No unresolved blocker remains for the next plan.

## Self-Check: PASSED

- All nine plan artifacts exist and all 26 pre-close-out commits resolve.
- Final source verification, security scans, builds, topology renders, and container smokes passed after the last source edit.
- The worktree contains only plan close-out metadata plus the orchestrator-owned, intentionally uncommitted `.planning/milestone.lock`.

---
*Phase: 01-platform-foundation*
*Completed: 2026-08-24*
