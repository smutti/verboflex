---
phase: 02-admin-configuration
plan: 08
subsystem: candidate-repository-mappings
tags: [fastapi, sqlalchemy, alembic, postgresql, openapi, tdd]

requires:
  - phase: 02-admin-configuration
    plan: 02
    provides: Stable Product identity with immutable active and editable candidate revisions
  - phase: 02-admin-configuration
    plan: 03
    provides: Global reusable Repository UUID registry
  - phase: 02-admin-configuration
    plan: 07
    provides: Exact live branch discovery and immutable provider source authority
provides:
  - Revision-owned direct/separate mapping schema with explicit repository sides and normalized target sets
  - Candidate-versioned direct mapping create/update with exact live branch membership and semantic no-op preservation
  - Administrator-only bounded mapping list/create/update API with exact stable tuple pagination and no delete lifecycle
  - Canonical OpenAPI and generated TypeScript client for the candidate mapping surface
  - Reproducible 100% changed-line branch coverage and 9/9 killed mapping mutants
affects: [02-09-separate-mappings, 02-12-format-detection, 02-14-layout-selection, 02-18-admin-ui, 02-20-phase-gauntlet]

actuals:
  tokens: 59270
  tasks: 3
  commits: 13

tech-stack:
  added: []
  patterns:
    - Keep product-specific repository configuration on an editable candidate revision while the global Repository remains reusable
    - Use the candidate revision version as the sole optimistic concurrency token for mapping mutations
    - Bind canonical opaque keyset cursors to the candidate revision and exact database ordering tuple

key-files:
  created:
    - backend/alembic/versions/0005_product_mappings.py
    - backend/src/verboflex/models/product_mapping.py
    - backend/src/verboflex/services/mappings.py
    - backend/src/verboflex/schemas/admin_mappings.py
    - backend/src/verboflex/api/v1/routes/admin_mappings.py
    - backend/tests/unit/services/test_mappings.py
    - backend/tests/api/test_admin_mappings.py
    - tools/verify_mapping_api_mutants.py
  modified:
    - backend/src/verboflex/models/__init__.py
    - backend/src/verboflex/api/v1/router.py
    - backend/tests/api/test_admin_products.py
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json
    - frontend/src/api/client/index.ts
    - frontend/src/api/client/sdk.gen.ts
    - frontend/src/api/client/types.gen.ts

key-decisions:
  - "Retain D-12: one ProductRepositoryMapping identity has exactly one explicit direct or separate topology."
  - "Store source branch, allowed targets, default target, and selected layout reference on the candidate revision mapping; a global Repository shares none of that product-specific configuration."
  - "Expose only guarded list/create/update operations in Plan 08; separate-topology mutation remains Plan 09 and no mapping delete lifecycle exists."
  - "Order mapping pages by topology rank, primary repository UUID, C-collated primary branch, NULLS-LAST translation repository/branch, then mapping UUID, with the cursor bound to the candidate revision."

patterns-established:
  - "Revision-owned configuration: effective mapping edits increment candidate version exactly once; normalized identical edits preserve version, timestamps, selected layout, and active revision."
  - "Closed mapping transport: manual format, layout, discovery, glob, path, file, locale, and lifecycle controls are rejected at the schema boundary."
  - "Form-addressable conflicts: mapping identity, candidate version, source branch, and allowed target branch failures have stable named fields."

requirements-completed: [PROD-03, PROD-04, PROD-05, PROD-06, PROD-09]

