---
phase: 02-admin-configuration
plan: 07
subsystem: bitbucket-live-discovery
tags: [bitbucket, httpx, fastapi, streaming, tdd]

requires:
  - phase: 02-admin-configuration
    plan: 05
    provides: Generation-serialized Bitbucket OAuth lifecycle and immediate local revocation
  - phase: 02-admin-configuration
    plan: 06
    provides: Safe generation-bound Bitbucket HTTP adapter and exact read endpoint allowlist
provides:
  - Exact live branch discovery with provider spelling/order and application-owned opaque pagination
  - Commit-bound source traversal under immutable A-03 page, entry, depth, candidate, and byte budgets
  - Read-only administrator discovery API that exposes metadata but never provider URLs or raw file bodies
  - Reproducible changed-line and mutation evidence for traversal, streaming, and generation boundaries
affects: [02-08-admin-connection-ui, 02-19-bitbucket-integration, 02-20-phase-gauntlet]

actuals:
  tokens: 49716
  tasks: 2
  commits: 12

tech-stack:
  added: []
  patterns:
    - Resolve an exact branch to a 40-character commit before every tree or raw source read
    - Traverse source pages breadth-first under one immutable budget object and fail rather than truncate
    - Count undecoded transport bytes while streaming and keep raw content inside the backend service boundary

key-files:
  created:
    - backend/src/verboflex/services/repository_discovery.py
    - backend/src/verboflex/schemas/admin_discovery.py
    - backend/src/verboflex/api/v1/routes/admin_discovery.py
    - backend/tests/integration/test_bitbucket_discovery.py
    - backend/tests/api/test_admin_discovery.py
    - tools/verify_bitbucket_discovery_mutants.py
  modified:
    - backend/src/verboflex/integrations/bitbucket/client.py
    - backend/src/verboflex/integrations/bitbucket/urls.py
    - backend/src/verboflex/api/v1/router.py
    - backend/src/verboflex/main.py
    - backend/tests/api/test_openapi_contract.py
    - backend/tests/api/test_admin_repositories.py
    - backend/tests/architecture/test_provider_boundaries.py
    - frontend/openapi.json
    - frontend/src/api/client/index.ts
    - frontend/src/api/client/sdk.gen.ts
    - frontend/src/api/client/types.gen.ts
    - tools/verify_bitbucket_http_adapter_mutants.py

key-decisions:
  - "Preserve Bitbucket branch spelling and provider order; paginate only through a bounded application-owned opaque cursor."
  - "Resolve branch authority once, then use only the immutable commit hash for source tree and raw reads."
  - "Treat any page, entry, depth, candidate, file-byte, aggregate-byte, continuation, generation, redirect, or encoding violation as a typed blocking failure instead of returning partial data."
  - "Expose only commit hash, relative path, size, and aggregate byte count; raw provider bytes remain backend-only and are never persisted."

patterns-established:
  - "Immutable provider read: exact branch detail precedes every source traversal and all downstream URLs contain its resolved commit hash."
  - "Bounded traversal: 50 pages, 5,000 entries, depth 12, 500 candidates, 1 MiB per file, and 20 MiB total are one frozen service contract."
  - "Continuation boundary: every provider next URL must remain on exact HTTPS api.bitbucket.org and the same repository/commit/directory resource path."

requirements-completed: [BITB-03, BITB-04]

