---
phase: 02-admin-configuration
plan: 28
subsystem: frontend-admin-pagination
tags: [react, typescript, pagination, cursors, bitbucket, tdd]
status: complete
requires:
  - phase: 02-admin-configuration
    plan: 27
    provides: Routed product editing and mobile wizard lifecycle
  - phase: 02-admin-configuration
    plan: 31
    provides: Completed gap-plan dependency baseline
provides:
  - Generation-safe ordered cursor accumulation without a new dependency
  - Reachable repository and mapping pages with explicit partial/end states
  - Exact configured-branch restoration beyond the first 100 branches
  - Bounded revision-mapping accumulation for routed wizard restoration
affects: [admin-products, admin-repositories, admin-mappings, product-wizard]
tech-stack:
  added: []
  patterns:
    - AbortController plus monotonic generation isolation
    - Opaque cursor forwarding with stable-identity ordered deduplication
    - Exact-detail hydration kept separate from paged provider order
key-files:
  created:
    - frontend/src/features/admin/useCursorCollection.ts
    - frontend/src/features/admin/useCursorCollection.test.ts
    - frontend/src/features/admin/repositories/ProductRepositoriesPage.test.tsx
    - frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx
  modified:
    - frontend/src/features/admin/repositories/ProductRepositoriesPage.tsx
    - frontend/src/features/admin/mappings/ProductMappingsPage.tsx
    - frontend/src/features/admin/products/ProductWizardPage.tsx
    - frontend/src/features/admin/products/ProductConfiguration.test.tsx
key-decisions:
  - "Treat the product's current-candidate endpoint as the mapping query identity so a successful local version increment does not invalidate its own saved row."
  - "Resolve configured branches through one exact generated-client request per unique opaque value and merge them after listed API order without changing paged loaded counts."
  - "Bound automatic wizard revision-mapping restoration to 50 pages and fail closed on repeated cursors or page-limit exhaustion."
patterns-established:
  - "Collection pages retain server cursors verbatim and one Load more action consumes exactly one prior cursor."
  - "Partial, empty, end, initial-error, and load-more-error states remain distinct."
actuals:
  tokens: 18259
  tasks: 2
  commits: 4
metrics:
  duration: 24m 23s
  completed: 2026-08-29
---

# Phase 02 Plan 28: Ordered Cursor and Exact Branch Restoration Summary

**Dependency-free React cursor collections now preserve API order across repository, mapping, and branch pages while exact generated-client reads keep configured branches beyond item 100 selected.**

## Performance

- **Duration:** 24m 23s
- **Started:** 2026-08-29T19:47:06Z
- **Completed:** 2026-08-29T20:11:29Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added a reusable cursor hook with opaque cursor forwarding, ordered stable-ID deduplication, one-request single-flight behavior, abort/generation isolation, and separate initial/load-more failures.
- Replaced first-page-only repository and mapping state with loaded counts, explicit partial/end copy, and bounded Load more controls that keep mobile projections locally contained.
- Replaced first-100-only branch state with per-side cursor collections and exact configured-branch reads, retaining the exact opaque spelling and one-detail-request-per-value bound.
- Accumulated every routed wizard revision-mapping page under a fixed 50-page ceiling, rejecting repeated cursors rather than treating a partial set as complete.
- Kept the generated API client authoritative; `api:check` regenerated the client with zero drift.

## Task Commits

Each task followed RED then GREEN:

1. **Task 1 RED: repository cursor boundaries** - `b99997f`
2. **Task 1 GREEN: shared hook and repository UI** - `adc593b`
3. **Task 2 RED: mapping and exact-branch boundaries** - `5d54ba5`
4. **Task 2 GREEN: mapping, branch, and wizard accumulation** - `3257895`

## Verification Evidence

| Gate | Result |
|---|---|
| Hook + repository focused command | 6/6 passed |
| Mapping + wizard focused command | 32/32 passed |
| Full frontend Vitest suite | 201/201 passed |
| TypeScript typecheck | Passed |
| ESLint, zero warnings | Passed |
| Vite production build | Passed; existing chunk-size advisory only |
| Generated OpenAPI client drift check | Passed, zero generated diff |
| Prettier check over all eight plan files | Passed |
| Current-source Playwright admin journeys | 2/2 passed |

Boundary fixtures prove 0/1/50/51 repository and mapping states, 100/101 branches, exact item-101 restoration, repeated-page deduplication, one Load more request per action, one detail request per unique configured value, stale AbortSignal cancellation, and rejection of late stale merges. Responsive assertions retain `min-w-0`, `max-w-full`, local branch overflow, and document-width checks at the existing 320/768/1024/1440 browser matrix.

## Decisions Made

- Stable API IDs or exact branch names are the only deduplication identities; UI labels and provider ordering are never reinterpreted.
- Exact configured values are merged only after paged items, so server page order remains observable and pagination counts do not falsely imply completion.
- Mapping save validation now requires every selected source/target to exist in the current listed-or-exact live set and collapses duplicate target inputs without altering opaque branch text.
- Partial mapping collections expose more work and never feed any preview/publication-ready decision in the files changed by this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Prevented a successful save from invalidating its own mapping collection**
- **Found during:** Task 2 GREEN regression run
- **Issue:** Including the mutable candidate concurrency version in the cursor query key caused the parent version callback to reset the just-saved mapping row.
- **Fix:** Bound the collection to the current-candidate resource identity under product/access authority; product changes still abort and reset the generation.
- **Files modified:** `frontend/src/features/admin/mappings/ProductMappingsPage.tsx`
- **Commit:** `3257895`

**2. [Rule 3 - Blocking] Preserved the generated-wire-shape guard**
- **Found during:** Full frontend regression suite
- **Issue:** A generic cursor interface structurally resembled a handwritten generated response and correctly tripped the repository's API-authority test.
- **Fix:** Expressed the internal generic slice as a wrapped read-only type while all concrete wire data continues to come from generated client responses.
- **Files modified:** `frontend/src/features/admin/useCursorCollection.ts`
- **Commit:** `3257895`

**3. [Rule 3 - Blocking] Verified browser journeys against current source instead of a stale nginx asset**
- **Found during:** Final Playwright verification
- **Issue:** The default localhost server returned a previous-day JavaScript asset, so its first browser run did not contain this plan's repository hook.
- **Fix:** Started the current Vite source on an isolated local port and reran both admin journeys; both passed, including page-width assertions.
- **Files modified:** None
- **Commit:** Not applicable

## Known Stubs

None.

## TDD Gate Compliance

- RED commits `b99997f` and `5d54ba5` were created before their respective implementations and failed for the intended missing cursor, abort, loaded-count, wizard traversal, and exact-branch behaviors.
- GREEN commits `adc593b` and `3257895` followed the matching RED commits and pass all focused and full regression gates.

## Self-Check: PASSED

- All eight planned code/test files exist.
- All four RED/GREEN task commits exist in history.
- No generated API file, dependency manifest, lockfile, schema, endpoint, auth path, or provider URL handling changed.
- No tracked file was deleted and no unrelated untracked planning/runtime artifact was staged.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
