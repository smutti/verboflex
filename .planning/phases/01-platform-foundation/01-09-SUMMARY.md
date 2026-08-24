---
phase: 01-platform-foundation
plan: 09
subsystem: api-contract-and-browser-auth
tags: [openapi, generated-client, react, authentication, fast-check, tdd]

requires:
  - phase: 01-platform-foundation/01-08
    provides: Final Phase 1 authenticated API, rate-limit, status, and worker surface
provides:
  - Byte-stable checked-in FastAPI OpenAPI contract and exact-pinned generated TypeScript client
  - Fail-visible API drift and handwritten wire-type boundary guards
  - React-memory-only browser session state machine using generated operations exclusively
  - Property-based authority invariants and narrow credential-persistence guards
affects: [login-ui, password-change-ui, protected-routing, phase-1-gauntlet]

actuals:
  tokens: 19088
  tasks: 2
  commits: 24

tech-stack:
  added:
    - fast-check 4.9.0 (exact dev pin)
  patterns:
    - Explicit stable FastAPI operation IDs feeding a deterministic generated client
    - Versioned asynchronous React authority transitions that reject stale responses
    - Access tokens confined to discriminated React memory state
    - Narrow TypeScript AST guards with positive and negative controls

key-files:
  created:
    - backend/tests/api/test_openapi_contract.py
    - frontend/src/features/auth/session.tsx
    - frontend/src/features/auth/session.test.tsx
    - frontend/src/features/auth/session.property.test.ts
    - frontend/src/features/auth/storage-guard.test.ts
  modified:
    - backend/src/verboflex/api/v1/routes/auth.py
    - backend/src/verboflex/api/v1/routes/health.py
    - backend/src/verboflex/api/v1/routes/system.py
    - backend/src/verboflex/api/v1/routes/users.py
    - frontend/openapi.json
    - frontend/src/api/client
    - frontend/package.json

key-decisions:
  - "Freeze explicit stable operation IDs and regenerate the browser client only from the canonical FastAPI OpenAPI document."
  - "Keep browser access authority exclusively in React memory; restore only through the HttpOnly refresh cookie and authenticated /users/me identity."
  - "Version every asynchronous session operation so logout and newer transitions invalidate stale network completions."
  - "Detect credential persistence with a narrow AST guard that proves both forbidden-surface detection and legitimate-browser-API allowance."

patterns-established:
  - "Contract pipeline: FastAPI application -> canonical sorted OpenAPI bytes -> exact-pinned generated TypeScript client -> fail-on-diff gate."
  - "Authority pipeline: generated auth operation -> in-memory access token -> generated /users/me -> ordinary principal; never infer roles from token claims."
  - "Fail-closed session transitions: restricted, signed-out, and checking states expose no normal principal."

requirements-completed: [PLAT-02, PLAT-03, AUTH-01]

coverage:
  - id: D1
    description: The checked-in OpenAPI and generated client contain exactly the seven approved methods, stable operation IDs, response schemas, and bearer boundaries, and regenerate byte-for-byte.
    requirement: PLAT-02
    verification:
      - kind: contract
        ref: backend/tests/api/test_openapi_contract.py and frontend api:check
        status: pass
    human_judgment: false
  - id: D2
    description: Ordinary, restricted, changed-password, reload, refresh-failure, and logout transitions use generated operations while access authority remains memory-only.
    requirement: AUTH-01
    verification:
      - kind: component
        ref: frontend/src/features/auth/session.test.tsx
        status: pass
    human_judgment: false
  - id: D3
    description: Arbitrary session event sequences cannot expose ordinary identity without an ordinary in-memory token, and non-ordinary states cannot expose a normal principal.
    requirement: AUTH-01
    verification:
      - kind: property
        ref: frontend/src/features/auth/session.property.test.ts
        status: pass
    human_judgment: false
  - id: D4
    description: Handwritten production code cannot persist credentials in Web Storage, IndexedDB object stores, URLs, logs, or analytics while unrelated browser API use remains permitted.
    requirement: PLAT-03
    verification:
      - kind: architecture
        ref: frontend/src/features/auth/storage-guard.test.ts
        status: pass
    human_judgment: false

