---
phase: 02-admin-configuration
plan: 02
subsystem: product-api
tags: [fastapi, sqlalchemy, postgresql, immutable-revisions, cursor-pagination, tdd]

requires:
  - phase: 01-platform-foundation
    provides: Provider-independent bearer authentication, database-backed roles, PostgreSQL/Alembic, and canonical OpenAPI export
  - phase: 02-admin-configuration
    plan: 01
    provides: Shared database-backed administrator dependency and internal-user authority
provides:
  - Globally unique UUID products under exact A-01 normalized identity
  - Immutable active product revisions with separately editable candidate revisions
  - Administrator-only create, detail, candidate update, and cursor-paginated collection API
  - Optimistic candidate-version conflicts, transactional rollback, and identity-preserving normalized no-ops
affects: [02-03-repository-model, 02-04-mapping-model, 02-16-validation-preview, 02-17-admin-configuration-ui, 02-20-phase-gauntlet]

actuals:
  tokens: 33928
  tasks: 3
  commits: 16

tech-stack:
  added: []
  patterns:
    - Immutable published revision plus separately versioned editable candidate
    - Exact application-owned NFKC and casefold identity key independent of database collation
    - Filter-bound opaque keyset cursor ordered by name_key then Product UUID
    - Closed response projection with route-specific bounded error contracts

key-files:
  created:
    - backend/alembic/versions/0002_product_revisions.py
    - backend/src/verboflex/api/v1/routes/admin_products.py
    - backend/src/verboflex/models/product.py
    - backend/src/verboflex/schemas/admin_products.py
    - backend/src/verboflex/services/products.py
    - backend/tests/api/test_admin_products.py
    - backend/tests/unit/test_product_names.py
    - tools/verify_product_api_mutants.py
  modified:
    - backend/src/verboflex/api/v1/router.py
    - backend/src/verboflex/main.py
    - backend/src/verboflex/models/__init__.py
    - backend/tests/api/test_openapi_contract.py
    - backend/tests/integration/test_migrations.py
    - frontend/openapi.json

key-decisions:
  - "Apply A-01 in application code and persist its name_key so global product identity never depends on locale-sensitive database collation."
  - "Keep an immutable active revision and a distinct editable candidate; a product mutation cannot publish or rewrite live configuration."
  - "Require the expected candidate version on every update and detect semantic equality before allocating or modifying a revision."
  - "Bind opaque cursors to the active-status filter and order collections by persisted name_key then Product UUID."

patterns-established:
  - "Product revision authority: published rows are immutable, candidate edits use optimistic version checks, and failed writes roll back the whole graph."
  - "Product identity: retain the administrator-facing display name while enforcing global uniqueness through the exact A-01 name_key."
  - "Closed product API: all routes share one database-backed admin guard and expose only explicit active/candidate summaries and bounded response codes."

requirements-completed: [PROD-01]

coverage:
  - id: D1
    description: "Product identity is UUID-based and globally unique under the exact A-01 NFKC, whitespace-collapse, casefold key."
    requirement: PROD-01
    verification:
      - kind: integration
        ref: "backend/tests/unit/test_product_names.py#test_product_uuid_remains_identity_while_a01_name_key_is_globally_unique"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/test_product_names.py#test_a01_normalizes_display_and_global_identity_key"
        status: pass
    human_judgment: false
  - id: D2
    description: "Published configuration remains immutable while candidate creation copies and edits a separate versioned graph."
    requirement: PROD-01
    verification:
      - kind: integration
        ref: "backend/tests/unit/test_product_names.py#test_active_revision_is_immutable_and_stale_candidate_writes_roll_back"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_admin_products.py#test_published_product_noop_and_candidate_creation_keep_active_summary_immutable"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every candidate update requires expected version; stale and duplicate writes roll back while normalized identical saves preserve revision identity and version."
    requirement: PROD-01
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_products.py#test_expected_version_conflicts_duplicate_name_and_identical_save_are_atomic"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_admin_products.py#test_racing_duplicate_create_has_one_winner_and_one_field_scoped_conflict"
        status: pass
    human_judgment: false
  - id: D4
    description: "Product collections are empty-safe, bounded to default 50 and maximum 100, filterable, cursor-validated, and server-ordered by name_key then UUID."
    requirement: PROD-01
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_products.py#test_product_collection_is_bounded_filtered_opaque_and_server_ordered"
        status: pass
    human_judgment: false
  - id: D5
    description: "The administrator bearer boundary denies every product route without mutation, and the closed API exposes no publication shortcut or generic revision mutation."
    requirement: PROD-01
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_products.py#test_every_product_route_reuses_bearer_admin_authority_and_denials_do_not_mutate"
        status: pass
      - kind: contract
        ref: "backend/tests/api/test_openapi_contract.py#test_admin_product_openapi_is_closed_and_exposes_no_publication_shortcut"
        status: pass
    human_judgment: false

