---
phase: 03-bitbucket-import-integration
plan: 07
subsystem: bitbucket-import-state-machine
tags: [bitbucket, celery, postgresql, watchdog, concurrency, tdd]

requires:
  - phase: 03-bitbucket-import-integration
    plan: 02
    provides: Durable logical import, immutable execution, and source-reference persistence
  - phase: 03-bitbucket-import-integration
    plan: 03
    provides: Current expanded Bitbucket capability generation
  - phase: 03-bitbucket-import-integration
    plan: 05
    provides: One-attempt generation-bound provider read boundary
  - phase: 03-bitbucket-import-integration
    plan: 06
    provides: Sanitized terminal provider diagnostics
provides:
  - Stable logical import identity across refresh and administrator retry
  - Atomic direct and separate mapping baselines with ordered commit-bound references
  - Bounded worker-loss terminalization with no automatic retry or redispatch
affects: [03-08, 03-09, 03-10, 03-12, import-ui, reconciliation]

actuals:
  tokens: 16477
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - One logical import owns immutable generation-fenced execution records
    - A single execution-level pointer atomically activates complete direct or separate baselines
    - Celery Beat only terminalizes abandoned current executions and never redispatches them

key-files:
  created: []
  modified:
    - backend/src/verboflex/services/import_jobs.py
    - backend/src/verboflex/worker/import_tasks.py
    - backend/src/verboflex/worker/celery_app.py
    - backend/src/verboflex/core/config.py
    - backend/src/verboflex/api/v1/routes/admin_mappings.py
    - backend/tests/integration/test_import_jobs.py
    - backend/tests/architecture/test_background_boundaries.py

key-decisions:
  - "Use the immutable execution as the atomic consistency boundary: direct activates Source, while separate activates Keys and Translations only after both sides validate."
  - "Retain one stable logical UUID while fencing every completion by current execution, revision, mapping, topology, side identity, and connection generation."
  - "Recover worker loss with an inclusive hard-limit-plus-grace database watchdog that terminalizes only and never retries or enqueues work."

patterns-established:
  - "Complete-side validation: direct requires Direct; separate requires non-empty ordered Keys then Translations references."
  - "Worker-loss recovery: bounded FOR UPDATE SKIP LOCKED batches preserve the prior baseline and make late completion a no-op."

requirements-completed: [BITB-02, BITB-05, BITB-06]

coverage:
  - id: D1
    description: Refresh, failure, and administrator retry reuse one logical UUID while replacing only the current execution projection and preserving the last valid baseline.
    requirement: BITB-02
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py#transition/retry/current-capability/concurrency tests
        status: pass
    human_judgment: false
  - id: D2
    description: Separate mappings persist ordered Keys and Translations references under one execution and activate neither side after a partial failure.
    requirement: BITB-05
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py#separate baseline tests
        status: pass
    human_judgment: false
  - id: D3
    description: Interrupted workers terminalize once at the inclusive configured bound, retain the prior baseline, and reject late completion without redispatch.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py#worker-loss watchdog test
        status: pass
    human_judgment: false
  - id: D4
    description: Import execution and watchdog tasks use validated dedicated limits, JSON-only UUID delivery, late acknowledgement, and the service-owned route boundary.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py#import watchdog settings and named task test
        status: pass
      - kind: unit
        ref: backend/tests/architecture/test_background_boundaries.py#import background boundary test
        status: pass
    human_judgment: false

duration: 12min active
completed: 2026-09-03
status: complete
---

# Phase 03 Plan 07: Durable Import State Machine Summary

**Stable logical imports now preserve the last successful baseline across failures, activate separate repositories atomically, and recover interrupted workers without automatic retry.**

## Performance

- **Duration:** 12 min active (plus the approved tracer checkpoint interval)
- **Started:** 2026-09-02T22:12:27Z
- **Completed:** 2026-09-03T07:31:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Completed the locked run/refresh/retry transition table so one public import UUID survives all executions while immutable execution identities suppress stale workers and revoked generations.
- Expanded published imports from direct-only to direct and separate topologies; separate Keys and Translations references remain distinct even when paths match and become active through one pointer movement only after complete validation.
- Added dedicated validated import soft, hard, grace, and scan limits plus a named JSON Celery watchdog that claims bounded rows with `FOR UPDATE SKIP LOCKED`, terminalizes once, preserves the active baseline, and never redispatches.
- Preserved the API-to-worker boundary: HTTP routes call the injected UUID-only enqueuer and never import or execute task bodies.

