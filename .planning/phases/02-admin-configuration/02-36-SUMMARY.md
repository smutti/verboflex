---
phase: 02-admin-configuration
plan: 36
subsystem: database
tags: [postgresql, alembic, sqlalchemy, partial-index, explain, tdd]

requires:
  - phase: 02-admin-configuration/02-24
    provides: Linear Alembic 0009 head and database-enforced PreviewJob ownership graph
provides:
  - Running-only state/started_at PostgreSQL access path for the bounded preview watchdog
  - Exact SQLAlchemy metadata parity for the named partial index
  - Reversible row/UUID-preserving migration and PostgreSQL EXPLAIN proof
affects: [02-admin-configuration/02-29, preview-watchdog, preview-jobs, database-performance]

actuals:
  tokens: 3759
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - Named PostgreSQL partial indexes are declared identically in Alembic and SQLAlchemy metadata
    - Query-plan tests use transaction-local planner settings and inspect the recursive JSON plan tree

key-files:
  created:
    - backend/alembic/versions/0010_preview_watchdog_index.py
  modified:
    - backend/src/verboflex/models/preview_job.py
    - backend/tests/integration/test_migrations.py

key-decisions:
  - "Index only PreviewJob rows whose state is exactly running, using the exact state/started_at key order required by the watchdog age predicate."
  - "Retain PreviewJob.id as the sole UUID primary key and Celery task identity; add no schema or model task_id field."
  - "Prove planner reachability with SET LOCAL enable_seqscan = off so the test demonstrates index usability without assuming a global PostgreSQL cost choice."

patterns-established:
  - "Migration/metadata parity: one explicit index name, column order, and partial predicate is shared by deployed DDL and ORM metadata."
  - "Bounded EXPLAIN proof: recursively inspect FORMAT JSON while asserting the exact filtered, ordered, 100-row selector output."

requirements-completed: [PROD-08, PROD-09]

coverage:
  - id: D1
    description: "Alembic 0010 and PreviewJob metadata expose the exact running-only state/started_at watchdog index without changing durable task identity."
    requirement: PROD-08
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_migrations.py#test_preview_watchdog_index_upgrade_downgrade_and_reupgrade_preserves_rows"
        status: pass
      - kind: unit
        ref: "backend/tests/integration/test_migrations.py#test_preview_job_identity_remains_uuid_without_task_id"
        status: pass
    human_judgment: false
  - id: D2
    description: "PostgreSQL can use the named partial index for the exact running-only started_at/id ordered selector bounded to 100 rows while excluding every other state."
    requirement: PROD-09
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_migrations.py#test_preview_watchdog_explain_reaches_partial_index_and_bounded_selector"
        status: pass
      - kind: integration
        ref: "cd backend && uv run pytest tests/integration/test_migrations.py -q"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 36: Preview Watchdog Index Summary

**A linear Alembic 0010 migration and matching SQLAlchemy metadata now provide a reversible running-only preview watchdog index with PostgreSQL EXPLAIN proof and unchanged UUID task identity.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-08-29T17:55:16Z
- **Completed:** 2026-08-29T18:01:26Z
- **Tasks:** 2
- **Files modified:** 3
- **Actual estimate scale:** 3,759 tokens (15,036 realized diff characters / 4)

## Accomplishments

- Added the single Alembic head `0010_preview_watchdog_index` after `0009_product_graph_integrity`, creating only `ix_preview_jobs_watchdog_state_started_at` on `(state, started_at)` where `state = 'running'`.
- Preserved every preview row and UUID across upgrade, downgrade to 0009, and re-upgrade while keeping `PreviewJob.id` as the sole primary-key/Celery identity and exposing no `task_id` field.
- Proved PostgreSQL can reach the named partial index for the exact running-only age predicate ordered by `started_at, id`, bounded to 100 rows, with all queued/succeeded/failed/timed_out rows excluded.

## Task Commits

The plan-level RED/GREEN/REFACTOR gates were committed atomically:

