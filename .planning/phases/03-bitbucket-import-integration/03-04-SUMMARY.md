---
phase: 03-bitbucket-import-integration
plan: 04
subsystem: bitbucket-admin-ui
tags: [bitbucket, openapi, react, typescript, accessibility, tdd]

requires:
  - phase: 03-bitbucket-import-integration
    plan: 03
    provides: Closed server capability profile and expanded OAuth reauthorization state
provides:
  - Deterministic generated TypeScript transport for the three closed Bitbucket capabilities
  - Accessible administrator capability profile with exact expanded-access and later-phase copy
  - Reauthorization recovery that preserves the prior server-projected profile on mutation failure
affects: [03-05, 03-10, 03-12, 03-15, phase-08]

actuals:
  tokens: 60305
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Generated OpenAPI types remain the sole browser wire authority
    - Capability readiness is exhaustively mapped from closed server literals
    - Mutations preserve the last successful projection until a bounded status refetch succeeds

key-files:
  created: []
  modified:
    - frontend/openapi.json
    - frontend/src/api/client/index.ts
    - frontend/src/api/client/sdk.gen.ts
    - frontend/src/api/client/types.gen.ts
    - frontend/src/api/admin-client-contract.test.ts
    - frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx
    - frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx
    - frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx

key-decisions:
  - "Render readiness through an exhaustive closed-literal label map; never derive capability from OAuth scopes, timestamps, or prior success."
  - "Show `Repository and pull-request access` only when both generated profile fields exactly identify the expanded server contract."
  - "Keep future source-write and pull-request readiness descriptive only, with no provider-write control in the browser."

patterns-established:
  - "Capability list: all three server-ordered rows remain visible for disconnected, ready, legacy, mixed, and unavailable projections."
  - "Capability loading: the initial region retains the final three-row geometry and exposes one accessible loading indicator per row."

requirements-completed: [BITB-02, BITB-06]

coverage:
  - id: D1
    description: The generated client exposes the exact closed capability contract and only authenticated VerboFlex status, connect, and reconnect requests.
    requirement: BITB-02
    verification:
      - kind: integration
        ref: frontend/src/api/admin-client-contract.test.ts#closed Bitbucket capability contract
        status: pass
      - kind: other
        ref: cd frontend && npm run api:check
        status: pass
    human_judgment: false
  - id: D2
    description: Administrators see exactly three accessible capability rows, expanded-access copy, loading geometry, and mixed readiness without client inference.
    requirement: BITB-02
    verification:
      - kind: automated_ui
        ref: frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx#UI3-C01/UI3-C05/UI3-C13/UI3-C17
        status: pass
      - kind: other
        ref: cd frontend && npm run build && npm run lint && npm run format:check
        status: pass
    human_judgment: false
  - id: D3
    description: Legacy reauthorization and connection failure retain the prior safe profile, exact recovery announcement, and updated revocation consequences.
    requirement: BITB-06
    verification:
      - kind: automated_ui
        ref: frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx#UI3-C10
        status: pass
      - kind: manual_procedural
        ref: User-confirmed Task 1 tracer checkpoint on 2026-09-02
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-09-02
status: complete
---

# Phase 03 Plan 04: Generated Capability Client and Administrator UX Summary

**Canonical generated capability transport now drives an exact three-row administrator profile with safe reauthorization, bounded refresh, and no provider-write affordance.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-09-02T21:12:32Z
- **Completed:** 2026-09-02T21:25:13Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Regenerated the canonical OpenAPI client so the browser receives only `source_read`, `source_write`, `pull_request`, their evaluation time, and the approved expanded profile identity.
- Rendered a flat, responsive `Capability profile` definition list in the required order with exact readiness and later-phase copy for every lifecycle state.
- Preserved the prior capability projection when connect or reconnect fails, disabled only the submitted action, and retained exact polite transition announcements.
- Updated the destructive connection confirmation to explain that imports are blocked while successful baselines remain recorded.
- Added one executable assertion for each required capability consideration: UI3-C01, UI3-C05, UI3-C10, UI3-C13, and UI3-C17.

## Task Commits

Each TDD task was committed as genuine RED evidence followed by GREEN behavior:

1. **Task 1 RED: generated closed capability contract** - `3e004aa` (test)
2. **Task 1 GREEN: canonical generated transport** - `63fa6bf` (feat)
3. **Task 2 RED: capability-profile UI considerations** - `614cb83` (test)
4. **Task 2 GREEN: accessible capability and reauthorization UX** - `7bb98fc` (feat)

## Files Created/Modified

- `frontend/openapi.json` - Canonical backend-exported capability schema.
- `frontend/src/api/client/index.ts` - Generated capability-profile type export.
- `frontend/src/api/client/sdk.gen.ts` - Generated authenticated VerboFlex operations.
- `frontend/src/api/client/types.gen.ts` - Closed readiness and expanded profile types.
- `frontend/src/api/admin-client-contract.test.ts` - Structural, runtime, forbidden-key, and deterministic-generation armor.
- `frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx` - Exact capability profile, skeleton geometry, bounded recovery, and revocation copy.
- `frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx` - Component coverage for all five named Phase 3 capability considerations.
- `frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx` - Type-safe aggregate fixtures for the expanded generated status contract.

## Decisions Made

- Readiness text is an exhaustive compile-time mapping over the generated union. No raw provider scope, timestamp, connection generation, or client heuristic participates in readiness.
- The expanded access label is rendered only when both generated `scope_label` and `scope_profile` equal their canonical expanded literals; legacy authority instead presents reauthorization through server-owned status and capability values.
- Source-write and pull-request readiness remains informational with `Not used during imports.` and no branch, commit, or pull-request mutation action.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Updated Workspace overview fixtures for the generated capability contract**

- **Found during:** Task 2 GREEN build verification
- **Issue:** TypeScript compilation failed because the Workspace overview test still constructed the superseded read-only status shape and omitted the now-required capability profile.
- **Fix:** Replaced the obsolete profile literals and supplied closed connected/disconnected capability fixtures without changing Workspace behavior.
- **Files modified:** `frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx`
- **Verification:** Focused Workspace and Bitbucket component suites pass; production TypeScript build succeeds.
- **Committed in:** `7bb98fc`

---

**Total deviations:** 1 auto-fixed (1 Rule 3)
**Impact on plan:** The adjustment was required for repository-wide type safety after canonical generation and added no runtime surface or scope expansion.

## Issues Encountered

- Introducing named readiness on all three rows made several older `Disconnected` text queries ambiguous. Those assertions were narrowed to the connection-status projection while the new capability tests use accessible named groups.
- Vite continues to report the pre-existing informational large-chunk warning after a successful build; lint and compilation have no errors.

## Verification

- `cd frontend && npm run api:generate` — passed.
- `cd frontend && npm test -- --run src/api/admin-client-contract.test.ts src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx` — 29 passed.
- `cd frontend && npm run api:check` — passed with zero generated drift after a second generation.
- `cd frontend && npm test -- --run src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx src/features/workspace/WorkspaceOverviewPage.test.tsx` — 25 passed.
- `cd frontend && npm run build` — passed.
- `cd frontend && npm run lint` — passed with zero warnings.
- `cd frontend && npm run format:check` — passed.
- Consideration marker scan — UI3-C01/C05/C10/C13/C17 each occur exactly once.

## TDD Gate Compliance

- Task 1 has RED commit `3e004aa` before GREEN commit `63fa6bf`.
- Task 2 has RED commit `614cb83` before GREEN commit `7bb98fc`.
- No refactor commit was required; focused, contract, build, lint, format, and deterministic-generation gates remain green.

## Known Stubs

None. Nullable values are closed lifecycle evidence, and empty arrays occur only as bounded test collectors or explicit aggregate fixtures.

## User Setup Required

The organizational Bitbucket consumer must carry the approved expanded authority and legacy connections must be reauthorized before imports can become ready. No browser-side provider write or additional setup was introduced by this plan.

## Next Phase Readiness

- Plan 03-05 can consume the generated expanded profile while hardening provider reads behind the server boundary.
- Plan 03-10 can reuse the closed source-read readiness when aggregating published mapping imports.
- Plan 03-15 has exact, unique executable markers for all five capability UI considerations.
- No blocker remains for the next wave.

## Self-Check: PASSED

- All eight modified implementation, generated, and test files exist.
- RED/GREEN commits `3e004aa`, `63fa6bf`, `614cb83`, and `7bb98fc` are present in git history.
- Coverage metadata names three deliverables and points only to passing verification evidence.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-02*
