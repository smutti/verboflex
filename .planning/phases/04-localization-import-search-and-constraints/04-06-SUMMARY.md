---
phase: 04-localization-import-search-and-constraints
plan: 06
subsystem: localization-parsing
tags: [python, canonical-parser, conformance, atomic-join, hypothesis, tdd]

requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [02, 03, 04, 05]
    provides: complete Android XML, Qt TS, JSON, and iOS strings canonical adapters with format-specific fixtures and bounds
provides:
  - closed registry dispatch for all four confirmed localization formats
  - deterministic direct and separate repository mapping parsing with atomic source/translation joins
  - exact cross-format construct inventory, shared limits, failure redaction, and canonical byte-order conformance
  - 100 percent statement and branch coverage across the canonical importing package
affects: [04-07-parser-checkpoint, canonical-persistence, localization-import, search-indexing, write-back]

actuals:
  tokens: 21990
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - mapping-level preflight before adapter work and all-values-or-bounded-issues aggregation
    - separate-side joins keyed by exact raw key and canonical selector bytes after both sides parse completely
    - repository-side, provider-path, locator-position, key, language, and selector-byte canonical ordering

key-files:
  created:
    - backend/tests/unit/localization/importing/test_conformance.py
    - backend/tests/fixtures/localization/conformance/manifest.json
    - backend/tests/fixtures/localization/conformance/direct.json
    - backend/tests/fixtures/localization/conformance/separate.json
  modified:
    - backend/src/verboflex/localization/importing/registry.py
    - backend/src/verboflex/localization/importing/core.py
    - backend/src/verboflex/localization/importing/android_xml.py
    - backend/tests/fixtures/localization/android/valid_structured.expected.json
    - backend/tests/unit/localization/importing/test_android_xml.py
    - backend/tests/unit/localization/importing/test_ios_strings.py

key-decisions:
  - "Separate mappings retain keys-side source records and translations-side target records independently; matching targets receive source text, translation-only targets retain null source, and key-only input never fabricates a target."
  - "Canonical value order is repository side, provider path, locator position, raw key, language, then canonical selector bytes; stable input ordinals only stabilize pre-parse file ordering."
  - "A separate mapping is accepted only after complete Keys and Translations parses share one normalized base-language authority and exact selector shapes for every overlapping raw key."
  - "Every adapter remains independently exception-safe even when called outside the registry, while the registry rebuilds and validates the entire immutable result graph at its trust boundary."

patterns-established:
  - "Atomic mapping: validate all inputs and resource ceilings, parse every file, then join or reject the complete snapshot with zero partial values."
  - "Separate provenance: keys and translations preserve their own locators and repository sides instead of collapsing into a synthetic record."
  - "Closed conformance: arbitrary inputs, forged immutable objects, adapter exceptions, malformed structures, and one-over limits produce only bounded allowlisted issues."

requirements-completed: [FMT-01, FMT-02, FMT-03, FMT-04, FMT-06]

coverage:
  - id: D1
    description: Android XML participates in the exact shared canonical contract, deterministic ordering, closed failure surface, and mapping aggregation.
    requirement: FMT-01
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_conformance.py#test_registry_dispatches_every_confirmed_format_to_a_complete_result[android_xml]"
        status: pass
      - kind: unit
        ref: "parser package branch coverage command: 169 passed, 100 percent"
        status: pass
    human_judgment: false
  - id: D2
    description: Qt TS participates in the exact shared canonical contract, deterministic ordering, closed failure surface, and mapping aggregation.
    requirement: FMT-02
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_conformance.py#test_registry_dispatches_every_confirmed_format_to_a_complete_result[qt_ts]"
        status: pass
      - kind: unit
        ref: "parser package branch coverage command: 169 passed, 100 percent"
        status: pass
    human_judgment: false
  - id: D3
    description: JSON participates in the exact shared canonical contract, deterministic ordering, closed failure surface, and mapping aggregation.
    requirement: FMT-03
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_conformance.py#test_registry_dispatches_every_confirmed_format_to_a_complete_result[json]"
        status: pass
      - kind: unit
        ref: "parser package branch coverage command: 169 passed, 100 percent"
        status: pass
    human_judgment: false
  - id: D4
    description: iOS strings participates in the exact shared canonical contract, deterministic ordering, closed failure surface, and mapping aggregation.
    requirement: FMT-04
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_conformance.py#test_registry_dispatches_every_confirmed_format_to_a_complete_result[ios_strings]"
        status: pass
      - kind: unit
        ref: "parser package branch coverage command: 169 passed, 100 percent"
        status: pass
    human_judgment: false
  - id: D5
    description: Direct and separate confirmed mappings return one complete bounded result, joining exact raw keys and selectors without manufacturing source or target data.
    requirement: FMT-06
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_conformance.py#test_direct_mapping_matches_hand_authored_fixture_and_is_order_stable"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_conformance.py#test_separate_mapping_joins_without_manufacturing_data"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_conformance.py#test_separate_mapping_failures_are_atomic"
        status: pass
    human_judgment: false