1. **RED: reversible watchdog migration, identity, and EXPLAIN contracts** — `2328386` (test)
2. **GREEN: linear Alembic 0010 and matching PreviewJob partial index** — `3e71038` (feat)
3. **REFACTOR: typed UUID retention and recursive EXPLAIN helpers** — `1ae0129` (refactor)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **RED:** the focused Task 1 command failed 2 tests because Alembic could not locate `0010_preview_watchdog_index` and SQLAlchemy metadata exposed no watchdog index.
- **GREEN:** the unchanged Task 1 command passed 2 tests; the tracer was then rerun unchanged and passed before Task 2 began.
- **REFACTOR:** the complete Task 2 command passed 3 tests after extracting typed UUID and JSON-plan traversal helpers.
- Git history contains the required `test(02-36)` → `feat(02-36)` → `refactor(02-36)` sequence.

## Verification and Acceptance Evidence

- Task 1 command: `2 passed, 7 deselected`; unchanged tracer rerun also passed.
- Task 2 command: `3 passed, 6 deselected`.
- Complete migration suite: `9 passed` against isolated PostgreSQL databases.
- Alembic reports exactly one head: `0010_preview_watchdog_index`; history proves parent `0009_product_graph_integrity`.
- Disposable schema rehearsal passed `upgrade head` → `alembic check` → `downgrade 0009_product_graph_integrity` → `upgrade head`; Alembic reported no new upgrade operations.
- Static checks: mypy passed all 81 source files, Ruff lint passed `src tests`, all three Plan 02-36 files passed Ruff format, and `git diff --check` passed.
- Security/supply-chain checks: scoped detect-secrets returned no findings, `uv lock --check` passed, and pip-audit reported no known vulnerabilities.

## Files Created/Modified

- `backend/alembic/versions/0010_preview_watchdog_index.py` — linear, precise create/drop migration for the running-only watchdog index.
- `backend/src/verboflex/models/preview_job.py` — exact matching partial-index metadata with unchanged UUID primary key.
- `backend/tests/integration/test_migrations.py` — retained-row/UUID, exact predicate, downgrade/re-upgrade, every-state exclusion, deterministic ordering, and JSON EXPLAIN coverage.

## Decisions Made

- The physical key remains exactly `(state, started_at)`; `id` remains the existing deterministic tiebreaker in the consumer query rather than a second task identity or an unplanned wider index.
- The partial predicate remains exactly `state = 'running'`, so queued and every terminal state are absent from the watchdog access path.
- The query-plan proof disables sequential scans only within its PostgreSQL transaction and restores normal planner behavior automatically when the transaction ends.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Context7 MCP was unavailable and the documented `ctx7` CLI fallback was not installed. No new dependency or unfamiliar API surface was introduced; implementation followed the repository's pinned SQLAlchemy/Alembic partial-index pattern and was validated by `alembic check` against PostgreSQL.
- Repository-wide Ruff formatting still reports the three unrelated test files already recorded under Plan 02-25 in `deferred-items.md`. All Plan 02-36 files pass the scoped format gate; those unrelated files were left untouched.
- Alembic check emits the existing product-mapping/preview-job foreign-key cycle warning, then completes with no new upgrade operations. Plan 02-36 adds no constraint or dependency cycle.

## Authentication Gates

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration or dependency change is required.

## Next Phase Readiness

- Plan 02-29 can implement the 100-row `FOR UPDATE SKIP LOCKED` watchdog selector against the proven named access path.
- Shared `PROD-08` and `PROD-09` completion remains subject to the sibling-plan readiness gate.
- No Plan 02-36 checkpoint or blocker remains.

## Self-Check: PASSED

- The created migration and both modified source/test files exist.
- RED commit `2328386`, GREEN commit `3e71038`, and REFACTOR commit `1ae0129` are reachable in order from the current branch.
- Both plan commands, the tracer rerun, the complete migration suite, Alembic single-head/check/reversal, static analysis, secret scan, supply-chain audit, and acceptance assertions pass.
- No tracked deletion, package change, skipped test, unrun plan verification, stub, new task-identity field, row/UUID rewrite, or unmodeled threat surface remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
