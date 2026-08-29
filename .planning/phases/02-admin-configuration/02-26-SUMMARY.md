---
phase: 02-admin-configuration
plan: 26
subsystem: api
tags: [fastapi, sqlalchemy, bitbucket, pagination, openapi, generated-client, mutation-testing]

requires:
  - phase: 02-admin-configuration/02-21
    provides: Expiry-safe generation-bound Bitbucket credential leases
  - phase: 02-admin-configuration/02-24
    provides: Database-enforced product revision graph ownership and immutable published children
provides:
  - Read-only mapping projections for explicitly owned active or candidate product revisions
  - Exact configured-branch resolution through one safe Bitbucket detail request
  - Cursor-faithful OpenAPI and generated TypeScript contracts without provider URL exposure
affects: [product-reactivation, repository-discovery, admin-configuration-ui, phase-02-verification]

actuals:
  tokens: 53833
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - Revision-scoped reads authorize through both the Product pointer and ProductRevision owner before querying graph rows
    - Opaque branch names cross the API as required query parameters and reach exactly one encoded adapter detail request
    - Generated API artifacts are produced twice and hash-compared before the committed drift gate

key-files:
  created: []
  modified:
    - backend/src/verboflex/services/mappings.py
    - backend/src/verboflex/api/v1/routes/admin_mappings.py
    - backend/src/verboflex/services/repository_discovery.py
    - backend/src/verboflex/api/v1/routes/admin_discovery.py
    - backend/tests/api/test_admin_mappings.py
    - backend/tests/api/test_admin_discovery.py
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json
    - frontend/src/api/admin-client-contract.test.ts
    - frontend/src/api/client/sdk.gen.ts
    - frontend/src/api/client/types.gen.ts
    - tools/verify_mapping_api_mutants.py

key-decisions:
  - "Authorize revision mapping reads only when the revision is the Product's current active or candidate pointer and independently belongs to that Product; never lock, clone, or mutate the graph."
  - "Treat branch_name as a required opaque query value and call resolve_repository_branch exactly once, preserving the original spelling and commit hash without a list scan."
  - "Keep provider continuation URLs server-side while preserving deterministic application items and opaque next_cursor values through route, OpenAPI, and generated-client boundaries."

patterns-established:
  - "Owned revision projection: pointer membership and revision ownership are separate fail-closed checks before deterministic graph pagination."
  - "Exact provider lookup: server-owned repository coordinates plus opaque caller branch spelling feed one expiry-safe adapter request."

requirements-completed: [PROD-03, PROD-04, PROD-06, PROD-07, PROD-08, PROD-09, BITB-03, BITB-04, UI-03]

coverage:
  - id: D1
    description: "An administrator can read deterministic mapping pages for an explicitly owned active or candidate revision without creating a candidate or changing graph state."
    requirement: PROD-03
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_mappings.py (20 passed)"
        status: pass
      - kind: other
        ref: "tools/verify_mapping_api_mutants.py (13/13 killed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "An exact configured branch beyond the first list page, including slash, percent, Unicode, space, question-mark, hash, and reserved spellings, resolves unchanged through one safe detail request."
    requirement: BITB-03
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_discovery.py (22 passed)"
        status: pass
      - kind: other
        ref: "tools/verify_bitbucket_discovery_mutants.py (14/14 killed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "OpenAPI and the generated TypeScript client expose the two read-only operations with required branch input, cursor envelopes, bounded errors, and no provider continuation URL."
    requirement: UI-03
    verification:
      - kind: integration
        ref: "backend/tests/api/test_openapi_contract.py (11 passed)"
        status: pass
      - kind: unit
        ref: "frontend/src/api/admin-client-contract.test.ts (7 passed)"
        status: pass
      - kind: other
        ref: "npm run api:check"
        status: pass
    human_judgment: false

duration: 2h 20m
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 26: Owned Revision and Exact Branch Reads Summary

**Read-only owned-revision mapping pages and exact opaque branch lookup now reach every reactivation/discovery state through deterministic, generated, secret-free contracts.**

## Performance

- **Duration:** 2h 20m
- **Started:** 2026-08-29T17:27:40Z
- **Completed:** 2026-08-29T17:47:51Z
- **Tasks:** 2
- **Files modified:** 16 implementation, test, assurance, and generated-contract files
- **Actual estimate scale:** 53,833 tokens (215,332 realized diff characters / 4)

