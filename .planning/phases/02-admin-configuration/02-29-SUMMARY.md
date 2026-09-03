---
phase: 02-admin-configuration
plan: 29
subsystem: background-processing
tags: [celery, postgresql, watchdog, worker-loss, skip-locked, tdd]

requires:
  - phase: 02-admin-configuration/02-21
    provides: Durable preview attempts, closed terminal vocabulary, and isolated retry identity
  - phase: 02-admin-configuration/02-35
    provides: Access-only Bitbucket client-credentials generations and production-provider smoke
  - phase: 02-admin-configuration/02-36
    provides: Running-only state/started_at PostgreSQL watchdog index
provides:
  - Clock-injected 100-row stale-running reconciler using FOR UPDATE SKIP LOCKED and exact attempt/generation/state CAS
  - Validated preview soft/hard/grace/interval policy with named Celery Beat reconciliation
  - Disposable process-loss proof from durable running through timeout and isolated successful retry
affects: [preview-jobs, celery-worker, compose-deployment, phase-02-verification]

actuals:
  tokens: 16588
  tasks: 3
  commits: 8

tech-stack:
  added: []
  patterns:
    - PostgreSQL remains the final task-state authority across worker, timeout, scheduler, and retry races
    - Celery worker execution and Beat scheduling run as separate Compose processes
    - Fault smokes gate provider I/O after a durable state commit before killing the owning process

key-files:
  created: []
  modified:
    - backend/src/verboflex/services/preview_jobs.py
    - backend/src/verboflex/core/config.py
    - backend/src/verboflex/worker/celery_app.py
    - backend/src/verboflex/worker/preview_tasks.py
    - backend/tests/integration/test_preview_jobs.py
    - docker-compose.yml
    - tools/phase2_smoke.sh
    - tools/verify_preview_job_mutants.py

key-decisions:
  - "Terminalize only exact running PreviewJob UUID/attempt/connection-generation identities; PreviewJob.id remains the Celery task identity and no task_id field is introduced."
  - "Use hard limit plus grace as the inclusive stale threshold, with a validated scan interval shorter than grace and a finite 300-second maximum terminalization bound."
  - "Keep Celery Beat separate from workers so loss of worker capacity cannot also remove durable reconciliation."
  - "Treat access-only, unexpired client-credentials generations as the sole current Bitbucket credential shape for preview creation and completion."

patterns-established:
  - "Recovery CAS: select bounded indexed work with SKIP LOCKED, then update only the selected immutable identity while state is still running."
  - "Process-loss proof: wait for durable running and a provider fault marker, SIGKILL the worker, remove the gate, start replacement capacity, and poll monotonic deadlines."

requirements-completed: [PROD-09, BITB-03, BITB-04]

coverage:
  - id: D1
    description: "Stale running preview attempts reach timed_out/time_limit_exceeded through a bounded indexed reconciler without a worker callback, and stale racers cannot overwrite the winner."
    requirement: PROD-09
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_preview_jobs.py#watchdog threshold, batch/index, race, and retry tests"
        status: pass
      - kind: other
        ref: "python tools/verify_preview_job_mutants.py — 16/16 killed"
        status: pass
    human_judgment: false
  - id: D2
    description: "Validated central timing settings configure late-ack preview execution and the named periodic stale-job task."
    requirement: BITB-03
    verification:
      - kind: integration
        ref: "cd backend && uv run pytest tests/integration/test_preview_jobs.py -x -k 'watchdog or hard_timeout or schedule' — 16 passed"
        status: pass
    human_judgment: false
  - id: D3
    description: "Separate scheduler capacity terminalizes a SIGKILL-stranded attempt, then replacement worker capacity completes a new retry without changing the original."
    requirement: BITB-04
    verification:
      - kind: e2e
        ref: "bash tools/phase2_smoke.sh --mock-provider --worker-loss"
        status: pass
      - kind: e2e
        ref: "bash tools/phase2_smoke.sh --mock-provider"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 29: Durable Preview Worker-Loss Recovery Summary

