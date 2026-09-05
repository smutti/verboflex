---
phase: 04-localization-import-search-and-constraints
plan: 07
subsystem: localization-parsing
tags: [parser-checkpoint, supply-chain, docker-compose, coverage, dependency-audit]

requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [02, 03, 04, 05, 06]
    provides: complete four-format canonical adapters, conformance fixtures, and deterministic mapping aggregation
provides:
  - immutable redacted evidence for the complete parser boundary
  - fail-fast host and isolated backend/worker checkpoint runner
  - explicit human approval for regex 2026.9.3 and @tanstack/react-virtual 3.14.10
affects: [canonical-persistence, grapheme-constraints, virtualized-search, dependency-lockfiles]

actuals:
  tokens: 12257
  tasks: 2
  commits: 1

tech-stack:
  added: []
  patterns:
    - redacted command evidence with output digests and immutable fixture-manifest hashes
    - unique disposable Compose projects with bounded readiness and fail-closed cleanup
    - exact-release human approval before suspicious dependency installation

key-files:
  created:
    - docs/evidence/phase-04-parser.md
    - tools/phase4_parser_checkpoint.sh
    - .planning/phases/04-localization-import-search-and-constraints/04-07-SUMMARY.md
  modified: []

key-decisions:
  - "The user explicitly approved exactly regex==2026.9.3 and @tanstack/react-virtual==3.14.10 after the blocking package-legitimacy checkpoint; this plan installs neither package."
  - "Canonical persistence, search, and constraints may proceed only from the verified parser evidence ledger, whose ten command records and five manifest hashes all pass."

patterns-established:
  - "Parser checkpoint: host coverage, static analysis, dependency audit, license policy, manifest equality, and isolated backend/worker execution must all pass before downstream authority begins."
  - "Supply-chain checkpoint: approval is release-exact and authorizes only later planned installation, never implicit installation inside the approval plan."

requirements-completed: [FMT-01, FMT-02, FMT-03, FMT-04, FMT-06, CONS-03, SRCH-08]

coverage:
  - id: D1
    description: "Android XML parser boundary is evidence-bound at complete statement and branch coverage."
    requirement: FMT-01
    verification:
      - kind: unit
        ref: "docs/evidence/phase-04-parser.md: Parser package branch coverage — 169 passed at 100 percent"
        status: pass
      - kind: integration
        ref: "bash tools/phase4_parser_checkpoint.sh --container-smoke"
        status: pass
    human_judgment: false
  - id: D2
    description: "Qt TS parser boundary is evidence-bound at complete statement and branch coverage."
    requirement: FMT-02
    verification:
      - kind: unit
        ref: "docs/evidence/phase-04-parser.md: Parser package branch coverage — 169 passed at 100 percent"
        status: pass
    human_judgment: false
  - id: D3
    description: "JSON parser boundary is evidence-bound at complete statement and branch coverage."
    requirement: FMT-03
    verification:
      - kind: unit
        ref: "docs/evidence/phase-04-parser.md: Parser package branch coverage — 169 passed at 100 percent"
        status: pass
    human_judgment: false
  - id: D4
    description: "iOS strings parser boundary is evidence-bound at complete statement and branch coverage."
    requirement: FMT-04
    verification:
      - kind: unit
        ref: "docs/evidence/phase-04-parser.md: Parser package branch coverage — 169 passed at 100 percent"
        status: pass
    human_judgment: false
  - id: D5
    description: "All supported and rejected parser categories remain exactly equal to the five fixture manifests."
    requirement: FMT-06
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_conformance.py#test_fixture_manifest_category_equality"
        status: pass
      - kind: other
        ref: "bash tools/phase4_parser_checkpoint.sh --verify-evidence — 10 commands and 5 manifests"
        status: pass
    human_judgment: false
  - id: D6
    description: "Exact regex 2026.9.3 release approved for a later planned grapheme-aware constraint installation."
    requirement: CONS-03
    verification:
      - kind: manual_procedural
        ref: "User signal: approved regex 2026.9.3 and @tanstack/react-virtual 3.14.10"
        status: pass
      - kind: other
        ref: "backend manifests and lockfile exclude regex at Plan 04-07 completion"
        status: pass
    human_judgment: false
  - id: D7
    description: "Exact @tanstack/react-virtual 3.14.10 release approved for a later planned virtualized-search installation."
    requirement: SRCH-08
    verification:
      - kind: manual_procedural
        ref: "User signal: approved regex 2026.9.3 and @tanstack/react-virtual 3.14.10"
        status: pass
      - kind: other
        ref: "frontend manifests and lockfile exclude @tanstack/react-virtual at Plan 04-07 completion"
        status: pass
    human_judgment: false

