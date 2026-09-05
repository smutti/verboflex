---
phase: 04-localization-import-search-and-constraints
plan: 12
subsystem: localization-import-api
tags: [fastapi, pydantic, sqlalchemy, postgresql, parser-diagnostics, openapi]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [10, 11]
    provides: stable localization scopes, immutable execution-owned parser issues, and atomic canonical dataset activation
  - phase: 03-bitbucket-import-integration
    provides: published mapping import API, durable import state machine, and administrator authority
provides:
  - closed active, retained, and not-created canonical dataset status on every published mapping import response
  - at most five validated parser issues ordered Direct or Keys then Translations with an exact remainder count
  - fixed parser copy keys that prevent stored diagnostic prose, source excerpts, exceptions, and provider bodies from crossing the API boundary
affects: [admin-import-ui, openapi-generation, generated-client, localization-search, import-retry]
actuals:
  tokens: 8642
  tasks: 1
  commits: 3
tech-stack:
  added: []
  patterns:
    - derive dataset visibility from the active localization scope rather than import request state
    - map durable parser categories to fixed public copy keys and never serialize stored messages
    - sort diagnostics by repository-side authority before persisted provider-file position
key-files:
  created: []
  modified:
    - backend/src/verboflex/schemas/imports.py
    - backend/src/verboflex/services/import_jobs.py
    - backend/src/verboflex/api/v1/routes/admin_mappings.py
    - backend/tests/api/test_admin_mappings.py
    - backend/tests/api/test_openapi_contract.py
    - backend/tests/integration/test_import_jobs.py
key-decisions:
  - "Canonical dataset status is derived from the locked semantic localization scope: the current successful execution is active, a different active execution is retained, and no active execution is not_created."
  - "Public parser diagnostics use a closed issue-code-to-message-key mapping; repository-controlled stored message text is never read into the response."
  - "Diagnostics are validated again at the API projection boundary and ordered Direct, or Keys before Translations, with persisted position as the provider-file tie-breaker."
patterns-established:
  - "Safe diagnostic projection: validate closed code, side, path, and coordinates before constructing a public record."
  - "Dataset authority projection: represent retained canonical data separately from the latest import execution state."
requirements-completed: [FMT-06, FMT-08]
coverage:
  - id: D1
    description: Failed refreshes expose a retained canonical dataset while a first parser failure exposes that no dataset was created.
    requirement: FMT-08
    verification:
      - kind: integration
        ref: backend/tests/api/test_admin_mappings.py#test_parser_failure_api_projects_retained_dataset_and_safe_ordered_issues
        status: pass
    human_judgment: false
  - id: D2
    description: Public parser outcomes contain at most five closed, bounded, ordered issues and no stored source, provider, or exception prose.
    requirement: FMT-06
    verification:
      - kind: integration
        ref: backend/tests/api/test_admin_mappings.py#test_parser_failure_api_projects_retained_dataset_and_safe_ordered_issues
        status: pass
      - kind: unit
        ref: backend/tests/api/test_openapi_contract.py#test_import_schema_literals_requirements_and_bounds_are_frozen
        status: pass
    human_judgment: false
  - id: D3
    description: Existing import endpoints retain administrator-only authority and publish the extended response through the same five-operation OpenAPI surface.
    requirement: FMT-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py#test_public_contract_has_exact_five_operations_and_closed_server_authority
        status: pass
    human_judgment: false
duration: 16min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 12: Bounded Parser Outcome API Summary

**Published mapping imports now distinguish retained canonical authority from first failure and expose only closed, bounded, safely ordered parser diagnostics.**

## Performance

- **Duration:** 16 minutes
- **Started:** 2026-09-05T12:16:34Z
- **Completed:** 2026-09-05T12:32:20Z
- **Tasks:** 1
- **Files changed:** 6 implementation/test files, plus GSD tracking artifacts

## Accomplishments

- Added closed `active`, `retained`, and `not_created` dataset status to the existing published mapping import response, derived from the locked stable localization scope.
- Added a schema-bounded five-item parser issue projection with exact remainder count, safe paths and coordinates, fixed copy keys, and deterministic Direct or Keys-before-Translations ordering.
- Kept raw stored diagnostic messages private and proved source fragments, exception text, script markup, provider bodies, credentials, and internal execution fields cannot enter the browser contract.
- Preserved the existing five-operation administrator-only API and updated exact import response regressions for the additive fields.

## Task Commits

The TDD task was committed atomically:

