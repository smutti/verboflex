---
phase: 04-localization-import-search-and-constraints
plan: 10
subsystem: localization-persistence
tags: [postgresql, sqlalchemy, alembic, canonical-identity, constraints]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [08]
    provides: normalized nullable base-language authority on revision-owned mappings
provides:
  - stable semantic localization scopes with canonical key and value identity
  - immutable value history, mutable locators, tombstones, and execution-owned staging provenance
  - versioned explicit key-language maximum-length constraints with materialized violation projections
  - closed persisted vocabularies and typed SQLAlchemy ownership relationships
affects: [04-11, 04-13, 04-15, 04-21, imports, search, review, write-back]
tech-stack:
  added: []
  patterns:
    - stable semantic identity separated from mutable repository locators
    - immutable import provenance with database-enforced execution ownership
    - explicit constraint rows plus transactionally materialized effective projections
key-files:
  created:
    - backend/alembic/versions/0016_canonical_translations.py
    - backend/src/verboflex/models/translation.py
    - backend/src/verboflex/models/translation_constraint.py
  modified:
    - backend/src/verboflex/models/__init__.py
    - backend/src/verboflex/models/import_job.py
    - backend/src/verboflex/models/product_mapping.py
    - backend/tests/integration/test_migrations.py
    - backend/tests/unit/localization/importing/test_contracts.py
key-decisions:
  - "Canonical group identity is product plus semantic mapping scope, repository, configured branch, and raw key; paths and positions remain mutable locators."
  - "Value identity adds exact language and the SHA-256 digest of versioned canonical selector bytes; raw decoded key and text are never normalized."
  - "Constraints store only explicit key-language rules; effective authority is materialized as none, base_default, or language_override with exact consistency checks."
  - "Product mappings expose localization scopes through a read-only composite relationship so revision UUIDs cannot become semantic identity."
patterns-established:
  - "Every canonical child row carries composite database ownership back to its stable scope, key, import job, or execution authority."
  - "Current values are tombstoned in place while immutable revisions retain last-known text, state, commit, execution, and correlation provenance."
requirements-completed: [FMT-07, FMT-08, CONS-01, CONS-02, CONS-03, CONS-04]
coverage:
  - id: D1
    description: Stable canonical scope, key, and individually addressable value identities preserve exact raw keys and typed selectors independently of paths.
    requirement: FMT-07
    verification:
      - kind: integration
        ref: backend/tests/integration/test_migrations.py#test_canonical_translation_identity_history_and_staging_are_database_authoritative
        status: pass
    human_judgment: false
  - id: D2
    description: Refresh-safe locators, immutable history, tombstones, and exact execution provenance preserve authority across repository movement.
    requirement: FMT-08
    verification:
      - kind: integration
        ref: backend/tests/integration/test_migrations.py#test_canonical_translation_identity_history_and_staging_are_database_authoritative
        status: pass
    human_judgment: false
  - id: D3
    description: Explicit language constraints accept the inclusive zero through 1,048,576 range and retain actor and optimistic-version metadata.
    requirement: CONS-01
    verification:
      - kind: integration
        ref: backend/tests/integration/test_migrations.py#test_translation_constraint_and_projection_contracts_are_database_authoritative
        status: pass
    human_judgment: false
  - id: D4
    description: Key-language uniqueness and independent explicit rows preserve base fallback and target override removal semantics.
    requirement: CONS-02
    verification:
      - kind: integration
        ref: backend/tests/integration/test_migrations.py#test_translation_constraint_and_projection_contracts_are_database_authoritative
        status: pass
    human_judgment: false
  - id: D5
    description: Current and tombstoned values store nonnegative grapheme counts and exact over-limit state.
    requirement: CONS-03
    verification:
      - kind: integration
        ref: backend/tests/integration/test_migrations.py#projection-boundaries
        status: pass
    human_judgment: false
  - id: D6
    description: Effective maximum, source, and violation columns reject every null, bound, source, and threshold inconsistency.
    requirement: CONS-04
    verification:
      - kind: integration
        ref: backend/tests/integration/test_migrations.py#projection-consistency
        status: pass
      - kind: unit
        ref: backend/tests/unit/localization/importing/test_contracts.py#test_canonical_models_export_closed_lowercase_vocabularies
        status: pass
    human_judgment: false
actuals:
  tokens: 30502
  tasks: 3
  commits: 11
duration: 32min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 10: Canonical Translation Persistence Summary

