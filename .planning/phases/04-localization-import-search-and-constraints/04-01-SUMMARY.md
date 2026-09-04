---
phase: 04-localization-import-search-and-constraints
plan: 01
subsystem: localization-parsing
tags: [python, xml, canonical-contract, typed-selectors, sha256, tdd]

requires:
  - phase: 02-admin-configuration
    provides: strict Android decoding, hardened XML parsing, and locale normalization primitives
  - phase: 03-bitbucket-import-integration
    provides: immutable commit-bound repository source and repository-side authority
provides:
  - immutable version-1 canonical parser records with typed selector identity
  - fail-closed four-format registry with a production Android scalar adapter
  - bounded closed parser issues and deterministic whole-result validation
  - hand-authored byte-stable Android scalar canonical manifest
affects: [04-02-android-parser, 04-03-qt-parser, 04-04-json-parser, 04-05-ios-parser, 04-06-parser-conformance, canonical-persistence]

actuals:
  tokens: 12658
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - frozen slots dataclasses at the untrusted repository-bytes boundary
    - versioned typed selector JSON with deterministic SHA-256 identity
    - canonical whole-result validation before persistence consumers

key-files:
  created:
    - backend/src/verboflex/localization/importing/core.py
    - backend/src/verboflex/localization/importing/registry.py
    - backend/src/verboflex/localization/importing/android_xml.py
    - backend/src/verboflex/localization/importing/__init__.py
    - backend/tests/unit/localization/importing/test_android_xml.py
    - backend/tests/unit/localization/importing/test_contracts.py
    - backend/tests/fixtures/localization/android/scalar.xml
    - backend/tests/fixtures/localization/android/scalar.expected.json
  modified: []

key-decisions:
  - "Use exactly six version-1 selector discriminators and compact sorted JSON so semantic selector identity is stable across field order."
  - "Keep ordered lossless structure fields explicit in serialized output and reject every structure kind outside the shared format-qualified version-1 allowlist."
  - "Exclude path and position from canonical value identity while rejecting duplicate identities and noncanonical result order atomically."
  - "Expose only five closed issue codes with bounded safe coordinates and messages; source fragments and exception payload fields are structurally absent."

patterns-established:
  - "Canonical identity: repository side, normalized language, byte-preserved logical key, and selector digest define parser-level value uniqueness; locator changes do not."
  - "Canonical result: adapters return an immutable sorted complete value tuple or an immutable sorted issue tuple, never both."
  - "Lossless structure: every emitted semantic node is format-qualified, versioned, allowlisted, ordered, and validated before result construction."

requirements-completed: [FMT-01, FMT-07]

coverage:
  - id: D1
    description: One real Android scalar resource crosses immutable bytes, strict UTF-8 and hardened XML parsing, confirmed registry dispatch, and canonical output.
    requirement: FMT-01
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_android_xml.py#test_android_scalar_snapshot_is_canonical_and_immutable"
        status: pass
      - kind: unit
        ref: "backend/tests/unit/localization/preview/test_android_xml.py (28 adjacent regression tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: Shared version-1 selector, structure, locator, ordering, identity, and review-state contracts are frozen and reject invalid outputs atomically.
    requirement: FMT-07
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_contracts.py"
        status: pass
      - kind: other
        ref: "uv run --project backend mypy backend/src/verboflex/localization/importing"
        status: pass
    human_judgment: false
  - id: D3
    description: Parser failures remain bounded and source-free, and the worker-facing parser package has no SQLAlchemy, FastAPI, Celery, or Bitbucket dependency.
    requirement: FMT-07
    verification:
      - kind: unit
        ref: "backend/tests/unit/localization/importing/test_android_xml.py#test_android_scalar_failures_are_atomic_and_closed"
        status: pass
      - kind: other
        ref: "rg sqlalchemy|fastapi|celery|bitbucket backend/src/verboflex/localization/importing (no matches)"
        status: pass
    human_judgment: false

duration: 39min
completed: 2026-09-04
status: complete
---

# Phase 04 Plan 01: Canonical Parser Tracer and Contract Summary

**A production Android scalar parser now returns immutable, identity-safe canonical records through a fail-closed registry backed by a frozen version-1 selector, structure, locator, ordering, and issue contract.**

## Performance

- **Duration:** 39min
- **Started:** 2026-09-04T20:12:03Z
- **Completed:** 2026-09-04T20:51:17Z
- **Tasks:** 2
- **Files created or modified:** 8

## Accomplishments