1. **Task 1 RED: failing parser outcome and dataset authority contracts** - `d33b1cb`
2. **Task 1 GREEN: bounded parser and active-dataset projection** - `7bd55a0`

**Plan metadata:** committed in the final documentation commit.

## Files Created/Modified

- `backend/src/verboflex/schemas/imports.py` - Defines closed dataset status and parser issue schemas with explicit item, path, coordinate, and remainder bounds.
- `backend/src/verboflex/services/import_jobs.py` - Derives dataset authority from the locked semantic scope and validates, orders, caps, and redacts current failed-execution issues.
- `backend/src/verboflex/api/v1/routes/admin_mappings.py` - Maps the safe service records onto the existing administrator import response.
- `backend/tests/api/test_admin_mappings.py` - Covers retained versus first failure, Keys-before-Translations ordering, fixed message keys, authorization, and inert forbidden-text canaries.
- `backend/tests/api/test_openapi_contract.py` - Freezes the new components, literals, required fields, item caps, coordinate limits, and recursive sensitive-field exclusions.
- `backend/tests/integration/test_import_jobs.py` - Keeps the established exact response contract assertions aligned with the additive fields.

## Decisions Made

- A dataset is `active` only when the locked scope points to the current successful execution and its import job; a different active execution is `retained`, and no active execution is `not_created`.
- Stored parser `message` text is deliberately ignored. The API maps the five allowed issue codes to five fixed `import.parser.*` copy keys.
- Side order is explicit rather than lexical: Direct for direct mappings, and Keys before Translations for separate mappings. Persisted issue position preserves provider-file order within each side.
- Invalid durable issue code, side, path, coordinate, or ownership is treated as a persisted-state conflict rather than projected partially.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Regression contract] Updated the established exact import response assertions**
- **Found during:** Task 1 adjacent import regression verification
- **Issue:** Two existing integration assertions compared the entire import response and correctly failed after the planned additive fields were introduced.
- **Fix:** Added `dataset_status`, `parser_issues`, and `parser_issue_remaining_count` to those exact response expectations without weakening any prior assertion.
- **Files modified:** `backend/tests/integration/test_import_jobs.py`
- **Verification:** The combined import, canonical activation, and background-boundary regression passed all 93 tests.
- **Committed in:** `7bd55a0`

---

**Total deviations:** 1 auto-fixed Rule 1 regression contract update.
**Impact on plan:** The extra test-only file preserves established exact API coverage for the planned additive contract; no product scope changed.

## TDD Gate Compliance

- RED commit `d33b1cb` failed at the intended seams: the public response lacked `dataset_status` and the OpenAPI document lacked both new component schemas.
- GREEN commit `7bd55a0` followed RED and passed the prescribed focused suite.
- No standalone REFACTOR commit was needed; the implementation remained focused and passed formatting, lint, and strict focused typing.

## Automated Checks

- Prescribed API/OpenAPI gate: `5 passed, 34 deselected`.
- Full changed API/OpenAPI files excluding the intentionally deferred checked-in schema export assertion: `38 passed, 1 deselected`.
- Adjacent import, canonical activation, and background-boundary regression: `93 passed`.
- Ruff project check: all backend source and tests passed; format check reported 163 files already formatted.
- Focused mypy: no issues in the three changed production modules.
- OpenAPI construction and recursive contract checks passed through the focused schema suite.
- Git whitespace, accidental deletion, and changed-line stub scans passed.

## Issues Encountered

- The full OpenAPI test file has one expected checked-in export drift assertion until Plan 04-15 performs the deliberately deferred final schema export and generated-client update. All live-schema contract tests pass.
- One-shot collection of every backend test remains blocked by the already-recorded duplicate preview/importing test-module basenames. The relevant suites were run independently, including all 93 adjacent import regressions.
- Package-wide `mypy` remains blocked by the existing missing `py.typed` package marker; focused strict typing of every changed production module passes.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None beyond the plan's declared stored-parser-issue to public-browser boundary. Closed schemas, projection-time validation, a five-item cap, fixed copy keys, stable-scope locking, and existing database-resolved administrator dependencies cover T-04-35 through T-04-37.

## Next Phase Readiness

- Plan 04-15 can export the final OpenAPI document and regenerate the frontend client after the remaining backend schema writers complete.
- Plan 04-22 can render retained-versus-first-failure copy and bounded Keys-before-Translations diagnostics directly from generated response fields.
- No user setup or implementation blocker remains.

## Self-Check: PASSED

All six implementation/test artifacts, the summary, and both ordered task commits were verified on disk before state advancement.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-05*
