---
phase: 02-admin-configuration
plan: 03
subsystem: repository-api
tags: [fastapi, sqlalchemy, postgresql, repository-registry, cursor-pagination, tdd]

requires:
  - phase: 01-platform-foundation
    provides: Provider-independent bearer authentication, PostgreSQL/Alembic, and canonical OpenAPI export
  - phase: 02-admin-configuration
    plan: 01
    provides: Shared database-backed administrator dependency
  - phase: 02-admin-configuration
    plan: 02
    provides: Stable Product UUIDs and immutable candidate configuration boundary
provides:
  - Global reusable repository UUIDs under normalized lowercase workspace and slug identity
  - Administrator-only register, list, and get-by-UUID repository API
  - Canonical opaque keyset pagination using descriptive-name or workspace/slug fallback order
  - Credential-free and provider-read-free repository selection contract
affects: [02-08-mapping-model, 02-18-product-configuration-ui, 02-20-phase-gauntlet, repository-discovery]

actuals:
  tokens: 30232
  tasks: 3
  commits: 9

tech-stack:
  added: []
  patterns:
    - Global provider identity separated from product-owned mapping configuration
    - Database uniqueness as the duplicate-registration concurrency linearization point
    - Canonical opaque cursor over the complete server ordering tuple

key-files:
  created:
    - backend/alembic/versions/0003_repositories.py
    - backend/src/verboflex/models/repository.py
    - backend/src/verboflex/services/repositories.py
    - backend/src/verboflex/schemas/admin_repositories.py
    - backend/src/verboflex/api/v1/routes/admin_repositories.py
    - backend/tests/integration/test_repository_registry.py
    - backend/tests/api/test_admin_repositories.py
    - tools/verify_repository_api_mutants.py
  modified:
    - backend/src/verboflex/models/__init__.py
    - backend/src/verboflex/api/v1/router.py
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json

key-decisions:
  - "Retain D-07: one global Repository UUID is uniquely identified by normalized lowercase workspace plus repository slug."
  - "Keep duplicate registration as a bounded conflict; get-by-UUID is the separate reuse and mapping-selection operation."
  - "Order collections by normalized descriptive-name key with workspace/slug fallback, then workspace, slug, and Repository UUID."
  - "Exclude provider reads, tokens, credentials, branches, and product mapping state from the repository registry boundary."

patterns-established:
  - "Repository identity: structural ASCII normalization and database composite uniqueness define one reusable provider resource."
  - "Repository selection: register never masquerades as reuse; consumers select an existing UUID through detail/list operations."
  - "Repository pagination: the cursor is canonical, bounded, and carries the entire four-part keyset position."

requirements-completed: [PROD-02]

coverage:
  - id: D1
    description: "Repository identity is globally reusable, normalized, credential-free, and race-safe under one composite database constraint."
    requirement: PROD-02
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_repository_registry.py#test_two_session_registration_race_has_one_201_one_409_and_one_row"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_repository_registry.py#test_repository_schema_is_global_credential_and_mapping_free"
        status: pass
    human_judgment: false
  - id: D2
    description: "Only an active administrator can register repositories, while duplicate registration conflicts and UUID selection remains separate."
    requirement: PROD-02
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_repositories.py#test_repository_registration_conflict_and_uuid_selection_are_separate_operations"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_admin_repositories.py#test_every_repository_route_reuses_admin_authority_and_denials_do_not_mutate"
        status: pass
    human_judgment: false
  - id: D3
    description: "Repository lists are empty-safe, default-50, maximum-100, cursor-validated, and exactly ordered by descriptive fallback plus provider identity and UUID."
    requirement: PROD-02
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_repositories.py#test_repository_collection_is_empty_bounded_opaque_and_exactly_server_ordered"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_admin_repositories.py#test_repository_service_and_cursor_rejection_branches_fail_closed"
        status: pass
    human_judgment: false
  - id: D4
    description: "The repository API is closed to additional fields and contains no token, credential, provider-read, branch, or product configuration capability."
    requirement: PROD-02
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_repositories.py#test_repository_api_is_closed_credential_free_and_provider_read_free"
        status: pass
      - kind: other
        ref: "uv run detect-secrets scan <02-03 changed contract files>"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-08-27
status: complete
---

# Phase 02 Plan 03: Global Repository Registry and Admin API Summary

**A normalized, credential-free global repository registry now exposes guarded registration and deterministic UUID selection without performing live provider discovery.**

## Performance

- **Active duration:** 15 min, excluding the overnight tracer-approval wait
- **Started:** 2026-08-26T21:29:12Z
- **Completed:** 2026-08-27T06:00:29Z
- **Tasks:** 3, including the context-satisfied D-07 checkpoint
- **Files modified:** 12 implementation, migration, contract, and evidence artifacts
- **Actual estimate scale:** 30,232 tokens (120,926 realized diff characters / 4, rounded)

