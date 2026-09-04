---
phase: 04-localization-import-search-and-constraints
plan: 04
subsystem: localization-parsing
tags: [python, json, canonical-contract, typed-selectors, tdd]

requires:
  - phase: 04-localization-import-search-and-constraints
    plan: 01
    provides: immutable canonical parser contracts, typed selectors, bounded issues, and deterministic ordering
provides:
  - strict duplicate-aware canonical parsing for flat-per-locale and locale-rooted JSON
  - raw JSON leaf identity with ordered typed parent-path selectors and source-order locators
  - exact JSON file, aggregate, peer-file, member, value, depth, and issue ceilings
  - hostile, golden, boundary, concurrency, and arbitrary-byte JSON fixture coverage
affects: [04-06-parser-conformance, canonical-persistence, localization-write-back]

actuals:
  tokens: 9585
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - stdlib JSON object-pair decoding with duplicate rejection before canonical traversal
    - iterative tree-budget validation before recursive canonical value construction
    - immutable all-values-or-bounded-issues parser and peer-file results

key-files:
  created:
    - backend/src/verboflex/localization/importing/json.py
    - backend/tests/unit/localization/importing/test_json.py
    - backend/tests/fixtures/localization/json/manifest.json
    - backend/tests/fixtures/localization/json/valid_nested.json
    - backend/tests/fixtures/localization/json/valid_nested.expected.json
    - backend/tests/fixtures/localization/json/invalid_cases.json
  modified: []

key-decisions:
  - "Keep each decoded leaf member as the raw logical key and store only its ordered parent members in the version-1 json_path selector."
  - "Use the confirmed layout identity to distinguish recursively nested flat-per-locale data from locale-rooted data; mixed locale roots fail atomically."
  - "Reject UTF-8 BOMs, invalid UTF-8, unpaired surrogates, unsafe controls, duplicate members, non-finite constants, and every non-object/non-string node without coercion."
  - "Apply exact 1 MiB file, 20 MiB aggregate, 500-file, 5,000-member, 5,000-value, and depth-12 ceilings before publishing any values."

patterns-established:
  - "JSON identity: normalized language, raw leaf name, and the ordered parent tuple form canonical value identity; dots and brackets are never parsed as path syntax."
  - "JSON location: decoded member names and zero-based source member indexes remain in the mutable structural address while canonical results use shared deterministic ordering."
  - "JSON safety: decoding and tree accounting complete before canonical output, and peer files return no values when any file fails."

requirements-completed: [FMT-03, FMT-06]

coverage:
  - id: D1
    description: Flat-per-locale and locale-rooted JSON recursively emit every string leaf with raw keys, typed parent paths, source-order locators, and correct source/translation projection.
    requirement: FMT-03
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_json.py#test_json_nested_locale_rooted_golden_manifest"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_json.py#test_json_flat_per_locale_recurses_and_retains_source_order_in_locators"
        status: pass
    human_judgment: false
  - id: D2
    description: JSON decoding rejects every duplicate, malformed encoding, unsafe string, unsupported scalar, non-finite value, and ambiguous root as one bounded source-free failure.
    requirement: FMT-03
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_json.py#test_json_hostile_fixture_inventory_fails_atomically_and_source_free"
        status: pass
      - kind: unit
        ref: "backend/tests/fixtures/localization/json/invalid_cases.json"
        status: pass
    human_judgment: false
  - id: D3
    description: Exact JSON resource limits, atomic peer parsing, deterministic concurrency, and arbitrary-byte exception safety are executable and covered by the format manifest.
    requirement: FMT-06
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_json.py#test_json_file_member_value_and_depth_limits_are_exact"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_json.py#test_json_peer_files_fail_atomically_and_obey_file_and_aggregate_limits"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_json.py#test_json_concurrent_calls_are_byte_equal_and_failure_isolated"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_json.py#test_arbitrary_json_bytes_never_escape_or_return_partial_values"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-09-04
status: complete
---

# Phase 04 Plan 04: Strict Canonical JSON Adapter Summary

**Duplicate-aware flat and nested JSON parsing now produces immutable typed-path canonical values under exact resource ceilings, with atomic bounded failures for every unsupported or unsafe document.**

## Performance

- **Duration:** 9min
- **Started:** 2026-09-04T21:40:54Z
- **Completed:** 2026-09-04T21:49:59Z
- **Tasks:** 2
- **Files created or modified:** 6

