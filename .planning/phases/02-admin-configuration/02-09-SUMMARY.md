---
phase: 02-admin-configuration
plan: 09
subsystem: separate-mapping-and-pr-grouping
tags: [fastapi, pydantic, sqlalchemy, openapi, tdd, property-testing]

requires:
  - phase: 02-admin-configuration
    plan: 08
    provides: Revision-owned candidate repository mappings with exact live branches and normalized target sets
provides:
  - Closed Separate mapping write topology with exactly one Keys side and one Translations side
  - Stable mapping identity across topology changes with candidate-only layout invalidation
  - Pure deterministic pull-request grouping solely by exact Repository UUID and target branch
  - Writable-side grouping preview constrained to configured targets and default
  - Canonical OpenAPI and generated TypeScript consumer for Direct or Separate mapping requests
affects: [02-12-format-detection, 02-14-layout-selection, 02-18-admin-ui, 07-pull-request-preparation, 08-bitbucket-write-workflow]

actuals:
  tokens: 43757
  tasks: 2
  commits: 9

tech-stack:
  added: []
  patterns:
    - Model Separate as two explicit repository sides under one revision-owned mapping identity
    - Derive pull-request group identity only from exact repository UUID and exact target branch
    - Keep grouping preview pure and exclude provider calls, persistence, PR jobs, and write execution

key-files:
  created:
    - backend/src/verboflex/services/pr_grouping.py
    - backend/tests/unit/services/test_pr_grouping.py
  modified:
    - backend/src/verboflex/api/v1/routes/admin_mappings.py
    - backend/src/verboflex/schemas/admin_mappings.py
    - backend/src/verboflex/services/mappings.py
    - backend/tests/api/test_admin_mappings.py
    - backend/tests/unit/services/test_mappings.py
    - frontend/openapi.json
    - frontend/src/api/client/index.ts
    - frontend/src/api/client/types.gen.ts
    - tools/verify_mapping_api_mutants.py

key-decisions:
  - "Fix pull-request grouping identity to exact Repository UUID plus exact target branch; mapping, file, language, and product never alter the group key."
  - "For Separate mappings, preview the Translations repository as the writable side; Direct previews its sole repository, and both expose only configured allowed targets and their default member."
  - "Keep grouping as deterministic preview metadata only; provider writes, pull-request jobs, and persistence remain outside Phase 2."

patterns-established:
  - "Closed side topology: Separate accepts exactly two sides with distinct Keys and Translations roles, while Direct remains a single explicit repository side."
  - "Permutation-invariant grouping: groups and their ordered changes are canonical regardless of mapping, file, or language input order."
  - "Topology-safe revisions: topology changes retain mapping UUID and candidate ownership, clear selected layout state, and never mutate the active revision."

requirements-completed: [PROD-03, PROD-04, PROD-05, PROD-06, PROD-07, PROD-09]

coverage:
  - id: D1
    description: "Separate mapping writes require exactly one Keys side and one Translations side, each with an independent reusable Repository UUID and exact live source branch, while preserving mapping and revision identity."
    requirement: PROD-07
    verification:
      - kind: unit
        ref: "backend/tests/unit/services/test_mappings.py#test_separate_mapping_requires_exact_keys_and_translations_sides"
        status: pass
      - kind: integration
        ref: "backend/tests/api/test_admin_mappings.py#test_separate_mapping_api_is_closed_versioned_and_topology_safe"
        status: pass
    human_judgment: false
  - id: D2
    description: "Only exact Repository UUID and exact target branch determine pull-request group identity; mapping, file and language permutations are invariant and empty input has no effects."
    requirement: PROD-05
    verification:
      - kind: unit
        ref: "backend/tests/unit/services/test_pr_grouping.py#test_only_exact_repository_and_target_branch_determine_group_identity"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/services/test_pr_grouping.py#test_mapping_file_and_language_permutations_leave_groups_invariant"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/services/test_pr_grouping.py#test_empty_input_is_empty_and_grouping_has_no_provider_or_persistence_capability"
        status: pass
    human_judgment: false
  - id: D3
    description: "Grouping preview selects the only writable repository side and rejects every target outside the configured allowlist while retaining its exact configured default."
    requirement: PROD-03
    verification:
      - kind: unit
        ref: "backend/tests/unit/services/test_mappings.py#test_mapping_grouping_preview_uses_only_the_writable_side_and_configured_targets"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/services/test_pr_grouping.py#test_grouping_preview_accepts_only_exact_configured_targets_and_default"
        status: pass
    human_judgment: false