## Task Commits

Each TDD task was committed with a genuine RED followed by GREEN:

1. **Task 1 RED: require logical import transition fencing** - `fbc5501` (test)
2. **Task 1 GREEN: complete logical import transitions** - `d64d320` (feat)
3. **Task 2 RED: require atomic separate imports and watchdog recovery** - `f99290b` (test)
4. **Task 2 GREEN: make imports atomic and recover worker loss** - `9ea2dab` (feat)

## Files Created/Modified

- `backend/src/verboflex/services/import_jobs.py` - Owns topology validation, logical transitions, complete-side reference validation, baseline activation, and stale-execution recovery.
- `backend/src/verboflex/worker/import_tasks.py` - Runs the UUID-only import task with dedicated limits and exposes the terminalization-only watchdog task.
- `backend/src/verboflex/worker/celery_app.py` - Registers the import watchdog schedule and import-specific task annotations alongside preview recovery.
- `backend/src/verboflex/core/config.py` - Validates finite ordered import execution and recovery limits under the 300-second cap.
- `backend/src/verboflex/api/v1/routes/admin_mappings.py` - Uses the stable start-or-refresh state-machine vocabulary.
- `backend/tests/integration/test_import_jobs.py` - Proves transitions, retries, generation fencing, direct/separate atomicity, ordered identity, worker loss, queue bounds, diagnostics, and baseline retention.
- `backend/tests/architecture/test_background_boundaries.py` - Proves named import worker registration and prevents route access to worker bodies.

## Decisions Made

- One `ImportExecution` is the complete baseline candidate. Its references are inserted and its job pointer moves in the same PostgreSQL transaction, so a separate mapping cannot expose mixed old/new sides.
- Reference order is semantic: Direct stands alone; separate references are grouped Keys then Translations, while `(repository_side, path)` keeps equal cross-side paths distinct.
- Timeout recovery uses the same fixed public failure projection as other import failures. It does not create an attempt-history surface or introduce an automatic retry path.
- Beat cadence is the minimum of preview and import scan intervals, preserving both independently validated recovery bounds.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The repository-wide backend suite reaches a pre-existing exact OpenAPI path assertion in `test_admin_products.py` that omits the three import routes added by Plan 03-01. This task's 93-test import/provider/diagnostic aggregate passes; the stale inventory is recorded in `deferred-items.md` for the Phase 3 gauntlet.
- Repository-wide Ruff format and strict mypy checks expose pre-existing out-of-scope findings. Every Plan 03-07 changed file passes Ruff check/format and every changed production module passes strict mypy; details are recorded in `deferred-items.md`.

## Verification

- `uv run pytest tests/integration/test_import_jobs.py tests/architecture/test_background_boundaries.py -x -k "separate or source_order or worker_loss or watchdog or background_boundary"` - 5 passed.
- `uv run pytest tests/integration/test_import_jobs.py tests/architecture/test_background_boundaries.py -x` - 32 passed.
- `uv run pytest tests/integration/test_preview_jobs.py -x -k "watchdog_settings or watchdog_schedule or task_delivery or named_watchdog_task"` - 12 passed.
- Import, provider adapter, discovery, diagnostic, and background-boundary aggregate - 93 passed.
- Ruff check and format verification over all six Task 2 source/test files - passed.
- Strict mypy over all four changed production modules - passed.

## TDD Gate Compliance

- Task 1 RED `fbc5501` preceded GREEN `d64d320` and was approved at the tracer checkpoint.
- Task 2 RED `f99290b` failed because separate mappings were excluded and no import watchdog schedule existed; GREEN `9ea2dab` passed the same unchanged contract.
- No refactor commit was required after the focused, aggregate, formatting, lint, and type gates.

## Known Stubs

None. No placeholder, skipped test, or unrun plan verification remains.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-08 can compare active commit-bound baselines against freshly resolved branches while relying on stable logical identity and complete separate-side provenance.
- Later polling and reconciliation UI can consume one current execution plus one valid active baseline without reconstructing attempt history.
- No Plan 03-07 blocker remains.

## Self-Check: PASSED

- All seven implementation and test artifacts exist.
- RED/GREEN commits `fbc5501`, `d64d320`, `f99290b`, and `9ea2dab` are present in repository history.
- Summary status, requirement traceability, verification evidence, and known-stub inventory are complete.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-03*
