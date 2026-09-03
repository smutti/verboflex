---
phase: 02-admin-configuration
plan: 05
subsystem: bitbucket-oauth-api
tags: [oauth2, fastapi, bitbucket, redis, postgresql, openapi, tdd]

requires:
  - phase: 01-platform-foundation
    provides: Provider-independent administrator bearer authority and canonical OpenAPI generation
  - phase: 02-admin-configuration
    plan: 04
    provides: Encrypted singleton Bitbucket connection, digest-only state, and generation authority
provides:
  - Linearizable Bitbucket refresh, reconnect, and immediate local revocation
  - Administrator-only status, start, reconnect, and local revoke APIs
  - State-authoritative OAuth callback with a fixed same-tab backend redirect
  - Closed secret-free OpenAPI contracts and generated TypeScript client operations
affects: [02-06-oauth-admin-ui, 02-07-oauth-status, 02-19-bitbucket-integration, 02-20-phase-gauntlet]

actuals:
  tokens: 48236
  tasks: 2
  commits: 15

tech-stack:
  added: []
  patterns:
    - Locked singleton generation serializes refresh, reconnect, and local revoke
    - OAuth callback authority is consumed exclusively from single-use state
    - Browser OAuth lifecycle responses and failures are no-store
    - Closed FastAPI schemas generate stable TypeScript client operations

key-files:
  created:
    - backend/src/verboflex/api/v1/routes/admin_bitbucket.py
    - backend/src/verboflex/schemas/admin_bitbucket.py
    - backend/tests/api/test_admin_bitbucket.py
  modified:
    - backend/src/verboflex/services/bitbucket_oauth.py
    - backend/src/verboflex/auth/principal.py
    - backend/src/verboflex/api/v1/router.py
    - backend/src/verboflex/audit/events.py
    - backend/tests/integration/test_bitbucket_oauth.py
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json
    - frontend/src/api/client/index.ts
    - frontend/src/api/client/sdk.gen.ts
    - frontend/src/api/client/types.gen.ts
    - tools/verify_bitbucket_oauth_mutants.py

key-decisions:
  - "Guarantee revocation locally by advancing the locked generation and deleting both ciphertexts; do not claim or model an unverified provider revoke operation."
  - "Authorize the callback from consumed OAuth state rather than an ambient bearer token, then redirect only to `/admin/bitbucket`."
  - "Use only the exact Bitbucket `repository` scope and expose the label `Read-only repository access`; never request write, pull-request, or administrative supersets."
  - "Expose only Disconnected, Connected, Reauthorization required, and Unavailable, with closed schemas and bounded errors."

patterns-established:
  - "OAuth lifecycle API: protected actions use current internal administrator authority, while the provider callback uses state-bound authority without a bearer dependency."
  - "Credential invalidation: generation advances and ciphertext deletion commit together before stale work can complete."
  - "Contract secrecy: provider credentials, encryption material, response bodies, generation internals, and guessed operations never enter API or OpenAPI projections."

requirements-completed: [BITB-01]

coverage:
  - id: D1
    description: "Refresh, reconnect, and local revoke serialize on the singleton and reject stale generation work without provider-side revoke claims."
    requirement: BITB-01
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_oauth.py"
        status: pass
      - kind: other
        ref: "tools/verify_bitbucket_oauth_mutants.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Only current administrators can start, inspect, reconnect, or locally revoke; the callback is authorized by consumed state and returns through one fixed redirect."
    requirement: BITB-01
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_bitbucket.py#test_admin_oauth_lifecycle_is_state_authoritative_and_locally_revocable"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_admin_bitbucket.py#test_every_protected_bitbucket_operation_requires_current_admin_without_mutation"
        status: pass
    human_judgment: false
  - id: D3
    description: "The canonical OpenAPI and generated client expose stable closed lifecycle contracts, exact repository-read scope, bounded vocabulary, and no provider secret material."
    requirement: BITB-01
    verification:
      - kind: integration
        ref: "backend/tests/api/test_openapi_contract.py#test_admin_bitbucket_openapi_is_closed_bounded_and_secret_free"
        status: pass
      - kind: other
        ref: "npm --prefix frontend run api:check"
        status: pass
    human_judgment: false