duration: 19min
completed: 2026-08-24
status: complete
---

# Phase 1 Plan 09: OpenAPI Contract and Memory-Only Browser Session Summary

**The backend/frontend contract is now deterministic and drift-blocking, while every approved browser authentication transition is implemented as generated-client-only, memory-only React state.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-08-24T18:17:41Z
- **Completed:** 2026-08-24T18:36:24Z
- **Tasks:** 2
- **Files modified:** 17
- **Task commits:** 24

## Accomplishments

- Froze exactly seven approved HTTP operations with explicit stable operation IDs, exact response sets, shared error schemas, and intentional OAuth2 bearer boundaries.
- Proved two OpenAPI exports and generated-client runs produce identical tracked bytes, while a controlled operation-ID mutation makes `api:check` fail and a restored clean source makes it pass.
- Implemented ordinary login, temporary restricted login, password replacement, reload restoration, refresh failure, and logout as an explicit discriminated React session state machine using generated operations only.
- Kept access tokens in React memory, used the HttpOnly refresh-cookie flow through central `credentials: "include"` configuration, and accepted roles only from `/users/me`.
- Added fast-check sequence invariants, stale-response invalidation, and a narrowly scoped credential-persistence guard with proved bad and good controls.

## TDD Evidence

### Task 1: Deterministic OpenAPI and generated client

- **RED:** The first exact contract assertion failed because framework-derived operation IDs did not match the approved stable names. The incomplete checked-in schema/client therefore could not satisfy the frozen contract.
- **GREEN:** Explicit operation IDs now produce `issue_token`, `refresh_access_token`, `logout`, `change_password`, `read_health`, `read_current_user`, and `read_system_status`. Canonical sorted compact JSON and the exact `@hey-api/openapi-ts@0.99.0` generator reproduce the tracked schema and client.
- **Contract armor:** Tests assert the exact seven method/path pairs, response codes, shared error `$ref` values, OAuth2 password flow, per-operation bearer security, central credentialed configuration, and absence of handwritten duplicate wire types. A known-bad `AccessTokenResponse` declaration proves the duplicate-type guard reaches its failure seam.
- **Drift negative control:** A temporary source mutation changed the health operation ID to `read_health_drift_control`; `npm run api:check` exited 1 with schema/client diffs. The source was restored with a scoped patch, generation returned green, and the source/generated diff was clean. Two subsequent export/generation passes remained byte-identical.

### Task 2: One transition at a time

1. **Ordinary login + identity:** `40ee956` introduced the failing generated login/`me` expectation; `a2a3bdb` stored the token in memory, loaded server identity, and entered `authenticated`.
2. **Temporary restricted login:** `6a32f8b` failed on temporary-token behavior; `7d5faf2` introduced `password_change_required` without normal principal exposure.
3. **Password change clears authority:** `c71d0d3` failed until `43029f4` used the generated change operation, cleared memory, and returned `signed_out`.
4. **Reload refresh + identity:** `c30d9bd` established the failing restoration contract; `185f3b9` typed the deferred control; `6ef0e1a` restored through generated refresh then `/users/me`; `0c8bb2e` kept failure handling outside the successful path.
5. **Refresh failure:** `8ef3272` failed until `2115171` discarded stale authority and entered `signed_out`.
6. **Logout despite network failure:** `62ddc20` failed until `0e44b93` cleared authority before I/O and retained the clear in `finally`; `3bf7228` removed completed scaffolding.
- **Race armor:** `eb9ffca` reproduced a delayed refresh completing after logout and restoring authority. `b1a4ae8` added operation versioning, so logout immediately invalidates the pending response and remains signed out.

## Property and Storage Evidence

