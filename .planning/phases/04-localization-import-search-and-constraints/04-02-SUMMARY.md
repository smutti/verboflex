---
phase: 04-localization-import-search-and-constraints
plan: 02
subsystem: localization-parsing
tags: [python, android-xml, defusedxml, canonical-parser, hypothesis, tdd]

requires:
  - phase: 04-localization-import-search-and-constraints
    plan: 01
    provides: immutable canonical parser contracts, validated result atomicity, and the Android scalar tracer
provides:
  - production Android XML canonical parsing for strings, plurals, string arrays, escapes, and allowlisted inline markup
  - hand-authored structured golden fixtures plus a machine-readable hostile and boundary corpus
  - deterministic bounded multi-file aggregation with failure-atomic peer handling
affects: [04-06-parser-conformance, canonical-persistence, localization-import-workers]

actuals:
  tokens: 15228
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - event-preserving XML parsing through a hardened custom ElementTree target
    - typed Android selectors for quantities and array positions
    - exact-limit preflight with bounded deterministic peer-file aggregation

key-files:
  created:
    - backend/tests/fixtures/localization/android/valid_structured.xml
    - backend/tests/fixtures/localization/android/valid_structured.expected.json
    - backend/tests/fixtures/localization/android/manifest.json
    - backend/tests/fixtures/localization/android/invalid_cases.json
  modified:
    - backend/src/verboflex/localization/importing/android_xml.py
    - backend/tests/unit/localization/importing/test_android_xml.py

key-decisions:
  - "Represent Android plural and string-array identity with the existing typed selector contract while preserving raw resource names byte-for-byte after strict UTF-8 decoding."
  - "Preserve semantic XML content as ordered text, tail, comment, CDATA, and allowlisted inline-node events while deriving display text from decoded semantic text only."
  - "Accept only b, i, u, and XLIFF 1.2 g inline markup with exact attribute contracts; reject all other elements, namespaces, and ambiguous shapes atomically."
  - "Apply exact file, aggregate, value, depth, structure-node, and issue bounds before returning any peer-file values."

patterns-established:
  - "Android structure: supported inline XML becomes a flat ordered event stream that retains text boundaries, comments, CDATA, tag attributes, and tails without reserializing source XML."
  - "Android failure atomicity: a failure in any peer input returns no values, a closed sorted issue set, and no source bytes or parser exceptions."
  - "Android limits: exact declared maxima pass and the first unit over each maximum fails with one of the canonical bounded issue codes."

requirements-completed: [FMT-01, FMT-06]

coverage:
  - id: D1
    description: Android scalar, plural, array, escape, Unicode, comment, CDATA, tail, and allowlisted markup resources produce exact canonical records from a hand-authored golden fixture.
    requirement: FMT-01
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_android_xml.py (structured golden and semantic-node tests)"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/preview/test_android_xml.py (28 adjacent regression tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: Hostile XML, invalid encodings, arbitrary bytes, duplicate identities, peer failures, and every exact parser boundary remain fail-closed, bounded, deterministic, and network-free.
    requirement: FMT-06
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_android_xml.py (boundary corpus and Hypothesis arbitrary-byte tests)"
        status: pass
      - kind: other
        ref: "uv run --project backend mypy backend/src/verboflex/localization/importing"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-09-04
status: complete
---

# Phase 04 Plan 02: Android XML Canonical Adapter Summary

**A hardened Android XML adapter now emits exact canonical scalar, plural, and array records with preserved semantic structure while enforcing deterministic, failure-atomic resource limits across individual and peer files.**

## Performance

- **Duration:** 20min
- **Started:** 2026-09-04T20:55:50Z
- **Completed:** 2026-09-04T21:15:38Z
- **Tasks:** 2
- **Files created or modified:** 6

## Accomplishments

- Extended the production Android adapter from scalar strings to plurals and string arrays with typed selector identity, Android escape decoding, Unicode preservation, and exact source/translation-side behavior.
- Preserved comments, CDATA, text/tail boundaries, and supported `b`, `i`, `u`, and XLIFF 1.2 `g` markup in an ordered canonical structure while excluding markup from display text.
- Added strict UTF-8/BOM handling, hardened XML rejection, exact byte/file/value/depth/structure/issue limits, arbitrary-byte safety, and deterministic all-or-nothing peer-file aggregation.

## Task Commits

1. **Task 1 RED: specify structured Android canonical output** - `0ff9963` (test)
2. **Task 1 GREEN: parse Android structured resources** - `d23b740` (feat)
3. **Task 2 RED: specify hostile and boundary behavior** - `c0c6274` (test)
4. **Task 2 GREEN: bound Android canonical parsing** - `7270dc5` (feat)

## Files Created/Modified

- `backend/src/verboflex/localization/importing/android_xml.py` - Hardened event-preserving Android parser, semantic validation, exact limits, and failure-atomic peer-file aggregation.
- `backend/tests/unit/localization/importing/test_android_xml.py` - Exact golden, malicious-input, boundary, atomicity, network-isolation, and arbitrary-byte coverage.
- `backend/tests/fixtures/localization/android/valid_structured.xml` - Structured Android source covering scalars, plurals, arrays, escapes, comments, CDATA, tails, and supported markup.
- `backend/tests/fixtures/localization/android/valid_structured.expected.json` - Hand-authored exact canonical output for the structured source.
- `backend/tests/fixtures/localization/android/manifest.json` - Required fixture categories and parser limit manifest.
- `backend/tests/fixtures/localization/android/invalid_cases.json` - Hostile, malformed, unsupported, encoding, control-character, and duplicate-key corpus.

## Decisions Made

- Android plural quantities and string-array indexes use the existing typed canonical selectors rather than encoding identity into logical keys.
- Semantic structure is a flat ordered event stream so text, tag boundaries, tails, comments, and CDATA remain distinguishable without storing or reserializing raw source XML.
- Inline markup is fail-closed: only attribute-free `b`, `i`, and `u`, plus exact XLIFF 1.2 `g` attributes, are accepted.
- Batch parsing preflights exact aggregate limits and returns no values whenever any peer file produces an issue or duplicate canonical identity.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Preview and importing Android tests share the same module basename under the repository's pytest import mode. They were run as separate invocations; all 67 importing tests and all 28 Android preview tests passed.

## Authentication Gates

None.

## Known Stubs

None in the files created or modified by this plan.

## TDD Gate Compliance

- RED `0ff9963` precedes GREEN `d23b740` for structured Android resource behavior.
- RED `c0c6274` precedes GREEN `7270dc5` for hostile-input, exact-boundary, and peer-file atomicity behavior.
- The final focused suite reports 44 passing tests; the complete importing package reports 67 passing tests.

## Next Phase Readiness

- Plan 04-06 can reuse the Android fixture manifest and exact-limit behavior for cross-format conformance and import-level aggregation.
- Canonical persistence receives deterministic typed selectors, lossless semantic structure, and either a complete ordered value set or a bounded issue set.

## Self-Check: PASSED

All six declared implementation, test, and fixture files plus this summary exist; all four TDD task commits resolve in RED/GREEN order; the final 44-test Android adapter suite, 67-test importing package, and 28-test adjacent Android preview suite pass; Ruff, formatting, MyPy, diff integrity, and stub/skip scans are clean.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-04*
