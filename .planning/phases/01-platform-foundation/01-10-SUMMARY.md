---
phase: 01-platform-foundation
plan: 10
subsystem: ui-foundation
tags: [shadcn, radix-ui, react, tailwind, supply-chain]

requires:
  - phase: 01-platform-foundation/01-09
    provides: Deterministic generated API client and memory-only browser session boundary
provides:
  - Official modern new-york-v4 Radix registry configuration
  - Thirteen project-owned shadcn UI primitives and the official Sidebar mobile hook
  - Exact-pinned audited frontend dependency graph with runnable type, lint, build, and audit gates
affects: [theme, authentication-ui, dashboard-shell, phase-1-gauntlet]

actuals:
  tokens: 145047
  tasks: 2
  commits: 6

tech-stack:
  added:
    - shadcn 4.19.0
    - radix-ui 1.6.7
    - next-themes 0.4.6
    - Tailwind CSS 4.3.3
    - ESLint 9.39.5 compatible toolchain
  patterns:
    - Exact official-registry component allowlist
    - Unified Radix direct dependency with individual primitives transitively locked
    - Registry-owned lint exceptions isolated from handwritten application code

key-files:
  created:
    - frontend/components.json
    - frontend/src/lib/utils.ts
    - frontend/src/components/ui
    - frontend/src/hooks/use-mobile.ts
    - frontend/eslint.config.js
    - frontend/src/index.css
  modified:
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/tsconfig.json
    - frontend/vite.config.ts
    - .planning/phases/01-platform-foundation/01-SPEC.md
    - .planning/phases/01-platform-foundation/01-RESEARCH.md
    - .planning/phases/01-platform-foundation/01-UI-SPEC.md
    - .planning/phases/01-platform-foundation/01-10-PLAN.md

key-decisions:
  - "Use the current official shadcn@4.19.0 new-york-v4 Radix registry source with direct radix-ui and next-themes instead of the superseded legacy adaptation."
  - "Allow exactly thirteen UI component files, components.json, utils.ts, and the official use-mobile hook as the 16-file registry/configuration boundary."
  - "Freeze ESLint and @eslint/js at 9.39.5 because the approved jsx-a11y plugin rejects ESLint 10; never force an incompatible peer graph."

patterns-established:
  - "Registry gate: named @shadcn items resolve to the official new-york-v4 Radix source and no custom registry namespace is configured."
  - "Generated-source gate: keep official Vite-transformed sources unchanged and scope unavoidable lint exceptions only to registry-owned paths."

requirements-completed: [PLAT-02, UI-01]

coverage:
  - id: D1
    description: Seven approved form, feedback, and action primitives plus shared config and utility are installed from the official modern registry.
    requirement: UI-01
    verification:
      - kind: other
        ref: "cd frontend && npm run typecheck && npm run lint"
        status: pass
    human_judgment: false
  - id: D2
    description: All thirteen approved primitives and the official Sidebar mobile hook compile and build within the exact 16-file registry/configuration allowlist.
    requirement: PLAT-02
    verification:
      - kind: other
        ref: "cd frontend && npm run test -- --run && npm run typecheck && npm run lint && npm run build"
        status: pass
      - kind: other
        ref: "Plan 01-10 allowlist checker with two proved failing negative controls"
        status: pass
    human_judgment: false
  - id: D3
    description: The resolved npm graph contains only approved direct additions, uses unified Radix, and has no known high-severity vulnerability.
    requirement: UI-01
    verification:
      - kind: other
        ref: "cd frontend && npm ls --depth=0 && npm audit --audit-level=high"
        status: pass
    human_judgment: false

duration: 31min
completed: 2026-08-24
status: complete
---

# Phase 1 Plan 10: Modern shadcn Primitive Boundary Summary

**The official shadcn 4.19 modern Radix registry now supplies exactly thirteen owned UI primitives and Sidebar's required mobile hook through a locked, audited dependency boundary.**

## Performance

- **Duration:** 31 min
- **Started:** 2026-08-24T18:46:06Z
- **Completed:** 2026-08-24T19:17:06Z
- **Tasks:** 2
- **Files modified:** 26 before this summary
- **Implementation commits:** 5 before metadata close-out

## Accomplishments