coverage:
  - id: D1
    description: "A direct mapping owns one exact source branch and normalized non-empty allowed targets with exactly one member default on the editable candidate revision."
    requirement: PROD-03
    verification:
      - kind: unit
        ref: "backend/tests/unit/services/test_mappings.py#test_direct_mapping_is_revision_owned_and_has_one_exact_repository_side"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/services/test_mappings.py#test_target_set_rejects_empty_malformed_or_nonmember_default_without_mutation"
        status: pass
    human_judgment: false
  - id: D2
    description: "Current live discovery is authoritative for exact source and target branch spelling; stale candidate versions and unavailable branches fail closed."
    requirement: PROD-04
    verification:
      - kind: unit
        ref: "backend/tests/unit/services/test_mappings.py#test_branches_must_match_current_live_discovery_exactly"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_admin_mappings.py#test_direct_create_update_conflicts_and_noop_preserve_active_revision"
        status: pass
    human_judgment: false
  - id: D3
    description: "The single mapping model projects Direct and Separate topology explicitly while keeping repository-specific configuration isolated per product candidate."
    requirement: PROD-06
    verification:
      - kind: unit
        ref: "backend/tests/unit/services/test_mappings.py#test_repository_reuse_never_shares_mapping_configuration_between_products"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_admin_mappings.py#test_mapping_collection_uses_exact_tuple_order_and_stable_opaque_pages"
        status: pass
    human_judgment: false
  - id: D4
    description: "Mapping mutations preserve product-owned lifecycle and candidate concurrency semantics needed by later pull-request behavior without introducing mapping state or delete operations."
    requirement: PROD-05
    verification:
      - kind: unit
        ref: "backend/tests/unit/services/test_mappings.py#test_duplicate_identity_conflicts_while_identical_update_is_a_true_noop"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_admin_mappings.py#test_route_table_and_openapi_expose_no_mapping_delete_operation"
        status: pass
    human_judgment: false
  - id: D5
    description: "Selected layout identity is schema-owned but remains absent until deterministic discovery and confirmation; administrators cannot persist a manual format or layout."
    requirement: PROD-09
    verification:
      - kind: unit
        ref: "backend/tests/unit/services/test_mappings.py#test_schema_is_reversible_revision_owned_and_has_no_manual_or_lifecycle_controls"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_admin_mappings.py#test_mapping_requests_are_admin_guarded_and_reject_manual_controls"
        status: pass
    human_judgment: false
  - id: D6
    description: "Candidate mapping collection pages are bounded to 50 by default and 100 maximum under a canonical candidate-bound opaque cursor and the exact PostgreSQL ordering tuple."
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_mappings.py#test_mapping_collection_is_empty_default_50_and_maximum_100"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/services/test_mappings.py#test_mapping_cursor_is_canonical_closed_and_candidate_bound"
        status: pass
      - kind: other
        ref: "tools/verify_mapping_api_mutants.py"
        status: pass
    human_judgment: false

duration: 1h05min
completed: 2026-08-27
status: complete
---

# Phase 02 Plan 08: Candidate Repository Mapping Summary

**Revision-owned direct mappings now persist and cross an administrator-only candidate API with exact live-branch validation, optimistic versioning, stable opaque pagination, and no independent lifecycle or manual layout authority.**

## Performance

- **Duration:** 1h05min, including the tracer approval handoff
- **Started:** 2026-08-27T11:39:22Z
- **Completed:** 2026-08-27T12:44:05Z
- **Tasks:** 3
- **Files modified:** 16 runtime, migration, API, generated-client, test, and evidence artifacts
- **Actual estimate scale:** 59,270 tokens (237,080 realized diff characters / 4)

## Accomplishments

- Added reversible PostgreSQL persistence for one revision-owned mapping identity, explicit direct/separate topology, exact repository sides, a normalized non-empty allowed-target set, one default member, and optional detected layout identity/version.
- Added exact live branch validation and candidate-versioned direct create/update. Effective changes increment once; normalized identical writes are true no-ops and never touch active configuration.
- Added administrator-only list/create/update endpoints with 50/100 bounds, canonical candidate-bound cursors, exact `C`-collated/NULLS-LAST/UUID ordering, named conflicts, and no delete route.
- Rejected administrator-authored discovery, format, layout, glob, path, file, locale, and lifecycle fields and synchronized the canonical OpenAPI plus TypeScript client.
- Closed the slice with 100% changed-production-line branch coverage, 9/9 killed mutants, 433 backend regressions, and the complete frontend/build smoke gate.