duration: 26min
completed: 2026-08-27
status: complete
---

# Phase 02 Plan 05: Organizational Bitbucket OAuth Lifecycle Summary

**A generation-serialized Bitbucket OAuth lifecycle now exposes closed administrator APIs, state-authoritative callbacks, immediate local revocation, and a secret-free canonical client contract.**

## Performance

- **Active duration:** 26 min, excluding the tracer approval wait
- **Started:** 2026-08-27T08:55:10Z
- **Completed:** 2026-08-27T09:50:25Z
- **Tasks:** 2
- **Files modified:** 15 implementation, contract, generated-client, test, and evidence artifacts
- **Actual estimate scale:** 48,236 tokens (192,942 realized diff characters / 4)

## Accomplishments

- Serialized reconnect, token refresh, and local revoke on one locked connection generation; stale completion cannot restore revoked or replaced authority.
- Published administrator-only status/start/reconnect/revoke routes and a bearer-free callback whose authority comes solely from single-use OAuth state.
- Fixed the provider authorization contract to exact `repository` scope, a fixed `/admin/bitbucket` same-tab redirect, and four approved public statuses.
- Kept access tokens, refresh tokens, encryption keys, provider response bodies, internal generations, and any guessed revoke operation out of responses and OpenAPI.
- Generated the canonical TypeScript client and proved the slice with 100% changed-line coverage, 11/11 killed mutants, and the full randomized backend regression.

## Task Commits

Each TDD and evidence gate was committed atomically:

1. **Task 1 RED: OAuth lifecycle concurrency contract** — `b599429` (test)
2. **Task 1 GREEN: linearizable OAuth lifecycle** — `c050243` (feat)
3. **Task 1 REFACTOR: centralized lifecycle locking** — `b0e14a2` (refactor)
4. **Task 2 RED: administrator API/OpenAPI contract** — `7c6fe26` (test)
5. **Task 2 GREEN: guarded lifecycle API** — `48ceeaa` (feat)
6. **Task 2 REFACTOR: unified local revoke transition** — `caa5500` (refactor)
7. **Task 2 evidence RED: bounded failure contract** — `9572c7f` (test)
8. **Task 2 evidence GREEN: missing-singleton fail-closed behavior** — `008d09f` (fix)
9. **Task 2 security RED: no-store lifecycle responses** — `84ea992` (test)
10. **Task 2 security GREEN: no-store lifecycle implementation** — `5244139` (fix)
11. **Task 2 evidence: structurally corrupt credential projection** — `589bac7` (test)
12. **Plan evidence: API-boundary mutation proof** — `2bfa1b9` (test)
13. **Contract output: regenerated TypeScript client** — `16f5c38` (chore)
14. **Evidence formatting:** `9d73c9d` (style)
15. **Secret-scan fixture classification:** `954fbd8` (test)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 1 RED:** the exact `cd backend && uv run pytest -q tests/integration/test_bitbucket_oauth.py -x` command failed before refresh/reconnect/local-revoke behavior existed (`b599429`).
- **Task 1 GREEN:** the unchanged command passed 7/7 after the minimal generation-serialized implementation (`c050243`).
- **Task 1 REFACTOR:** the unchanged command remained 7/7 after lifecycle locking was centralized (`b0e14a2`); the user explicitly approved the tracer checkpoint.
- **Task 2 RED:** the exact `cd backend && uv run pytest -q tests/api/test_admin_bitbucket.py tests/api/test_openapi_contract.py -x` command failed with the administrator Bitbucket route module absent (`7c6fe26`).
- **Task 2 GREEN:** the unchanged command passed 12/12 after the minimal guarded API, closed schemas, callback, token exchange, and OpenAPI surface landed (`48ceeaa`).
- **Task 2 REFACTOR:** the unchanged command remained 12/12 after local revoke paths were unified (`caa5500`).
- **Final exact proof:** the unchanged Task 2 command passes 20/20 after bounded failure, no-store, corrupt-row, and scan armor.

