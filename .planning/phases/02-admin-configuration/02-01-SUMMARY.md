---
phase: 02-admin-configuration
plan: 01
subsystem: auth-api
tags: [fastapi, sqlalchemy, postgresql, oauth2, rbac, tdd]

requires:
  - phase: 01-platform-foundation
    provides: Provider-independent internal users, additive roles, bearer authority, sessions, password hashing, and CLI bootstrap/reset mechanics
provides:
  - Administrator-only internal-user list, create, update, reset, deactivate, and reactivate API
  - Fixed-order additive role assignment across all 15 non-empty role combinations on one User UUID
  - Transactional self-admin and last-active-admin protection under concurrent mutations
  - Shared CLI and HTTP credential/lifecycle authority with one-time temporary secrets
affects: [02-17-admin-configuration-ui, 02-20-phase-gauntlet, user-administration, authorization]

actuals:
  tokens: 30712
  tasks: 2
  commits: 10

tech-stack:
  added: []
  patterns:
    - Transaction-scoped PostgreSQL advisory lock plus actor and target row locks for administrative authority changes
    - Shared service authority reused by HTTP routes and CLI wrappers
    - Normalized equality check before any token, role, password, or session mutation

key-files:
  created:
    - backend/src/verboflex/api/v1/routes/admin_users.py
    - backend/src/verboflex/schemas/admin_users.py
    - backend/src/verboflex/services/admin_users.py
    - backend/tests/integration/test_admin_user_concurrency.py
    - backend/tests/unit/services/test_admin_users.py
  modified:
    - backend/src/verboflex/api/v1/router.py
    - backend/src/verboflex/cli.py
    - backend/tests/api/test_admin_users.py
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json

key-decisions:
  - "Keep the Phase 1 User UUID as the sole identity while roles remain additive many-to-many authority memberships."
  - "Serialize every administrative authority mutation with the existing global advisory lock, then re-read and lock actor and target rows before validating prospective state."
  - "Treat normalized identical display-name and role updates as true no-ops: no token-version advance, session revocation, or relationship rewrite."
  - "Delegate existing CLI reset/deactivation commands to the same transactional service used by HTTP instead of creating a colliding cli/users.py package path."

patterns-established:
  - "Lifecycle authority: validate current admin, target lifecycle, and last-admin survival inside one serialized transaction before mutation."
  - "Credential replacement: generate plaintext once, persist only its hash, advance authority exactly once, revoke sessions, and expose plaintext only in a successful one-time response."
  - "Closed admin API: every route shares the database-backed bearer/admin dependency and maps only bounded 401/403/404/409/422 responses."

requirements-completed: [AUTH-02, AUTH-03]

coverage:
  - id: D1
    description: "An active administrator can list and create internal users with stable opaque pagination and one-time credentials."
    requirement: AUTH-02
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_users.py#test_active_admin_creates_user_and_receives_one_non_persistent_temporary_password"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_admin_users.py#test_user_list_has_stable_opaque_default_and_maximum_pagination"
        status: pass
    human_judgment: false
  - id: D2
    description: "All 15 supported non-empty additive role combinations round-trip in fixed order on the same User UUID."
    requirement: AUTH-03
    verification:
      - kind: unit
        ref: "backend/tests/unit/services/test_admin_users.py#test_every_non_empty_role_combination_round_trips_on_the_same_user_uuid"
        status: pass
    human_judgment: false
  - id: D3
    description: "Self-admin removal and last-active-admin removal or deactivation fail atomically, including concurrent requests."
    requirement: AUTH-02
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_admin_user_concurrency.py#test_concurrent_cross_deactivation_cannot_remove_the_last_active_admin"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_admin_user_concurrency.py#test_concurrent_cross_role_removal_cannot_remove_the_last_active_admin"
        status: pass
    human_judgment: false
  - id: D4
    description: "Normalized identical display-name and role submissions are non-mutating no-ops."
    requirement: AUTH-02
    verification:
      - kind: unit
        ref: "backend/tests/unit/services/test_admin_users.py#test_identical_normalized_update_is_a_non_mutating_noop"
        status: pass
    human_judgment: false
  - id: D5
    description: "Reset and reactivation issue fresh one-time credentials, invalidate prior credentials and sessions, and advance authority once."
    requirement: AUTH-02
    verification:
      - kind: unit
        ref: "backend/tests/unit/services/test_admin_users.py#test_reset_and_reactivation_always_issue_fresh_credentials_and_revoke_authority"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_admin_user_concurrency.py#test_concurrent_resets_serialize_and_only_the_last_committed_secret_is_valid"
        status: pass
    human_judgment: false
  - id: D6
    description: "Every lifecycle endpoint shares the bearer/admin guard, bounded status contract, rejection no-mutation rule, and one-time plaintext schema."
    requirement: AUTH-02
    verification:
      - kind: integration
        ref: "backend/tests/api/test_admin_users.py#test_every_admin_user_endpoint_uses_the_same_bearer_and_admin_guard_without_mutation"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_openapi_contract.py#test_admin_user_openapi_keeps_temporary_credentials_on_one_time_responses_only"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-08-26