duration: 9h15min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 06: Cross-Format Canonical Mapping Summary

**One closed registry now parses all four localization formats into byte-stable direct or atomic separate mapping results, with exact source/target joins and a fully covered bounded failure surface.**

## Performance

- **Duration:** 9h15min
- **Started:** 2026-09-04T22:11:09Z
- **Completed:** 2026-09-05T07:26:33Z
- **Tasks:** 2
- **Files created or modified:** 10

## Accomplishments

- Registered Android XML, Qt TS, JSON, and iOS strings behind one closed dispatcher and froze exact cross-format categories, construct IDs, ceilings, canonical JSON stability, and arbitrary-input failure behavior.
- Added `parse_canonical_mapping()` with complete preflight resource checks, deterministic file aggregation, direct topology support, and all-or-nothing separate Keys/Translations parsing.
- Joined separate mappings on exact raw key and canonical selector bytes while preserving independent locators: matching targets receive source text, translation-only entries retain null source, and key-only entries create no target.
- Reached 100% statement and branch coverage across the entire canonical importing package with 169 passing parser tests.

## Task Commits

1. **Task 1 RED: specify four-format conformance and exact global bounds** - `0dc7bd8` (test)
2. **Task 1 GREEN: enforce cross-format canonical conformance** - `aed9dbe` (feat)
3. **Task 2 RED: specify direct and separate atomic mapping joins** - `6667ebe` (test)
4. **Task 2 GREEN: implement atomic canonical mapping joins** - `ab5072a` (feat)

No separate refactor commit was needed; the GREEN changes retain the existing immutable dataclass, adapter, and bounded-issue patterns.

## Files Created/Modified

- `backend/src/verboflex/localization/importing/registry.py` - Closed four-format snapshot dispatch plus bounded direct/separate mapping aggregation and selector-exact joins.
- `backend/src/verboflex/localization/importing/core.py` - Shared exact limits, result-graph reconstruction validation, and provider-position-first canonical ordering.
- `backend/src/verboflex/localization/importing/android_xml.py` - Adapter-local arbitrary-input validation and sanitized invalid provenance.
- `backend/tests/unit/localization/importing/test_conformance.py` - Manifest equality, construct inventory, byte stability, arbitrary-input, boundary, mapping, join, and defensive conformance coverage.
- `backend/tests/fixtures/localization/conformance/manifest.json` - Exact shared limits and supported/rejected construct inventory for all four formats.
- `backend/tests/fixtures/localization/conformance/direct.json` - Hand-authored complete direct mapping projection.
- `backend/tests/fixtures/localization/conformance/separate.json` - Exact join, translation-only, key-only, duplicate, incompatible-selector, malformed-side, and ambiguous-language projections.
- `backend/tests/fixtures/localization/android/valid_structured.expected.json` - Golden output reordered to the shared locator-position-first contract.
- `backend/tests/unit/localization/importing/test_android_xml.py` - Android golden order expectation aligned with the shared canonical order.
- `backend/tests/unit/localization/importing/test_ios_strings.py` - Collision-free exact safe-message assertion for arbitrary-byte redaction.

## Decisions Made

- Kept source-side and target-side values as distinct canonical records so repository provenance and write-back locators are never synthesized or lost.
- Enriched only matching translation records with the keys-side source text; unmatched translations remain explicit null-source targets and unmatched keys remain source-only records.
- Compared complete selector sets for every raw key appearing on both sides, rejecting structural mismatches before any joined values can escape.
- Put locator position before key and language in canonical ordering, then used raw selector bytes as the final semantic tie-breaker; this preserves provider order while remaining byte-stable.
- Enforced aggregate file count, per-file bytes, total bytes, value count, normalized base language, format equality, topology, and duplicate provider paths before returning mapping authority.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Closed Android adapter calls with forged non-byte input**
- **Found during:** Task 2 complete parser coverage verification
- **Issue:** The registry rejected non-byte content, but a direct call to the Android adapter could reach byte operations with a forged frozen input and raise `TypeError`.
- **Fix:** Added exact adapter-local input checks, a closed invalid-input result, and sanitized repository-side/path projection matching the other adapters.
- **Files modified:** `backend/src/verboflex/localization/importing/android_xml.py`, `backend/tests/unit/localization/importing/test_conformance.py`
- **Verification:** Arbitrary and forged single/batch conformance tests pass; the importing package has 100% branch coverage.
- **Committed in:** `ab5072a`

