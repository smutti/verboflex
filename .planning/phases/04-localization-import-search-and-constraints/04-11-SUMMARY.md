---
phase: 04-localization-import-search-and-constraints
plan: 11
subsystem: localization-import
tags: [postgresql, sqlalchemy, celery, canonical-localization, reconciliation, provenance]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [10, 27]
    provides: canonical translation schema, immutable staging/history guards, and exact published base-language authority
  - phase: 03-bitbucket-import-integration
    plans: [7, 9]
    provides: UUID-only workers, immutable source references, import finalization, and rewrite confirmation authority
provides:
  - execution-owned canonical parse manifests bound to exact ordered source references and a deterministic digest
  - stable semantic reconciliation for moves, renames, tombstones, source changes, external changes, and exact submission correlation
  - atomic canonical dataset and source-baseline activation for normal and confirmed rewrite paths
  - authoritative grapheme and effective maximum-character projection recomputation during import activation
affects: [translation-search, translation-detail, review-workflow, constraints, write-back, pull-requests]
actuals:
  tokens: 32444
  tasks: 3
  commits: 9
tech-stack:
  added: []
  patterns:
    - parse provider bytes outside final locks, then persist immutable execution-owned staging before activation
    - reconcile by scope/repository/branch/raw-key/language/selector identity while keeping paths and positions mutable
    - advance canonical scope and import baseline in one transaction after exact authority and manifest revalidation
key-files:
  created:
    - backend/src/verboflex/services/translation_imports.py
  modified:
    - backend/src/verboflex/services/import_jobs.py
    - backend/src/verboflex/worker/import_tasks.py
    - backend/tests/integration/test_translation_import_activation.py
    - backend/tests/architecture/test_background_boundaries.py
key-decisions:
  - "File path and source position remain mutable locator data; refresh identity never uses fuzzy text, path proximity, or transient mapping UUIDs."
  - "Approved survives imported target change only when an immutable prior revision has the same durable correlation reference and exact expected content; source changes always reset targets to Draft."
  - "Canonical source references are inserted with staging while the execution is running, then the finalizer revalidates their exact ordered equality instead of inserting duplicate provenance rows."
  - "Legacy published mappings without canonical base-language authority retain the Phase 3 finalization and rewrite-confirmation path."
patterns-established:
  - "Inactive-first import: source references, canonical values, or bounded parser issues are immutable before any searchable pointer changes."
  - "Append-before-update history: every content, review-reset, explicit deletion, or absence transition receives immutable execution/commit/correlation provenance."
  - "Semantic-scope swap: revision, mapping, import, execution, and dataset version pointers change together only after job success/baseline authority is durable."
requirements-completed: [FMT-07, FMT-08, CONS-04]
coverage:
  - id: D1
    description: Complete direct and separate parser results stage under one exact execution while parser issues and stale workers cannot expose partial rows.
    requirement: FMT-07
    verification:
      - kind: integration
        ref: backend/tests/integration/test_translation_import_activation.py#stage_and_activation_cases
        status: pass
      - kind: other
        ref: backend/tests/architecture/test_background_boundaries.py#UUID-only_worker_boundary
        status: pass
    human_judgment: false
  - id: D2
    description: Refresh reconciliation preserves semantic identity across moves, exposes renames as old tombstone plus unrelated new Draft, and records external/source changes without guessing origin.
    requirement: FMT-08
    verification:
      - kind: integration
        ref: backend/tests/integration/test_translation_import_activation.py#refresh_truth_table
        status: pass
    human_judgment: false
  - id: D3
    description: Every activated normal or confirmed-rewrite dataset recomputes grapheme counts and effective maximum-character projections in the same transaction as its source baseline.
    requirement: CONS-04
    verification:
      - kind: integration
        ref: backend/tests/integration/test_translation_import_activation.py#atomic_activation_and_rollback_cases
        status: pass
    human_judgment: false
duration: 38min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 11: Atomic Canonical Import Activation Summary

