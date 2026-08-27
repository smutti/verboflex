---
status: resolved
trigger: "Fix the randomized admin-user role-order isolation defect surfaced after Phase 02 Plan 04"
created: 2026-08-27
updated: 2026-08-27T10:44:57+02:00
---

# Debug Session: Randomized Admin Role Order

## Symptoms

- **Expected behavior:** Every supported non-empty role combination round-trips in `FIXED_ROLE_ORDER`, independently of pytest execution order or seed.
- **Actual behavior:** The default `pytest-randomly` full backend suite produced two role-order assertion failures, while the unchanged parametrized test passes 15/15 in isolation and the deterministic suite passes 343/343 with `--randomly-dont-reorganize`.
- **Error:** Persisted `target.roles` order differed from `FIXED_ROLE_ORDER` in `tests/unit/services/test_admin_users.py::test_every_non_empty_role_combination_round_trips_on_the_same_user_uuid`.
- **Timeline:** First observed during Phase 02 Plan 04 after the admin-user lifecycle shipped in Plan 02-01.
- **Reproduction:** Run the full backend suite with the default pytest-randomly ordering and capture the failing seed/cases; compare against the same cases in isolation.

## Current Focus

- **hypothesis:** CONFIRMED — `User.roles` omits relationship `order_by`, so SQLAlchemy/PostgreSQL may expose arbitrary association query order even though service records are separately canonicalized.
- **bug_class:** heisenbug-mandelbug — the missing deterministic mapping contract is always observable, while the user-facing order defect depends on incidental query/row order.
- **test:** Human confirmation in the real admin-user workflow: update a user with multiple roles, reload it, and inspect the role sequence.
- **expecting:** Every reload presents roles in `admin`, `product_manager_reviewer`, `translator`, `viewer` order with omitted roles skipped.
- **next_action:** COMPLETE — human verification confirmed the original workflow is fixed; archive the session and commit the scoped fix, regression, and resolution records with hooks.
- **reasoning_checkpoint:**
  - hypothesis: `User.roles` returns noncanonical order because its SQLAlchemy relationship has no `order_by`, leaving database row order unspecified.
  - confirming_evidence:
    - Under seed 4, five cases failed only when asserting direct `target.roles`; the separately canonicalized `updated.roles` projection passed.
    - The deterministic mapper-contract regression directly observed `User.roles.property.order_by is False`.
  - falsification_test: If adding `order_by="Role.name"` does not make `User.roles.property.order_by` equal `roles.name`, or if deleting that line does not restore the RED regression, this hypothesis is false.
  - fix_rationale: Declaring ordering on the relationship fixes the read boundary that exposed unspecified database order, so all callers receive the role collection in the domain's fixed order.
  - blind_spots: The original five-case failure also depended on process/row-layout state and may not replay on every fresh database; production-like PostgreSQL verification therefore includes the full randomized suite with the preserved seed.
  - candidate_causes:
    - code: `User.roles` lacks relationship `order_by` despite a fixed-order domain contract.
    - environment/config: pytest-randomly and PostgreSQL plan selection alter when unspecified result order becomes visible, but cannot guarantee or repair ordering.
    - data: association-row churn changes incidental row layout, but a declared relationship order makes layout irrelevant.
  - and_gate: no — the missing ORM ordering alone violates the fixed-order contract; seed, planner, and row layout only expose the latent defect.
- **tdd_checkpoint:**
  - test_file: backend/tests/unit/services/test_admin_users.py
  - test_name: test_user_roles_relationship_declares_fixed_role_order
  - status: green
  - failure_output: "RED before fix: assert relationship_order is not False; E assert False is not False"

## Evidence

- timestamp: 2026-08-27T10:01:29+02:00
  checked: Phase 0 semantic and keyword knowledge-base recall
  found: MemPalace is not installed and `.planning/debug/knowledge-base.md` does not exist, so no prior-session candidate is available.
  implication: Proceed with fresh evidence gathering; the durable keyword fallback also has no entries to match.