## Accomplishments

- Parsed confirmed flat-per-locale and locale-rooted JSON recursively while preserving raw leaf identity, ordered parent selectors, normalized language, side-aware source/translation text, and source-order locators.
- Rejected duplicate members, ambiguous locale roots, invalid encodings and strings, non-finite constants, arrays, and non-string scalar leaves without partial output or source leakage.
- Enforced exact file, aggregate, file-count, member, value, depth, and issue bounds with deterministic concurrent, peer-file, and arbitrary-byte behavior.

## Task Commits

1. **Task 1 RED: specify flat and nested canonical JSON values** - `5638469` (test)
2. **Task 1 GREEN: parse canonical JSON string leaves** - `4612dc5` (feat)
3. **Task 2 RED: specify hostile inputs and exact bounds** - `0fb2a22` (test)
4. **Task 2 GREEN: harden canonical JSON parsing** - `3910c4c` (feat)

No separate refactor commit was needed; the green implementation retained the smallest adapter surface that satisfies both behavior slices.

## Files Created/Modified

- `backend/src/verboflex/localization/importing/json.py` - Strict ordered decoding, canonical traversal, resource accounting, atomic peer parsing, and bounded issue mapping.
- `backend/tests/unit/localization/importing/test_json.py` - Golden, identity, empty, hostile, exact-boundary, concurrency, and property coverage.
- `backend/tests/fixtures/localization/json/valid_nested.json` - Locale-rooted nested source fixture with repeated leaves, punctuation, and empty values.
- `backend/tests/fixtures/localization/json/valid_nested.expected.json` - Hand-authored expected canonical projection.
- `backend/tests/fixtures/localization/json/invalid_cases.json` - Duplicate, malformed, encoding, control, mixed-root, and non-string hostile corpus.
- `backend/tests/fixtures/localization/json/manifest.json` - Format categories, exact limits, and fixture inventory for later conformance checks.

## Decisions Made

- The `json_path` selector stores one ordered `parents` tuple; the leaf member itself remains the byte-preserved decoded logical key.
- Confirmed layout identity is authoritative: flat layouts obtain language from the exact path template, while locale-rooted layouts normalize each root member and reject canonical locale collisions.
- Empty objects are valid zero-value documents only with a valid configured base language; empty strings remain real canonical values.
- Resource preflight and full-tree accounting precede canonical construction so no prefix of an oversized or invalid document can escape.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Authentication Gates

None.

## Known Stubs

None.

## TDD Gate Compliance

- Task 1 RED `5638469` failed because the canonical JSON module did not exist, then GREEN `4612dc5` passed the focused flat, nested, and empty suite.
- Task 2 RED `0fb2a22` failed on absent exact-limit and peer-parser contracts plus unsafe-string taxonomy, then GREEN `3910c4c` passed the complete JSON suite.
- RED and GREEN gates appear in the required order; no refactor commit was necessary.

## Verification

- `uv run --project backend pytest backend/tests/unit/localization/importing/test_json.py -q` - 15 passed.
- `uv run --project backend pytest backend/tests/unit/localization/importing -q` - 104 passed.
- `uv run --project backend pytest backend/tests/unit/localization/preview/test_json.py -q` - 58 passed.
- `uv run --project backend ruff check backend/src/verboflex/localization/importing/json.py backend/tests/unit/localization/importing/test_json.py` - passed.
- `uv run --project backend ruff format --check backend/src/verboflex/localization/importing/json.py backend/tests/unit/localization/importing/test_json.py` - passed.
- `uv run --project backend mypy backend/src/verboflex/localization/importing/json.py` - passed.
- Parser dependency-isolation scan for SQLAlchemy, FastAPI, Celery, Bitbucket, and network clients - no matches.

## Next Phase Readiness

- Plan 04-05 can implement the iOS `.strings` adapter against the same immutable result and bounded issue contracts.
- Plan 04-06 can register all four adapters and prove mapping-level limits and direct/separate conformance using the JSON manifest.
- No blockers or required external setup remain.

## Self-Check: PASSED

All six declared adapter, test, and fixture files plus this summary exist; all four TDD commits resolve in RED/GREEN order; focused, canonical-regression, adjacent-preview, Ruff, formatting, MyPy, dependency-isolation, stub, and threat-surface checks pass.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-04*
