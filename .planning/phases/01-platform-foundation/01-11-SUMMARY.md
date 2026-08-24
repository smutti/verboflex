---
phase: 01-platform-foundation
plan: 11
subsystem: ui-foundation
tags: [tailwind, shadcn, design-tokens, accessibility, tdd]

requires:
  - phase: 01-platform-foundation/01-10
    provides: Official modern new-york-v4 Radix registry configuration and project-owned primitives
provides:
  - Exact Phase 1 typography, spacing, color, focus, font, and radius roles
  - One-time global stylesheet integration at the React entry point
  - Fail-closed static theme contract with proved negative controls
affects: [authentication-ui, dashboard-shell, phase-1-gauntlet]

actuals:
  tokens: 3008
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - Semantic theme roles mapped into modern shadcn Tailwind variables
    - Static source contract limited to the governed stylesheet and app entry

key-files:
  created:
    - frontend/src/styles/theme.test.ts
  modified:
    - frontend/src/index.css
    - frontend/src/main.tsx

key-decisions:
  - "Keep official generated shadcn component sources unchanged; enforce Phase 1 visuals through the global theme boundary."
  - "Do not add a next-themes provider until a selectable or dark theme is approved; the official Sonner wrapper already falls back to system without one."

patterns-established:
  - "Theme boundary: approved literal roles live in index.css and generated primitives consume semantic aliases."
  - "Theme drift gate: inspect only handwritten theme sources and prove each custom guard with a known-bad mutation."

requirements-completed: [PLAT-02, UI-01]

coverage:
  - id: D1
    description: "The global theme implements the exact approved Phase 1 typography, spacing, colors, system font, focus indicator, and radius ceiling."
    requirement: UI-01
    verification:
      - kind: unit
        ref: "frontend/src/styles/theme.test.ts#approved Phase 1 theme contract"
        status: pass
      - kind: other
        ref: "cd frontend && npm run lint && npm run build"
        status: pass
    human_judgment: false
  - id: D2
    description: "Theme drift fails fast without inspecting or modifying official generated shadcn component sources."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "cd frontend && npm run test -- --run src/styles/theme.test.ts"
        status: pass
      - kind: other
        ref: "Six isolated negative controls: size, weight, spacing, remote font, missing focus-visible, and radius above 8px"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-08-24
status: complete
---

# Phase 1 Plan 11: Approved Visual Theme Summary

**A quiet, exact Phase 1 theme now maps approved visual roles into modern shadcn/Tailwind and rejects token drift through a fail-closed static contract.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-08-24T19:23:33Z
- **Completed:** 2026-08-24T19:31:31Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Replaced the generated placeholder stylesheet with exact four-size/two-weight typography, the seven-step 4px spacing scale, approved color roles, the system font stack, a visible teal focus indicator, and an 8px panel-radius ceiling.
- Mapped those roles to the semantic variables consumed by the official modern shadcn sources without editing any generated component.
- Imported the stylesheet exactly once from `main.tsx` and added seven static contract tests over handwritten sources only.
- Proved all six requested known-bad classes fail for the intended clause, restored the stylesheet after every mutation, and proved the clean state green.

## Task Commits

1. **Task 1: Apply exact typography, spacing, color, focus, and radius** — `7128de2` (feat)
2. **Task 2: Make visual-token drift fail fast** — `7cb92f7` (test)

## Files Created/Modified

- `frontend/src/index.css` — Approved semantic tokens, shadcn mappings, base font/surface rules, and focus-visible treatment.
- `frontend/src/main.tsx` — Single global stylesheet import at the application entry.
- `frontend/src/styles/theme.test.ts` — Fail-closed static contract for the governed CSS and import boundary.

## Decisions Made

- Kept the official modern component sources byte-for-byte outside this plan's scope; the global theme is the customization seam.
- Did not wrap the application in `ThemeProvider`. Phase 1 defines no dark/selectable theme, and the official Sonner wrapper's `useTheme` fallback already supplies `system` when no provider is present. This avoids implying an unapproved dark-mode contract or adding theme persistence/UI.

## TDD and Negative-Control Evidence

- The theme behavior existed after Task 1, so Task 2 followed the old-coder pre-existing-behavior rule: correct assertions passed cleanly, then throwaway source mutants demonstrated that the assertions can fail.
- **6/6 controls killed:** display size `28px → 30px`; semibold `600 → 700`; spacing `24px → 22px`; injected remote `@font-face`; `:focus-visible → :focus`; panel radius `8px → 12px`.
- Every control produced exactly one failing contract test for its intended clause. The source was restored after each control and the final focused run passed 7/7 tests.

## Verification Evidence

- Focused theme contract: **1 file, 7 tests passed**.
- Full frontend suite: **5 files, 22 tests passed**.
- Randomized suite health, seed `1101`: **5 files, 22 tests passed**.
- TypeScript: 0 errors.
- ESLint: 0 errors and 0 warnings.
- Production build: Vite completed successfully; compiled CSS 47.36 kB and JS 200.53 kB before gzip.
- Generated API drift check: passed with no OpenAPI or client diff.
- Dependency audit: 0 vulnerabilities at `high` threshold; this plan added no dependency.
- API/HTTP surface: unchanged; `old-coder-api` is not applicable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Made static source loading compatible with Vitest and the approved type graph**

- **Found during:** Task 2 focused contract run.
- **Issue:** Vite transformed `import.meta.url`/raw asset access under jsdom, while direct Node imports lacked types because `@types/node` is not an approved direct dependency.
- **Fix:** Read the source with Vitest's Node runtime, used a narrow documented type boundary in the test, and added no package or configuration file.
- **Files modified:** `frontend/src/styles/theme.test.ts`.
- **Verification:** Focused test, typecheck, lint, and full build all pass.
- **Committed in:** `7cb92f7`.

---

**Total deviations:** 1 auto-fixed blocking issue
**Impact on plan:** The intended three-file boundary and direct dependency set remain exact.

## Issues Encountered

- The initial checker-source loader failed before test collection; it was not counted as behavioral RED. The final checker was subsequently subjected to the complete six-control mutation matrix.

## Known Stubs

None.

## User Setup Required

None - no external service, secret, font download, or manual configuration is required.

## Next Phase Readiness

- Plan 01-12 can build login and password-change surfaces using named theme utilities and the existing official form primitives.
- Plan 01-13 can apply the same roles to the authenticated shell without creating a second styling system.
- No blocker remains.

## Self-Check: PASSED

- All three governed files exist.
- Commits `7128de2` and `7cb92f7` exist.
- The final source state passes focused/full tests, shuffled suite, typecheck, lint, build, API drift, and dependency audit gates.

---
*Phase: 01-platform-foundation*
*Completed: 2026-08-24*
