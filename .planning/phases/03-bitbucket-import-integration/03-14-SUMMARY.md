---
phase: 03-bitbucket-import-integration
plan: 14
subsystem: testing
tags: [docker-compose, playwright, bitbucket, oauth2, celery, tdd]

requires:
  - phase: 03-13
    provides: generated import client, mapping UI, polling, and reconciliation dialog
provides:
  - deployment-like mock proof for the complete Phase 3 import and recovery journey
  - optional live Bitbucket read-only smoke with enforced provider method audit
  - sanitized pre-closeout evidence and deterministic cleanup verification
affects: [03-15, 03-16, phase-08-bitbucket-pull-requests]

actuals:
  tokens: 23887
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - disposable seven-service Compose verification with fail-closed cleanup
    - TLS audit boundary separating OAuth POST from GET-only provider resources
    - owner-only live configuration with digest-only retained evidence

key-files:
  created:
    - backend/tests/architecture/test_phase3_live_provider_smoke.py
    - docs/evidence/phase-03.md
  modified:
    - tools/phase3_smoke.sh
    - backend/src/verboflex/services/import_jobs.py
    - backend/src/verboflex/worker/import_tasks.py
    - backend/tests/integration/test_migrations.py
    - frontend/e2e/admin-configuration.spec.ts

key-decisions:
  - "Keep live Bitbucket execution supplemental: an absent configuration is an explicit successful skip and never substitutes for mandatory mock evidence."
  - "Route configured live traffic through an ephemeral TLS audit boundary that permits the token POST but rejects every non-GET provider resource request before forwarding."
  - "Carry source-movement classification alongside imported references so production workers can persist complete rewrite proposals atomically."

patterns-established:
  - "Live evidence allowlist: retain only readiness, counts, timing, SHA-256 identities, zero mutations, and local revoke status."
  - "Provider method separation: OAuth token acquisition is classified independently from api.bitbucket.org repository traffic."

requirements-completed: [BITB-02, BITB-05, BITB-06]

coverage:
  - id: D1
    description: Complete deployment-like import, retry, watchdog, and reconciliation journey executes without provider writes.
    requirement: BITB-02
    verification:
      - kind: e2e
        ref: "bash tools/phase3_smoke.sh --mock-provider"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_migrations.py#Phase 3 deployment cycle"
        status: pass
    human_judgment: false
  - id: D2
    description: Import refresh classifies equal, fast-forward, and rewritten movement while retaining or proposing the correct mapping baseline.
    requirement: BITB-05
    verification:
      - kind: e2e
        ref: "frontend/e2e/admin-configuration.spec.ts#deployment-like Phase 3 import, recovery, watchdog, and rewrite journeys"
        status: pass
    human_judgment: false
  - id: D3
    description: Supplemental live-read mode is bounded, credential-safe, GET-only for provider resources, and explicitly skippable when unconfigured.
    requirement: BITB-06
    verification:
      - kind: unit
        ref: "backend/tests/architecture/test_phase3_live_provider_smoke.py"
        status: pass
      - kind: other
        ref: "bash tools/phase3_smoke.sh --self-test-live-mode"
        status: pass
      - kind: other
        ref: "bash tools/phase3_smoke.sh --live-provider-read-only --skip-if-unconfigured"
        status: pass
    human_judgment: false

duration: 1h25min
completed: 2026-09-03
status: complete
---

# Phase 03 Plan 14: Deployment and Live Read Smoke Summary

**A full disposable import/recovery smoke plus an optional Bitbucket live-read path with enforced GET-only resource traffic, local revoke, digest-only evidence, and complete cleanup**

## Performance

- **Duration:** 1h25min
- **Started:** 2026-09-03T12:12:23Z
- **Completed:** 2026-09-03T13:37:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Proved the browser-to-API-to-PostgreSQL-to-Redis-to-worker import path for direct and separate mappings, including equal/fast-forward movement, failures, same-UUID retry, watchdog recovery, and rewrite confirmation.
- Distinguished the allowed OAuth token POST from 59 mocked provider resource GETs and proved zero branch, source, pull-request, or other resource mutations.
- Implemented the optional live path through authenticated VerboFlex APIs for connection, reconnection, preview, publication, one commit-bound direct import, and local revoke.
- Added a credential-independent live-mode self-test covering argument routing, generated driver/proxy syntax, redaction, method classification, mutation rejection, bounded evidence, and trap cleanup.
- Recorded an honest explicit live skip because the four supplemental variables were absent; no live provider result was fabricated.

## Task Commits

Each task was committed atomically with TDD RED before GREEN:

1. **Task 1 RED: deployment import smoke contract** - `3014031` (test)
2. **Task 1 GREEN: deployment import recovery smoke** - `cdb0548` (feat)
3. **Task 2 RED: live provider smoke contract** - `09c8952` (test)
4. **Task 2 GREEN: supplemental live provider read smoke** - `160836c` (feat)

## Files Created/Modified

