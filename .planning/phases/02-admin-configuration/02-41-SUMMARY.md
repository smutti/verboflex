---
phase: 02-admin-configuration
plan: 41
subsystem: api-contract
tags: [fastapi, openapi, typescript, generated-client, revalidation, authorization]

requires:
  - phase: 02-40
    provides: Durable exact active-revision revalidation and sidecar confirmation authority
provides:
  - Four administrator-only HTTP operations for active-revision recovery
  - Closed bounded recovery schemas with exact revision, mapping, commit, generation, digest, and layout identity
  - Canonical OpenAPI and pinned generated TypeScript client exports for the recovery UI
  - Fail-closed 401, 403, 404, 409, and 503 behavior without provider-write authority
affects: [02-38, 02-42, 02-43, admin-ui, openapi, generated-client]

actuals:
  tokens: 62218
  tasks: 2
  commits: 6

tech-stack:
  added: []
  patterns:
    - Dedicated active-revision HTTP vocabulary over shared internal preview-job persistence
    - Canonical backend OpenAPI as the sole source for generated frontend functions and types
    - Complete compare identity at create and confirmation boundaries

key-files:
  created: []
  modified:
    - backend/src/verboflex/api/v1/routes/admin_previews.py
    - backend/src/verboflex/api/v1/routes/admin_products.py
    - backend/src/verboflex/schemas/admin_products.py
    - backend/src/verboflex/schemas/previews.py
    - backend/tests/api/test_openapi_contract.py
    - backend/tests/integration/test_preview_jobs.py
    - frontend/openapi.json
    - frontend/src/api/admin-client-contract.test.ts
    - frontend/src/api/client/index.ts
    - frontend/src/api/client/sdk.gen.ts
    - frontend/src/api/client/types.gen.ts

key-decisions:
  - "The public recovery contract uses active_revision terminology even where the compatibility service record retains candidate-named storage fields."
  - "Every recovery route uses the existing bearer/admin dependency; exact stale identity is projected as a bounded 409 and provider unavailability as a bounded 503."
  - "All four TypeScript operations and their public barrel exports are regenerated from canonical OpenAPI with @hey-api/openapi-ts 0.99.0; generated files are never hand-edited."
  - "Recovery remains read-only toward Bitbucket and returns neither source contents, credentials, nor raw provider responses."

patterns-established:
  - "Boundary vocabulary: translate internal compatibility names and error codes exactly once at the active-revision API projection."
  - "Generated authority: export backend OpenAPI, run the pinned generator, then require api:check to produce a zero diff."

requirements-completed: [PROD-01, PROD-08, PROD-09, BITB-01, BITB-04, UI-03]

coverage:
  - id: D1
    description: Administrator recovery eligibility, create, get, and confirmation bind one exact inactive published revision while stale and unauthorized requests fail closed.
    requirement: PROD-09
    verification:
      - kind: integration
        ref: backend/tests/integration/test_preview_jobs.py::test_active_revision_revalidation_api_is_admin_only_exact_and_read_only
        status: pass
    human_judgment: false
  - id: D2
    description: The distributed OpenAPI contract exposes four unique operations with closed active-revision schemas and bounded error responses.
    requirement: BITB-04
    verification:
      - kind: contract
        ref: backend/tests/api/test_openapi_contract.py (13 passed)
        status: pass
    human_judgment: false
  - id: D3
    description: The frontend consumes only pinned generated functions and types with no OpenAPI or client drift.
    requirement: UI-03
    verification:
      - kind: contract
        ref: frontend/src/api/admin-client-contract.test.ts (11 passed) and npm run api:check
        status: pass
    human_judgment: false
  - id: D4
    description: Every changed backend production branch is covered and the preview authority remains mutation-sensitive.
    requirement: PROD-08
    verification:
      - kind: other
        ref: diff-cover 9ea3706...HEAD --branch-coverage (69/69 lines)
        status: pass
      - kind: other
        ref: tools/verify_preview_job_mutants.py (16/16 killed)
        status: pass
    human_judgment: false

duration: 3h 54m
completed: 2026-08-31
status: complete
---

# Phase 02 Plan 41: Active Revision Recovery API and Generated Client Summary

**Four admin-only, exact-identity active-revision recovery operations now flow from FastAPI through canonical OpenAPI into a pinned generated TypeScript client, without provider writes or sensitive payloads.**

