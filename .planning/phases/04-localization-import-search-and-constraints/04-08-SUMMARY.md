---
phase: 04-localization-import-search-and-constraints
plan: 08
subsystem: localization-persistence
tags: [postgresql, sqlalchemy, alembic, locale, constraints]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [07]
    provides: verified parser evidence and the normalized base-language requirement
provides:
  - nullable legacy-safe base-language authority on each revision-owned mapping
  - reversible Alembic 0015 migration with named length and normalization checks
  - migration and ORM regression coverage for canonical locale persistence
affects: [04-10, 04-26, 04-27, canonical-imports, maximum-length-constraints]
tech-stack:
  added: []
  patterns:
    - nullable legacy-safe authority with no guessed default
    - bounded canonical locale values protected by matching ORM and database checks
key-files:
  created:
    - backend/alembic/versions/0015_mapping_base_language.py
    - .planning/phases/04-localization-import-search-and-constraints/deferred-items.md
  modified:
    - backend/src/verboflex/models/product_mapping.py
    - backend/tests/integration/test_migrations.py
    - backend/tests/unit/services/test_mappings.py
key-decisions:
  - "Persist base_language as nullable VARCHAR(64) with separate named length and normalized-locale checks; legacy rows remain null with no guessed default."
  - "Add no base-language index until a proven query consumer exists."
patterns-established:
  - "Locale authority belongs to the revision-owned mapping and remains nullable for legacy rows."
  - "Schema length and normalization invariants use explicit names mirrored in SQLAlchemy metadata and Alembic."
requirements-completed: [FMT-07, FMT-08, CONS-04]
coverage:
  - id: D1
    description: Each revision-owned mapping persists a nullable base-language authority without guessing a value for legacy rows.
    requirement: FMT-07
    verification:
      - kind: integration
        ref: backend/tests/integration/test_migrations.py#base-language-authority
        status: pass
    human_judgment: false
  - id: D2
    description: Upgrade, downgrade, and re-upgrade preserve legacy mapping rows while adding or removing only the base-language contract.
    requirement: FMT-08
    verification:
      - kind: integration
        ref: backend/tests/integration/test_migrations.py#base-language-round-trip
        status: pass
    human_judgment: false
  - id: D3
    description: PostgreSQL and SQLAlchemy expose the same named bounded canonical-locale constraints and reject malformed or oversized values.
    requirement: CONS-04
    verification:
      - kind: integration
        ref: backend/tests/integration/test_migrations.py#base-language-constraints
        status: pass
      - kind: unit
        ref: backend/tests/unit/services/test_mappings.py#mapping-schema-inventory
        status: pass
    human_judgment: false
actuals:
  tokens: 3073
  tasks: 1
  commits: 5
duration: 15min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 08: Mapping Base-Language Persistence Summary

**A nullable, normalized `base_language` authority now lives on each revision-owned mapping, protected by matching SQLAlchemy and PostgreSQL constraints and a reversible migration contract.**

## Performance

- **Duration:** 15 minutes
- **Started:** 2026-09-05T09:14:36Z
- **Completed:** 2026-09-05T09:29:04Z
- **Tasks:** 1
- **Files changed:** 5 implementation, test, and tracking files

## Accomplishments

- Added Alembic revision `0015_mapping_base_language` with a nullable `VARCHAR(64)` column and explicitly named length and canonical-locale checks.
- Mirrored the migration contract in `ProductRepositoryMapping`, leaving legacy mappings null instead of guessing a base language.
- Proved accepted canonical forms, malformed and oversized rejection, legacy upgrade behavior, downgrade preservation, re-upgrade behavior, exact constraint names, and the deliberate absence of an unproven index.
- Kept the complete backend test corpus green by exercising the importing and preview trees separately and running worker smoke tests against isolated temporary Redis/Celery infrastructure.

## Task Commits

Each task was committed atomically through the required TDD sequence:

1. **RED: add failing mapping base-language migration contract** - `ccf0820`
2. **RED correction: isolate checks on a candidate mapping** - `9557298`
3. **GREEN: persist normalized mapping base language** - `f7eec38`
4. **REFACTOR: align base-language column metadata** - `50a2175`
5. **Regression: align exact mapping schema inventory** - `329e777`

## Files Created/Modified

- `backend/alembic/versions/0015_mapping_base_language.py` - Reversible column and named check-constraint migration.
- `backend/src/verboflex/models/product_mapping.py` - Nullable bounded field plus matching ORM table constraints.
- `backend/tests/integration/test_migrations.py` - Upgrade, validation, downgrade, and re-upgrade contract.
- `backend/tests/unit/services/test_mappings.py` - Exact mapping schema regression inventory.
- `.planning/phases/04-localization-import-search-and-constraints/deferred-items.md` - Pre-existing collection and typing issues discovered by broad verification.

## Decisions Made

- Stored base language as nullable `VARCHAR(64)` with independent named length and normalized-locale constraints so each failure mode remains inspectable and legacy rows remain valid.
- Accepted canonical language, optional script, and optional region forms while rejecting alternate casing, underscores, whitespace, extra subtags, and overlong input.
- Added no index because the plan established no base-language lookup consumer.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the RED test fixture to avoid the immutable published-mapping guard**

- **Found during:** Task 1 GREEN verification
- **Issue:** The first fixture attempted to mutate a published active mapping, so the existing revision-graph trigger correctly rejected the setup before the new base-language contract could be exercised.
- **Fix:** Created a candidate legacy mapping and ran all new constraint checks against that mutable revision-owned row.
- **Files modified:** `backend/tests/integration/test_migrations.py`
- **Commit:** `9557298`

**2. [Rule 1 - Bug] Updated the adjacent exact-schema regression**

- **Found during:** Task 1 full regression verification
- **Issue:** The mapping schema inventory still expected the pre-migration column and constraint set.
- **Fix:** Added `base_language` and both named checks to the exact unit-test inventory.
- **Files modified:** `backend/tests/unit/services/test_mappings.py`
- **Commit:** `329e777`

**Total deviations:** 2 auto-fixed bugs (2 Rule 1); no scope expansion or architectural decisions.

## Verification

- Plan focus: `1 passed, 14 deselected` for `pytest backend/tests/integration/test_migrations.py -q -k 'base_language or head'`.
- Migration integration suite: `15 passed`.
- Mapping service suite: `16 passed`.
- Backend corpus: `945 passed` outside preview plus `181 passed` in preview; worker smoke tests separately passed `4/4` with isolated Redis/Celery infrastructure.
- Ruff check and format: all `backend/src` and `backend/tests` passed.
- Focused model mypy: passed with no issues.
- Alembic: `0015_mapping_base_language (head)`.

## Issues Encountered

- Default backend pytest collection collides on duplicate importing/preview test basenames. The complete corpus was verified in two non-overlapping runs and the packaging issue was recorded in `deferred-items.md` and `.planning/WINDOWS.md`.
- Full backend mypy reports 12 pre-existing errors in parser modules outside this plan. The changed model passes focused mypy; the parser debt was recorded in `deferred-items.md` and `.planning/WINDOWS.md`.

## Authentication Gates

None.

## User Setup Required

None.

## Known Stubs

None.

## Next Phase Readiness

- Mapping revisions now carry the durable language authority required by canonical import and per-language maximum-length enforcement work.
- Plan 04-09 can proceed; Plans 04-10, 04-26, and 04-27 can consume the persisted `base_language` field without guessing legacy values.

## Self-Check: PASSED

- All implementation, test, tracking, and summary files exist.
- All five task commits are present in repository history.
- All three requirement coverage entries validate as automatically covered.
