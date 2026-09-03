---
phase: 03-bitbucket-import-integration
plan: 15
subsystem: testing
tags: [pytest, vitest, stryker, playwright, docker, openapi, source-digest]

requires:
  - phase: 03-14
    provides: deployment-like import/recovery smoke and supplemental live-read boundary
provides:
  - exact Phase 3 semantic, UI, API, provider, and background scope equality
  - ordered 14-layer fail-closed closeout gauntlet with backend and frontend mutation proof
  - canonical immutable-source manifest, stable digest, and sanitized bounded evidence
affects: [03-16, phase-08-bitbucket-pull-requests, verification, release-gates]

actuals:
  tokens: 71828
  tasks: 2
  commits: 11

tech-stack:
  added: []
  patterns:
    - exact-set architecture guards with executable negative-control fixtures
    - manifest-bound source digest separated from mutable closeout evidence
    - fail-closed mutation ownership for backend authority and frontend interaction boundaries

key-files:
  created:
    - backend/tests/architecture/test_phase3_gauntlet.py
    - tools/phase3_gauntlet.sh
    - tools/phase3_source_manifest.txt
    - tools/verify_import_job_mutants.py
  modified:
    - backend/tests/architecture/test_phase3_scope.py
    - backend/tests/architecture/test_provider_boundaries.py
    - backend/tests/architecture/test_background_boundaries.py
    - backend/tests/integration/test_import_jobs.py
    - docs/evidence/phase-03.md

key-decisions:
  - "Bind Phase 3 closeout to one manifest digest that includes implementation, tests, configuration, and verifier tools but excludes mutable evidence, review, verification, and summary artifacts."
  - "Require targeted Stryker ownership at exact source locations for polling, action labels, cursor termination, and reconciliation response handling, with every generated mutant killed."
  - "Collect only the two approved Phase 3 Playwright owners so unrelated credential-gated specs cannot contaminate the closeout gate."

patterns-established:
  - "Closeout layering: source state, negative controls, full suites, quality/generated contracts, mutation, UI, supply chain, architecture, deployment smoke, API seal, final source state."
  - "Mutation fail-closedness: the backend verifier requires exactly one reviewed mutation per authority domain and the frontend report requires exact file/line ownership."

requirements-completed: [BITB-02, BITB-05, BITB-06]

coverage:
  - id: D1
    description: Phase 3 requirements, decisions, fallback edges, prohibitions, UI considerations, API rows, provider boundaries, and background boundaries reconcile by exact executable equality.
    requirement: BITB-02
    verification:
      - kind: unit
        ref: "backend/tests/architecture/test_phase3_scope.py and boundary architecture suites"
        status: pass
    human_judgment: false
  - id: D2
    description: The complete backend, frontend, worker, migration, OpenAPI, UI, audit, and deployment candidate passes one ordered fail-closed gauntlet.
    requirement: BITB-05
    verification:
      - kind: other
        ref: "bash tools/phase3_gauntlet.sh (14/14 layers)"
        status: pass
      - kind: e2e
        ref: "frontend/e2e/admin-configuration.spec.ts#UI3-C23 and UI3-C26"
        status: pass
    human_judgment: false
  - id: D3
    description: Capability, state, provenance, ancestry, rewrite, error, polling, action, cursor, and reconciliation boundaries are protected by killed mutants and digest-bound sanitized evidence.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: "tools/verify_import_job_mutants.py (6/6 killed)"
        status: pass
      - kind: unit
        ref: "Stryker targeted import UI mutation report (25/25 killed)"
        status: pass
      - kind: other
        ref: "tools/source_state.sh --verify-report-digest"
        status: pass
    human_judgment: false

duration: 1h30min
completed: 2026-09-03
status: complete
---

# Phase 03 Plan 15: Exact Scope and Closeout Gauntlet Summary

**Exact Phase 3 scope equality and a 14-layer closeout gauntlet now bind 950 backend tests, 356 frontend tests, 31 killed mutants, provider-read-only smoke evidence, and the API matrix to one stable source digest.**

## Performance

- **Duration:** 1h30min
- **Started:** 2026-09-03T15:47:26+02:00
- **Completed:** 2026-09-03T17:17:26+02:00
- **Tasks:** 2
- **Files modified:** 20

## Accomplishments

