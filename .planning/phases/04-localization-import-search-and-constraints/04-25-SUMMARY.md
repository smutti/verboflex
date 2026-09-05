---
phase: 04-localization-import-search-and-constraints
plan: 25
subsystem: translation-constraint-api
tags: [fastapi, pydantic, sqlalchemy, oauth2, optimistic-concurrency, unicode]

requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [13, 21]
    provides: active grouped translation detail and transaction-safe authoritative constraint services
provides:
  - strict closed PUT and DELETE constraint mutation contracts
  - exact two-role authorization with shared translation-detail currentness and scope checks
  - fresh group counts, per-value constraint projections, and eligibility after every successful mutation
affects: [openapi-generation, generated-client, constraint-ui, approval-workflow]

actuals:
  tokens: 11542
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - closed StrictInt request models at the HTTP trust boundary
    - shared transaction wrapper for scoped mutation, commit, rollback, and bounded errors
    - response reuse of the authoritative grouped-detail constraint projection

key-files:
  created:
    - backend/src/verboflex/schemas/translation_constraints.py
    - backend/src/verboflex/api/v1/routes/translation_constraints.py
  modified:
    - backend/src/verboflex/api/v1/router.py
    - backend/src/verboflex/main.py
    - backend/tests/api/test_translation_constraints.py

key-decisions:
  - "Only admin and product_manager_reviewer may mutate constraints; translator and viewer retain authenticated detail reads but receive the same generic mutation denial."
  - "Mutation responses embed the existing authoritative constraint projection and add exact group violating/total counts and the new server version."
  - "Missing, inaccessible, inactive, incomplete, and tombstoned authority maps to generic 404; stale versions map to generic 409 without mutation."
  - "Credentialed CORS explicitly allows PUT and DELETE so the separate browser SPA can reach the planned mutation endpoints."

patterns-established:
  - "Constraint route boundary: resolve authenticated group scope, call the versioned service, commit once, and return freshly projected authority."
  - "No-limit is null while zero remains an explicit integer throughout request, service, and response serialization."

requirements-completed: [SRCH-05, SRCH-07, CONS-01, CONS-02, CONS-05]

coverage:
  - id: D1
    description: "PUT accepts only exact integers from 0 through 1,048,576 and a nonnegative exact expected version; DELETE accepts only the exact version."
    requirement: CONS-01
    verification:
      - kind: api
        ref: "backend/tests/api/test_translation_constraints.py — strict schema, missing/extra/null/coercion, and bound cases"
        status: pass
    human_judgment: false
  - id: D2
    description: "Admin and product_manager_reviewer may mutate while translator and viewer receive a bounded generic 403 without service dispatch."
    requirement: CONS-02
    verification:
      - kind: api
        ref: "backend/tests/api/test_translation_constraints.py — complete four-role read/mutation matrix"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every success returns current actual/effective/source/status, exact group counts, eligibility, and server version from authoritative persistence."
    requirement: SRCH-05
    verification:
      - kind: api
        ref: "backend/tests/api/test_translation_constraints.py and backend/tests/api/test_translations.py — mutation and detail projections"
        status: pass
    human_judgment: false
  - id: D4
    description: "Zero, no-limit, equality, exact overage, empty content, and visible Unicode character semantics remain precise and non-ambiguous."
    requirement: CONS-05
    verification:
      - kind: api
        ref: "backend/tests/api/test_translation_constraints.py — EDGE-CONS-05 boundary, empty, encoding, and precision cases"
        status: pass
    human_judgment: false
  - id: D5
    description: "Stable operation IDs and registered v1 routes expose the constraint contract without adding translation, review, comment, provider, or write-back mutation."
    requirement: SRCH-07
    verification:
      - kind: architecture
        ref: "OpenAPI-adjacent and provider/background boundary suites"
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-09-05
status: complete
---
# Phase 04 Plan 25: Role-Gated Constraint Mutation API Summary

**Closed exact-integer PUT/DELETE contracts now expose version-safe maximum-length mutations to the two authorized roles and return fresh authoritative counts, projections, and eligibility.**

## Performance

- **Duration:** 18min
- **Started:** 2026-09-05T14:31:08Z
- **Completed:** 2026-09-05T14:49:08Z
- **Tasks:** 2
- **Files created or modified:** 5

## Accomplishments

- Added closed Pydantic request models that reject missing, extra, null, boolean, float, string-coerced, negative, and out-of-range values before any service dispatch.
- Registered stable `putTranslationConstraint` and `deleteTranslationConstraint` operations with exact admin/product-manager-reviewer authorization and shared translation-detail scope/currentness checks.
- Returned authoritative server versions, group violating/total counts, and per-value actual/effective/source/status/eligibility after every successful PUT or DELETE.
- Proved zero, no-limit, equality, exact overage, empty content, and visible Unicode-character behavior without introducing review, comment, provider, text, or write-back mutation.

## TDD Gate Compliance

- **Task 1 RED — `356e6ff`:** the strict transport and projection tests failed because the constraint schema module did not exist.
- **Task 1 GREEN — `1fe1d81`:** closed exact-integer mutation models and authoritative response projections made the focused schema slice pass.
- **Task 2 RED — `65b4608`:** the complete route, role, currentness, CORS, and operation-ID matrix failed because the mutation routes were absent.
- **Task 2 GREEN — `8cbaf12`:** role-gated PUT/DELETE endpoints, bounded error mapping, router registration, and browser preflight support made the complete API slice pass.
- **REFACTOR — `1b08ae6`:** centralized transaction/error handling and made random-UUID response assertions order-independent while all focused tests remained green.