status: complete
---

# Phase 02 Plan 01: Internal-user and Additive-role Administration Summary

**A database-authorized FastAPI administration surface now manages one stable internal-user identity through additive roles and serialized credential/lifecycle changes without leaking temporary secrets.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-08-26T19:53:18Z
- **Completed:** 2026-08-26T20:28:24Z
- **Tasks:** 2
- **Files modified:** 11 implementation and test artifacts
- **Actual estimate scale:** 30,712 tokens (122,846 realized diff characters / 4)

## Accomplishments

- Shipped closed administrator-only list, create, update, password reset, deactivate, and reactivate operations over the existing bearer and database authority model.
- Preserved the Phase 1 User UUID across all 15 supported non-empty role combinations, with deterministic role ordering and normalized no-op semantics.
- Protected self-admin and last-active-admin invariants with a global advisory lock, row locks, prospective-state validation, and real PostgreSQL concurrency tests.
- Unified CLI and HTTP lifecycle mechanics so every password replacement uses fresh one-time plaintext, persists only a hash, advances authority once, and revokes live sessions.
- Regenerated the canonical OpenAPI artifact and proved one-time credential fields occur only on successful create, reset, and reactivate responses.

## Task Commits

Each TDD gate and follow-up test/format correction was committed atomically:

1. **Task 1 RED: guarded admin-user tracer contract** — `9c39ae6` (test)
2. **Task 1 GREEN: guarded admin-user tracer** — `a8718cd` (feat)
3. **Task 1 REFACTOR: service boundary cleanup** — `6317721` (refactor)
4. **Task 2 RED: lifecycle, role, concurrency, CLI, and OpenAPI contract** — `75a473b` (test)
5. **Task 2 RED correction: scope OpenAPI success-response assertion** — `4c591be` (test)
6. **Task 2 RED formatting** — `0827be1` (style)
7. **Task 2 GREEN: lifecycle and additive-role authority** — `de01cb4` (feat)
8. **Task 2 REFACTOR: lifecycle contract projection cleanup** — `14170e3` (refactor)
9. **Task 2 test armor: lifecycle rejection branches** — `9b47f8c` (test)
10. **Task 2 quality-gate formatting** — `7dcc02b` (style)

Plan metadata is committed separately with this summary and the synchronized planning state.

## TDD Gate Evidence

- **Task 1 RED:** the focused API contract failed because the guarded admin-user route/service did not exist (`9c39ae6`).
- **Task 1 GREEN:** the unchanged focused command passed 7/7 after minimal tracer implementation (`a8718cd`).
- **Task 1 REFACTOR:** the unchanged focused command remained 7/7 (`6317721`); the user then approved the mandatory tracer feedback gate.
- **Task 2 RED:** after resolving test collection namespace isolation, the unchanged focused command failed on the intended missing `update_admin_user` service behavior (`75a473b`).
- **Task 2 GREEN:** the unchanged focused command passed 40/40 (`de01cb4`).
- **Task 2 REFACTOR:** the unchanged focused command remained 40/40 (`14170e3`).
- **Final focused proof:** the exact Task 2 and plan-level commands each pass 44/44 after rejection-branch armor.

## Verification and Gauntlet Evidence

- Exact Task 2 command: **44 passed**.
- Exact plan-level command: **44 passed**.
- Phase 1 CLI regression suite: **24 passed**.
- Full backend suite with PostgreSQL, ephemeral Redis 7, and a real Celery solo worker: **306 passed**.
- Ruff lint and formatting: **65 files checked, pass**.
- mypy: **39 source files, pass**.
- Focused Task 2 plus CLI coverage suite: **68 passed**; Task 2 differential coverage against the approved tracer commit is **100% (179/179 changed lines)**.
- Four targeted negative-control mutants covering inactive reset, authority status mapping, normalized input mapping, and unexpected-error propagation were all killed (**4/4**).
- Dependency graph is unchanged; no package installation or supply-chain expansion occurred.
- Stub scan found no production placeholders, TODOs, FIXMEs, or empty UI-bound values in changed artifacts.

## Files Created/Modified

