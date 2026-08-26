---
phase: 01-platform-foundation
plan: 03
subsystem: ui
tags: [react, vite, typescript, vitest, openapi, hey-api, tdd]

requires:
  - phase: 01-platform-foundation
    plan: 02
    provides: Locked FastAPI application with the exact constant health contract and stable OpenAPI surface
provides:
  - Locked standalone React, Vite, TypeScript, and Vitest frontend
  - Deterministic FastAPI OpenAPI export and exact-pinned generated fetch client
  - Tested loading, exact-online, sanitized-error, and retry health tracer states
affects: [frontend-shell, authentication-ui, openapi-contract, docker]

actuals:
  tokens: 50829
  tasks: 2
  commits: 11

tech-stack:
  added:
    - React 19.2.8 and ReactDOM 19.2.8
    - Vite 8.2.2 with plugin-react 6.1.0
    - TypeScript 6.0.3
    - Vitest 4.1.11, jsdom 30.0.1, and Testing Library
    - "@hey-api/openapi-ts 0.99.0"
  patterns:
    - Generate the frontend HTTP contract only from the live FastAPI OpenAPI document
    - Configure generated fetch clients through a handwritten runtime-config seam outside generated output
    - Render stable UI state from generated results without exposing transport diagnostics

key-files:
  created:
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/openapi.json
    - frontend/openapi-ts.config.ts
    - frontend/src/api/client
    - frontend/src/api/config.ts
    - frontend/src/App.tsx
    - frontend/src/App.test.tsx
    - backend/src/verboflex/scripts/export_openapi.py
  modified:
    - .gitignore
    - .planning/phases/01-platform-foundation/01-SPEC.md
    - .planning/phases/01-platform-foundation/01-RESEARCH.md

key-decisions:
  - "React type declarations are exact direct development dependencies after the user's explicit dependency-boundary approval."
  - "TypeScript is exact-pinned to 6.0.3 because a real generator run proved the approved generator 0.99.0 is incompatible with TypeScript 7 compiler APIs."
  - "The generator's vulnerable js-yaml transitive is overridden to patched 4.3.1 without adding a direct dependency or changing the exact generator version."
  - "Generated fetch calls use a centralized VITE_API_BASE_URL seam and include credentials; UI errors collapse to approved stable copy."

patterns-established:
  - "Contract generation: deterministic backend serializer -> checked-in openapi.json -> exact-pinned generated client."
  - "Health tracer state: loading by default, online only for exact status ok, every other response or network rejection becomes a sanitized retry state."

requirements-completed: [PLAT-01, PLAT-02, PLAT-03]

coverage:
  - id: D1
    description: Standalone locked frontend compiles against a client generated from the live FastAPI schema
    requirement: PLAT-01
    verification:
      - kind: other
        ref: "cd frontend && npm run api:check && npm run typecheck && npm run build"
        status: pass
    human_judgment: false
  - id: D2
    description: Health tracer renders pending, exact online, sanitized failure, and retry behavior
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "frontend/src/App.test.tsx#API health tracer"
        status: pass
    human_judgment: false
  - id: D3
    description: FastAPI health OpenAPI contract is exported deterministically without handwritten frontend duplication
    requirement: PLAT-03
    verification:
      - kind: other
        ref: "cd frontend && npm run api:check"
        status: pass
      - kind: unit
        ref: "backend/tests/api/test_health.py#exact health contract"
        status: pass
    human_judgment: false

duration: 51 min
completed: 2026-08-24
status: complete
---

# Phase 1 Plan 3: Generated Frontend Health Tracer Summary

**A locked React/Vite/TypeScript application now consumes the live FastAPI health contract through exact-pinned generated code and renders tested loading, online, and sanitized retry states.**

## Performance

- **Duration:** 51 min
- **Started:** 2026-08-24T14:14:12Z
- **Completed:** 2026-08-24T15:05:57Z
- **Tasks:** 2
- **Files modified:** 32 before plan close-out metadata

## Accomplishments

- Created a standalone Node 24-compatible frontend with a registry- and integrity-locked dependency graph and zero reported npm vulnerabilities.
- Added a deterministic backend OpenAPI serializer, checked-in schema, exact-pinned Hey API generator, generated fetch client, and centralized runtime configuration without handwritten API types.
- Proved loading, exact `API online`, sanitized error, rejected-network, and retry behavior through observable component tests and preserved one-behavior-at-a-time RED/GREEN history.
- Proved a second schema/client generation produces no tracked diff and that the resulting source passes TypeScript and the production Vite build.

