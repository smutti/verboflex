---
phase: 02-admin-configuration
plan: 35
subsystem: bitbucket-provider-smoke
tags: [bitbucket, oauth2, client-credentials, docker-compose, security, tdd]

requires:
  - phase: 02-admin-configuration/02-21
    provides: Expiry-safe server-owned Bitbucket client_credentials authority and bounded admin lifecycle APIs
provides:
  - Base Compose provider credential configuration inherited by backend and worker
  - Production-API-only provider probe with no provider credential authority
  - Sanitized mock-provider evidence for three exchanges, exact repository scope, five GETs, and zero writes
  - Exact 44-row coverage inventory with three declared semantic replacements and 41 identity mappings
affects: [bitbucket, provider-smoke, deployment, phase-2-verification]

actuals:
  tokens: 20010
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Owner-only temporary environment files feed required provider settings into base Compose
    - External provider probes drive authenticated production APIs and never own provider tokens
    - Provider evidence records only bounded grant, scope, method, and category metadata

key-files:
  created: []
  modified:
    - docker-compose.yml
    - tools/phase2_live_provider.py
    - tools/phase2_mock_provider.py
    - tools/phase2_smoke.sh
    - backend/tests/architecture/test_phase2_live_provider_smoke.py
    - backend/tests/architecture/test_provider_boundaries.py
    - .planning/phases/02-admin-configuration/COVERAGE.md

key-decisions:
  - "Keep the live probe behind authenticated VerboFlex APIs; only production service code may acquire or hold a provider token."
  - "Replace exactly three obsolete OAuth coverage keys while preserving the other 41 keys and dispositions byte-for-semantic-byte."

patterns-established:
  - "Provider smoke boundary: test drivers own local administrator sessions and non-secret repository identity only."
  - "Secret-safe provider spy: audit rows use the exact bounded key set category/effective_scope/grant_type/method."

requirements-completed: [BITB-01, BITB-03, BITB-04]

coverage:
  - id: D1
    description: Base Compose makes backend and worker provider-ready without a generated override or secret output
    requirement: BITB-01
    verification:
      - kind: integration
        ref: "tools/phase2_smoke.sh --base-client-credentials"
        status: pass
      - kind: unit
        ref: "backend/tests/architecture/test_phase2_live_provider_smoke.py"
        status: pass
    human_judgment: false
  - id: D2
    description: Production APIs own three exact-scope client_credentials generations and a bounded five-GET repository read
    requirement: BITB-03
    verification:
      - kind: integration
        ref: "tools/phase2_smoke.sh --mock-live-provider"
        status: pass
      - kind: unit
        ref: "backend/tests/architecture/test_provider_boundaries.py"
        status: pass
    human_judgment: false
  - id: D3
    description: The 44-row capability inventory preserves 41 identity mappings and exactly three declared OAuth semantic replacements
    requirement: BITB-04
    verification:
      - kind: unit
        ref: "backend/tests/architecture/test_phase2_live_provider_smoke.py#test_coverage_rewrites_exactly_three_keys_without_semantic_loss"
        status: pass
    human_judgment: false

duration: 29min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 35: Server-Owned Provider Smoke Summary

**Base Compose now carries server-owned Bitbucket client credentials while a token-blind production-API probe proves repeated exact-scope reads, revocation, reacquisition, and secret-free teardown.**

## Performance

- **Duration:** 29 min
- **Started:** 2026-08-29T16:25:03Z
- **Completed:** 2026-08-29T16:54:12Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Forwarded the exact three required Bitbucket settings through base Compose to both backend and worker, validated from an owner-only temporary environment, with no generated override.
- Replaced the provider-aware probe with an authenticated local VerboFlex API driver; provider token exchange, bearer handling, encryption, serialization, and generation authority remain exclusively in production code.
- Proved three client_credentials acquisitions, exact `repository` scope, exactly five provider GETs, zero provider resource writes, terminal local disconnection, complete resource cleanup, and no credential material in evidence.
- Reconciled the capability inventory to exactly 44 unique rows through the declared three-key rewrite while preserving all 41 other keys and dispositions.

## Task Commits

Each TDD task was committed as an intentional RED followed by GREEN:

1. **Task 1 RED: server-owned provider smoke contracts** - `6e9ba8c` (test)
2. **Task 1 GREEN: base Compose and token-blind production-API probe** - `2c239ac` (feat)
3. **Task 2 RED: reacquisition and exact coverage rewrite contracts** - `d1cf4c9` (test)
4. **Task 2 GREEN: serialized lifecycle and 44-row inventory** - `6c6845a` (feat)

## Files Created/Modified

