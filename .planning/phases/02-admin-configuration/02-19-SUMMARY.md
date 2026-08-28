---
phase: 02-admin-configuration
plan: 19
subsystem: frontend-admin
tags: [react, typescript, oauth, polling, playwright, vitest]

requires:
  - phase: 02-admin-configuration/02-18
    provides: Product, repository, mapping, user, and lifecycle administration surfaces backed by generated API operations
provides:
  - Credential-safe four-state Bitbucket connection lifecycle page
  - Identity-guarded preview polling with exact layout confirmation and backend-authoritative publication
  - Responsive mocked-provider Playwright coverage for the assembled admin journey
affects: [02-20, admin-configuration, release-verification]

actuals:
  tokens: 29017
  tasks: 3
  commits: 11

tech-stack:
  added: []
  patterns:
    - Generated API operations remain the only frontend integration boundary
    - Preview jobs use complete immutable identities to reject stale responses
    - Provider secrets are transient and never enter SPA storage, URL state, logs, or toasts

key-files:
  created:
    - frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx
    - frontend/src/features/admin/previews/ProductPreviewPage.tsx
    - frontend/src/features/admin/previews/usePreviewPolling.ts
    - frontend/e2e/admin-configuration.spec.ts
  modified:
    - frontend/src/router.tsx
    - frontend/src/features/admin/products/ProductConfiguration.test.tsx

key-decisions:
  - "Accept OAuth authorization destinations only when they are transient HTTPS URLs without user info or fragments, then navigate in the same tab."
  - "Treat the complete preview job, revision, connection, detector, input, attempt, mapping, product, and repository-side tuple as polling identity."
  - "Enable publication only after explicit current exact-candidate confirmation and reflect lifecycle changes only from backend success responses."

patterns-established:
  - "Bounded provider projection: render only the approved Bitbucket status vocabulary, bounded UTC timestamps, and the fixed read-only scope label."
  - "Bounded polling: poll every two seconds through 30 seconds, every five seconds through 90 seconds, then pause for manual refresh or retry."
  - "Exact preview authority: only complete confidence-1.0 candidates can be confirmed, and publication retains backend version authority."

requirements-completed: [PROD-01, PROD-08, PROD-09, BITB-01, BITB-03, BITB-04, UI-03]

coverage:
  - id: D1
    description: Credential-safe Bitbucket connection lifecycle with four approved states, bounded timestamps, and local revoke confirmation
    requirement: BITB-01
    verification:
      - kind: unit
        ref: frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx
        status: pass
      - kind: e2e
        ref: frontend/e2e/admin-configuration.spec.ts#OAuth states and preview polling expose bounded state without provider or credential residue
        status: pass
    human_judgment: false
  - id: D2
    description: Currentness-guarded polling, four-format exact candidates, explicit confirmation, and backend-authoritative publish/reactivate flows
    requirement: PROD-09
    verification:
      - kind: unit
        ref: frontend/src/features/admin/previews/usePreviewPolling.test.ts
        status: pass
      - kind: unit
        ref: frontend/src/features/admin/previews/ProductPreviewPage.test.tsx
        status: pass
      - kind: e2e
        ref: frontend/e2e/admin-configuration.spec.ts#product lifecycle remains backend-authoritative for deactivate and reactivation blockers
        status: pass
    human_judgment: false
  - id: D3
    description: Assembled responsive admin journey across products, wizard, repositories, mappings, users, lifecycle, OAuth, and preview publication
    requirement: UI-03
    verification:
      - kind: e2e
        ref: frontend/e2e/admin-configuration.spec.ts
        status: pass
      - kind: integration
        ref: npm test -- --run (182 tests)
        status: pass
    human_judgment: false

duration: 32min
completed: 2026-08-28
status: complete
---

# Phase 02 Plan 19: OAuth, Preview, and Admin Journey Summary

**Credential-safe Bitbucket OAuth status, deterministic preview confirmation/publication, and a responsive four-scenario Playwright admin journey**

## Performance

- **Duration:** 32 min
- **Started:** 2026-08-28T19:14:17Z
- **Completed:** 2026-08-28T19:46:29Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added the `/admin/bitbucket` route with four approved provider states, bounded UTC timestamps, safe same-tab OAuth initiation/reconnection, and named local revoke confirmation.
- Added complete-identity preview polling, timeout/manual-refresh behavior, exact four-format candidate selection, current confirmation, and backend-authoritative publish/reactivate handling with linked blockers.
- Added isolated Playwright coverage across 320, 768, 1024, and wide layouts for product projections, the five-step wizard, repository/mapping topologies, one-time user credentials, lifecycle actions, OAuth states, preview retry, and secret-residue checks.

## Task Commits

Each task was committed atomically, with TDD gates preserved:

1. **Task 1: Connect and display one read-only Bitbucket status**
   - `89eae8d` — RED: failing Bitbucket connection page contract
   - `ccdd11e` — GREEN: read-only Bitbucket connection lifecycle
   - `0ae81b6` — REFACTOR: centralized bounded timestamps
   - `0c54a4e` — type-exact deferred OAuth fixture