- `tools/phase3_smoke.sh` - Mandatory mock topology plus optional audited live-read execution and credential-free self-tests.
- `backend/tests/architecture/test_phase3_live_provider_smoke.py` - Fail-closed live-mode argument, skip, redaction, method, and cleanup contract.
- `backend/tests/integration/test_migrations.py` - Exact Phase 3 downgrade/upgrade verification.
- `frontend/e2e/admin-configuration.spec.ts` - Complete real-stack import, retry, watchdog, and rewrite journey.
- `backend/src/verboflex/services/import_jobs.py` - Carries validated source movement into import completion.
- `backend/src/verboflex/worker/import_tasks.py` - Runs production ancestry classification before atomically finishing an import.
- `docs/evidence/phase-03.md` - Sanitized mock and supplemental live-read pre-closeout evidence.

## Decisions Made

- Live provider execution remains optional. Missing variables produce a stable exit-zero supplemental skip, while any configured run that starts must pass every audit and cleanup gate.
- The ephemeral TLS proxy records only category, method, resource family, and status. It never records headers, credentials, URLs, provider bodies, repository names, branches, paths, or source content.
- Production connection, reconnection, preview, publication, import, polling, and revoke operations are driven through local authenticated APIs; the smoke driver has no direct provider authority.
- Live output is restricted to closed readiness, OAuth/resource counts, duration, result count, SHA-256 identities, zero resource mutations, and successful local revoke.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the deployment browser driver's API origin**

- **Found during:** Task 1 (complete import/recovery journey)
- **Issue:** Two API reads used the frontend origin and received the SPA document instead of JSON.
- **Fix:** Derived the successful authentication response origin and used it for the affected API reads.
- **Files modified:** `frontend/e2e/admin-configuration.spec.ts`
- **Verification:** The full Playwright deployment journey passed 1/1.
- **Committed in:** `cdb0548`

**2. [Rule 2 - Missing Critical] Wired production source-movement classification into worker completion**

- **Found during:** Task 1 (rewrite journey)
- **Issue:** The production worker returned only source references, so a rewritten branch could not create the complete durable reconciliation proposal exercised by the planned smoke.
- **Fix:** Added a bounded processing result carrying references plus movement classification and passed it into atomic import completion.
- **Files modified:** `backend/src/verboflex/services/import_jobs.py`, `backend/src/verboflex/worker/import_tasks.py`
- **Verification:** Direct, separate, and zero-delta rewrite journeys passed with 59 GETs and zero provider writes.
- **Committed in:** `cdb0548`

**3. [Rule 2 - Missing Critical] Added an executable architecture contract for the live-mode safety boundary**

- **Found during:** Task 2 (supplemental live-read implementation)
- **Issue:** The plan required a self-test but did not list a persistent test file for the argument, skip, redaction, GET-only, and cleanup contract required by project TDD policy.
- **Fix:** Added three failing tests before implementation, then made them pass without live credentials.
- **Files modified:** `backend/tests/architecture/test_phase3_live_provider_smoke.py`
- **Verification:** 3/3 tests and Ruff passed; RED and GREEN commits are ordered.
- **Committed in:** `09c8952`, `160836c`

---

**Total deviations:** 3 auto-fixed (1 bug, 2 missing critical functionality)
**Impact on plan:** All fixes were required for the planned deployment proof and security boundary; no product-facing scope was added.

## Issues Encountered

- The configured live run was not executed because its four explicitly supplemental environment variables were absent. The required no-credential path returned the exact documented skip with exit 0, and no live result is claimed.
- The smoke exposed the API-origin and production movement-wiring defects above; both were corrected before final verification.

## Authentication Gates

None. Optional live credentials were not required for plan completion and were neither requested nor read.

## Known Stubs

None. Empty initializers and collections found by the mechanical scan are runtime state or test fixtures, not unwired product output.

## User Setup Required

No setup is required for the mandatory Phase 3 closeout. A deliberate supplemental live run requires owner-provided values for:

- `VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID`
- `VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET`
- `VERBOFLEX_BITBUCKET_LIVE_WORKSPACE`
- `VERBOFLEX_BITBUCKET_LIVE_REPOSITORY`

`VERBOFLEX_BITBUCKET_LIVE_BRANCH` is optional and defaults to `main`. Values must remain outside Git and are copied only into a mode-0600 temporary environment removed by the exit trap.

## TDD Gate Compliance

- Task 1: RED `3014031` precedes GREEN `cdb0548`.
- Task 2: RED `09c8952` precedes GREEN `160836c`.
- Final plan verification reran the complete mandatory Docker smoke and both credential-independent live-mode gates after the GREEN commits.

## Next Phase Readiness

- Plan 03-15 can bind the final source manifest and evidence digests against a freshly verified, cleanup-complete runtime candidate.
- Plan 03-16 can review and independently verify the phase with the live path present but without treating missing external credentials as a blocker.
- No disposable Docker resource, temporary runtime, or live secret file remains.

## Self-Check: PASSED

All eight implementation/evidence files exist, all four RED/GREEN commits resolve, and the final post-GREEN verification and cleanup gates passed.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-03*
