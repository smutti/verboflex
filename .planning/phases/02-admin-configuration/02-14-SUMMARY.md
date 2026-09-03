---
phase: 02-admin-configuration
plan: 14
subsystem: preview-confirmation-publication
tags: [fastapi, sqlalchemy, celery, postgres, openapi, tdd, concurrency]

requires:
  - phase: 02-10
    provides: Product-row publication lock, lifecycle conflicts, and atomic active-revision replacement
  - phase: 02-13
    provides: Four-format preview detection with exact candidate, layout, generation, commit, and digest identity
provides:
  - One complete, immutable confirmation authority for each current mapping preview result
  - An all-mapping publication/reactivation predicate serialized by the Product row lock
  - A closed confirmation HTTP contract and synchronized generated TypeScript client
affects: [02-15, 02-18, 02-19, 02-20, phase-3-imports]

actuals:
  tokens: 55961
  tasks: 2
  commits: 16

tech-stack:
  added: []
  patterns:
    - Confirmation authority is a complete snapshot whose selected output digest is checked against the current successful preview result
    - Publication revalidates every mapping identity under the existing Product row lock and never partially advances the active revision

key-files:
  created:
    - backend/alembic/versions/0007_preview_confirmations.py
  modified:
    - backend/src/verboflex/services/preview_jobs.py
    - backend/src/verboflex/services/publication.py
    - backend/src/verboflex/api/v1/routes/admin_previews.py
    - backend/src/verboflex/models/product_mapping.py
    - backend/src/verboflex/schemas/previews.py
    - frontend/src/api/client/types.gen.ts
    - tools/verify_product_publication_mutants.py

key-decisions:
  - "A confirmation is current only when its complete candidate, job, mapping, repository side, connection generation, commit, detector, layout, and result digest identity still matches."
  - "The Product row lock remains the sole linearization point: every candidate mapping is rechecked before one atomic publication/reactivation transition."
  - "Reactivating an unchanged published revision reuses the same exact confirmation predicate; stale or failed work never displaces the previous active revision."

patterns-established:
  - "Closed confirmation snapshot: persist only bounded identifiers and digests, never provider bytes, credentials, tokens, or Celery internals."
  - "Atomic all-mapping predicate: one stale or missing confirmation blocks the entire revision and preserves the live revision unchanged."
  - "Equivalent retry: a second publication request after the winner observes the already-active revision as a non-mutating no-op."

requirements-completed: [PROD-01, PROD-08, PROD-09]

coverage:
  - id: D1
    description: Admin confirms exactly one current detected layout for a mapping through a closed HTTP contract.
    requirement: PROD-09
    verification:
      - kind: integration
        ref: backend/tests/integration/test_preview_jobs.py#confirmation currentness and stale identity cases
        status: pass
      - kind: other
        ref: backend/tests/api/test_openapi_contract.py#preview confirmation request and response schema
        status: pass
    human_judgment: false
  - id: D2
    description: Publication and reactivation succeed only when every mapping has one exact current confirmation, atomically under concurrent requests.
    requirement: PROD-01
    verification:
      - kind: integration
        ref: backend/tests/integration/test_product_publication.py#two-session atomic publication and reactivation cases
        status: pass
      - kind: other
        ref: tools/verify_product_publication_mutants.py#15/15 publication and confirmation mutants killed
        status: pass
    human_judgment: false
  - id: D3
    description: Preview validation authority rejects failed, historical, partial, or tampered results without changing the previous active revision.
    requirement: PROD-08
    verification:
      - kind: integration
        ref: backend/tests/integration/test_preview_jobs.py backend/tests/integration/test_product_publication.py
        status: pass
      - kind: other
        ref: diff-cover /tmp/verboflex-02-14-final-coverage.xml --compare-branch=89b0d88 --fail-under=100
        status: pass
    human_judgment: false

duration: 1h07m
completed: 2026-08-27
status: complete
---

# Phase 02 Plan 14: Exact Preview Confirmation and Atomic Publication Summary

**Complete preview-result confirmation snapshots now gate one atomic, all-mapping publication or reactivation transition under the Product lock.**