## Task Commits

Each TDD and evidence gate was committed atomically:

1. **Task 2 RED: direct revision mapping contract** — `0f6fcb8` (test)
2. **Task 2 RED fixture correction: reusable repository identity** — `5beb15d` (test)
3. **Task 2 GREEN: direct revision mapping persistence** — `baf5ccb` (feat)
4. **Task 3 RED: candidate mapping API contract** — `77eb4fb` (test)
5. **Task 3 RED fixture correction: complete collision identity** — `0465650` (test)
6. **Task 3 GREEN: candidate mapping administration** — `46a2fe6` (feat)
7. **Task 3 REFACTOR: centralized conflict projection** — `480bc9e` (refactor)
8. **Canonical OpenAPI RED: frozen mapping operations and responses** — `2e1fabb` (test)
9. **Generated client synchronization** — `8b5c3c9` (chore)
10. **Adjacent product-route regression alignment** — `654cdfd` (test)
11. **Changed-line edge coverage armor** — `d9730e2` (test)
12. **Mutation resistance evidence** — `b50d29e` (test)
13. **Canonical cursor-evidence formatting** — `f3ef504` (style)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 2 RED:** the exact `cd backend && uv run pytest -q tests/unit/services/test_mappings.py -x` command failed before the revision-owned mapping model and service existed (`0f6fcb8`).
- **Task 2 GREEN:** the unchanged tracer command passed **10/10** after the minimal model, reversible migration, and direct mapping service landed (`baf5ccb`).
- **Task 2 REFACTOR:** the unchanged command remained green; no justified behavior-preserving source refactor existed, so no empty commit was created. The tracer was approved before expansion.
- **Task 3 RED:** the exact `cd backend && uv run pytest -q tests/api/test_admin_mappings.py -x` command failed with the intended missing-route 404 before implementation (`77eb4fb`).
- **Task 3 GREEN:** the unchanged command passed **13/13** after the minimal guarded list/create/update surface landed (`46a2fe6`).
- **Task 3 REFACTOR:** the unchanged command remained **13/13** after domain-conflict projection was centralized (`480bc9e`).
- **Final exact Task 3 proof:** the unchanged command passes **15/15** after edge coverage and mutation armor.
- **Final plan proof:** `cd backend && uv run pytest -q tests/unit/services/test_mappings.py tests/api/test_admin_mappings.py -x` passes **28/28**.

## Gauntlet Evidence

- Full randomized backend regression under preserved seed `4`, using project PostgreSQL plus a temporary isolated Redis 7 and Celery solo worker: **433 passed in 31.73s**. The worker and container were stopped and removed afterward.
- Canonical OpenAPI, reversible migrations, and architecture suite: **20 passed**.
- Ruff lint: **all checks passed**; Ruff format: **111 files already formatted**.
- mypy: **66 source files, no issues**.
- Focused coverage selection: **38 passed**; changed-line branch coverage against the approved Task 3 RED boundary `77eb4fb^`: **100% (168/168 production lines)**.
- Mapping mutation checker negative control passed; baseline passed; **9/9 mutants killed** across authorization, closed input, cursor canonicality/binding, topology and branch order, pagination lookahead, no-op semantics, and named conflict projection.
- Frontend canonical client check, TypeScript, ESLint, Prettier, Vitest **75/75**, and production build all passed; Vite transformed 1,948 modules.
- `uv lock --check` resolved **112 packages**; this plan changed no dependency manifest or lockfile.
- `pip-audit` found **no known Python vulnerabilities**; the local `verboflex` package was the sole expected non-PyPI skip.
- License evidence remained approved: SQLAlchemy 2.0.52 is MIT, HTTPX 0.28.1 is BSD, defusedxml 0.7.1 is PSF, and cryptography 50.0.1 is Apache-2.0 or BSD-3-Clause.
- `npm audit --audit-level=high` passed. The pre-existing moderate `qs` advisory in development-only Stryker tooling remains recorded in `deferred-items.md`; no JavaScript dependency graph changed.
- `detect-secrets` found **0 findings** across all 16 changed source, migration, tests, generated contracts, and mutation-evidence files.
- Stub scan found no placeholder, TODO, FIXME, skipped test, empty UI-bound value, or unrun verification on the changed production surface.

