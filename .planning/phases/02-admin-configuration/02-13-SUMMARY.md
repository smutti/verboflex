---
phase: 02-admin-configuration
plan: 13
subsystem: localization-preview-detectors
tags: [qt-ts, json, ios-strings, celery, tdd, property-testing, mutation-testing]

requires:
  - phase: 02-12
    provides: Immutable bounded preview contracts, strict Android detector, and durable commit-bound worker path
provides:
  - Strict read-only Qt TS, duplicate-aware JSON, and bounded iOS strings preview detectors
  - One fail-closed registry returning separate exact format, repository-side, and locale-layout candidates
  - Four-format durable worker processing without source writers, canonical identities, or confirmation authority
affects: [02-14, 02-15, 02-19, localization-preview, admin-configuration]

actuals:
  tokens: 22005
  tasks: 2
  commits: 11

tech-stack:
  added: []
  patterns:
    - One candidate represents exactly one format, repository side, and locale path convention at confidence 1.0
    - iOS strings are decoded and lexed in one bounded pass with immutable character spans and no serializer
    - Overlapping file claims, duplicate semantic identities, invalid peers, unsupported grammar, and ambiguous locale paths fail closed

key-files:
  created:
    - backend/src/verboflex/localization/preview/registry.py
    - backend/src/verboflex/localization/preview/qt_ts.py
    - backend/src/verboflex/localization/preview/json.py
    - backend/src/verboflex/localization/preview/ios_strings.py
    - backend/tests/unit/localization/preview/test_qt_ts.py
    - backend/tests/unit/localization/preview/test_json.py
    - backend/tests/unit/localization/preview/test_ios_strings.py
    - tools/verify_ios_preview_mutants.py
  modified:
    - backend/src/verboflex/localization/preview/core.py
    - backend/src/verboflex/worker/preview_tasks.py
    - backend/tests/integration/test_preview_jobs.py

key-decisions:
  - "iOS preview locale identity requires exactly one bounded `<locale>.lproj` directory component; the candidate stores the canonical locale and a `{locale}.lproj` path template."
  - "The iOS adapter accepts strict UTF-8 with optional BOM or BOM-matched UTF-16LE/BE, uses documented escapes and C-style comments, and exposes immutable decoded-source spans without any writer interface."
  - "The durable worker invokes one four-format registry while retaining the Plan 12 `process_android_preview` call seam as a compatibility delegate."
  - "A line comment may terminate at end-of-file; missing semicolons, unterminated block comments, plural dictionaries, preprocessor input, and malformed escapes remain blocking."

patterns-established:
  - "Exact detector registry: run every strict adapter, keep separate candidates, and discard any duplicate candidate or overlapping file claim."
  - "Bounded lexer: explicit cursor states handle trivia, quoted tokens, escapes, surrogate pairs, and half-open spans in linear time."
  - "Format gauntlet: exact supported/unsupported fixtures plus randomized bytes, 100% changed branch coverage, and drift-checked targeted mutants."

requirements-completed: [PROD-08, PROD-09]

coverage:
  - id: D1
    description: Strict Qt TS and both minimal JSON layouts return separate exact deterministic candidates while malformed, duplicate, unsupported, ambiguous, or over-budget input fails closed
    requirement: PROD-09
    verification:
      - kind: unit
        ref: backend/tests/unit/localization/preview/test_qt_ts.py and test_json.py
        status: pass
      - kind: other
        ref: cd backend && uv run pytest -q tests/unit/localization/preview tests/integration/test_preview_jobs.py -x (213 passed)
        status: pass
    human_judgment: false
  - id: D2
    description: Bounded iOS strings lexer accepts only approved encodings, comments, quoted pairs, and documented escapes while retaining immutable source spans and no writer
    requirement: PROD-09
    verification:
      - kind: unit
        ref: backend/tests/unit/localization/preview/test_ios_strings.py
        status: pass
      - kind: other
        ref: tools/verify_ios_preview_mutants.py (11/11 killed; negative control passed)
        status: pass
    human_judgment: false
  - id: D3
    description: One durable commit-bound worker processor returns deterministic separate Android, iOS, JSON, and Qt candidates without provider writes or canonical identity
    requirement: PROD-08
    verification:
      - kind: integration
        ref: backend/tests/integration/test_preview_jobs.py#test_all_four_formats_return_separate_exact_layout_candidates
        status: pass
      - kind: integration
        ref: full randomized backend suite with PostgreSQL, Redis, and Celery worker (672 passed)
        status: pass
    human_judgment: false

