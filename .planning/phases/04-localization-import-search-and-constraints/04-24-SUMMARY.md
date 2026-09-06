---
phase: 04-localization-import-search-and-constraints
plan: 24
subsystem: translation-routing
tags: [react-router, authentication, navigation, vitest, playwright]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [23]
    provides: Principal-scoped translation workspace and search page
provides:
  - Protected direct translation search index with authenticated workspace context
  - All-role Translations navigation after Workspace with responsive keyboard semantics
affects: [translation-detail, phase-04-browser-verification]
actuals:
  tokens: 4451
  tasks: 2
  commits: 7
tech-stack:
  added: []
  patterns:
    - Reuse the session route boundary and principal-scoped Outlet workspace
    - Share one destination component between desktop navigation and mobile Sheet
key-files:
  created: []
  modified:
    - frontend/src/router.tsx
    - frontend/src/router.test.tsx
    - frontend/src/components/layout/AppShell.tsx
    - frontend/src/components/layout/AppShell.test.tsx
key-decisions:
  - "Translation search inherits the established signed-out login redirect and authenticated unknown-path Workspace fallback; no new return-to protocol is introduced."
  - "Use the existing boundary-aware navigation matching for Translations and descendants, with a shared 44px navigation target minimum."
requirements-completed: [SRCH-01, SRCH-06, SRCH-08]
coverage:
  - id: D1
    description: Authenticated direct translation search restores authorized principal preferences and defaults for all roles; session checking, signed-out and password-change states cannot start translation reads.
    verification:
      - kind: integration
        ref: frontend/src/router.test.tsx
        status: pass
    human_judgment: false
  - id: D2
    description: Translations follows Workspace in desktop and mobile navigation, supports active descendants and keyboard selection, and retains responsive focus and containment.
    verification:
      - kind: unit
        ref: frontend/src/components/layout/AppShell.test.tsx
        status: pass
      - kind: automated_ui
        ref: Chromium production-preview smoke at 320, 768, 1024 and 1440px
        status: pass
    human_judgment: false
duration: 8min
completed: 2026-09-06
status: complete
---

# Phase 04 Plan 24: Authenticated Translation Navigation Summary

Translation search is directly reachable at `/translations` behind server-restored session authority and appears immediately after Workspace in primary navigation.

## Performance

- Started: 2026-09-06T08:44:30Z (approximate executor start).
- Completed: 2026-09-06T08:52:00Z.
- Tasks: 2; implementation/test files: 4.
- Actual tokens: 4,451, ceiling of 17,802 realized implementation/test diff characters divided by four; excludes metadata and harness tokens.

## Accomplishments

- Registered a nested `/translations` parent with an index `TranslationSearchPage`, using the existing `TranslationsWorkspace` Outlet and authenticated AppShell. The server principal and memory-only token pass through unchanged.
- Tested every internal role, direct URLs with ignored query parameters, principal-isolated defaults, authorized stored product/language choices, session loading and signed-out no-read behavior, restricted-password redirects, and bounded unknown nested paths.
- Added exactly one Translations destination after Workspace, using the approved Lucide Languages icon. Shared link logic preserves active descendants, boundary-safe matching, visible focus, Enter selection, responsive containment, Sheet closure and trigger-focus restoration.
- Verified the production bundle and SPA fallback in Chromium at 320, 768, 1024 and 1440px using fixture-backed generated network responses. Navigation order, current state, at-least-44px targets and absence of horizontal overflow passed with zero browser runtime errors.

## Task Commits and TDD Gate Compliance

1. `5ab10d1` — Task 1 RED: five direct search/preference cases failed because translations redirected to Workspace; existing auth/fallback assertions passed.
2. `d36485f` — Task 1 GREEN: registered authenticated workspace/index route; runtime tests passed after correcting the assertion to generated query field `q`.
3. `06275be` — Task 1 typing correction: explicitly selected non-throwing generated refresh transport for the deferred promise. TypeScript then passed.
4. `4fe1059` — Task 2 RED: twelve navigation assertions failed because the destination was absent.
5. `13b454e` — Task 2 GREEN: added shared Translations destination and formatted changed tests.
6. `e708981` — Supplemental RED: four role cases failed the 44px navigation-target assertion after production browser smoke exposed the undersized target.
7. `ce84ddb` — Supplemental GREEN: raised shared routed and standalone navigation targets to 44px.

Both tasks have observed RED before implementation. No standalone REFACTOR was needed; the existing route and destination patterns remain canonical. The initial Task 1 production commit preceded detection of a test-only generic Promise type error; the immediately following correction restored typecheck before final validation. No check remains failing or skipped.

## Verification

- Router: 32 passed; AppShell: 32 passed; combined final run: **64 passed**.
- `npm --prefix frontend run typecheck`: passed.
- `npm --prefix frontend run lint`: passed, zero tolerated warnings.
- `npm --prefix frontend run build`: passed, 1,988 modules transformed. The existing chunk-size advisory remains out of scope.
- Production Vite preview with Chromium: direct `/translations` returns HTTP 200 and renders actual authenticated search at 320/768/1024/1440px; navigation text/order, active state, target height, page containment and zero runtime errors passed.
- Reviewed the four-file diff against AGENTS.md and the UI contract: no backend authorization change, dependency, raw HTML, persistent token, detail route or provider action introduced.
- `git diff --check`, stub scan, tracked-deletion check and ownership review passed. Existing untracked runtime/research directories were preserved. The owned preview server was stopped.
- Context7 MCP and CLI were unavailable; nested route and Outlet behavior were checked against [official React Router routing documentation](https://reactrouter.com/start/declarative/routing).

## Decisions Made

The existing application redirects signed-out navigation to Login without retaining a return-to URL. Translation routing deliberately uses that same contract. Unknown nested translation paths use the existing authenticated Workspace fallback. Plan 18 owns the future opaque detail child under this parent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Enforced the required mobile touch target on shared navigation links.**

- Found during Task 2 production-browser verification: the inherited `min-h-9` navigation target was below the UI contract's 44px minimum.
- Added a failing role-parametrized assertion and changed the shared routed/standalone link minimum to `min-h-[44px]`, preserving the same desktop/mobile component.
- Files: `frontend/src/components/layout/AppShell.tsx` and its test.
- Verification: 64 focused tests, TypeScript, lint, production build and Chromium responsive smoke all pass.
- Commits: `e708981`, `ce84ddb`.

## Threat Review

- T-04-76: early session branches execute before the authenticated route tree; no translation options/search requests occur while checking, signed out or restricted to password change.
- T-04-77: exact target and order tests plus boundary-aware descendant matching keep active navigation tied to the URL; `/translations-other` never matches.
- No additional security surface outside the planned browser-location/authenticated-route boundary was introduced.

## Known Stubs

None. Unknown detail routes remain subject to the established fallback until Plan 18 registers its explicitly owned implementation.

## Issues Encountered / User Setup

- Corrected the test query-field spelling and the generated deferred-refresh generic type; these did not require production changes.
- Started preview from the frontend working directory after the first invocation used the repository root; final production smoke passed.
- No authentication gate or external setup required.
- Shared requirement readiness: 0/3 ready; later declaring sibling plans are still incomplete, so global requirement completion remains deferred.

## Self-Check: PASSED

All four changed files exist and all seven task commits resolve in git history. Both task acceptance sets, the plan verification commands, and the production smoke passed. Working-tree changes are limited to plan tracking plus pre-existing unrelated artifacts.
