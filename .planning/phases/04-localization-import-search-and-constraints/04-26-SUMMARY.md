---
phase: 04-localization-import-search-and-constraints
plan: 26
subsystem: preview-confirmation
tags: [fastapi, pydantic, sqlalchemy, base-language, currentness, openapi]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [08]
    provides: nullable normalized base-language storage on revision-owned mappings
provides:
  - exact detected-language membership and sole-language defaulting under preview confirmation locks
  - language-bound candidate and active-revalidation digests, equality, and currentness
  - closed administrator request and response contracts with bounded base-language failures
affects: [04-09, 04-27, publication, imports, admin-ui, active-revalidation]
tech-stack:
  added: []
  patterns:
    - mapping base_language remains the sole durable language authority
    - confirmation digests bind server-validated language selection to complete preview identity
    - invalid confirmation paths finish before authority mutation
key-files:
  created:
    - backend/tests/api/test_admin_previews.py
  modified:
    - backend/src/verboflex/services/preview_jobs.py
    - backend/src/verboflex/schemas/previews.py
    - backend/src/verboflex/api/v1/routes/admin_previews.py
    - backend/tests/integration/test_preview_jobs.py
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json
key-decisions:
  - "A required-but-nullable API field lets the server select one sole canonical detected language while forcing an explicit exact member for multi-language candidates."
  - "The raw result digest remains the compare token, while persisted and returned confirmation digests additionally bind the selected base language."
  - "Active revalidation may only confirm the mapping's already-persisted base language and stores no duplicate language authority in its sidecar."
patterns-established:
  - "Confirmation membership: resolve one exact candidate, reject noncanonical or foreign languages, then mutate authority only after all checks pass."
  - "Currentness: recompute the language-bound digest and verify selected-layout membership against the mapping's base language."
requirements-completed: [FMT-07, FMT-08, CONS-04]
coverage:
  - id: D1
    description: One detected language defaults deterministically while multiple languages require an explicit exact candidate member.
    requirement: FMT-07
    verification:
      - kind: integration
        ref: backend/tests/integration/test_preview_jobs.py#base-language candidate confirmation tests
        status: pass
      - kind: unit
        ref: backend/tests/api/test_admin_previews.py#closed base-language schema tests
        status: pass
    human_judgment: false
  - id: D2
    description: Base language participates in confirmation equality, digest, selected-layout checks, candidate currentness, and active-revalidation authority.
    requirement: FMT-08
    verification:
      - kind: integration
        ref: backend/tests/integration/test_preview_jobs.py#base-language currentness and active-revalidation tests
        status: pass
    human_judgment: false
  - id: D3
    description: Missing, foreign, changed, stale, sentinel, and duplicate selections return bounded outcomes without mutating candidate or published authority.
    requirement: CONS-04
    verification:
      - kind: integration
        ref: backend/tests/integration/test_preview_jobs.py#base-language failure-atomicity tests
        status: pass
      - kind: unit
        ref: backend/tests/api/test_admin_previews.py#base_language_required route mapping
        status: pass
    human_judgment: false
actuals:
  tokens: 66215
  tasks: 1
  commits: 4
duration: 19min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 26: Base-Language Preview Confirmation Summary

**Preview confirmation now proves one canonical detected base language and binds it to persisted equality, language-aware digests, currentness, and immutable active-revalidation evidence.**

## Performance

- **Duration:** 19 minutes
- **Started:** 2026-09-05T10:18:01Z
- **Completed:** 2026-09-05T10:37:20Z
- **Tasks:** 1
- **Files changed:** 7 implementation, contract, generated, and test files, plus GSD tracking artifacts

## Accomplishments

- Added deterministic sole-language selection and exact canonical membership validation for multi-language preview candidates under the existing mapping and job locks.
- Bound base language into persisted confirmation digests, idempotent equality, complete-confirmation checks, selected-layout membership, candidate currentness, and active-revalidation currentness.
- Preserved the mapping field as the only durable language authority: active-revalidation sidecars bind its value cryptographically but do not duplicate it.
- Exposed required, nullable, bounded, extra-forbidden administrator request fields and non-null response fields, including the bounded `base_language_required` conflict.
- Proved failure atomicity for missing, foreign, changed, stale, unavailable, sentinel, and duplicate submissions across candidate and published authority.

## Task Commits

Task 1 followed the ordered TDD cycle:

1. **RED: failing base-language confirmation contract** - `f98d6b4`
2. **GREEN: language-bound confirmation, currentness, and API** - `3eaceb4`
3. **REFACTOR: shared language-bound currentness digest comparison** - `05ae0d0`