## Accomplishments

- Added a global Repository UUID with structural lowercase workspace/slug normalization, named checks, composite uniqueness, reversible migration, and no product or credential state.
- Exposed administrator-only create, list, and detail routes where duplicate registration is a bounded `409` and get-by-UUID is the separate reuse path.
- Delivered canonical cursor pagination with empty, default-50, maximum-100, malformed, oversized, noncanonical, wrong-shape, wrong-type, and exact ordering proofs.
- Closed request and response schemas against additional fields and froze the canonical FastAPI/OpenAPI contract without provider reads or token storage.
- Added reproducible 100% statement/branch coverage and six targeted mutation checks for the highest-risk repository invariants.

## Task Commits

Each TDD and evidence gate was committed atomically:

1. **Task 2 RED: repository registry contract** — `32302da` (test)
2. **Task 2 GREEN: global repository registry** — `4042070` (feat)
3. **Task 2 REFACTOR: isolated input normalization** — `d861331` (refactor)
4. **Task 3 RED: guarded repository API contract** — `31a9eca` (test)
5. **Task 3 GREEN: guarded repository registry API** — `91dccb4` (feat)
6. **Task 3 REFACTOR: tuple-based cursor comparison** — `cca3f6d` (refactor)
7. **Task 3 evidence armor: validation coverage and mutation proof** — `a45a7be` (test)
8. **Task 3 contract RED: exact repository OpenAPI operations** — `6b70d51` (test)
9. **Task 3 contract GREEN: canonical frontend OpenAPI** — `d3340e3` (fix)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 2 RED:** the exact integration command failed on the missing repository registry behavior (`32302da`).
- **Task 2 GREEN:** the unchanged command passed 4/4 after the global model, migration, and service landed (`4042070`).
- **Task 2 REFACTOR:** the unchanged command remained 4/4 after normalization was isolated (`d861331`); the user explicitly approved the tracer feedback gate.
- **Task 3 RED:** `cd backend && uv run pytest -q tests/api/test_admin_repositories.py -x` failed with `404 != 201` because no repository route existed (`31a9eca`).
- **Task 3 GREEN:** the unchanged exact command passed 4/4 after minimal schemas, routes, list authority, and router registration (`91dccb4`).
- **Task 3 REFACTOR:** the unchanged exact command remained 4/4 after the keyset predicate became one lexicographic tuple comparison (`cca3f6d`).
- **Contract RED/GREEN:** the exact OpenAPI suite failed only on stale canonical frontend schema after the operation map was frozen (`6b70d51`), then passed 8/8 after canonical regeneration (`d3340e3`).
- **Final focused proof:** the exact Task 3 command passes 5/5 after validation and cursor rejection armor.

## Verification and Gauntlet Evidence

- Exact Task 3 command: **5 passed**.
- Exact plan-level command: **9 passed**.
- Migration plus canonical OpenAPI contract suite: **11 passed**.
- Full backend suite with PostgreSQL, ephemeral Redis 7, and a real Celery solo worker: **338 passed**.
- Ruff lint and formatting: **83 files checked, pass**.
- mypy: **48 source files including the mutation tool, pass**.
- Focused plan coverage: **9 passed**, **100% statements (183/183)** and **100% branches (28/28)**.
- Differential coverage against `459b185`: **100% (183/183 changed repository source lines)**.
- Targeted mutation checker negative control passed; all six high-risk mutants were killed (**6/6**): admin authorization, conflict mapping, closed input, cursor canonicality, exact collection ordering, and UUID selection.
- `detect-secrets` returned an empty result over all changed registry, API, contract, test, evidence, and canonical OpenAPI artifacts.
- The dependency graph is unchanged; no package installation, runtime capability, or supply-chain expansion occurred.
- Stub scan found no production placeholder, TODO, FIXME, or empty UI-bound value.

## API Contract Review

- The additive `/api/v1/admin/repositories` collection and UUID detail paths use stable operation IDs and explicit response models.
- Authentication and authorization reuse database-loaded OAuth2 bearer authority and the administrator role dependency; denied requests cause no repository mutation.
- Registration is intentionally non-idempotent for equal normalized identity and returns bounded `409`; UUID lookup/list provide the explicit reuse operation.
- List cost is bounded to default 50 and maximum 100 through canonical opaque keyset cursors; ordering is server-owned and complete.
- Request and response models forbid additional properties and project only UUID, workspace, repository slug, and optional descriptive name.
- The slice performs no external reads and stores no token, credential, branch, mapping, topology, format, or product ownership state.

## Files Created/Modified

