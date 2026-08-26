---
phase: 01-platform-foundation
plan: 06
subsystem: auth
tags: [oauth2, jwt, redis, postgresql, authorization, tdd]

requires:
  - phase: 01-platform-foundation
    plan: 05
    provides: Provider-independent users, roles, Argon2 credentials, and refresh-session persistence
provides:
  - Strict HS256 ordinary and password-change bearer authority
  - Non-enumerating Redis-limited OAuth2 password credential exchange
  - PostgreSQL-backed current principal, safe identity projection, and reusable role enforcement
affects: [refresh-rotation, logout, password-change, protected-api, external-oidc]

actuals:
  tokens: 16567
  tasks: 3
  commits: 33

tech-stack:
  added: []
  patterns:
    - Load active, token-version, session, and role authority from PostgreSQL for every protected request
    - Enforce the Redis login limiter before user lookup and Argon2 verification
    - Persist only SHA-256 refresh-token hashes while returning plaintext solely in an HttpOnly cookie

key-files:
  created:
    - backend/src/verboflex/auth/access_tokens.py
    - backend/src/verboflex/auth/login.py
    - backend/src/verboflex/auth/principal.py
    - backend/src/verboflex/auth/rate_limits.py
    - backend/tests/auth/test_access_tokens.py
    - backend/tests/auth/test_login.py
    - backend/tests/auth/test_roles.py
    - backend/tests/api/test_me.py
  modified:
    - backend/src/verboflex/api/v1/routes/auth.py
    - backend/src/verboflex/api/v1/routes/users.py

key-decisions:
  - "JWT verification is fixed to configured HS256 with an explicit required-claim set and five-second clock tolerance; ordinary authority lasts 900 seconds and restricted password-change authority lasts 300 seconds."
  - "Login rate limiting is authoritative and fail-closed: Redis is consulted before database lookup or Argon2, attempt six returns 429, and limiter failure returns 503 without authority mutation."
  - "Signed claims identify a candidate authority only; current active state, token_version, session validity, password-change policy, and roles are always loaded from PostgreSQL."
  - "Refresh plaintext is generated with 32 random bytes, never persisted, and is exposed only through the scoped HttpOnly SameSite=Lax cookie."

requirements-completed: [PLAT-03, AUTH-01, AUTH-04]

coverage:
  - id: D1
    description: Ordinary and password-change JWTs have exact purpose-specific claims and lifetimes and reject hostile authority
    requirement: AUTH-01
    verification:
      - kind: test
        ref: "backend/tests/auth/test_access_tokens.py"
        status: pass
    human_judgment: false
  - id: D2
    description: Internal credentials exchange for ordinary or restricted authority without account enumeration
    requirement: AUTH-01
    verification:
      - kind: integration
        ref: "backend/tests/auth/test_login.py"
        status: pass
    human_judgment: false
  - id: D3
    description: Login is Redis-limited before verification and fails closed without durable mutation
    requirement: PLAT-03
    verification:
      - kind: integration
        ref: "backend/tests/auth/test_login.py"
        status: pass
    human_judgment: false
  - id: D4
    description: Current identity returns only the safe provider-independent database projection
    requirement: AUTH-04
    verification:
      - kind: integration
        ref: "backend/tests/api/test_me.py"
        status: pass
    human_judgment: false
  - id: D5
    description: Reusable role dependencies trust database roles and ignore forged JWT role claims
    requirement: AUTH-04
    verification:
      - kind: test
        ref: "backend/tests/auth/test_roles.py and backend/tests/api/test_me.py"
        status: pass
    human_judgment: false

duration: 38 min
completed: 2026-08-24
status: complete
---

# Phase 1 Plan 6: Internal OAuth2 Authority Summary

**VerboFlex now exchanges internal corporate-email credentials for short-lived, purpose-bound bearer authority and resolves every protected identity and role decision against current PostgreSQL state.**

## Performance

- **Duration:** 38 min
- **Started:** 2026-08-24T16:12:00Z
- **Completed:** 2026-08-24T16:50:00Z
- **Tasks:** 3
- **Files modified:** 10 before plan close-out metadata

## Accomplishments

