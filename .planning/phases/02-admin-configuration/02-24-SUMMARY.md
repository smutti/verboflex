---
phase: 02-admin-configuration
plan: 24
subsystem: database
tags: [postgresql, alembic, sqlalchemy, composite-foreign-keys, triggers, tdd]

requires:
  - phase: 02-admin-configuration/02-21
    provides: Alembic 0008 client-credentials schema head and existing product publication/preview persistence
provides:
  - Database-enforced product, revision, mapping, and preview-job ownership graph
  - Non-null revision identity snapshots with bounded legacy backfill and corruption rejection
  - No-bypass PostgreSQL immutability guards for published revision roots, mappings, sides, and targets
  - Dependency-safe Alembic 0009 downgrade and verified re-upgrade path
affects: [02-admin-configuration/02-25, product-candidates, publication, preview-jobs, database-integrity]

actuals:
  tokens: 13798
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - Composite unique keys and foreign keys encode ownership at every cross-table graph edge
    - Published-child triggers lock revisions then owning products in stable order before authorizing writes
    - Publication persists candidate metadata before switching pointers inside one atomic transaction

key-files:
  created:
    - backend/alembic/versions/0009_product_graph_integrity.py
    - backend/tests/integration/test_product_graph_integrity.py
  modified:
    - backend/src/verboflex/models/product.py
    - backend/src/verboflex/models/product_mapping.py
    - backend/src/verboflex/models/preview_job.py
    - backend/src/verboflex/services/publication.py
    - backend/tests/integration/test_migrations.py

key-decisions:
  - "Reject any legacy cross-owner product or preview graph with one bounded integrity error before schema changes; never infer or silently repair ownership."
  - "Treat both the currently active graph and every published historical graph as immutable, with no session setting or trigger bypass."
  - "Serialize child writes against publication by locking affected revisions and their owning products in stable UUID order."
  - "Keep established ORM revision construction valid by snapshotting a missing identity from the owning Product while retaining database non-null authority."

patterns-established:
  - "Owned pointer: nullable Product pointers use (product_id, revision_id) composite foreign keys against a named composite unique key."
  - "Owned preview: every PreviewJob proves both product→candidate revision and candidate revision→mapping identity."
  - "Metadata-first publication: flush publication metadata while the revision is still candidate, then atomically switch Product pointers."

requirements-completed: [PROD-02, PROD-03, PROD-04, PROD-06, PROD-07, PROD-08]

coverage:
  - id: D1
    description: "Product active and candidate pointers cannot reference a revision owned by another product."
    requirement: PROD-02
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_product_graph_integrity.py#test_database_rejects_every_cross_graph_reference"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_migrations.py#test_product_graph_integrity_upgrade_downgrade_and_reupgrade"
        status: pass
    human_judgment: false
  - id: D2
    description: "Published mapping source branches and repository sides are immutable while candidate-side edits remain valid."
    requirement: PROD-03
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_product_graph_integrity.py#test_published_graph_is_immutable_but_candidate_graph_remains_editable"
        status: pass
    human_judgment: false
  - id: D3
    description: "Published allowed-target branch sets are immutable while valid candidate targets can be inserted and removed."
    requirement: PROD-04
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_product_graph_integrity.py#test_published_graph_is_immutable_but_candidate_graph_remains_editable"
        status: pass
    human_judgment: false
  - id: D4
    description: "Direct topology mapping roots, selected layouts, and repository identities cannot change after publication."
    requirement: PROD-06
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_product_graph_integrity.py#test_published_graph_is_immutable_but_candidate_graph_remains_editable"
        status: pass
    human_judgment: false
  - id: D5
    description: "Keys and translation repository-side rows remain revision-owned and immutable in published graphs."
    requirement: PROD-07
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_product_graph_integrity.py#test_published_graph_is_immutable_but_candidate_graph_remains_editable"
        status: pass
    human_judgment: false
  - id: D6
    description: "Preview jobs cannot combine a product with another product's candidate or a candidate with another revision's mapping."
    requirement: PROD-08
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_product_graph_integrity.py#test_database_rejects_every_cross_graph_reference"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_preview_jobs.py (targeted regression run excluding one pre-existing adapter-wiring failure)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 24: PostgreSQL Product Graph Integrity Summary

**Composite ownership keys and no-bypass PostgreSQL triggers now prevent cross-product graph corruption and every published-child mutation while preserving valid candidate edits and atomic publication.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-29T15:54:04Z
- **Completed:** 2026-08-29T16:18:54Z
- **Tasks:** 2
- **Files modified:** 10 implementation/test files
- **Actual estimate scale:** 13,798 tokens (55,191 realized diff characters / 4)