- Initialized the official neutral `new-york` Vite configuration, resolved by Tailwind v4 and `shadcn@4.19.0` to the modern `new-york-v4` Radix source.
- Installed exactly the thirteen approved component files, `components.json`, `src/lib/utils.ts`, and the official `src/hooks/use-mobile.ts` Sidebar dependency: 16/16 governed files and no unrelated component.
- Replaced the originally audited individual Radix direct packages with exact `radix-ui@1.6.7`, authorized `next-themes@0.4.6`, and preserved all individual `@radix-ui/react-*` packages as transitive-only implementation details.
- Added the approved Tailwind and lint prerequisites needed to make the plan's typecheck, lint, and production-build gates executable.
- Proved the component and direct-dependency allowlist checkers fail against known-bad inputs before accepting their clean-state results.

## Approval and Decision History

- `5aaf612` recorded the initially approved conservative legacy adaptation without hiding the upstream drift that prompted it.
- The user then explicitly superseded that choice with “Procedi con il moderno e implementa”.
- `1d39214` made the modern boundary authoritative in the SPEC, audit, UI contract, and plan before modern registry files were installed.
- `4d6ab3a` recorded the compatible ESLint resolution after npm rejected the incompatible 10.x graph without changing any approved package name.

## Registry Provenance

- CLI: `shadcn@4.19.0`, official `shadcn-ui/ui` repository, maintainers `shadcn` and `npm_bot_shadcn`, Node `>=20.18.1`, lock integrity `sha512-EQF6R+CUXTsEP2BpyhxrUEAFesrtFD1POvVOf5jM+wkgtA4kG1EW1+1Wlmi9LqiprSL681JJXBcS0u8WkVVVyQ==`.
- Registry: implicit official `@shadcn` URL `https://ui.shadcn.com/r/styles/{style}/{name}.json`; `components.json` contains no third-party registry.
- CLI inspection resolves `style=new-york`, `base=radix`, Tailwind v4, `@/components/ui`, `@/lib/utils`, and `@/hooks`.
- `shadcn add --diff` reports the installed files unchanged except for the CLI's expected Vite transform that removes non-applicable `"use client"` directives.

| Official item | Registry response SHA-256 |
|---|---|
| button | `9f7f226ca4f52ad6c9ea420e82ec1ca4e236cfa69e8d0b0ac3096a3133cfc465` |
| input | `9f3fa74d6744e2106878db7d6a7d7c7f1a1d2650ee9bc04ec981c7e78a132d9e` |
| label | `11851fa86fcaaa70050086b42f3457627a6a98230789d216ad627068ddee9c57` |
| form | `63dd5ec1ad25eff37b95445743236a9550f7ed950dd15c495fe7ebb23366deb0` |
| alert | `530f99d6b5cf6d3182f5dca4809577e2ce31de6a07dd0bb1245fc6b306456804` |
| badge | `0bb0fe8c8c1fa512fe84e960416c6585f129a0e579287b660e3d6ec4c42abdcf` |
| sonner | `439c5d5256091829350d3136309f55f8ba788f1cc0f0dbad016ce6b5b2765488` |
| tooltip | `17873816035c46cfae78486034703840a9fd9b0a00457b61faf68ee2e2510d04` |
| dropdown-menu | `b14db93e531088958b3fe42c5a793aa40840677092a377a2e92fc267eac8992a` |
| separator | `cf1802f2c1f2fa4e1e853142a5dbd68a763756afe365520b1b33e44696e983c3` |
| sidebar | `a58ce44fe368b62399bf501ea1dfb2a3ba886a11decc01585875508ae633c49f` |
| sheet | `4e213f76cc45ba7db57d493d72789ddce0d877c99c14f40804614260b07061dd` |
| skeleton | `f5137a0b549e0d12ac95ef3f37eda2971a0e80b4ba818f7426d153fc079e5e7d` |
| use-mobile | `4cd4736a08751c89e2ebc10f9d329c430ddb6194f46bf848e5ed470c0407bca1` |

## Exact Governed File Inventory

