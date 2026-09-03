---
phase: 02-admin-configuration
plan: 40
subsystem: backend-authority
tags: [postgresql, alembic, sqlalchemy, preview-jobs, revalidation, mutation-testing]

requires:
  - phase: 02-24
    provides: Durable commit-bound preview jobs and exact confirmation authority
  - phase: 02-29
    provides: Publication and reactivation lifecycle guarded by all-mapping confirmation
  - phase: 02-32
    provides: Published graph ownership and database immutability triggers
  - phase: 02-39
    provides: Generation-aware durable preview execution and recovery foundations
provides:
  - Domain-separated active-revision revalidation jobs over the exact published mapping identity
  - Immutable sidecar confirmations that restore reactivation authority without graph mutation
  - Reversible revision-scope schema with composite ownership and job/scope constraints
  - Fail-closed generation, commit, revision-version, mapping, layout, and concurrency proofs
affects: [02-38, 02-41, 02-42, 02-43, publication, preview-jobs]

actuals:
  tokens: 27419
  tasks: 2
  commits: 8

tech-stack:
  added: []
  patterns:
    - Domain-separated durable job identity for candidate and active-revalidation scopes
    - Immutable operational sidecar outside the guarded published configuration graph
    - Exact-currentness fallback that preserves original candidate confirmation semantics

key-files:
  created:
    - backend/alembic/versions/0011_active_revision_revalidations.py
    - backend/tests/architecture/test_preview_job_mutation_verifier.py
  modified:
    - backend/src/verboflex/models/preview_job.py
    - backend/src/verboflex/models/__init__.py
    - backend/src/verboflex/services/preview_jobs.py
    - backend/tests/integration/test_preview_jobs.py
    - backend/tests/integration/test_product_publication.py
    - backend/tests/integration/test_product_graph_integrity.py
    - backend/tests/integration/test_migrations.py
    - tools/verify_preview_job_mutants.py

key-decisions:
  - "Candidate canonical identity bytes and digest remain byte-for-byte unchanged; active revalidation has a separate revision_scope domain."
  - "Revalidation evidence is append-only sidecar state and never updates or clones a published revision graph."
  - "Reactivation first accepts an original still-current candidate confirmation, then falls back to the latest exact active-revalidation sidecar."
  - "The mutation inventory remains unchanged; selectors are anchored to candidate scope where active scope introduced a second textual occurrence."

patterns-established:
  - "Scoped authority: every durable preview lookup, retry, latest-attempt check, confirmation, and currentness decision carries revision_scope."
  - "Recovery sidecar: operational evidence references owned product/revision/mapping/job tuples but remains outside published-child mutation triggers."

requirements-completed: [PROD-01, PROD-08, PROD-09, BITB-01, BITB-04]

coverage:
  - id: D1
    description: An inactive product can revalidate and explicitly reconfirm its exact published revision after a Bitbucket generation change, then reactivate without graph mutation.
    requirement: PROD-01
    verification:
      - kind: integration
        ref: backend/tests/integration/test_preview_jobs.py::test_inactive_active_revision_can_revalidate_confirm_and_reactivate_without_graph_mutation
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_product_publication.py::test_generation_commit_version_and_mapping_drift_block_reactivation_until_reconfirmed
        status: pass
    human_judgment: false
  - id: D2
    description: The revision-scope schema and immutable sidecar migrate reversibly and cannot mutate the published graph.
    requirement: PROD-08
    verification:
      - kind: integration
        ref: backend/tests/integration/test_migrations.py::test_active_revision_revalidation_sidecar_migrates_reversibly
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_product_graph_integrity.py::test_active_revision_revalidation_never_mutates_published_graph
        status: pass
    human_judgment: false
  - id: D3
    description: Candidate compatibility and every new active-currentness branch remain covered and mutation-sensitive.
    requirement: BITB-04
    verification:
      - kind: integration
        ref: backend/tests/integration/test_preview_jobs.py::test_admin_explicitly_confirms_one_exact_current_layout
        status: pass
      - kind: other
        ref: diff-cover 2a5473f...HEAD --branch-coverage (218/218 lines)
        status: pass
      - kind: other
        ref: tools/verify_preview_job_mutants.py (16/16 killed)
        status: pass
    human_judgment: false

duration: 2h 18m
completed: 2026-08-31
status: complete
---

# Phase 02 Plan 40: Active Revision Revalidation Authority Summary

**Immutable, generation-bound active-revision sidecar confirmation now restores safe reactivation without changing the published graph or candidate identity contract.**

## Performance

