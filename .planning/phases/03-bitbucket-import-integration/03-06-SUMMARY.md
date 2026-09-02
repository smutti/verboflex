---
phase: 03-bitbucket-import-integration
plan: 06
subsystem: bitbucket-import-diagnostics
tags: [bitbucket, structured-logging, sqlalchemy, pytest, tdd]

requires:
  - phase: 03-bitbucket-import-integration
    plan: 02
    provides: Durable logical imports, immutable execution identity, and baseline-preserving failure terminalization
  - phase: 03-bitbucket-import-integration
    plan: 05
    provides: Closed provider operation and failure vocabularies with one-attempt reads
provides:
  - Allowlisted structured Bitbucket failure events with safe operation, category, status, import, execution, and timing fields
  - Exactly one diagnostic after each durable terminal provider failure
  - Logging-handler isolation that cannot change import state or public error projection
affects: [03-07, 03-08, 03-10, operations, bitbucket-imports]

actuals:
  tokens: 8777
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Provider failures carry only a closed operation, closed category, and nullable safe status
    - Operational events are emitted after durable terminalization and never authorize public behavior
    - Logging failures are contained inside the diagnostic boundary

key-files:
  created:
    - backend/src/verboflex/integrations/bitbucket/diagnostics.py
    - backend/tests/integration/test_bitbucket_diagnostics.py
  modified:
    - backend/src/verboflex/integrations/bitbucket/client.py
    - backend/src/verboflex/services/import_jobs.py
    - backend/tests/integration/test_import_jobs.py
    - backend/tests/integration/test_bitbucket_http_adapter.py

key-decisions:
  - "Emit a provider-failure diagnostic only after the exact current import execution has durably transitioned to failed."
  - "Carry operation and provider status on the sanitized internal provider error; use the closed source-tree operation only for legacy discovery errors that lack operation metadata."
  - "Keep public import failures fixed at provider_unavailable while server diagnostics retain the closed provider category."

patterns-established:
  - "Terminalization-first diagnostics: database state commits before one bounded operational event is emitted."
  - "Closed error transport: internal provider errors contain only kind, nullable numeric status, and a Phase 3 read operation."

requirements-completed: [BITB-06]

coverage:
  - id: D1
    description: Structured diagnostics retain the required bounded operational fields and reject every seeded provider, credential, source, URL, path, and traceback canary.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_bitbucket_diagnostics.py
        status: pass
    human_judgment: false
  - id: D2
    description: Authentication, permission, rate-limit, missing-source, timeout, unavailable, invalid-source, and limit failures each produce one event and one fixed public projection.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py::test_terminal_provider_failure_emits_one_sanitized_diagnostic_and_public_error
        status: pass
    human_judgment: false
  - id: D3
    description: A failing logging handler cannot alter durable import terminalization or leak its exception into the public response.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py::test_diagnostic_handler_failure_cannot_change_import_terminalization
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-09-03
status: complete
---

# Phase 03 Plan 06: Sanitized Import Diagnostics Summary

**Terminal Bitbucket import failures now emit one correlated and timed allowlisted server event while public failures remain fixed and logging faults cannot affect durable state.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-09-02T21:50:23Z
- **Completed:** 2026-09-02T22:05:44Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Defined a typed diagnostic schema containing only a closed Phase 3 operation, closed error category, safe provider status, import/correlation UUID, positive execution sequence, and bounded elapsed milliseconds.
- Emitted exactly one event after durable terminalization for all eight required provider failure families while preserving the existing concise `provider_unavailable` public response.
- Proved recursively that provider bodies, credentials, authorization headers, source content, URLs, repository selectors, branch/path values, and tracebacks cannot enter the log record.
- Isolated logging-handler failures so the current execution still reaches `failed` and the logical import still reaches `import_failed`.

## Task Commits

Each TDD task was committed with a genuine RED followed by GREEN:

1. **Task 1 RED: require a closed structured diagnostic schema** - `69c20a0` (test)
2. **Task 1 GREEN: add sanitized Bitbucket diagnostics** - `fbf72c7` (feat)
3. **Task 2 RED: require terminal import failure diagnostics** - `809abf6` (test)
4. **Task 2 GREEN: emit terminal import diagnostics** - `107160c` (feat)

