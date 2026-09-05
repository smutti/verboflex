---
phase: 04-localization-import-search-and-constraints
plan: 21
subsystem: localization-constraints
tags: [constraints, graphemes, sqlalchemy, optimistic-concurrency, imports]

requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [10, 11, 14]
    provides: canonical translation storage, atomic import activation, and versioned UAX 29 grapheme counting
provides:
  - dynamic base-default and target-override constraint projection
  - transaction-local recomputation for import activation and translation edits
  - exact idempotent PUT and DELETE services with optimistic row-lock concurrency
  - authoritative over-limit approval and submission eligibility projection
affects: [translation-editing, review-approval, pull-request-submission, translation-detail]

actuals:
  tokens: 15820
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - one transaction-local recomputation service for every constraint-affecting boundary
    - stable authority-row locks plus exact expected-version equality for mutations
    - explicit rules only, with inherited and absent states derived dynamically

key-files:
  created:
    - backend/src/verboflex/services/translation_constraints.py
    - backend/tests/integration/test_translation_constraints.py
  modified:
    - backend/src/verboflex/services/translation_imports.py

key-decisions:
  - "Constraint precedence is exact-language override, dynamic mapping base-language default, then none; inherited state is never persisted as a nullable rule."
  - "All counts and eligibility projections are recomputed through grapheme_count(display_text) inside the caller transaction, including import activation and the later-edit seam."
  - "PUT and DELETE lock stable scope, mapping, key, and rule authority in deterministic order and compare exact server-owned versions before mutation."
  - "Over-limit or tombstoned values remain stored and readable while approval_eligible and submission_eligible are false."

patterns-established:
  - "Constraint mutation boundary: validate exact integers, lock authority, compare version, mutate explicit rule, recompute, flush, and leave commit ownership to the caller."
  - "Dynamic inheritance: base-language rule changes fan out across every value sharing the raw key while exact target overrides remain independent."

requirements-completed: [SRCH-05, CONS-01, CONS-02, CONS-03, CONS-04]

coverage:
  - id: D1
    description: "Base defaults, target overrides, removal fallback, and exact labels are projected dynamically without materializing inherited rules."
    requirement: CONS-01
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_translation_constraints.py — inheritance, override, removal, and no-authority cases"
        status: pass
    human_judgment: false
  - id: D2
    description: "PUT and DELETE enforce inclusive bounds, exact integer/version semantics, idempotency, and one-winner row-lock concurrency."
    requirement: CONS-02
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_translation_constraints.py — mutation, stale-writer, and two-session cases"
        status: pass
    human_judgment: false
  - id: D3
    description: "Import, edit, and rule mutations use the versioned grapheme authority and atomically persist count, maximum, source, and violation."
    requirement: CONS-03
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_translation_constraints.py and test_translation_import_activation.py"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/test_grapheme_count.py — 24 passed"
        status: pass
    human_judgment: false
  - id: D4
    description: "Zero, one, many, threshold, tombstone, empty-set, and missing-base recomputation states are exact and transaction-local."
    requirement: CONS-04
    verification:
      - kind: integration
        ref: "Focused constraints plus import activation regression — 53 passed"
        status: pass
    human_judgment: false
  - id: D5
    description: "Returned value projections expose authoritative effective source, label, violation, and approval/submission eligibility for grouped read consumers."
    requirement: SRCH-05
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_translation_constraints.py — effective projection and eligibility assertions"
        status: pass
    human_judgment: false

duration: 17min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 21: Transaction-Safe Constraint Service Summary

**Dynamic inherited limits, exact UAX 29 recomputation, and versioned row-locked mutations now produce one authoritative constraint and eligibility projection inside every caller transaction.**

## Performance

- **Duration:** 17min
- **Started:** 2026-09-05T14:10:20Z
- **Completed:** 2026-09-05T14:27:00Z
- **Tasks:** 2
- **Files created or modified:** 3

## Accomplishments

- Added dynamic base-default, exact target-override, inherited, and no-limit projection across all values sharing a raw key, including mappings whose translations live in separate repositories.
- Centralized import activation, future translation edits, PUT, and DELETE on one grapheme-based recomputation path that persists counts, effective authority, and violations without committing outside the caller boundary.
- Added strict inclusive `0..1,048,576` mutation validation, exact expected-version comparison, identical-PUT idempotency, bounded absent-DELETE behavior, and deterministic row locks for concurrent writers.
- Preserved over-limit and tombstoned translation rows while projecting authoritative cannot-approve/cannot-submit eligibility.

## TDD Gate Compliance