duration: 2h27min
completed: 2026-08-27
status: complete
---

# Phase 02 Plan 09: Separate Mapping and Pull-Request Grouping Summary

**Separate mappings now preserve one revision-owned identity across explicit Keys and Translations sides, while a pure permutation-invariant contract groups future changes only by exact Repository UUID and exact target branch.**

## Performance

- **Duration:** 2h27min, including the tracer approval handoff
- **Started:** 2026-08-27T12:54:52Z
- **Completed:** 2026-08-27T15:21:21Z
- **Tasks:** 2
- **Files modified:** 11 runtime, API, generated-client, test, and evidence artifacts
- **Actual estimate scale:** 43,757 tokens (175,025 realized diff characters / 4)

## Accomplishments

- Added a closed Separate request union that requires exactly one Keys and one Translations side, validates each independent repository and exact live branch, and retains one mapping UUID under candidate-revision authority.
- Made topology changes clear stale selected-layout identity/version without mutating the active revision; normalized identical Separate writes remain true no-ops.
- Added pure deterministic grouping whose complete identity is exactly `(repository_uuid, target_branch)`. Mapping, product, file, and language never split or merge groups, while branch case remains significant.
- Added configuration preview metadata that maps Direct to its sole repository and Separate to its Translations repository, accepts only configured target branches, and creates no provider request, persistence write, or PR job.
- Synchronized the canonical OpenAPI and generated TypeScript client with the Direct/Separate write union.

## Task Commits

Each TDD and evidence gate was committed atomically:

1. **Task 1 RED: Separate mapping contract** — `77e2238` (test)
2. **Task 1 GREEN: Separate mapping topology** — `9ce9e1f` (feat)
3. **Task 1 REFACTOR: centralized mapping row projection** — `d4f7bfb` (refactor)
4. **Task 2 RED: fixed grouping contract** — `e55d9e4` (test)
5. **Task 2 GREEN: pure fixed grouping** — `3b111db` (feat)
6. **Task 2 evidence formatting** — `4887742` (style)
7. **Task 2 mutation resistance** — `d549317` (test)
8. **Task 2 rejection coverage armor** — `a7de50f` (test)
9. **Canonical Separate OpenAPI/client synchronization** — `1e70189` (chore)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 1 RED:** the exact `cd backend && uv run pytest -q tests/unit/services/test_mappings.py tests/api/test_admin_mappings.py -x` command failed before Separate write behavior existed (`77e2238`).
- **Task 1 GREEN:** the unchanged command passed **34/34** after the minimal closed topology and validation landed (`9ce9e1f`).
- **Task 1 REFACTOR:** the unchanged command remained **34/34** after mapping row projection was centralized (`d4f7bfb`). The tracer was then approved before expansion.
- **Task 2 RED:** the exact `cd backend && uv run pytest -q tests/unit/services/test_pr_grouping.py tests/unit/services/test_mappings.py -x` command failed because the grouping module did not exist (`e55d9e4`).
- **Task 2 GREEN:** the unchanged command passed **21/21** after the minimal pure grouping and preview implementation landed (`3b111db`).
- **Task 2 REFACTOR:** the unchanged command remained **21/21**; no justified production refactor existed, so no empty commit was created.
- **Final exact Task 2 proof:** the unchanged command passes **21/21**.
- **Final plan proof:** `cd backend && uv run pytest -q tests/unit/services/test_mappings.py tests/unit/services/test_pr_grouping.py tests/api/test_admin_mappings.py -x` passes **40/40**.

