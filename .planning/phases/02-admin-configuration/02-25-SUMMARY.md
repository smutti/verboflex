---
phase: 02-admin-configuration
plan: 25
subsystem: api
tags: [fastapi, sqlalchemy, postgresql, candidates, publication, concurrency, mutation-testing]

requires:
  - phase: 02-admin-configuration/02-24
    provides: Database-enforced product graph ownership and no-bypass published-child immutability
provides:
  - Complete active-to-candidate mapping graph clone with fresh revision, mapping, side, and target identities
  - Revision-owned candidate identity that leaves Product effective identity unchanged before publication
  - Atomic publication of metadata, identity, active pointer, candidate clear, and operational state
  - Mutation proof for clone depth, confirmation clearing, Product locking, identity isolation, and promotion fields
affects: [product-candidates, admin-product-api, publication, preview-confirmations, phase-02-verification]

actuals:
  tokens: 11820
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - Product row locks serialize candidate creation and publication while equal retries converge idempotently
    - Candidate revisions own editable identity until a single publication transaction promotes it to Product
    - Active mapping graphs clone recursively with fresh parent identities and cleared preview authority

key-files:
  created: []
  modified:
    - backend/src/verboflex/services/products.py
    - backend/src/verboflex/services/publication.py
    - backend/src/verboflex/schemas/admin_products.py
    - backend/src/verboflex/api/v1/routes/admin_products.py
    - backend/tests/api/test_admin_products.py
    - backend/tests/integration/test_product_publication.py
    - backend/tests/unit/test_product_names.py
    - tools/verify_product_api_mutants.py
    - tools/verify_product_publication_mutants.py

key-decisions:
  - "Keep candidate edit identity exclusively on ProductRevision; Product display_name/name_key remain the effective published identity until publication commits."
  - "Clone every active mapping, repository side, and allowed target with fresh graph identities while retaining configuration values and selected layout but clearing all preview confirmation authority."
  - "Publish candidate metadata, canonical unique identity, active pointer, candidate clear, and activation beneath one Product lock and one transaction without any Plan 24 trigger bypass."

patterns-established:
  - "Recursive candidate copy: eager-load the complete active graph, remap parent identities once, and construct new child rows under the remapped mapping IDs."
  - "Atomic promotion: validate eligibility and canonical identity before ordered metadata, identity, and pointer flushes inside one transaction."

requirements-completed: [PROD-01, PROD-02, PROD-03, PROD-04, PROD-05, PROD-06, PROD-07, PROD-08]

coverage:
  - id: D1
    description: "Editing a published product creates exactly one isolated candidate with a complete, value-identical direct/separate mapping graph and no inherited preview authority."
    requirement: PROD-02
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_products.py#test_existing_product_edit_clones_complete_graph_once_and_isolates_candidate_identity"
        status: pass
      - kind: other
        ref: "tools/verify_product_api_mutants.py (13/13 killed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Candidate identity remains revision-owned until publication atomically promotes identity, metadata, graph pointers, and activation."
    requirement: PROD-01
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_product_publication.py#test_product_lock_linearizes_publish_equal_retry_and_stale_writer"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_product_publication.py#test_fault_at_publication_identity_or_pointer_flush_rolls_back_every_step"
        status: pass
      - kind: other
        ref: "tools/verify_product_publication_mutants.py (25/25 killed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Publication rejects missing, partial, stale, noncanonical, nonunique, or unconfirmed candidates and preserves Plan 24 published-child immutability."
    requirement: PROD-08
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_product_publication.py#test_normalized_name_conflict_rolls_back_identity_metadata_and_pointers"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_product_publication.py#test_new_active_mapping_children_remain_database_immutable_after_publication"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_product_publication.py#test_closed_blockers_leave_active_and_candidate_graphs_unchanged"
        status: pass
    human_judgment: false

duration: 21min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 25: Complete Candidate Clone and Atomic Identity Publication Summary

**Published-product edits now create one fully isolated deep-cloned candidate, and publication promotes its canonical identity and complete graph atomically under Product-row authority.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-08-29T17:03:33Z
- **Completed:** 2026-08-29T17:24:57Z
- **Tasks:** 2
- **Files modified:** 9 implementation, test, and assurance files
- **Actual estimate scale:** 11,820 tokens (47,280 realized diff characters / 4)

## Accomplishments

- Deep-cloned every active direct/separate mapping, repository side, and allowed target into one candidate using distinct revision and mapping-owned identities while preserving all configuration values and selected layout.
- Cleared confirmed preview job, digest, actor, and timestamp authority from every cloned mapping; zero-mapping candidates remain repeatable but publication-ineligible.
- Kept Product effective identity and the entire active graph byte-stable during edits, with identical repeated and concurrent saves converging on one candidate beneath a Product lock.
- Published canonical unique candidate identity, revision metadata, active pointer, candidate clear, and activation in one transaction with fault rollback, equal-retry idempotency, and Plan 24 trigger enforcement.
- Expanded fail-closed mutation assurance to kill every reviewed clone-depth, lock, identity-isolation, confirmation, eligibility, and promotion-field mutant.

## Task Commits

The plan-level TDD gates and final assurance were committed atomically:

1. **Task 1 RED: complete candidate clone contracts** — `f0b7d4f` (test)
2. **Task 1 GREEN: deep-clone editable product candidates** — `a16e535` (feat)
3. **Task 2 RED: atomic identity promotion contracts** — `9609166` (test)
4. **Task 2 GREEN: atomic candidate identity and graph publication** — `87514b3` (feat)
5. **Plan assurance: clone and publication mutation proof** — `fa91b7c` (test)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 1 RED:** the focused clone/concurrency contract failed because identical concurrent edits produced `[200, 409]` instead of `[200, 200]`; the full API contract also showed the candidate response lacked revision-owned `name`.
- **Task 1 GREEN:** `tests/api/test_admin_products.py -x` passed 15/15 with complete graph cloning, zero-mapping behavior, identity isolation, repeatability, and concurrency assertions.
- **Task 2 RED:** the publish-time normalized-name conflict contract failed because publication neither raised the bounded identity conflict nor proved full rollback.
- **Task 2 GREEN:** publication/name tests initially passed 39/39; the final assurance-enhanced suite passed 40/40, including three injected flush failures and direct SQL/ORM published-child rejection.
- No refactor commit was needed; changed-file formatting, lint, typing, and mutation gates are green.

## Verification and Acceptance Evidence

- Required Task 1 API verification: **15 passed**.
- Required Task 2 publication/name verification: **40 passed**.
- Product API mutation proof: negative control passed and **13/13 mutants killed**.
- Product publication mutation proof: negative control passed and **25/25 mutants killed**.
- Static/security gates: repository-wide Ruff lint passed; all nine Plan 02-25 files are Ruff-formatted; mypy passed across 81 source files; detect-secrets found no results; `git diff --check` passed.
- Acceptance covers complete direct/separate/side/target cloning, fresh identities, confirmation clearing, Product identity immutability, one-candidate convergence, empty-graph blocking, all-mapping currentness, publish uniqueness, idempotency, concurrency, fault rollback, and no Plan 24 bypass.

## Files Created/Modified

- `backend/src/verboflex/services/products.py` — revision-owned candidate identity, locked idempotent edits, and complete recursive active-graph cloning.
- `backend/src/verboflex/services/publication.py` — canonical identity/uniqueness validation and ordered atomic identity plus graph promotion.
- `backend/src/verboflex/schemas/admin_products.py` — candidate revision identity in the closed administrator response.
- `backend/src/verboflex/api/v1/routes/admin_products.py` — candidate revision name projection through the existing protected edit route.
- `backend/tests/api/test_admin_products.py` — complete graph, identity, empty mapping, repeat, and concurrent edit contracts.
- `backend/tests/integration/test_product_publication.py` — promotion, noncanonical identity, fault, lock, activation, and immutable-child contracts.
- `backend/tests/unit/test_product_names.py` — candidate identity snapshots and active revision immutability coverage.
- `tools/verify_product_api_mutants.py` — 13 fail-closed API/clone mutation subjects.
- `tools/verify_product_publication_mutants.py` — 25 fail-closed confirmation, publication, identity, and lifecycle mutation subjects.

## Decisions Made

- Candidate edits compare and mutate `ProductRevision.display_name/name_key`; `Product.display_name/name_key` remain the effective published identity until atomic publication.
- The clone copies all durable configuration and selected layout, but no preview job row or confirmation field is reusable as candidate currentness authority.
- Equal input is checked after acquiring the Product lock and before stale-version rejection, so concurrent identical saves return the same candidate while divergent stale writers remain bounded conflicts.
- Publication uses existing Plan 24 database triggers as authority; there is no session flag, role exception, trigger disable, or alternate write path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Expanded mutation proof to cover the complete Plan 02-25 assurance boundary**
- **Found during:** Plan-level verification after Task 2
- **Issue:** Existing mutation scripts covered older candidate/version and preview predicates but could not prove full clone depth, confirmation clearing, Product locking, canonical candidate identity, or every atomic promotion field; two publication subjects had also drifted from current source formatting.
- **Fix:** Added exact fail-closed clone and publication mutants, a canonical durable identity rollback assertion, and inactive-to-active publication coverage. Equivalent mutants whose behavior remained protected by the database constraint or SQLAlchemy autoflush were replaced with observable authority-boundary mutants.
- **Files modified:** `backend/tests/integration/test_product_publication.py`, `tools/verify_product_api_mutants.py`, `tools/verify_product_publication_mutants.py`
- **Verification:** Negative controls passed; API mutation score is 13/13 and publication mutation score is 25/25.
- **Committed in:** `fa91b7c`

---

**Total deviations:** 1 auto-fixed (1 Rule 2 missing critical)
**Impact on plan:** The additional work only completed the mutation assurance explicitly required by the plan; it introduced no runtime dependency, endpoint, schema, or broader product behavior.

## Issues Encountered

- Repository-wide `ruff format --check src tests` reports three pre-existing untouched test files outside Plan 02-25. They are recorded in `.planning/phases/02-admin-configuration/deferred-items.md`; all Plan 02-25 files pass the scoped formatting gate.
- One proposed uniqueness mutant was equivalent because PostgreSQL uniqueness plus bounded `IntegrityError` mapping preserved the same public result; one explicit-flush mutant was equivalent because the uniqueness query autoflush retained the same atomic/fault behavior. Both were replaced with observable, non-equivalent authority mutations.

## Authentication Gates

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration, migration, or dependency change is required.

## Next Phase Readiness

- Existing-product editing is now routed through a complete isolated candidate graph, and downstream administrator UI/import flows can depend on candidate identity without changing the effective Product early.
- Publication and reactivation retain full mapping/current-preview authority and Plan 24 database immutability.
- Shared `PROD-*` requirements should advance only when the requirements readiness gate confirms no later declaring plan remains incomplete.
- No Plan 02-25 checkpoint or blocker remains.

## Self-Check: PASSED

- All nine modified implementation, test, and assurance files exist.
- Both RED commits precede their GREEN commits; all five Plan 02-25 commits are reachable from the current branch.
- Both required task commands, both mutation scripts, concurrency/fault/immutability assertions, static analysis, and secret scanning pass.
- No tracked deletion, skipped Plan 02-25 test, unrun verification, known stub, dependency change, trigger bypass, or unmodeled threat surface remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
