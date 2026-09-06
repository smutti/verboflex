---
phase: 04-localization-import-search-and-constraints
plan: 22
subsystem: published-import-ui
tags: [react, typescript, parser-diagnostics, polling, accessibility, vitest]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [15]
    provides: generated canonical dataset and parser issue contracts
provides:
  - bounded atomic parser outcomes with retained-dataset copy and administrator recovery
  - current retry and polling authority with terminal focus and responsive presentation
affects: [import-diagnostics, admin-mappings, phase-verification]
actuals:
  tokens: 8987
  tasks: 2
  commits: 5
tech-stack:
  added: []
  patterns:
    - fixed category text and literal generated issue fields
    - execution-monotonic collection reconciliation and per-request polling cancellation
key-files:
  created: []
  modified:
    - frontend/src/features/admin/imports/PublishedMappingImports.tsx
    - frontend/src/features/admin/imports/PublishedMappingImports.test.tsx
    - frontend/src/features/admin/imports/useImportPolling.ts
    - frontend/src/features/admin/imports/useImportPolling.test.ts
key-decisions:
  - "Parser outcomes use canonical dataset_status for retained/no-dataset copy and expose only five safe issue categories."
  - "Accepted generated import projections become visible immediately; older collection responses cannot roll execution or terminal status backward."
  - "Cancel superseded browser status GETs and fence each response generation without cancelling durable worker execution."
requirements-completed: [FMT-06, FMT-08]
coverage:
  - id: D1
    description: "Parser failures retain canonical baseline context, show exact bounded diagnostics in side/provider order, and limit recovery by principal role."
    requirement: FMT-06
    verification:
      - kind: unit
        ref: "frontend/src/features/admin/imports/PublishedMappingImports.test.tsx — retained/no-dataset, zero/one/five/seven issues, safe text, and four-role recovery assertions"
        status: pass
    human_judgment: false
  - id: D2
    description: "Accepted imports and terminal polling remain current through stale collection, overlapping GET, duplicate retry, and unmount conditions."
    requirement: FMT-08
    verification:
      - kind: integration
        ref: "frontend/src/features/admin/imports/PublishedMappingImports.test.tsx — real polling hook and deferred request regressions"
        status: pass
      - kind: unit
        ref: "frontend/src/features/admin/imports/useImportPolling.test.ts — bounded schedule, complete identity, terminal stop, and unmount cancellation"
        status: pass
    human_judgment: false
  - id: D3
    description: "Parser outcomes wrap without clipped content at 390/768/1440, preserve keyboard focus, announce state transitions, and disable nonessential motion."
    verification:
      - kind: automated_ui
        ref: "/tmp/verboflex-04-22-smoke.mjs — Chromium DOM bounds and computed reduced-motion styles; /tmp/verboflex-04-22-{390,768,1440}.png"
        status: pass
      - kind: unit
        ref: "frontend/src/features/admin/imports/PublishedMappingImports.test.tsx — user-triggered terminal focus, background focus preservation and live-region assertions"
        status: pass
    human_judgment: false
duration: 12min
completed: 2026-09-06
status: complete
---

# Phase 04 Plan 22: Published Parser Outcomes Summary

**Published mapping rows now show bounded, literal parser diagnostics while preserving canonical datasets and fencing retry, polling, and terminal focus authority.**

## Performance

- Started: 2026-09-06T08:09:52Z
- Completed: 2026-09-06T08:21:41Z
- Tasks: 2
- Implementation/test files modified: 4
- Actuals: 35,945 realized diff characters / 4, rounded upward to 8,987 estimate-scale tokens; five implementation/test commits.

## Accomplishments

- Exact retained-dataset and first-failure alerts use the generated canonical dataset status. Five closed category labels, literal paths and safe optional locations replace generic parser prose. Issues retain provider order within Keys before Translations, stop at five, and include the exact remainder count.
- The existing mapping Retry import remains the only retry action. Only a base-language issue renders Configure base language, only for the authenticated administrator, with the exact product Preview route.
- Accepted server projections immediately disable further imports. Execution-aware collection reconciliation and terminal persistence prevent rollback; generation-fenced, abortable status GETs prevent older manual requests from replacing newer results.
- User-initiated terminal errors focus their own row alert when focus still belongs to the invoking workflow. Background failures preserve unrelated focus. Responsive wrapping and reduced-motion styles work in the actual browser.

## Task Commits and TDD Gate Compliance