- **Task 1 RED — `96b718a`:** the focused recomputation contracts failed at collection because the new constraint service did not exist.
- **Task 1 GREEN — `9d39f32`:** dynamic projection, transaction-local recomputation, edit seam, and import activation integration made the focused inheritance/activation slice pass.
- **Task 2 RED — `9cd9889`:** exact mutation, idempotency, conflict, and concurrent-writer contracts failed because the mutation API and typed outcomes did not exist.
- **Task 2 GREEN — `64d7f04`:** strict mutation validation, explicit-rule persistence, optimistic versioning, and recomputation made the complete mutation slice pass.
- **REFACTOR — `400af7f`:** consolidated stable rule locking and strengthened immutability evidence; the combined constraint and activation suite remained green.

Git history preserves both mandatory RED commits before their corresponding GREEN commits.

## Task Commits

1. **RED: Add failing constraint recomputation contracts** - `96b718a` (test)
2. **GREEN: Centralize authoritative constraint recomputation** - `9d39f32` (feat)
3. **RED: Add failing optimistic constraint mutation contracts** - `9cd9889` (test)
4. **GREEN: Add optimistic constraint mutation services** - `64d7f04` (feat)
5. **REFACTOR: Consolidate explicit rule locking** - `400af7f` (refactor)

## Files Created/Modified

- `backend/src/verboflex/services/translation_constraints.py` - Effective projection, recomputation/edit seam, strict mutation services, typed outcomes, and deterministic authority locking.
- `backend/src/verboflex/services/translation_imports.py` - Import activation now delegates to the shared authoritative recomputation service.
- `backend/tests/integration/test_translation_constraints.py` - PostgreSQL-backed inheritance, Unicode, threshold, transaction, idempotency, immutability, and concurrency evidence.

## Decisions Made

- Treat zero as a valid explicit limit and reject booleans, floats, strings, nulls, negatives, and values above `1,048,576`; Python's implicit integer coercions never enter stored authority.
- Locate defaults dynamically from the mapping's configured base language and all same-raw-key rules, so split translation-source repositories inherit correctly without duplicating rules.
- Return presentation labels separately from the persisted three-state source: base values are `default`, target exact rules are `override`, inherited targets are `inherited`, and unconstrained values are `none`.
- Flush after recomputation but never commit in the service, keeping rule changes and every affected projection atomic with the caller's import or edit transaction.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Seeded missing-base evidence without violating active-revision immutability**
- **Found during:** Task 1 GREEN integration verification
- **Issue:** The initial missing-base fixture tried to null the base language on a published active mapping, which correctly triggered the database's immutable revision guard before the intended service assertion.
- **Fix:** Seeded a dedicated mapping whose base authority is absent from creation, preserving production immutability while exercising the exact missing-base rejection path.
- **Files modified:** `backend/tests/integration/test_translation_constraints.py`
- **Verification:** The complete constraint and activation suite passes, including the missing-base case.
- **Committed in:** `9d39f32`

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking test-fixture issue).
**Impact on plan:** No production scope or behavior changed; the adjustment made the intended negative-path test valid under existing database invariants.

## Issues Encountered

- Collecting `tests/unit/localization/importing/` and `tests/unit/localization/preview/` in one pytest process reproduces the already-recorded duplicate module-basename collision. Both complete directories passed independently (171 importing and 181 preview tests), so no Plan 04-21 verification was skipped.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. The `structure=[]` matches in integration fixtures are intentional complete parser structures, not UI or production placeholders.

## Verification

- `uv run --project backend pytest backend/tests/integration/test_translation_constraints.py backend/tests/integration/test_translation_import_activation.py -q` - 53 passed.
- Focused Task 2 PUT/DELETE/bounds/precision/idempotency/concurrency selection - 33 passed, 1 deselected.
- Constraint, activation, import-job, and background-boundary regression set - 129 passed.
- Importing parser unit suite - 171 passed; preview parser unit suite - 181 passed.
- Versioned grapheme unit suite - 24 passed; migration integration suite - 21 passed.
- Focused Ruff lint and format checks over all three changed files - passed.
- Strict mypy over both changed production modules - passed with no issues.
- Alembic reports one head: `0017_translation_search_indexes`.
- FastAPI OpenAPI creation and Celery import-task registration smoke - passed.
- `uv lock --check --project backend` and `uv run --project backend pip check` - passed.
- Stub scan found no production placeholders; authority scan confirmed shared `grapheme_count`, row locks, no service commit, and no `len(display_text)` implementation.

## Next Phase Readiness

- Later API and workflow plans can call the exact mutation services and consume the returned eligibility projection without duplicating constraint logic.
- `recompute_after_translation_edit` is ready for the Phase 5 translation mutation boundary.
- No constraint-service, import-activation, concurrency, Unicode, typing, migration, or dependency blocker remains.

## Self-Check: PASSED

- All three declared implementation/test files and this summary exist.
- RED, GREEN, and REFACTOR commits `96b718a`, `9d39f32`, `9cd9889`, `64d7f04`, and `400af7f` resolve in repository history.
- The implementation commit range contains no tracked-file deletions.
- Required frontmatter, requirement IDs, verification evidence, deviation ledger entry, and stub disclosure are present.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-05*