- `fast-check@4.9.0` runs 250 state-machine sequences of up to 100 events each. It asserts that an authenticated principal always has a non-empty ordinary memory token and that checking, restricted, and signed-out states expose no normal principal.
- The initial property RED shrank to a counterexample demonstrating missing authority transitions; the implemented reducer then passed all generated sequences.
- A material mutation removing the ordinary-principal restriction was killed by the property suite, which shrank a restricted-principal counterexample.
- A material mutation removing the post-refresh version check was killed by the delayed-refresh/logout race test because `/users/me` was reached after logout. Both mutations were restored and the focused 11-test suite passed.
- The storage guard parses actual handwritten production TypeScript/TSX and rejects credential writes through Web Storage, IndexedDB object stores, URL parameters/history/location, console output, and analytics/telemetry.
- Its known-bad fixture is detected on all five forbidden surfaces. Its known-good fixture proves theme storage, `indexedDB.open`, language query parameters, and noncredential console/analytics use remain allowed; the guard also asserts that `session.tsx` is actually scanned.

## Task Commits

1. **Task 1 contract RED/GREEN/armor:** `b7f2cfd`, `c51cae1`, `c461673`, `2403bfe`
2. **Task 2 ordered session transitions:** `40ee956`, `a2a3bdb`, `6a32f8b`, `7d5faf2`, `c71d0d3`, `43029f4`, `c30d9bd`, `185f3b9`, `6ef0e1a`, `0c8bb2e`, `8ef3272`, `2115171`, `62ddc20`, `0e44b93`, `3bf7228`
3. **Task 2 property/storage/race armor:** `917be07`, `ec5b941`, `e632670`, `eb9ffca`, `b1a4ae8`

## Files Created/Modified

- `backend/tests/api/test_openapi_contract.py` - exact HTTP surface, security, canonical-byte, generated configuration, and duplicate-type contract.
- `backend/src/verboflex/api/v1/routes/{auth,health,system,users}.py` - explicit stable operation IDs only; no new route was introduced.
- `frontend/openapi.json` and `frontend/src/api/client` - deterministic generated contract artifacts.
- `frontend/src/App.tsx` and `frontend/src/App.test.tsx` - migrated the existing health call site to the stable generated operation name without changing rendering or routing.
- `frontend/src/features/auth/session.tsx` - explicit versioned memory-only session state and generated-operation orchestration.
- `frontend/src/features/auth/session.test.tsx` - ordered user-observable transition and stale-response tests.
- `frontend/src/features/auth/session.property.test.ts` - fast-check authority state invariants.
- `frontend/src/features/auth/storage-guard.test.ts` - narrow AST credential-persistence boundary with bad/good controls.
- `frontend/package.json` and `frontend/package-lock.json` - approved exact fast-check development pin.

## Decisions Made

- Generated operation names are treated as a stable consumer contract rather than framework-derived implementation details.
- Browser code never parses token claims for identity or roles. The token establishes transport authority only; `/users/me` is the server-confirmed principal source.
- Refresh restoration begins in `checking_session` and can reach authenticated authority only after both refresh and identity succeed.
- Every asynchronous operation captures a monotonically increasing version; logout and newer transitions invalidate earlier completions without requiring token decoding or persistent state.

## Final Evidence

- Full backend regression: **206 passed**.
- `uv run ruff check .`: pass.
- `uv run mypy src tests`: no issues across **57 source files**.
- OpenAPI contract: **4 passed**.
- `npm run api:check`: deterministic generation and tracked drift gate pass.
- Focused session/property/storage suite: **11 passed**.
- Full frontend regression: **15 passed** across 4 files.
- `npm run typecheck`: pass.
- `npm run build`: production Vite build pass.
- `npm audit --audit-level=high`: **0 vulnerabilities**.
- Cleanup: the plan-owned Celery worker stopped and the isolated Redis/PostgreSQL containers were stopped and auto-removed; no matching process or container remains.

## Security Evidence

