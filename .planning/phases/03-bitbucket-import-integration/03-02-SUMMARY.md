---
phase: 03-bitbucket-import-integration
plan: 02
subsystem: bitbucket-import
tags: [postgresql, sqlalchemy, alembic, fastapi, authorization, tdd]

requires:
  - phase: 03-bitbucket-import-integration
    plan: 01
    provides: Durable logical imports, immutable executions, published mapping routes, and UUID-only dispatch
provides:
  - Database-authoritative import ownership, state, identity, and immutable provenance constraints
  - Fail-first administrator authorization and exact active-product mapping ownership
  - Baseline-preserving terminal behavior for empty source selections and failed dispatch
  - Closed import response and OpenAPI contracts without provider, credential, source, or attempt internals
affects: [03-05, 03-06, 03-07, 03-08, 03-09, 03-10, 03-12]

actuals:
  tokens: 11099
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - PostgreSQL composite ownership and immutable terminal provenance remain authoritative over ORM writes
    - Import access requires an active product and its exact active published revision before any durable or queue work
    - Failed refresh attempts retain the last successful baseline while replacing only current bounded failure state

key-files:
  created: []
  modified:
    - backend/alembic/versions/0012_import_jobs.py
    - backend/src/verboflex/models/import_job.py
    - backend/src/verboflex/models/__init__.py
    - backend/src/verboflex/services/import_jobs.py
    - backend/tests/integration/test_migrations.py
    - backend/tests/integration/test_import_jobs.py
    - backend/tests/api/test_openapi_contract.py

key-decisions:
  - "An active Product is part of import authority for list, start, status, and worker currentness; a retained active-revision pointer on an inactive Product grants no import access."
  - "An execution that selects zero source files is terminally failed and never replaces a prior successful baseline."
  - "Public import schemas expose repository selectors and commit-bound metadata only; credentials, provider diagnostics, source bytes, queue identity, and attempt history remain internal."

patterns-established:
  - "Fail-first import boundary: authenticate and authorize, lock the active Product graph, validate exact mapping ownership, then persist and dispatch."
  - "Baseline preservation: current execution failure changes latest state and bounded error only; active_baseline_execution_id remains unchanged."

requirements-completed: [BITB-02, BITB-05, BITB-06]

coverage:
  - id: D1
    description: PostgreSQL enforces the reversible import graph, composite ownership, valid states, unique identities, and immutable terminal provenance.
    requirement: BITB-05
    verification:
      - kind: integration
        ref: backend/tests/integration/test_migrations.py::test_import_schema_is_reversible_and_database_authoritative
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_migrations.py::test_immutable_source_reference_and_terminal_execution_provenance
        status: pass
    human_judgment: false
  - id: D2
    description: Anonymous and non-admin callers fail before mapping, write, or dispatch work, and invalid ownership identities remain unavailable.
    requirement: BITB-02
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py::test_import_authorization_fails_before_mapping_or_dispatch_work
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py::test_import_ownership_rejects_candidate_inactive_wrong_and_forged_identities
        status: pass
    human_judgment: false
  - id: D3
    description: Empty source selections and failed dispatch terminalize safely without erasing the previous successful baseline.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py::test_import_empty_source_terminalizes_and_preserves_the_last_baseline
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py::test_import_enqueue_failure_is_terminal_bounded_and_baseline_preserving
        status: pass
    human_judgment: false
  - id: D4
    description: Import OpenAPI and response graphs exclude credential, provider, raw source, queue, stack, and attempt-history fields.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/api/test_openapi_contract.py::test_import_public_contract_is_closed_and_provider_source_history_free
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-09-02
status: complete
---

# Phase 03 Plan 02: Import Authority and Failure Boundaries Summary

**Published-mapping imports now have reversible database authority, immutable provenance, fail-first access control, baseline-preserving failures, and a closed public contract.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-02T20:24:12Z
- **Completed:** 2026-09-02T20:36:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Hardened the import schema with named state, ownership, uniqueness, current-execution, baseline, and immutable-provenance authority and verified upgrade, downgrade, and re-upgrade on PostgreSQL.
- Closed list, start, status, and worker access to the exact active Product and its active published mapping while proving anonymous and all non-admin roles cause no import or dispatch work.
- Made empty selections and failed queue dispatch terminal, bounded, and unable to replace the last successful baseline.
- Froze all three import operations and their recursive public schema graph without leaking credentials, provider diagnostics, source bytes, task identities, or attempt history.

## Task Commits

1. **Task 1 RED: require import schema authority** — `8d90feb` (test)
2. **Task 1 GREEN: harden import provenance schema** — `093f62f` (feat)
3. **Task 2 RED: require authorization, ownership, failure, and leakage boundaries** — `28c115a` (test)
4. **Task 2 GREEN: close import failure boundaries** — `44cf822` (feat)
5. **Plan refactor: normalize expanded migration tests** — `9bffeb5` (refactor)

## Files Created/Modified

- `backend/alembic/versions/0012_import_jobs.py` — Adds named composite ownership, baseline, and immutable provenance database authority with dependency-safe downgrade.
- `backend/src/verboflex/models/import_job.py` — Aligns SQLAlchemy metadata with the hardened import schema.
- `backend/src/verboflex/models/__init__.py` — Registers the complete import model graph.
- `backend/src/verboflex/services/import_jobs.py` — Rejects inactive Product authority and zero-reference execution results while preserving prior baselines.
- `backend/tests/integration/test_migrations.py` — Proves reversible schema authority, malformed and cross-owner rejection, and terminal provenance immutability.
- `backend/tests/integration/test_import_jobs.py` — Proves role, ownership, empty-source, dispatch, baseline, and response-leakage matrices.
- `backend/tests/api/test_openapi_contract.py` — Freezes import operations and recursively rejects internal provider/source/history properties.

## Decisions Made

- A Product must be active at every public and worker import authority boundary; retaining an active revision on a deactivated Product is not sufficient.
- An empty selected-source set is a failed execution, not a valid empty baseline.
- The public error category remains bounded to `provider_unavailable` in this plan; raw dispatch exceptions and their content are never persisted or returned.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected product lifecycle OpenAPI path classification**
- **Found during:** Task 2 full contract regression
- **Issue:** The lifecycle test used substring matching, so the new `published` import routes were incorrectly classified as product `publish` actions.
- **Fix:** Match only the exact final lifecycle path segment.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`
- **Verification:** The complete migration, import, and OpenAPI suite passes.
- **Committed in:** `44cf822`

---

**Total deviations:** 1 auto-fixed (1 Rule 1)
**Impact on plan:** The correction was required for the existing exact route inventory to recognize the planned import endpoints without weakening lifecycle coverage.

## Issues Encountered

- The RED matrices confirmed two implementation defects: inactive Products retained import authority and an empty reference tuple became a successful baseline. Both are now closed by minimal service predicates.
- The previously expanded import routes were absent from the exact global OpenAPI inventory. Task 2 added them as part of its planned public-contract coverage.

## TDD Gate Compliance

- Task 1: RED `8d90feb` precedes GREEN `093f62f`.
- Task 2: RED `28c115a` reproduced inactive-product and empty-source failures before GREEN `44cf822`.
- Final focused gate: 35/35 PostgreSQL migration, import integration, and OpenAPI contract tests pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Import schema, ownership, failure, and leakage invariants are ready for capability validation and provider-bound execution expansion.
- No blocker or known stub remains from this plan.

## Self-Check: PASSED

- All seven implementation and test artifacts exist.
- All five RED, GREEN, and REFACTOR commits are present in repository history.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-02*