## API Contract Review

- The three operations are additive, administrator-only, versioned below `/api/v1`, and represented in canonical OpenAPI with explicit 401/403/404/409/422/503 response schemas where applicable.
- Collection access is bounded to 50 by default and 100 maximum. The server owns ordering and a canonical opaque cursor binds every continuation to the same candidate revision.
- Create is intentionally non-idempotent by identity: an existing mapping returns a bounded `mapping_identity` conflict. Update is candidate-version guarded and normalized identical content is a true idempotent no-op.
- UUIDs identify product, repository, and mapping resources; exact branch strings remain provider authority. Errors expose stable bounded details and no provider body, credential, stack, or database diagnostic.
- Global middleware continues to enforce the existing application rate-limit boundary. The list performs no provider reads; mutations validate only the referenced repository's current live branches before persistence.
- No mapping-delete operation exists in the route table, checked-in OpenAPI, or generated client. Product candidate publication remains the only operational lifecycle.

## Security Contract Review

- Administrator authorization is evaluated before database mutation; anonymous and authenticated non-admin callers fail without mapping persistence.
- Product/candidate ownership, expected version, mapping UUID, and uniqueness constraints are revalidated transactionally under locks. Stale, duplicate, cross-candidate, and unavailable identities fail closed.
- Source and target branches must be exact members of current live discovery. Case folding, trimming, manual discovery results, and guessed layout/path controls never gain authority.
- Active revision identity and content remain unchanged across successful candidate edits, conflicts, invalid input, missing dependencies, and normalized no-ops.
- Canonical cursor decoding rejects malformed JSON/base64, alternate encodings, wrong scalar types, extra fields, excessive length, and another candidate revision.

## Decisions Made

- Kept the already-approved D-12 one-model topology: Direct uses one `direct` repository side; Separate projects `keys` plus `translations` sides under the same mapping identity.
- Kept global Repository reuse deliberately narrow: branch, targets, layout selection, timestamps, and candidate version remain revision-owned configuration.
- Used the exact ordered tuple `(direct=0/separate=1, primary repository UUID, primary branch COLLATE "C", translations repository UUID NULLS LAST, translations branch COLLATE "C" NULLS LAST, mapping UUID)` for both pages and cursors.
- Kept Plan 08 writes Direct-only. Separate mutation belongs to Plan 09 and deterministic layout detection/confirmation belongs to Plans 12–14.

## Residual Assumptions

- The read projection accepts already-valid Separate rows so ordering and shared topology are frozen, while Plan 09 remains responsible for the separate-topology write contract and its repository/branch validation.
- `selected_layout_candidate_id` and `selected_layout_version` are intentionally null before discovery and confirmation; they are modeled future state, not a manual input or implementation stub. Plans 12–14 own their population.
- PROD-05 pull-request grouping and the remaining operational portions of PROD-03/04/06/09 continue through Plans 09, 18, 19, and 20; this plan supplies their revision-owned configuration boundary and does not claim pull-request execution.
- The application-level rate limiter already wraps the new routes; no route-specific rate policy was added because list access is database-bounded and mutations perform one bounded live branch discovery.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Bug] Preserved complete reusable repository fixture identity**
- **Found during:** Task 2 RED and Task 3 collision fixtures
- **Issue:** Truncated or reused repository slugs could collapse distinct UUID fixtures and weaken repository-reuse and collision evidence.
- **Fix:** Derived fixture slugs from the complete UUID and retained distinct collision repositories without changing assertions.
- **Files modified:** `backend/tests/unit/services/test_mappings.py`, `backend/tests/api/test_admin_mappings.py`
- **Committed in:** `5beb15d`, `0465650`

