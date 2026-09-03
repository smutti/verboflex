---
phase: 02-admin-configuration
plan: 23
subsystem: auth
tags: [postgresql, sqlalchemy, cli, rbac, concurrency, tdd]

requires:
  - phase: 02-admin-configuration
    provides: Plan 02-01 administrator user lifecycle, additive roles, one-time credentials, and HTTP authority locking
provides:
  - One advisory-locked last-active-admin deactivation authority shared by HTTP and CLI adapters
  - Cross-entry-point PostgreSQL concurrency proof for lifecycle and role mutations
  - R1-R3 identity, ordering, idempotency, role-set, and fresh-credential regression matrix
affects: [phase-02-verification, admin-users, privileged-cli, authorization]

actuals:
  tokens: 7766
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Adapter-specific error mapping around one transaction-owned advisory-lock command
    - Canonical User UUID retained while roles remain fixed-order set membership
    - Bounded retry for generated credential policy collisions before authority mutation

key-files:
  created:
    - backend/tests/test_cli.py
  modified:
    - backend/src/verboflex/services/admin_users.py
    - backend/src/verboflex/cli.py
    - backend/tests/unit/services/test_admin_users.py
    - backend/tests/integration/test_admin_user_concurrency.py

key-decisions:
  - "Keep the canonical User UUID unchanged across every role plurality, ordering, lifecycle, and concurrency path; roles remain membership only."
  - "Route HTTP UUID and CLI normalized-email deactivation through one global authority lock, target lock, and survivor predicate."
  - "Retry generated temporary credentials only within a bounded policy-validation loop, never exposing rejected candidates."

patterns-established:
  - "Cross-entry survivor authority: acquire the global advisory lock before actor/target row locks and validate prospective active-admin state before mutation."
  - "Privileged adapter boundary: domain conflicts are shared; HTTP and CLI translate only their bounded transport/process outcomes."

requirements-completed: [AUTH-02, AUTH-03]

coverage:
  - id: D1
    description: "CLI and HTTP deactivation share one serialized survivor-safe authority and cannot remove the final active administrator."
    requirement: AUTH-02
    verification:
      - kind: integration
        ref: "backend/tests/test_cli.py#test_cli_sole_admin_deactivation_fails_without_changing_authority"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_admin_user_concurrency.py#test_cross_entry_cli_and_http_deactivation_preserve_one_active_admin_and_both_uuids"
        status: pass
    human_judgment: false
  - id: D2
    description: "Normalized email, deterministic ordering, role-set permutations, repetition, and concurrent lifecycle changes preserve one User UUID."
    requirement: AUTH-03
    verification:
      - kind: integration
        ref: "backend/tests/unit/services/test_admin_users.py#test_edge_r1_adjacency_empty_ordering_and_idempotency_preserve_rows"
        status: pass
      - kind: integration
        ref: "backend/tests/unit/services/test_admin_users.py#test_edge_r2_role_set_encoding_ordering_and_idempotency_preserve_uuid"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_admin_user_concurrency.py#test_concurrent_cli_lifecycle_and_http_role_mutation_preserve_authority_identity"
        status: pass
    human_judgment: false
  - id: D3
    description: "Repeated and concurrent credential changes leave only the final committed credential valid and keep every candidate out of captured logs."
    requirement: AUTH-02
    verification:
      - kind: integration
        ref: "backend/tests/unit/services/test_admin_users.py#test_edge_r3_repeated_authority_changes_retry_collisions_and_redact_candidates"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_admin_user_concurrency.py#test_concurrent_resets_serialize_and_only_the_last_committed_secret_is_valid"
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 23: Cross-entry Administrator Survivor Authority Summary

**CLI and HTTP user deactivation now converge on one PostgreSQL-serialized survivor invariant, backed by UUID-preserving role and credential concurrency tests.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-08-29T15:08:29Z
- **Completed:** 2026-08-29T15:21:18Z
- **Tasks:** 2
- **Files modified:** 5
- **Actual estimate scale:** 7,766 tokens (31,062 realized diff characters / 4)

## Accomplishments