## Gauntlet Evidence

- Full randomized backend regression under preserved seed `4`, with an isolated Redis 7 container and a distinct Celery solo worker connected through `VERBOFLEX_REDIS_URL`: **445 passed in 31.01s**. Both temporary processes were stopped afterward.
- Reversible migrations, architecture boundaries, and canonical OpenAPI: **20 passed**.
- Ruff lint: **all checks passed**; Ruff format: **114 files already formatted**.
- mypy: **68 source/evidence files, no issues**.
- Focused coverage selection: **40 passed**; changed-line branch coverage against Task 2 RED boundary `e55d9e4`: **100% (54/54 production lines)**. The new grouping module has 100% statement and branch coverage.
- Mutation checker negative control and baseline passed; **13/13 mutants killed**, including branch case folding, mapping-derived grouping, input-order dependence, unconfigured targets, Separate ordering, version/no-op behavior, and bounded conflict projection.
- Frontend canonical API check, TypeScript, ESLint, Prettier, Vitest **75/75**, and production build all passed; Vite transformed 1,948 modules.
- `uv lock --check` resolved **112 packages** and this plan changed no dependency manifest or lockfile.
- `pip-audit` found **no known Python vulnerabilities**; the local `verboflex` package was the sole expected non-PyPI skip. The 108-line dependency-license inventory completed successfully.
- `npm audit --audit-level=high` passed. The pre-existing moderate `qs` advisory in development-only Stryker tooling remains recorded in `deferred-items.md`; the JavaScript dependency graph did not change.
- `detect-secrets` found **0 findings** across all 11 changed source, API, test, generated-contract, and mutation-evidence files.
- Stub scan found no placeholder, TODO, FIXME, skipped test, empty UI-bound value, or unrun verification on the changed surface.

## Security Contract Review

- Separate sides are a closed two-element role set. Missing, duplicate, extra, manually authored, unavailable, stale, or cross-candidate identities fail without candidate or active-state mutation.
- Exact branch membership remains current live-discovery authority. Trimming and case folding do not broaden source or target identity.
- Candidate version is checked transactionally; mapping UUID remains stable through topology replacement and active revision state is never changed by candidate configuration.
- The grouping module has no provider, database, task-queue, or HTTP capability. Empty and populated previews are pure immutable metadata.
- Future writable grouping for Separate uses only the Translations repository. Only configured allowed target branches and their exact default are projected.

## Decisions Made

- Fixed D-17 group identity to exact Repository UUID plus exact target branch and made all other change metadata non-authoritative for grouping.
- Fixed D-18 preview authority to the mapping's configured allowlist/default, using the sole Direct side or the Separate Translations side as the future write destination.
- Kept provider writes and pull-request job creation out of this plan; Phases 7-8 will consume the pure grouping contract rather than redefining it.

## Residual Assumptions

- Separate's Translations side is the only writable destination for future localized-value changes; the Keys side remains source context unless a later approved phase explicitly introduces key mutation.
- The grouping contract intentionally preserves exact branch spelling and UUID identity. Any future aliasing, branch normalization, or provider-side canonicalization would be an architectural change to D-17.
- `PullRequestGroupingPreview` is configuration metadata only. It intentionally does not store a selection or schedule work, and no PR provider implementation is expected before Phases 7-8.
- Layout selection remains null after a topology change until deterministic detection and explicit confirmation in Plans 12-14; this is approved domain state, not a stub.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Formatting] Normalized grouping test imports**
- **Found during:** Task 2 final static gate
- **Issue:** The new test import block did not satisfy the repository's deterministic Ruff formatting contract.
- **Fix:** Applied the mechanical import-only formatting without changing assertions or behavior.
- **Files modified:** `backend/tests/unit/services/test_pr_grouping.py`
- **Committed in:** `4887742`

