---
phase: 02-admin-configuration
plan: 21
subsystem: bitbucket-auth
tags: [bitbucket, oauth2, client-credentials, postgresql, alembic, fastapi, encryption]

requires:
  - phase: 02-admin-configuration/02-20
    provides: Exact-scope read-only Bitbucket proof, encrypted singleton authority, and Phase 2 quality evidence
provides:
  - Access-only encrypted Bitbucket client-credentials generations with reversible schema support
  - Expiry-authoritative repository leases with serialized renewal and durable stale-generation invalidation
  - Direct administrator connect/reconnect/status/revoke API with no callback, workspace, or provider-secret surface
affects: [02-admin-configuration/02-22, 03-bitbucket-import-integration, bitbucket-security]

actuals:
  tokens: 33142
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - Access-only provider credentials are encrypted at rest and authorized by a singleton generation plus authoritative expiry
    - Renewal performs one client-credentials exchange while holding the singleton row lock and invalidates failed expired generations durably
    - Public provider APIs expose a closed no-store status projection and never carry provider credentials or callback state

key-files:
  created:
    - backend/alembic/versions/0008_bitbucket_client_credentials.py
    - .planning/phases/02-admin-configuration/02-USER-SETUP.md
  modified:
    - backend/src/verboflex/models/bitbucket_connection.py
    - backend/src/verboflex/services/bitbucket_oauth.py
    - backend/src/verboflex/core/config.py
    - backend/src/verboflex/api/v1/routes/admin_bitbucket.py
    - backend/src/verboflex/schemas/admin_bitbucket.py
    - backend/tests/integration/test_migrations.py
    - backend/tests/integration/test_bitbucket_oauth.py
    - backend/tests/api/test_admin_bitbucket.py

key-decisions:
  - "Persist client-credentials authority as encrypted access-only material while retaining legacy paired rows for reversible migration compatibility; refresh-only rows remain impossible."
  - "Treat provider expiry at or before the injected clock as unusable, renew within a 60-second skew under the singleton lock, and advance/clear the generation after renewal failure."
  - "Expose direct administrator connect and reconnect operations with only status, repository scope labels, timestamps, and expiry; callback, workspace, generation, and credential fields remain absent."

patterns-established:
  - "Expiry-authoritative lease: every provider read proves access-only shape, exact repository scope, positive remaining lifetime, and current generation."
  - "Bounded recovery: provider failures become one stable unavailable error while durable public status becomes Reauthorization required."
  - "Direct backend acquisition: browser requests trigger the backend exchange but never contain or receive provider credentials."

requirements-completed: [BITB-01, BITB-03, BITB-04]

coverage:
  - id: D1
    description: "Encrypted access-only client-credentials persistence permits disconnected, legacy paired, and access-only states while rejecting refresh-only state and safely invalidating access-only authority on downgrade"
    requirement: BITB-03
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_migrations.py and backend/tests/integration/test_bitbucket_oauth.py; focused client_credentials/credential_state run: 10 passed"
        status: pass
      - kind: other
        ref: "Disposable PostgreSQL Alembic upgrade head, downgrade 0007, upgrade head: head restored"
        status: pass
    human_judgment: false
  - id: D2
    description: "Repository leases reject exact expiry, serialize one renewal for concurrent callers, and permanently invalidate an expired generation after failed or incomplete acquisition"
    requirement: BITB-04
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_oauth.py: 9 passed"
        status: pass
    human_judgment: false
  - id: D3
    description: "Administrator status, direct connect, reconnect, and local revoke expose a six-field no-store contract with no callback, workspace, generation, or provider-secret surface"
    requirement: BITB-01
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_bitbucket.py: 5 passed"
        status: pass
      - kind: other
        ref: "Combined migration/OAuth/API verification: 18 passed"
        status: pass
    human_judgment: false

duration: 26min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 21: Client-Credentials Authority Summary

**Encrypted access-only Bitbucket client credentials with expiry-safe serialized renewal and a direct, secret-free administrator API**

## Performance

- **Duration:** 26 min
- **Started:** 2026-08-29T14:37:05Z
- **Completed:** 2026-08-29T15:03:17Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Added Alembic and matching ORM constraints for encrypted access-only client-credentials generations, including safe downgrade invalidation and clean re-upgrade.
- Replaced authorization-code, callback-state, and refresh authority with exact-scope client-credentials acquisition, authoritative expiry, one-winner renewal, and durable stale-generation rejection.
- Replaced callback/start routes with administrator-only direct connect/reconnect/status/revoke operations returning exactly six bounded no-store fields.

## Task Commits

Each TDD task was committed atomically:

1. **Task 1: Persist one access-only client-credentials generation through the real service**
   - `722f47e` — RED client-credentials authority and credential-state tests
   - `fc6a98d` — GREEN access-only encrypted persistence and reversible migration
2. **Task 2: Remove callback authority and make every provider lease expiry-safe**
   - `2ca1a9b` — RED expiry, renewal failure, and production-boundary tests
   - `50ccb1f` — GREEN expiry-safe leases and client-credentials-only service boundary
3. **Task 3: Expose only bounded client-credentials connect and recovery status**
   - `3117c2f` — RED direct API and closed-contract tests
   - `d8e0715` — GREEN direct administrator API and bounded schemas