## Verification and Gauntlet Evidence

- Exact focused Task 2 command: **20 passed**.
- Exact plan verification command: **27 passed**.
- PostgreSQL migration rehearsal: **3 passed**.
- Full randomized backend regression under preserved seed `4`, with isolated live Redis and Celery worker: **358 passed**; the temporary worker and container were stopped afterward.
- Ruff lint and backend-config formatting: **94 files, pass**.
- mypy: **56 backend source/evidence files, pass**.
- Differential source coverage against the Task 1 refactor `b0e14a2`: **100% (174/174 changed lines)**; focused total statement/branch coverage was **94.57%**.
- Mutation checker negative control passed; all reviewed lifecycle and API mutants were killed: **11/11**.
- Frontend canonical API drift check, ESLint, TypeScript, Vitest, and production build passed; Vitest reported **75/75**.
- `detect-secrets` returned **0 findings** for every introduced source, API test, OpenAPI, client, and mutation-evidence artifact. The two findings in the changed principal file are pre-existing password-message constants outside its two-line session-authority diff.
- `pip-audit` found **no known vulnerabilities**; the local `verboflex` package was the sole expected non-PyPI skip.
- License audit confirmed `httpx 0.28.1` as BSD, `defusedxml 0.7.1` as PSF, and `cryptography 50.0.1` as Apache-2.0 or BSD-3-Clause.
- Stub scan found no placeholder, TODO, FIXME, empty UI-bound value, skipped test, or unrun verification introduced by this plan.

## Security Contract Review

- Protected lifecycle actions resolve a current internal administrator and internal session; viewers and anonymous callers receive bounded authorization failures before Redis or database mutation.
- The callback has no bearer dependency, atomically consumes digest-bound state, rejects replay and wrong bindings before token exchange, and can redirect only to `/admin/bitbucket`.
- The standard-library exchange posts only to the fixed Bitbucket token endpoint, refuses redirects, bounds transport time and response size, and converts provider failures into stable application errors without body leakage.
- Start, reconnect, callback success/failure, status, and local revoke responses are `Cache-Control: no-store`.
- Public status exposes only the approved vocabulary, fixed read-only scope label, and bounded timestamps; generations and credential metadata stay internal.

## Files Created/Modified

- `backend/src/verboflex/api/v1/routes/admin_bitbucket.py` — stable administrator lifecycle operations, state callback, fixed redirect, no-store responses, and bounded errors.
- `backend/src/verboflex/schemas/admin_bitbucket.py` — closed authorization, status, and error schemas.
- `backend/src/verboflex/services/bitbucket_oauth.py` — locked refresh/reconnect/revoke, public status, exact authorization URL, and bounded token exchange.
- `backend/src/verboflex/auth/principal.py` — carries the verified internal session UUID required to bind administrative state.
- `backend/src/verboflex/audit/events.py` — secret-free generation lifecycle audit events.
- `backend/tests/integration/test_bitbucket_oauth.py` and `backend/tests/api/test_admin_bitbucket.py` — concurrency, revocation, authority, hostile callback, transport, no-store, and secret-boundary evidence.
- `backend/tests/api/test_openapi_contract.py`, `frontend/openapi.json`, and `frontend/src/api/client/` — canonical stable OpenAPI and generated TypeScript operations.
- `tools/verify_bitbucket_oauth_mutants.py` — fail-closed mutation runner covering service and HTTP contract boundaries.

## Decisions Made