## Accomplishments

- Added an admin-only revision mapping projection that validates active/candidate pointer membership and independent revision ownership, then returns stable pages without locks, candidate creation, or graph mutation.
- Added a required `branch_name` exact-read operation that preserves slash, percent, Unicode, spaces, question marks, hashes, other reserved characters, and `commit_hash` through one expiry-safe adapter detail request with no list scan.
- Froze both operation IDs and bounded response contracts in OpenAPI, regenerated the TypeScript client twice with identical hashes, and retained application cursors without leaking provider continuation URLs.
- Closed the new boundary with 53 focused API/OpenAPI tests, a 106-test integration/architecture slice, and 27/27 killed mapping/discovery mutants.

## Task Commits

The plan-level RED/GREEN/REFACTOR gates were committed in order:

1. **Task 1 RED: owned revision mapping read contracts** — `eaf1cde` (test)
2. **Task 1 GREEN: owned revision mapping projection** — `90a6443` (feat)
3. **Task 2 RED: exact configured branch contracts** — `53be947` (test)
4. **Task 2 GREEN: exact configured branch resolution** — `e73a38c` (feat)
5. **REFACTOR: canonical OpenAPI/generated client and assurance alignment** — `b562efe` (refactor)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 1 RED:** `tests/api/test_admin_mappings.py -x` failed intentionally after 9 passes because the new revision route returned 404 instead of the expected authenticated contract.
- **Task 1 GREEN:** the mapping API suite passed 20/20 across active-only, candidate, wrong-product, stale-pointer, deterministic cursor, and mutation-free reads.
- **Task 2 RED:** `tests/api/test_admin_discovery.py -x` failed intentionally because the exact branch route was absent and returned 404.
- **Task 2 GREEN:** the discovery API suite passed 22/22, including the index-101 branch and exact slash/percent/Unicode/space/question-mark/hash/reserved round trips with one detail call and zero list calls.
- **REFACTOR:** canonical artifacts were generated twice with identical SHA-256 hashes; `npm run api:check` passed against the committed contract.

## Acceptance Evidence

- Required Task 1 command: **20 passed**.
- Required Task 2 command: **22 passed**.
- Combined mapping/discovery/OpenAPI slice: **53 passed**.
- Mapping/discovery/service/adapter/architecture acceptance slice: **106 passed**.
- Mapping mutation proof: baseline passed and **13/13 mutants killed**.
- Discovery mutation proof: baseline passed and **14/14 mutants killed**.
- Frontend affected suites: **41 passed**, including canonical generated-client contract **7/7**.
- Backend static gates: mypy passed across 81 source files; Ruff lint passed; all nine scoped Python files are formatted.
- Frontend static/build gates: typecheck, ESLint, Prettier, and Vite production build passed.
- Security/source gates: detect-secrets reported zero findings; `git diff --check` passed; exact routes project only bounded schemas and expose no provider URL/token/body.
- Plan success criteria are satisfied: active-only revision graphs and beyond-page branches are addressable without state creation, widened provider authority, or pagination metadata loss.

## Files Created/Modified

- `backend/src/verboflex/services/mappings.py` — shared deterministic revision graph pagination with active/candidate pointer and owner validation.
- `backend/src/verboflex/api/v1/routes/admin_mappings.py` — admin-only read projection and unchanged candidate-only mutation routes.
- `backend/src/verboflex/services/repository_discovery.py` — exact server-owned repository branch detail resolution through the existing safe adapter.
- `backend/src/verboflex/api/v1/routes/admin_discovery.py` — required bounded `branch_name` query and safe `AdminBranchResponse` projection.
- `backend/tests/api/test_admin_mappings.py` — active/candidate ownership, stale/wrong revision, cursor fidelity, and byte-stable graph assertions.
- `backend/tests/api/test_admin_discovery.py` — index-101 and exact reserved-name round trips, no-list proof, bounded failures, and OpenAPI query contract.
- `backend/tests/api/test_openapi_contract.py` — frozen operation IDs, read-only path surface, and canonical schema assertions.
- `backend/tests/integration/test_bitbucket_http_adapter.py` — current expiry-safe credential lease fixture for broad adapter regression.
- `frontend/openapi.json` and `frontend/src/api/client/` — canonical generated operations, query data, responses, and revision identity.
- `frontend/src/api/admin-client-contract.test.ts` — generated operation/read-only/cursor contract coverage.
- `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx` and `frontend/src/features/admin/products/ProductConfiguration.test.tsx` — canonical revision-name fixtures.
- `tools/verify_mapping_api_mutants.py` — current shared-revision cursor and ordering mutation subjects.

