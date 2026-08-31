---
phase: 02-admin-configuration
plan: 42
subsystem: admin-ui-recovery
tags: [react, vitest, playwright, celery, bitbucket, revalidation, accessibility]

requires:
  - phase: 02-41
    provides: Four generated administrator-only active-revision recovery operations and exact closed schemas
provides:
  - Accessible per-mapping stale/current recovery UI for inactive published products
  - Server-authoritative all-mapping Reactivate gating with bounded polling, focus, and live-region behavior
  - Real reconnect-to-revalidate-to-confirm-to-reactivate browser proof over backend, worker, database, and provider mock
  - Immutable published-graph and zero candidate, publish, or provider-write evidence
affects: [02-38, 02-43, admin-preview, active-revision-recovery, phase-02-gauntlet]

actuals:
  tokens: 19139
  tasks: 2
  commits: 10

tech-stack:
  added: []
  patterns:
    - Server eligibility is the only browser authority for published mapping currentness
    - Active-revision recovery state is isolated from candidate preview and publication state
    - Browser E2E snapshots immutable graph identity before and after recovery

key-files:
  created: []
  modified:
    - frontend/src/features/admin/previews/ProductPreviewPage.tsx
    - frontend/src/features/admin/previews/ProductPreviewPage.test.tsx
    - frontend/e2e/admin-configuration.spec.ts
    - backend/tests/architecture/test_phase2_gap_closure.py
    - backend/tests/api/test_admin_products.py
    - tools/verify_product_publication_mutants.py

key-decisions:
  - "Published confirmation badges and Reactivate availability are derived from exact server eligibility, never from persisted layout presence alone."
  - "Run validation again uses only generated active-revision eligibility, create, get, and confirm operations; candidate and publication operations are forbidden shortcuts."
  - "The real E2E proves recovery by an unchanged graph snapshot plus an ordered HTTP/provider audit, not by UI terminal state alone."
  - "Every asynchronous recovery result is generation-bound; obsolete success and failure responses are ignored while current failures remain bounded and focus-restoring."

patterns-established:
  - "Published recovery component: separate polling, selection, confirmation, announcement, and cleanup state for the active revision scope."
  - "Recovery evidence: reconnect, eligibility, branch reads, revalidation create/get/confirm, and reactivate must occur in order with no candidate, publish, or provider-write route."

requirements-completed: [PROD-01, PROD-08, PROD-09, BITB-01, BITB-03, BITB-04, UI-03]

coverage:
  - id: D1
    description: An administrator can identify and recover each generation-stale published mapping with bounded accessible state while Reactivate remains fail-closed.
    requirement: UI-03
    verification:
      - kind: unit
        ref: frontend/src/features/admin/previews/ProductPreviewPage.test.tsx (36 passed)
        status: pass
      - kind: other
        ref: frontend changed-scope branch coverage (634/634 lines)
        status: pass
    human_judgment: false
  - id: D2
    description: Recovery uses only exact generated active-revision operations and cannot create a candidate, publish, or write to Bitbucket.
    requirement: BITB-04
    verification:
      - kind: unit
        ref: ProductPreviewPage.test.tsx::recovers generation-stale active mappings without candidate mutation
        status: pass
      - kind: e2e
        ref: admin-configuration.spec.ts::unchanged active revision reactivation uses real backend state and blocks stale confirmation
        status: pass
    human_judgment: false
  - id: D3
    description: A real reconnect-to-reactivate journey preserves the published revision, mapping, layout, sides, targets, commits, and original preview evidence while adding only the expected sidecar and active state.
    requirement: PROD-09
    verification:
      - kind: e2e
        ref: bash tools/phase2_smoke.sh --mock-live-provider (8/8 passed)
        status: pass
      - kind: other
        ref: bash tools/phase2_gauntlet.sh --gap-closure (18/18 layers passed)
        status: pass
    human_judgment: false

duration: 2h 37m
completed: 2026-08-31
status: complete
---

# Phase 02 Plan 42: Inactive Product Revalidation UI and Real Recovery E2E Summary

**Administrators can now recover stale confirmations on an unchanged published revision through a bounded, accessible, read-only Bitbucket flow whose real browser proof preserves the complete published graph.**

## Performance

- **Duration:** 2h 37m
- **Started:** 2026-08-31T17:55:16Z
- **Completed:** 2026-08-31T20:32:11Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added server-authoritative current/stale badges, `Run validation again`, bounded polling, exact confirmation, and all-mapping Reactivate gating for inactive published revisions.
- Kept recovery accessible through keyboard focus restoration, a polite atomic live region, fixed bounded error copy, and polling/unmount cleanup across success, failure, timeout, and supersession races.
- Extended the real Playwright journey through reconnect, branch resolution, worker processing, confirmation, and reactivation without intercepting application APIs.
- Proved the published revision/mapping/layout/side/target graph remains unchanged, only the expected sidecar generation advances, and no candidate, publish, or provider-write request occurs.
- Closed the full Phase 2 assurance gate with 801 backend tests, 271 frontend tests, 100% changed-scope branch coverage, all mutation inventories killed, and the 18/18 gap-closure gauntlet.

