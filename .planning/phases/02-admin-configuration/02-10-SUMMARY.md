---
phase: 02-admin-configuration
plan: 10
subsystem: product-publication-api
tags: [fastapi, sqlalchemy, postgresql, concurrency, openapi, tdd]

requires:
  - phase: 02-admin-configuration
    plan: 02
    provides: Stable product UUIDs with immutable active and editable candidate revisions
  - phase: 02-admin-configuration
    plan: 08
    provides: Revision-owned mapping configuration and selected-layout state
  - phase: 02-admin-configuration
    plan: 09
    provides: Closed Direct/Separate mapping topology and target configuration
provides:
  - Product-row-lock publication authority with one atomic active-pointer swap
  - Fail-closed ordered publication blockers including absent preview confirmation
  - Administrator-only publish, deactivate, and reactivate lifecycle API
  - Canonical OpenAPI and generated TypeScript lifecycle operations
affects: [02-14-preview-confirmation, 02-18-admin-ui, 02-20-phase-gauntlet]

actuals:
  tokens: 50822
  tasks: 2
  commits: 11

tech-stack:
  added: []
  patterns:
    - Product row lock is the sole publication and operational lifecycle linearization point
    - Closed ordered blocker vocabulary is projected unchanged through bounded HTTP 409 responses
    - Successful lifecycle responses re-read the committed product projection before returning

key-files:
  created:
    - backend/src/verboflex/services/publication.py
    - backend/tests/integration/test_product_publication.py
    - tools/verify_product_publication_mutants.py
  modified:
    - backend/src/verboflex/schemas/admin_products.py
    - backend/src/verboflex/api/v1/routes/admin_products.py
    - backend/tests/api/test_admin_products.py
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json
    - frontend/src/api/client/index.ts
    - frontend/src/api/client/sdk.gen.ts
    - frontend/src/api/client/types.gen.ts

key-decisions:
  - "Use the Product row lock as the sole publication, deactivation, and reactivation linearization point."
  - "Keep absent preview confirmation as the explicit `preview_confirmation_required` blocker until Plan 02-14 supplies the digest predicate."
  - "Project publication blockers as one closed ordered 409 vocabulary, while stale identities and versions use an empty-blocker lifecycle conflict."
  - "Return lifecycle success only from a fresh post-commit product projection; provider writes and canonical translation mutations remain absent."

patterns-established:
  - "Atomic publication: validate the complete candidate graph, mark the candidate published, swap the active pointer, clear the candidate pointer, and activate in one transaction."
  - "Operational suspension: deactivation changes only Product.is_active and preserves both revision graphs and every mapping."
  - "Fail-closed lifecycle API: administrator authority precedes service access and every rejection preserves the durable graph."

requirements-completed: [PROD-01, PROD-08]

coverage:
  - id: D1
    description: "Concurrent publication has one atomic winner, equal retry is idempotent, and stale writers leave the graph unchanged."
    requirement: PROD-01
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_product_publication.py#test_product_lock_linearizes_publish_equal_retry_and_stale_writer"
        status: pass
      - kind: other
        ref: "tools/verify_product_publication_mutants.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Missing mappings, invalid topology or targets, absent layout, and absent preview confirmation block publication without mutating active or candidate state."
    requirement: PROD-08
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_product_publication.py#test_closed_blockers_leave_active_and_candidate_graphs_unchanged"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_admin_products.py#test_admin_product_lifecycle_is_guarded_atomic_and_preview_fail_closed"
        status: pass
    human_judgment: false
  - id: D3
    description: "Only active administrators can publish, deactivate, or reactivate through stable closed HTTP contracts."
    requirement: PROD-01
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_products.py#test_admin_product_lifecycle_is_guarded_atomic_and_preview_fail_closed"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_openapi_contract.py#test_admin_product_openapi_is_closed_to_exact_lifecycle_operations"
        status: pass
    human_judgment: false
  - id: D4
    description: "Lifecycle routes expose no provider branch, commit, pull-request, webhook, or canonical translation write capability."
    requirement: PROD-08
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_products.py#test_product_lifecycle_surface_exposes_no_provider_or_translation_write_capability"
        status: pass
      - kind: other
        ref: "backend/tests/architecture/test_provider_boundaries.py"
        status: pass
    human_judgment: false

duration: 28min
completed: 2026-08-27
status: complete
---

# Phase 02 Plan 10: Atomic Product Publication Lifecycle Summary

**Product-row locking now publishes one fully eligible candidate atomically and exposes guarded lifecycle APIs that remain explicitly blocked until preview confirmation exists.**

## Performance

- **Duration:** 28 min, including the tracer approval handoff
- **Started:** 2026-08-27T15:30:25Z
- **Completed:** 2026-08-27T15:58:28Z
- **Tasks:** 2
- **Files modified:** 11 runtime, API, generated-client, test, and evidence artifacts
- **Actual estimate scale:** 50,822 tokens (203,289 realized diff characters / 4, truncated)