**An indexed generation-safe preview watchdog, independent Celery Beat scheduler, and real SIGKILL deployment smoke now guarantee bounded terminalization and isolated retry after worker loss.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-08-29T18:12:28Z
- **Completed:** 2026-08-29T18:47:07Z
- **Tasks:** 3
- **Files modified:** 12
- **Actual estimate scale:** 16,588 tokens (66,353 realized diff characters / 4)

## Accomplishments

- Added an injected-clock reconciler that selects only stale `running` attempts at the inclusive hard-limit-plus-grace threshold, orders by `started_at, id`, limits to 100, uses the Plan 36 index with `FOR UPDATE SKIP LOCKED`, and terminalizes through an exact UUID/attempt/generation/state compare-and-set.
- Centralized and validated soft, hard, grace, and interval settings; registered `verboflex.preview.reconcile_stale_jobs`, late acknowledgement, reject-on-worker-lost, and a separate Compose Beat service.
- Proved actual worker-process loss: a fault-gated preview reached durable `running`, its owning worker was SIGKILLed, the scheduler produced `timed_out/time_limit_exceeded`, and replacement capacity completed attempt 2 while the original remained immutable.

## Task Commits

The plan-level RED/GREEN/REFACTOR gates were committed atomically:

1. **Task 1 RED: stale recovery and race contracts** — `cd42e9c` (test)
2. **Task 1 GREEN: clock-injected stale-attempt reconciliation** — `6775c29` (feat)
3. **Task 2 RED: timing, schedule, and acknowledgement contracts** — `d30eb7e` (test)
4. **Task 2 GREEN: validated periodic durable recovery** — `94aeaf5` (feat)
5. **Task 3 RED: separate scheduler and process-loss proof contracts** — `3c92248` (test)
6. **Task 3 GREEN: SIGKILL terminalization and replacement retry smoke** — `1b1c29e` (feat)
7. **REFACTOR: recovery mutation armor** — `3bda22b` (refactor)
8. **Regression fixture: access-only publication preview authority** — `5cdcd10` (test)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 1 RED:** `pytest tests/integration/test_preview_jobs.py -x` stopped after 3 passes because `reconcile_stale_preview_jobs` did not exist.
- **Task 1 GREEN:** the complete preview integration suite passed 51/51 with threshold, 100/101 batch, index, watchdog/watchdog, late-success, hard-timeout, and retry isolation coverage.
- **Task 2 RED:** the focused 16-test selection stopped after 3 passes because the named reconcile task and timing policy were absent.
- **Task 2 GREEN:** the complete preview suite passed 63/63 with validated settings, schedule registration, late acknowledgement, and reject-on-worker-lost assertions.
- **Task 3 RED:** the focused architecture test failed with `KeyError: scheduler` against the pre-change Compose model.
- **Task 3 GREEN/REFACTOR:** all 12 deployment architecture tests and 64 preview integration tests pass; the expanded mutation proof kills all 16/16 reviewed mutants.
- Git history contains an intentional RED before every GREEN and the required plan-level `test(02-29)` → `feat(02-29)` → `refactor(02-29)` sequence.

## Verification and Acceptance Evidence

