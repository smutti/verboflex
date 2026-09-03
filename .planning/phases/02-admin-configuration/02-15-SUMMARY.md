---
phase: 02-admin-configuration
plan: 15
subsystem: generated-api-client
tags: [openapi, typescript, hey-api, vitest, contract-testing, tdd]

requires:
  - phase: 02-14
    provides: Complete Phase 2 admin HTTP surface and synchronized canonical OpenAPI/client outputs
provides:
  - Executable proof that Phase 2 admin calls use generated types and the established in-memory bearer transport
  - Exact stable and unique operation IDs for all 29 Phase 2 admin routes
  - Deterministic pinned OpenAPI/client drift enforcement with immutable dependency manifests
affects: [02-16, 02-17, 02-18, 02-19, 02-20, frontend-admin-ui]

actuals:
  tokens: 3104
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - FastAPI OpenAPI remains the sole wire-contract authority and generated client files are never hand-maintained
    - Every Phase 2 admin operation ID is frozen as a unique path-method mapping before UI consumption

key-files:
  created:
    - frontend/src/api/admin-client-contract.test.ts
  modified: []

key-decisions:
  - "Keep the existing pinned api:generate and api:check scripts unchanged; deterministic regeneration plus git diff is the drift authority."
  - "Freeze the complete set of 29 Phase 2 admin operation IDs and require uniqueness, not only the first user-list tracer operation."
  - "Treat the already-current Plan 02-14 generated outputs as canonical regression armor: no generated or dependency file needed a committed edit."

patterns-established:
  - "Generated boundary contract: exercise one real generated call, assert exact transport/auth behavior, and inspect the canonical schema for forbidden secret/provider-write surfaces."
  - "Drift gate: regenerate with the pinned toolchain and fail on any OpenAPI or generated-client diff while package manifests remain byte-identical."

requirements-completed: [UI-03]

coverage:
  - id: D1
    description: Phase 2 frontend code can call the generated admin user-list operation with its exact response type and an in-memory bearer token.
    requirement: UI-03
    verification:
      - kind: unit
        ref: frontend/src/api/admin-client-contract.test.ts#calls the generated user list with its exact response type and an in-memory bearer
        status: pass
    human_judgment: false
  - id: D2
    description: All 29 Phase 2 admin operations have exact stable unique IDs and expose no forbidden credential or provider-write surface.
    requirement: UI-03
    verification:
      - kind: unit
        ref: frontend/src/api/admin-client-contract.test.ts#freezes every Phase 2 admin operation ID
        status: pass
      - kind: unit
        ref: frontend/src/api/admin-client-contract.test.ts#keeps list and provider-facing admin schemas free of credential material
        status: pass
    human_judgment: false
  - id: D3
    description: Canonical OpenAPI and generated TypeScript outputs cannot drift silently and dependency manifests remain immutable.
    requirement: UI-03
    verification:
      - kind: other
        ref: cd frontend && npm run api:check && git diff --quiet -- package.json package-lock.json
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-08-28
status: complete
---

# Phase 02 Plan 15: Canonical Generated Admin Client Summary

**The canonical TypeScript boundary now proves in-memory bearer transport, freezes all 29 Phase 2 admin operation IDs, rejects secret/provider-write leakage, and fails deterministically on generated drift.**

## Performance

- **Active duration:** 18 min
- **Elapsed:** 10h01m including the approved tracer checkpoint
- **Started:** 2026-08-27T21:13:15Z
- **Completed:** 2026-08-28T07:13:53Z
- **Tasks:** 2
- **Files changed:** 1 test contract; canonical generated outputs and dependency manifests remained unchanged

## Accomplishments

- Exercised `listAdminUsers` through the generated SDK with its exact response type, exact GET URL, and bearer authority held only in request memory.
- Froze every Phase 2 admin path/method to one exact operation ID and proved all 29 IDs are unique.
- Rejected forbidden credential fields, raw provider bodies, provider write endpoints, and handwritten admin-user wire duplicates.
- Kept `api:generate` and `api:check` unchanged and demonstrated that the drift command exits non-zero for controlled schema drift.
- Preserved `package.json`, `package-lock.json`, OpenAPI, and all generated client outputs byte-for-byte.

## Task Commits

1. **Task 1: Generate and call one Phase 2 admin operation** — `f7d9b04` (`test`)
2. **Task 2: Lock deterministic generated-client drift** — `a435c32` (`test`)