## Accomplishments

- Added a single Product-lock publication authority that gives concurrent writers one winner, preserves equal-retry idempotency, and rolls back every stale or blocked attempt.
- Added the complete ordered blocker set for mapping, target, layout, and preview eligibility; preview remains deliberately fail closed until Plan 02-14.
- Added administrator-only publish, deactivate, and reactivate routes with stable 404/409/422 behavior and post-commit active/candidate summaries.
- Preserved configuration through deactivation and required the same publication predicate for reactivation.
- Froze the canonical OpenAPI/generated client and proved 100% statement/branch coverage plus 10/10 killed publication mutants.

## Task Commits

1. **Task 1 RED: atomic publication contract** — `03cf09d` (test)
2. **Task 1 GREEN: Product-lock publication authority** — `bbc9f05` (feat)
3. **Task 2 RED: lifecycle HTTP contract** — `3274a9e` (test)
4. **Task 2 GREEN: guarded lifecycle API** — `898e609` (feat)
5. **Canonical OpenAPI RED: exact lifecycle operations** — `4ce5a4a` (test)
6. **Contract test formatting** — `fe345e0` (style)
7. **Canonical OpenAPI/client synchronization** — `8c5a47d` (chore)
8. **Lifecycle response coverage armor** — `11b4635` (test)
9. **Publication boundary coverage armor** — `fa6d947` (test)
10. **Publication mutation resistance** — `7fe063a` (test)
11. **Mutation proof formatting** — `59e97bc` (style)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 1 RED:** the exact `cd backend && uv run pytest -q tests/integration/test_product_publication.py -x` command failed before the publication authority existed (`03cf09d`).
- **Task 1 GREEN:** the unchanged command passed **7/7** after the minimal Product-lock implementation (`bbc9f05`).
- **Task 1 REFACTOR:** the unchanged command remained **7/7**; no justified refactor existed, so no empty commit was created. The tracer was explicitly approved.
- **Task 2 RED:** the exact `cd backend && uv run pytest -q tests/api/test_admin_products.py -x` command failed on exactly the three missing lifecycle routes (`3274a9e`).
- **Task 2 GREEN:** the unchanged command passed **11/11** after the thin guarded routes and closed schemas landed (`898e609`).
- **Task 2 REFACTOR:** the unchanged command remained **11/11**; no behavior-preserving production refactor was warranted.
- **Final plan proof:** `cd backend && uv run pytest -q tests/integration/test_product_publication.py tests/api/test_admin_products.py -x` passes **20/20** after evidence armor.

## Gauntlet Evidence

- Focused publication, lifecycle, and canonical OpenAPI suite: **31 passed**.
- Full randomized backend regression at seed `4`, with PostgreSQL 18 plus an isolated Redis 7 and Celery solo worker: **458 passed in 30.77s**.
- Reversible migrations, architecture boundaries, and canonical OpenAPI: **20 passed**.
- Ruff lint passed; Ruff formatting reports **109 files already formatted**.
- mypy reports **69 source/evidence files with no issues**.
- Plan production coverage is **100% statements (248/248)** and **100% branches (52/52)**; differential coverage from `03cf09d^` is **100% (163/163 changed production lines)**.
- Mutation checker negative control reached its failure path; baseline passed; **10/10 mutants were killed** across fail-closed preview, identity/version conflicts, eligibility, deactivation/reactivation, RBAC, closed schema, and blocker projection.
- Frontend canonical API drift, TypeScript, ESLint, Prettier, Vitest **75/75**, and Vite production build all passed; Vite transformed **1,948 modules**.
- `uv lock --check` resolved **112 packages**; this plan added no dependency and changed no lockfile.
- `pip-audit` found **no known Python vulnerabilities**; only the local non-PyPI `verboflex` package was skipped. The dependency license inventory completed successfully.
- `npm audit --audit-level=high` passed. The pre-existing moderate `qs` advisory in development-only Stryker tooling remains deferred; this plan changed no JavaScript dependency graph.
- `detect-secrets` returned **0 findings** across all changed source, tests, generated contracts, and mutation evidence.

## API and Security Contract Review

- All lifecycle operations use the existing database-backed bearer/admin dependency; anonymous and viewer requests fail before service mutation.
- Product UUID, candidate/active revision UUID, and expected version are explicit request authority. Stale identities and versions return the same bounded lifecycle conflict.
- Blocked publication returns the complete stable ordered blocker set without provider diagnostics, stack data, or partial graph changes.
- No lifecycle request or response contains provider credentials, repository write controls, raw source, canonical translations, commits, pull requests, or webhooks.
- Successful responses are built from a fresh product read after the transaction commits, so the browser never receives a speculative active summary.

## Decisions Made

