---
phase: 03-bitbucket-import-integration
plan: 03
subsystem: bitbucket-oauth
tags: [bitbucket, oauth2, fastapi, pydantic, security, tdd]

requires:
  - phase: 03-bitbucket-import-integration
    plan: 01
    provides: Durable import tracer and generation-current repository-read authority
  - phase: 02-admin-configuration
    plan: 35
    provides: Server-owned client-credentials acquisition and secret-free provider smoke boundary
provides:
  - Exact pullrequest:write acquisition with a closed documented implication allowlist
  - Legacy repository-only reauthorization and import-lease denial
  - Secret-free administrator capability profile for source reads, later source writes, and later pull requests
affects: [03-04, 03-05, 03-06, 03-07, 03-08, phase-08]

actuals:
  tokens: 8676
  tasks: 2
  commits: 7

tech-stack:
  added: []
  patterns:
    - Provider authority is validated once into a closed server capability profile
    - Browser projections remove credential generation and raw or effective provider authority
    - Future mutation readiness is descriptive and creates no executable provider-write route

key-files:
  created: []
  modified:
    - backend/src/verboflex/services/bitbucket_oauth.py
    - backend/src/verboflex/integrations/bitbucket/client.py
    - backend/src/verboflex/schemas/admin_bitbucket.py
    - backend/src/verboflex/api/v1/routes/admin_bitbucket.py
    - backend/tests/integration/test_bitbucket_oauth.py
    - backend/tests/api/test_admin_bitbucket.py
    - backend/tests/api/test_openapi_contract.py

key-decisions:
  - "Request exactly pullrequest:write and accept only its documented pull-request and repository implication closure; missing, duplicate, case-altered, or unexpected authority fails closed."
  - "Treat repository-only generations as locally revocable legacy credentials that require reauthorization and cannot issue an import lease."
  - "Expose capability evidence as exactly three closed readiness dimensions plus evaluation time; keep source generation and provider authority server-private."

patterns-established:
  - "Capability evidence: source_read, source_write, and pull_request are closed literals derived only from the server profile."
  - "Later-phase readiness remains data only; Phase 3 exposes no branch, source-commit, or pull-request mutation operation."

requirements-completed: [BITB-02, BITB-06]

coverage:
  - id: D1
    description: The organizational connection requests and validates exactly the approved expanded Bitbucket capability.
    requirement: BITB-02
    verification:
      - kind: integration
        ref: backend/tests/integration/test_bitbucket_oauth.py::test_exact_scope_accepts_only_pullrequest_write_implication_closure
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_bitbucket_oauth.py::test_capability_profile_is_closed_timestamped_and_generation_bound
        status: pass
    human_judgment: false
  - id: D2
    description: A legacy repository-only generation requires reauthorization and cannot authorize an import read.
    requirement: BITB-06
    verification:
      - kind: integration
        ref: backend/tests/integration/test_bitbucket_oauth.py::test_reauthorization_required_repository_generation_denies_import_lease
        status: pass
      - kind: integration
        ref: backend/tests/api/test_admin_bitbucket.py::test_legacy_authority_projects_reauthorization_required_capability
        status: pass
    human_judgment: false
  - id: D3
    description: Administrator status exposes three closed readiness dimensions without credentials, provider detail, generation identity, or provider-write affordances.
    requirement: BITB-02
    verification:
      - kind: integration
        ref: backend/tests/api/test_admin_bitbucket.py::test_capability_projection_is_recursive_forbidden_field_free
        status: pass
      - kind: unit
        ref: backend/tests/api/test_openapi_contract.py::test_admin_bitbucket_openapi_is_closed_bounded_and_secret_free
        status: pass
    human_judgment: false

duration: 22min
completed: 2026-09-02
status: complete
---

# Phase 03 Plan 03: Expanded Bitbucket OAuth Capability Summary

**Exact expanded Bitbucket OAuth authority now yields a generation-bound server profile and a secret-free administrator projection with no executable provider mutations.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-09-02T20:44:25Z
- **Completed:** 2026-09-02T21:06:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Replaced the obsolete requested repository authority with exact `pullrequest:write` acquisition and a closed documented implication validator.
- Preserved encrypted access-only rotation, expiry, renewal, and local revocation while denying import leases to legacy repository-only generations.
- Added one closed admin capability profile containing source-read, later source-write, and later pull-request readiness plus bounded evaluation time, without source generation or provider authority detail.
- Kept the public Bitbucket surface to status, connect, reconnect, and local revoke; no branch, commit, pull-request, merge, approval, decline, or repository-administration action was introduced.

## Task Commits

Each TDD task was committed as genuine RED evidence followed by GREEN behavior:

1. **Task 1 RED: expanded OAuth capability** - `25b0774` (test)
2. **Task 1 RED extension: legacy reauthorization profile** - `664fd8a` (test)
3. **Task 1 GREEN: exact authority and closed service profile** - `3618091` (feat)
4. **Task 1 regression fix: retained adapter scope import** - `0672ce3` (fix)
5. **Task 2 RED: closed administrator capability projection** - `3273f1d` (test)
6. **Task 2 GREEN: bounded readiness schema and route mapping** - `83a8465` (feat)
7. **Task 2 contract armor: canonical backend OpenAPI assertions** - `10ea0cf` (test)