- `backend/src/verboflex/services/admin_users.py` — single transactional authority for user creation, roles, lifecycle, credentials, session revocation, pagination, and CLI reuse.
- `backend/src/verboflex/api/v1/routes/admin_users.py` — closed administrator HTTP routes and bounded lifecycle error projection.
- `backend/src/verboflex/schemas/admin_users.py` — fixed-role request normalization and secret-bearing versus ordinary response boundaries.
- `backend/src/verboflex/api/v1/router.py` — registers the admin-user router.
- `backend/src/verboflex/cli.py` — preserves existing CLI entry points while delegating reset and deactivation to the shared service.
- `backend/tests/unit/services/test_admin_users.py` — role matrix, no-op, lifecycle credential, self-admin, and CLI reuse proofs.
- `backend/tests/integration/test_admin_user_concurrency.py` — real PostgreSQL last-admin and concurrent-reset serialization proofs.
- `backend/tests/api/test_admin_users.py` — authenticated lifecycle, denial, status, no-mutation, pagination, and secret-boundary proofs.
- `backend/tests/api/test_openapi_contract.py` — exact admin-user OpenAPI and one-time credential placement proof.
- `frontend/openapi.json` — canonical generated API contract consumed by the frontend.

## Decisions Made

- Retained one provider-independent User UUID as the only identity; roles change authorization memberships, never identity.
- Reused the Phase 1 transaction advisory lock and added row-level revalidation so authorization cannot become stale between dependency resolution and mutation.
- Kept role serialization in the fixed enum order and detected normalized equality before relationship replacement or authority invalidation.
- Preserved the existing `verboflex.cli` public module and console entry point while moving durable mechanics into the shared service.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking path] Reused the existing CLI module instead of creating a colliding package**
- **Found during:** Task 2
- **Issue:** The plan named `backend/src/verboflex/cli/users.py`, but the repository already exposes `backend/src/verboflex/cli.py` as the public module and console entry point; adding a same-name package would alter imports and entry-point behavior.
- **Fix:** Kept public wrappers in `cli.py` and delegated their database mechanics to `services/admin_users.py`.
- **Files modified:** `backend/src/verboflex/cli.py`, `backend/src/verboflex/services/admin_users.py`
- **Verification:** Phase 1 CLI regressions pass 24/24 and the Task 2 CLI reuse unit proof passes.
- **Committed in:** `de01cb4`

**2. [Rule 3 - Blocking collection] Isolated duplicate test module basenames**
- **Found during:** Task 2 RED
- **Issue:** Pytest collection confused the new unit service module with the existing API module because both were named `test_admin_users.py` outside a package namespace.
- **Fix:** Added `backend/tests/unit/services/__init__.py` so pytest imports the unit suite through an unambiguous package path.
- **Files modified:** `backend/tests/unit/services/__init__.py`
- **Verification:** The exact RED command then reached and failed on the intended missing service behavior; final focused commands pass 44/44.
- **Committed in:** `75a473b`

**3. [Rule 1 - Test bug] Restricted the OpenAPI success-response assertion to lifecycle routes owned by this plan**
- **Found during:** Task 2 RED
- **Issue:** An initial test revision accidentally required a `200` response schema on unrelated protected routes such as logout.
- **Fix:** Scoped the assertion to the admin-user surface while retaining global bearer-security checks.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`
- **Verification:** RED still failed on missing production behavior and the canonical OpenAPI suite passes.
- **Committed in:** `4c591be`

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking issues).
**Impact on plan:** All corrections preserved the approved architecture and strengthened executable evidence; no feature or dependency scope was added.

## Issues Encountered

- The first full-suite attempt lacked Redis/Celery runtime services. An ephemeral Redis container and real worker were started automatically.
- Celery's prefork pool terminated with a macOS/Python 3.14 segmentation fault before executing tests; the supported solo pool provided the same real broker/worker boundary for the smoke run, which passed 306/306. Both worker and container were stopped after verification.

## Authentication Gates

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration or new dependency is required.

## Next Phase Readiness

- Plan 02-02 can build product configuration over the established Phase 1 identity and this plan's administrator authority.
- The later 02-17 UI plan can consume the canonical admin-user OpenAPI surface, including deliberate one-time credential acknowledgement flows.
- `AUTH-02` and `AUTH-03` are complete for this backend plan but remain pending in the cross-phase requirement ledger until their shared UI and final-gauntlet plans (02-17 and 02-20) also complete.

## Self-Check: PASSED

- All 11 implementation/test artifacts listed above exist.
- All 10 Task 1 and Task 2 commits exist on `codex/phase-2-admin-configuration` in RED → GREEN → REFACTOR order.
- Exact focused, plan-level, CLI regression, lint, format, type, differential coverage, mutation-control, and full backend smoke claims were rerun after the final source/test changes.
- No tracked file deletion, unresolved stub, unrun verification, or unintended generated artifact remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-26*