## Files Created/Modified

- `backend/src/verboflex/integrations/bitbucket/diagnostics.py` - Defines the allowlisted event schema, validation, timing cap, and logging-failure containment.
- `backend/src/verboflex/integrations/bitbucket/client.py` - Carries the exact closed provider operation and safe nullable status on provider errors.
- `backend/src/verboflex/services/import_jobs.py` - Times the attempt and emits one diagnostic only after exact durable failure terminalization.
- `backend/tests/integration/test_bitbucket_diagnostics.py` - Proves useful-field equality, invalid-field rejection, elapsed-time bounds, and recursive canary exclusion.
- `backend/tests/integration/test_import_jobs.py` - Proves the eight-category terminalization matrix, one attempt, one event, fixed public error, and logger isolation.
- `backend/tests/integration/test_bitbucket_http_adapter.py` - Updates the bounded adapter-error contract to include the new closed operation field.

## Decisions Made

- The stable logical import UUID is also the server correlation identity; the execution sequence distinguishes retries without exposing provider or queue identity.
- Diagnostics are subordinate to state: an obsolete execution that does not terminalize emits no terminal failure event.
- Provider category remains server-only metadata. The API continues returning one bounded `provider_unavailable` category and its fixed baseline-aware message.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated the existing adapter error-shape regression**
- **Found during:** Task 2 aggregate provider regression
- **Issue:** The pre-existing adapter test required exactly `kind` and `provider_status`, so the planned closed `operation` field correctly failed that old assertion.
- **Fix:** Added exact `REPOSITORY_METADATA` operation equality and updated the safe field inventory.
- **Files modified:** `backend/tests/integration/test_bitbucket_http_adapter.py`
- **Verification:** The complete 79-test provider/import aggregate passes.
- **Committed in:** `107160c`

**2. [Rule 1 - Bug] Re-enabled the bounded logger after process-local Alembic configuration**
- **Found during:** Task 2 GREEN verification
- **Issue:** Alembic disables loggers imported before its test-process configuration, preventing otherwise valid diagnostic events from reaching the capture handler.
- **Fix:** The diagnostic helper explicitly enables only its own named logger immediately before the bounded emission while retaining exception containment.
- **Files modified:** `backend/src/verboflex/integrations/bitbucket/diagnostics.py`
- **Verification:** The eight-category matrix and logging-handler failure test pass under the migrated PostgreSQL fixture.
- **Committed in:** `107160c`

---

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 3)
**Impact on plan:** Both changes were required to make the planned operation metadata and migrated-process diagnostics executable; neither widens the public or provider boundary.

## Issues Encountered

- Alembic's process-local logging setup disabled the named logger in the PostgreSQL integration fixture. The boundary now remains explicitly active and still accepts only the allowlisted payload.

## Verification

- `uv run pytest tests/integration/test_bitbucket_diagnostics.py tests/integration/test_import_jobs.py -x -k "diagnostic or sanitized_error"` - 25 passed, 9 deselected.
- `uv run pytest tests/integration/test_bitbucket_diagnostics.py tests/integration/test_import_jobs.py tests/integration/test_bitbucket_http_adapter.py tests/integration/test_bitbucket_discovery.py -x` - 79 passed.
- Ruff lint and format checks over all changed Python files - passed.
- Strict mypy over the three changed production modules - passed.

## TDD Gate Compliance

- Task 1 RED `69c20a0` precedes GREEN `fbf72c7`.
- Task 2 RED `809abf6` failed because no terminal event was emitted, then GREEN `107160c` satisfied the same unchanged matrix.
- No refactor commit was required after the final lint, format, type, and aggregate regression gates.

## Known Stubs

None. No placeholder, skipped test, or unrun verification remains.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-07 can add retry and latest-attempt behavior while reusing stable import/execution correlation.
- Plan 03-08 can extend the same closed operation metadata to ancestry and diffstat reads.
- No blocker remains from this plan.

## Self-Check: PASSED

- All six implementation and test artifacts exist.
- RED/GREEN commits `69c20a0`, `fbf72c7`, `809abf6`, and `107160c` are present in repository history.
- No failed self-check, skipped test, known stub, or unrun verification remains.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-03*