**A reversible PostgreSQL contract now preserves stable translation identity, immutable import history, mutable locators, tombstones, exact provenance, and versioned maximum-length authority for every canonical value.**

## Performance

- **Duration:** 32 minutes
- **Started:** 2026-09-05T09:43:18Z
- **Completed:** 2026-09-05T10:15:18Z
- **Tasks:** 3
- **Files changed:** 8 implementation and test files, plus GSD tracking artifacts

## Accomplishments

- Added Alembic revision `0016_canonical_translations` with stable localization scopes, canonical keys and values, immutable value revisions, mutable locators, execution staging, bounded parse issues, explicit constraints, and a symmetric downgrade.
- Enforced natural identity, exact composite ownership, selector byte/digest/version integrity, immutable provenance, running-execution-only staging, exact active-dataset authority, and tombstone consistency at the PostgreSQL boundary.
- Added versioned explicit key-language maximum-length rules and materialized grapheme/effective-source/violation columns whose null, boundary, and threshold combinations fail closed for active and tombstoned rows.
- Exposed the complete model graph with read-only semantic mapping navigation and exact lowercase `StrEnum` vocabularies shared by later persistence services.

## Task Commits

Each task was committed through a complete RED, GREEN, and REFACTOR sequence:

1. **Task 1 RED: failing stable canonical persistence contract** - `004a69a`
2. **Task 1 GREEN: canonical translation persistence** - `f6cac45`
3. **Task 1 REFACTOR: isolated canonical migration fixtures** - `a120a8c`
4. **Task 2 RED: failing constraint projection contract** - `e5b59ff`
5. **Task 2 GREEN: explicit constraints and violation projection** - `03ec720`
6. **Task 2 REFACTOR: reusable projection fixture** - `f8a67ac`
7. **Task 3 RED: failing canonical model graph contract** - `aeb8c73`
8. **Task 3 GREEN: canonical relationships, exports, and vocabularies** - `166f3d7`
9. **Task 3 REFACTOR: shared enum serialization assertions** - `c2cd37b`
10. **Verification style gate: repository formatting** - `4266141`

**Plan metadata:** committed in the final documentation commit.

## Files Created/Modified

- `backend/alembic/versions/0016_canonical_translations.py` - Complete reversible PostgreSQL schema, named constraints, indexes, and activation/provenance/immutability triggers.
- `backend/src/verboflex/models/translation.py` - Stable scope/key/value/history/locator/staging/issue models, relationships, projections, and persisted vocabularies.
- `backend/src/verboflex/models/translation_constraint.py` - Versioned explicit key-language maximum rule with actor provenance.
- `backend/src/verboflex/models/import_job.py` - Composite mapping ownership seam used by canonical scopes.
- `backend/src/verboflex/models/product_mapping.py` - Composite semantic-identity uniqueness and read-only owned-scope navigation.
- `backend/src/verboflex/models/__init__.py` - One public import boundary for all canonical entities and vocabularies.
- `backend/tests/integration/test_migrations.py` - Real-PostgreSQL upgrade/downgrade, identity, history, tombstone, provenance, activation, constraint, and projection contracts.
- `backend/tests/unit/localization/importing/test_contracts.py` - Exact exports, relationships, enum serialization, parser parity, and fail-closed vocabulary tests.
- `.planning/phases/04-localization-import-search-and-constraints/deferred-items.md` - Broad-suite environmental and stale historical-test findings.
- `.planning/WINDOWS.md` - Cross-phase visibility for the two open broad-suite findings.

## Decisions Made

- Made product plus semantic mapping identity the durable scope; the current revision and mapping UUIDs remain replaceable authority pointers.
- Excluded path, file position, and structural position from key/value identity so repository moves update only the locator.
- Stored canonical selector bytes, digest, and schema version together so equality is byte-exact and future selector formats can coexist safely.
- Kept revisions immutable and retained tombstoned current rows with last-known state and provenance instead of deleting review authority.
- Stored one explicit constraint per stable key and exact language. Absence expresses inheritance; no nullable pseudo-rule represents fallback.
- Materialized only the closed effective sources `none`, `base_default`, and `language_override`, with zero as a valid inclusive maximum.
- Made mapping-to-scope ORM navigation read-only and composite so application code cannot reparent a scope by treating a revision-owned UUID as identity.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved pre-0015 migration fixture compatibility**