## Task Commits

1. **Task 1 RED: require stale active-revision recovery UI** - `5b42610` (test)
2. **Task 1 GREEN: implement active-revision recovery UI** - `e6fc0a2` (feat)
3. **Task 2 RED: require real reconnect-to-reactivate recovery** - `fd16920` (test)
4. **Task 2 GREEN: prove the real immutable recovery journey** - `0a4b363` (test)
5. **REFACTOR: normalize recovery implementation and E2E evidence** - `41cf52e` (refactor)
6. **Assurance: align frozen recovery route inventory** - `d81007f` (test)
7. **Assurance: parse the current review closure inventory** - `542f53d` (test)
8. **Assurance: include active recovery product routes** - `c81e165` (test)
9. **Assurance: close active recovery UI race coverage** - `ee4cb70` (test)
10. **Assurance: retarget publication mutation selectors** - `3e9739f` (test)

## Files Created/Modified

- `frontend/src/features/admin/previews/ProductPreviewPage.tsx` - Loads exact active-revision eligibility, renders published mapping recovery, isolates bounded polling/confirmation state, and derives Reactivate only from complete server currentness.
- `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx` - Proves stale/current rendering, candidate-operation exclusion, focus/live-region behavior, bounded errors, polling cutoff, deduplication, supersession, exact eligibility, and cleanup.
- `frontend/e2e/admin-configuration.spec.ts` - Seeds an inactive immutable product, drives the real recovery flow, snapshots graph identity, audits application/provider routes, and guards secrets.
- `backend/tests/architecture/test_phase2_gap_closure.py` - Aligns the frozen 34-route inventory and fail-closed review-row parser with the already shipped Plan 02-41 recovery API.
- `backend/tests/api/test_admin_products.py` - Includes eligibility and per-mapping active revalidation create paths in the exact product-path contract.
- `tools/verify_product_publication_mutants.py` - Anchors legacy candidate-confirmation mutants uniquely after active sidecar recovery introduced parallel predicates.

## Decisions Made

- Treated the backend eligibility response as the sole currentness authority. A stored selected layout cannot independently authorize reactivation after a connection generation changes.
- Kept active-revision recovery state separate from candidate preview state even where both render the same read-only candidate details.
- Bound every asynchronous job, confirmation, and eligibility response to its initiating generation; late success and late failure are both inert.
- Required the E2E to observe real backend, Celery worker, PostgreSQL, Redis, frontend, and mock provider processes and to audit the actual positive and forbidden route sets.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added explicit candidate scope to legacy E2E preview fixtures**
- **Found during:** Task 2 RED harness setup.
- **Issue:** Older direct `PreviewJob` fixture rows omitted the now-required revision scope and could not reach the intended recovery failure.
- **Fix:** Marked those existing fixture jobs as candidate-scoped without changing production behavior.
- **Files modified:** `frontend/e2e/admin-configuration.spec.ts`
- **Verification:** The RED harness reached the intended 7/8 recovery failure, then the GREEN harness passed 8/8.
- **Committed in:** `fd16920`

**2. [Rule 3 - Blocking] Updated the frozen administrator route count after Plan 02-41**
- **Found during:** Final gap-closure gauntlet.
- **Issue:** The architecture invariant still expected 30 routes although Plan 02-41 had canonically added four active-recovery operations.
- **Fix:** Raised only the exact route count to 34.
- **Files modified:** `backend/tests/architecture/test_phase2_gap_closure.py`
- **Verification:** Focused architecture contract passed and the final semantic closure passed 28/28.
- **Committed in:** `d81007f`

**3. [Rule 3 - Blocking] Retargeted the review finding parser to the current closed inventory table**
- **Found during:** Final gap-closure gauntlet.
- **Issue:** The fail-closed parser expected superseded CR/WR headings while the canonical review stores the same exact inventory as table rows.
- **Fix:** Parsed only the bounded review table section while preserving exact set, cardinality, uniqueness, and whole-row fingerprints.
- **Files modified:** `backend/tests/architecture/test_phase2_gap_closure.py`
- **Verification:** Focused parser contracts passed 3/3 and semantic closure passed 28/28.
- **Committed in:** `542f53d`

**4. [Rule 3 - Blocking] Added the two Plan 02-41 product-owned recovery paths to the exact API set**
- **Found during:** Full backend regression in the final gauntlet.
- **Issue:** The product path contract omitted reactivation eligibility and per-mapping revalidation job creation.
- **Fix:** Added exactly those two paths without relaxing the closed set.
- **Files modified:** `backend/tests/api/test_admin_products.py`
- **Verification:** Focused API contract and the complete backend suite passed 801/801.
- **Committed in:** `c81e165`