- Enforced exact equality for all three Phase 3 requirements, 18 decisions, six fallback edges, two complete prohibitions, 26 UI considerations with exact owners, 56 API capabilities, and provider/background boundaries.
- Added a canonical source manifest and a 14-layer gauntlet covering full backend/frontend suites, quality and generated contracts, migrations, targeted mutation, Playwright reflow/accessibility, dependency/license/secret/schema audits, architecture, deployment smoke, and API pre-seal.
- Killed 6/6 reviewed backend authority mutants and 25/25 frontend polling/action/cursor/dialog mutants, with explicit negative controls and target-ownership drift detection.
- Captured sanitized evidence for digest `ddb3e79ad5e00891f8d3bcaa6bd4d8b39ad738bb0e97f0ad16b0d05f25cb9310` after the final 14/14-layer run and removed all disposable runtime resources.

## Task Commits

Each task was committed atomically with RED before GREEN:

1. **Task 1 RED: exact Phase 3 scope guard** - `4adce09` (test)
2. **Task 1 GREEN: semantic, UI, provider, and background equality** - `8209007` (feat)
3. **Task 2 RED: gauntlet contract** - `8f467ce` (test)
4. **Task 2 GREEN: manifest, mutation verifier, and closeout gauntlet** - `13c0b66` (feat)
5. **Task 2: evolve inherited Phase 2 guards** - `8fc4438` (fix)
6. **Task 2: restore strict backend quality gates** - `1cc7b49` (fix)
7. **Task 2: align generated discovery rate-limit contract** - `9c2e51d` (fix)
8. **Task 2: strengthen provenance and ancestry mutation coverage** - `99b6b96` (test)
9. **Task 2: bind exact frontend mutation targets** - `611e68d` (fix)
10. **Task 2: isolate approved Phase 3 Playwright owners** - `933b7a9` (fix)
11. **Task 2: record sanitized gauntlet evidence** - `bf15abd` (docs)

## Files Created/Modified

- `backend/tests/architecture/test_phase3_scope.py` - Exact requirements, decisions, edge, prohibition, UI-owner, API-matrix, and deferred-scope equality.
- `backend/tests/architecture/test_provider_boundaries.py` - Non-vacuous provider method and endpoint prohibition checks.
- `backend/tests/architecture/test_background_boundaries.py` - Worker/HTTP separation and background execution boundaries.
- `backend/tests/architecture/test_phase3_gauntlet.py` - RED-first contract for the manifest, ordered layer set, mutation domains, and bounded evidence.
- `tools/phase3_source_manifest.txt` - Canonical digest input spanning Phase 3 sources, tests, configuration, and tools.
- `tools/verify_import_job_mutants.py` - Isolated capability/state/provenance/ancestry/rewrite/error mutation verifier.
- `tools/phase3_gauntlet.sh` - Ordered 14-layer pre-closeout gate with deterministic cleanup.
- `backend/tests/integration/test_import_jobs.py` - Persisted-generation and non-boolean ancestry boundary assertions.
- `backend/src/verboflex/schemas/admin_discovery.py` - Closed `rate_limited` discovery state aligned with emitted failures.
- `frontend/openapi.json` and `frontend/src/api/client/types.gen.ts` - Regenerated canonical browser contract.
- `docs/evidence/phase-03.md` - Bounded final counts, durations, hashes, and immutable source digest.

## Decisions Made

- Mutable evidence, review, verifier, and summary artifacts remain outside the source manifest so evidence can truthfully reference the immutable implementation without self-reference.
- Backend mutation proof uses isolated source copies and fails on subject drift, a green mutant, an invalid baseline, or any mutation result that did not reach an assertion failure.
- Frontend mutation proof owns exact locations in each required behavior area and rejects missing, moved, uncovered, surviving, timeout, or errored mutants.
- The Phase 3 browser layer selects only `admin-configuration.spec.ts` and its two approved UI markers; external auth-shell credentials are not a precondition for this phase gate.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Evolved stale Phase 2 scope guards for the completed Phase 3 surface**

- **Found during:** Task 2 full backend layer.
- **Issue:** Two inherited Phase 2 architecture tests still prohibited the Phase 3 import model/routes and expected the older capability schema.
- **Fix:** Preserved the original deferred/write prohibitions while admitting exactly the completed import surface and current route count.
- **Files modified:** `backend/tests/architecture/test_phase2_scope.py`, `backend/tests/architecture/test_phase2_gap_closure.py`
- **Verification:** Full backend suite passed 950/950.
- **Committed in:** `8fc4438`