**2. [Rule 2 - Missing Critical Evidence] Extended the mutation verifier for exact grouping semantics**
- **Found during:** Task 2 mutation gate
- **Issue:** Existing mutation evidence did not challenge branch case, repository-vs-mapping identity, input permutation, or configured-target rejection; Task 1's additional no-op comparison also made one older mutation subject ambiguous.
- **Fix:** Added four deterministic grouping mutants, selected the new grouping tests, and made the existing direct no-op mutation subject exact. The negative control passes and all 13 mutants are killed.
- **Files modified:** `tools/verify_mapping_api_mutants.py`
- **Committed in:** `d549317`

**3. [Rule 2 - Missing Critical Evidence] Closed grouping rejection branches**
- **Found during:** Task 2 changed-line branch coverage gate
- **Issue:** Invalid change values, malformed configured target sets, and a corrupt Separate mapping preview left three changed production lines uncovered.
- **Fix:** Added focused fail-closed tests and reached 100% changed-line branch coverage.
- **Files modified:** `backend/tests/unit/services/test_pr_grouping.py`, `backend/tests/unit/services/test_mappings.py`
- **Committed in:** `a7de50f`

**4. [Rule 2 - Missing Critical Contract] Synchronized canonical OpenAPI and generated client**
- **Found during:** Full randomized backend regression
- **Issue:** Runtime Separate requests were implemented while the checked-in OpenAPI and generated TypeScript consumer still represented Direct-only writes.
- **Fix:** Regenerated the canonical schema and typed client, then passed backend schema equality, frontend API drift, type, lint, test, and build gates.
- **Files modified:** `frontend/openapi.json`, `frontend/src/api/client/index.ts`, `frontend/src/api/client/types.gen.ts`
- **Committed in:** `1e70189`

## Authentication Gates

None.

## Known Stubs

None. Null selected-layout state after topology change is intentional pending deterministic discovery/confirmation in Plans 12-14; preview-only grouping is the complete approved Phase 2 boundary.

## Issues Encountered

- The first final full-suite harness started the Celery worker with configuration names that `Settings` does not consume, so two worker smoke tests failed while 443 tests passed. The harness was corrected to `VERBOFLEX_REDIS_URL`, waited for worker readiness, and the identical seed then passed 445/445. No product change was required.
- `api:check` correctly reports a diff before generated artifacts are committed because it regenerates and compares to `HEAD`. The generated schema/client were first validated by backend OpenAPI tests and frontend type/lint/test/build gates, committed atomically, and the final clean-state `api:check` passed.
- `npm audit` continues to report the pre-existing moderate `qs` advisory through development-only Stryker tooling. The high-severity gate passes and the unchanged advisory remains deferred for reviewed upstream remediation.

## Next Phase Readiness

- Plans 12-14 can detect and confirm one exact layout for Direct or Separate mappings without inventing side identity or retaining stale selections across topology changes.
- Plan 18 can consume the generated Direct/Separate API union and preview the exact writable repository and configured targets.
- Phases 7-8 can consume the pure group contract directly for job preparation and provider execution while preserving the exact D-17 boundary.
- No authentication gate, dependency change, open verification, temporary runtime, or generated artifact blocks continuation.

## TDD Gate Compliance

- Task 1 follows RED → GREEN → REFACTOR (`77e2238` → `9ce9e1f` → `d4f7bfb`).
- Task 2 follows RED → GREEN (`e55d9e4` → `3b111db`); the unchanged REFACTOR gate passed and no empty commit was created.
- All exact focused commands were retained unchanged across their task gates, and the complete final surface passes the plan command.
- The old-coder evidence loop drove the fresh randomized regression, 100% changed-line coverage, mutation resistance, static analysis, supply-chain checks, secret scan, and generated-consumer verification recorded above.

## Self-Check: PASSED

All eleven changed artifacts, this summary, and all nine task/evidence commits were found before planning state was advanced.