**Plan metadata:** committed in the final documentation commit.

## Files Created/Modified

- `backend/src/verboflex/services/preview_jobs.py` - Exact language selection, language-bound digest/equality/currentness, failure-atomic candidate assignment, and active-revalidation validation.
- `backend/src/verboflex/schemas/previews.py` - Closed required-but-nullable request and non-null response fields bounded to 64 characters.
- `backend/src/verboflex/api/v1/routes/admin_previews.py` - Administrator-only language projection and bounded `base_language_required` conflict mapping.
- `backend/tests/integration/test_preview_jobs.py` - Candidate and active-revalidation selection, equality, digest, invalidation, stale/foreign/duplicate rejection, and zero-mutation regressions.
- `backend/tests/api/test_admin_previews.py` - Pure schema and route-error contract tests.
- `backend/tests/api/test_openapi_contract.py` - Checked OpenAPI shape, requiredness, nullability, bounds, and response coverage.
- `frontend/openapi.json` - Regenerated canonical frontend API input.

## Decisions Made

- Kept `base_language` required at the HTTP shape but nullable so a sole detected language can be selected deterministically by the server; multiple candidates reject null with `base_language_required`.
- Kept the completed preview result digest unchanged as the optimistic compare token and generated a second confirmation digest over the full preview identity plus selected base language.
- Rejected noncanonical detector sentinel languages such as `default` rather than persisting them into the normalized mapping field.
- Required active revalidation to match the mapping's existing base language exactly; legacy published mappings with null authority remain blocked and unchanged.
- Treated an exact repeated confirmation as idempotent while rejecting a changed selection after confirmation without overwriting authority.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Seeded an FK-valid actor in the direct service contract**

- **Found during:** Task 1 GREEN focused verification
- **Issue:** The new sole-language service test used a random actor UUID that violated the existing confirmation-to-user foreign key before it could assert the language contract.
- **Fix:** Seeded the confirming user through the established test model and retained a different actor on the idempotent replay to prove actor immutability.
- **Files modified:** `backend/tests/integration/test_preview_jobs.py`
- **Verification:** Focused base-language suite passes all 10 tests.
- **Committed in:** `3eaceb4`

**2. [Rule 2 - Missing Critical Functionality] Kept the checked OpenAPI contract synchronized**

- **Found during:** Adjacent API regression verification
- **Issue:** The plan changed public request and response schemas, but the checked contract test and canonical frontend OpenAPI input were not listed in its files.
- **Fix:** Added exact required/nullability/bounds assertions and regenerated the deterministic schema.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`, `frontend/openapi.json`
- **Verification:** Mapping and OpenAPI regression suite passes all 37 tests, including byte-identical export validation.
- **Committed in:** `3eaceb4`

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 2). Both were required to preserve existing database and API contracts; no architecture expansion was introduced.

## TDD Gate Compliance

- RED `f98d6b4` introduced the candidate, active-revalidation, failure-atomicity, and schema/route tests; the focused run failed in all 10 selected tests before implementation.
- GREEN `3eaceb4` implemented the behavior and left the focused, adjacent preview, and OpenAPI regressions passing.
- REFACTOR `05ae0d0` centralized the language-bound digest comparison across both currentness paths without behavior changes.

## Verification

- Prescribed focused gate: `10 passed, 72 deselected`.
- Complete preview integration/API regression: `82 passed`.
- Mapping and checked OpenAPI regression: `37 passed`.
- Ruff format check: all 6 changed Python implementation/contract files already formatted.
- Ruff check: all changed Python implementation/contract files passed.
- Focused Mypy: no issues in the 3 changed production modules.
- Git diff whitespace check: passed.

## Issues Encountered

- The focused GREEN pass initially exposed the test actor foreign-key omission; this was corrected within the test contract before broader verification.
- Adjacent OpenAPI regression correctly detected stale generated and checked contracts; both were synchronized and reverified.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None beyond the plan's declared administrator-selection boundary. Existing bearer-role enforcement, exact detected-list membership, live-authority locks, and failure-atomic tests cover that boundary.

## Next Phase Readiness

- Plan 04-09 and browser consumers can expose an exact base-language selector backed by a closed API contract.
- Plan 04-27 can propagate confirmed language authority into candidate cloning without inventing a second storage seam.
- Import and publication consumers can reject changed or legacy-null language authority through existing currentness predicates.

## Self-Check: PASSED

- All 7 implementation, generated-contract, and test files exist.
- RED `f98d6b4`, GREEN `3eaceb4`, and REFACTOR `05ae0d0` are present in repository history.
- The canonical summary exists with complete requirement coverage and verification results.