duration: 42min
completed: 2026-08-26
status: complete
---

# Phase 02 Plan 02: Immutable Product Revisions and Candidate API Summary

**Administrator-only product APIs now preserve globally normalized identity and immutable live configuration while all edits remain explicit, optimistic, rollback-safe candidate revisions.**

## Performance

- **Duration:** 42 min
- **Started:** 2026-08-26T20:38:21Z
- **Completed:** 2026-08-26T21:20:03Z
- **Tasks:** 3, including the context-satisfied D-20 decision checkpoint
- **Files modified:** 14 implementation, migration, contract, and evidence artifacts
- **Actual estimate scale:** 33,928 tokens (135,711 realized diff characters / 4)

## Accomplishments

- Implemented the exact A-01 product-name contract with deterministic display normalization, casefold identity, global database uniqueness, UUID identity, and rejection of empty, control-bearing, or overlong input.
- Added immutable published revisions and separately editable candidates; candidate creation copies the active graph and no route can publish or mutate an active revision.
- Exposed guarded create, detail, candidate update, and collection routes with closed active/candidate summaries and zero durable mutation for unauthorized callers.
- Enforced mandatory expected candidate versions, atomic 409 conflicts, field-scoped duplicate-name responses, racing-create safety, and identity/version-preserving semantic no-ops.
- Delivered filter-bound opaque keyset pagination with empty, default-50, maximum-100, malformed, oversized, noncanonical, status-filter, and stable `name_key + UUID` proofs.
- Regenerated the canonical OpenAPI artifact and added a reproducible mutation tool for the five highest-risk product invariants.

## Task Commits

Each TDD gate, correction, and evidence hardening step was committed atomically:

1. **Task 2 RED: product revision contract** — `68f84c1` (test)
2. **Task 2 RED fixture isolation** — `4226ae3` (test)
3. **Task 2 RED metadata assertion correction** — `dcc2c58` (test)
4. **Task 2 GREEN: immutable product revisions** — `0840d5c` (feat)
5. **Task 2 REFACTOR: centralized candidate comparisons** — `7e29f2e` (refactor)
6. **Task 3 RED: guarded admin-product API contract** — `b3453d7` (test)
7. **Task 3 RED correction: configured CORS origin** — `4856676` (test)
8. **Task 3 GREEN: guarded product candidate APIs** — `b137fb1` (feat)
9. **Task 3 REFACTOR: bounded route error projection** — `1ddd372` (refactor)
10. **Task 3 contract RED: closed admin-product OpenAPI** — `5cda85b` (test)
11. **Task 3 contract GREEN: canonical operation responses** — `1acf5c1` (fix)
12. **Task 3 contract formatting** — `b474fde` (style)
13. **Task 3 test armor: rejection, race, and active paths** — `4fcfe9f` (test)
14. **Task 3 REFACTOR: fail-closed invalid-input fallback** — `de1a3f8` (refactor)
15. **Task 3 cursor armor: structurally valid noncanonical cursor rejection** — `0b8acfa` (test)
16. **Task 3 mutation evidence: reproducible product mutant proof** — `76b5cdd` (test)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 2 RED:** the exact focused command failed on the intended missing revision behavior after two test-infrastructure corrections (`68f84c1`, `4226ae3`, `dcc2c58`).
- **Task 2 GREEN:** the unchanged focused command passed 14/14 after the minimum immutable revision implementation (`0840d5c`).
- **Task 2 REFACTOR:** the unchanged focused command remained 14/14 (`7e29f2e`); the user explicitly approved the mandatory tracer feedback gate.
- **Task 3 RED:** the exact command `cd backend && uv run pytest -q tests/api/test_admin_products.py -x` failed before production implementation, first surfacing the missing PATCH CORS contract after the route behavior landed only in the test (`b3453d7`).
- **Task 3 GREEN:** the unchanged exact command passed 5/5 after the minimum guarded route, schema, and service implementation (`b137fb1`).
- **Task 3 REFACTOR:** the unchanged exact command remained 5/5 after tightening response projection (`1ddd372`).
- **Final focused proof:** the exact Task 3 command passes 8/8 after contract and rejection armor.