duration: 1h38min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 07: Parser Checkpoint and Package Approvals Summary

**A reproducible ten-command parser gate now binds four-format correctness to redacted evidence, while exact human approval unlocks two downstream dependencies without installing them.**

## Performance

- **Duration:** 1h38min, including the blocking human approval handoff
- **Started:** 2026-09-05T07:32:31Z
- **Completed:** 2026-09-05T09:10:17Z
- **Tasks:** 2
- **Files created or modified:** 2

## Accomplishments

- Created a fail-fast parser checkpoint covering 169 tests at 100% statement and branch coverage, Ruff, mypy, dependency audit, license policy, exact manifest equality, and an isolated backend/worker Compose smoke.
- Published a redacted evidence ledger containing ten passing command records, five current fixture-manifest hashes, equal nonempty backend/worker canonical digests, one worker response, zero persistence writes, passing disclosure scans, and confirmed cleanup.
- Recorded explicit human approval for exactly `regex==2026.9.3` and `@tanstack/react-virtual==3.14.10`; neither package was installed by this plan.

## Task Commits

1. **Task 1: Run and record the complete parser checkpoint** - `2b35361` (test)
2. **Task 2: Verify parser evidence and approve the two flagged packages** - satisfied by the exact user approval signal and recorded in this summary

## Files Created/Modified

- `tools/phase4_parser_checkpoint.sh` - Reproducible host, license, manifest, disclosure, and disposable backend/worker parser gate.
- `docs/evidence/phase-04-parser.md` - Redacted immutable command, version, count, duration, digest, and manifest-hash evidence.
- `.planning/phases/04-localization-import-search-and-constraints/04-07-SUMMARY.md` - Records both exact package approvals and plan completion.

## Decisions Made

- The exact user signal `approved regex 2026.9.3 and @tanstack/react-virtual 3.14.10` approves both release identities for their later planned installs.
- Approval is release-specific and does not authorize a different version, package identity, or unplanned direct dependency.
- This approval plan installs neither dependency; lockfile mutation remains owned by downstream implementation plans.
- The verified parser evidence is the sole authority to begin downstream canonical persistence, search, and constraint work.

## Supply-Chain Approvals

| Package | Exact release | Decision | Scope |
|---|---:|---|---|
| `regex` | `2026.9.3` | APPROVED by human on 2026-09-05 | May be installed only by its downstream planned implementation; no installation occurred here. |
| `@tanstack/react-virtual` | `3.14.10` | APPROVED by human on 2026-09-05 | May be installed only by its downstream planned implementation; no installation occurred here. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced a transitive-import persistence assertion with fail-closed method guards**
- **Found during:** Task 1 container smoke
- **Issue:** Importing the application package transitively loads SQLAlchemy modules even when the parser performs no database work, so module-presence incorrectly failed the smoke.
- **Fix:** Guarded SQLAlchemy engine, connection, and session persistence methods so any actual database boundary crossing fails immediately while pure parsing remains valid.
- **Files modified:** `tools/phase4_parser_checkpoint.sh`
- **Verification:** Backend and worker parser probes both passed with equal canonical digests and zero persistence writes.
- **Committed in:** `2b35361`