**Execution-scoped canonical manifests now reconcile stable translation identities and atomically expose the same exact execution as both searchable dataset and Bitbucket source baseline.**

## Performance

- **Duration:** 38 minutes
- **Started:** 2026-09-05T11:17:46Z
- **Completed:** 2026-09-05T11:55:48Z
- **Tasks:** 3
- **Files changed:** 5 implementation/test files, plus GSD tracking artifacts

## Accomplishments

- Extended the UUID-only import worker to parse confirmed direct or complete Keys-plus-Translations layouts outside final locks and persist exact inactive values or bounded safe issues under immutable execution/source provenance.
- Implemented stable refresh reconciliation for moves, raw-key renames, complete absence, explicit Qt deleted rows, external target changes, source fan-out, append-only revisions, exact submission correlation, and authoritative constraint projections.
- Unified normal import and confirmed rewrite promotion through one atomic activation seam so scope dataset and import baseline pointers either advance to the same execution or remain byte-stable after rollback/stale completion.
- Preserved stable scope and translation UUIDs across published mapping revision clones while keeping legacy Phase 3 mappings operational.

## Task Commits

Each TDD slice was committed atomically:

1. **Task 1 RED: failing canonical staging contracts** - `4816001`
2. **Task 1 GREEN: canonical parse manifest staging** - `d0e0f88`
3. **Task 2 RED: failing refresh reconciliation matrix** - `f797025`
4. **Task 2 GREEN: stable identity/history/tombstone reconciliation** - `1e5e656`
5. **Task 3 RED: failing atomic activation and rollback contracts** - `fd8398f`
6. **Task 3 GREEN: normal and rewrite dataset activation** - `35d45f9`
7. **Task 3 correctness fix: semantic scope revision swap** - `7e3c708`
8. **Task 3 correctness fix: complete empty manifests** - `4caf01d`

**Plan metadata:** committed in the final documentation commit.

## Files Created/Modified

- `backend/src/verboflex/services/translation_imports.py` - Owns immutable staging manifests, digest revalidation, stable reconciliation, history/provenance, constraint projections, and atomic scope activation.
- `backend/src/verboflex/services/import_jobs.py` - Integrates canonical parsing and activation into existing import finalization and confirmed rewrite authority while retaining legacy behavior.
- `backend/src/verboflex/worker/import_tasks.py` - Carries the canonical manifest digest inside process memory while keeping the Celery message UUID-only.
- `backend/tests/integration/test_translation_import_activation.py` - Covers staging, the D-08 through D-13 refresh matrix, direct/separate activation, revision clones, parser failure, rewrite confirmation, concurrency, and rollback.
- `backend/tests/architecture/test_background_boundaries.py` - Guards worker payload and canonical parser/staging boundaries statically.

## Decisions Made

- Stable translation identity excludes file path and source position. Moves are locator updates; renames are intentionally two independent events: old tombstone and new Draft.
- Same-value refresh preserves state only when current content still matches immutable imported history. An untracked current value that happens to equal provider content requires exact correlation evidence before Approved can survive.
- Exact correlation means both durable reference equality and exact immutable revision content equality; reference reuse or commit-prefix similarity cannot authorize approval preservation.
- Source-text change takes precedence over target correlation and resets every associated target selector/language to Draft while retaining its translated text and context.
- An issue-free empty file is a complete empty manifest and can activate an empty dataset; zero source references or any bounded parse issue cannot activate.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking test fixture] Flushed publication before activating the test revision**
- **Found during:** Task 1 focused PostgreSQL verification
- **Issue:** The new seed fixture attempted publication and active-revision assignment in one flush, violating the database's immutable active-revision guard ordering.
- **Fix:** Flushed the published revision first, then assigned the active revision exactly like established integration fixtures.
- **Files modified:** `backend/tests/integration/test_translation_import_activation.py`
- **Verification:** Task 1 focused suite passed with 9 selected cases.
- **Committed in:** `d0e0f88`