- Added explicit-HS256 JWT issuance and verification for 900-second ordinary authority with `sid` and 300-second sessionless `password_change` authority, including required claims, five-second clock tolerance, exact lifetime validation, and one stable invalid-token seam.
- Implemented `POST /api/v1/auth/token` over the OAuth2 password form with canonical email normalization, dummy Argon2 verification, an atomic Redis fixed-window limiter, indistinguishable 401 failures, exact 429/503 surfaces, hashed seven-day refresh persistence, and the approved cookie scope.
- Implemented `GET /api/v1/users/me` with an exact safe projection and database-authoritative active state, token version, session state, password-change policy, and sorted provider-independent roles.
- Added reusable `require_roles(*allowed)` enforcement and proved that forged JWT role claims cannot elevate a database `viewer`.

## Task Commits

Task 1 preserves token RED/GREEN chronology:

- **Ordinary JWT:** seam `bf357dc`, RED `6c46652`, GREEN `19b97db`
- **Restricted password-change JWT:** RED `9e0f1d1`, GREEN `fd57ecb`
- **Strict verification:** RED `feace12`, GREEN `b48ab17`
- **Hostile and wrong-purpose authority:** seam `5224af1`, RED `dca09b8`, GREEN `debb7d0`
- **Exact lifetime property:** RED `d33c71f`, GREEN `8ef63e4`

Task 2 preserves endpoint RED/GREEN chronology:

- **Final callable login seam:** `710c966`
- **Ordinary credential exchange:** RED `ced1ed4`, GREEN `7359d0a`, REFACTOR `d5761ea`
- **Temporary credential restriction:** RED `72fb24c`, GREEN `994dfc5`
- **Non-enumerating failure and ordering armor:** `4d93bef`, `d75b32b`, `6a96ab4`

Task 3 preserves protected identity and authorization chronology:

- **Current identity:** RED `1c978f5`, seam `f42753c`, real-PostgreSQL RED `d344f63`, GREEN `3e18166`, REFACTOR `a333bc9`
- **Principal denial boundaries:** `d0fc021`
- **Reusable roles:** RED `7bc038b`, GREEN `82e47c4`
- **Forged role rejection:** `12f99e4`

Final gauntlet hardening:

- **Fail-closed boundary coverage:** `6874e5c`
- **Explicit JWT library policy:** `7a4294f`
- **Material login, Redis, and principal mutants:** `d97b0d3`

## RED/GREEN Evidence

- `POST /auth/token` was callable with its final dependency signature before its first endpoint assertion; the ordinary RED received the inherited 501 response while expecting 200, then the minimal GREEN exchanged one real PostgreSQL user.
- The temporary-credential RED reached the registered endpoint and failed on incomplete runtime behavior while expecting the approved 200 restricted response; GREEN returned a five-minute `password_change` token without session or cookie.
- `GET /users/me` first failed against its callable 501 seam, then a real-PostgreSQL signed-token RED reached the principal seam and failed on incomplete behavior; GREEN returned the exact safe projection.
- The reusable role dependency RED failed with `NotImplementedError`; GREEN accepted `admin` and exact `product_manager_reviewer` while denying `viewer` with 403.
- Throwaway mutants changed the generic 401 body, bypassed dummy Argon2, raised the login limit, removed Redis fail-closed translation, removed durable principal checks, changed password-change 403 to 401, and trusted forged admin claims. Each produced the expected behavioral RED and was restored before the clean-source run.
- Hypothesis generated overlong JWT expiry windows; all examples fail closed, and the targeted mutation run killed explicit algorithm, required-claim, clock-tolerance, UTC-clock, limiter-key/result, refresh-entropy, missing-session, and expiry-boundary mutants.

## TDD Gate Compliance

- Both changed HTTP endpoints retained callable final-signature seams before endpoint assertions, so no API RED failed on import, collection, dependency setup, or a missing route.
- Each primary public behavior has preserved RED and GREEN commits, and refactors occurred only after GREEN.
- Generic 401, dummy verification, 429 ordering, Redis 503 ordering, durable rejection, and forged-claim tests were GREEN on their first clean-source run because the immediately preceding minimal slice already contained the shared ordering branch. Their RED evidence is therefore preserved as killed throwaway mutants rather than fabricated production regressions.
- No test was skipped, weakened, or broadened to manufacture GREEN.

## Files Created/Modified