- Routed a real Android scalar resource from immutable bytes through strict decoding, hardened XML parsing, confirmed-format dispatch, and deterministic canonical output.
- Froze and validated the version-1 selector, structure, locator, identity, ordering, and review-state contracts that every later format adapter must implement.
- Made parser diagnostics atomic, closed, bounded, source-free, and independent of SQLAlchemy, FastAPI, Celery, and Bitbucket clients.

## Task Commits

1. **Task 1 RED: specify the Android scalar canonical path** - `b8e41d0` (test)
2. **Task 1 GREEN: implement the Android scalar canonical parser** - `cad5c2c` (feat)
3. **Task 2 RED: freeze canonical contract behavior** - `06965cd` (test)
4. **Task 2 GREEN: validate and export canonical contracts** - `1e755fe` (feat)
5. **Task 2 REFACTOR: derive runtime allowlists from public types** - `b745428` (refactor)

## Files Created/Modified

- `backend/src/verboflex/localization/importing/core.py` - Immutable canonical records, closed vocabularies, selector serialization/digests, result ordering, and output validation.
- `backend/src/verboflex/localization/importing/registry.py` - Exact four-format dispatch with fail-closed unsupported adapters.
- `backend/src/verboflex/localization/importing/android_xml.py` - Strict production Android scalar adapter with bounded safe failure mapping.
- `backend/src/verboflex/localization/importing/__init__.py` - Public canonical parser contract exports.
- `backend/tests/unit/localization/importing/test_android_xml.py` - Android scalar tracer, authority, malicious-input, and atomic-failure coverage.
- `backend/tests/unit/localization/importing/test_contracts.py` - Selector, structure, locator, identity, ordering, issue, and golden-manifest contract coverage.
- `backend/tests/fixtures/localization/android/scalar.xml` - Immutable real Android scalar source bytes.
- `backend/tests/fixtures/localization/android/scalar.expected.json` - Hand-authored compact canonical output manifest.

## Decisions Made

- Selector identity uses exactly `scalar`, `android_quantity`, `android_array_item`, `qt_numerus`, `qt_length_variant`, and `json_path` at schema version 1.
- Selector fields serialize as sorted compact JSON while typed tuple sequence values retain their explicit order.
- Lossless structure serializes fields as ordered name/value records and admits only shared format-qualified version-1 node kinds.
- Parser-level duplicate identity ignores mutable path/position and uses repository side, normalized language, raw logical key, and selector digest.
- Canonical issues expose only the five researched categories plus safe path/side/coordinate/message fields.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Preview and importing Android tests share the same module basename under the repository's pytest import mode. Running those adjacent suites as separate invocations avoided the collection-name collision; both suites passed independently.

## Authentication Gates

None.

## Known Stubs

| File | Line | Stub | Resolution |
| --- | ---: | --- | --- |
| `backend/src/verboflex/localization/importing/registry.py` | 36 | Qt canonical dispatch intentionally returns a closed unsupported-structure result. | Plan 04-03 supplies the Qt adapter. |
| `backend/src/verboflex/localization/importing/registry.py` | 37 | JSON canonical dispatch intentionally returns a closed unsupported-structure result. | Plan 04-04 supplies the JSON adapter. |
| `backend/src/verboflex/localization/importing/registry.py` | 38 | iOS strings canonical dispatch intentionally returns a closed unsupported-structure result. | Plan 04-05 supplies the iOS adapter. |

These explicit fail-closed seams do not block this plan's Android-scalar goal and are recorded in `.planning/WINDOWS.md` for later closure.

## TDD Gate Compliance

- RED `b8e41d0` precedes GREEN `cad5c2c` for the production Android scalar tracer.
- RED `06965cd` precedes GREEN `1e755fe` for the frozen shared contracts.
- REFACTOR `b745428` removed duplicate runtime allowlists; the focused and adjacent suites remained green.

## Next Phase Readiness

- Plan 04-02 can extend the proven Android adapter with plurals, arrays, escapes, and allowlisted inline structure without changing canonical identity.
- Plans 04-03 through 04-05 can implement Qt, JSON, and iOS against the frozen public contract and close their registered stubs.
- Plan 04-06 can build cross-format conformance and mapping-level aggregation on deterministic validated results.

## Self-Check: PASSED

All eight declared implementation, test, and fixture files plus this summary exist; all five TDD task commits resolve in RED/GREEN/REFACTOR order; the final 36-test canonical suite and 28-test adjacent Android preview suite pass; Ruff, formatting, MyPy, dependency-isolation inspection, and coverage classification all pass.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-04*