- Preview integration: `64 passed`.
- Focused watchdog/hard-timeout/schedule selection: `16 passed, 48 deselected`.
- Deployment architecture: `12 passed`.
- Publication confirmation compatibility: `26 passed` after moving its fixture to the active access-only credential shape.
- Mutation proof: baseline passed and `16/16` mutants were killed, including threshold, state, SKIP LOCKED, generation CAS, terminal timestamp, scheduler registration, and retry isolation.
- Worker-loss smoke: PASS for durable running → SIGKILL → `timed_out/time_limit_exceeded` → replacement attempt success, with bounded polling and complete cleanup.
- Normal mocked-provider smoke: PASS with client credentials, exact repository scope, five GETs, zero writes, local revoke, separate scheduler readiness, and complete cleanup.
- Static/configuration: mypy passed all 81 source files; Ruff lint passed `src tests`; all Plan 02-29 files pass Ruff format; shell syntax, Compose config, `uv lock --check`, and `git diff --check` pass.
- Security/supply chain: pip-audit reports no known vulnerabilities. Scoped detect-secrets exits successfully; its only findings are the three known literal test-fixture keyword sentinels in `test_phase2_live_provider_smoke.py`, not credentials.
- Broad backend sweep reached 762 passes and 7 failures before the three stale publication credential fixtures were corrected. The corrected publication suite passes 26/26; the four remaining unrelated CLI/Redis infrastructure failures are pre-existing and recorded in the phase deferred-items ledger.

## Files Created/Modified

- `backend/src/verboflex/services/preview_jobs.py` — exact stale selector, timeout CAS, central enqueue limits, and access-only generation currentness.
- `backend/src/verboflex/core/config.py` — positive and relational validation for preview soft/hard/grace/interval bounds.
- `backend/src/verboflex/worker/celery_app.py` — named Beat entry, task annotations, and bounded loop interval.
- `backend/src/verboflex/worker/preview_tasks.py` — late-ack/reject-on-worker-lost run task and named reconcile task.
- `backend/tests/integration/test_preview_jobs.py` — exact threshold, 100/101/index, races, retry isolation, settings, schedule, and mutation armor.
- `backend/tests/integration/test_product_publication.py` — access-only preview generation fixture.
- `backend/tests/architecture/test_phase2_live_provider_smoke.py` — separate scheduler and worker-loss composition contracts.
- `docker-compose.yml` — shared preview bounds and independent scheduler with writable Beat schedule state.
- `tools/phase2_smoke.sh` — bounded scheduler readiness, worker-loss orchestration, evidence scanning, and cleanup.
- `tools/phase2_mock_provider.py` — owner-controlled bounded source-read fault gate and closed disconnected-client handling.
- `tools/phase2_compose_flow.py` — secret-safe setup, terminal-state, retry, and original-row immutability probes.
- `tools/verify_preview_job_mutants.py` — explicit recovery and retry mutation operators.

## Decisions Made

- `PreviewJob.id` remains both the durable database identity and Celery task identity; no `task_id` schema or API field was added.
- Scheduler deliveries never infer ownership from Celery state. PostgreSQL UUID/attempt/generation/current-state predicates decide the one legal terminal transition.
- The timeout response stays closed as `timed_out` plus `time_limit_exceeded`, with `finished_at` and no result; no worker-loss cause field or provider diagnostic reaches the API.
- Worker and scheduler share central Settings and dependencies but remain separate processes, so loss of worker capacity cannot remove reconciliation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed a stale Redis monkeypatch from the preview integration harness**
- **Found during:** Task 1 RED
- **Issue:** The fixture patched the removed `preview_tasks.get_redis_client` symbol and prevented the new recovery contracts from reaching their intended RED failure.
- **Fix:** Removed only the obsolete patch; task execution remains PostgreSQL-authoritative.
- **Files modified:** `backend/tests/integration/test_preview_jobs.py`
- **Verification:** Task 1 reached the intentional missing-reconciler RED, then the complete suite passed.
- **Committed in:** `cd42e9c`

**2. [Rule 1 - Bug] Forced SQL NULL for terminal JSON results**
- **Found during:** Task 1 GREEN
- **Issue:** SQLAlchemy JSON `None` encoded JSON `null`, violating the database terminal-result constraint.
- **Fix:** The watchdog CAS writes SQL `NULL` with `sqlalchemy.null()`.
- **Files modified:** `backend/src/verboflex/services/preview_jobs.py`
- **Verification:** All threshold, batch, race, and retry tests pass.
- **Committed in:** `6775c29`