- Removed the privileged CLI bypass around D-05 by sharing the HTTP advisory lock, target lock, prospective survivor check, revocation, and token-version transition.
- Proved CLI-versus-HTTP deactivation and CLI-lifecycle-versus-HTTP-role races always retain one active administrator and both canonical User UUID rows.
- Added named R1-R3 coverage for normalized email adjacency, empty pages, deterministic ordering, idempotent creates/updates, fixed-order role sets, zero-role rejection, credential repetition, and concurrent final authority.
- Made generated reset/reactivation credentials retry bounded candidate-policy collisions while keeping rejected candidates outside responses and logs.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1 RED: CLI survivor authority specification** — `fa7e31a` (test)
2. **Task 1 GREEN: shared locked deactivation authority** — `c2f36b7` (feat)
3. **Task 2 RED: cross-entry R1-R3 authority matrix** — `2c5eb3c` (test)
4. **Task 2 GREEN: guaranteed fresh temporary authority** — `37b8c8e` (feat)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 1 RED:** the exact focused command failed because sole-admin CLI deactivation returned success and changed authority instead of producing the shared lifecycle conflict.
- **Task 1 GREEN:** the unchanged focused command passed after both adapters used `_deactivate_user_under_admin_authority_lock`.
- **Task 2 RED:** the R1-R3 matrix failed because repeated generated credential material aborted a reset instead of retrying to issue fresh authority.
- **Task 2 GREEN:** the unchanged Task 2 command passed 30/30 after bounded candidate-policy retry was added.
- No refactor commit was needed; the GREEN implementations already retained the established service and adapter boundaries.

## Verification and Acceptance Evidence

- Exact Task 1 command: **27 passed**.
- Exact Task 2 command: **30 passed**.
- Existing administrator HTTP regression suite: **15 passed**.
- PostgreSQL concurrency suite repeated five additional times: **6 passed per run**, with one active administrator after every race.
- mypy: **2 source files checked, pass**.
- CLI adapter source inspection: **pass**; the deactivation wrapper contains no row-state assignment or transaction ownership.
- Identity assertions retain the original User UUID across every role permutation and concurrent lifecycle outcome.
- Captured-log assertions found no generated credential candidate in service or concurrency logs.

## Files Created/Modified

- `backend/src/verboflex/services/admin_users.py` — shared deactivation command and bounded fresh-credential generation.
- `backend/src/verboflex/cli.py` — deterministic process mapping for the shared last-admin domain conflict.
- `backend/tests/test_cli.py` — CLI survivor behavior, bounded rejection, and delegation proofs.
- `backend/tests/unit/services/test_admin_users.py` — R1-R3 edge and UUID-preservation matrix.
- `backend/tests/integration/test_admin_user_concurrency.py` — real PostgreSQL cross-entry and identity-preserving race proofs.

## Decisions Made

- Preserved the no-change assumption-delta decision: one canonical User UUID remains primary identity and roles are only fixed-vocabulary set membership.
- Kept transaction ownership in the existing public service adapters while centralizing all deactivation authority after the same global lock.
- Bounded fresh-credential collision retries to eight attempts and fail closed with a non-secret internal error if generation cannot produce valid new authority.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Authentication Gates

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration or dependency change is required.

## Next Phase Readiness

- CR-10 / verifier gap G1 is closed with executable CLI, service, HTTP-regression, and cross-entry concurrency evidence.
- The shared `AUTH-02` and `AUTH-03` requirement IDs remain ledger-pending until all later Phase 2 gap-closure plans that also declare them are summarized.
- Ready for Plan 02-24 and the remaining Phase 2 gap-closure sequence.

## Self-Check: PASSED

- All five implementation/test artifacts and this summary exist.
- All four TDD commits exist in RED → GREEN → RED → GREEN order.
- Coverage metadata validates with three fully automated deliverables and no schema errors.
- Required focused, API regression, concurrency-repeat, type, and CLI source-inspection checks pass.
- No tracked deletion, generated dependency change, stub, skipped test, unrun verification, or unmodeled threat surface remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
