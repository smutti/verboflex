---
phase: 04-localization-import-search-and-constraints
plan: 05
subsystem: localization-parsing
tags: [python, ios-strings, lexer, utf-16, canonical-parser, hypothesis, tdd]

requires:
  - phase: 04-localization-import-search-and-constraints
    plan: 01
    provides: immutable canonical parser contracts, scalar selectors, bounded issues, and the proven iOS preview decoder and lexer seam
provides:
  - complete canonical parsing for strict Apple .strings assignments under UTF-8 and BOM-qualified UTF-16
  - lossless encoding, comment, whitespace, token, source-span, quote, escape, and file-order metadata
  - exact iOS parser resource ceilings with bounded atomic single-file and peer-file failures
  - golden, hostile, boundary, concurrency, and arbitrary-byte iOS fixture coverage
affects: [04-06-parser-conformance, canonical-persistence, localization-write-back]

actuals:
  tokens: 12090
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - metadata-retaining subclass of the proven single-pass preview lexer
    - strict BOM-gated decoding with encoding authority retained in canonical structure
    - deterministic all-values-or-bounded-issues peer-file aggregation

key-files:
  created:
    - backend/src/verboflex/localization/importing/ios_strings.py
    - backend/tests/unit/localization/importing/test_ios_strings.py
    - backend/tests/fixtures/localization/ios/manifest.json
    - backend/tests/fixtures/localization/ios/valid.strings
    - backend/tests/fixtures/localization/ios/valid.expected.json
    - backend/tests/fixtures/localization/ios/invalid_cases.json
  modified: []

key-decisions:
  - "Extend the existing preview decoder and single-pass lexer so canonical parsing inherits its exact escape and surrogate grammar while adding lossless token metadata."
  - "Represent encoding, BOM, comments, whitespace, key/value lexemes, punctuation spans, quote/escape style, and assignment order as version-1 iOS structure and locator metadata outside stable identity."
  - "Enforce exact 1 MiB file, 20 MiB aggregate, 500-file, 5,000-assignment, 4,096-comment, 20,000-token, and 4,096-escape ceilings before returning canonical authority."
  - "Parse peer files in deterministic side/path order and discard all values when any peer, aggregate identity, or resource bound fails."

patterns-established:
  - "iOS identity: decoded key, normalized path language, repository side, and the shared scalar selector define identity; encoding, path, spans, comments, and order remain locators or structure."
  - "iOS preservation: every decoded source character is represented by ordered trivia, key/value token, or separator span metadata, with BOM and encoding retained separately."
  - "iOS safety: unsupported encodings and syntax, unsafe controls, duplicate decoded keys, excessive work, and arbitrary bytes return only closed source-free issues."

requirements-completed: [FMT-04, FMT-06]

coverage:
  - id: D1
    description: Strict UTF-8 and BOM-qualified UTF-16 Apple .strings assignments emit exact scalar canonical values with normalized language and side-aware source or translated text.
    requirement: FMT-04
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_ios_strings.py#test_ios_valid_golden_manifest_emits_complete_scalar_values"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_ios_strings.py#test_ios_encoding_variants_have_equal_semantics_and_distinct_metadata"
        status: pass
    human_judgment: false
  - id: D2
    description: Comments, whitespace, source spans, quote and escape style, Unicode and surrogate decoding, file order, and empty translations remain lossless canonical metadata.
    requirement: FMT-04
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_ios_strings.py#test_ios_comments_whitespace_and_source_spans_preserve_the_document"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_ios_strings.py#test_ios_escape_sequences_decode_without_losing_lexical_style"
        status: pass
    human_judgment: false
  - id: D3
    description: Hostile grammar and encodings, duplicate decoded keys, exact resource boundaries, peer failures, concurrency, and arbitrary bytes remain deterministic, bounded, source-free, and atomic.
    requirement: FMT-06
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_ios_strings.py#test_ios_hostile_fixture_inventory_fails_atomically_and_source_free"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_ios_strings.py#test_ios_file_assignment_comment_token_and_escape_limits_are_exact"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_ios_strings.py#test_ios_peer_files_fail_atomically_and_obey_file_and_aggregate_limits"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_ios_strings.py#test_ios_concurrent_calls_are_byte_equal_and_failure_isolated"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_ios_strings.py#test_arbitrary_ios_bytes_never_escape_or_return_partial_values"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-09-04
status: complete
---

# Phase 04 Plan 05: iOS Strings Canonical Adapter Summary

**A metadata-retaining extension of the proven iOS lexer now emits exact scalar canonical values across strict UTF-8 and BOM-qualified UTF-16 while rejecting hostile or excessive input atomically.**

## Performance

- **Duration:** 12min
- **Started:** 2026-09-04T21:52:59Z
- **Completed:** 2026-09-04T22:05:36Z
- **Tasks:** 2
- **Files created or modified:** 6

## Accomplishments