**2. [Rule 1 - Cross-revision scope bug] Prevented staging from prematurely replacing active mapping authority**
- **Found during:** Final Task 3 code review
- **Issue:** Reusing a stable semantic scope for a cloned mapping revision could update current mapping fields before activation, conflicting with the still-active prior import and breaking atomic visibility.
- **Fix:** Staging now reuses the scope without changing active authority; activation swaps revision, mapping, import, execution, and dataset version together after final revalidation.
- **Files modified:** `backend/src/verboflex/services/translation_imports.py`, `backend/src/verboflex/services/import_jobs.py`, `backend/tests/integration/test_translation_import_activation.py`
- **Verification:** Added a published revision-clone integration case; the full 92-test import/architecture set passed.
- **Committed in:** `7e3c708`

**3. [Rule 1 - Empty dataset bug] Distinguished complete empty content from missing source input**
- **Found during:** Final Task 3 code review
- **Issue:** An issue-free file containing no canonical values had no scope to activate, even though only zero source files—not a complete empty file—must fail.
- **Fix:** Complete empty manifests now create inactive scope authority and atomically expose an empty current dataset; parser-issue manifests still create no active rows.
- **Files modified:** `backend/src/verboflex/services/translation_imports.py`, `backend/tests/integration/test_translation_import_activation.py`
- **Verification:** Empty-manifest and parser-failure activation cases both pass.
- **Committed in:** `4caf01d`

---

**Total deviations:** 3 auto-fixed (2 Rule 1 correctness fixes, 1 Rule 3 blocking fixture fix)
**Impact on plan:** All fixes enforce the stated atomicity and completeness contracts without adding product scope.

## TDD Gate Compliance

- Task 1 has ordered RED `4816001` and GREEN `d0e0f88` commits.
- Task 2 has ordered RED `f797025` and GREEN `1e5e656` commits.
- Task 3 has ordered RED `fd8398f` and GREEN `35d45f9` commits, followed by focused correctness commits `7e3c708` and `4caf01d`.
- No standalone REFACTOR commit was needed; cleanup and compatibility adjustments were necessary parts of the GREEN/correctness changes and all gates remained green.

## Verification

- Task 1 prescribed staging/worker/parser-failure gate: `9 passed, 12 deselected`.
- Task 2 prescribed refresh truth-table gate: `6 passed, 10 deselected`.
- Task 3 prescribed activation/rewrite/superseded/rollback gate: `30 passed, 56 deselected`.
- Canonical importing unit regression: `171 passed`.
- Preview detector unit regression: `181 passed`.
- Import, preview, discovery, repository, migration, and background-boundary integration regression: `223 passed`.
- Combined import/activation/background regression during GREEN: `92 passed`.
- Ruff check and format check: all five changed implementation/test files passed.
- Focused mypy: no issues in `translation_imports.py`, `import_jobs.py`, or `import_tasks.py`.
- Alembic: exactly one head, `0016_canonical_translations (head)`; no migration was added because Plan 04-10 already supplied the required schema and Plan 04-13 owns the next migration number.
- Backend deployment smoke: FastAPI OpenAPI construction and the `verboflex.import.run` Celery task import/name assertion passed.
- Git diff whitespace, stub-pattern, and deletion scans passed.

## Issues Encountered

- The first Alembic smoke invocation ran from the repository root and could not find `script_location`; rerunning from `backend/` succeeded and reported the single expected head.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None beyond the plan's declared repository/parser-to-staging and staging-to-active trust boundaries. Exact immutable provenance, bounded issue storage, final lock revalidation, stale-worker rejection, and transaction rollback cover those surfaces.

## Next Phase Readiness

- Search/detail plans can rely on one active semantic scope whose dataset execution always equals the import's active baseline execution.
- Review and write-back plans can use immutable value revisions plus `correlation_reference` to prove exact submission origin without guessing from text or commit prefixes.
- Constraint mutation plans can reuse the same grapheme/effective-limit projection semantics invoked by import activation.
- No blockers or user setup remain for downstream Phase 4 work.

## Self-Check: PASSED

All five implementation/test artifacts and all eight task/correctness commits were verified on disk before state advancement.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-05*