- **T-07-01 / stale generated client:** byte-stable canonical export, exact pinned generator, checked-in artifacts, fail-on-diff script, and a controlled drift failure prove the boundary.
- **T-07-02 / browser credential disclosure:** access tokens exist only in React memory, refresh authority remains in the HttpOnly cookie flow, and a narrow AST guard rejects credential persistence/logging.
- **T-07-03 / authority elevation:** discriminated states plus fast-check invariants prevent normal principal exposure from restricted or signed-out authority; operation versioning prevents stale response resurrection.
- **T-07-04 / client-authoritative roles:** roles and principal data come exclusively from generated `/users/me`; browser code does not parse access-token claims.

## API Gate Resolution

- **Surface:** exactly seven previously approved method/path pairs; no framework, admin, accidental, or duplicate route was admitted.
- **Authentication:** exact per-operation OAuth2 security remains frozen; cookie credentials are configured centrally for generated requests.
- **Errors:** every approved stable 400/401/403/422/429/503 response maps to the shared `ErrorResponse` schema where applicable.
- **Compatibility:** stable explicit operation IDs required a generated health call-site rename in the existing app/test. This is a greenfield internal client migration, with no ungenerated consumer type retained.
- **Non-applicable concerns:** no new pagination, idempotency-key, versioning, deprecation, or public rate-limit policy was introduced in this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Migrated the existing health consumer to the stable generated operation**

- **Found during:** Task 1 generated-client typecheck.
- **Issue:** Freezing `read_health` changed the generated export name, so the pre-existing scaffold import no longer compiled.
- **Fix:** Updated only the generated import/call in `App.tsx` and its test; routing and rendering remained unchanged.
- **Verification:** Frontend typecheck, all 15 tests, and production build pass.
- **Committed in:** `c51cae1`.

**2. [Rule 2 - Missing Critical] Rejected stale asynchronous authority after logout**

- **Found during:** Task 2 adversarial race review.
- **Issue:** A refresh already in flight could complete after logout and continue into identity loading.
- **Fix:** Added per-operation version capture and invalidation, with authority cleared synchronously at logout start.
- **Verification:** The delayed-refresh negative test failed before the fix and passes after it; removing the post-refresh check kills the test again.
- **Committed in:** `eb9ffca`, `b1a4ae8`.

**3. [Rule 3 - Blocking] Narrowed the OpenAPI test helper for strict static typing**

- **Found during:** Final mypy gate.
- **Issue:** The JSON dictionary helper returned `Any` despite declaring `str | None`.
- **Fix:** Return the `$ref` only after an explicit `isinstance(..., str)` check.
- **Verification:** Contract tests pass and strict mypy reports no issues across 57 source files.
- **Committed in:** `2403bfe`.

---

**Total deviations:** 3 auto-fixed (1 missing critical, 2 blocking)
**Impact on plan:** All fixes preserve the approved API/auth architecture and add no new route, rendering responsibility, or unapproved runtime dependency.

## Issues Encountered

- Python 3.14's local prefork Celery test worker exited with a platform-level segmentation fault, so the already-supported `solo` pool was used only for the isolated test worker. Application code and production configuration were unchanged, and the full worker-backed backend suite passed.
- During restoration of the first one-off property mutation, an overly broad patch initially placed the principal condition on the wrong reducer arm. The immediate focused rerun failed three tests, the source was corrected precisely, and the complete 11-test focused suite plus typecheck passed from a clean source state. This restoration failure demonstrates that the post-mutation clean-state gate was effective.

## User Setup Required

None - no external configuration or service account is required.

## Next Phase Readiness

- Plans 01-11 and 01-12 can consume the session provider for login, forced-password-change, and protected route/rendering work without owning token persistence or handwritten API calls.
- The Phase 1 gauntlet can treat OpenAPI drift, generated-client-only auth operations, state invariants, and credential-storage boundaries as executable guarantees.
- No Plan 01-09 blocker remains.

## Self-Check: PASSED