## Performance

- **Duration:** 1h07m
- **Started:** 2026-08-27T20:04:18Z
- **Completed:** 2026-08-27T21:11:13Z
- **Tasks:** 2
- **Files modified:** 16

## Accomplishments

- Added a versioned confirmation snapshot that binds the selected candidate and layout to the exact successful preview job, immutable source identity, live Bitbucket connection generation, and complete result digest.
- Replaced the publication seam with a real all-mapping predicate that rechecks every digest under the single Product row lock, admits one concurrent winner, and treats an equivalent retry as a no-op.
- Preserved the previous active revision for every stale, failed, incomplete, mismatched, or tampered mapping while applying the identical predicate to reactivation.
- Froze the new closed FastAPI/OpenAPI contract, regenerated the TypeScript client, reached 100% changed-line coverage, and killed all 15 targeted mutants.

## Task Commits

Each TDD gate and assurance refinement was committed atomically:

1. **Task 1: Confirm exactly one current layout and reject every stale identity**
   - `ecd2404` — RED confirmation contract
   - `bc8436e` — complete preview result digests
   - `1982394` — isolated stale-completion session reads
   - `091f14b` — formatted confirmation contracts
   - `ccef38e` — migration schema lock
   - `5a9ef0c` — historical preview rejection evidence
   - `9ea8c27` — current confirmation authority implementation
2. **Task 2: Complete the atomic all-mapping publication predicate**
   - `f3fe139` — RED current-confirmation publication tests
   - `ff164a2` — corrected stale publication fixtures
   - `10202c8` — current-confirmation publication implementation
   - `7e95aa5` — decomposed confirmation currentness
   - `5cc1dc6` — confirmation boundary coverage
   - `418b15f` — removed unreachable confirmation guards
   - `05f00aa` — 15-mutant publication proof
   - `b400ed0` — frozen confirmation OpenAPI contract
   - `5e9560f` — synchronized generated preview confirmation client

## Files Created/Modified

- `backend/alembic/versions/0007_preview_confirmations.py` — adds the complete confirmation snapshot columns and database constraints.
- `backend/src/verboflex/models/product_mapping.py` — persists bounded confirmation authority on the candidate mapping.
- `backend/src/verboflex/schemas/previews.py` — defines closed confirmation request and response schemas.
- `backend/src/verboflex/api/v1/routes/admin_previews.py` — exposes the admin-only confirmation operation.
- `backend/src/verboflex/services/preview_jobs.py` — validates confirmation completeness and exact current preview-result identity.
- `backend/src/verboflex/services/publication.py` — applies the all-mapping confirmation predicate under the Product lock.
- `backend/src/verboflex/services/mappings.py` — clears obsolete confirmation state when mapping identity changes.
- `backend/tests/integration/test_preview_jobs.py` — covers complete confirmation and every stale identity boundary.
- `backend/tests/integration/test_product_publication.py` — proves atomic publication/reactivation, failure preservation, concurrency, and retry behavior.
- `backend/tests/unit/services/test_mappings.py` — verifies mapping changes invalidate confirmation authority.
- `backend/tests/api/test_openapi_contract.py` — freezes the closed HTTP and generated-client surface.
- `frontend/openapi.json` and `frontend/src/api/client/` — synchronize the canonical OpenAPI document and TypeScript client.
- `tools/verify_product_publication_mutants.py` — kills confirmation, publication, lifecycle, authorization, and schema mutants.

## Decisions Made

- Currentness is conjunctive and fail-closed: a confirmation is usable only when every recorded identity component and digest is complete and still exact.
- Publication performs no provider I/O and accepts no historical evidence; it revalidates persisted preview authority for all candidate mappings inside the Product transaction.
- Reactivation does not receive a relaxed path. It must satisfy the same current-confirmation predicate as first publication.
- Confirmation responses remain closed and exclude provider source, tokens, credentials, task payloads, and canonical translation data.

## Verification