- **Duration:** 2h 18m
- **Started:** 2026-08-31T11:17:13Z
- **Completed:** 2026-08-31T13:35:11Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Added a domain-separated `active_revalidation` preview scope that reuses the existing UUID-only, read-only worker path while binding the exact active revision, mapping, commits, provider generation, detector, and layout identity.
- Persisted explicit administrator evidence in a reversible, immutable sidecar with composite ownership constraints and no published-graph mutation path.
- Made reactivation accept either its original still-current candidate confirmation or a latest exact sidecar, while generation, commit, version, mapping, layout, partial evidence, and concurrency drift all fail closed.
- Proved 100% branch-aware changed-source coverage, 16/16 killed preview-authority mutants, reversible migration, graph immutability, and isolated Redis/Celery execution.

## Task Commits

Each TDD gate and assurance repair was committed atomically:

1. **Task 1 RED: expose active revision recovery gap** - `3bcfc4d` (test)
2. **Task 1 GREEN: add immutable active revision authority** - `600f855` (feat)
3. **Task 2 RED: require reversible exact authority** - `338205f` (test)
4. **Task 2 GREEN: enforce ownership and stale denial** - `355f51f` (feat)
5. **Assurance: close active-revalidation authority coverage** - `f7eacde` (test)
6. **Verifier RED: expose ambiguous mutation selector** - `d0b1747` (test)
7. **Verifier GREEN: disambiguate mutation selectors** - `49ceeba` (fix)
8. **Formatting gate: normalize plan-owned sources** - `1c6b50f` (style)

## Files Created/Modified

- `backend/alembic/versions/0011_active_revision_revalidations.py` - Adds the closed revision scope, backfill, composite job/scope authority, immutable confirmation sidecar, and reversible downgrade.
- `backend/src/verboflex/models/preview_job.py` - Models scoped jobs and immutable active-revalidation confirmation evidence.
- `backend/src/verboflex/models/__init__.py` - Registers the sidecar in explicit Alembic metadata exports.
- `backend/src/verboflex/services/preview_jobs.py` - Implements active job creation/reuse, confirmation, currentness fallback, eligibility, and scoped revision/mapping identity checks.
- `backend/tests/integration/test_preview_jobs.py` - Covers the recovery tracer, namespace isolation, retries, bounded blockers, corruption denial, and every changed branch.
- `backend/tests/integration/test_product_publication.py` - Proves generation/commit/version/mapping drift and concurrent confirmation/reactivation behavior.
- `backend/tests/integration/test_product_graph_integrity.py` - Proves sidecar inserts and denied writes leave the published graph byte-for-byte unchanged.
- `backend/tests/integration/test_migrations.py` - Proves upgrade, downgrade, re-upgrade, retained data, and exact constraint behavior.
- `backend/tests/architecture/test_preview_job_mutation_verifier.py` - Requires every reviewed mutation subject to remain unambiguous.
- `tools/verify_preview_job_mutants.py` - Anchors unchanged mutation semantics to unique candidate-scope source fragments.

`backend/src/verboflex/services/publication.py` required no code change: its existing all-mapping predicate already consumes `is_current_preview_confirmation`, so the scoped fallback remains behind the established Product row lock.

## Decisions Made

- Preserved `_canonical_identity` and candidate complete-result digest behavior byte-for-byte; only active work includes `revision_scope` in its domain-separated identities.
- Kept sidecar evidence immutable and independent from `ProductRevision`, mapping, side, and target rows; the only lifecycle mutation remains the existing locked product activation transition.
- Required the latest attempt within the same scope and exact live generation/commit/layout tuple; historical jobs and confirmations remain inspectable but never authoritative after drift.
- Kept the existing mutation inventory and thresholds unchanged. Selector repairs only add contextual anchors after active scope created valid duplicate text.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Closed branch-coverage gaps around new authority failure boundaries**
- **Found during:** Post-Task 2 branch-aware diff coverage.
- **Issue:** The planned behavioral matrix left defensive namespace, retry-race, malformed evidence, eligibility, and short-circuit branches unexecuted; initial changed-source coverage was 73%.
- **Fix:** Added behavioral integration cases for every missing branch without changing production behavior or coverage configuration.
- **Files modified:** `backend/tests/integration/test_preview_jobs.py`
- **Verification:** Preview module 71/71 passed and branch-aware diff coverage reached 218/218 lines (100%).
- **Committed in:** `f7eacde`