- timestamp: 2026-08-27T10:02:10+02:00
  checked: Complete admin-user service, `User`/`Role` mappings, role seed migration, test module, and pytest configuration
  found: `_load_requested_roles` and `_to_record` explicitly canonicalize `FIXED_ROLE_ORDER`, but the many-to-many `User.roles` relationship has no `order_by`; the regression's second assertion directly compares this unordered relationship collection to the canonical service projection.
  implication: The persistence contains the correct role set, but ORM read order is not contracted; reproduce before treating this as the confirmed root cause.
- timestamp: 2026-08-27T10:03:23+02:00
  checked: Full backend suite under generated pytest-randomly seed 2974387314
  found: All 19 admin-user service cases passed; 341/343 tests passed. The only failures were pre-existing live Redis/worker smoke checks because port 56379 had no service.
  implication: Role ordering is seed-dependent but deterministic for a given seed; this run neither confirms nor eliminates the unordered relationship hypothesis. Worker failures are outside this debug scope and environmental.
- timestamp: 2026-08-27T10:03:23+02:00
  checked: SBFL Phase 1.25 eligibility
  found: Skipped because the current reproducible run has no failing role-order test and no per-test coverage spectrum for a failing/passing role case.
  implication: Use deterministic seed replay and differential debugging instead of an invalid spectrum ranking.
- timestamp: 2026-08-27T10:04:02+02:00
  checked: Phase 02 summaries, deferred-items ledger, and git history for the original seed
  found: The two failures and deterministic 343-pass comparison are recorded, but the generated pytest-randomly seed and concrete failing parameter IDs were not preserved.
  implication: Derive a stable reproducing seed with a bounded deterministic sample and record it as the regression provenance.
- timestamp: 2026-08-27T10:04:53+02:00
  checked: Targeted parametrized regression under `--randomly-seed=0`
  found: All 15 combinations passed in 1.43 seconds.
  implication: Seed 0 is a working differential case; it does not disprove unspecified ORM ordering because row insertion order may also depend on process allocation and preceding test execution.
- timestamp: 2026-08-27T10:05:18+02:00
  checked: Targeted parametrized regression under `--randomly-seed=1`
  found: All 15 combinations passed in 1.44 seconds; the intended multi-seed shell loop then stopped because `status` is a read-only zsh parameter.
  implication: Seed 1 is another working case; resume the bounded sample with a non-reserved result variable.
- timestamp: 2026-08-27T10:06:25+02:00
  checked: Targeted parametrized regression stability sample under fixed seeds 2 through 20
  found: Every seed passed all 15 combinations, with 19 consecutive zero-failure runs.
  implication: Parameter reordering alone is insufficient; the trigger likely also requires prior service-module database churn or process state, an AND-gate candidate spanning code ordering and test data history.
- timestamp: 2026-08-27T10:06:25+02:00
  checked: Bug taxonomy after 21 targeted working seeds and one prior unseeded failure report
  found: Provisionally classified as heisenbug-mandelbug because the failure is transient until a stable order seed is found; the earlier SBFL step was skipped, so no flaky ranking needs revocation.
  implication: Use bounded stability sampling and differential prior-state tests; reclassify if fixed-seed replay becomes deterministic.
- timestamp: 2026-08-27T10:06:59+02:00
  checked: Complete admin-user service module under `--randomly-seed=0`
  found: All 19 service cases passed in 2.44 seconds.
  implication: Seed 0 remains a working module-order case; sample additional stable module orders before expanding to full-suite state.
- timestamp: 2026-08-27T10:07:47+02:00
  checked: Complete service module under stable seeds 1 through 4
  found: Seeds 1, 2, and 3 passed 19/19. Seed 4 failed five parametrized cases (`requested_roles10`, `11`, `13`, `12`, and `6`), every failure at line 159 where direct `target.roles` order is compared; the canonical `updated.roles` assertion at line 156 passed.
  implication: Stable seed 4 reproduces the exact defect and differentiates persistence/ORM read ordering from service response projection.
