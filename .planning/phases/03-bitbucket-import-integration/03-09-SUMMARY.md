---
phase: 03-bitbucket-import-integration
plan: 09
subsystem: bitbucket-import-reconciliation
tags: [bitbucket, postgres, fastapi, reconciliation, concurrency, tdd]

requires:
  - phase: 03-bitbucket-import-integration
    plan: 08
    provides: Complete mapping-scoped equal, fast-forward, and rewritten-history evidence
provides:
  - Durable complete rewrite proposals with exact mapping, execution, generation, commit, delta, and digest identity
  - Bounded administrator comparison responses with ordered direct or Keys-then-Translations metadata
  - Atomic explicit baseline confirmation that preserves immutable historical executions
affects: [03-10, 03-11, 03-13, phase-06, phase-08, import-reconciliation]

actuals:
  tokens: 26996
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Complete rewrite evidence is persisted as immutable proposal and ordered-delta sidecars before it can authorize confirmation
    - Confirmation locks Product, mapping, logical import, and proposal in stable order and revalidates every current identity
    - A reconstructible SHA-256 digest binds persisted authority without exposing provider bodies, URLs, credentials, or source bytes

key-files:
  created:
    - backend/alembic/versions/0013_import_rewrite_proposals.py
  modified:
    - backend/src/verboflex/models/__init__.py
    - backend/src/verboflex/models/import_job.py
    - backend/src/verboflex/services/import_jobs.py
    - backend/src/verboflex/schemas/imports.py
    - backend/src/verboflex/api/v1/routes/admin_mappings.py
    - backend/tests/integration/test_import_jobs.py
    - backend/tests/integration/test_migrations.py

key-decisions:
  - "Keep the active baseline pointer unchanged until a complete current proposal is explicitly confirmed; old and proposed executions remain immutable."
  - "Bind browser confirmation to proposal UUID, proposed execution UUID, and a reconstructible full-authority digest, then revalidate ownership, topology, revision version, generation, commits, and ordered delta under locks."
  - "Treat direct and separate mappings as one confirmation boundary; separate Keys and Translations move through the single logical baseline pointer together."
  - "Return a distinct bounded stale-proposal 409 for obsolete, duplicate, generation-changed, or identity-mismatched confirmation attempts."

patterns-established:
  - "Current proposal lookup: only one pending complete mapping-scoped proposal can produce a public comparison."
  - "Baseline identity guard: downstream work must pass the exact current ImportExecution UUID through require_current_import_baseline."

requirements-completed: [BITB-05, BITB-06]

coverage:
  - id: D1
    description: Complete direct, separate, and zero-delta rewrite evidence persists with reversible ownership-safe PostgreSQL constraints while the old baseline remains active.
    requirement: BITB-05
    verification:
      - kind: integration
        ref: backend/tests/integration/test_migrations.py#rewrite migration contracts
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py#rewrite proposal contracts
        status: pass
    human_judgment: false
  - id: D2
    description: Administrators can read only a complete current metadata-only comparison in canonical side and file order with exact commits and bounded counts.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py#rewrite comparison contracts
        status: pass
    human_judgment: false
  - id: D3
    description: Confirmation atomically advances one direct or separate mapping baseline only for fresh full identity, while stale and duplicate requests change nothing and old executions become non-current.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py#rewrite confirmation and current baseline contracts
        status: pass
    human_judgment: false

duration: 46min
completed: 2026-09-03
status: complete
---

# Phase 03 Plan 09: Durable Rewrite Confirmation Summary

**Complete mapping-scoped rewritten-history evidence now remains inert until an administrator atomically confirms its exact current proposal, execution, generation, commits, and ordered metadata digest.**

## Performance

- **Duration:** 46 min
- **Started:** 2026-09-03T08:02:23Z
- **Completed:** 2026-09-03T08:46:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added a reversible PostgreSQL proposal model whose immutable identity binds product, published revision/version, mapping/topology, logical import, old baseline, proposed execution, connection generation, exact side commits, completeness, and ordered localization-file delta.
- Added a closed secret-free comparison API that returns only current proposal identity, exact commits, bounded Added/Modified/Removed counts, and stable metadata rows.
- Added atomic direct and separate confirmation with stable lock order, full currentness and digest revalidation, explicit administrator attribution, and distinct stale-proposal conflicts.
- Preserved every prior execution and source reference; only the logical import's active-baseline pointer moves, and `require_current_import_baseline` rejects the old identity afterward.

## Task Commits

Each TDD task has a genuine RED commit followed by its GREEN implementation:

1. **Task 1 RED: durable rewrite proposal contracts** - `6893192` (test)
2. **Task 1 GREEN: proposal schema and persistence** - `1ea8db2` (feat)
3. **Task 2 RED: comparison and confirmation contracts** - `fa86bb1` (test)
4. **Task 2 GREEN: bounded comparison and atomic confirmation** - `a6e302c` (feat)

## Files Created/Modified

- `backend/alembic/versions/0013_import_rewrite_proposals.py` - Creates reversible proposal/delta tables and database guards for ownership, currentness, status transitions, immutability, and canonical delta order.
- `backend/src/verboflex/models/__init__.py` - Registers rewrite models in canonical SQLAlchemy metadata.
- `backend/src/verboflex/models/import_job.py` - Defines complete proposal and ordered metadata-delta persistence.
- `backend/src/verboflex/services/import_jobs.py` - Validates and persists complete evidence, reconstructs and checks its digest, reads current comparisons, confirms under locks, and guards current baseline identity.
- `backend/src/verboflex/schemas/imports.py` - Defines closed bounded comparison and confirmation contracts.
- `backend/src/verboflex/api/v1/routes/admin_mappings.py` - Exposes administrator-only comparison and confirmation operations with bounded 404/409 behavior.
- `backend/tests/integration/test_import_jobs.py` - Covers direct, separate, zero-delta, ownership, incomplete evidence, stale identity, generation change, duplicate confirmation, atomic pointer movement, and secret-free responses.
- `backend/tests/integration/test_migrations.py` - Covers upgrade, downgrade, re-upgrade, constraints, triggers, and forged authority rejection.

## Decisions Made

- Proposal status transitions are the audit record: a new retry supersedes prior pending authority, while confirmation records its timestamp and administrator without rewriting identity fields.
- The confirmation digest is computed only from persisted, reconstructible authority fields and ordered delta ordinals, allowing lock-time integrity verification before pointer movement.
- Missing or cross-owned resources remain 404; an existing proposal whose authority is no longer current returns the dedicated `Import rewrite proposal stale` 409.
- Zero localization-file delta remains confirmable because divergent commit history, not file-count magnitude, is what requires the explicit decision.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Registered the new proposal models in canonical metadata**
- **Found during:** Task 1 (Persist one complete current rewrite proposal)
- **Issue:** The plan's file list did not include the model registry, but migrations and runtime metadata could not consistently discover the new tables without it.
- **Fix:** Exported `ImportRewriteProposal` and `ImportRewriteDelta` through `backend/src/verboflex/models/__init__.py`.
- **Files modified:** `backend/src/verboflex/models/__init__.py`
- **Verification:** Migration upgrade/downgrade/re-upgrade and all import integration tests pass.
- **Committed in:** `1ea8db2`

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking issue)
**Impact on plan:** The additional registry edit is required for schema discovery and does not expand product scope.

## Issues Encountered

- A first RED test run received route-level 404 because the comparison and confirmation operations did not yet exist; this was the expected failing contract before GREEN implementation.
- Lock-time digest verification required the stored digest shape to be reconstructible from proposal and ordered-delta rows. The digest was normalized to those complete persisted fields before any release artifact depended on the earlier internal form.

## Verification

- Focused Task 1 proposal/migration suite: 10/10 passed; import aggregate 47/47 passed; migrations 13/13 passed.
- Focused Task 2 comparison/confirmation/current-baseline/separate suite: 13/13 passed.
- Final import and migration aggregate: 67/67 passed.
- Ruff lint and format checks over all plan source and test targets: passed.
- Strict mypy over the comparison/confirmation service, schemas, and routes: passed.
- No package or provider mutation capability was added; all responses remain metadata-only and secret-free.

## TDD Gate Compliance

- Task 1 RED `6893192` preceded GREEN `1ea8db2`; the tracer was explicitly approved before expansion.
- Task 2 RED `fa86bb1` failed on the absent comparison route before GREEN `a6e302c` passed the unchanged contract plus direct/separate expansion cases.
- No refactor commit was required after aggregate test, lint, formatting, and strict type gates.

## Known Stubs

None. No placeholder, skipped test, TODO, FIXME, or unrun plan verification remains.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-10 can freeze pagination, capability, action, error, and the complete five-operation API contract around these comparison and confirmation services.
- Plans 03-11 and 03-13 can generate and consume the exact proposal identity without client-side ancestry or completeness inference.
- Later pending-edit and submission work can reject obsolete baselines through `require_current_import_baseline`; provider writes remain unavailable until Phase 8.

## Self-Check: PASSED

- All eight implementation and test artifacts plus this summary exist.
- RED/GREEN commits `6893192`, `1ea8db2`, `fa86bb1`, and `a6e302c` are present in repository history.
- Summary status, requirements, coverage, TDD order, verification evidence, threat-boundary disposition, and stub inventory are complete.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-03*