- Provider-side revoke remains an explicit opt-out: v1 guarantees immediate local invalidation and makes no unverified provider API claim.
- The callback consumes state authority without requiring or trusting an ambient access token.
- The browser receives a fixed repository-read scope description and never selects scopes, destinations, or provider diagnostics.
- Reauthorization remains an approved public status vocabulary value, but internal provider failures never expand the response schema.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Bounded a missing singleton instead of returning HTTP 500**
- **Found during:** Task 2 evidence armor
- **Issue:** A deleted or unavailable organizational connection row escaped through `scalar_one()` as an internal server error.
- **Fix:** Switched the lock boundary to a bounded optional lookup and raised `OAuthConnectionUnavailable`.
- **Files modified:** `backend/src/verboflex/services/bitbucket_oauth.py`, `backend/tests/api/test_admin_bitbucket.py`
- **Verification:** Exact focused command passes 20/20; missing-row callback returns the closed 503 error without exchange.
- **Committed in:** `9572c7f`, `008d09f`

**2. [Rule 2 - Missing Critical] Prevented caching of OAuth state and callback failures**
- **Found during:** Task 2 security review
- **Issue:** Start/reconnect responses carrying OAuth state and bounded callback errors had no explicit cache prohibition.
- **Fix:** Added `Cache-Control: no-store` to successful and failed lifecycle responses.
- **Files modified:** `backend/src/verboflex/api/v1/routes/admin_bitbucket.py`, `backend/tests/api/test_admin_bitbucket.py`
- **Verification:** Dedicated RED failed first; exact focused command then passes 20/20.
- **Committed in:** `84ea992`, `5244139`

**3. [Rule 2 - Missing Critical] Regenerated the canonical TypeScript API client**
- **Found during:** Plan contract verification
- **Issue:** The checked-in OpenAPI document contained the lifecycle surface, but the generated browser client had not yet materialized the stable operations and types.
- **Fix:** Regenerated the project-owned client from the canonical schema and ran the no-drift check.
- **Files modified:** `frontend/src/api/client/index.ts`, `frontend/src/api/client/sdk.gen.ts`, `frontend/src/api/client/types.gen.ts`
- **Verification:** `api:check`, TypeScript, ESLint, 75 Vitest tests, and Vite production build all pass.
- **Committed in:** `16f5c38`

---

**Total deviations:** 3 auto-fixed (1 bug, 2 missing critical correctness/security requirements)
**Impact on plan:** All changes close failure, caching, or canonical-consumer gaps without broadening the approved OAuth scope or provider claims.

## Issues Encountered

- Differential coverage initially exposed one defensive corrupt-token-pair branch not reachable through the database check constraint; a narrow structural-session test now proves it fails closed (`589bac7`).
- The existing mutation runner had drifted after refresh introduced a second encryption assignment and initially copied too little frontend contract context; the runner now uses exact unique subjects, focused OpenAPI node IDs, a valid negative control, and kills 11/11 mutants (`2bfa1b9`).
- Ruff was first invoked outside the backend configuration boundary for the evidence tool; the backend formatter was then applied and the full format gate rerun (`9d73c9d`).

## Authentication Gates

None. The user-approved tracer verification checkpoint was normal planned flow and required no credential disclosure.

## Known Stubs

None.

## User Setup Required

No new setup beyond the Bitbucket OAuth client ID, client secret, callback URI, and encryption keyring already introduced by Plan 02-04. Production Bitbucket credentials remain outside source control.

## Next Phase Readiness

- Plan 02-06 can consume the generated status/start/reconnect/revoke operations for the administrator UI.
- Background Bitbucket work can capture a connection generation and reject stale completion after reconnect or local revoke.
- No open blocker, stub, skipped test, unrun verification, or untracked generated artifact remains.

## Self-Check: PASSED

- Every implementation, contract, generated-client, test, evidence, and summary artifact listed above exists.
- All 15 plan commits exist on `codex/phase-2-admin-configuration` in valid Task 1 and Task 2 RED → GREEN → REFACTOR order.
- Coverage metadata validates with three automatically proven deliverables and no schema errors.
- Exact focused, plan-level, migration, randomized regression, lint, format, type, coverage, mutation, frontend, dependency, license, secret, and stub gates are proven above.
- No tracked deletion, open stub, skipped test, unrun verification, or unintended generated artifact remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-27*