## Accomplishments

- Added Alembic 0009 with stable named composite ownership keys, non-null revision identity backfill, bounded preflight corruption rejection, and complete dependency-safe downgrade.
- Made PostgreSQL authoritative for the full published graph: revision identity, mapping roots, selected layouts, confirmations, repository sides, and allowed targets all reject direct SQL writes.
- Preserved editable candidate graphs and no-bypass publication by locking revision/product ownership in stable order and flushing metadata before the atomic pointer switch.
- Proved migration reversal, corrupt legacy rejection without reparenting, direct-SQL adversarial writes, repository registry adjacency, and publication concurrency/regression behavior on PostgreSQL 18.

## Task Commits

The plan-level TDD gates were committed atomically:

1. **RED: ownership and published-graph database contracts** — `8f69b8a` (test)
2. **GREEN: Alembic 0009, ORM metadata, and authoritative triggers** — `3f76950` (feat)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **RED migration:** `test_product_graph_integrity_migration_rejects_legacy_cross_ownership` failed because upgrading corrupt 0008 data did not raise an integrity error.
- **RED direct SQL:** `test_database_rejects_every_cross_graph_reference` failed because PostgreSQL accepted another product's revision as the active pointer.
- **GREEN Task 1:** `tests/integration/test_migrations.py -x` passed 6/6, including valid identity backfill, corrupt legacy rejection, downgrade to 0008, and re-upgrade.
- **GREEN Task 2:** graph integrity and publication suites passed 23/23.
- No refactor commit was needed; the final migration and model names were metadata-drift clean.

## Verification and Acceptance Evidence

- Required combined migration, graph, and publication verification: **29 passed**.
- Final product/mapping/preview/repository regression gauntlet: **140 passed**, with one unrelated pre-existing preview-adapter test explicitly deselected and recorded below.
- Standalone disposable PostgreSQL cycle: `upgrade head` → `alembic check` → `downgrade 0008_bitbucket_client_credentials` → `upgrade head`; **pass**, final head `0009_product_graph_integrity` and no new upgrade operations.
- Adversarial direct SQL: cross-product pointers, cross-product preview candidates, cross-revision mappings, active/published revision roots, mappings, sides, and targets all rejected; valid candidate equivalents passed.
- Static checks: changed-file Ruff format **pass**, repository-wide Ruff lint **pass**, mypy across 81 source files **pass**, and `git diff --check` **pass**.
- Full diagnostic backend sweep collected 719 tests. Two Plan 02-24 schema/order failures found by that sweep were fixed; six unrelated existing/infrastructure failures remain recorded in `deferred-items.md`.

## Files Created/Modified

- `backend/alembic/versions/0009_product_graph_integrity.py` — bounded preflight, identity backfill, composite ownership constraints, full graph triggers, and reversible downgrade.
- `backend/src/verboflex/models/product.py` — owned Product pointers, revision identity snapshots, view-only pointer relationships, and compatibility snapshot population.
- `backend/src/verboflex/models/product_mapping.py` — mapping ownership composite uniqueness and single-parent child relationships.
- `backend/src/verboflex/models/preview_job.py` — product/candidate and candidate/mapping composite ownership declarations.
- `backend/src/verboflex/services/publication.py` — metadata-first flush before atomic pointer promotion.
- `backend/tests/integration/test_migrations.py` — valid backfill/reversal and corrupt legacy migration contracts.
- `backend/tests/integration/test_product_graph_integrity.py` — direct-SQL ownership, full immutability, candidate-edit, and no-bypass proof.
- `backend/tests/integration/test_product_publication.py` — publication fixture ordering aligned with database authority.
- `backend/tests/api/test_admin_products.py` — lifecycle fixture ordering aligned with immutable graph construction.
- `backend/tests/unit/test_product_names.py` — deployed identity/constraint/trigger schema assertions and metadata-first publication helper.

## Decisions Made