- Parsed quoted Apple `.strings` assignments into exact decoded scalar values across UTF-8, optional UTF-8 BOM, and BOM-qualified UTF-16 LE/BE without accepting heuristic encodings or `.stringsdict` structures.
- Preserved BOM/encoding, every comment and whitespace run, key/value raw lexemes and character spans, separator spans, quote/escape style, source order, normalized language, and explicit empty translations outside stable identity.
- Added a manifest-backed hostile and exact-boundary suite proving duplicate, malformed, control, encoding, token, batch, concurrency, and arbitrary-byte failures return zero partial values and bounded source-free issues.

## Task Commits

1. **Task 1 RED: specify complete scalar and lexical preservation** - `ef4a58e` (test)
2. **Task 1 GREEN: parse canonical iOS strings values** - `0ba0f8e` (feat)
3. **Task 2 RED: specify hostile input, exact boundaries, peers, and concurrency** - `5f1b1e1` (test)
4. **Task 2 GREEN: harden canonical iOS strings parsing** - `57f476a` (feat)

No separate refactor commit was needed; the GREEN implementation remained a direct extension of the established lexer and canonical-result patterns.

## Files Created/Modified

- `backend/src/verboflex/localization/importing/ios_strings.py` - Strict decoder/lexer adapter, lossless lexical metadata, scalar canonical mapping, exact resource accounting, safe issues, and atomic peer aggregation.
- `backend/tests/unit/localization/importing/test_ios_strings.py` - Golden, encoding, escape, comment/span, hostile, limit, peer, concurrency, authority, and arbitrary-byte coverage.
- `backend/tests/fixtures/localization/ios/valid.strings` - Real `.strings` source covering comments, escaped key identity, controls, Unicode, surrogate pairs, and an empty value.
- `backend/tests/fixtures/localization/ios/valid.expected.json` - Hand-authored semantic and lexical golden projection.
- `backend/tests/fixtures/localization/ios/invalid_cases.json` - Malformed encoding, grammar, control, duplicate, escape, surrogate, comment, and string corpus.
- `backend/tests/fixtures/localization/ios/manifest.json` - Required category, fixture, and exact-limit inventory for conformance reuse.

## Decisions Made

- Reused the preview decoder and inherited lexer state machine rather than introducing a second escape/surrogate grammar.
- Kept only the decoded key and scalar selector in semantic identity; all lexical and encoding facts are write-back-grade structure or locator metadata.
- Applied resource ceilings during lexing and before batch work, then validated duplicates only after complete lexical parsing so malformed suffixes cannot be hidden by an earlier duplicate.
- Used one generic bounded message per closed issue code and retained only safe coordinates, never repository excerpts or decoder exceptions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected an invalid adjacency assertion in the Task 1 RED test**
- **Found during:** Task 1 GREEN verification
- **Issue:** The span coverage assertion used `zip(..., strict=True)` on a sequence and its one-element-short tail, so Python correctly raised even when every span was contiguous.
- **Fix:** Made the intentionally unequal adjacent-pair traversal explicit with `strict=False`; the original RED failure remained the missing canonical adapter.
- **Files modified:** `backend/tests/unit/localization/importing/test_ios_strings.py`
- **Verification:** The complete Task 1 focused command passed all 13 selected cases after correction.
- **Committed in:** `0ba0f8e`

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug).
**Impact on plan:** The correction fixed only the test oracle; no production behavior or scope changed.

## Issues Encountered

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## TDD Gate Compliance

- Task 1 RED `ef4a58e` failed on the absent adapter before GREEN `0ba0f8e` supplied scalar and lexical preservation.
- Task 2 RED `5f1b1e1` failed on absent limit, issue-bound, and peer-parser contracts before GREEN `57f476a` supplied them.
- Both required RED commits precede their corresponding GREEN commits; no separate refactor was necessary.

## Verification

- `uv run --project backend pytest backend/tests/unit/localization/importing/test_ios_strings.py -q` - 20 passed.
- `uv run --project backend pytest backend/tests/unit/localization/importing -q` - 124 passed.
- `uv run --project backend pytest backend/tests/unit/localization/preview/test_ios_strings.py -q` - 48 passed.
- `uv run --project backend ruff check backend/src/verboflex/localization/importing/ios_strings.py backend/tests/unit/localization/importing/test_ios_strings.py` - passed.
- `uv run --project backend ruff format --check backend/src/verboflex/localization/importing/ios_strings.py backend/tests/unit/localization/importing/test_ios_strings.py` - passed.
- `uv run --project backend mypy backend/src/verboflex/localization/importing/ios_strings.py` - passed.
- Parser dependency-isolation scan for SQLAlchemy, FastAPI, Celery, Bitbucket, and network clients - no matches.

## Next Phase Readiness

- Plan 04-06 can register all four complete adapters and reuse the iOS golden/hostile manifest in the cross-format conformance and direct/separate aggregation matrix.
- Canonical persistence receives deterministic iOS scalar identities and complete write-back-grade locators or bounded atomic failures.
- No blockers or external setup remain.

## Self-Check: PASSED

All six declared adapter, test, and fixture files plus this summary exist; all four TDD commits resolve in RED/GREEN order; the final focused, canonical-regression, adjacent-preview, Ruff, formatting, MyPy, dependency-isolation, stub, and coverage-classification checks pass.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-04*
