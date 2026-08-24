---
phase: 01-platform-foundation
plan: 07
subsystem: auth
tags: [fastapi, postgresql, redis, jwt, argon2, refresh-rotation, tdd]

requires:
  - phase: 01-platform-foundation/01-06
    provides: Signed access tokens, durable session principals, login limiting, and password policy primitives
provides:
  - One-time opaque refresh-token rotation with hashed storage and replay-family revocation
  - Idempotent logout that clears ambient cookies and revokes sid-bearing access authority
  - Atomic password replacement with policy enforcement and global authority invalidation
affects: [authorization, frontend-session-client, deployment-smoke, security-audit]

actuals:
  tokens: 19127
  tasks: 3
  commits: 17

tech-stack:
  added: []
  patterns:
    - Exact Origin then Redis then PostgreSQL ordering for cookie-authenticated mutations
    - PostgreSQL row-lock serialization for one-time refresh authority
    - User-row lock plus one transaction for credential and authority replacement

key-files:
  created:
    - backend/src/verboflex/auth/origin.py
    - backend/src/verboflex/auth/refresh_sessions.py
    - backend/src/verboflex/auth/password_change.py
    - backend/tests/auth/test_refresh.py
    - backend/tests/auth/test_logout.py
    - backend/tests/auth/test_password_change.py
    - backend/tests/integration/test_refresh_concurrency.py
  modified:
    - backend/src/verboflex/auth/rate_limits.py
    - backend/src/verboflex/api/v1/routes/auth.py

key-decisions:
  - "Refresh credentials are 32 random bytes encoded as 43 URL-safe characters and only their SHA-256 digests are durable."
  - "A used refresh predecessor is a replay signal: revoke its entire family before returning the stable 401 surface."
  - "Logout stays available during Redis outage, while refresh and password change fail closed before PostgreSQL or Argon2."
  - "Password-change-purpose authority is accepted only by change-password and is reconciled with current user state before mutation."

patterns-established:
  - "Ambient-cookie mutation boundary: exact Origin allowlist, absent Origin for non-browser clients, action limiter, then database work."
  - "Authority replacement: lock the current durable authority, mutate all related state in one transaction, and issue/clear cookies only after success."

requirements-completed: [PLAT-03, AUTH-01]

coverage:
  - id: D1
    description: Refresh tokens rotate once, remain hashed at rest, and revoke their whole family on replay under concurrency.
    requirement: AUTH-01
    verification:
      - kind: integration
        ref: backend/tests/auth/test_refresh.py and backend/tests/integration/test_refresh_concurrency.py
        status: pass
    human_judgment: false
  - id: D2
    description: Logout is idempotent, clears the approved cookie path, and invalidates current session access authority.
    requirement: AUTH-01
    verification:
      - kind: integration
        ref: backend/tests/auth/test_logout.py
        status: pass
    human_judgment: false
  - id: D3
    description: Password replacement is policy-validating, atomic, and revokes all old authority.
    requirement: AUTH-01
    verification:
      - kind: integration
        ref: backend/tests/auth/test_password_change.py
        status: pass
    human_judgment: false
  - id: D4
    description: Auth lifecycle routes retain their approved OpenAPI signatures with no generated-client drift.
    requirement: PLAT-03
    verification:
      - kind: other
        ref: frontend npm run api:check
        status: pass
    human_judgment: false

duration: 33min
completed: 2026-08-24
status: complete
---

# Phase 1 Plan 07: Session Lifecycle Summary

**One-time hashed refresh rotation, replay-family defense, idempotent logout, and atomic password replacement now complete the internal OAuth2 session lifecycle.**

## Performance

- **Duration:** 33 min
- **Started:** 2026-08-24T16:55:09Z
- **Completed:** 2026-08-24T17:27:49Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Added 256-bit opaque refresh credentials, SHA-256-only persistence, serialized one-time rotation, predecessor lineage, and family-wide replay revocation.
- Added exact-origin/rate ordering and stable refresh/logout response and cookie behavior, including idempotent invalid and repeated logout.
- Added atomic current-user password replacement with the exact 12-128 Python-character policy, Argon2 rehash, token-version advance, global session revocation, and old-authority invalidation.
- Proved real PostgreSQL two-request serialization, mutation-sensitive security boundaries, full randomized regression, and 100% scoped statement and branch coverage.

## TDD Evidence

### Task 1: Refresh rotation and replay defense

- **RED:** The registered final-signature `POST /api/v1/auth/refresh` seam returned 501; the first route assertion expected exact 200 body/cookie and predecessor/successor state and failed on 501. Focused REDs then isolated malformed/dead/used tokens, replay-family state, Origin, request 31, Redis outage, entropy, expiry boundary, and concurrency.
- **GREEN:** `rotate_refresh_session` validates the exact 43-character token shape, hashes before lookup, locks the predecessor with `FOR UPDATE`, consumes it once, creates one child, and returns a sid-bearing access token plus a fresh cookie. Replay commits family revocation before the stable 401. Origin and Redis execute before database work.
- **REFACTOR:** Cookie setting/clearing moved to one route helper; action limiting became one hashed-identity seam. All focused and full suites remained green.
- **Concurrency:** A migrated plan-owned PostgreSQL database ran two simultaneous requests for one token. Responses were exactly one 200 and one 401; the durable family had one used predecessor, at most one successor, and replay left the family revoked. The concurrency test passed repeatedly and in the final randomized suite.