- Corrupt legacy graphs abort the migration with `legacy product graph ownership violation`; the migration does not expose row identifiers and never reparents data.
- Published history remains immutable even after another revision becomes active, so both old and new active graphs are protected after publication.
- The trigger has no `current_setting`, `set_config`, bypass marker, role exception, or caller-specific path; every caller crosses the same database authority.
- Child mutation locks affected revisions in UUID order and then their owning Product rows, serializing candidate edits with publication metadata and pointer authority.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Made existing publication obey the required metadata-first database ordering**
- **Found during:** Task 2 publication regression verification
- **Issue:** The service dirtied revision metadata and Product pointers in one flush, allowing SQLAlchemy to update the pointer first and causing the new authoritative trigger to reject otherwise valid publication.
- **Fix:** Flushed candidate publication metadata before assigning active/candidate pointers, inside the same transaction so any later failure still rolls back atomically.
- **Files modified:** `backend/src/verboflex/services/publication.py`
- **Verification:** Publication regressions passed 20/20, including the concurrent equal-retry/stale-writer proof.
- **Committed in:** `3f76950`

**2. [Rule 2 - Missing Critical] Preserved established ORM revision construction with non-null identity snapshots**
- **Found during:** Task 2 publication regression verification
- **Issue:** Existing service and test construction paths omitted the new non-null revision identity columns and failed before exercising publication behavior.
- **Fix:** Added a mapper insert hook that copies only missing snapshot values from the already-persisted owning Product; explicit caller values remain authoritative.
- **Files modified:** `backend/src/verboflex/models/product.py`
- **Verification:** Product, mapping, preview, publication, and API regression gauntlet passed 140 selected tests.
- **Committed in:** `3f76950`

**3. [Rule 3 - Blocking] Reordered published test fixtures to construct complete candidate graphs before publication**
- **Found during:** Broader publication and administrator lifecycle verification
- **Issue:** Legacy fixtures inserted mapping children beneath revisions already marked published, which the new database authority correctly rejects.
- **Fix:** Fixtures now build complete unpublished graphs, persist publication metadata, then assign active pointers—the same required production order.
- **Files modified:** `backend/tests/integration/test_product_publication.py`, `backend/tests/api/test_admin_products.py`, `backend/tests/unit/test_product_names.py`
- **Verification:** Publication passed 20/20, administrator products passed 13/13, and product-name/schema tests passed 14/14.
- **Committed in:** `3f76950`

**4. [Rule 1 - Bug] Finalized Alembic check-constraint names under the metadata naming convention**
- **Found during:** Standalone disposable `alembic check`
- **Issue:** Unfinalized full names received a second naming-convention prefix in the deployed database and produced metadata drift.
- **Fix:** Wrapped the two revision identity check names with `op.f(...)` for both creation and downgrade removal.
- **Files modified:** `backend/alembic/versions/0009_product_graph_integrity.py`
- **Verification:** Disposable `alembic check` reports no new upgrade operations; downgrade and re-upgrade both pass.
- **Committed in:** `3f76950`

---

**Total deviations:** 4 auto-fixed (2 Rule 2 missing critical, 1 Rule 3 blocking, 1 Rule 1 bug)
**Impact on plan:** Every fix was required to keep the prescribed database authority compatible, reversible, and atomically publishable; no new dependency, endpoint, table, or bypass surface was added.

## Issues Encountered

- Context7 was not installed in the executor environment. The documented CLI fallback also reported `ctx7 not found`; no new library API or dependency was introduced, and implementation followed the existing pinned Alembic/SQLAlchemy project patterns.
- PostgreSQL client executables `createdb`/`dropdb` were absent. Disposable database lifecycle was rerun successfully through the already-installed psycopg driver.
- The full backend diagnostic sweep exposed six unrelated existing/infrastructure failures. They are documented in `.planning/phases/02-admin-configuration/deferred-items.md` and do not affect any Plan 02-24 acceptance criterion.

## Authentication Gates

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration or dependency change is required.

## Next Phase Readiness

- Plan 02-25 can safely deep-clone active graphs into candidates and promote revision-owned identity because database ownership and immutability are now authoritative.
- The shared `PROD-02`, `PROD-03`, `PROD-04`, `PROD-06`, `PROD-07`, and `PROD-08` requirement IDs remain ledger-pending until all later Phase 2 gap-closure plans that declare them are summarized.
- No Plan 02-24 checkpoint or blocker remains.

## Self-Check: PASSED

- Both created artifacts and all eight modified implementation/test artifacts exist.
- RED commit `8f69b8a` precedes GREEN commit `3f76950`; both are reachable from the current branch.
- Required task commands, adversarial SQL, publication regressions, repository adjacency checks, static analysis, and disposable migration replay all pass.
- No tracked deletion, generated dependency change, skipped Plan 02-24 test, unrun verification, stub, bypass setting, silent reparenting, or unmodeled threat surface remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