## Performance

- **Duration:** 3h 54m
- **Started:** 2026-08-31T13:50:52Z
- **Completed:** 2026-08-31T17:44:41Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Exposed eligibility, job creation, job inspection, and confirmation for one exact inactive published revision under the existing bearer/admin boundary.
- Required complete optimistic identity across revision/version, mapping, repository-side commits, provider generation, preview digest, and layout candidate; every drift returns a bounded conflict and cannot produce usable evidence.
- Kept the recovery namespace distinct from candidate preview vocabulary while reusing the durable read-only service authority implemented in Plan 02-40.
- Exported the real backend OpenAPI and regenerated the TypeScript SDK, types, and public barrel exclusively through the pinned generator.
- Proved 100% branch-aware coverage across all changed backend production lines, 16/16 killed preview mutants, deterministic generated-client drift, and zero provider-write or secret-bearing surface.

## Task Commits

1. **Task 1 RED: require exact admin recovery routes** - `9246664` (test)
2. **Task 1 GREEN: expose exact active-revision API** - `ca04c75` (feat)
3. **Task 2 RED: require generated recovery contract** - `328694f` (test)
4. **Task 2 GREEN: export OpenAPI and generate client** - `7ec1fd4` (feat)
5. **Assurance: close stale and duplicate-role branch proofs** - `09d62cf` (test)
6. **Task 1 REFACTOR: narrow recovery error boundary** - `8862930` (refactor)

## Files Created/Modified

- `backend/src/verboflex/api/v1/routes/admin_previews.py` - Adds create/get/confirm active-revision resources, exact confirmation comparison, bounded error translation, and active public projections.
- `backend/src/verboflex/api/v1/routes/admin_products.py` - Adds read-only reactivation eligibility for one exact published revision.
- `backend/src/verboflex/schemas/admin_products.py` - Defines bounded eligibility and per-mapping currentness responses.
- `backend/src/verboflex/schemas/previews.py` - Defines closed active-revision job and confirmation request/response schemas.
- `backend/tests/integration/test_preview_jobs.py` - Proves 401/403/404/409/503, exact identity, duplicate-role denial, success, graph immutability, secret absence, and zero provider writes.
- `backend/tests/api/test_openapi_contract.py` - Freezes operation IDs, methods, paths, required fields, closed schemas, and active-only vocabulary.
- `frontend/openapi.json` - Canonical exported backend contract.
- `frontend/src/api/client/index.ts` - Generated public barrel for the four new functions and types.
- `frontend/src/api/client/sdk.gen.ts` - Generated request functions with exact paths, methods, bearer security, and response/error maps.
- `frontend/src/api/client/types.gen.ts` - Generated active-revision data, response, and error types.
- `frontend/src/api/admin-client-contract.test.ts` - Freezes generated runtime functions, paths, methods, symbols, and the 34-operation Phase 2 inventory.

## Decisions Made

- Kept candidate and active namespaces separate at the public boundary. The adapter renames compatibility storage fields and maps the internal `stale_candidate` code to `stale_active_revision` without changing Plan 02-40 persistence.
- Used the existing admin principal dependency on all four routes and delegated exclusively to the Plan 02-40 background-job/service authority.
- Required duplicate repository-side roles to fail closed during both job creation and confirmation, preventing dictionary normalization from hiding conflicting caller evidence.
- Accepted `frontend/src/api/client/index.ts` as a required generated artifact because the pinned generator owns the entire client directory and `api:check` validates that directory as one deterministic unit.

## API Safety Review

- **Authentication/authorization:** every route requires a valid bearer token and the admin role; explicit 401 and 403 cases pass.
- **Compatibility:** all operations are additive and use unique operation IDs; existing candidate routes and schemas remain unchanged.
- **Idempotency/blast radius:** create reuses the exact current job authority, confirmation is exact and replay-safe, and response collections are bounded.
- **Sensitive data:** closed response schemas omit tokens, ciphertext, provider diagnostics, source bytes, repository contents, and raw provider responses.
- **Provider authority:** no Bitbucket write operation, candidate publication, or published-graph mutation surface was added.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Preserved the generator-owned public client barrel**
- **Found during:** Task 2 canonical client generation.
- **Issue:** The pinned generator deterministically updates `frontend/src/api/client/index.ts`, although the plan's expected generated diff named only SDK and type files. Excluding it would hide the new exports and make `api:check` fail.
- **Fix:** Kept the generated barrel output untouched and verified repeat generation produces zero diff.
- **Files modified:** `frontend/src/api/client/index.ts`
- **Verification:** `npm run api:check` passed post-commit.
- **Committed in:** `7ec1fd4`