coverage:
  - id: D1
    description: "Live branches preserve exact provider names and order while provider pagination stays private behind an application-owned cursor."
    requirement: BITB-03
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_discovery.py#test_lists_exact_branches_with_validated_opaque_pagination"
        status: pass
      - kind: api
        ref: "backend/tests/api/test_admin_discovery.py#test_admin_branch_collection_is_exact_bounded_and_application_opaque"
        status: pass
    human_judgment: false
  - id: D2
    description: "Source discovery resolves the exact branch first and uses its immutable commit for deterministic tree and raw reads."
    requirement: BITB-03
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_discovery.py#test_resolves_commit_then_streams_exact_bounded_source_candidates"
        status: pass
      - kind: api
        ref: "backend/tests/api/test_admin_discovery.py#test_admin_source_discovery_returns_metadata_only_and_maps_closed_failures"
        status: pass
    human_judgment: false
  - id: D3
    description: "Traversal stops at the exact A-03 page, entry, depth, candidate, single-file, and aggregate byte limits instead of truncating."
    requirement: BITB-04
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_discovery.py#test_every_source_traversal_budget_blocks_instead_of_truncating"
        status: pass
      - kind: other
        ref: "tools/verify_bitbucket_discovery_mutants.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Traversal, unsafe continuations, redirects, compression, oversize data, and reconnect/revoke races expose only typed bounded failures with no provider body."
    requirement: BITB-04
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_discovery.py#test_hostile_source_reads_fail_closed_without_returning_provider_bytes"
        status: pass
      - kind: other
        ref: "backend/tests/architecture/test_provider_boundaries.py"
        status: pass
    human_judgment: false

duration: 37min
completed: 2026-08-27
status: complete
---

# Phase 02 Plan 07: Live Repository Discovery Summary

**Exact live branches and immutable commit-bound source reads now cross a read-only administrator API under frozen A-03 traversal and streaming limits, without exposing provider URLs or raw bodies.**

## Performance

- **Duration:** 37 min, including the tracer approval handoff
- **Started:** 2026-08-27T10:49:35Z
- **Completed:** 2026-08-27T11:26:46Z
- **Tasks:** 2
- **Files modified:** 18 runtime, API, generated-client, test, architecture, and evidence artifacts
- **Actual estimate scale:** 49,716 tokens (198,867 realized diff characters / 4)

## Accomplishments

- Added live Bitbucket branch traversal with `pagelen=100`, validated opaque provider continuations, exact spelling/order preservation, and a separate 50-default/100-maximum application cursor.
- Added branch-to-commit resolution before source access, repository-relative path normalization, deterministic candidate ordering, same-resource continuation validation, and streamed raw-byte counting.
- Centralized the exact A-03 ceilings: 50 pages, 5,000 entries, depth 12, 500 candidates, 1 MiB per file, and 20 MiB aggregate.
- Added a closed administrator source endpoint whose success response contains only commit hash, relative path, size, and total bytes; raw provider bytes are neither persisted nor projected.
- Froze the discovery surface with 100% changed-line coverage, 14/14 discovery mutants killed, and the existing HTTP transport mutation suite still 10/10.

## Task Commits

Each TDD and evidence gate was committed atomically:

1. **Task 1 RED: exact live branch contract** — `1a9fdb3` (test)
2. **Task 1 GREEN: exact live branch discovery** — `c1c4350` (feat)
3. **Task 1 REFACTOR: isolate branch page parsing** — `4243e1d` (refactor)
4. **Task 2 RED: bounded commit-source contract** — `6e565d9` (test)
5. **Task 2 RED correction: raw-source OpenAPI assertion** — `fea8048` (test)
6. **Task 2 static test correction** — `26e4d3f` (test)
7. **Task 2 GREEN: commit-bound source discovery** — `580611b` (feat)
8. **Task 2 REFACTOR: centralized streamed byte accounting** — `f385806` (refactor)
9. **Generated client synchronization** — `7022778` (chore)
10. **Changed-line boundary armor** — `82816bc` (test)
11. **Mutation resistance evidence** — `bb53c0d` (test)
12. **Repository surface regression alignment** — `0afdfdc` (test)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 1 RED:** the exact tracer command failed before live branch discovery existed (`1a9fdb3`).
- **Task 1 GREEN:** the unchanged command passed after the minimal provider and application pagination implementation (`c1c4350`).
- **Task 1 REFACTOR:** the unchanged command remained **9/9** after branch-page parsing was isolated (`4243e1d`); the tracer was then approved.
- **Task 2 RED:** the exact `cd backend && uv run pytest -q tests/integration/test_bitbucket_discovery.py tests/api/test_openapi_contract.py -x` command failed because commit-bound source discovery did not exist (`6e565d9`).
- **Task 2 GREEN:** the unchanged command passed **20/20** after the minimal traversal, streaming, validation, and API implementation (`580611b`).
- **Task 2 REFACTOR:** the unchanged command remained **20/20** after both live and mock transport chunks were routed through one byte-accounting helper (`f385806`).
- **Final exact proof:** the unchanged Task 2 command passes **37/37** after boundary and mutation armor.