**5. [Rule 3 - Blocking] Closed active recovery race and error branch coverage without exclusions**
- **Found during:** Changed-scope coverage gate.
- **Issue:** Initial frontend changed-scope coverage was 92%, leaving polling, confirmation, eligibility, cutoff, and supersession branches unproven.
- **Fix:** Added meaningful UI tests for current and obsolete success/failure races, bounded errors, exact authority, focus, live-region, cutoff, deduplication, and cleanup.
- **Files modified:** `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx`
- **Verification:** Focused suite passed 36/36 and frontend changed-scope branch coverage reached 634/634 lines (100%).
- **Committed in:** `ee4cb70`

**6. [Rule 3 - Blocking] Retargeted candidate publication mutation selectors after active sidecar recovery**
- **Found during:** Mutation layer of the final gap-closure gauntlet.
- **Issue:** Three exact selectors described the pre-Plan 02-40 legacy shape or became ambiguous after active-revalidation predicates were added.
- **Fix:** Anchored only the existing legacy completeness, state, and identity mutants to their current unique candidate contexts; exact-count drift detection, names, inventory, and threshold remained unchanged.
- **Files modified:** `tools/verify_product_publication_mutants.py`
- **Verification:** Negative self-test passed and the complete publication mutation score remained 25/25 killed inside the final gauntlet.
- **Committed in:** `3e9739f`

---

**Total deviations:** 6 auto-fixed (6 Rule 3 blocking assurance repairs)
**Impact on plan:** Every deviation restored a frozen test or verifier to already shipped authority or strengthened planned assurance. No production API, persistence, dependency, lockfile, coverage exclusion, mutation inventory, threshold, candidate shortcut, or provider-write surface was added.

## Verification

- Product preview unit/RTL suite: **36/36 passed**, including exact stale recovery, focus, live-region, polling, error, race, and cleanup behavior.
- Frontend full suite: **271/271 passed**; backend full suite: **801/801 passed**.
- Changed-scope branch coverage: backend **641/641** and frontend **634/634**, both **100%**.
- Type/build quality: mypy passed 81 source files; Ruff lint passed and 133 backend files remained formatted; TypeScript, ESLint, Prettier, and Vite production build passed.
- Mutation: all backend verifier inventories killed, publication **25/25**, preview jobs **16/16**, Android **10/10**, iOS **11/11**; Stryker polling mutation gate passed.
- Real runtime harness: `bash tools/phase2_smoke.sh --mock-live-provider` passed **8/8** with provider audit `client_credentials`, exact `repository` scope, five GETs, and zero writes.
- Gap closure: `bash tools/phase2_gauntlet.sh --gap-closure` passed **18/18 layers** from zero; source digest remained `21d7cab7a0a20ee285727edc88553cbabf70b488d85672c2a7164590990733c4`.
- Runtime cleanup: zero Phase 2 containers, networks, volumes, or secret files remained, and zero images created by Plan 02-42 remained. The two pre-existing `verboflex-frontend:phase02-27-e2e` and `verboflex-backend:phase02-27-e2e` cache images were intentionally preserved.
- Dependency integrity: `frontend/package.json` and `frontend/package-lock.json` remained byte-for-byte unchanged.

## TDD Gate Compliance

- Task 1: RED `5b42610` failed on the absent recovery UI before GREEN `e6fc0a2`; REFACTOR evidence is `41cf52e`.
- Task 2: RED `fd16920` reached the exact real 7/8 failure after the worker succeeded but before recovery could confirm/reactivate; GREEN `0a4b363` passed the same self-contained 8/8 harness.
- All later test-only commits repaired or strengthened assurance after their exact failures were observed; none preceded the corresponding RED evidence.

## Issues Encountered

- The first real E2E RED correctly failed because the published selected layout did not match the provider candidate after reconnect. The GREEN seed uses the provider's immutable commit and exact Android layout, allowing confirmation without changing the graph.
- The full gauntlet exposed four frozen contract drifts and three mutation selector drifts introduced by already completed Plans 02-40 and 02-41; all were repaired test-only and revalidated from zero.
- Vite retains its pre-existing non-blocking warning for a JavaScript chunk larger than 500 kB. No dependency or bundling configuration changed in this plan.
- The optional real external-provider layer remained skipped because explicit opt-in/local server configuration was not supplied; the mandatory isolated mock-live-provider harness passed fully.

## User Setup Required

None - no new credentials, provider scope, dependency, package, or local service configuration is required.

## Next Phase Readiness

- Plan 02-43 can add and prove runtime anti-framing headers on the already green frontend image and shared smoke lifecycle.
- Plan 02-38 can later perform the fresh ASVS review and independent verifier closeout after Plan 02-43.
- WR-03 through WR-07 remain OPEN non-blocking warnings exactly as required; this plan does not claim to resolve them.

## Known Stubs

None.

## Authentication Gates

None.

## Self-Check: PASSED

- All six modified implementation, test, and verifier artifacts exist on disk.
- All ten RED, GREEN, refactor, and assurance commits exist in git history.
- Both mandatory plan verification commands and the final 18/18 gap-closure gauntlet completed successfully.
- The tracked implementation tree was clean before summary/tracking updates; only the explicitly preserved untracked workspace artifacts remain.
- Independent runtime inspection confirmed no Phase 2 containers, networks, or volumes remain.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-31*