1. `frontend/components.json`
2. `frontend/src/lib/utils.ts`
3. `frontend/src/components/ui/alert.tsx`
4. `frontend/src/components/ui/badge.tsx`
5. `frontend/src/components/ui/button.tsx`
6. `frontend/src/components/ui/dropdown-menu.tsx`
7. `frontend/src/components/ui/form.tsx`
8. `frontend/src/components/ui/input.tsx`
9. `frontend/src/components/ui/label.tsx`
10. `frontend/src/components/ui/separator.tsx`
11. `frontend/src/components/ui/sheet.tsx`
12. `frontend/src/components/ui/sidebar.tsx`
13. `frontend/src/components/ui/skeleton.tsx`
14. `frontend/src/components/ui/sonner.tsx`
15. `frontend/src/components/ui/tooltip.tsx`
16. `frontend/src/hooks/use-mobile.ts`

No `table`, `tabs`, standalone `dialog`, `select`, data grid, Base UI, React Aria, third-party registry, or extra hook file exists.

## Direct Dependency and Lock Diff

The root lock moved from 189 to 762 package entries and from 13 to 33 direct entries. All 20 additions are exact pins; Group 2 changed no direct package or lock entry.

### Runtime additions

| Dependency | Version |
|---|---:|
| `@hookform/resolvers` | 5.9.1 |
| `class-variance-authority` | 0.7.1 |
| `clsx` | 2.1.1 |
| `lucide-react` | 1.34.0 |
| `next-themes` | 0.4.6 |
| `radix-ui` | 1.6.7 |
| `react-hook-form` | 7.86.0 |
| `sonner` | 2.0.8 |
| `tailwind-merge` | 3.6.0 |
| `zod` | 4.4.3 |

### Development additions

| Dependency | Version |
|---|---:|
| `@eslint/js` | 9.39.5 |
| `@tailwindcss/vite` | 4.3.3 |
| `eslint` | 9.39.5 |
| `eslint-plugin-jsx-a11y` | 6.10.2 |
| `eslint-plugin-react-hooks` | 7.1.1 |
| `eslint-plugin-react-refresh` | 0.5.4 |
| `shadcn` | 4.19.0 |
| `tailwindcss` | 4.3.3 |
| `tw-animate-css` | 1.4.0 |
| `typescript-eslint` | 8.67.0 |

No direct dependency was removed or upgraded. Direct individual `@radix-ui/react-*` packages are absent. Lock integrity for `radix-ui@1.6.7` is `sha512-QBdhh1arIEUvPC0dQ5+nwWAxt7+N+oP/9jPwjJkGFoSk/sqxg32gJtSXGtFh8frAIcS6oC9cx2Q+7KYCQLOAeA==`; `next-themes@0.4.6` is `sha512-pZvgD5L0IEvX5/9GWyHMf3m8BKiVQwsCMHfoFosXtXBMnaS0ZnIJ9ST4b4NqLVKDEm8QBxoNNGNaBv2JNF6XNA==`.

The new direct licenses are MIT except `class-variance-authority` (Apache-2.0) and `lucide-react` (ISC). The complete direct inventory reported no unknown license.

## Verification Evidence

- Group 1: `npm run typecheck && npm run lint` passed after seven official files were installed.
- Group 2/final fresh run: **4 test files, 15 tests passed**; TypeScript reported 0 errors; ESLint reported 0 errors and 0 warnings; Vite 8.2.2 produced the production bundle; `npm ls --depth=0` returned a valid tree.
- `npm audit --audit-level=high`: **0 vulnerabilities** across the resolved graph.
- Component/config allowlist: **16/16 pass**; component subset **13/13 pass**; hook **1/1**; utility **1/1**; config **1/1**.
- Custom negative controls: **2/2 failed for the intended reason** (injected `table.tsx`; injected direct `@radix-ui/react-slot`) before clean-state acceptance.
- API surface: unchanged; `old-coder-api` remained non-applicable.
- Coverage, mutation, property, and browser checks are not claimed for generated/config-only behavior in this plan; handwritten application behavior did not change. The Phase 1 final gauntlet owns those layers.

## Task Commits

1. **Record conservative registry decision** — `5aaf612` (docs; later superseded, history retained)
2. **Authorize modern official registry boundary** — `1d39214` (docs)
3. **Record compatible lint resolution** — `4d6ab3a` (docs)
4. **Task 1: Install approved form, feedback, and action primitives** — `ed0f637` (chore)
5. **Task 2: Install approved navigation, disclosure, and loading primitives** — `fd992c2` (feat)

## Files Created/Modified Outside the 16-File Registry Boundary