## Files Created/Modified

- `backend/alembic/versions/0008_bitbucket_client_credentials.py` — access-only credential-state upgrade and safe downgrade invalidation.
- `backend/src/verboflex/models/bitbucket_connection.py` — ORM constraint matching the deployed access-required/refresh-optional states.
- `backend/src/verboflex/services/bitbucket_oauth.py` — exact client-credentials exchange, encrypted persistence, expiry-aware lease, serialized renewal, local revoke, and stable errors.
- `backend/src/verboflex/core/config.py` — backend client ID/secret/keyring settings without callback configuration.
- `backend/src/verboflex/api/v1/routes/admin_bitbucket.py` — direct administrator connect, reconnect, status, and revoke operations.
- `backend/src/verboflex/schemas/admin_bitbucket.py` — closed six-field status and bounded unavailable response.
- `backend/src/verboflex/main.py` — API-lifespan lease authority constructed without Redis callback state.
- `backend/src/verboflex/worker/preview_tasks.py` — worker lease authority constructed from the client-credentials-only service.
- `backend/tests/integration/test_migrations.py` — access-only, refresh-only, legacy paired, downgrade, and re-upgrade coverage.
- `backend/tests/integration/test_bitbucket_oauth.py` — persistence, concurrency, expiry, renewal failure, exact exchange, and configuration coverage.
- `backend/tests/api/test_admin_bitbucket.py` — direct lifecycle, authorization, expiry, bounded failure, and closed OpenAPI coverage.
- `.planning/phases/02-admin-configuration/02-USER-SETUP.md` — secret-free production OAuth consumer and environment setup checklist.

## Decisions Made

- Legacy paired rows remain migration-compatible, but production service authority is client-credentials-only and rejects any refresh-bearing row for reads.
- The credential becomes unusable exactly at provider expiry; renewal begins within a fixed 60-second skew and serializes on the singleton row lock.
- A failed renewal advances the generation and clears credential ciphertext before returning a bounded error, so stale leases cannot recover authority.
- Repository workspace remains registry-owned and is not invented in the organizational provider connection status.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Widened the Alembic revision-version column for the prescribed revision identifier**
- **Found during:** Task 1 (first migration upgrade)
- **Issue:** The prescribed `0008_bitbucket_client_credentials` revision identifier exceeds Alembic's existing 32-character version column and could not be recorded.
- **Fix:** Widened `alembic_version.version_num` to 64 before applying the revision. Downgrade retains the wider metadata column because the currently recorded long revision cannot be safely stored during the downgrade transition otherwise.
- **Files modified:** `backend/alembic/versions/0008_bitbucket_client_credentials.py`
- **Verification:** Focused migration tests passed, and the explicit disposable upgrade/downgrade/re-upgrade cycle returned to `0008_bitbucket_client_credentials (head)`.
- **Committed in:** `fc6a98d`

**2. [Rule 3 - Blocking] Updated non-route production service constructors after removing callback state**
- **Found during:** Task 2 (client-credentials-only service boundary)
- **Issue:** API lifespan and Celery preview worker still passed the removed Redis callback-state dependency and would fail to construct the lease authority.
- **Fix:** Removed the obsolete Redis dependency from both constructor call sites.
- **Files modified:** `backend/src/verboflex/main.py`, `backend/src/verboflex/worker/preview_tasks.py`
- **Verification:** Ruff passed, focused API import/execution passed, and the combined 18-test verification passed.
- **Committed in:** `50ccb1f`

---

**Total deviations:** 2 auto-fixed (2 Rule 3 blocking)
**Impact on plan:** Both fixes were required to execute the prescribed revision and keep existing API/worker construction aligned; provider authority and public scope were not expanded.

## Issues Encountered

- Context7 was not installed in the executor environment, so no external library lookup could be performed. The implementation used the plan's researched, pinned platform contracts and existing standard-library/SQLAlchemy project patterns; no dependency was added.

## TDD Gate Compliance

- Task 1: RED `722f47e` precedes GREEN `fc6a98d`; tracer feedback gate passed before expansion.
- Task 2: RED `2ca1a9b` precedes GREEN `50ccb1f`.
- Task 3: RED `3117c2f` precedes GREEN `d8e0715`.
- No refactor commit was needed; every final focused and combined gate passed.

## Known Stubs

None.

## User Setup Required

**External service configuration remains incomplete.** See [02-USER-SETUP.md](./02-USER-SETUP.md) for:

- Bitbucket OAuth consumer client ID and client secret environment variables.
- Operator-managed encryption keyring configuration.
- Exact `repository` permission selection and secret-free verification.

No real Bitbucket credential was required or used by the deterministic automated tests.

## Next Phase Readiness

- Plan 02-22 can regenerate the browser client from the direct backend contract and replace the existing callback-navigation UI.
- The backend contract, reversible persistence, expiry recovery, and direct administrator operations are fully verified.
- No execution blocker remains; production use waits only on the documented external Bitbucket consumer setup.

## Self-Check: PASSED

- All 12 created or modified plan artifacts exist.
- All six RED/GREEN task commits exist in the required order.
- Every focused command, the combined 18-test plan command, and the explicit reversible migration cycle passed.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
