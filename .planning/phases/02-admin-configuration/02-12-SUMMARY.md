---
phase: 02-admin-configuration
plan: 12
subsystem: localization-preview-detectors
tags: [android-xml, defusedxml, celery, bitbucket, tdd, property-testing, mutation-testing]

requires:
  - phase: 02-04
    provides: Approved official defusedxml provenance and Python 3.14/Linux compatibility
  - phase: 02-07
    provides: Commit-bound bounded Bitbucket source discovery
  - phase: 02-11
    provides: Durable PostgreSQL-authoritative preview jobs and UUID-only worker boundary
provides:
  - Strict read-only Android XML preview detection through the durable worker
  - Immutable bounded candidate/sample contracts with exact deterministic ordering
  - Fail-closed A-02 encoding/grammar and exact A-03 byte/language/sample limits
  - Canonical OpenAPI and generated TypeScript contracts for noncanonical preview results
affects: [02-13, 02-14, 02-15, localization-preview, admin-configuration]

actuals:
  tokens: 52369
  tasks: 2
  commits: 10

tech-stack:
  added:
    - defusedxml==0.7.1
  patterns:
    - Preview adapters consume commit-bound bounded bytes and expose immutable noncanonical results only
    - Unsupported encoding, grammar, ambiguity, or exceeded limits invalidate a complete layout without truncation or substitution
    - Unicode code-point sorting plus explicit per-language and global ceilings makes samples reproducible

key-files:
  created:
    - backend/src/verboflex/localization/preview/core.py
    - backend/src/verboflex/localization/preview/android_xml.py
    - backend/tests/unit/localization/preview/test_android_xml.py
    - tools/verify_android_preview_mutants.py
  modified:
    - backend/src/verboflex/worker/preview_tasks.py
    - backend/src/verboflex/services/preview_jobs.py
    - backend/src/verboflex/schemas/previews.py
    - backend/tests/integration/test_preview_jobs.py
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json
    - frontend/src/api/client/types.gen.ts

key-decisions:
  - "Android preview accepts only strict UTF-8 with an optional UTF-8 BOM and plain direct-child string elements; every unsupported construct fails closed."
  - "One candidate represents exactly one Android res root and repository side at confidence 1.0; preview output never creates canonical identity or confirmation authority."
  - "The 1 MiB/file, 20 MiB total, 32-language, 10-sample/language, and 100-sample ceilings are exact validation boundaries, never truncation defaults."
  - "Provider reads remain commit-bound and mutation-free; parsing and persistence stay behind the durable Celery worker boundary."

patterns-established:
  - "Fail-closed detector: unsupported bytes, XML grammar, locale qualifiers, duplicates, or ambiguity yield no candidate rather than a partial candidate."
  - "Bounded preview contract: immutable files, languages, keys, and samples are validated again when crossing the untrusted worker persistence boundary."
  - "Detector evidence: exact boundaries, arbitrary-byte properties, changed-line branch coverage, and targeted mutants surround each parser implementation."

requirements-completed: [PROD-08, PROD-09, BITB-04]

coverage:
  - id: D1
    description: Commit-bound Android resource discovery and strict read-only preview through API, worker, provider adapter, and PostgreSQL
    requirement: PROD-08
    verification:
      - kind: integration
        ref: backend/tests/integration/test_preview_jobs.py#test_android_preview_completes_read_only
        status: pass
      - kind: integration
        ref: uv run pytest -q tests/unit/localization/preview/test_android_xml.py tests/integration/test_preview_jobs.py -x (58 passed)
        status: pass
    human_judgment: false
  - id: D2
    description: Strict A-02 Android encoding and grammar with ambiguity, entity, markup, duplicate, malformed, empty, and arbitrary-byte rejection
    requirement: PROD-09
    verification:
      - kind: unit
        ref: backend/tests/unit/localization/preview/test_android_xml.py
        status: pass
      - kind: other
        ref: tools/verify_android_preview_mutants.py (10/10 killed; negative control passed)
        status: pass
    human_judgment: false
  - id: D3
    description: Exact A-03 file, aggregate, language, per-language sample, and global sample boundaries with commit identity and zero provider mutations
    requirement: BITB-04
    verification:
      - kind: unit
        ref: backend/tests/unit/localization/preview/test_android_xml.py (exact boundary and property contracts)
        status: pass
      - kind: other
        ref: diff-cover against d00ab7c (150/150 changed production lines and branches)
        status: pass
    human_judgment: false

duration: 32m
completed: 2026-08-27
status: complete
---

# Phase 2 Plan 12: Strict Android Preview Detector Summary

**Commit-bound Android resources now produce deterministic, bounded, read-only preview candidates through the durable worker while every unsupported byte, grammar, ambiguity, or exceeded A-03 limit fails closed.**

## Performance

- **Duration:** 32m
- **Started:** 2026-08-27T18:37:22Z
- **Completed:** 2026-08-27T19:09:16Z
- **Tasks:** 2
- **Files modified:** 16