## Task Commits

The dependency-boundary and compatibility records precede package use:

- **Approved React type dependency revision:** `9838f25` (docs)
- **Compatible TypeScript audit resolution:** `1b7e53b` (docs)

Task commits preserve the tracer and TDD chronology:

1. **Task 1: Lock Vite and generate the health client** - `a318b61` (feat)
2. **Task 2 loading RED** - `0395cf5` (test)
3. **Task 2 loading GREEN** - `5a0c059` (feat)
4. **Task 2 online RED** - `51ff732` (test)
5. **Task 2 online GREEN** - `f216b34` (feat)
6. **Task 2 error/retry RED** - `e5c4af6` (test)
7. **Task 2 error/retry GREEN** - `087bac7` (feat)
8. **Rejected-network regression armor** - `bda91c7` (test)

## RED/GREEN Evidence

- **Loading RED:** `vitest` collected the component test and failed because no accessible `status` existed; this was a behavioral assertion failure, not an import or setup failure.
- **Loading GREEN:** the component invoked `readHealthApiV1HealthGet` and rendered `Checking API connection`; the focused and full suites passed.
- **Online RED:** the generated call returned the exact `{status: "ok"}` data, but the test failed waiting for `API online` while the component remained loading.
- **Online GREEN:** only the exact generated healthy payload transitions the accessible status to `API online`; focused/full tests and TypeScript passed.
- **Error/retry RED:** the generated error result carried a raw internal database diagnostic, and the test failed because the required alert/retry UI did not exist.
- **Error/retry GREEN:** all non-healthy results and rejected calls render only the approved generic copy, never raw diagnostics, and `Retry connection` invokes the generated operation again.
- **Immediately-green network edge:** the rejected-network test exercised behavior already added by the error GREEN. A throwaway mutant changed the rejection path to `online`; the focused test failed on the missing alert, the mutant was restored with no source diff, and the four-test suite passed.
- **Refactor:** no separate implementation refactor was necessary after the final GREEN; the state machine remained small, named, and green. Test cleanup isolation was introduced while the online behavior was still RED without changing assertions.

## TDD Gate Compliance

- Three meaningful behavioral RED commits precede their matching GREEN commits.
- Test and implementation changes were never committed together to obtain GREEN.
- No assertion was weakened, skipped, or broadened.
- The final focused suite reports 4 passed, 0 failed.

## Files Created/Modified

- `frontend/package.json` / `frontend/package-lock.json` - Exact direct pins, generated-contract scripts, patched transitive override, and integrity-locked graph.
- `backend/src/verboflex/scripts/export_openapi.py` - Deterministic serialization of the live FastAPI schema.
- `frontend/openapi.json` / `frontend/openapi-ts.config.ts` - Checked-in contract and exact generator configuration.
- `frontend/src/api/client/` - Generator-owned request, response, client, and SDK code.
- `frontend/src/api/config.ts` - Base URL and credential configuration consumed by the generated client initializer.
- `frontend/src/App.tsx` - Health connection state machine and stable accessible UI.
- `frontend/src/App.test.tsx` - Loading, exact healthy, API-error/retry, and rejected-network behavior.
- `frontend/index.html`, `frontend/src/main.tsx`, `frontend/tsconfig.json`, `frontend/vite.config.ts` - Runnable Vite/React/TypeScript/Vitest scaffold.

## Decisions Made

- The two explicitly approved DefinitelyTyped packages are exact direct dependencies because React does not bundle its declarations and Testing Library marks them optional.
- TypeScript 6.0.3 replaces the initially observed 7.0.2 within the already approved package boundary; 7.0.2 caused the exact generator to fail before generation by accessing a removed compiler API.
- `js-yaml` is forced to patched transitive version 4.3.1 through npm `overrides`; the direct dependency allowlist remains exactly 12 names and `npm audit` is clean.
- The generated client is bundled into the project output and imports `createClientConfig` from `src/api/config.ts`; credentials are included and the default base URL remains same-origin.

## Deviations from Plan

### Approved Boundary Revision

- Execution paused before installation because `@types/react` and `@types/react-dom` were required but absent from the approved direct set. After the user's explicit “approvo”, SPEC and audit were revised and committed before installation.

### Auto-fixed Issues