## Verification and Gauntlet Evidence

- Exact Task 3 command: **8 passed**.
- Exact plan-level command: **22 passed**.
- Migration plus canonical OpenAPI contract suite: **11 passed**.
- Full backend suite with PostgreSQL, ephemeral Redis 7, and a real Celery solo worker: **329 passed**.
- Ruff lint and formatting: **76 files checked, pass**.
- mypy: **44 source files plus the mutation tool, pass**.
- Full-suite coverage: **329 passed**; changed product source coverage against `db263d8` is **100% (285/285 changed lines)**. Repository-wide coverage is 99% because pre-existing admin-user branches remain outside this plan's scope.
- Targeted mutation negative control passes, then all five high-risk mutants are killed (**5/5**): candidate-version conjunction, semantic-equality conjunction, UUID-first collection order, cursor-filter conjunction, and viewer-access authorization.
- `detect-secrets` found no credential material in changed product API, service, test, or evidence files.
- Pytest order randomization remained enabled. The dependency graph is unchanged, so no package-legitimacy or supply-chain expansion gate was required.
- Stub scan found no production placeholders, TODOs, FIXMEs, or empty UI-bound values in changed artifacts.

## API Contract Review

- Resource-oriented product paths, JSON request/response schemas, stable operation IDs, and additive versioning remain compatible with the existing `/api/v1` contract.
- Authentication and authorization use the shared OAuth2 bearer and database-backed administrator dependency; explicit tests prove 401/403 denial and zero graph mutation.
- Candidate updates are intrinsically idempotent under required expected versions, semantic no-op detection, transaction rollback, and global A-01 uniqueness.
- Collection blast radius is bounded by fixed default/maximum sizes and opaque keyset cursors; no expensive expansion fields or external side effects are exposed.
- Error responses are non-enumerating and closed to explicit 401, 403, 404, 409, and 422 cases. Product-specific rate-limit policy is intentionally unchanged in this internal-admin slice and remains part of the phase-wide security gauntlet rather than this resource contract.

## Files Created/Modified

- `backend/src/verboflex/models/product.py` — UUID product identity, globally unique A-01 key, immutable revision rows, and active/candidate pointers.
- `backend/alembic/versions/0002_product_revisions.py` — reversible product and revision schema with global identity and pointer/version constraints.
- `backend/src/verboflex/services/products.py` — A-01 authority, candidate copy/edit/no-op logic, optimistic conflicts, and cursor pagination.
- `backend/src/verboflex/schemas/admin_products.py` — closed create/update/detail/list request and active/candidate response projections.
- `backend/src/verboflex/api/v1/routes/admin_products.py` — administrator-only create, detail, update, and list routes with bounded error mapping.
- `backend/src/verboflex/api/v1/router.py` and `backend/src/verboflex/main.py` — router registration and PATCH CORS support.
- `backend/tests/unit/test_product_names.py` — normalization, identity, schema, immutability, conflict, and migration-independent service proofs.
- `backend/tests/api/test_admin_products.py` — guarded API, rollback, no-op, active/candidate, pagination, cursor, CORS, race, and rejection proofs.
- `backend/tests/api/test_openapi_contract.py` and `frontend/openapi.json` — exact closed product surface and canonical generated contract.
- `backend/tests/integration/test_migrations.py` — declarative metadata compatibility with the product schema.
- `tools/verify_product_api_mutants.py` — fail-closed negative control and five targeted product mutation checks.

## Decisions Made