**2. [Rule 3 - Blocking] Closed branch-aware recovery API assurance gaps**
- **Found during:** Post-Task 2 changed-source coverage.
- **Issue:** Initial diff coverage was 61/69 lines (88%); stale eligibility, duplicate commit roles, and one overly broad defensive error branch were not covered.
- **Fix:** Added exact 409 assertions for stale eligibility and duplicate roles in create/confirmation, then narrowed the error translator to its three declared domain failures.
- **Files modified:** `backend/tests/integration/test_preview_jobs.py`, `backend/src/verboflex/api/v1/routes/admin_previews.py`
- **Verification:** Relevant regression 85/85 passed and branch-aware diff coverage reached 69/69 lines (100%).
- **Committed in:** `09d62cf`, `8862930`

---

**Total deviations:** 2 auto-fixed (2 Rule 3 blocking deterministic-assurance repairs)
**Impact on plan:** The generated surface gained only the generator-owned public barrel, and backend changes only strengthened exact fail-closed proof. No dependency, lockfile, provider-write surface, coverage exclusion, or mutation threshold changed.

## Verification

- Backend relevant regression: **85/85 passed** across preview integration and OpenAPI contract modules.
- Task 1 tracer: exact admin-only recovery node passed, including 401/403/404/409/503, stale identity, duplicate roles, graph immutability, and absence of a translations table.
- Backend OpenAPI: **13/13 passed**, including unique operation IDs, exact methods/paths, closed schemas, error mappings, and forbidden-field scans.
- Frontend generated contract: **11/11 passed**; `npm run api:check` regenerated all artifacts with **zero diff**.
- Coverage: changed backend production scope is **69/69 lines, 100% branch-aware** against Plan 02-41 base `9ea3706`.
- Mutation: targeted preview authority score is **16/16 killed**.
- Quality: mypy passed 81 source files; Ruff lint passed and 133 backend files were canonically formatted; frontend typecheck, ESLint, Prettier, and production build passed.
- Supply chain: `uv lock --check` passed; pip-audit found no known vulnerabilities; npm high-severity audit passed and the production moderate audit found zero vulnerabilities. Two already-known moderate findings remain dev-only.
- Secrets: detect-secrets scanned all handwritten changed source/test files with **0 findings**.
- Dependency integrity: `frontend/package.json` and `frontend/package-lock.json` remained byte-for-byte unchanged.

## TDD Gate Compliance

- Task 1: RED `9246664` precedes GREEN `ca04c75`; the later exact-boundary REFACTOR is `8862930`.
- Task 2: RED `328694f` precedes GREEN `7ec1fd4`.
- The RED failures were the missing 404 recovery resources and missing generated symbols/OpenAPI operations respectively; both became green only after implementation and canonical generation.

## Issues Encountered

- The first pre-commit `api:check` correctly showed the intended generated diff against HEAD. The authoritative post-GREEN run regenerated the same files and exited zero.
- Vite retains its pre-existing non-blocking warning for a JavaScript chunk larger than 500 kB; this plan adds no handwritten frontend runtime bundle.

## User Setup Required

None - no new package, credential, provider scope, or runtime service configuration is required.

## Next Phase Readiness

- Plan 02-42 can implement the administrator recovery UI against four real generated operations and dedicated active-revision types.
- Recovery remains constrained to read-only Bitbucket access and exact published-revision evidence.
- WR-03 through WR-07 remain OPEN non-blocking warnings as required by the phase plan; this plan does not claim to resolve them.

## Known Stubs

None.

## Authentication Gates

None.

## Self-Check: PASSED

- All eleven modified artifacts exist on disk.
- All six RED, GREEN, assurance, and refactor commits exist in git history.
- Every mandatory plan verification and all final assurance reruns completed successfully.
- The tracked implementation tree was clean after deterministic regeneration; only the explicitly preserved untracked workspace artifacts remain.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-31*