**2. [Rule 1 - Bug] Replaced a collision-prone iOS redaction oracle**
- **Found during:** Task 2 complete parser coverage verification
- **Issue:** The property test compared arbitrary byte hex against safe English messages; the one-byte token `ed` falsely matched “Malformed” despite no payload disclosure.
- **Fix:** Asserted the exact closed iOS issue-message allowlist instead, which directly proves the intended redaction boundary without substring collisions.
- **Files modified:** `backend/tests/unit/localization/importing/test_ios_strings.py`
- **Verification:** The previously minimized `b'\xed'` example and all 169 parser tests pass.
- **Committed in:** `ab5072a`

**3. [Rule 3 - Blocking] Updated the Android golden for the mandated global order**
- **Found during:** Task 2 full parser regression verification
- **Issue:** Changing the shared order from digest/key-first to provider locator position made the existing Android structured golden and explicit key sequence stale.
- **Fix:** Reordered only the affected golden records and expectation to position-first, selector-byte order.
- **Files modified:** `backend/tests/fixtures/localization/android/valid_structured.expected.json`, `backend/tests/unit/localization/importing/test_android_xml.py`
- **Verification:** The Android golden passes and all four adapter suites remain green.
- **Committed in:** `ab5072a`

**4. [Rule 2 - Missing Critical] Closed defensive parser branches required by the next blocking checkpoint**
- **Found during:** Task 2 overall verification
- **Issue:** The next plan's mandated 100% parser branch gate initially measured 89.41%, leaving malformed authority, aggregate, token/node, and result-rebuild defenses unproven.
- **Fix:** Added focused cross-format conformance for every remaining defensive branch without adding dependencies or widening supported grammars.
- **Files modified:** `backend/tests/unit/localization/importing/test_conformance.py`
- **Verification:** Exact parser-package coverage command reports 1,756 statements and 698 branches at 100% with 169 tests passing.
- **Committed in:** `ab5072a`

---

**Total deviations:** 4 auto-fixed (2 Rule 1 bugs, 1 Rule 2 missing critical coverage, 1 Rule 3 blocking regression).
**Impact on plan:** The fixes close direct adapter safety, make the redaction oracle deterministic, preserve the existing Android golden under the required order, and leave Plan 04-07's parser coverage prerequisite green. No new format grammar, dependency, endpoint, persistence, or external authority was introduced.

## Issues Encountered

- The first full parser checkpoint rehearsal exposed the incomplete branch coverage and the flaky one-byte hex redaction assertion; both were resolved within Task 2 and the exact gate now passes.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## TDD Gate Compliance

- Task 1 RED `0dc7bd8` failed with nine expected conformance gaps before GREEN `aed9dbe` registered all adapters and enforced the shared result contract.
- Task 2 RED `6667ebe` failed with nine missing-mapping cases before GREEN `ab5072a` supplied direct/separate aggregation and exact joins.
- Both required RED commits precede their corresponding GREEN commits; no separate refactor commit was necessary.

## Verification

- `uv run --project backend pytest backend/tests/unit/localization/importing/test_conformance.py -q -k 'direct or separate or join'` - 11 passed.
- `uv run --project backend pytest backend/tests/unit/localization/importing --cov=verboflex.localization.importing --cov-branch --cov-report=term-missing --cov-fail-under=100 -q` - 169 passed; 1,756 statements and 698 branches at 100%.
- `uv run --project backend ruff format --check backend/src/verboflex/localization/importing backend/tests/unit/localization/importing` - 13 files already formatted.
- `uv run --project backend ruff check backend/src/verboflex/localization/importing backend/tests/unit/localization/importing` - passed.
- `uv run --project backend mypy backend/src/verboflex/localization/importing` - passed for seven source files.
- Stub, skipped-test, and threat-surface scans found no shipping defects or unplanned trust boundaries.

## Next Phase Readiness

- Plan 04-07 can run the immutable parser checkpoint from a green 100% branch baseline and record container/runtime evidence without changing parser behavior.
- Canonical persistence can consume one deterministic direct or atomic separate result with explicit null source semantics and independent repository locators.
- No blockers, packages, external setup, or authentication steps remain from this plan.

## Self-Check: PASSED

All ten declared source, test, and fixture files plus this summary exist; all four TDD commits resolve in RED/GREEN order; the exact mapping, 100% parser coverage, Ruff, MyPy, stub, skipped-test, threat-surface, and deterministic coverage-classification checks pass.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-05*