## Decisions Made

- Revision IDs are authorized by both Product pointer membership and ProductRevision ownership; accepting either fact alone would permit stale or cross-product graph reads.
- Exact branch names remain opaque data in a required query parameter and are never reconstructed from a paginated branch listing or normalized by the application.
- The safe adapter remains the only provider authority: repository origin is server-owned, the lease is expiry/generation checked, failures are bounded, and the response contains only unchanged name plus commit hash.
- Application cursors preserve stable ordering and pagination identity, while provider continuation URLs never cross the API or generated-client boundary.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Realigned the mapping mutation harness after the shared revision paginator refactor**
- **Found during:** Plan-level mapping mutation verification
- **Issue:** Two exact-source mutation subjects still targeted the candidate-only variable/indentation and could not execute against the new owned-revision paginator.
- **Fix:** Retargeted the cursor binding and primary-branch ordering subjects to the shared `revision` implementation without weakening any mutant.
- **Files modified:** `tools/verify_mapping_api_mutants.py`
- **Verification:** Baseline passed and 13/13 mutants were killed.
- **Committed in:** `b562efe`

**2. [Rule 3 - Blocking] Updated a stale Plan 21 credential-lease integration fixture**
- **Found during:** Broad 106-test acceptance slice
- **Issue:** The legacy fixture bypassed the current expiry-safe locked-row lookup and lacked a provider expiry clock, preventing the adapter regression from reaching Plan 02-26 behavior.
- **Fix:** Supplied the scalar row result, deterministic clock, unexpired access-only credential, and explicit legacy refresh-token rejection case.
- **Files modified:** `backend/tests/integration/test_bitbucket_http_adapter.py`
- **Verification:** The broad mapping/discovery/adapter/architecture slice passed 106/106.
- **Committed in:** `b562efe`

**3. [Rule 3 - Blocking] Aligned existing frontend fixtures with the canonical revision schema**
- **Found during:** Generated-client typecheck after OpenAPI synchronization
- **Issue:** Plan 25 had added required revision-owned `name`, but four older fixture objects still modeled the previous generated type.
- **Fix:** Added the product's corresponding revision name to each affected preview/configuration fixture.
- **Files modified:** `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx`, `frontend/src/features/admin/products/ProductConfiguration.test.tsx`
- **Verification:** All 41 affected frontend tests, typecheck, lint, formatting, and build passed.
- **Committed in:** `b562efe`

---

**Total deviations:** 3 auto-fixed (3 Rule 3 blocking)
**Impact on plan:** All fixes restored existing assurance/fixture compatibility with already-required contracts; no dependency, persistence schema, provider authority, or product scope was added.

## Issues Encountered

- Repository-wide Ruff formatting still reports the same three untouched files recorded by Plan 02-25 in `deferred-items.md`; every Plan 02-26 Python file passes the scoped formatting gate.
- The Vite production build emits the existing advisory that the main JavaScript chunk exceeds 500 kB; build output is valid and this plan does not change the application bundle architecture.

## Authentication Gates

None.

## Known Stubs

None.

## User Setup Required

None - no external configuration, migration, dependency, or credential change is required.

## Next Phase Readiness

- Active-only product reactivation can load its owned published mapping graph without synthesizing candidate state.
- Admin configuration can validate any exact configured Bitbucket branch independently of branch-list pagination while retaining safe lease, redirect, budget, and bounded-error contracts.
- Canonical generated clients expose both operations for later UI plans; requirements remain subject to the shared-ID readiness gate.
- No Plan 02-26 checkpoint or blocker remains; ready for Plan 02-27.

## Self-Check: PASSED

- All declared implementation, test, assurance, generated-contract, and summary files exist.
- Both RED commits precede their GREEN commits; the REFACTOR follows GREEN and all five Plan 02-26 code commits are reachable from the current branch.
- All acceptance commands, mutation proofs, generated-client drift checks, static/security gates, and coverage metadata classification pass.
- No tracked deletion, skipped Plan 02-26 test, unrun verification, known stub, dependency change, provider write path, or unmodeled threat surface remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
