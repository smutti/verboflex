---
phase: 03-bitbucket-import-integration
plan: 08
subsystem: bitbucket-import-classification
tags: [bitbucket, ancestry, diffstat, imports, tdd, reconciliation]

requires:
  - phase: 03-bitbucket-import-integration
    plan: 05
    provides: Generation-current, operation-bound, GET-only Bitbucket provider adapter
  - phase: 03-bitbucket-import-integration
    plan: 07
    provides: Stable logical imports, immutable executions, atomic separate baselines, and watchdog fencing
provides:
  - Exact bounded equality, descendant, and divergence comparison over immutable commits
  - Complete metadata-only localization diffstat with pagination and budget enforcement
  - Mapping-scoped equal, fast-forward, or review-required classification for direct and separate mappings
affects: [03-09, 03-10, 03-13, phase-08, import-reconciliation]

actuals:
  tokens: 15283
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Equality short-circuits locally while every non-equal comparison uses exact commit-bound provider reads
    - Separate mapping sides are compared in Keys then Translations order and yield one atomic mapping result
    - Incomplete or forged evidence raises a closed provider-read failure before any rewrite authority exists

key-files:
  created: []
  modified:
    - backend/src/verboflex/integrations/bitbucket/client.py
    - backend/src/verboflex/integrations/bitbucket/urls.py
    - backend/src/verboflex/services/repository_discovery.py
    - backend/src/verboflex/services/import_jobs.py
    - backend/tests/architecture/test_provider_boundaries.py
    - backend/tests/integration/test_bitbucket_http_adapter.py
    - backend/tests/integration/test_bitbucket_discovery.py
    - backend/tests/integration/test_import_jobs.py

key-decisions:
  - "Treat exact commit equality as a provider-free current result; only a complete ancestry proof may produce fast-forward."
  - "Compare every side before reading rewrite deltas, then preserve canonical side order and each provider traversal ordinal in one mapping-scoped candidate."
  - "Reject incomplete, mismatched, forged-side, noncanonical-order, unsafe-path, or stale-generation evidence with no candidate or confirmation authority."
  - "Keep zero localization-file delta complete and review-required when immutable commits diverge."

patterns-established:
  - "Closed movement result: equal, fast-forward, or review-required; only review-required carries a complete rewrite candidate."
  - "Atomic separate classification: one rewritten side holds Keys and Translations together while unrelated mappings remain outside the call boundary."

requirements-completed: [BITB-05, BITB-06]

coverage:
  - id: D1
    description: Exact commit equality and bounded ancestry distinguish current, proven fast-forward, and rewritten source movement without provider writes.
    requirement: BITB-05
    verification:
      - kind: integration
        ref: backend/tests/integration/test_bitbucket_http_adapter.py#ancestry contracts
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py#direct equal and fast-forward classification
        status: pass
    human_judgment: false
  - id: D2
    description: Rewritten commits yield only complete bounded localization-file metadata in stable side and provider traversal order.
    requirement: BITB-05
    verification:
      - kind: integration
        ref: backend/tests/integration/test_bitbucket_http_adapter.py#diffstat contracts
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py#ordered separate rewrite candidate
        status: pass
    human_judgment: false
  - id: D3
    description: Direct and separate mappings classify atomically; zero delta remains review-required and incomplete or forged evidence supplies no confirmation authority.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_import_jobs.py#zero delta separate and fail-closed classification
        status: pass
      - kind: unit
        ref: backend/tests/architecture/test_provider_boundaries.py#GET-only adapter surface
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-09-03
status: complete
---

# Phase 03 Plan 08: Exact Source Movement Classification Summary

**Exact commit ancestry now advances only proven descendants, while rewritten direct or separate mappings produce one complete ordered metadata-only review candidate.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-09-03T07:36:47Z
- **Completed:** 2026-09-03T07:56:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added exact, bounded Bitbucket ancestry reads that short-circuit equality, prove descendants through complete pagination, and classify divergence only after exhaustive comparison.
- Added complete diffstat traversal limited to localization-file metadata, exact old/new commits, stable side identity, provider order, and explicit page/row/path/byte ceilings.
- Added mapping-scoped classification for direct and atomic Keys-plus-Translations mappings with closed `equal`, `fast-forward`, and `review-required` outcomes.
- Ensured zero-delta rewrites remain complete review candidates while incomplete, mismatched, unsafe, over-budget, repeated-cursor, or generation-obsolete evidence yields no authority.

## Task Commits

Each TDD task has a genuine RED commit followed by its GREEN implementation:

1. **Task 1 RED: exact ancestry and bounded diffstat contracts** - `f215bef` (test)
2. **Task 1 GREEN: bounded ancestry and diffstat reads** - `91d51b6` (feat)
3. **Task 2 RED: mapping-scoped movement classification contracts** - `caa30d2` (test)
4. **Task 2 GREEN: direct and separate movement classification** - `e2313c7` (feat)

## Files Created/Modified

- `backend/src/verboflex/integrations/bitbucket/client.py` - Reads exact ancestry and complete bounded localization diffstat through generation-current GET operations.
- `backend/src/verboflex/integrations/bitbucket/urls.py` - Constructs and validates commit-exact ancestry and diffstat URLs.
- `backend/src/verboflex/services/repository_discovery.py` - Extends the provider protocol with ancestry and diffstat capabilities.
- `backend/src/verboflex/services/import_jobs.py` - Defines safe movement inputs/results and mapping-scoped classification.
- `backend/tests/architecture/test_provider_boundaries.py` - Keeps the expanded adapter surface explicitly allowlisted and GET-only.
- `backend/tests/integration/test_bitbucket_http_adapter.py` - Covers equality, pagination, reachability, diffstat parsing, bounds, continuation safety, and generation fencing.
- `backend/tests/integration/test_bitbucket_discovery.py` - Freezes the extended discovery protocol without provider writes.
- `backend/tests/integration/test_import_jobs.py` - Covers direct/separate classification, zero delta, retries, ordering, and forged/incomplete evidence.

## Decisions Made

- Equality is an exact local comparison and performs no ancestry or diffstat request.
- A mapping advances automatically only when every side is equal or a completely proven descendant and at least one side moved.
- Any divergent side makes the entire direct or separate mapping review-required; separate sides remain ordered and atomic.
- All side ancestry is established before any divergent-side diffstat is read, preventing a partial side comparison from becoming a candidate.
- Rewrite candidates contain repository UUIDs, exact commits, relations, and localization-file metadata only; provider URLs, bodies, credentials, and source bytes are excluded.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Verification] Extended the existing adapter surface allowlist**
- **Found during:** Task 1 (Read exact ancestry and complete bounded diffstat)
- **Issue:** The plan's Task 1 file list omitted the architecture test that denies unreviewed provider capabilities, but the new read methods could not remain mechanically constrained without updating it.
- **Fix:** Added only `compare_repository_ancestry` and `list_repository_diffstat` to the closed allowed adapter-method set; the three Phase 8 writes remain declarations with no callable transport.
- **Files modified:** `backend/tests/architecture/test_provider_boundaries.py`
- **Verification:** The aggregate provider/import/architecture suite passes 109/109 tests.
- **Committed in:** `91d51b6`

---

**Total deviations:** 1 auto-fixed (1 Rule 2 missing critical verification)
**Impact on plan:** The added test-only file preserves the existing security boundary without expanding production scope.

## Issues Encountered

- The first RED staging command retained `backend` as its shell directory and therefore addressed a nonexistent nested path. Git staged and committed nothing; the exact test file was then staged from the repository root and committed normally as `caa30d2`.

## Verification

- Task 1 focused ancestry/diffstat suite: 15 passed.
- Task 1 provider/discovery/architecture aggregate: 65 passed.
- Task 2 focused classification suite: 18 passed.
- Final import/provider/discovery/architecture aggregate: 109 passed.
- Ruff check and format verification over all seven plan source/test targets: passed.
- Strict mypy over all four changed production modules: passed.

## TDD Gate Compliance

- Task 1 RED `f215bef` preceded GREEN `91d51b6` and its tracer was explicitly approved.
- Task 2 RED `caa30d2` failed on the absent classification contract before GREEN `e2313c7` passed the unchanged tests.
- No refactor commit was required after the focused, aggregate, formatting, lint, and type gates.

## Known Stubs

None. No placeholder, skipped test, TODO, FIXME, or unrun plan verification remains.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-09 can persist only `review-required` candidates whose complete mapping-scoped identity and metadata passed this classifier.
- Proven fast-forwards and exact equality are available as closed service outcomes for integration with the durable import state machine.
- No Plan 03-08 blocker remains; provider mutation operations remain unavailable until Phase 8.

## Self-Check: PASSED

- All eight implementation/test artifacts exist.
- RED/GREEN commits `f215bef`, `91d51b6`, `caa30d2`, and `e2313c7` are present in repository history.
- Summary status, requirement traceability, verification evidence, TDD order, threat-boundary disposition, and known-stub inventory are complete.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-03*