- `backend/src/verboflex/models/repository.py` and `backend/alembic/versions/0003_repositories.py` — global provider identity, named constraints, and reversible schema.
- `backend/src/verboflex/services/repositories.py` — normalization, conflict authority, UUID lookup, exact ordering, and canonical cursor pagination.
- `backend/src/verboflex/schemas/admin_repositories.py` — closed create, item, and collection projections.
- `backend/src/verboflex/api/v1/routes/admin_repositories.py` and `backend/src/verboflex/api/v1/router.py` — guarded create/list/detail surface and router registration.
- `backend/tests/integration/test_repository_registry.py` — schema, sequential conflict, separate lookup, and real two-session race proof.
- `backend/tests/api/test_admin_repositories.py` — authorization, registration, selection, pagination, ordering, rejection, closed-schema, and provider-boundary proof.
- `backend/tests/api/test_openapi_contract.py` and `frontend/openapi.json` — exact canonical browser-facing contract.
- `tools/verify_repository_api_mutants.py` — fail-closed negative control and six targeted repository mutation checks.

## Decisions Made

- Adopted the already-approved one-way D-07 decision without reopening it: normalized workspace and slug identify one global reusable Repository UUID.
- Kept provider identity normalization structural and ASCII-only; optional descriptive names use NFKC, Unicode whitespace collapse, and casefold solely for display ordering.
- Kept registration conflict semantics distinct from reuse so a repeated create cannot masquerade as another successful selection.
- Bound every cursor to the exact normalized sort key, workspace, slug, and UUID position and reject noncanonical encodings.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical evidence] Closed validation branches and added reproducible mutation proof**
- **Found during:** Task 3 final evidence gate
- **Issue:** The first fail-closed coverage run reported 93.36%, leaving seven service lines and seven partial branches unexercised; coverage alone also did not prove the highest-risk assertions could detect behavioral regressions.
- **Fix:** Added meaningful direct-caller and hostile-cursor rejection cases plus a fail-closed mutation runner with its own negative control and six reviewed mutations.
- **Files modified:** `backend/tests/api/test_admin_repositories.py`, `tools/verify_repository_api_mutants.py`
- **Verification:** Repository source coverage is 100% statements/branches and all six mutants are killed.
- **Committed in:** `a45a7be`

**2. [Rule 2 - Missing critical contract] Added the repository operations to canonical OpenAPI**
- **Found during:** Full backend regression
- **Issue:** The global exact-operation test and checked-in frontend schema did not yet include the new guarded repository endpoints, producing two plan-caused failures.
- **Fix:** Froze exact methods, operation IDs, response codes, security, and error schemas, then regenerated the canonical frontend OpenAPI document.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`, `frontend/openapi.json`
- **Verification:** Migration plus OpenAPI suite passes 11/11 and the full backend suite passes 338/338.
- **Committed in:** `6b70d51`, `d3340e3`

---

**Total deviations:** 2 auto-fixed (2 missing critical correctness/evidence requirements).
**Impact on plan:** Both additions close required consumer-contract and evidence gaps without changing the approved architecture, dependency graph, or Phase 2 capability boundary.

## Issues Encountered

- The first focused coverage gate failed at 93.36%; rejection-path armor raised the exact changed source surface to 100% statement and branch coverage.
- The first full regression exposed two repository-caused OpenAPI drift failures; the contract was frozen RED-first and the canonical artifact regenerated.
- Differential coverage was initially invoked from the backend directory with repository-root include paths and correctly reported no matched lines; rerunning the same fail-under gate from the repository root matched and proved all 183 changed source lines.
- Full regression required a real Redis/Celery boundary. An ephemeral Redis 7 container and a separate Celery solo worker were started automatically, all 338 tests passed, and both temporary services were stopped afterward.

## Authentication Gates

None.

## Known Stubs

None.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: authorization | backend/src/verboflex/api/v1/routes/admin_repositories.py | New administrator HTTP surface not explicitly enumerated in the plan threat table; mitigated by the shared database-backed admin dependency and zero-mutation 401/403 tests. |

## User Setup Required

None - no external service configuration or new dependency is required.

## Next Phase Readiness

- Plan 02-04 can establish the organizational OAuth credential boundary independently of the credential-free registry.
- Plan 02-08 can attach revision-owned mapping configuration to selected Repository UUIDs without copying provider identity or coupling products.
- `PROD-02` is delivered by this backend plan but remains pending in the shared requirement ledger until the plans that also declare it complete.

## Self-Check: PASSED

- All 12 implementation, migration, contract, and evidence artifacts listed above exist.
- All nine Task 2 and Task 3 commits exist on `codex/phase-2-admin-configuration` in valid RED → GREEN → REFACTOR order.
- Coverage metadata classifies all four deliverables as automatically proven by passing executable evidence.
- Exact focused, plan-level, migration, OpenAPI, full regression, lint, format, type, differential coverage, mutation-control, and secret-scan claims were rerun after the final source/test changes.
- No tracked deletion, unresolved stub, unrun verification, live temporary verification service, or unintended generated artifact remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-27*