- Product row locking remains the one linearization point for publication, deactivation, and reactivation rather than introducing another lock or lifecycle service.
- Preview confirmation is not administratively bypassable: the default predicate returns false and the API reports `preview_confirmation_required` until Plan 02-14 wires current digest confirmation.
- Stable blocker conflicts and stale identity/version conflicts share HTTP 409 but retain distinct closed payloads: ordered blockers versus an empty blocker list.
- Deactivation is configuration-preserving and idempotent; reactivation validates the exact published revision and uses the same eligibility predicate.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Contract] Synchronized canonical OpenAPI and the generated TypeScript client**
- **Found during:** Task 2 canonical consumer verification
- **Issue:** The existing contract deliberately prohibited a publication route and the checked-in schema/client did not include the three approved lifecycle operations.
- **Fix:** Froze exact operation IDs, response statuses, request/response schemas, blocker vocabulary, and capability exclusions, then regenerated the canonical client.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`, `frontend/openapi.json`, `frontend/src/api/client/index.ts`, `frontend/src/api/client/sdk.gen.ts`, `frontend/src/api/client/types.gen.ts`
- **Verification:** Backend OpenAPI tests, frontend API drift, type, lint, test, and build gates all pass.
- **Committed in:** `4ce5a4a`, `8c5a47d`

**2. [Rule 2 - Missing Critical Evidence] Closed publication branches and added reproducible mutation proof**
- **Found during:** Coverage and mutation gauntlet
- **Issue:** Planned happy-path evidence did not execute every corruption, stale-retry, and route-projection branch or prove high-risk assertions detected regressions.
- **Fix:** Added meaningful guard/response tests and a negative-controlled ten-mutant verifier.
- **Files modified:** `backend/tests/integration/test_product_publication.py`, `backend/tests/api/test_admin_products.py`, `tools/verify_product_publication_mutants.py`
- **Verification:** Production statement/branch and differential coverage are 100%; all 10 mutants are killed.
- **Committed in:** `11b4635`, `fa6d947`, `7fe063a`

---

**Total deviations:** 2 auto-fixed (2 missing critical contract/evidence requirements).
**Impact on plan:** Both additions close consumer and evidence gaps without changing the approved publication architecture, provider capability boundary, or dependency graph.

## Issues Encountered

- The first full randomized harness supplied `VERBOFLEX_REDIS_URL` but not the distinct `VERBOFLEX_TEST_CELERY_REDIS_URL` consumed by two worker smoke tests, so 456 tests passed and two correctly failed against the default closed port. After binding both variables to the isolated Redis/worker, the identical seed passed 458/458. No product change was required.
- Ruff was initially invoked with a path that resolved outside the repository and then with the wrong configuration root for the evidence script. The canonical backend config was applied and the final lint/format/type gates passed.
- The ephemeral Celery worker was warm-stopped and the plan-owned Redis container was stopped and automatically removed after verification; no temporary runtime remains.

## Authentication Gates

None. The Task 1 tracer approval was normal planned flow and required no credential disclosure.

## Known Stubs

None. `fail_closed_preview_confirmation` is the approved security gate owned by Plan 02-14, not an unfinished bypass: it deliberately prevents publication and reactivation until a current preview digest exists.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: authorization | backend/src/verboflex/api/v1/routes/admin_products.py | Three new administrator lifecycle endpoints extend the HTTP trust boundary; the shared database-backed admin dependency and no-mutation 401/403 tests mitigate it. |

## User Setup Required

None - no dependency, credential, provider write scope, or external service configuration was added.

## Next Phase Readiness

- Plan 02-11 can schedule durable preview work against candidate revisions while this publication authority remains fail closed.
- Plan 02-14 can replace only the confirmation predicate with current digest authority; publication mechanics, blocker vocabulary, and API contracts are already frozen.
- Plan 02-18 can consume the generated lifecycle operations and render active/candidate summaries plus explicit blocker states.
- `PROD-01` and `PROD-08` remain pending in the shared requirement ledger until every sibling plan declaring them has a completed summary.

## TDD Gate Compliance

- Task 1 preserves RED → GREEN (`03cf09d` → `bbc9f05`) and an unchanged green REFACTOR gate.
- Task 2 preserves RED → GREEN (`3274a9e` → `898e609`) and an unchanged green REFACTOR gate.
- Both exact task commands were retained unchanged across their gates; no test assertion was weakened to reach GREEN.

## Self-Check: PASSED

- All 11 runtime, contract, generated-client, test, and evidence artifacts listed in frontmatter exist.
- All 11 task/evidence commits exist on `codex/phase-2-admin-configuration` in valid TDD order.
- Final focused, randomized regression, migration, architecture, OpenAPI, coverage, mutation, frontend, build, static, dependency, license, and secret claims were rerun after the final source/test changes.
- No tracked deletion, unresolved stub, skipped test, unrun verification, generated-client drift, temporary runtime, or unintended untracked artifact remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-27*
