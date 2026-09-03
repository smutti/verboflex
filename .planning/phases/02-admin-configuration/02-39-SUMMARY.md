---
phase: 02-admin-configuration
plan: 39
subsystem: deployment-testing
tags: [docker-compose, celery, scheduler, watchdog, recovery, mutation-testing, tdd]

requires:
  - phase: 02-admin-configuration/02-37
    provides: Base Compose worker-loss recovery and the mandatory Phase 2 gap-closure gauntlet
provides:
  - Exact scheduler deployment environment, backend image, and restart authority in staging and production
  - Mandatory killed-worker watchdog recovery through both shipped deployment overlays
  - Isolated, secret-safe overlay retries restricted to the exact address-bind race
affects: [02-38, phase-02-verification, deployment-smoke, preview-watchdog]

actuals:
  tokens: 4743
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - Deployment overlays give API, worker, and scheduler one exact backend-process authority
    - One public worker-loss entry point executes staging then production in isolated disposable projects
    - Deployment smoke secrets are generated per attempt, owner-only, scanned, and removed by trap-owned cleanup

key-files:
  created:
    - .planning/phases/02-admin-configuration/02-39-SUMMARY.md
  modified:
    - docker-compose.staging.yml
    - docker-compose.prod.yml
    - backend/tests/architecture/test_phase2_live_provider_smoke.py
    - tools/phase2_smoke.sh
    - tools/phase2_gauntlet.sh

key-decisions:
  - "Both deployment schedulers explicitly inherit the overlay environment, deployed backend image, and unless-stopped restart authority while retaining the base Celery Beat command."
  - "The authoritative worker-loss gate always runs staging and production in separate projects and retries only the exact address-bind race, at most three times per overlay."

patterns-established:
  - "Rendered deployment parity: compare exact environment keys without including seeded values in failure diagnostics."
  - "Dual-overlay recovery: base Compose, then the named deployment overlay, then the mock-provider override, with no base-only success path."

requirements-completed: [PROD-08, BITB-01, BITB-04]

coverage:
  - id: D1
    description: Rendered staging and production give backend, worker, and scheduler the same deployment environment, backend image, restart policy, and watchdog bounds while preserving their distinct commands.
    requirement: BITB-01
    verification:
      - kind: integration
        ref: backend/tests/architecture/test_phase2_live_provider_smoke.py#test_deployment_overlays_give_scheduler_exact_worker_authority
        status: pass
      - kind: integration
        ref: "docker compose -f docker-compose.yml -f docker-compose.staging.yml config --quiet && docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet"
        status: pass
    human_judgment: false
  - id: D2
    description: A killed running preview is terminalized by the independent scheduler and retried successfully in isolated staging and production deployments without changing the original row.
    requirement: PROD-08
    verification:
      - kind: integration
        ref: backend/tests/architecture/test_phase2_live_provider_smoke.py#test_worker_loss_smoke_exercises_staging_and_production_overlays
        status: pass
      - kind: e2e
        ref: "bash tools/phase2_smoke.sh --mock-provider --worker-loss"
        status: pass
    human_judgment: false
  - id: D3
    description: The official gap-closure contract retains one mandatory worker-loss layer whose command covers both deployment overlays and leaves no resources or secrets behind.
    requirement: BITB-04
    verification:
      - kind: integration
        ref: "bash tools/phase2_gauntlet.sh --gap-closure-contract"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-08-31
status: complete
---

# Phase 02 Plan 39: Deployment Scheduler Recovery Summary

**Staging and production now deploy Celery Beat with exact backend-process authority, and the mandatory worker-loss gate proves bounded watchdog terminalization plus an isolated successful retry in both overlays.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-08-31T10:33:57Z
- **Completed:** 2026-08-31T11:08:29Z
- **Tasks:** 2
- **Files modified:** 5 implementation/test/harness files plus this summary
- **Actual estimate scale:** 4,743 tokens (18,970 realized diff characters / 4, rounded to the nearest whole token)

## Accomplishments

- Gave the staging and production scheduler the exact deployment environment anchor, overlay-specific backend image, and `unless-stopped` restart policy already used by the API and worker, while preserving the inherited Celery Beat command.
- Added value-free rendered-Compose contracts that compare app environment, password-bearing database authority, Redis, OAuth/keyring settings, preview watchdog bounds, image, restart policy, and process roles across backend, worker, and scheduler.
- Made `--mock-provider --worker-loss` run one isolated staging recovery followed by one isolated production recovery, with base Compose + deployment overlay + mock override ordering and no base-only fallback.
- Proved each killed running preview reaches bounded `timed_out/time_limit_exceeded`, a replacement attempt succeeds, and the original terminal row remains unchanged; every project and secret artifact is removed afterward.

## Task Commits

The two TDD tasks and their validation-policy repair were committed atomically with hooks enabled:

1. **Task 1 RED: failing scheduler deployment-authority contract** — `5cc4c39` (test)
2. **Task 1 GREEN: staging and production scheduler authority** — `4c325db` (feat)
3. **Task 2 RED: failing dual-overlay worker-loss contract** — `7f5cc4c` (test)
4. **Task 2 GREEN: isolated staging and production recovery** — `b7b87f8` (feat)
5. **Exact formatting and secret-policy preservation** — `625e26e` (fix)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Compliance

- **Task 1 RED:** `5cc4c39` failed only on the observable staging/production scheduler environment, image, restart, and backend-process authority gaps.
- **Task 1 GREEN:** `4c325db` supplied the exact overlay fields; the focused rendered-config test and both Compose renders passed.
- **Task 2 RED:** `7f5cc4c` failed at the absent explicit deployment-overlay authority before the dual runner existed.
- **Task 2 GREEN:** `b7b87f8` supplied the isolated dual-overlay path; the focused contract and real staging-plus-production smoke passed.
- Git history preserves the required `test(02-39)` → `feat(02-39)` sequence for both behavioral contracts. No separate refactor commit was necessary.