The dependency plan had already regenerated the complete client. The tracer therefore used fail controls to prove non-vacuity and committed regression armor without manufacturing a generated-file change.

## Files Created/Modified

- `frontend/src/api/admin-client-contract.test.ts` — generated-call transport/type proof, closed secret/provider surface checks, handwritten-wire rejection, and the complete 29-operation ID contract.

`frontend/openapi.json`, `frontend/src/api/client/`, `frontend/package.json`, and `frontend/package-lock.json` were regenerated/checked but have no committed diff from Plan 02-14.

## Decisions Made

- The existing pinned generator/runtime remains the only client-generation path; neither scripts nor generated files were hand-maintained.
- Stable operation identity is a complete exact map across all Phase 2 admin routes, with a uniqueness assertion to prevent aliasing.
- Generated runtime coverage is boundary-focused: the tracer proves one real typed request and the canonical surface; later UI plans consume additional generated operations without creating handwritten wire types.

## Verification

- Exact Task 2 and plan command: **6/6 focused Vitest tests passed**; canonical regeneration produced no diff; both dependency manifest hashes remained unchanged.
- Randomized frontend suite (`--sequence.shuffle --sequence.seed=21515`): **81/81 tests passed**.
- Frontend static/build: TypeScript, ESLint, Prettier, canonical API drift, and Vite production build passed; **1,948 modules transformed**.
- Focused generated-boundary coverage: **193/563 lines**, **82/506 branches**, and **24/107 functions** across loaded generated/runtime modules. The realized plan diff contains only the test contract, so there are **0 changed handwritten production lines** to submit to changed-line coverage.
- Mutation/non-vacuity: **1/1 transport mutant killed** (`GET` changed to `POST`, exact assertion failed); the duplicate-wire checker also rejects its embedded known-bad interface/type fixture.
- Drift negative control: changing the backend user-list operation ID made `api:check` exit non-zero with OpenAPI and SDK diffs; canonical regeneration restored a clean tree.
- Backend randomized suite with temporary Redis/Celery (`--randomly-seed=21515`): **698/698 tests passed**.
- Focused backend contracts: architecture, migrations, and OpenAPI **21/21 passed**; live worker smoke **4/4 passed**.
- Backend static: Ruff check/format passed; MyPy passed for **81 source files**. No handwritten production code changed, so the pre-existing complexity inventory is unaffected.
- Supply chain and secrets: `uv lock --check`, `pip-audit`, production `npm audit --omit=dev`, and the audited secret policy with its negative control passed; no dependency changed.

## TDD Gate Compliance

- Task 1 produced the RED/regression commit `f7d9b04`. Because Plan 02-14 had already generated the Phase 2 operations, controlled failures established that the new test was non-vacuous; no GREEN production commit was required.
- Task 2 added the missing complete operation-ID proof in `a435c32`; the existing drift scripts were intentionally unchanged and their positive and negative paths were both exercised.

## Deviations from Plan

None - the dependent plan had already synchronized the generated boundary, so this plan added the executable contract and drift proof without unnecessary generated-file churn.

## Issues Encountered

- The first backend run had **696 passes and 2 worker-smoke failures** because the required local Redis/Celery transport was not running. Temporary isolated Redis/Celery infrastructure was started automatically; the final fresh run passed **698/698**, and the infrastructure was removed.
- The initial frontend randomization invocation used the obsolete `--seed` spelling. Vitest 4.1.11 exposes `--sequence.seed`; the corrected deterministic command passed **81/81**.

## Known Stubs

None. The changed file contains no TODO, FIXME, placeholder, skipped test, or unwired data source.

## Threat Flags

None. This plan added only executable contract tests. It introduced no endpoint, authentication path, file-access boundary, schema, dependency, or runtime capability.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-16 can build the admin navigation shell against one canonical generated API surface.
- Plans 02-17 through 02-19 can consume the exact generated user, product, repository, mapping, OAuth, preview, confirmation, and publication operations without handwritten wire duplicates.
- No blocker remains.

## Self-Check: PASSED

- `frontend/src/api/admin-client-contract.test.ts` exists and both `f7d9b04` and `a435c32` are present in repository history.
- The exact plan verification, fresh randomized frontend/backend suites, focused backend smokes, static checks, build, drift, mutation control, supply-chain audit, and secret negative control passed on the final canonical source state.
- Only the known untracked `.gsd/`, `.planning/milestone.lock`, and `graphify-out/` paths remain; none was modified or staged by this plan.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-28*