## Accomplishments

- Added the first production preview adapter, automatically discovering Android resource roots and returning exactly one immutable candidate per exact layout and repository side at confidence 1.0.
- Wired commit-bound Plan 07 repository bytes through the Plan 11 durable Celery job into a bounded PostgreSQL result without provider writes, source serialization, canonical translation identity, or confirmation authority.
- Closed A-02 to strict UTF-8 with optional BOM and plain direct-child `<string name="...">` elements; UTF-16/32, invalid declarations/bytes/NUL, DTD/entities, markup, arrays/plurals, duplicates, unsupported qualifiers, malformed/empty XML, and outside-root content cannot confirm.
- Enforced exact A-03 limits of 1 MiB per file, 20 MiB total, 32 languages, 10 samples per language, and 100 samples total with Unicode code-point deterministic ordering and `samples_are_partial=true`.
- Promoted the approved `defusedxml==0.7.1` dependency, synchronized the canonical OpenAPI/TypeScript contracts, and surrounded the detector with boundary, property, coverage, static, and mutation evidence.

## Task Commits

Each TDD gate and follow-up proof was committed atomically:

1. **Task 1 RED: Android worker tracer** — `2210d02`
2. **Task 1 GREEN: Android preview tracer** — `5d91643`
3. **Task 1 REFACTOR: tracer lint cleanup** — `50b1e93`
4. **Task 2 RED: strict Android boundary contracts** — `d00ab7c`
5. **Task 2 GREEN: Android preview boundaries** — `433c37a`
6. **Task 2 REFACTOR: decomposed strict validation** — `55e4350`
7. **Evidence armor: fail-closed mutation proof** — `1df0a05`
8. **Generated contract: canonical OpenAPI and TypeScript client** — `bc4b25e`
9. **Evidence armor: changed-line branch coverage** — `c133c64`
10. **Static gate: integration contract formatting** — `04089b2`

## Files Created/Modified

- `backend/src/verboflex/localization/preview/core.py` — Defines immutable candidate/sample models, exact caps, deterministic sampling, IDs, and strict untrusted-worker validation.
- `backend/src/verboflex/localization/preview/android_xml.py` — Discovers exact Android resource roots and performs strict fail-closed byte, XML, ambiguity, and budget validation.
- `backend/src/verboflex/worker/preview_tasks.py` — Resolves exact repository sides/commits and invokes the read-only Android detector through bounded source discovery.
- `backend/src/verboflex/schemas/previews.py` and `backend/src/verboflex/services/preview_jobs.py` — Project and persist bounded noncanonical candidates without raw source or provider data.
- `backend/tests/unit/localization/preview/test_android_xml.py` — Proves successful detection, exact boundaries, unsupported matrices, deterministic sampling, immutability, and arbitrary-byte safety.
- `backend/tests/integration/test_preview_jobs.py` — Proves API-to-worker-to-provider-to-detector-to-PostgreSQL behavior and zero provider mutations.
- `backend/tests/api/test_openapi_contract.py`, `frontend/openapi.json`, and `frontend/src/api/client/` — Freeze and generate the bounded browser-facing preview contract.
- `tools/verify_android_preview_mutants.py` — Kills ten targeted limit, decoder, parser, ambiguity, and sampler mutants with a negative self-control.

## Decisions Made

- Valid Android preview is deliberately narrow: strict UTF-8 optional-BOM bytes, one `<resources>` root, and plain direct-child string elements only.
- A layout is the exact Android `res` root plus repository side; multiple roots stay separate and every candidate ID is derived from that immutable identity and contract version.
- Any ambiguity or unsupported resource invalidates the whole affected layout. The detector never drops conflicting data, replaces invalid characters, lowers confidence, or emits a truncated success.
- Preview samples are always partial and noncanonical. Explicit confirmation and canonical import/write authority remain outside this adapter and later plans.

## TDD Gate Compliance

- Task 1 RED failed before implementation (`2210d02`), GREEN passed after implementation (`5d91643`), and REFACTOR retained the unchanged 3-test tracer before the user-approved expansion checkpoint (`50b1e93`).
- Task 2 RED failed on the absent exact 1 MiB file boundary (`d00ab7c`); GREEN passed the unchanged command with 52 tests after fail-closed boundary implementation (`433c37a`).
- Task 2 REFACTOR preserved the unchanged command while reducing changed production complexity below grade C (`55e4350`).
- The final exact Task 2 command passes 58 tests, all 150 changed production lines and branches are covered, and all ten targeted mutants are killed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added mutation and branch-coverage evidence for every fail-closed boundary**
- **Found during:** Task 2 evidence gauntlet
- **Issue:** Passing examples alone did not prove the exact off-by-one limits, unsupported grammar, strict decoding, and sampler caps would resist plausible implementation mutations.
- **Fix:** Added a drift-checked ten-mutant verifier, its negative control, and focused tests for ignored paths, folded-language duplicates, empty names, and malformed untrusted persistence payloads.
- **Files modified:** `backend/tests/unit/localization/preview/test_android_xml.py`, `tools/verify_android_preview_mutants.py`
- **Verification:** 58 focused tests, 150/150 changed lines and branches, 10/10 mutants killed, negative control passed.
- **Committed in:** `1df0a05`, `c133c64`