**2. [Rule 2 - Missing Critical Contract] Synchronized canonical OpenAPI and the generated TypeScript client**
- **Found during:** Task 3 OpenAPI drift gate
- **Issue:** The runtime routes existed while the checked-in operation/status contract and generated client still represented the previous surface.
- **Fix:** Froze exact operations and schemas in the OpenAPI test, regenerated the canonical schema/client, and proved no delete operation exists.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`, `frontend/openapi.json`, `frontend/src/api/client/index.ts`, `frontend/src/api/client/sdk.gen.ts`, `frontend/src/api/client/types.gen.ts`
- **Committed in:** `2e1fabb`, `8b5c3c9`

**3. [Rule 1 - Regression] Admitted only the approved mapping subresources in the product surface assertion**
- **Found during:** Full randomized backend regression
- **Issue:** A pre-existing exact product-path allowlist rejected the newly approved candidate mapping subresources despite their guarded contract.
- **Fix:** Extended the assertion only for mapping collection/detail and retained its negative publish-shortcut protection.
- **Files modified:** `backend/tests/api/test_admin_products.py`
- **Committed in:** `654cdfd`

**4. [Rule 2 - Missing Critical Evidence] Closed candidate, cursor, dependency, and corruption branches with mutation proof**
- **Found during:** Changed-line coverage and mutation gates
- **Issue:** The planned behavioral suite left malformed canonical cursor shapes, unavailable candidates/discovery, corrupt stored topology, and bounded error projection without complete executable evidence.
- **Fix:** Added focused edge tests, reached 100% changed-line branch coverage, added a fail-closed negative-controlled mutation verifier, and killed all 9 reviewed mutants.
- **Files modified:** `backend/tests/unit/services/test_mappings.py`, `backend/tests/api/test_admin_mappings.py`, `tools/verify_mapping_api_mutants.py`
- **Committed in:** `d9730e2`, `b50d29e`, `f3ef504`

## Authentication Gates

None.

## Known Stubs

None. Optional selected-layout fields are deliberate pre-detection domain state owned by Plans 12–14, and the Separate write path is an explicit Plan 09 boundary rather than an incomplete Plan 08 handler.

## Issues Encountered

- The first full randomized run exposed the stale product-path assertion; after its focused correction, the identical seed passed 433/433 on the final surface.
- One initial mutation variant created a pagination cycle and timed out rather than failing by assertion. It was replaced with an equivalent deterministic topology-order fault; the final checker completes normally and kills 9/9 by assertion.
- Context7 was unavailable both as MCP and local `ctx7` CLI. No dependency API was introduced or changed, so implementation followed the approved project contracts and locked local versions without installing unreviewed tooling.
- `npm audit` continues to report the pre-existing moderate `qs` advisory through development-only Stryker tooling. The high-severity gate passes and the unchanged advisory remains in `deferred-items.md` for reviewed upstream remediation.

## Next Phase Readiness

- Plan 09 can add Separate write mutation against the shared mapping identity and the already-proven exact list projection/order.
- Plans 12–14 can populate the existing selected layout candidate UUID/version only through deterministic discovery and confirmation; manual layout input remains closed.
- Plan 18 can consume the canonical generated mapping client for administrator UI without inventing a parallel lifecycle or client-side ordering authority.
- No authentication gate, dependency change, open verification, runtime container, or generated artifact blocks continuation.

## TDD Gate Compliance

- RED precedes GREEN for both behavior-adding tasks (`0f6fcb8` → `baf5ccb`, `77eb4fb` → `46a2fe6`).
- Task 3 has a distinct behavior-preserving REFACTOR commit (`480bc9e`); Task 2 had no justified refactor and therefore no empty commit.
- Every exact RED/GREEN/REFACTOR command is recorded above, and all final focused commands pass unchanged.

## Self-Check: PASSED

All eight key created artifacts, this summary, and all thirteen task/evidence commits were found before planning state was advanced.