**3. [Rule 1 - Bug] Made Celery Beat persistence writable in the runtime image**
- **Found during:** Task 3 worker-loss smoke
- **Issue:** Beat exited with `PermissionError` while creating `celerybeat-schedule` in the read-only application directory.
- **Fix:** Compose supplies `--schedule=/tmp/celerybeat-schedule` to the separate scheduler.
- **Files modified:** `docker-compose.yml`, `backend/tests/architecture/test_phase2_live_provider_smoke.py`
- **Verification:** Scheduler readiness and both Compose smokes pass.
- **Committed in:** `1b1c29e`

**4. [Rule 1 - Bug] Aligned previews with client-credentials access-only generations**
- **Found during:** Task 3 worker-loss smoke
- **Issue:** Preview creation/currentness still required a refresh token retired by Plan 35, causing HTTP 503 against a valid client-credentials connection.
- **Fix:** Preview generation authority now requires access ciphertext, no refresh ciphertext, repository scope, an unexpired provider lease, matching generation, and no revocation; affected integration fixtures use the same invariant.
- **Files modified:** `backend/src/verboflex/services/preview_jobs.py`, `backend/tests/integration/test_preview_jobs.py`, `backend/tests/integration/test_product_publication.py`
- **Verification:** Preview 64/64, publication 26/26, and both Compose smokes pass.
- **Committed in:** `1b1c29e`, `5cdcd10`

**5. [Rule 2 - Missing Critical Functionality] Added a deterministic post-running fault gate**
- **Found during:** Task 3 implementation
- **Issue:** A fast loopback provider left no reliable window to prove process loss after the running commit.
- **Fix:** Extended the existing provider/flow helpers with an owner-only bounded block marker, secure non-secret state, monotonic polling, disconnected-client handling, and original-row assertions.
- **Files modified:** `tools/phase2_mock_provider.py`, `tools/phase2_compose_flow.py`, `tools/phase2_smoke.sh`
- **Verification:** The real SIGKILL smoke passes repeatedly and leaves no containers, volumes, networks, images, or temporary files.
- **Committed in:** `1b1c29e`

---

**Total deviations:** 5 auto-fixed (3 Rule 1, 1 Rule 2, 1 Rule 3).
**Impact on plan:** Every deviation was required for a truthful deterministic recovery proof; no dependency, schema, endpoint, response, or task-identity scope was added.

## Issues Encountered

- Context7 MCP was unavailable and the documented `ctx7` CLI fallback was not installed. Celery 5.6 and SQLAlchemy 2.0 behavior was checked against official primary documentation before implementation.
- Repository-wide Ruff formatting still reports the two unrelated admin-user test files already recorded under Plan 02-25 in `deferred-items.md`. All files changed by Plan 02-29 pass the scoped format gate.
- The broad backend sweep still depends on an unpublished Redis test worker at port 56379 and retains two legacy last-admin CLI expectations. These four unrelated failures predate this plan and were not altered.

## Authentication Gates

None.

## Known Stubs

None.

## User Setup Required

None - production defaults are centralized, Compose supplies the four preview settings, and no dependency or manual credential change was introduced.

## Next Phase Readiness

- CR-09/G5 is closed with unit/integration, mutation, and actual process-loss evidence.
- Plans that enqueue preview jobs can rely on finite terminalization independently of worker callback survival and can retry terminal attempts without corrupting history.
- No Plan 02-29 checkpoint or blocker remains.

## Self-Check: PASSED

- The summary and all eight key production/test/deployment artifacts exist.
- All eight RED/GREEN/REFACTOR/regression commits are reachable in order from the current branch.
- Both Compose smoke projects completed cleanup; no Plan 02-29 containers, volumes, or networks remain.
- Every plan command, the 16/16 mutation gate, scoped static/security checks, and acceptance assertions were executed; the only repository-wide failures are the explicitly documented pre-existing deferred items.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