- `frontend/package.json`, `frontend/package-lock.json` — exact direct pins and resolved graph.
- `frontend/tsconfig.json`, `frontend/vite.config.ts` — official `@/*` alias and Tailwind Vite integration.
- `frontend/eslint.config.js` — executable approved lint toolchain; exceptions apply only to known official registry-source patterns.
- `frontend/src/index.css` — official Tailwind/shadcn initialization target, handed to Plan 01-11 for the approved visual-token contract.
- Phase planning files — append-only approvals, audit evidence, modern UI boundary, and exact 16-file plan inventory.

## Decisions Made

- Followed the user's final modern-source choice while retaining the superseded conservative choice as visible decision history.
- Used official named registry items rather than raw copied source; the CLI performed its normal Vite-only directive transform.
- Kept the registry config free of custom namespaces, so every named item resolves through official `@shadcn` only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Selected the compatible ESLint 9 line without forcing peers**

- **Found during:** Task 1 dependency installation.
- **Issue:** `eslint-plugin-jsx-a11y@6.10.2` rejects ESLint 10, so npm stopped with `ERESOLVE`.
- **Fix:** Reverified and exact-pinned official `eslint@9.39.5` and `@eslint/js@9.39.5`; no `--force` or `--legacy-peer-deps` was used.
- **Verification:** `npm ls --depth=0`, lint, build, and audit pass.
- **Committed in:** `4d6ab3a`, `ed0f637`.

**2. [Rule 3 - Blocking] Added missing Vite/Tailwind/alias/lint prerequisites**

- **Found during:** Task 1 official CLI preflight and the required lint gate.
- **Issue:** The existing scaffold had no Tailwind plugin, import alias, stylesheet target, ESLint config, or `lint` script, so official shadcn initialization and the plan verifier could not run.
- **Fix:** Added only already approved tool packages and minimal official Vite/Tailwind/alias/lint configuration.
- **Verification:** `shadcn info`, typecheck, lint, build, and all 15 existing frontend tests pass.
- **Committed in:** `ed0f637`.

**3. [Rule 3 - Blocking] Scoped new React lint rules around unchanged official registry source**

- **Found during:** Task 2 lint gate.
- **Issue:** Current React Hooks lint rules reject the official Sidebar random skeleton width and official `use-mobile` effect initialization; editing them would diverge from the user-selected modern source.
- **Fix:** Disabled only `react-hooks/purity` and `react-hooks/set-state-in-effect` on registry-owned component/hook paths. Handwritten application code retains the normal rules except previously existing, explicitly scoped effect exceptions.
- **Verification:** Generated sources remain CLI-identical modulo Vite directive transforms; lint exits with 0 errors/warnings and build passes.
- **Committed in:** `fd992c2`.

---

**Total deviations:** 3 auto-fixed blocking issues
**Impact on plan:** The exact modern registry source and 16-file allowlist are preserved; no unapproved dependency, registry, component, API, or screen entered scope.

## Issues Encountered

- The first conservative choice was deliberately superseded by the user's later modern-source authorization; both decisions remain append-only in planning history.
- npm warns that ESLint 9.39.5 is outside current upstream support, but it is the newest compatible line accepted by every approved lint plugin. This is a known supply-chain compatibility limit, not a vulnerability finding; Phase 1's final audit should re-evaluate when `eslint-plugin-jsx-a11y` supports ESLint 10.
- npm reported the optional transitive `fsevents@2.3.3` install script as not pre-approved on this macOS environment; it was not executed, is not direct, and all build/test gates pass.

## Known Stubs

None. The global stylesheet is an intentional official initialization target and Plan 01-11 owns its approved theme-token implementation.

## User Setup Required

None - no external account, secret, or manual configuration is required.

## Next Phase Readiness

- Plan 01-11 can apply the approved visual tokens to the initialized Tailwind/shadcn stylesheet.
- Plans 01-12 and 01-13 can import the exact owned form, feedback, navigation, disclosure, loading, and toast primitives.
- No Plan 01-10 blocker remains.

## Self-Check: PASSED

- All 16 governed registry/configuration files exist.
- Commits `5aaf612`, `1d39214`, `4d6ab3a`, `ed0f637`, and `fd992c2` exist.
- Final test/type/lint/build/audit and both negative controls passed from the current source state.

---
*Phase: 01-platform-foundation*
*Completed: 2026-08-24*