2. **Task 2: Poll preview candidates, confirm exact layouts, and publish**
   - `619e3f9` — RED: failing preview confirmation/publication contracts
   - `7643414` — GREEN: preview confirmation and publication workflow
   - `ddb2897` — REFACTOR: centralized exact candidate rules
3. **Task 3: Verify the assembled admin journey on desktop and mobile**
   - `1148126` — responsive mocked-provider Playwright journey
   - `4120fa6` — formatter normalization after task completion
   - `d2e1181` — live preview router regression assertion

## Files Created/Modified

- `frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx` — bounded Bitbucket status, OAuth initiation/reconnection, and local revoke UI.
- `frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx` — credential-boundary and lifecycle contract tests.
- `frontend/src/features/admin/previews/usePreviewPolling.ts` — complete-identity polling cadence, stale-response rejection, timeout pause, and manual refresh.
- `frontend/src/features/admin/previews/usePreviewPolling.test.ts` — polling timing, durability, and stale-response tests.
- `frontend/src/features/admin/previews/ProductPreviewPage.tsx` — commit resolution, layout candidate selection, confirmation, blockers, publication, and reactivation.
- `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx` — exact candidate/currentness/publication behavior tests.
- `frontend/src/router.tsx` — live Bitbucket and product preview routes.
- `frontend/e2e/admin-configuration.spec.ts` — complete responsive mocked-provider admin workflow.
- `frontend/src/features/admin/products/ProductConfiguration.test.tsx` — router regression aligned with the live empty-mapping preview projection.

## Decisions Made

- OAuth destinations are accepted only as HTTPS URLs without user info or fragments; provider responses remain transient and never become browser state.
- Polling identity includes every authority-bearing job field and ordered repository side, so stale attempts cannot overwrite a replacement job or revision.
- A preview candidate is confirmable only when confidence is exactly 1.0 and files, languages, keys, and samples are all non-empty.
- Publication and reactivation remain disabled until every mapping has explicit current confirmation, and only a successful backend response changes the displayed lifecycle state.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Made the deferred OAuth test fixture type-exact**

- **Found during:** Task 1 aggregate type checking
- **Issue:** The deferred authorization response fixture did not fully match the generated operation response type.
- **Fix:** Gave the fixture the generated authorization result shape without weakening production types.
- **Files modified:** `frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx`
- **Verification:** Focused Bitbucket Vitest command, TypeScript, and full frontend tests pass.
- **Committed in:** `0c54a4e`

**2. [Rule 1 - Bug] Preserved polling cadence for referentially identical responses**

- **Found during:** Task 2 GREEN loop
- **Issue:** A mock/provider returning the same response object could prevent the next scheduled poll even though the job remained non-terminal.
- **Fix:** Rescheduled from the complete polling state while retaining immutable identity and stale-response guards.
- **Files modified:** `frontend/src/features/admin/previews/usePreviewPolling.ts`
- **Verification:** Focused polling/page Vitest command passes 19 tests, including repeated-response cadence and stale replacement cases.
- **Committed in:** `7643414`

**3. [Rule 3 - Blocking] Replaced the removed preview placeholder regression assertion**

- **Found during:** Aggregate frontend Vitest verification after Task 3
- **Issue:** A Plan 18 router test still asserted the placeholder copy replaced by the live Plan 19 preview route.
- **Fix:** Asserted the generated empty-mapping preview alert and recovery copy.
- **Files modified:** `frontend/src/features/admin/products/ProductConfiguration.test.tsx`
- **Verification:** Product configuration tests pass 27/27 and the full frontend suite passes 182/182.
- **Committed in:** `d2e1181`

---

**Total deviations:** 3 auto-fixed (1 Rule 1 bug, 2 Rule 3 blockers)
**Impact on plan:** All fixes were required to preserve type safety, polling correctness, and aggregate regression coverage; no feature scope was added.

## Issues Encountered

- Port 8080 was occupied by an older nginx bundle that predated Plan 19. Task 3 verification was rerun against the current Vite application on `http://127.0.0.1:8081`; all four Playwright scenarios passed there.
- The production build retains the existing Vite advisory that the main JavaScript chunk exceeds 500 kB. It is a warning only and was not introduced as a correctness failure by this plan.
- Best-effort deviation registration in `.planning/WINDOWS.md` was rejected because its pre-existing frontmatter counts disagree with its entries; the deviations remain recorded above in this canonical summary.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: oauth-redirect | `frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx` | Same-tab external authorization navigation is a trust boundary; destinations are restricted to transient HTTPS URLs without user info or fragments. |
| threat_flag: publication-mutation | `frontend/src/features/admin/previews/ProductPreviewPage.tsx` | Confirmation and publication mutate server state; generated operations, current exact identities, named confirmation, and backend-authoritative success guard the boundary. |

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 20 can run the final phase quality gate over the completed admin workflow.
- No unresolved stubs, skipped tests, authentication gates, or unrun verification commands remain.

## Self-Check: PASSED

- All created implementation and E2E files exist.
- All ten implementation, TDD, formatting, and regression commits resolve in git history.
- Targeted, aggregate, build, and Plan 19 browser verification commands completed successfully.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-28*