- `backend/src/verboflex/auth/access_tokens.py` - Purpose-bound JWT issue/decode policy and stable denial seams.
- `backend/src/verboflex/auth/login.py` - Normalized, non-enumerating credential exchange and hashed refresh authority.
- `backend/src/verboflex/auth/rate_limits.py` - Atomic Redis fixed-window login limiter and dependency.
- `backend/src/verboflex/auth/principal.py` - Database-backed principal loading and reusable role dependency.
- `backend/src/verboflex/api/v1/routes/auth.py` - Implemented OAuth2 token endpoint; retained Plan 01-07 seams.
- `backend/src/verboflex/api/v1/routes/users.py` - Implemented protected current-identity route.
- `backend/tests/auth/test_access_tokens.py` - Exact claims, hostile inputs, property, clock, and mutation contracts.
- `backend/tests/auth/test_login.py` - Real-PostgreSQL HTTP login, cookie, rate-limit, outage, and privacy contracts.
- `backend/tests/auth/test_roles.py` - Accepted-role and exact denial dependency contracts.
- `backend/tests/api/test_me.py` - Real-PostgreSQL identity, durable revocation, purpose, and forged-role contracts.

## Decisions Made

- Only `HS256` is accepted and explicitly supplied at both PyJWT boundaries; required claims and a five-second tolerance are passed explicitly rather than relying on library defaults.
- Ordinary JWTs require a durable session id, while `password_change` JWTs must omit it; crossing either purpose boundary fails closed.
- Login-limit identity is a SHA-256 digest of canonical email plus client IP, and one Redis Lua call owns increment, first-attempt expiry, count, and TTL.
- Redis unavailability is an authentication availability failure, not permission to bypass the limiter: the route returns 503 before user lookup, Argon2, session insertion, or cookie mutation.
- The refresh credential uses 32 random bytes, only its SHA-256 digest is durable, and temporary credentials never create refresh authority.
- JWT role-like fields are ignored. Role names are loaded, validated against the stable enum, sorted, and authorized from PostgreSQL on every request.
- Microsoft Entra/OIDC remains deferred; all implemented subject and role seams stay provider-independent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Security] Added explicit malformed-authority and configuration boundaries**
- **Found during:** final fail-closed coverage gate
- **Issue:** The planned happy and hostile-path tests left signing-secret absence, purpose/session contradictions, malformed Redis state, unknown durable roles, and empty role allowlists without direct assertions.
- **Fix:** Added focused fail-closed contracts without changing the approved API or architecture.
- **Files modified:** token, login, role, and current-identity tests
- **Committed in:** `6874e5c`

**2. [Rule 2 - Security] Hardened material policy gaps exposed by generated mutants**
- **Found during:** Tier-3 mutation gate
- **Issue:** Generated mutants could alter PyJWT policy arguments, Redis Lua/key/result wiring, refresh entropy, and exact session expiry without failing the original suite.
- **Fix:** Added boundary-spy and behavioral tests for explicit HS256/required-claim/leeway/UTC policy, exact Redis invocation/result, 32-byte refresh entropy, no malformed-identity query, missing sessions, and inclusive expiry rejection.
- **Files modified:** `backend/tests/auth/test_access_tokens.py`, `backend/tests/auth/test_login.py`, `backend/tests/api/test_me.py`
- **Committed in:** `7a4294f`, `d97b0d3`

---

**Total deviations:** 2 auto-fixed security-assurance gaps. **Impact:** Assurance increased without expanding the HTTP surface, schema, dependency set, or product scope.

## Issues Encountered

- The first scoped coverage run reported 89.36%, exposing untested fail-closed branches and three inherited Plan 01-07 endpoint seams. Focused boundary tests raised all five plan-owned auth modules and `/users/me` to 100% statements and branches; changed-line coverage is 214/214.
- The final mutation run generated 310 mutants across the plan-owned service modules. After bounded hardening, access-token material policy mutants are killed; login killed 99/109, principal 85/103, and rate limiting 49/55. Remaining survivors are internal exception-message rewrites, HTTP header-name casing equivalents, boolean/whitespace equivalents, a truth-table-equivalent purpose condition, and same-request UTC timestamp-default equivalents. They were reviewed and not chased with artificial internal-message assertions.
- No dependency, infrastructure, or documentation lookup blocked implementation.

## Verification Results