**2. [Rule 3 - Blocking] Reduced changed detector/core complexity below grade C**
- **Found during:** Task 2 REFACTOR static gate
- **Issue:** Complete fail-closed collection and untrusted-mapping validation initially concentrated too many branches in individual functions.
- **Fix:** Extracted single-purpose byte classification, layout collection, candidate construction, header parsing, and relationship validation helpers without changing output.
- **Files modified:** `backend/src/verboflex/localization/preview/android_xml.py`, `backend/src/verboflex/localization/preview/core.py`
- **Verification:** Ruff, formatter, mypy, radon, focused tests, 100% diff branch coverage, and 10/10 mutants pass.
- **Committed in:** `55e4350`

**3. [Rule 3 - Blocking] Synchronized the expanded browser-facing preview contract**
- **Found during:** Full randomized backend/OpenAPI drift gate
- **Issue:** Task 1 expanded the backend result schema while the checked-in canonical OpenAPI document and generated TypeScript client still exposed the closed pre-detector skeleton.
- **Fix:** Regenerated the canonical schema and client, adding the exact candidate and sample projections without changing package manifests.
- **Files modified:** `frontend/openapi.json`, `frontend/src/api/client/index.ts`, `frontend/src/api/client/types.gen.ts`
- **Verification:** 11 OpenAPI contract tests, frontend API drift check, typecheck, lint, format, 75 randomized tests, and production build pass.
- **Committed in:** `bc4b25e`

**4. [Rule 3 - Blocking] Applied repository formatting to the tracer integration file**
- **Found during:** Final full static gauntlet
- **Issue:** Two Task 1 integration expressions did not match the current Ruff formatter output.
- **Fix:** Applied the repository formatter with no behavior change.
- **Files modified:** `backend/tests/integration/test_preview_jobs.py`
- **Verification:** Ruff formatter/check, mypy, exact focused suite, and full randomized backend suite pass.
- **Committed in:** `04089b2`

**Total deviations:** 4 auto-fixed (1 Rule 2, 3 Rule 3).
**Impact on plan:** The additions strengthen fail-closed assurance, maintainability, and contract synchronization; they add no canonical import, write, confirmation, or new product scope.

## Issues Encountered

- The first post-implementation randomized run exposed the stale checked-in OpenAPI/client contract. Regeneration resolved it, and the final backend run passed 517/517.
- One coverage attempt overlapped the frontend OpenAPI generator and observed its atomic target while the shell redirection had temporarily truncated it. All final verification was rerun sequentially; canonical drift and 100% changed-line branch coverage pass.
- `npm audit` continues to report the already-known moderate `qs` advisory only through development tooling. The high-severity gate passes, and the production dependency audit reports zero vulnerabilities.

## Verification Evidence

- Exact Task 2 command: `58 passed`.
- Full backend randomized suite: `517 passed` with disposable PostgreSQL 18, Redis 7, and Celery worker execution; migration/architecture/OpenAPI slice: `21 passed`.
- Backend static gates: Ruff clean, 120 files formatted, mypy clean across 78 source files, and no changed preview function at radon grade C or worse.
- Changed production coverage: `150/150`, 100% line and branch coverage against Task 2 RED `d00ab7c`.
- Mutation: negative control passed and `10/10` targeted fail-closed mutants killed.
- Frontend: typecheck, lint, format, 75 randomized tests, generated API drift check, and production build passed.
- Supply chain: `uv lock --check`, exact `defusedxml==0.7.1`, `pip-audit` with no known vulnerabilities, license inventory, high-severity npm audit, and production npm audit passed.
- Secret gate: the full audited repository scan passed and its unexpected-finding negative control was rejected.

## Known Stubs

None. The adapter is fully wired to bounded commit-bound source discovery and durable result persistence; canonical import, write, and administrator confirmation are intentionally outside Plan 02-12 scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plans 02-13 and 02-14 can add Qt/JSON/iOS detectors behind the same immutable bounded contract and worker persistence boundary.
- Plan 02-15 can consume exact successful candidates for administrator confirmation without granting preview adapters canonical or write authority.
- No blockers remain. Representative repositories may later justify an explicit reviewed A-03 limit change; current limits intentionally fail closed rather than adapt silently.

## Self-Check: PASSED

- All 16 created/modified plan files exist.
- All 10 RED, GREEN, REFACTOR, evidence, contract, and formatting commits exist on `codex/phase-2-admin-configuration`.
- The exact focused verification, full randomized backend, worker, migration, architecture, OpenAPI, frontend, static, coverage, mutation, secret, and supply-chain gates are green.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-27*