- Exact plan command: **66 passed**.
- Focused branch coverage: **82 passed; 118/118 changed lines and branches covered (100%)**.
- Randomized backend suite (`--randomly-seed=21414`): **698 passed**.
- Migration, architecture, OpenAPI, and worker slice: **25 passed**.
- Frontend randomized Vitest (`--seed=21414`): **75 passed**; typecheck, lint, format, API drift check, and production build passed.
- Static analysis: Ruff passed; MyPy passed for **82 source files**.
- Mutation: negative control passed; baseline passed; **15/15 targeted mutants killed**.
- Supply chain: `uv lock --check` passed; `pip-audit` found no known runtime vulnerabilities; production `npm audit --omit=dev` found none. Two moderate transitive `qs` advisories remain confined to the existing frontend development toolchain.
- Secret policy: repository scan passed and the exact-policy negative control was observed failing as required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test fixture] Corrected SQL JSON null and nested-session setup**
- **Found during:** Task 2 GREEN
- **Issue:** Two new stale-result fixtures represented a JSON null as SQL `NULL` and opened a second SQLite transaction before the first fixture transaction was released.
- **Fix:** Stored a JSON null and sequenced the session setup so the tests exercise the intended production boundary.
- **Files modified:** `backend/tests/integration/test_product_publication.py`
- **Verification:** Exact Task 2 command passed.
- **Committed in:** `ff164a2`

**2. [Rule 2 - Assurance] Closed uncovered confirmation boundaries and added explicit mutants**
- **Found during:** Task 2 refactor and changed-line coverage
- **Issue:** Initial focused coverage did not independently prove missing candidate identity, wrong repository side, corrupted result state, or each confirmation bypass.
- **Fix:** Added boundary cases, removed unreachable guards, and extended the publication mutation checker with six confirmation-specific mutants.
- **Files modified:** `backend/tests/integration/test_product_publication.py`, `backend/src/verboflex/services/preview_jobs.py`, `tools/verify_product_publication_mutants.py`
- **Verification:** 100% changed-line coverage and 15/15 mutants killed.
- **Committed in:** `5cc1dc6`, `418b15f`, `05f00aa`

**3. [Rule 2 - API contract] Synchronized the confirmation operation with OpenAPI and the generated client**
- **Found during:** Full randomized backend suite
- **Issue:** The implemented confirmation route was absent from the checked-in OpenAPI assertions and generated client, leaving the new public boundary incomplete.
- **Fix:** Added exact closed schema and response assertions, regenerated the canonical document, and regenerated the TypeScript client.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`, `frontend/openapi.json`, `frontend/src/api/client/`
- **Verification:** Backend OpenAPI tests, frontend API drift check, typecheck, lint, randomized tests, and build passed.
- **Committed in:** `b400ed0`, `5e9560f`

---

**Total deviations:** 3 auto-fixed (1 Rule 1, 2 Rule 2).
**Impact on plan:** All corrections strengthened correctness and the planned public contract; no architectural boundary or dependency changed.

## Issues Encountered

- The first randomized backend run exposed three OpenAPI/client drift failures; the generated contract synchronization above resolved all three before the final 698-test run.
- The first changed-line report was 89%; missing high-risk boundaries were added until the final report reached 100%.
- An initial bare MyPy invocation targeted the installed package rather than source paths; the canonical source invocation completed with no issues across 82 files.

## Known Stubs

None. No TODO, FIXME, placeholder, skipped test, or unrun verification remains in the files changed by this plan.

## Threat Flags

None. The confirmation endpoint, persisted digest authority, and publication trust boundary were all declared and mitigated in the plan threat model; no additional security surface was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-15 can consume an active revision whose mappings each carry one explicit, current, format/layout confirmation.
- Import and canonical translation phases can rely on a single active revision transition and must continue to reject historical preview evidence.
- No blocker remains. Temporary Celery and Redis verification infrastructure was stopped after the final run.

## Self-Check: PASSED

- All 16 changed implementation, migration, test, OpenAPI, and generated-client files exist.
- All 16 task commits are present in repository history.
- Exact plan verification, full randomized suites, changed-line coverage, mutation, static, build, supply-chain, and secret checks passed on the final revision.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-27*
