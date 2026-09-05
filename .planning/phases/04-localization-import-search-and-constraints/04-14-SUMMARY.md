---
phase: 04-localization-import-search-and-constraints
plan: 14
subsystem: localization-constraints
tags: [unicode, uax29, grapheme-clusters, regex, hypothesis]

requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [07]
    provides: explicit human approval for exactly regex 2026.9.3
provides:
  - one pure backend authority for UAX #29 extended grapheme counting
  - exact regex 2026.9.3 runtime pin and reproducible uv lock identity
  - Unicode golden and property coverage for visible display-text counting
affects: [constraint-recomputation, import-activation, translation-detail, approval-eligibility]

actuals:
  tokens: 4364
  tasks: 1
  commits: 2

tech-stack:
  added: [regex==2026.9.3]
  patterns:
    - one compiled extended-grapheme matcher shared by every backend constraint path
    - explicit package-plus-contract version attached to persisted count authority

key-files:
  created:
    - backend/src/verboflex/localization/graphemes.py
    - backend/tests/unit/localization/test_grapheme_count.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock

key-decisions:
  - "GRAPHEME_ALGORITHM_VERSION combines the exact installed regex release with the UAX #29 extended-grapheme contract."
  - "The counter accepts only str display_text, performs no normalization or markup parsing, and streams matches from one compiled regex pattern."

patterns-established:
  - "Visible-text counting: parsers and later services pass display_text to grapheme_count; raw format markup never enters this module."
  - "Absent text remains explicit: None and every non-string input raise TypeError instead of producing a misleading zero."

requirements-completed: [CONS-03, CONS-04]

coverage:
  - id: D1
    description: "A versioned backend function counts UAX #29 extended grapheme clusters over visible display text."
    requirement: CONS-03
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/test_grapheme_count.py — 24 passed"
        status: pass
      - kind: other
        ref: "uv run --project backend pip check"
        status: pass
    human_judgment: false
  - id: D2
    description: "The reusable count authority preserves exact integer boundary behavior for later import and edit recomputation paths."
    requirement: CONS-04
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/test_grapheme_count.py#test_count_is_an_exact_nonnegative_integer_at_limit_boundaries"
        status: pass
    human_judgment: false
  - id: D3
    description: "The approved regex release is exact-pinned in both project metadata and the uv lock without another direct dependency."
    requirement: CONS-03
    verification:
      - kind: other
        ref: "uv lock --project backend --check; pip-audit; pip-licenses regex identity"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 14: Versioned Unicode Grapheme Counter Summary

**Exact-pinned regex 2026.9.3 now provides one pure, versioned, compiled-`\\X` backend authority for visible Unicode grapheme counts.**

## Performance

- **Duration:** 5min
- **Started:** 2026-09-05T09:33:49Z
- **Completed:** 2026-09-05T09:39:10Z
- **Tasks:** 1
- **Files created or modified:** 4

## Accomplishments

- Installed only the human-approved `regex==2026.9.3` release and recorded its canonical PyPI artifacts and hashes in `uv.lock`.
- Added `grapheme_count(display_text: str) -> int` backed by one compiled UAX #29 `\\X` matcher, with explicit non-string rejection and no normalization or markup reparsing.
- Added 24 golden/property cases for empty, ASCII, composed/decomposed accents, modifiers, ZWJ emoji, flags, CRLF, RTL, multiline, adjacency, ordering, absence, versioning, and exact limit boundaries.

## TDD Gate Compliance

- **RED — `83f87a0`:** 24 focused tests failed because `verboflex.localization.graphemes` did not yet exist; no production or dependency files had changed.
- **GREEN — `dd424b1`:** the exact dependency pin and minimal compiled matcher made all 24 focused tests pass.
- **REFACTOR:** Not needed. The GREEN implementation is already one constant, one compiled matcher, one explicit type guard, and one public function.

## Task Commits

1. **RED: Add failing grapheme counter contract** - `83f87a0` (test)
2. **GREEN: Implement versioned grapheme counting** - `dd424b1` (feat)

## Files Created/Modified

- `backend/src/verboflex/localization/graphemes.py` - Pure versioned extended-grapheme counter over caller-supplied visible text.
- `backend/tests/unit/localization/test_grapheme_count.py` - Unicode golden, property, type, ordering, and boundary coverage.
- `backend/pyproject.toml` - Exact approved `regex==2026.9.3` direct dependency.
- `backend/uv.lock` - Canonical release artifacts, hashes, and project dependency edge.

## Decisions Made

- Version count authority as `regex==2026.9.3;uax29=extended_grapheme_clusters`, deriving the package part from the installed module so the runtime record cannot silently disagree with the exact pin.
- Keep structure removal at the parser boundary: this utility counts only `display_text` and deliberately does not interpret XML, Qt, JSON, iOS syntax, or HTML-like markup.
- Iterate compiled matches instead of materializing a match list, keeping auxiliary memory constant for upstream-bounded repository text.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Kept strict mypy compatible without adding an unapproved package**
- **Found during:** Task 1 GREEN static verification
- **Issue:** The approved `regex` distribution exposes the required runtime API but publishes no type metadata, so strict mypy rejected its import.
- **Fix:** Added the narrow `import-untyped` suppression on the single `regex` import; no replacement or additional dependency was installed.
- **Files modified:** `backend/src/verboflex/localization/graphemes.py`
- **Verification:** `uv run --project backend mypy backend/src/verboflex/localization/graphemes.py` passes.
- **Committed in:** `dd424b1`

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking issue).
**Impact on plan:** The adjustment preserves strict project checking and the approved dependency boundary without changing behavior or architecture.

## Issues Encountered

None. The already-recorded duplicate test-module namespace collision prevents collecting both localization subtrees in one pytest invocation; their separate adjacent runs passed with 169 importing tests and 181 preview tests.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Verification

- `uv run --project backend pytest backend/tests/unit/localization/test_grapheme_count.py -q` - 24 passed.
- `uv run --project backend pytest backend/tests/unit/localization/importing -q` - 169 passed.
- `uv run --project backend pytest backend/tests/unit/localization/preview -q` - 181 passed.
- `uv run --project backend pip check` - no broken requirements.
- `uv lock --project backend --check` - 113 packages resolved with a current lock.
- Targeted Ruff formatting/lint and strict mypy - passed.
- `uv run --project backend pip-audit` - no known vulnerabilities; the local project was the only unauditable package.
- `uv run --project backend pip-licenses --packages regex --format=json --with-urls` - exact 2026.9.3 identity, canonical upstream URL, and `Apache-2.0 AND CNRI-Python` license metadata.
- Acceptance checks confirmed the exact direct dependency delta, one exact lock package, one public function, one compiled `\\X` matcher, deterministic counts, and no `len(display_text)` implementation.

## Next Phase Readiness

- Plan 04-21 can import this function for transaction-bound constraint recomputation after activation, constraint mutation/removal, and the future translation-edit seam.
- No package, Unicode behavior, security, typing, or test blocker remains for downstream constraint work.

## Self-Check: PASSED

- All four declared implementation/test/dependency files and this summary exist.
- RED commit `83f87a0` and GREEN commit `dd424b1` resolve in repository history with no file deletions.
- Required frontmatter, verification, stub disclosure, and exact requirement IDs are present.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-05*