Git history preserves each RED commit before its corresponding GREEN commit, followed by one behavior-preserving REFACTOR commit.

## Task Commits

1. **RED: Add failing constraint transport schemas** - `356e6ff` (test)
2. **GREEN: Define closed constraint mutation schemas** - `1fe1d81` (feat)
3. **RED: Add failing constraint route contracts** - `65b4608` (test)
4. **GREEN: Expose role-gated constraint mutations** - `8cbaf12` (feat)
5. **REFACTOR: Centralize constraint mutation transactions** - `1b08ae6` (refactor)

## Files Created/Modified

- `backend/src/verboflex/schemas/translation_constraints.py` - Strict closed request models and response projections that preserve null versus zero.
- `backend/src/verboflex/api/v1/routes/translation_constraints.py` - Scoped, role-gated, version-safe PUT/DELETE endpoints with bounded error mapping.
- `backend/src/verboflex/api/v1/router.py` - Translation-constraint router registration.
- `backend/src/verboflex/main.py` - Credentialed CORS support for the new PUT and DELETE browser mutations.
- `backend/tests/api/test_translation_constraints.py` - Direct-schema and PostgreSQL-backed API evidence for bounds, roles, currentness, rollback, Unicode, exact counts, and OpenAPI.

## Decisions Made

- Reuse the grouped-detail `TranslationConstraintProjectionResponse` in mutation responses so read and write consumers cannot drift on actual/effective/source/status/eligibility semantics.
- Treat inaccessible, missing, inactive, incomplete, and tombstoned authority uniformly as `404 Translation unavailable`, while stale optimistic versions return `409 Translation constraint conflict`.
- Run the existing grouped-detail scope/currentness lookup before mutation and commit only after the Plan 21 service returns its authoritative projection.
- Preserve browser architecture by adding only the required `PUT` and `DELETE` CORS methods; route behavior remains synchronous database-only work allowed by D-21.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Allowed constraint mutation methods through credentialed CORS**
- **Found during:** Task 2 GREEN API verification
- **Issue:** The separate browser SPA could not preflight the planned constraint mutations because CORS allowed only `GET` and `POST`.
- **Fix:** Added `PUT` and `DELETE` to the explicit allow-methods list and covered both successful and denied origins.
- **Files modified:** `backend/src/verboflex/main.py`, `backend/tests/api/test_translation_constraints.py`
- **Verification:** The full constraint/detail/CORS API slice passes with 41 tests.
- **Committed in:** `8cbaf12`

---

**Total deviations:** 1 auto-fixed (1 Rule 2 critical browser transport issue).
**Impact on plan:** No product scope expanded; this completes the required transport path for the planned endpoints.

## Issues Encountered

- The full exact OpenAPI freeze suite reports the expected two Plan 04-15-owned failures: the canonical operation inventory and checked-in generated frontend schema do not yet include the three Plan 13 reads and two Plan 25 mutations. All 16 adjacent OpenAPI assertions pass, and the existing Phase 4 deferred item now names all five planned operations. No client regeneration was performed outside Plan 04-15 ownership.
- Random UUID ordering made one initial response assertion nondeterministic; the refactor compares the authoritative projections by stable display text/value set instead of database UUID order.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. The test-only `structure=[]` fixture and empty dispatch-call list are intentional evidence, not production placeholders or unwired UI data.

## Verification

- Task 1 exact schema/projection selection - 28 passed, 5 deselected.
- Task 2 exact role/currentness/detail selection - 37 passed, 2 deselected.
- Full constraint, translation-detail, and CORS API slice - 41 passed.
- Constraint-service and translation-search integration regression - 41 passed.
- OpenAPI-adjacent contract suite excluding the Plan 04-15-owned freeze/export assertions - 16 passed, 2 deselected.
- Provider and background architecture boundaries - 11 passed.
- Ruff lint and focused format checks over all changed implementation/test files - passed.
- Focused mypy over the schema, route, router, and application modules - passed with no issues.
- `uv lock --check --project backend` and `uv run --project backend pip check` - passed.
- Stub and mutation-surface scans found no production placeholders and no review, comment, provider, translation-text, write-back, or Celery dispatch path.

## Threat Review

- T-04-68 is mitigated by database-resolved principals, the exact two-role dependency, authenticated group-scope resolution, and the complete four-role API matrix.
- T-04-69 is mitigated by closed strict schemas, exact expected-version comparison, generic bounded failures, rollback on every error, and fresh server-owned projections.
- No security-relevant surface beyond the plan's authenticated mutation route boundary was introduced.

## Next Phase Readiness

- Plan 04-15 can freeze the final Phase 4 operation inventory and regenerate the checked-in frontend client with both mutation operations.
- The constraint UI and later approval workflow can consume one authoritative read/write projection without client-owned validation or count logic.
- No schema, role, currentness, transaction, Unicode, static-analysis, or dependency blocker remains.

## Self-Check: PASSED

- All five declared implementation/test files and this summary exist.
- RED, GREEN, and REFACTOR commits `356e6ff`, `1fe1d81`, `65b4608`, `8cbaf12`, and `1b08ae6` resolve in repository history.
- The implementation commit range contains no tracked-file deletions.
- Required frontmatter, requirement IDs, verification evidence, deviation ledger status, threat review, and stub disclosure are present.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-05*