duration: 35m
completed: 2026-08-27
status: complete
---

# Phase 2 Plan 13: Exact Qt, JSON, and iOS Preview Detectors Summary

**Qt TS, both minimal JSON layouts, and a bounded span-aware iOS strings lexer now flow through one deterministic four-format durable preview registry, with every unsupported or ambiguous interpretation failing closed.**

## Performance

- **Duration:** 35m
- **Started:** 2026-08-27T19:18:31Z
- **Completed:** 2026-08-27T19:53:13Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Added strict Qt TS and duplicate-aware JSON adapters for exact flat-per-locale and locale-rooted candidates, sharing one bounded locale/path recognizer.
- Added a linear iOS `.strings` lexer for UTF-8 optional-BOM and BOM-matched UTF-16LE/BE input, C-style comments, documented escapes, surrogate pairs, immutable spans, and exhaustive fail-closed rejection.
- Expanded the durable worker from Android-only dispatch to one four-format registry that preserves separate exact candidates and rejects overlapping claims without adding writers, canonical translations, or confirmation authority.
- Surrounded all changed detector and worker behavior with randomized/property fixtures, 594/594 changed lines and branches, and an 11/11 drift-checked mutation proof.

## Task Commits

1. **Task 1 RED: Qt and JSON contracts** — `c8493c6`
2. **Task 1 GREEN: strict Qt and JSON detectors** — `b804ecf`
3. **Task 1 REFACTOR: decomposed validation** — `5a11eef`
4. **Task 2 RED: iOS and four-format worker contracts** — `7221e11`
5. **Task 2 RED refinement: line comments through EOF** — `774a47c`
6. **Task 2 GREEN: bounded iOS detector and registry worker** — `8de1bbc`
7. **Task 2 REFACTOR: bounded lexer helpers** — `0df46db`
8. **Task 2 STYLE: canonical registry formatting** — `42dabc2`
9. **Evidence armor: iOS mutation proof** — `5f8f3ab`
10. **Evidence armor: complete detector boundary coverage** — `0eee83c`
11. **Evidence refactor: remove unreachable guards** — `285e39b`

## Files Created/Modified

- `backend/src/verboflex/localization/preview/core.py` — Centralizes the strict locale subset, exact locale-path templates, immutable candidates, sampling, and untrusted persistence validation.
- `backend/src/verboflex/localization/preview/qt_ts.py` — Hardened minimal `TS/context/message/source/translation` detector with strict UTF-8 and unsupported-state rejection.
- `backend/src/verboflex/localization/preview/json.py` — Duplicate-aware strict JSON detector for exactly flat-per-locale and locale-rooted string maps.
- `backend/src/verboflex/localization/preview/ios_strings.py` — Bounded state-machine decoder/lexer with source spans and no serialization interface.
- `backend/src/verboflex/localization/preview/registry.py` — Runs all four adapters and removes duplicate or overlapping interpretations.
- `backend/src/verboflex/worker/preview_tasks.py` — Resolves commit-bound bytes and delegates each repository side through the complete registry.
- `backend/tests/unit/localization/preview/` and `backend/tests/integration/test_preview_jobs.py` — Prove exact grammar, encoding, locale, limit, ambiguity, deterministic ordering, resource closure, and durable four-format behavior.
- `tools/verify_ios_preview_mutants.py` — Reproducible negative-controlled proof for eleven parser, decoder, path, layout, and registry mutations.

## Decisions Made

- iOS path identity follows the platform layout: exactly one canonicalizable `<locale>.lproj` directory is replaced by `{locale}.lproj`; missing, malformed, or multiple locale directories are non-confirmable.
- `.strings` escape support is deliberately narrow: quote, backslash, newline, carriage return, tab, and four-hex-digit `\U` code units, including valid surrogate pairs. Unknown or isolated surrogate escapes fail closed.
- Comments are trivia only. `//` may end at EOF and `/* ... */` must close; raw controls inside quoted strings remain unsupported.
- The registry never chooses between interpretations. Exact candidates remain separate, while duplicate candidate IDs or any file claimed by more than one adapter are removed.
- `process_android_preview` remains as a compatibility delegate, but production preview execution and new integration paths use the complete registry processor.

## TDD Gate Compliance