## Gauntlet Evidence

- Final plan command: **47 passed** across provider discovery, administrator API, and canonical OpenAPI.
- Full randomized backend regression at seed `4`, using project PostgreSQL plus a temporary isolated Redis 7 and Celery solo worker: **405 passed in 28.02s**. The worker and temporary container were stopped and removed afterward.
- Architecture plus migration regression: **10 passed**; adjacent provider/OAuth/lifecycle regression: **23 passed**.
- Ruff lint: **all checks passed**; Ruff format: **106 files already formatted**.
- mypy: **64 source/evidence files, no issues**.
- Changed-line coverage against the approved Task 1 boundary `4243e1d`: **100% (244/244 changed production lines)** with `diff-cover --fail-under=100`.
- Discovery mutation checker negative control passed; baseline passed; **14/14 mutants killed**. The existing HTTP boundary checker also passed its negative control and killed **10/10**.
- Frontend canonical client check, TypeScript, ESLint, Prettier, Vitest **75/75**, and production build all passed.
- OpenAPI compatibility proof preserved all **25** prior operations and response status sets while adding exactly **2** read-only discovery operations.
- `uv lock --check` resolved **112 packages**; Plan 02-07 changed no dependency or lock file.
- `pip-audit` found **no known Python vulnerabilities**; the local `verboflex` package was the sole expected non-PyPI skip.
- License evidence: HTTPX 0.28.1 is BSD, defusedxml 0.7.1 is PSF, cryptography 50.0.1 is Apache-2.0 or BSD-3-Clause, SQLAlchemy 2.0.52 and FastAPI 0.141.1 are MIT.
- `npm audit --audit-level=high` passed. A pre-existing moderate `qs` advisory confined to the Stryker development chain is recorded in `deferred-items.md`; no package graph was modified.
- `detect-secrets` returned **0 findings** over all changed source, tests, generated contracts, and mutation tools.
- Stub scan found no placeholder, TODO, FIXME, skipped test, empty UI-bound value, or unrun verification on the changed production surface.

## Security Contract Review

- Every provider URL is validated before token-bearing transport; source continuations must retain the exact repository, commit, and directory path.
- Redirects are rejected, non-identity content encoding is rejected, JSON metadata is bounded to 1 MiB, and raw files are counted from undecoded transport chunks before retention.
- Credential generation is checked before dispatch and after streaming, so reconnect or local revoke discards in-flight data.
- All limit excesses and malformed provider shapes fail closed with stable typed states; no partial source result is returned.
- Public API schemas are closed and metadata-only. No raw content, provider response body, access token, refresh token, or provider continuation appears in persistence, logs, or API responses.

## Decisions Made

- Provider branch spelling and sequence are authoritative; the application adds pagination without sorting, case folding, or exposing provider URLs.
- The commit hash is the only authority for source reads after branch resolution; mutable branch names never appear in tree or raw URLs.
- Exact limits are immutable correctness and denial-of-service controls, not configuration knobs for this phase.
- Candidate source files are Android XML, Qt `.ts`, JSON, and iOS `.strings`; other files count toward traversal entries but are never downloaded.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Bug] Corrected the RED OpenAPI raw-body prohibition**
- **Found during:** Task 2 RED validation
- **Issue:** The generic forbidden token `content` collided with OpenAPI's required media-type metadata rather than testing raw source fields.
- **Fix:** Replaced it with exact forbidden raw-source field names while preserving the intended closed-schema assertion.
- **Files modified:** `backend/tests/api/test_openapi_contract.py`
- **Committed in:** `fea8048`

