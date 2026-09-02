---
phase: 03-bitbucket-import-integration
plan: 05
subsystem: bitbucket-provider-boundary
tags: [bitbucket, httpx, oauth2, ssrf, tdd, architecture]

requires:
  - phase: 03-bitbucket-import-integration
    plan: 03
    provides: Exact pullrequest:write capability profile and generation-bound read lease
provides:
  - One-attempt generation-current provider reads with closed safe failure kinds
  - Application-owned operation vocabulary split into seven Phase 3 reads and three non-executable Phase 8 mutations
  - Operation-specific URL validation and exact 56-row Bitbucket API coverage reconciliation
affects: [03-06, 03-08, phase-08, bitbucket-imports]

actuals:
  tokens: 12615
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Every authenticated provider request is bound to a closed operation before lease acquisition
    - Later branch, source-commit, and pull-request writes are declarations without callable transport
    - Provider continuation paths remain bound to the originating repository resource

key-files:
  created: []
  modified:
    - backend/src/verboflex/integrations/bitbucket/client.py
    - backend/src/verboflex/integrations/bitbucket/urls.py
    - backend/tests/integration/test_bitbucket_http_adapter.py
    - backend/tests/integration/test_bitbucket_discovery.py
    - backend/tests/architecture/test_provider_boundaries.py

key-decisions:
  - "Use one ten-value application vocabulary: seven Phase 3 read operations and exactly three Phase 8 write declarations for branch creation, source commit creation, and pull-request creation."
  - "Reject non-read operations and operation/URL mismatches before credential acquisition; the Phase 3 adapter retains a GET-only public surface."
  - "Accept response scope evidence only when pullrequest:write is present within its exact documented implication closure, with no duplicates or unexpected scopes."
  - "Pin branch-list continuation paths to the originally configured repository so same-host cross-repository pagination cannot reuse authority."

patterns-established:
  - "Operation-first validation: BitbucketOperation and its phase partitions are checked before any lease is acquired."
  - "Coverage equality: all 56 reviewed Bitbucket capabilities have exactly one INTEGRATE or OPT-OUT disposition."

requirements-completed: [BITB-02, BITB-06]

coverage:
  - id: D1
    description: Provider authentication, permission, rate-limit, missing-source, timeout, unavailable, redirect, decoding, continuation, and budget failures stop after one request with closed safe metadata.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_bitbucket_http_adapter.py::test_provider_status_failures_are_closed_and_one_attempt
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_bitbucket_http_adapter.py::test_reconnect_or_revoke_discards_stale_provider_results
        status: pass
    human_judgment: false
  - id: D2
    description: Phase 3 executes only operation-bound GET reads while the three approved future mutations remain non-executable declarations.
    requirement: BITB-02
    verification:
      - kind: unit
        ref: backend/tests/architecture/test_provider_boundaries.py::test_operation_vocabulary_separates_phase_three_reads_from_phase_eight_writes
        status: pass
      - kind: unit
        ref: backend/tests/architecture/test_provider_boundaries.py::test_operation_and_url_are_rejected_before_credential_acquisition
        status: pass
      - kind: unit
        ref: backend/tests/architecture/test_provider_boundaries.py::test_http_adapter_exports_only_current_read_capabilities_and_get_transport
        status: pass
    human_judgment: false
  - id: D3
    description: The complete 56-row Phase 3 Bitbucket capability ledger is reconciled exactly once with no silent additions or omissions.
    requirement: BITB-02
    verification:
      - kind: unit
        ref: backend/tests/architecture/test_provider_boundaries.py::test_phase_three_coverage_accounts_for_all_56_capabilities_exactly_once
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-09-02
status: complete
---

# Phase 03 Plan 05: Provider Operation Boundary Summary