**2. [Rule 1 - Bug] Aligned the typed discovery failure contract with the emitted rate-limit state**

- **Found during:** Task 2 type and OpenAPI layers.
- **Issue:** The discovery route emitted `rate_limited`, but the Pydantic response literal and checked-in generated client omitted it.
- **Fix:** Added the closed state, updated the contract assertion, and regenerated the OpenAPI/browser types.
- **Files modified:** `backend/src/verboflex/schemas/admin_discovery.py`, `backend/tests/api/test_openapi_contract.py`, `frontend/openapi.json`, `frontend/src/api/client/types.gen.ts`
- **Verification:** Mypy, 40 targeted API tests, OpenAPI no-diff, and the full gauntlet passed.
- **Committed in:** `1cc7b49`, `9c2e51d`

**3. [Rule 3 - Blocking] Restored strict formatting for previously completed Phase 3 files**

- **Found during:** Task 2 backend format gate.
- **Issue:** Five existing Phase 3 sources/tests did not satisfy the configured Ruff formatter.
- **Fix:** Applied the repository formatter without behavior changes.
- **Files modified:** Phase 3 schema, API, live-smoke, OAuth, and migration test files.
- **Verification:** Ruff reported 143 files already formatted on the final run.
- **Committed in:** `1cc7b49`

**4. [Rule 2 - Missing Critical] Added assertions that kill persisted-provenance and malformed-ancestry mutants**

- **Found during:** Task 2 targeted backend mutation layer.
- **Issue:** Existing tests did not prove that a drifted persisted execution generation or a non-boolean completeness value was rejected.
- **Fix:** Added focused integration boundaries and included the persisted-generation owner in the isolated mutation selection.
- **Files modified:** `backend/tests/integration/test_import_jobs.py`, `tools/verify_import_job_mutants.py`
- **Verification:** All six reviewed backend mutants were killed.
- **Committed in:** `99b6b96`

**5. [Rule 3 - Blocking] Bound frontend mutation and Playwright collection to exact Phase 3 owners**

- **Found during:** Task 2 mutation and browser layers.
- **Issue:** Broad Stryker ranges included unrelated branches, and Playwright imported a credential-gated auth spec before applying the marker filter.
- **Fix:** Selected exact covered locations across all four required UI behaviors, asserted report ownership, and collected only the approved Phase 3 E2E file.
- **Files modified:** `tools/phase3_gauntlet.sh`
- **Verification:** Stryker killed 25/25; both approved Playwright checks passed.
- **Committed in:** `611e68d`, `933b7a9`

---

**Total deviations:** 5 auto-fixed (1 bug, 1 missing critical functionality, 3 blocking issues)
**Impact on plan:** Every change tightened or restored a planned closeout gate; no provider-write or product-facing scope was added.

## Issues Encountered

- The gauntlet deliberately failed on stale inherited guards, OpenAPI drift, two uncovered backend mutants, overly broad frontend mutation ranges, and unrelated Playwright credential collection. Each failure produced a focused correction before the canonical final run.
- Vite reported its existing bundle-size advisory during production build; the build completed successfully and this advisory is outside the Phase 3 correctness scope.

## Authentication Gates

None. The mandatory gauntlet uses deterministic local provider infrastructure; the previously documented live-provider path remains supplemental.

## Known Stubs

None. Empty shell lifecycle variables are cleanup sentinels, and the `todo`/`fixme` strings in the scope parser are intentional rejected-test markers rather than product placeholders.

## User Setup Required

None for the mandatory closeout candidate.

## TDD Gate Compliance

- Task 1 RED `4adce09` precedes GREEN `8209007`.
- Task 2 RED `8f467ce` precedes GREEN `13c0b66`.
- Subsequent gauntlet failures were corrected by focused commits, including new mutation assertions before the final passing run.

## Next Phase Readiness

- Plan 03-16 can perform fresh independent review and verification against the canonical Phase 3 digest and bounded evidence.
- The candidate has 14/14 passing layers, 56/56 API capabilities explicitly accounted for, zero provider resource mutations in smoke, and no remaining Phase 3 Docker/runtime resources.
- No blocking-human condition remains.

## Self-Check: PASSED

All declared implementation, test, tool, manifest, generated-contract, and evidence files exist; all eleven task commits resolve; the final source digest remained unchanged; and every disposable Phase 3 container, network, volume, image, worker, and recorded runtime file was removed.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-03*