## Verification and Acceptance Evidence

- Focused plan contracts: both new architecture tests passed together; the complete provider-smoke architecture file passed **14/14**.
- Compose: staging and production `config --quiet` renders passed with exact scheduler deployment authority.
- Runtime smoke: staging and production each observed durable `running`, killed the owning worker, reached bounded `timed_out/time_limit_exceeded`, started replacement capacity, succeeded on isolated retry, and preserved the original row.
- Official contract: `bash tools/phase2_gauntlet.sh --gap-closure-contract` passed with exactly one dual-overlay worker-loss layer.
- Backend/static regressions: mypy passed across **81 source files**; Ruff lint and formatting passed.
- Frontend regressions: **20 files / 260 tests**, TypeScript, ESLint, Prettier, and Vite production build passed; the existing chunk-size warning remained non-blocking.
- Property suites: **200 backend + 3 frontend passed**.
- Exact diff coverage remained **354/354 backend lines (100%)** and **477/477 frontend lines (100%)**, with no selector, base, exclusion, or budget changes.
- Mutation authority remained **159/159 killed**, including Stryker polling **30/30**, with all negative controls passing.
- Migrations/OpenAPI: **9 migration tests passed** and the generated API client remained clean.
- Supply chain and secrets: Python audit reported no known vulnerabilities; production npm audit reported zero vulnerabilities; the configured full-graph policy accepted the already-known moderate development-only advisory. Exact source/runtime secret checks passed.
- Cleanup: zero Phase 02-37 smoke containers, networks, volumes, images, runtime directories, worker-loss state files, or temporary secret reports remained.

## Files Created/Modified

- `docker-compose.staging.yml` — explicit staging scheduler image, deployment environment, and restart policy.
- `docker-compose.prod.yml` — explicit production scheduler image, deployment environment, and restart policy.
- `backend/tests/architecture/test_phase2_live_provider_smoke.py` — exact rendered deployment authority and dual-overlay worker-loss contracts.
- `tools/phase2_smoke.sh` — explicit overlay selection, isolated per-overlay projects, exact address-race retry, ephemeral deployment secrets, and dual recovery orchestration.
- `tools/phase2_gauntlet.sh` — preserved the exact reviewed secret-fixture inventory after test formatting; the single worker-loss layer continues to invoke the now-dual public command.

## Decisions Made

- Deployment scheduler authority is explicit in each shipped overlay; it is not inferred from local base-Compose defaults.
- The public worker-loss mode is indivisible: staging must pass before production runs, and success requires both overlays.
- Only exit code 75 for the existing address-bind race is retryable, with three complete isolated attempts maximum per overlay; every other failure remains fatal.
- Preview semantics, provider scope, credentials, product graphs, and watchdog bounds remain unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Supplied valid ephemeral deployment secrets to the real overlay fixture**
- **Found during:** Task 2 staging smoke.
- **Issue:** The staging/production settings correctly rejected the local sentinel JWT value before readiness, and password-protected PostgreSQL required one shared per-attempt credential across the rendered services.
- **Fix:** Generated owner-only PostgreSQL and JWT values per attempt, injected them through the existing mode-0600 runtime environment, included both in multi-surface secret scans, and retained unconditional cleanup.
- **Files modified:** `tools/phase2_smoke.sh`
- **Verification:** Both deployment overlays completed killed-worker recovery without emitting or retaining either value.
- **Committed in:** `b7b87f8`

**2. [Rule 3 - Blocking] Preserved exact formatting and reviewed secret-detection policy**
- **Found during:** Post-task repository validation.
- **Issue:** Ruff required mechanical formatting of the expanded architecture test, which shifted three pre-existing secret-fixture line numbers in the exact reviewed inventory.
- **Fix:** Applied the configured formatter and updated only those exact path/line/type entries; detector scope, inventory size, negative control, and failure policy were unchanged.
- **Files modified:** `backend/tests/architecture/test_phase2_live_provider_smoke.py`, `tools/phase2_gauntlet.sh`
- **Verification:** Ruff lint/format and the exact source-secret scan passed.
- **Committed in:** `625e26e`

## Authentication Gates

None.

## Known Stubs

None. Empty shell globals are intentional lifecycle state initialized before trap-owned setup and do not flow into product behavior or UI rendering.

## Issues Encountered

- An additional full 18-layer gauntlet run reached **785 passing backend tests** but stopped on two pre-existing Plan 02-37 semantic-inventory assertions that still expect `CR-01..CR-10` headings in the now-replaced Phase 2 review document. The failure precedes and is independent of all five 02-39 files; changing that cross-plan review contract would exceed this plan and collide with the remaining fresh-review plans. Every exact 02-39 verification command, plus the architecture, coverage, mutation, migration, supply-chain, secret, Compose, runtime, and cleanup layers relevant to this plan, passed unchanged.

## Threat Review

- No unplanned network, authentication, file-access, schema, or provider-write surface was introduced. The planned deployment-to-scheduler, lost-worker-to-watchdog, and smoke-secret boundaries were exercised directly; all high threats in the plan register are mitigated.

## User Setup Required

None. No external configuration, dependency, or credential is required for the deterministic dual-overlay gate.

## Next Phase Readiness

- CR-11 is closed with deployment-config and runtime recovery evidence for both shipped overlays.
- Plan 02-40 can continue the fresh-review closure sequence; WR-03 through WR-07 remain intentionally outside this plan.

## Self-Check: PASSED

All five modified artifacts and this summary exist, all five task commits are reachable, and the branch remains `codex/phase-2-admin-configuration`.