- Focused auth/API suite with seed `1062026` - 54 passed.
- Thresholded scoped coverage - 54 passed; 100% statements and branches across 200 statements and 42 branches.
- Full backend suite with seed `1062026` - 119 passed.
- Changed-line coverage against `339d1fd` - 214/214 executable lines, 100%.
- `uv run mypy src tests` - no issues across 38 source files.
- `uv run ruff check .` / `uv run ruff format --check .` - pass; 41 files formatted.
- `uv run radon cc ...` - average A (3.0); the deliberately strict decoder is C18 and database principal reconciliation is C14, both fully branch-covered and mutation-reviewed.
- `uv run pip-audit` - no known vulnerabilities; local non-PyPI package intentionally skipped.
- `uv run pip-licenses --summary` - dependency license inventory completed; this plan added no dependency.
- `detect-secrets` - known-bad AWS control detected; zero findings in production source/config/migrations and zero findings in tests.
- `npm run api:check` - OpenAPI schema and generated client are drift-free after the endpoint implementation.
- Real PostgreSQL ASGI tests - isolated migrated database per login/principal contract; every database explicitly dropped after its test.
- Source and stub scan - no Microsoft/Entra/OIDC/provider field, skipped test, TODO, or FIXME; only the three inherited Plan 01-07 501 seams remain.

## Security Evidence

- **T-04-01 / spoofing:** tampered, expired, missing, malformed, overlong, and mis-scoped JWTs fail; database active state, token version, and session state override signed claims.
- **T-04-02 / disclosure:** wrong password, unknown email, malformed email, and inactive user share one exact 401 body/header; unknown and malformed identities traverse dummy Argon2 without a user query.
- **T-04-03 / denial of service:** exact atomic Redis contract runs before query/Argon2; attempt six is 429; outage and malformed limiter state are 503 with no mutation.
- **T-04-04 / elevation:** `password_change` is denied from `/users/me`, durable forced-change policy also returns 403, roles are loaded from PostgreSQL, and forged admin claims remain `viewer`.
- **T-04-05 / tampering:** ordinary login persists only the refresh digest and ties access authority to that exact durable session; restricted login persists nothing.

## API Gate Resolution

- **Scope:** implemented existing `POST /api/v1/auth/token` and `GET /api/v1/users/me` final signatures; no new method/path, pagination, version, or deprecation surface was introduced.
- **Authentication:** OAuth2 password form in; bearer JWT out; refresh credential only in the approved cookie. All protected requests reconcile bearer claims with current durable state.
- **Authorization:** exact safe self projection, 401 for invalid ordinary authority, 403 for password-change authority or insufficient roles; forged authorization fields are ignored.
- **Rate limit:** one normalized-email-and-IP fixed window, attempts 1-5 admitted, attempt 6 denied with exact `Retry-After` and `X-RateLimit-Remaining: 0`; limiter outage returns exact 503.
- **Compatibility:** pass; `npm run api:check` regenerated the schema/client with zero diff because the callable final signatures were established by the earlier scaffold.

## Known Stubs

- `backend/src/verboflex/api/v1/routes/auth.py:107` - inherited callable `POST /auth/refresh` 501 seam, intentionally owned by Plan 01-07.
- `backend/src/verboflex/api/v1/routes/auth.py:124` - inherited callable `POST /auth/logout` 501 seam, intentionally owned by Plan 01-07.
- `backend/src/verboflex/api/v1/routes/auth.py:144` - inherited callable `POST /auth/change-password` 501 seam, intentionally owned by Plan 01-07.

These inherited seams do not prevent Plan 01-06's token, principal, identity, or role goals. They are already present in the cross-phase broken-windows ledger and were not duplicated.

## User Setup Required

None. Local and deployed operators use the previously documented PostgreSQL, Redis, and JWT settings; no Microsoft or external identity-provider setup is introduced.

## Next Phase Readiness

- Plan 01-07 can rotate refresh families, revoke logout authority, and replace restricted credentials through the existing final-signature seams and durable session lineage.
- Later protected APIs can reuse `CurrentPrincipal` and `require_roles` without trusting UI state or caller role claims.
- No unresolved blocker, unapproved dependency, or plan-owned temporary resource remains after cleanup.

## Self-Check: PASSED

- All 10 plan source/test artifacts exist and all 33 pre-close-out commits resolve.
- Final test, coverage, static, complexity, mutation, security, supply-chain, OpenAPI compatibility, and real-PostgreSQL checks passed after the last test edit.
- The only uncommitted non-ignored path before close-out is the orchestrator-owned `.planning/milestone.lock`.

---
*Phase: 01-platform-foundation*
*Completed: 2026-08-24*