**2. [Rule 3 - Blocking] Repaired mutation selector ambiguity caused by the second scoped retry/status occurrence**
- **Found during:** Full targeted preview mutation proof.
- **Issue:** The fail-closed verifier correctly rejected ambiguous textual subjects after active scope introduced a second valid occurrence.
- **Fix:** Added a RED uniqueness contract, then anchored candidate retry/status and explicit model-export mutants to unique context. Mutant inventory, count, thresholds, and semantics were unchanged.
- **Files modified:** `backend/tests/architecture/test_preview_job_mutation_verifier.py`, `tools/verify_preview_job_mutants.py`
- **Verification:** Verifier negative control passed and all 16/16 reviewed mutants were killed twice, including after final formatting.
- **Committed in:** `d0b1747`, `49ceeba`

**3. [Rule 3 - Blocking] Applied the pinned formatter to plan-owned files**
- **Found during:** Final type/lint/format gate.
- **Issue:** Four plan-owned files were semantically green but not canonical under the pinned Ruff formatter.
- **Fix:** Applied Ruff formatting only and reran focused behavior, coverage, and mutation gates.
- **Files modified:** `backend/src/verboflex/models/preview_job.py`, `backend/src/verboflex/services/preview_jobs.py`, `backend/tests/integration/test_migrations.py`, `backend/tests/integration/test_product_graph_integrity.py`
- **Verification:** Mypy, Ruff lint, Ruff format check, focused tests, 100% changed-source coverage, and 16/16 mutation score passed.
- **Committed in:** `1c6b50f`

---

**Total deviations:** 3 auto-fixed (3 Rule 3 blocking assurance repairs)
**Impact on plan:** All changes were necessary to keep existing assurance gates fail-closed. No dependency, provider write, coverage exclusion, mutation threshold change, or published-graph mutation was introduced.

## Verification

- Exact Plan 02-40 nodes: **9 passed**, including both tracer nodes, reversible migration, graph immutability, four-case authority drift matrix, and verifier contract.
- Relevant backend regression: **114 passed** across preview, publication, graph-integrity, and migration modules.
- Broad backend regression: **794 passed, 4 deselected**. The two worker nodes were then run against disposable Redis/Celery and passed **2/2**; the remaining two are the pre-existing Phase 02 review-inventory assertions awaiting the fresh final review plan.
- Coverage: repository suite reported 97%; exact changed production scope remained **218/218 lines, 100% branch-aware**, with no base, selector, exclusion, or budget weakening.
- Mutation: verifier negative control passed; targeted preview authority score **16/16 killed**.
- Migration: `0011_active_revision_revalidations` is the single head; migration module **10/10 passed**, including upgrade/downgrade/re-upgrade.
- Quality: mypy passed 81 source files; Ruff lint passed and 133 files were canonically formatted.
- Supply chain: `uv lock --check` passed; pip-audit found no known vulnerabilities; Python license inventory was non-empty; npm high-severity audit and production moderate audit found zero vulnerabilities. Two already-known moderate findings remain confined to a development-only transitive dependency.
- Secrets: detect-secrets scanned all ten changed source/test/tool files with **0 findings**.
- Runtime cleanup: disposable Redis container and Celery worker were stopped; no `verboflex-02-40` runtime resource remains.

## TDD Gate Compliance

- Task 1: RED `3bcfc4d` precedes GREEN `600f855`.
- Task 2: RED `338205f` precedes GREEN `355f51f`.
- Mutation-verifier deviation: RED `d0b1747` precedes GREEN `49ceeba`.

## Issues Encountered

- The phase-wide review artifact currently contains the newer CR-11/CR-12/CR-13 closure narrative, while two legacy semantic-inventory tests still expect CR-01 through CR-10 headings. This pre-existing cross-plan mismatch is deliberately owned by the remaining fresh-review plan and does not touch any 02-40 file or behavior.
- Running the complete backend suite without worker infrastructure initially produced two Redis connection failures. The exact same worker nodes passed against an isolated disposable Redis broker and distinct Celery worker, proving the failures were environmental.

## User Setup Required

None - no new external service configuration or dependency is required.

## Next Phase Readiness

- CR-12 now has backend recovery authority: inactive published configurations can be revalidated and reconfirmed after provider generation change without candidates or graph mutation.
- The remaining Phase 2 plans can add the corresponding administrator interaction and final fresh review/evidence closure over this stable service boundary.
- No blocking stub, skipped mandatory plan verification, schema head conflict, dependency drift, or runtime residue remains.

## Known Stubs

None.

## Authentication Gates

None.

## Self-Check: PASSED

- All created artifacts exist on disk.
- All eight implementation, TDD, assurance, and formatting commits exist in git history.
- Every mandatory plan verification and the final changed-source assurance rerun completed successfully.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-31*
