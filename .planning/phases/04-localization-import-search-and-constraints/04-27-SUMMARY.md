---
phase: 04-localization-import-search-and-constraints
plan: 27
subsystem: product-publication
tags: [sqlalchemy, base-language, candidate-cloning, publication, immutable-history]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [26]
    provides: language-bound preview confirmation equality, digest, and currentness
provides:
  - exact nullable base-language propagation through active-to-candidate graph cloning
  - direct and separate publication coverage with immutable prior history and idempotent retries
  - stale-language and legacy-null publication denial without inferred locale authority
affects: [publication, canonical-import, active-revalidation, product-administration]
actuals:
  tokens: 4793
  tasks: 1
  commits: 3
tech-stack:
  added: []
  patterns:
    - clone revision-owned mapping authority field-for-field while clearing candidate confirmation proof
    - preserve nullable locale authority exactly and let complete confirmation currentness fail closed
key-files:
  created: []
  modified:
    - backend/src/verboflex/services/products.py
    - backend/tests/integration/test_product_publication.py
key-decisions:
  - "Candidate graph cloning copies base_language exactly beside selected layout identity while continuing to clear job, digest, actor, and timestamp confirmation proof."
  - "Publication uses Plan 04-26's complete language-bound currentness predicate; a changed or null candidate language is blocked rather than defaulted."
  - "Published mappings remain immutable, and an equal publication retry returns the existing revision without changing mapping identity, version, or language."
patterns-established:
  - "Nullable authority propagation: clone the stored locale verbatim; never derive a conventional base locale during revision lifecycle operations."
requirements-completed: [FMT-07, FMT-08, CONS-04]
coverage:
  - id: D1
    description: Direct and separate mappings retain their exact selected base language through candidate cloning, publication, and repeated no-op publication.
    requirement: FMT-07
    verification:
      - kind: integration
        ref: backend/tests/integration/test_product_publication.py#test_base_language_clone_publication_and_noop_preserve_exact_direct_and_separate_values
        status: pass
    human_judgment: false
  - id: D2
    description: Changing candidate base language invalidates its prior confirmation and cannot mutate the previously published revision graph.
    requirement: FMT-08
    verification:
      - kind: integration
        ref: backend/tests/integration/test_product_publication.py#test_base_language_change_invalidates_confirmation_without_mutating_published_history
        status: pass
    human_judgment: false
  - id: D3
    description: Legacy-null mapping authority remains null through cloning and cannot publish without a fresh exact confirmation.
    requirement: CONS-04
    verification:
      - kind: integration
        ref: backend/tests/integration/test_product_publication.py#test_base_language_legacy_null_clone_stays_null_and_cannot_publish_without_confirmation
        status: pass
    human_judgment: false
duration: 6min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 27: Base-Language Candidate Publication Summary

**Exact nullable base-language authority now survives candidate graph cloning and atomic publication while stale changes and legacy nulls remain fail-closed.**

## Performance

- **Duration:** 6 minutes
- **Started:** 2026-09-05T11:04:52Z
- **Completed:** 2026-09-05T11:11:15Z
- **Tasks:** 1
- **Files changed:** 2 implementation and integration-test files, plus GSD tracking artifacts

## Accomplishments

- Copied each active mapping's exact nullable `base_language` into its fresh candidate mapping alongside the existing topology, semantic identity, layout selection, sides, and targets.
- Proved direct and separate language values survive clone, current confirmation, publication, and equal repeated publication while the previous published graph remains byte-equal.
- Proved a changed candidate language makes confirmation stale and a legacy null remains null and unpublishable without fresh exact confirmation.
- Brought the publication integration fixture onto Plan 04-26's language-bound digest/currentness contract so real publication tests exercise the complete predicate.

## Task Commits

Task 1 followed the ordered TDD cycle:

1. **RED: failing base-language lifecycle cases** - `87b065f`
2. **GREEN: exact nullable candidate-clone propagation** - `c8aa041`

No REFACTOR commit was needed: the minimal production change is already the explicit field-for-field graph-copy mapping required by the plan.

**Plan metadata:** committed in the final documentation commit.

## Files Created/Modified

- `backend/src/verboflex/services/products.py` - Copies exact nullable base-language authority while deep-cloning an active mapping graph.
- `backend/tests/integration/test_product_publication.py` - Covers direct/separate cloning, current and stale publication, immutable history, idempotent retry, and legacy-null denial.

## Decisions Made

- Kept `base_language` separate from disposable confirmation proof: candidate cloning preserves the locale selection but still clears confirmed job, digest, actor, and timestamp fields.
- Reused Plan 04-26's complete currentness predicate rather than adding publication-specific locale inference or duplicate validation.
- Treated exact null propagation as required behavior; publication remains blocked until a later fresh confirmation establishes canonical language authority.

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

- RED `87b065f` added direct/separate clone/publication, stale-language, immutable-history, repeated no-op, and legacy-null cases. The prescribed focused run failed in exactly the two clone-dependent cases because both non-null candidate languages were `None`.
- GREEN `c8aa041` copied the exact nullable field in the production graph clone. The prescribed focused suite then passed all 41 selected tests.
- No refactor was necessary; the one-field explicit clone mapping is the simplest complete implementation.

## Verification

- Prescribed focused publication/preview gate: `41 passed, 72 deselected`.
- Complete publication and preview integration regression: `113 passed`.
- Adjacent administrator-product clone/candidate regression: `4 passed, 27 deselected`.
- Ruff format check: both changed Python files already formatted.
- Ruff check: both changed Python files passed.
- Focused Mypy: no issues in `services/products.py`.
- Git diff whitespace check: passed.

## Issues Encountered

- The inherited publication confirmation fixture still produced Plan 04-25 raw digests and sentinel `default` language candidates, causing six baseline failures under Plan 04-26 currentness. The RED test commit updated that fixture to exact canonical languages and language-bound confirmation digests before proving the new clone failure.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None beyond the plan's declared candidate-to-published graph boundary. Exact copy assertions, complete currentness, immutable-history snapshots, and fail-closed stale/null cases cover that boundary.

## Next Phase Readiness

- Canonical import and publication consumers can rely on exact selected base-language authority after active-to-candidate revision cloning.
- No migration, API, generated-client, or external-service follow-up is required for this plan.

## Self-Check: PASSED

- Both changed implementation/test files and this summary exist on disk.
- RED `87b065f` and GREEN `c8aa041` are present in repository history in the required order.
- Coverage metadata classifies all three deliverables as fully automated and passing.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-05*
