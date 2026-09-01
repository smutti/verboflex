---
phase: 02-admin-configuration
plan: 44
subsystem: ui
tags: [react, typescript, vitest, playwright, bitbucket]

requires:
  - phase: 02-admin-configuration
    provides: "Plan 02-38 immutable active-revision revalidation and provider-audited smoke baseline"
provides:
  - "Exact generated branch-detail commit resolution for candidate previews"
  - "The same exact resolver for immutable active-revision revalidation"
  - "Branch-101+, opaque-name, fail-closed, and zero-provider-write regression evidence"
affects: [02-45, admin-preview, product-lifecycle, bitbucket-read-boundary]

actuals:
  tokens: 6171
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Configured source sides are projected once, then resolved through generated exact-detail reads"
    - "Provider branch identity is accepted only by byte-for-byte returned-name equality"

key-files:
  created: []
  modified:
    - frontend/src/features/admin/previews/ProductPreviewPage.tsx
    - frontend/src/features/admin/previews/ProductPreviewPage.test.tsx
    - frontend/e2e/admin-configuration.spec.ts

key-decisions:
  - "Use getAdminRepositoryBranch as the sole preview commit authority; branch-list pages are never searched or paginated for commit resolution."
  - "Preserve configured branch names as opaque strings and reject missing data or any returned-name mismatch before job creation."

patterns-established:
  - "Exact source resolution: repository UUID plus unchanged branch_name produces one guarded commit per direct, keys, or translations role."
  - "Candidate and active-revision flows share commit resolution while retaining distinct version and lifecycle authority."

requirements-completed: [PROD-08]

coverage:
  - id: D1
    description: "Candidate direct and separate previews resolve configured branch 101+ through exact generated detail reads."
    requirement: PROD-08
    verification:
      - kind: unit
        ref: "frontend/src/features/admin/previews/ProductPreviewPage.test.tsx#resolves branch 101 through exact detail"
        status: pass
      - kind: automated_ui
        ref: "frontend/e2e/admin-configuration.spec.ts#100/101 exact branches stay fail-closed at 200 percent zoom"
        status: pass
    human_judgment: false
  - id: D2
    description: "Immutable active-revision revalidation uses the same exact resolver without candidate or lifecycle authority confusion."
    requirement: PROD-08
    verification:
      - kind: unit
        ref: "frontend/src/features/admin/previews/ProductPreviewPage.test.tsx#resolves branch 101 through exact detail for active sources"
        status: pass
      - kind: e2e
        ref: "frontend/e2e/admin-configuration.spec.ts#unchanged active revision reactivation uses real backend state and blocks stale confirmation"
        status: pass
    human_judgment: false
  - id: D3
    description: "Mismatch and provider-read failures stop before preview jobs, publication, reactivation, or Bitbucket writes."
    requirement: PROD-08
    verification:
      - kind: integration
        ref: "bash tools/phase2_smoke.sh --mock-live-provider (five repository GETs, zero provider writes)"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-09-01
status: complete
---

# Phase 02 Plan 44: Exact Preview Branch Resolution Summary

**Candidate and active-revision previews now bind every configured source side to an exact generated Bitbucket branch-detail response, including branches beyond list page one.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-09-01T14:51:18Z
- **Completed:** 2026-09-01T14:58:15Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Removed first-page branch-list lookup from preview commit authority and replaced it with one generated detail request per configured side.
- Preserved direct versus separate keys/translations roles and ordering for both candidate preview and immutable active-revision revalidation.
- Added branch-101+, reserved-character, case, Unicode, missing-data, partial-side failure, and provider-read-only browser evidence.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1: RED — exact branch-101 preview contract** - `422a780` (`test`)
2. **Task 2: GREEN — exact generated branch-detail resolution** - `ad635a6` (`feat`)
3. **Task 3: REFACTOR — shared configured-side resolver** - `8bc797d` (`refactor`)

## Files Created/Modified

- `frontend/src/features/admin/previews/ProductPreviewPage.tsx` - Projects configured source sides and requires exact detail identity before returning commits.
- `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx` - Covers candidate/active direct and separate branch-101 resolution plus fail-closed mismatches and failures.
- `frontend/e2e/admin-configuration.spec.ts` - Exercises routed candidate and real active-revalidation detail GETs with provider-write audit.

## Verification

- `npm test -- --run src/features/admin/previews/ProductPreviewPage.test.tsx src/router.test.tsx` — 74 passed.
- `npm run typecheck` — passed.
- `npm run lint` — passed with zero warnings.
- `npm run api:check` — deterministic regeneration passed with no generated-client drift.
- `bash tools/phase2_smoke.sh --mock-live-provider` — 8 Playwright tests passed; repository scope, five GETs, and zero provider writes confirmed.
- Package manifests, lockfile, OpenAPI, generated client, API configuration, backend schemas, and migrations were not modified.

## TDD Gate Compliance

- RED failed for the intended reason: the production resolver made zero `getAdminRepositoryBranch` calls and still depended on the first branch-list page.
- GREEN passed the unchanged focused contract after exact detail resolution was implemented.
- REFACTOR preserved the green contract while isolating `ConfiguredPreviewSourceSide`, `configuredPreviewSourceSides`, and `resolveConfiguredBranchCommit`.

## Decisions Made

- The generated exact branch-detail operation is the only authority for preview commits; no branch-list fallback exists.
- Exact returned-name equality is mandatory and no trimming, case folding, Unicode normalization, or manual URL transformation is applied.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CR-14 is closed with ordered RED/GREEN/REFACTOR evidence and routed provider-read-only proof.
- Plan 02-45 can consume the restored preview-route baseline without API, schema, generated-client, or package changes.

## Self-Check: PASSED

- All three modified implementation/test paths and this summary exist.
- Commits `422a780`, `ad635a6`, and `8bc797d` are present in repository history.
- Coverage metadata classifies all three deliverables as automatically proven by passing evidence.

---
*Phase: 02-admin-configuration*
*Completed: 2026-09-01*