- Task 1 recorded RED `c8493c6`, GREEN `b804ecf`, and REFACTOR `5a11eef`; its user-approved tracer gate passed 90 tests before expansion.
- Task 2 recorded RED `7221e11` and `774a47c` before implementation, GREEN `8de1bbc`, and REFACTOR `0df46db`; the unchanged exact command passes 49 tests on the final source state.
- The full plan command passes 213 tests; assertions were not weakened during GREEN or REFACTOR.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added a reproducible iOS and registry mutation proof**
- **Found during:** Task 2 gauntlet
- **Issue:** The planned behavior tests did not independently prove that plausible strict-decoding, duplicate-key, semicolon, escape, surrogate, path-ambiguity, invalid-peer, and registry-omission defects would be detected.
- **Fix:** Added a fail-closed isolated mutation harness with a green baseline, exact source-drift checks, one assertion failure per mutant, and a checker negative control.
- **Files modified:** `tools/verify_ios_preview_mutants.py`
- **Verification:** Negative control passed; all 11 reviewed non-equivalent mutants were killed.
- **Committed in:** `5f8f3ab`

**2. [Rule 2 - Missing Critical] Closed changed detector and worker branch gaps**
- **Found during:** Final changed-line coverage gate
- **Issue:** The first gate reported 87% over the Plan 13 diff, leaving structural, path, collection-limit, duplicate-language, production-resource, and defensive branches without direct evidence.
- **Fix:** Added behavior-focused boundary tests, proved the production adapter is always closed, and removed two logically unreachable guards rather than adding vacuous assertions.
- **Files modified:** `backend/tests/unit/localization/preview/test_qt_ts.py`, `test_json.py`, `test_ios_strings.py`, `backend/tests/integration/test_preview_jobs.py`, `backend/src/verboflex/localization/preview/core.py`, `qt_ts.py`
- **Verification:** 213 plan tests pass and diff-cover reports 594/594 changed lines and branches.
- **Committed in:** `0eee83c`, `285e39b`

**Total deviations:** 2 auto-fixed (2 Rule 2).
**Impact on plan:** Both additions strengthen fail-closed evidence and remove unreachable complexity; no writer, canonical identity, API, schema, dependency, or product scope was added.

## Issues Encountered

- The initial RED classified a `//` comment ending at EOF as malformed. This contradicted the approved C-style comment contract, so the RED fixture was corrected before GREEN and remained observably failing until implementation.
- A whole-backend complexity negative control correctly finds pre-existing C/D functions outside the Plan 13 diff. Every changed preview/worker function is below grade C; no unrelated refactor was attempted.
- `npm audit` continues to report the already-recorded moderate `qs` advisory through development-only Stryker tooling. The high-severity gate passes and the production dependency audit reports zero vulnerabilities.

## Verification Evidence

- Exact Task 2 command: `49 passed`.
- Plan verification command: `213 passed`.
- Full backend randomized suite with seed `21313`, PostgreSQL 18, Redis 7, and a live Celery worker: `672 passed`.
- Migration, architecture, and canonical OpenAPI contract slice: `21 passed`.
- Changed production line/branch coverage against `246b476`: `594/594`, 100%.
- Mutation: checker negative control passed and `11/11` targeted iOS/registry mutants were killed.
- Backend static gates: Ruff clean, 127 files formatted, strict mypy clean across 81 source files, and all changed functions below radon grade C with a working negative control.
- Frontend regression/build: 75 randomized tests, typecheck, ESLint, Prettier, canonical generated-client drift check, and Vite production build passed.
- Supply chain: `uv lock --check`, `pip-audit`, Python license inventory, high-severity npm audit, production npm audit, dependency tree, and license inventory passed; no dependency changed in this plan.
- Secret gate: the audited repository scan passed and its exact-policy negative control was rejected as required.

## Known Stubs

None. The word `placeholder` appears only inside a deliberately injected mutation payload; production detectors and the worker are fully wired. Canonical import, source writing, and confirmation remain intentionally outside this plan rather than stubbed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-14 can bind successful exact candidates to preview confirmation/currentness and publication without changing parser or worker authority.
- Plan 02-15 can consume the already-closed public candidate contract; canonical identities and writers remain deferred.
- No blockers or open broken-window entries remain.

## Self-Check: PASSED

- All 11 created or modified implementation, test, integration, and mutation-proof files exist.
- All 11 RED, GREEN, REFACTOR, style, and evidence commits exist on `codex/phase-2-admin-configuration`.
- Coverage metadata classifies all three deliverables as fully automated and passing.
- The exact focused command, complete plan verification, full randomized backend, changed-line coverage, mutation, static, frontend, migration, architecture, OpenAPI, secret, and supply-chain gates pass on the final source state.
- The broken-windows ledger has zero open entries.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-27*