- Locked the already-approved D-20 model: active configuration is immutable, candidate configuration is editable, and publication remains a separate future atomic operation.
- Made A-01 an application-owned pure normalization function and a stored global key rather than delegating identity to database collation.
- Kept duplicate-name disclosure field-scoped and generic while preserving distinct stale-version conflicts.
- Rejected noncanonical cursors as well as malformed, oversized, and filter-mismatched cursors so opaque tokens have one deterministic representation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test bug] Used the configured frontend origin in the PATCH preflight proof**
- **Found during:** Task 3 RED
- **Issue:** The first test used `http://localhost:8080`, while the approved application configuration registers `http://localhost:5173`; the mismatch produced an irrelevant origin rejection.
- **Fix:** Corrected only the test origin while retaining the intended PATCH-method failure.
- **Files modified:** `backend/tests/api/test_admin_products.py`
- **Verification:** The unchanged exact RED command continued to fail on missing PATCH support, and final focused proof passes 8/8.
- **Committed in:** `4856676`

**2. [Rule 2 - Missing critical functionality] Allowed PATCH through the existing CORS boundary**
- **Found during:** Task 3 GREEN
- **Issue:** The new candidate-edit route was unreachable from the configured browser frontend because PATCH was absent from allowed CORS methods.
- **Fix:** Added PATCH to the exact method allowlist.
- **Files modified:** `backend/src/verboflex/main.py`
- **Verification:** The explicit browser preflight contract passes and the full backend regression suite remains green.
- **Committed in:** `b137fb1`

**3. [Rule 2 - Missing critical contract] Closed product operation responses and regenerated canonical OpenAPI**
- **Found during:** Plan-level contract verification
- **Issue:** Framework-default OpenAPI advertised an impossible POST 404 and omitted intended bounded errors, leaving frontend consumers with a wider and inaccurate contract.
- **Fix:** Added precise per-operation response declarations, froze the absence of publication/revision shortcuts, and regenerated `frontend/openapi.json`.
- **Files modified:** `backend/src/verboflex/api/v1/routes/admin_products.py`, `backend/tests/api/test_openapi_contract.py`, `frontend/openapi.json`
- **Verification:** The contract first failed intentionally in `5cda85b`; migration plus canonical OpenAPI verification now passes 11/11.
- **Committed in:** `5cda85b`, `1acf5c1`

**4. [Rule 2 - Missing critical evidence] Added rejection, cursor, race, and mutation armor required by the evidence contract**
- **Found during:** Final old-coder gauntlet
- **Issue:** Happy-path coverage alone did not prove duplicate-create races, active/candidate graph preservation, structurally valid noncanonical cursor rejection, or that the highest-risk assertions could detect behavioral regressions.
- **Fix:** Added focused integration armor and a reproducible negative-control mutation runner for five product invariants.
- **Files modified:** `backend/tests/api/test_admin_products.py`, `tools/verify_product_api_mutants.py`
- **Verification:** Changed-line coverage is 100% and all 5 targeted mutants are killed after the negative control passes.
- **Committed in:** `4fcfe9f`, `0b8acfa`, `76b5cdd`

---

**Total deviations:** 4 auto-fixed (1 test bug, 3 missing correctness/evidence requirements).
**Impact on plan:** The corrections preserve D-20 and the planned resource architecture, add no dependency, and close browser, consumer-contract, rollback, and evidence gaps.

## Issues Encountered

- The first full-suite attempt had no Redis broker or Celery worker. An ephemeral Redis 7 container and real Celery solo worker were started automatically; the full suite then passed 329/329, and both temporary processes were stopped after verification.
- Repository-wide coverage remains 99% because pre-existing admin-user branches are not exercised by this product plan. The required changed product source surface is fully covered at 100% (285/285).

## Authentication Gates

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration or new dependency is required.

## Next Phase Readiness

- Plan 02-03 can attach reusable repository candidates to the stable Product UUID and immutable candidate graph.
- Later mapping and preview plans can rely on distinct active/candidate summaries and deterministic keyset ordering without gaining a publication shortcut.
- `PROD-01` is delivered by this backend plan but remains pending in the cross-phase requirement ledger until its shared UI and final-gauntlet plans also complete.

## Self-Check: PASSED

- All 14 implementation, migration, contract, and evidence artifacts listed above exist.
- All 16 Task 2 and Task 3 commits exist on `codex/phase-2-admin-configuration` in valid RED → GREEN → REFACTOR order.
- Exact focused, plan-level, migration, OpenAPI, full regression, lint, format, type, differential coverage, mutation-control, and secret-scan claims were rerun after the final source/test changes.
- No tracked file deletion, unresolved stub, unrun verification, live temporary verification service, or unintended generated artifact remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-26*