**A closed ten-operation vocabulary now confines Phase 3 to generation-current one-attempt GET reads while preserving only three inert Phase 8 mutation declarations.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-09-02T21:31:09Z
- **Completed:** 2026-09-02T21:43:54Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added distinct closed failures for provider status, transport, decoding, limits, local connection state, and stale generations without retaining provider bodies or unsafe request details.
- Bound every adapter read to an application-owned operation and an operation-specific HTTPS `api.bitbucket.org` path before acquiring a credential lease.
- Declared only branch creation, source commit creation, and pull-request creation for Phase 8 while keeping every Phase 3 resource request GET-only and every write non-executable.
- Reconciled all 56 Phase 3 coverage rows exactly once and pinned branch pagination to the original repository path.

## Task Commits

Each TDD task has a genuine RED commit followed by its GREEN implementation:

1. **Task 1 RED: bounded provider read failures** - `1d95f6a` (test)
2. **Task 1 GREEN: one-attempt closed provider failures** - `ce8a76f` (feat)
3. **Task 2 RED: closed operation and 56-row policy** - `8f4bd89` (test)
4. **Task 2 GREEN: operation-bound read adapter** - `0b58efe` (feat)

## Files Created/Modified

- `backend/src/verboflex/integrations/bitbucket/client.py` - Carries safe failure metadata, binds reads to operations, validates expanded capability evidence, and preserves generation-current one-attempt GET transport.
- `backend/src/verboflex/integrations/bitbucket/urls.py` - Defines the closed operation vocabulary, phase partitions, and operation-specific URL families.
- `backend/tests/integration/test_bitbucket_http_adapter.py` - Proves one request per failure, closed status kinds, secret-safe errors, and stale-generation rejection.
- `backend/tests/integration/test_bitbucket_discovery.py` - Proves expanded scope reads, bounded continuations, and same-host cross-repository continuation rejection.
- `backend/tests/architecture/test_provider_boundaries.py` - Freezes exact operation partitions, adapter methods, GET-only transport, and all 56 coverage dispositions.

## Decisions Made

- Commit ancestry and diffstat are Phase 3 read operations in the vocabulary, but their endpoint path families remain closed until Plan 03-08 implements their bounded readers.
- Scope evidence must include `pullrequest:write` and may contain only its documented implication closure. Legacy repository-only evidence cannot satisfy the provider read boundary.
- The adapter exposes no generic provider request method; all public entry points remain named read capabilities.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Updating the provider capability contract required existing integration fixtures to represent the expanded `pullrequest:write` authority instead of the superseded repository-only header. No production compatibility path was retained.

## Verification

- `uv run pytest tests/integration/test_bitbucket_http_adapter.py tests/integration/test_bitbucket_discovery.py tests/architecture/test_provider_boundaries.py -x` — 51 passed.
- `uv run pytest tests/integration/test_bitbucket_oauth.py tests/integration/test_bitbucket_http_adapter.py tests/integration/test_bitbucket_discovery.py tests/architecture/test_provider_boundaries.py -x` — 64 passed.
- Ruff over the two production modules and three test modules — passed.
- mypy over the two production modules — passed.

## TDD Gate Compliance

- Task 1 has RED commit `1d95f6a` before GREEN commit `ce8a76f`.
- Task 2 has RED commit `8f4bd89` before GREEN commit `0b58efe`.
- No refactor commit was required; the focused and aggregate provider suites remained green.

## Known Stubs

None. The future write values are intentionally non-executable policy declarations owned by Phase 8, not incomplete Phase 3 behavior.

## User Setup Required

None for this plan. The expanded OAuth consumer grant and reconnection are owned by Plan 03-03.

## Next Phase Readiness

- Plan 03-06 can add structured server-only diagnostics without widening public error metadata.
- Plan 03-08 can attach bounded ancestry and diffstat GET paths to their already-declared read operations.
- Phase 8 has exactly three predeclared mutation families and still cannot execute them through the Phase 3 adapter.

## Self-Check: PASSED

- All five modified implementation and test files exist.
- Commits `1d95f6a`, `ce8a76f`, `8f4bd89`, and `0b58efe` are present in history.
- All plan verification commands passed and no skipped tests, stubs, or unrun checks remain.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-02*