**2. [Rule 3 - Blocking Quality] Restored static correctness in the Task 1 API test**
- **Found during:** Task 2 GREEN lint gate
- **Issue:** The tracer test retained one unused SQL import, omitted the `BitbucketBranch` type import, and had noncanonical import ordering.
- **Fix:** Corrected imports only; the approved tracer implementation and commits were not rewritten.
- **Files modified:** `backend/tests/api/test_admin_discovery.py`
- **Committed in:** `26e4d3f`

**3. [Rule 2 - Missing Critical Evidence] Closed every changed security branch and added mutation proof**
- **Found during:** Changed-line coverage and mutation gates
- **Issue:** The planned happy/hostile cases left provider-shape, header, stream, continuation, and API error branches without direct executable evidence.
- **Fix:** Added boundary armor, metadata-only API assertions, a negative-controlled 14-mutant verifier, and realigned the prior HTTP mutation subject with streamed reads.
- **Files modified:** `backend/tests/integration/test_bitbucket_discovery.py`, `backend/tests/api/test_admin_discovery.py`, `tools/verify_bitbucket_discovery_mutants.py`, `tools/verify_bitbucket_http_adapter_mutants.py`
- **Committed in:** `82816bc`, `bb53c0d`

**4. [Rule 2 - Missing Critical Contract] Synchronized the checked-in TypeScript client**
- **Found during:** Client drift gate
- **Issue:** Canonical OpenAPI contained the new branch/source operations while the checked-in generated client did not.
- **Fix:** Regenerated and verified the typed client without changing package manifests or lockfiles.
- **Files modified:** `frontend/src/api/client/index.ts`, `frontend/src/api/client/sdk.gen.ts`, `frontend/src/api/client/types.gen.ts`
- **Committed in:** `7022778`

**5. [Rule 1 - Regression] Updated the frozen repository path surface**
- **Found during:** Full randomized backend regression
- **Issue:** A prior registry test still asserted that only collection/detail paths existed and rejected the approved read-only branch/source subresources.
- **Fix:** Added the two approved paths while retaining credential-free registry payload and provider-boundary assertions.
- **Files modified:** `backend/tests/api/test_admin_repositories.py`
- **Committed in:** `0afdfdc`

---

**Total deviations:** 5 resolved auto-fixes (2 test/regression bugs, 1 blocking static issue, 2 missing critical evidence/contract synchronizations).
**Impact on plan:** All changes strengthen the approved discovery contract without adding provider mutations, persistence, new dependencies, or mapping-grouping decisions.

## Issues Encountered

- The first changed-line run reported 84%; security armor raised it to 100% without excluding branches or weakening the threshold.
- The first full randomized run exposed the stale repository path assertion; after the focused regression fix, the identical seed passed 405/405.
- `npm audit` reports a moderate pre-existing `qs` advisory through development-only Stryker tooling. It is recorded for a reviewed upstream upgrade and is outside this plan's unchanged dependency graph.

## Authentication Gates

None. The Task 1 tracer approval was planned flow and required no live Bitbucket credentials.

## Known Stubs

None.

## User Setup Required

None for this plan. Live organizational Bitbucket credentials remain outside source control and are consumed only through the previously approved OAuth connection.

## Next Phase Readiness

- Branch and source discovery are available as stable generated-client operations for the administrator UI.
- Later parser/import plans can reuse immutable source snapshots and exact A-03 limits without receiving generic provider transport authority.
- Mapping grouping/layout decisions remain unclaimed and available to their dedicated plan.
- The broken-windows ledger has zero open entries; no stub, skipped test, unrun verification, secret finding, or generated-client drift remains.

## Self-Check: PASSED

- Every created runtime, API, test, generated-client, mutation, and summary artifact listed above exists.
- All 12 plan commits exist on `codex/phase-2-admin-configuration` in valid Task 1 and Task 2 RED → GREEN → REFACTOR order.
- Summary frontmatter records exact requirements `[BITB-03, BITB-04]`, measured actuals, and `status: complete`.
- The final broken-windows ledger reports zero open entries.