- **Found during:** Task 1 full migration regression
- **Issue:** The shared mapping fixture initially wrote `base_language` while rehearsing revisions that predated that column.
- **Fix:** Made base-language seeding opt-in and enabled it only for canonical-schema tests.
- **Files modified:** `backend/tests/integration/test_migrations.py`
- **Verification:** Full migration suite passes upgrade, downgrade, and re-upgrade.
- **Commit:** `a120a8c`

**2. [Rule 1 - Bug] Closed PostgreSQL three-valued NULL projection escape**

- **Found during:** Task 2 GREEN verification
- **Issue:** A constrained source with a null effective maximum produced SQL `UNKNOWN`, which a check constraint accepts.
- **Fix:** Required `effective_max_chars IS NOT NULL` explicitly for base-default and language-override projections.
- **Files modified:** `backend/alembic/versions/0016_canonical_translations.py`, `backend/src/verboflex/models/translation.py`
- **Verification:** Every invalid null/source/violation combination now raises `IntegrityError`.
- **Commit:** `03ec720`

**3. [Rule 1 - Bug] Corrected SQLAlchemy relationship-name introspection**

- **Found during:** Task 3 GREEN verification
- **Issue:** The RED test treated the relationship collection iterator as relationship names rather than mapper objects.
- **Fix:** Asserted against the collection's explicit keys while retaining composite local/remote pair checks.
- **Files modified:** `backend/tests/unit/localization/importing/test_contracts.py`
- **Verification:** All 25 canonical unit contracts pass.
- **Commit:** `166f3d7`

**4. [Rule 3 - Blocking] Applied the repository formatting gate**

- **Found during:** Overall static verification
- **Issue:** Two long test expressions did not match Ruff's canonical format.
- **Fix:** Applied Ruff formatting only to the two changed contract files and reran all prescribed checks.
- **Files modified:** `backend/tests/integration/test_migrations.py`, `backend/tests/unit/localization/importing/test_contracts.py`
- **Verification:** Ruff check and format-check both pass.
- **Commit:** `4266141`

**Total deviations:** 4 auto-fixed (3 Rule 1, 1 Rule 3); all were correctness or verification fixes with no architecture expansion.

## TDD Gate Compliance

- Task 1 has ordered RED `004a69a`, GREEN `f6cac45`, and REFACTOR `a120a8c` commits.
- Task 2 has ordered RED `e5b59ff`, GREEN `03ec720`, and REFACTOR `f8a67ac` commits.
- Task 3 has ordered RED `aeb8c73`, GREEN `166f3d7`, and REFACTOR `c2cd37b` commits.

## Verification

- Prescribed migration and model regression: `43 passed` across `test_migrations.py` and `test_contracts.py`.
- Task 1 focused migration contract: passed, including head and reversible canonical schema cases.
- Task 2 focused constraint/review/projection contract: `2 passed, 39 deselected`.
- Task 3 canonical model contracts: `25 passed`.
- Ruff check: all changed migration, model, and contract files passed.
- Ruff format check: all 8 changed implementation/test files passed.
- Focused mypy: no issues in `import_job.py`, `product_mapping.py`, `translation.py`, or `translation_constraint.py`.
- Alembic: exactly one head, `0016_canonical_translations (head)`.
- Broad split backend regression: `972 passed`; four unrelated checks remain open as described below.

## Issues Encountered

- Default whole-tree pytest collection still collides on duplicate importing/preview test basenames. This was already recorded by Plan 04-08; the established split invocation was used for broad verification.
- Two worker smoke tests require a Redis/Celery worker at `127.0.0.1:56379`, which was not running in this execution environment.
- Two historical Phase 2 architecture guards still assert that translation model modules must not exist; those assertions are stale now that Phase 4 deliberately owns canonical persistence.
- The two new broad-suite findings are recorded in `deferred-items.md` and `.planning/WINDOWS.md`. They do not affect the prescribed migration/model gates.

## Authentication Gates

None.

## User Setup Required

None.

## Known Stubs

None.

## Threat Flags

None beyond the plan's declared parser/staging-to-canonical and owner-to-child trust boundaries. Both are covered by named composite foreign keys, database triggers, and forged-write tests.

## Next Phase Readiness

- Import reconciliation can now target stable canonical identities without binding review authority to repository paths or revision UUIDs.
- Search and detail projections can consume indexed current values, review states, tombstones, and constraint-violation filters.
- Constraint services can implement optimistic PUT/DELETE and transactional inheritance recomputation over explicit rules and materialized value projections.

## Self-Check: PASSED

- All implementation, test, tracking, and summary files exist.
- All ten implementation/TDD commits are present in repository history.
- All six requirement coverage entries validate as automatically covered.