- `docker-compose.yml` - Requires and forwards the three provider settings through `x-backend-common`.
- `tools/phase2_live_provider.py` - Drives only authenticated local production APIs and emits bounded non-secret diagnostics.
- `tools/phase2_mock_provider.py` - Serves the exact client_credentials and repository-read surface with sanitized audit rows.
- `tools/phase2_smoke.sh` - Runs base and mock-live scenarios with owner-only configuration, secret scans, health gates, and complete teardown.
- `backend/tests/architecture/test_phase2_live_provider_smoke.py` - Pins Compose inheritance, credential ownership, lifecycle, sanitized evidence, and exact inventory preservation.
- `backend/tests/architecture/test_provider_boundaries.py` - Updates the exact integrated provider capability manifest.
- `.planning/phases/02-admin-configuration/COVERAGE.md` - Replaces the three obsolete OAuth decisions and retains the other 41 decisions unchanged.

## Decisions Made

- The live probe may hold a local administrator session and non-secret repository identity, but it may not read provider client credentials, contact or parse the token endpoint, receive a provider bearer, import the provider adapter, or write credential ciphertext.
- `oauth-client-credentials-acquisition` and `oauth-client-credentials-reacquisition` are INTEGRATE; the consolidated authorization-code/callback/refresh-token capability is a reasoned OPT-OUT; `oauth-effective-scope-inspection` remains INTEGRATE.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added an application-side mock provider readiness gate**

- **Found during:** Task 2 mock-live verification
- **Issue:** Compose `service_started` did not guarantee that the TLS mock was accepting connections before the first production API connect.
- **Fix:** Added a bounded backend-to-provider health check before the probe runs, without passing any credential.
- **Files modified:** `tools/phase2_smoke.sh`
- **Verification:** The exact Task 2 command and a fresh plan-wide mock smoke both passed.
- **Committed in:** `6c6845a`

**2. [Rule 1 - Bug] Made disposable TLS material compatible and fully contained**

- **Found during:** Task 2 mock-live verification
- **Issue:** Python 3.14/OpenSSL rejected the generated CA because it lacked Authority Key Identifier metadata, and OpenSSL derived a serial file outside the disposable runtime directory.
- **Fix:** Added CA/server key identifiers and an explicit in-runtime CA serial path; removed the leaked temporary serial file and verified no plan-owned temporary artifact remained.
- **Files modified:** `tools/phase2_smoke.sh`
- **Verification:** Mock TLS health, provider audit, secret scan, and post-run resource/temp checks passed.
- **Committed in:** `6c6845a`

---

**Total deviations:** 2 auto-fixed (1 Rule 3 blocking issue, 1 Rule 1 bug)
**Impact on plan:** Both fixes were required for deterministic, secure mock execution and did not broaden provider authority.

## Issues Encountered

- The all-dependency npm audit reported two moderate findings in a development-only `typed-rest-client` dependency, below the required high-severity gate; the production-only moderate gate reported zero vulnerabilities. No package mutation was needed for this plan.

## Verification

- `cd backend && uv run pytest tests/architecture -q` - 21 passed.
- `bash tools/phase2_smoke.sh --base-client-credentials` - passed from base Compose with full teardown.
- `bash tools/phase2_smoke.sh --mock-live-provider` - passed with three exchanges, exact repository scope, five GETs, zero writes, secret scan, and full teardown.
- `bash tools/phase2_smoke.sh --live-provider-read-only` - deterministic SKIP before provider contact because no explicit live opt-in/configuration was supplied.
- Ruff, Bash syntax, `uv lock --check`, `pip-audit`, detect-secrets, npm high-severity audit, and production npm moderate audit passed their required gates.

## TDD Gate Compliance

- Task 1 RED `6e9ba8c` failed intentionally with 5 failures and 4 passes before GREEN `2c239ac`.
- The committed tracer was rerun end to end and passed (8 architecture tests plus base-client-credentials smoke) before Task 2 began.
- Task 2 RED `d1cf4c9` failed intentionally with 3 failures and 11 passes before GREEN `6c6845a`.
- No refactor commit was necessary after either GREEN.

## Known Stubs

None.

## User Setup Required

None for deterministic plan completion. Real Bitbucket Cloud execution remains an explicit opt-in using a local mode-0600 server configuration and was not required or exercised.

## Next Phase Readiness

- The server-owned provider boundary, base deployment wiring, mock-live evidence path, and exact coverage inventory are ready for final Phase 2 verification.
- No blockers or open checkpoints remain.

## Self-Check: PASSED

- All seven planned artifacts and this summary exist.
- RED/GREEN commits `6e9ba8c`, `2c239ac`, `d1cf4c9`, and `6c6845a` are present in git history.
- Stub scan found only intentional empty accumulators/default audit metadata; no incomplete shipped behavior is present.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