- timestamp: 2026-08-27T10:07:47+02:00
  checked: Bug taxonomy after stable seed discovery
  found: Reclassified from provisional heisenbug-mandelbug to order-dependent Bohrbug because seed 4 provides deterministic inputs and a localized assertion failure.
  implication: Use deterministic reproduction plus direct query/relationship fault localization; SBFL remains skipped because pytest-cov is aggregate rather than per-test spectrum coverage.
- timestamp: 2026-08-27T10:08:42+02:00
  checked: Immediate isolated replay of the complete service module with `--randomly-seed=4`
  found: The replay passed 19/19 instead of reproducing the five failures; the second planned replay was intentionally not run because the first disproved seed-only determinism.
  implication: Seed 4 is a preserved exposing seed but not a sufficient reproducer; process/row-layout state is a second contributing condition. Reclassify as heisenbug-mandelbug and replace incidental sampling with a deterministic physical-order repro.
- timestamp: 2026-08-27T10:09:44+02:00
  checked: Role enum/order contract and project relationship mappings
  found: `RoleName` defines the fixed order as admin, product-manager/reviewer, translator, viewer; no SQLAlchemy relationship in the project currently declares collection ordering.
  implication: Added a minimal two-role behavioral regression that reverses legal association-row insertion order and requires the ORM boundary to restore the specified domain order.
- timestamp: 2026-08-27T10:10:41+02:00
  checked: First agent-authored reverse-association regression under `--randomly-seed=4`
  found: The test passed before any production fix because this particular PostgreSQL plan traversed fixed role IDs rather than physical join-row insertion order.
  implication: The test is not a valid RED oracle and must not drive a fix; replace it with a deterministic assertion on the ORM loader's missing ordering contract.
- timestamp: 2026-08-27T10:11:49+02:00
  checked: Agent-authored mapper-contract regression under stable `--randomly-seed=4`
  found: RED reproduced deterministically: `test_user_roles_relationship_declares_fixed_role_order` failed because `User.roles.property.order_by` is exactly `False`.
  implication: Confirms the ORM mapping itself lacks the ordering contract; the production fix belongs at the relationship read boundary, not in service-only projection sorting or test reseeding.
- timestamp: 2026-08-27T10:34:38+02:00
  checked: TDD GREEN regression and minimal-diff inspection
  found: After adding only `order_by="Role.name"` to `User.roles`, the stable-seed mapper-contract regression passed 1/1; the production and test diff contains nine additions, no deletions, and `git diff --check` passed.
  implication: The target contract is green and the fix is not behavior-deleting; revert-and-reconfirm must now prove causality.
- timestamp: 2026-08-27T10:35:19+02:00
  checked: Fix-acceptance mutation availability and revert-and-reconfirm
  found: Removing only `order_by="Role.name"` restored the exact RED assertion (`order_by is False`), and reapplying it restored GREEN 1/1. Stryker is absent and unconfigured; the repository's mutmut configuration explicitly limits mutation to auth modules and excludes `models/user.py`.
  implication: Causality is confirmed by the required revert signal. The formal mutation signal must be recorded as skipped due to unavailable scoped tooling; the manual removal mutant was nevertheless killed by the driving regression.
- timestamp: 2026-08-27T10:35:46+02:00
  checked: Adjacent admin-user service and API suites under stable `--randomly-seed=4`
  found: All 35 tests passed, including all role combinations, mapper contract, lifecycle invariants, and HTTP boundary behavior.
  implication: The fix preserves adjacent admin-user functionality; proceed to the full randomized backend suite.
- timestamp: 2026-08-27T10:37:42+02:00
  checked: First full backend suite under stable `--randomly-seed=4`
  found: Role-order and all other non-live tests passed; 342/344 passed. The only two failures were `tests/worker/test_smoke_task.py` because Redis at 127.0.0.1:56379 refused connections and no distinct Celery worker was online, matching the pre-fix environment failure already recorded.
  implication: No regression is attributable to the fix, but the full-suite signal requires a rerun with its declared live Redis/worker prerequisites.