**1. [Rule 2 - Security] Patched vulnerable generator transitive**
- **Found during:** Task 1 dependency lock audit
- **Issue:** The initial graph reported four high-severity paths, all rooted in vulnerable `js-yaml` beneath the exact approved generator.
- **Fix:** Added an npm override to compatible patched `js-yaml@4.3.1`; no direct dependency changed.
- **Files modified:** `frontend/package.json`, `frontend/package-lock.json`
- **Verification:** `npm audit` reports 0 vulnerabilities and the lock asserts `js-yaml=4.3.1`.
- **Committed in:** `a318b61`

**2. [Rule 3 - Blocking] Resolved generator/compiler incompatibility**
- **Found during:** Task 1 first real generation
- **Issue:** `@hey-api/openapi-ts@0.99.0` failed under TypeScript 7.0.2 at `SyntaxKind.AnyKeyword` before producing a client.
- **Fix:** Exact-pinned the already approved TypeScript package to official compatible 6.0.3 and regenerated the lock.
- **Files modified:** `frontend/package.json`, `frontend/package-lock.json`, `01-RESEARCH.md`
- **Verification:** Generation, TypeScript, tests, and build pass under Node 24.15.0.
- **Committed in:** `1b7e53b`, `a318b61`

**3. [Rule 3 - Blocking] Corrected runtime-config path semantics**
- **Found during:** Task 1 generated typecheck
- **Issue:** The initial relative `runtimeConfigPath` was interpreted from project root and generated an invalid import outside `src`.
- **Fix:** Configured the project-root path `./src/api/config.ts` and enabled TypeScript's documented bundler import-extension option.
- **Files modified:** `frontend/openapi-ts.config.ts`, `frontend/tsconfig.json`
- **Verification:** Generated import is `../config.ts`; `npm run typecheck` passes.
- **Committed in:** `a318b61`

**Total deviations:** 3 auto-fixed (1 security, 2 blocking) plus 1 explicitly approved dependency-boundary revision. **Impact:** All changes were necessary for a secure, compilable implementation; no product scope was added.

## Issues Encountered

- npm 11 reported an unapproved optional `fsevents` install script. No script approval was granted or required on this macOS environment; the package remains a locked optional transitive and all required commands pass.
- The final phase-wide coverage, Stryker mutation, browser, license, and Docker layers are intentionally owned by Plans 01-13 through 01-15; this plan does not claim those layers ran.

## Verification Results

- `npm run test -- --run src/App.test.tsx` - 4 passed, 0 failed
- `npm run test -- --run --sequence.shuffle --sequence.seed=103` - 4 passed, seed 103
- `npm run api:check` - pass; regeneration produced no tracked schema/client diff
- `npm run typecheck` - pass
- `npm run build` - pass; 29 modules transformed
- `npm audit` - 0 vulnerabilities
- Direct-dependency/lock gate - 12 approved direct names, 186 integrity-locked npm entries, generator 0.99.0, TypeScript 6.0.3, patched js-yaml 4.3.1
- Handwritten contract guard - no health request/response type exists outside generated output
- `uv run pytest -q` - 1 passed
- `uv run mypy src tests` - pass
- `uv run ruff check src tests` - pass
- `uv run ruff format --check src tests` - 15 files formatted

## API Gate Resolution

- **Scope:** internal, greenfield contract consumed without changing any backend method, path, schema, status, or security signature.
- **Compatibility:** pass; checked-in schema/client establishes the first consumer baseline and drift is fail-on-diff.
- **No implementation leakage:** pass; the UI sees only the generated health result and stable copy, never transport, database, or exception details.
- Other action, pagination, authorization, and rate-limit gates are not applicable to this anonymous bounded read tracer; the backend contract remains owned by its dedicated plans.

## Known Stubs

None introduced by this plan. The generated SDK includes the six intentional backend 501 seams already recorded by Plan 01-02 in `.planning/WINDOWS.md`; this tracer invokes only the implemented health operation.

## User Setup Required

None - the frontend defaults to same-origin API requests and accepts optional `VITE_API_BASE_URL` configuration at build time.

## Next Phase Readiness

- Plan 01-04 can add environment validation and Docker baselines around independently locked backend and frontend applications.
- Later auth UI plans can reuse the generated SDK and centralized credentials/base-URL configuration without creating handwritten HTTP types.
- No unresolved blocker remains.

## Self-Check: PASSED

- Every claimed key artifact exists and all ten pre-close-out commits resolve.
- The final source state is clean except for the orchestrator-owned, intentionally uncommitted `.planning/milestone.lock`.
- Focused/randomized tests, generation drift, TypeScript, production build, backend checks, and npm audit all passed after the final source edit.

---
*Phase: 01-platform-foundation*
*Completed: 2026-08-24*