### Task 2: Idempotent logout

- **RED:** The final-signature `POST /api/v1/auth/logout` seam returned 501 instead of exact 204/cookie clearing and left the session active.
- **GREEN:** Valid authority is row-locked and revoked; missing, malformed, unknown, already-revoked, and repeated cookies all reach the same exact 204 and clear-cookie path. Current sid-bearing access is rejected after revocation.
- **REFACTOR:** Logout reuses the shared Origin, action limiter, digest lookup, and cookie policy. Hostile Origin stops before Redis/PostgreSQL; request 11 is 429. Redis outage deliberately preserves logout availability without weakening refresh/password-change fail-closed behavior.

### Task 3: Atomic password replacement

- **RED:** The final-signature `POST /api/v1/auth/change-password` seam returned 501 instead of exact 204/400/401/422 behavior. Separate focused REDs covered wrong current password, length, same/email-derived password, restricted purpose, stale principal/session, Redis ordering, and injected transaction failure.
- **GREEN:** The service derives the current user only from signed claims, locks that user, reconciles active/token-version/purpose/session state, verifies Argon2, preserves Unicode/spaces, updates the hash and forced-change flag, increments `token_version`, and revokes every current-user session in one transaction. Success clears the refresh cookie and mints no replacement authority.
- **REFACTOR:** Stable password-policy details were centralized at the service boundary and mutation armor separated inactive, stale-version, missing-user, exact-expiry, cross-user, and already-revoked-session state. An injected session-update failure returned 500 with every user/session field rolled back.

## Task Commits

1. **Lifecycle seams and refresh RED/GREEN:** `1e53cfa`, `05925e3`, `f5e4469`
2. **Refresh denial, replay, and PostgreSQL concurrency armor:** `afb3f6f`, `84aab7d`
3. **Logout RED/GREEN and idempotency/order armor:** `d908e1e`, `eca1507`, `3c3e4c7`
4. **Password-change RED/GREEN and atomic-policy armor:** `9b2c517`, `4354f00`, `8b2b1d0`
5. **Green refactors and branch/mutation assurance:** `751da06`, `ba46bc1`, `8a962f2`, `715d25c`, `c85ec16`, `5cb9b4a`

## Files Created/Modified

- `backend/src/verboflex/auth/origin.py` - exact allowlist protection for ambient-cookie mutations.
- `backend/src/verboflex/auth/rate_limits.py` - per-action hashed-identity Redis limits.
- `backend/src/verboflex/auth/refresh_sessions.py` - opaque token validation, digesting, locked rotation, replay revocation, and idempotent revocation.
- `backend/src/verboflex/auth/password_change.py` - purpose-aware candidate decoding and atomic password/authority replacement.
- `backend/src/verboflex/api/v1/routes/auth.py` - final refresh, logout, and change-password HTTP behavior plus shared cookie policy.
- `backend/tests/auth/test_refresh.py` - exact refresh, Origin, rate, outage, replay, timeline, storage, and mutation armor.
- `backend/tests/auth/test_logout.py` - exact idempotency, cookie, access-revocation, Origin, rate, and outage contracts.
- `backend/tests/auth/test_password_change.py` - success, policy, purpose, stale authority, isolation, rollback, rate, and outage contracts.
- `backend/tests/integration/test_refresh_concurrency.py` - real PostgreSQL two-request serialization proof.
- `backend/tests/__init__.py`, `backend/tests/auth/__init__.py`, `backend/tests/integration/__init__.py` - stable test-module imports for shared fixtures.

## Decisions Made

- Refresh token replay is distinguished from ordinary invalid authority by its durable consequence, not its HTTP body: the response remains the same 401 while the entire family is revoked.
- Exact Origin comparison precedes Redis and PostgreSQL for cookie mutations; absent Origin remains valid for non-browser clients.
- Logout remains fail-open only for its limiter so users can shed ambient authority during Redis failure; refresh and password change remain fail-closed.
- Password change never accepts user identity or authorization state from the request and never mints post-change authority; a fresh login is mandatory.

## Mutation and Coverage Evidence

- Scoped randomized auth/API coverage: **142 passed**, **249/249 statements**, **42/42 branches**, **100%**.
- Full randomized backend suite: **177 passed** with seed `1072026`.
- Mutation testing covered refresh/session, password-change, action-limit, and Origin modules. All material security mutations were killed, including lost row locking, reduced entropy, wrong expiry boundaries, incomplete family/global revocation, stale user/session acceptance, cross-user revocation, non-atomic commits, raw/unscoped limiter keys, and off-by-one limits.
- Remaining bounded survivors only rewrite internal exception messages that routes intentionally map to stable public bodies, select equivalent SQLAlchemy UUID defaults, preserve an equivalent replay truth table, or alter same-request time defaults without changing the specified authority outcome. No internal-message assertions were added solely to inflate the score.