- timestamp: 2026-08-27T10:39:20+02:00
  checked: Full backend suite under stable `--randomly-seed=4` with isolated live Redis/Celery prerequisites
  found: All 344 tests passed in 24.01 seconds, including the mapper regression, all 15 role combinations, concurrency tests, API tests, and four worker smoke cases. The unique Celery worker and Redis container were then stopped; residue checks found no container, process, or port listener.
  implication: The original randomized role-order defect is absent and related backend functionality remains green in the production-like PostgreSQL/Redis/worker test environment.
- timestamp: 2026-08-27T10:39:53+02:00
  checked: Final static analysis and source hygiene
  found: Ruff lint passed, Ruff format reported both changed files already formatted, mypy found no issues in 51 source files, and `git diff --check` passed. Unrelated `.gsd/`, `graphify-out/`, and `.planning/milestone.lock` state remained untouched.
  implication: The accepted one-line fix and its regression guard are ready for required human verification before archival and commits.
- timestamp: 2026-08-27T10:44:57+02:00
  checked: Required human verification checkpoint
  found: The user responded "confirmed fixed" for the original admin-user update/reload workflow.
  implication: End-to-end verification is complete; the debug session may be marked resolved and archived.

## Eliminated

- hypothesis: Reversing association-row insertion order alone deterministically forces noncanonical `User.roles` output.
  evidence: The reverse two-role regression passed unchanged under seed 4, proving PostgreSQL may choose a plan whose incidental order remains canonical.
  timestamp: 2026-08-27T10:10:41+02:00

## Resolution

- **root_cause:** `User.roles` declares a many-to-many collection without SQLAlchemy `order_by`; database association rows are sets with unspecified query order, so persisted reloads sometimes differ from `FIXED_ROLE_ORDER` even though `_to_record` sorts its separate response projection.
- **fix:** Added `order_by="Role.name"` to the `User.roles` SQLAlchemy relationship so collection reloads no longer depend on unspecified PostgreSQL result order.
- **verification:**
  - target_test: {result: pass, command: "uv run pytest tests/unit/services/test_admin_users.py::test_user_roles_relationship_declares_fixed_role_order --randomly-seed=4"}
  - mutation_check: {result: skipped, reason_if_skipped: "Stryker is absent/unconfigured and existing mutmut scope excludes models/user.py", mutant_killed: "manual removal mutant killed by the driving regression"}
  - no_op_deletion: {result: pass, deletion_justified_by_rca: false, evidence: "production diff is one addition; combined fix/test diff is nine additions and no deletions"}
  - adjacent_tests: {result: pass, suites_run: ["tests/unit/services/test_admin_users.py", "tests/api/test_admin_users.py", "full backend suite under seed 4"]}
  - revert_and_reconfirm: {result: pass, bug_returned_on_revert: true, fixed_on_reapply: true}
  - static_checks: {result: pass, checks: ["ruff check", "ruff format --check", "mypy src", "git diff --check"]}
  - human_verification: {result: pass, response: "confirmed fixed", timestamp: "2026-08-27T10:44:57+02:00"}
  - guardrail_verdict: accepted
- **files_changed:** [backend/src/verboflex/models/user.py, backend/tests/unit/services/test_admin_users.py]
- **oracle_type:** specified — `RoleName`/`FIXED_ROLE_ORDER` is the explicit domain contract.
- **prevention:**
  - branched_5_whys:
    - code: The service canonicalized its response projection, but the ORM relationship declared no ordering contract; without a mapper-level regression, the collection boundary could silently depend on database row order.
    - environment_data: PostgreSQL query plans and association-row layout often returned the roles incidentally in canonical order, so ordinary isolated and deterministic runs masked the missing contract until randomized execution and row churn exposed it.
  - and_gate: No — the missing ORM ordering is sufficient to violate the contract; environment and data conditions only determine whether the violation is visible in a particular run.
  - why_not_caught: No deterministic gate existed for ORM collection ordering; the existing behavioral combination test depended on incidental PostgreSQL ordering, while lint and type checks cannot infer this runtime relationship contract.
  - recurrence_guard: The specified-contract regression `backend/tests/unit/services/test_admin_users.py::test_user_roles_relationship_declares_fixed_role_order` fails if `User.roles` loses its `Role.name` ordering declaration.
