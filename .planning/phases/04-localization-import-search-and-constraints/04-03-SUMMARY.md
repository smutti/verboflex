---
phase: 04-localization-import-search-and-constraints
plan: 03
subsystem: localization-parsing
tags: [python, qt-ts, defusedxml, canonical-parser, hypothesis, tdd]

requires:
  - phase: 04-localization-import-search-and-constraints
    plan: 01
    provides: immutable canonical parser contracts, typed Qt selectors, validated result atomicity, and safe preview XML utilities
provides:
  - complete Qt TS 2.0/2.1 canonical parsing for ID/source identity, context metadata, locations, numerus forms, length variants, and lifecycle status
  - hand-authored structured golden fixtures plus a machine-readable hostile and boundary corpus
  - deterministic bounded multi-file aggregation with failure-atomic peer handling
affects: [04-06-parser-conformance, canonical-persistence, localization-import-workers, qt-write-back]

actuals:
  tokens: 17811
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - hardened allowlist parsing for the exact Qt TS 2.0/2.1 grammar
    - typed selectors that separate raw Qt ID/source keys from context, disambiguation, form, and priority identity
    - exact-limit preflight with bounded deterministic peer-file aggregation

key-files:
  created:
    - backend/src/verboflex/localization/importing/qt_ts.py
    - backend/tests/unit/localization/importing/test_qt_ts.py
    - backend/tests/fixtures/localization/qt/valid_structured.ts
    - backend/tests/fixtures/localization/qt/valid_structured.expected.json
    - backend/tests/fixtures/localization/qt/manifest.json
    - backend/tests/fixtures/localization/qt/invalid_cases.json
  modified: []

key-decisions:
  - "Use the exact Qt message ID as the raw key when present; otherwise use source text while keeping context and disambiguation in typed selector fields."
  - "Represent numerus ordinals and length-variant priorities with existing Qt selector kinds while treating repeated source locations as mutable provenance only."
  - "Map active and unfinished translations to Draft, retain obsolete and vanished content as deleted records, and never derive VerboFlex approval from Qt lifecycle metadata."
  - "Reject non-allowlisted XML structure atomically and aggregate peer files only after exact byte, file, value, and identity checks succeed."

patterns-established:
  - "Qt identity: raw ID/source keys remain stable while context, disambiguation, form index, and priority distinguish canonical selector identity."
  - "Qt status: upstream lifecycle state is typed provenance and deletion evidence, never review approval authority."
  - "Qt failure atomicity: any malformed, hostile, ambiguous, duplicate, or over-budget input returns no canonical values and only bounded source-free issues."

requirements-completed: [FMT-02, FMT-06]

coverage:
  - id: D1
    description: Qt ID/source messages, contexts, metadata, locations, numerus forms, length variants, and lifecycle states produce exact deterministic canonical records.
    requirement: FMT-02
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_qt_ts.py (structured golden, selector identity, lifecycle, and location tests)"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/preview/test_qt_ts.py (47 adjacent regression tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: Hostile XML, invalid encodings, arbitrary bytes, duplicate identities, peer failures, and every exact Qt parser boundary remain fail-closed, bounded, deterministic, and network-free.
    requirement: FMT-06
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_qt_ts.py (hostile corpus, boundary, concurrency, and Hypothesis arbitrary-byte tests)"
        status: pass
      - kind: other
        ref: "uv run --project backend mypy backend/src/verboflex/localization/importing"
        status: pass
    human_judgment: false

duration: 19min
completed: 2026-09-04
status: complete
---

# Phase 04 Plan 03: Qt TS Canonical Adapter Summary

**A hardened Qt TS 2.0/2.1 adapter now emits stable ID/source identities, typed numerus and length-variant records, lossless metadata and locations, and deterministic all-or-nothing results under hostile or over-budget input.**

## Performance

- **Duration:** 19min
- **Started:** 2026-09-04T21:18:36Z
- **Completed:** 2026-09-04T21:37:51Z
- **Tasks:** 2
- **Files created or modified:** 6

## Accomplishments

- Implemented the exact supported Qt TS 2.0/2.1 root, dependency, context, message, location, metadata, translation, numerus, and length-variant grammar with typed canonical structure.
- Preserved raw ID/source identity separately from context and disambiguation while representing numerus indexes and variant priorities as collision-safe selectors and locations as non-identity provenance.
- Added hardened XML/encoding rejection, exact file/batch/cardinality/depth ceilings, arbitrary-byte safety, deterministic concurrency, canonical duplicate detection, and atomic peer-file aggregation.

## Task Commits

1. **Task 1 RED: specify complete Qt canonical message behavior** - `5460c86` (test)
2. **Task 1 GREEN: implement Qt canonical message parsing** - `14fb2ba` (feat)
3. **Task 2 RED: specify hostile, boundary, and concurrency behavior** - `04724ba` (test)
4. **Task 2 GREEN: harden Qt canonical parsing** - `213af06` (feat)

## Files Created/Modified

- `backend/src/verboflex/localization/importing/qt_ts.py` - Hardened Qt parser, typed identity and structure mapping, exact limits, and deterministic peer aggregation.
- `backend/tests/unit/localization/importing/test_qt_ts.py` - Exact golden, lifecycle, malicious-input, boundary, concurrency, atomicity, and arbitrary-byte coverage.
- `backend/tests/fixtures/localization/qt/valid_structured.ts` - Structured Qt TS source covering root metadata, contexts, identity variants, locations, numerus forms, length variants, and lifecycle states.
- `backend/tests/fixtures/localization/qt/valid_structured.expected.json` - Hand-authored exact canonical projection for the structured source.
- `backend/tests/fixtures/localization/qt/manifest.json` - Required fixture categories and exact Qt parser limit manifest.
- `backend/tests/fixtures/localization/qt/invalid_cases.json` - Hostile, malformed, unsupported, ambiguous, encoding, control-character, and duplicate-identity corpus.

## Decisions Made

- Qt message IDs and source fallback text remain raw logical keys; context and disambiguation distinguish only source-based selector identity.
- Numerus ordinals and length-variant priorities are typed selector fields, while repeated locations remain ordered provenance that cannot change canonical identity.
- Qt active and unfinished state imports as Draft; obsolete and vanished state retains content and provenance as deleted records without granting approval.
- Batch parsing sorts peer inputs, preflights exact limits, bounds and sorts safe issues, and discards all candidate values if any peer or complete identity fails.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Preview and importing Qt tests share the same module basename under the repository's pytest import mode. They were run as separate invocations; all 89 importing tests and all 47 Qt preview tests passed.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None in the files created or modified by this plan.

## TDD Gate Compliance

- RED `5460c86` precedes GREEN `14fb2ba` for Qt identity, numerus, variants, locations, and lifecycle behavior.
- RED `04724ba` precedes GREEN `213af06` for hostile-input, exact-boundary, concurrency, duplicate, and peer-file atomicity behavior.
- The final focused suite reports 22 passing tests; the complete importing package reports 89 passing tests.

## Next Phase Readiness

- Plan 04-06 can register the Qt adapter alongside the shared format dispatch and reuse the manifest-backed corpus for cross-format conformance.
- Canonical persistence receives deterministic typed Qt identities, preserved supported structure, and either a complete ordered value set or a bounded issue set.

## Self-Check: PASSED

All six declared implementation, test, and fixture files plus this summary exist; all four TDD task commits resolve in RED/GREEN order; the final 22-test Qt adapter suite, 89-test importing package, 47-test adjacent Qt preview suite, and 23-test shared contract suite pass; Ruff, formatting, MyPy, diff integrity, and stub/skip scans are clean.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-04*