**2. [Rule 1 - Bug] Preserved actionable container failures and idempotent cleanup**
- **Found during:** Task 1 initial fail-fast runner execution
- **Issue:** A shell-function failure could terminate before the runner recorded its bounded diagnostic, and a second cleanup pass treated an already-removed image as failure.
- **Fix:** Isolated the container command in a cleanup-trapped subshell, parsed only its allowlisted result fields, and made image cleanup idempotent.
- **Files modified:** `tools/phase4_parser_checkpoint.sh`
- **Verification:** The complete runner reports the container command digest and leaves no matching containers, volumes, networks, images, or temporary directories.
- **Committed in:** `2b35361`

**3. [Rule 1 - Bug] Removed a self-triggering evidence sanitization phrase**
- **Found during:** Task 1 evidence generation
- **Issue:** Introductory prose used a forbidden diagnostic keyword and caused the evidence ledger to reject itself despite containing no diagnostic payload.
- **Fix:** Replaced the ambiguous prose while retaining the strict forbidden-content scan.
- **Files modified:** `tools/phase4_parser_checkpoint.sh`, `docs/evidence/phase-04-parser.md`
- **Verification:** Evidence verification passes with ten command records and five manifest hashes.
- **Committed in:** `2b35361`

**4. [Rule 2 - Missing Critical] Confined coverage data to the owner-only runtime directory**
- **Found during:** Task 1 cleanup verification
- **Issue:** The coverage tool otherwise left a generated `.coverage` file at repository root, violating the checkpoint's complete temporary-file cleanup contract.
- **Fix:** Bound `COVERAGE_FILE` to the trap-cleaned owner-only host runtime directory.
- **Files modified:** `tools/phase4_parser_checkpoint.sh`
- **Verification:** A complete runner execution passes and leaves no repository coverage artifact.
- **Committed in:** `2b35361`

---

**Total deviations:** 4 auto-fixed (3 Rule 1 bugs, 1 Rule 2 missing critical cleanup).
**Impact on plan:** All fixes strengthened the planned fail-fast, no-persistence, redaction, and cleanup guarantees without adding dependencies or widening scope.

## Issues Encountered

- The first container rehearsal exposed the transitive-import false positive; the next full run exposed the evidence wording false positive. Both were corrected before the committed evidence was generated and independently reverified.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Verification

- `bash tools/phase4_parser_checkpoint.sh --run` - passed all ten host and isolated-container records; evidence self-verification passed.
- Plan Task 1 exact automated chain - 169 tests passed at 100% coverage; Ruff format/lint, mypy, pip-audit, 106-package license policy, manifest equality, and container smoke passed.
- `test -s docs/evidence/phase-04-parser.md && test -x tools/phase4_parser_checkpoint.sh && bash tools/phase4_parser_checkpoint.sh --verify-evidence` - passed with ten commands and five manifests.
- Backend manifests and lockfile contain no `regex==2026.9.3`; frontend manifests and lockfile contain no `@tanstack/react-virtual==3.14.10`.
- Stub, skipped-test, cleanup, disclosure, and threat-surface scans found no open shipping defect or unplanned trust boundary.

## Next Phase Readiness

- Plans implementing canonical persistence, search, constraints, and browser virtualization may now consume the green parser evidence boundary.
- Downstream plans may install only the two exact approved releases in their intended dependency scopes and must rerun their final vulnerability, license, lockfile, and build gauntlets.
- No parser checkpoint, supply-chain approval, authentication, environment, or cleanup blocker remains.

## Self-Check: PASSED

- The executable runner, evidence ledger, and required summary exist at their declared paths.
- Task commit `2b35361` resolves in repository history with no file deletions.
- Evidence self-verification reports ten passing commands and five current manifest hashes.
- Both approved dependencies remain absent, no coverage artifact remains, and the coverage classifier accepts all seven deliverables.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-05*