## Verification Results

- Focused refresh/logout/password lifecycle suite - 56 passed.
- Focused auth/API plus PostgreSQL concurrency suite - 142 passed at 100% statement and branch coverage.
- Full backend suite, randomized seed `1072026` - 177 passed.
- Password property/boundary suite - 9 passed.
- `uv run mypy src tests` - no issues across 48 source files.
- `uv run ruff check .` / `uv run ruff format --check .` - pass; 51 files formatted.
- `uv run radon cc ...` - average A (3.57); the two transactional services are C13/C15 and fully branch-covered plus mutation-reviewed.
- `npm run api:check` - OpenAPI export and generated client are drift-free.
- `uv run pip-audit` - no known vulnerabilities; local non-PyPI package intentionally skipped.
- `uv run pip-licenses --summary` - dependency license inventory completed; no dependency changed in this plan.
- `detect-secrets` - AWS known-bad control detected; zero findings in source, migrations, configuration, and tests.
- Source/stub scan - no TODO, FIXME, 501, or “Not implemented” in plan-owned files; broken-window entries 2-4 are fixed.
- Real PostgreSQL - every per-test database was explicitly dropped; the plan-owned PostgreSQL 18 container was stopped and auto-removed after final verification.

## Security Evidence

- **T-05-01 / refresh spoofing:** structural opaque-token validation, SHA-256 lookup, predecessor row locking, exactly one successor, and replay-family revocation are tested against real PostgreSQL.
- **T-05-02 / cookie CSRF:** exact Origin rejection happens before limiter and database mutation; cookie set/delete use the approved `HttpOnly`, `SameSite=lax`, `/api/v1/auth` policy.
- **T-05-03 / elevation:** password-change purpose is accepted only here, must still match durable forced-change state, and remains rejected by normal protected endpoints.
- **T-05-04 / tampering:** password/hash/flag/version/session revocation share one transaction; injected failure proves full rollback and cross-user isolation.
- **T-05-05 / denial of service:** refresh 31 and password change 11 stop before database/Argon2, malformed/outage limiter state fails closed, and raw bearer/cookie authority is absent from Redis keys.

## API Gate Resolution

- **Scope:** completed the existing `POST /api/v1/auth/refresh`, `/logout`, and `/change-password` final signatures; no new endpoint or version surface.
- **Authentication/authorization:** refresh authority stays in the approved cookie; password change accepts ordinary or restricted bearer purpose only after signed and durable reconciliation.
- **Idempotency:** logout is target-state idempotent for valid, missing, malformed, unknown, expired/revoked, and repeated authority.
- **Rate limits:** refresh allows 30/minute and rejects 31; logout/password change allow 10/minute and reject 11, with exact retry metadata.
- **Compatibility:** generated OpenAPI/client check passes with zero drift.

## Deviations from Plan

### Auto-fixed Issues

**1. [Security assurance] Added mutation-derived authorization and isolation cases**

- **Found during:** Final gauntlet after all planned behavior was green.
- **Issue:** Branch coverage alone did not distinguish inactive/stale/missing password principals, exact access-session expiry, nonzero token versions, cross-user session revocation, or exact Redis call state.
- **Fix:** Added focused behavior tests that killed every material survivor without changing the approved HTTP surface.
- **Files modified:** `backend/tests/auth/test_refresh.py`, `backend/tests/auth/test_logout.py`, `backend/tests/auth/test_password_change.py`
- **Verification:** Focused 56 pass, full 177 pass, scoped coverage 100%, material mutants killed.
- **Committed in:** `715d25c`, `c85ec16`, `5cb9b4a`

---

**Total deviations:** 1 auto-fixed security-assurance gap. **Impact:** Stronger executable evidence only; no product, API, schema, dependency, or infrastructure scope expansion.

## Issues Encountered

- Mutmut retains equivalent/internal survivors by design. Each survivor in the plan-owned functions was inspected or bounded; no assertion was added for a private exception message that cannot alter the stable HTTP contract.
- The first limiter-evidence type check exposed an `object` narrowing gap in the fake Redis call capture; an explicit string assertion fixed the test typing without changing production code.

## User Setup Required

None - no external service configuration or dependency change is required.

## Next Phase Readiness

- The auth lifecycle is complete for the approved internal username/password v1 model and is ready for system-status/worker/deployment smoke work in Plan 01-08.
- Microsoft/Entra/OIDC remains intentionally deferred; no provider-specific field or flow was introduced.
- The only remaining open broken windows belong to Plan 01-08: system status and the deferred Celery worker target.

## Self-Check: PASSED

- Every declared key file exists and all 17 task commits are present.
- All task acceptance criteria and the plan-level randomized verification pass.
- The plan-owned PostgreSQL container is removed and no plan-owned 501 seam remains.

---
*Phase: 01-platform-foundation*
*Completed: 2026-08-24*