1. Task 1 RED — `9bd13da`: eight expected failures for missing parser alert, issue anatomy, and administrator recovery; legacy tests remained green.
2. Task 1 GREEN — `a34693a`: shared parser presentation and role-aware recovery; 29 component tests and TypeScript passed.
3. Task 2 RED — `568ba9b`: six expected failures covering accepted retry visibility, out-of-order status, terminal focus, and reduced-motion controls.
4. Task 2 GREEN — `8a76ed2`: immediate accepted projection, monotonic state, terminal focus, and polling request fencing; 55 focused tests and TypeScript passed.
5. REFACTOR — `68464e3`: consolidated initial-import/retry authority and effect cleanup ownership; 56 focused tests, lint, TypeScript, and production build passed.

## Files Created/Modified

- `PublishedMappingImports.tsx`: shared bounded parser alert, administrator Preview recovery, accepted/terminal projection reconciliation, and focus handling.
- `PublishedMappingImports.test.tsx`: exact copy, zero/one/five/more issues, closed category safety, role recovery, real-hook races, focus, and responsive contracts.
- `useImportPolling.ts`: per-request generation and AbortSignal for superseded or unmounted browser observation; unavailable generated results pause safely.
- `useImportPolling.test.ts`: generated-request and unmount assertions account for browser GET cancellation while durable worker work remains unchanged.

## Decisions Made

- Reuse `getAdminImport` and `startAdminPublishedMappingImport`, the existing generated names, rather than the plan's illustrative `getImportJob`/`createImportJob` names.
- Preserve server-projected provider ordering within repository side; no client path sorting or raw parser prose is introduced.
- Use the existing authenticated session only for the exceptional base-language recovery component.
- Browser observation cancellation is independent of background execution ownership.

## Deviations from Plan

**1. [Rule 2 - Missing critical race protection] Extend the existing polling hook and its tests**
- Found during Task 2: two overlapping manual status reads shared one generation and could overwrite a newer terminal outcome; the component test reproduced the rollback.
- Fix: increment generation for every request, abort superseded observation GETs, abort on authority change/unmount, and retain the existing logical-import/execution identity checks.
- Files: `useImportPolling.ts`, `useImportPolling.test.ts`, plus the planned component regression suite.
- Verification: the deferred-response race, all 19 polling tests, and the complete 56-test focused slice pass.
- Commit: `8a76ed2`.
- Impact: two adjacent files added to the plan's file list; no new API, dependency, provider write, or worker cancellation.

## Verification

- Focused component and polling suites: 56 tests passed across 2 files.
- `npm --prefix frontend run typecheck`: passed.
- `npm --prefix frontend run lint`: passed with zero warnings after capturing the effect-owned ref for cleanup.
- `npm --prefix frontend run build`: passed; repeated the existing nonblocking >500 kB chunk advisory.
- Chromium smoke using the real Vite-transformed component and generated GET with controlled API responses: document widths exactly 390/768/1440; no alert, issue, or button clipping; computed transition property `none` under reduced motion. Mobile screenshot visually inspected.
- `git diff --check`: passed. No tracked files deleted, no production stubs, raw HTML rendering, TODOs, or FIXMEs introduced.
- Review checked safe field selection, role restriction, execution/identity ownership, terminal stop, literal path rendering, and cleanup. No unresolved finding remains.

## Issues Encountered

- The first browser smoke harness expected a named export from Vite's prebundled CommonJS adapter; using the adapter's default export fixed the harness. A subsequent motion assertion was corrected to inspect `transition-property: none` rather than the irrelevant inherited transition duration.
- No implementation or verification remains deferred.

## Known Stubs

None. Empty issue arrays are intentional zero-issue fixtures; no unwired production data remains.

## Threat Review

- T-04-70: bounded fixed categories and literal fields, no server prose or executable imported markup.
- T-04-71: per-request and complete-job authority fences plus monotonic collection reconciliation.
- T-04-72: existing bounded schedule, immediate duplicate prevention, terminal stop, and observation cleanup.
- No new endpoint, authentication path, file-access boundary, or database trust surface.

## Documentation References

- [React effect cleanup](https://react.dev/reference/react/useEffect) and [React Router Link](https://reactrouter.com/api/components/Link); Context7 MCP and CLI were unavailable, so official documentation supplied the fallback.

## User Setup Required

None.

## Next Phase Readiness

Published mappings expose the approved parser outcomes through the generated contract. Phase-level integration and remaining plans can proceed; the browser smoke server was stopped after verification.

## Self-Check: PASSED

All four implementation/test files and this summary exist. All five task commits resolve in Git history. The focused checks and browser measurements above passed, and unrelated user/runtime files remain untouched.