## Files Created/Modified

- `backend/src/verboflex/services/bitbucket_oauth.py` - Requests exact expanded authority, validates its implication closure, classifies legacy generations, and creates closed capability evidence.
- `backend/src/verboflex/integrations/bitbucket/client.py` - Retains the explicitly named legacy response-scope check until the dedicated adapter hardening plan.
- `backend/src/verboflex/schemas/admin_bitbucket.py` - Defines the closed capability-readiness model and expanded application-owned profile label.
- `backend/src/verboflex/api/v1/routes/admin_bitbucket.py` - Projects service evidence without generation, credentials, raw scope, or provider detail.
- `backend/tests/integration/test_bitbucket_oauth.py` - Proves exact outbound scope, implication validation, lifecycle safety, and legacy lease denial.
- `backend/tests/api/test_admin_bitbucket.py` - Proves lifecycle readiness, administrator authorization, no-store responses, and recursive field exclusion.
- `backend/tests/api/test_openapi_contract.py` - Pins the expanded backend contract and forbidden provider metadata.

## Decisions Made

- The persisted `scope_profile` remains an internal generation classifier. The browser receives the application-owned `repository_and_pull_request` profile and closed readiness values, never the provider's scope response.
- Connected authority projects `ready` for source reads and `ready_for_later_phase` for source writes and pull requests. Other lifecycle states project the same closed state across all three dimensions.
- An unavailable configured service exposes unavailable readiness with no fabricated evaluation timestamp; service-derived profiles retain their actual bounded evaluation time.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Restored application importability after the tracer renamed the scope constant**

- **Found during:** Task 2 RED execution
- **Issue:** `BitbucketHttpAdapter` still imported the removed `REPOSITORY_SCOPE`, preventing FastAPI and the API test module from loading.
- **Fix:** Import and use the retained `LEGACY_REPOSITORY_SCOPE` name for the adapter's existing response-header validation. Plan 03-05 remains the owner of the broader adapter policy change.
- **Files modified:** `backend/src/verboflex/integrations/bitbucket/client.py`
- **Verification:** Imported `verboflex.main` successfully, then observed the intended Task 2 RED assertion failure.
- **Committed in:** `0672ce3`

**2. [Rule 2 - Critical contract] Updated the canonical backend OpenAPI security assertion**

- **Found during:** Plan regression verification
- **Issue:** The central OpenAPI test still required the superseded read-only schema and did not protect the new nested profile from generation or authority leakage.
- **Fix:** Pin the expanded application profile, exact readiness fields, exact closed unions, and recursive forbidden provider metadata.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`
- **Verification:** Focused backend OpenAPI contract test passes.
- **Committed in:** `10ea0cf`

---

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 2)
**Impact on plan:** Both fixes were necessary to keep the application importable and the canonical backend contract security-complete; no provider-write behavior or dependency was added.

## Issues Encountered

- The checked-in frontend OpenAPI artifact now intentionally differs from the canonical backend export. Plan 03-04 Task 1 owns the generated-client RED/GREEN cycle and will export and regenerate it; generated files were not edited in this plan.

## Verification

- `uv run pytest tests/integration/test_bitbucket_oauth.py tests/api/test_admin_bitbucket.py -x` — 21 passed.
- `uv run pytest tests/api/test_openapi_contract.py -x -k "admin_bitbucket"` — 1 passed.
- Focused plan predicates for capability, reauthorization, exact scope, import lease, and forbidden fields — 6 passed.
- Ruff over all seven touched Python files — passed.
- mypy over the four touched production modules — passed.

## TDD Gate Compliance

- Task 1 has RED commits `25b0774` and `664fd8a` before GREEN commit `3618091`.
- Task 2 has RED commit `3273f1d` before GREEN commit `83a8465`.
- No refactor commit was required; the unchanged focused suites remained green.

## Known Stubs

None. Nullable timestamps represent explicit disconnected or unavailable lifecycle state and do not feed placeholder UI data.

## User Setup Required

Before live expanded capability can be acquired, grant `pullrequest:write` to the organizational Bitbucket OAuth consumer and reconnect the global Bitbucket connection. No live provider mutation is performed by this plan.

## Next Phase Readiness

- Plan 03-04 can regenerate the canonical TypeScript client and render the approved capability profile from these closed backend fields.
- Plan 03-05 can harden the provider read adapter and replace its retained legacy response-scope compatibility check with the complete Phase 3 operation policy.
- No blocker remains for the next wave.

## Self-Check: PASSED

- All seven modified implementation and test files exist.
- All seven Task 1 and Task 2 commits are present in git history.
- Coverage metadata validates with all three deliverables automatically covered by passing tests.

---
*Phase: 03-bitbucket-import-integration*
*Completed: 2026-09-02*
