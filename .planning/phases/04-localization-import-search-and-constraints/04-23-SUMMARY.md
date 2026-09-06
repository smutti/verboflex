---
phase: 04-localization-import-search-and-constraints
plan: 23
subsystem: translation-search-workspace
tags: [react, typescript, vitest, playwright, generated-api, principal-memory]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [16, 17]
    provides: Validated search/preferences controller and window-virtualized result list
provides:
  - Exact five-filter responsive translation search page
  - Authorized product-scoped language options and generated client contract
  - Principal-lifetime memory with Back scroll/focus restoration and token-refresh reauthorization
affects: [translation-route-integration, translation-detail, phase-04-browser-verification]
actuals:
  tokens: 76423
  tasks: 2
  commits: 5
tech-stack:
  added: []
  patterns:
    - Resolve global and selected-product authorized options before mounting the search controller
    - Key workspace memory by principal and discard cached pages on access-token rotation
    - Reuse generated transport, preference codec, cursor controller, and one virtual result list
key-files:
  created:
    - frontend/src/features/translations/TranslationFilters.tsx
    - frontend/src/features/translations/TranslationFilters.test.tsx
    - frontend/src/features/translations/TranslationSearchPage.tsx
    - frontend/src/features/translations/TranslationSearchPage.test.tsx
    - frontend/src/features/translations/TranslationsWorkspace.tsx
  modified:
    - backend/src/verboflex/api/v1/routes/translations.py
    - backend/src/verboflex/services/translation_search.py
    - backend/tests/api/test_translations.py
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json
    - frontend/src/api/client/types.gen.ts
key-decisions:
  - "Resolve live global product choices and selected-product language choices before mounting search; a changed product clears an unavailable language before any result request."
  - "Workspace memory belongs to the authenticated principal lifetime; token rotation preserves query/filter memory but reauthorizes options and reloads result pages."
  - "Only the existing codec persists version/productId/language; repository content, queries, other filters, cursors, and tokens remain memory-only."
requirements-completed: [SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-08]
coverage:
  - id: D1
    description: Five exact responsive filters expose approved labels, options, defaults, keyboard interaction, and immediate changes.
    verification:
      - kind: unit
        ref: frontend/src/features/translations/TranslationFilters.test.tsx
        status: pass
      - kind: automated_ui
        ref: Chromium actual-component smoke at 320, 768, and 1440 pixels
        status: pass
    human_judgment: false
  - id: D2
    description: Authorized options precede queries and product changes revalidate language without leaking inaccessible scope.
    verification:
      - kind: unit
        ref: frontend/src/features/translations/TranslationSearchPage.test.tsx
        status: pass
      - kind: integration
        ref: backend/tests/api/test_translations.py#test_options_scope_languages_without_narrowing_products_or_enumerating_missing_products
        status: pass
    human_judgment: false
  - id: D3
    description: Literal 300ms typing, immediate Enter/clear/filter actions, request-race rejection, loading/error/empty states, and one cursor list compose deterministically.
    verification:
      - kind: unit
        ref: frontend/src/features/translations/TranslationSearchPage.test.tsx
        status: pass
      - kind: unit
        ref: frontend/src/features/translations/useTranslationSearch.test.ts
        status: pass
    human_judgment: false
  - id: D4
    description: Back restores query, pages, window scroll and invoking link focus; principal changes discard memory and token rotation reauthorizes without losing input.
    verification:
      - kind: unit
        ref: frontend/src/features/translations/TranslationSearchPage.test.tsx
        status: pass
      - kind: automated_ui
        ref: Chromium actual workspace search-to-detail-to-search smoke
        status: pass
    human_judgment: false
duration: 18min
completed: 2026-09-06
status: complete
---

# Phase 04 Plan 23: Translation Search Workspace Summary

Translation search now composes exact filters, live product-language authorization, generation-safe cursor results, and principal-lifetime Back navigation memory.

## Performance

- Started: 2026-09-06T08:24:00Z (approximate executor start).
- Completed: 2026-09-06T08:42:16Z.
- Tasks: 2.
- Changed implementation/test/generated files: 11.
- Actual tokens: 76,423, ceiling of 305,689 realized diff characters divided by four. The generated single-line OpenAPI export dominates this metric; this is not harness token usage.

## Accomplishments

- Implemented Product, Language, Approval state, Length status, and Deleted status in the approved order using project-owned shadcn Select controls, explicit All choices, 44px targets, and one/two/five-column responsive layout.
- Resolved current authorized products and selected-product languages before the first query, revalidated remembered choices, and held product changes behind language authorization with cancellation of the prior search controller.
- Composed the existing hook without duplicating debounce/cursor authority. Typing waits exactly 300ms; Enter, clearing the final character, Clear search, explicit filters, and Clear filters apply immediately. Clear filters resets query and all five filters in one result request.
- Added five loading skeleton rows, safe search/options retry, distinct default-empty and filtered-empty copy with active criteria, and one existing virtual list with all loaded groups and continuation callbacks.
- Kept snapshots in the principal-keyed feature workspace. Back restores loaded pages, query, filters, window scroll, and the invoking opaque detail link. Token refresh preserves query/filter memory but invalidates cached pages and reauthorizes both options and results. Browser storage failures leave the page usable.

## Task Commits and TDD Gate Compliance

1. `569e1d2` — Task 1 RED: exact filters and product-scoped language options. The component suite failed on the absent component; the API test failed because scoped languages still contained both products' languages.
2. `810afb6` — Task 1 GREEN: exact five filters, optional product language scope, generated transport and precise OpenAPI contract.
3. `a8673d0` — Task 2 RED: full page composition contract failed on the absent page/workspace implementation.
4. `061bb8d` — Supplemental RED: a concrete token-rotation test failed because query memory reset to empty; blocked-browser-storage coverage also added.
5. `dff3bbf` — Task 2 GREEN: composed page/workspace, continuous in-memory snapshots, principal remounting and token-refresh result invalidation.

Both tasks have observed RED before GREEN. No separate REFACTOR was necessary: filter mapping is owned by one component, snapshot lifetime by one workspace, and network/debounce authority remains entirely in Plan 16's existing controller.

## Verification

- Exact page/filter suites: **26 passed** (18 page cases, eight filter cases).
- Adjacent hook, preference, actual virtual-list, and generated-client suites: **77 passed** across four files.
- Translation API and OpenAPI contract: **27 passed**, including optional scope, unchanged omitted-parameter behavior, all-role authentication, active-product ordering, and identical missing/inactive-product language results.
- TypeScript and ESLint with zero tolerated warnings: passed.
- Ruff over four changed backend files and strict mypy over the two changed backend source files: passed.
- `npm --prefix frontend run api:check`: passed, regenerated schemas/client have no drift.
- `npm --prefix frontend run build`: passed, 1,978 modules transformed. Existing large-chunk advisory remains unchanged.
- Chromium smoke compiled and rendered the actual page, workspace, filters and real virtualizer in React Strict Mode with generated-network response fixtures. At **320/768/1440px**, it found exactly five filters, **one/two/five computed filter columns**, no horizontal page overflow, and only **9/11/13 mounted rows from 50 loaded**. Search → detail → Back restored the literal query with **zero browser runtime errors**.
- Smoke screenshots inspected: `/tmp/verboflex-plan23-320.png`, `/tmp/verboflex-plan23-768.png`, `/tmp/verboflex-plan23-1440.png`. Temporary repository harness files were removed and the owned Vite server stopped.
- `git diff --check`, tracked deletion check, stub scan, and working-tree ownership review passed. Unrelated runtime/research artifacts were preserved.
- Official React effect, React Router Outlet, and Radix Select references were consulted after Context7 MCP and CLI were unavailable: https://react.dev/reference/react/useEffect, https://reactrouter.com/api/components/Outlet, https://www.radix-ui.com/primitives/docs/components/select.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added product-scoped language authorization to the existing options read**

- Found during Task 1/Task 2 integration.
- The generated `listTranslationOptions` operation had `query: never`; global language options could not prove language membership for a selected product.
- Added optional UUID `product_id`, narrowing only language choices inside the existing authorized active-product SQL. The response retains every authorized product. Omitted scope preserves prior behavior; inactive and unknown UUIDs both return an empty language collection. No new endpoint or mutation was added.
- Updated API/OpenAPI tests and regenerated the browser contract; this is covered by RED `569e1d2` and GREEN `810afb6`.
- The old-coder-api skill and its breaking-changes reference guided the additive compatibility choice. Internal existing HTTP surface, product/translation resource model already sufficient. Boring, compatibility, authentication, authorization, bounded collection, unchanged field cost, and no implementation leakage gates pass on code/test evidence. Idempotency is not applicable to this GET. Wider rate-limit/incident controls were not changed or independently audited; this adds a predicate to the existing one-query bounded options read.

## Threat Review

- T-04-73: principal-scoped codec, live-option intersection, snapshot validation by the existing hook, malformed preference tests, explicit memory-before-preference precedence.
- T-04-74: all option reads use the authenticated generated endpoint; product-language scope stays inside the server's authorized active-product query and preserves non-enumeration.
- T-04-75: existing immediate abort/generation guards, 300ms free-text dispatch, bounded cursor pages, unmount cancellation during product changes, stale response tests.
- No dependency, new endpoint, provider action, filesystem trust boundary, or schema migration was introduced.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: query_scope | backend/src/verboflex/api/v1/routes/translations.py | Optional product UUID crosses the existing authenticated options boundary; exact UUID parsing and authorized SQL scope are covered by API/OpenAPI tests. |

## Issues Encountered

- The multi-value backend fixture initially changed only its leading language; updated all members of its logical key before asserting product-language membership.
- JSDOM needed the same pointer-capture/scroll shims used by existing Radix component tests. A test-only unsupported `exact` option was removed for TypeScript.
- The temporary browser command had a syntax error before execution; the corrected standalone smoke script then passed. No application defect or skipped verification resulted.
- Existing build chunk-size advisory remains out of scope and already documented by preceding plans.

## Known Stubs

None. Empty collections, null selections, loading-only disabled callbacks, and the Input placeholder are intentional control states, not missing feature implementations. Production route/shell registration is explicitly owned by Plan 04-24.

## Authentication Gates / User Setup

None.

## Integration Handoff

- Mount `TranslationsWorkspace({ accessToken, principal })` as the parent translation route. It renders an `Outlet`; its index child is `TranslationSearchPage` with no props. Plan 04-24 owns router and shell registration, as specified by that plan.
- `TranslationsWorkspaceContext` exposes `accessToken`, `principal`, `snapshot`, and `setSnapshot`. Detail may call `setSnapshot(null)` after a successful constraint change to invalidate cached search pages; ordinary detail navigation preserves the saved snapshot.
- The search page mounts one `TranslationResultList` using the exact Plan 17 props. `onOpenDetails` captures scroll/group identity; restoration finds the actual link via its existing `data-translation-group-id` and uses `focus({ preventScroll: true })` after virtualization mounts it.
- Shared requirements were checked with `requirements.ready-ids`: **0/6 ready**, because later sibling plans still own portions. No premature global completion flags are applied.

## Self-Check: PASSED

All five new frontend files and all six modified backend/generated files exist. All five task commits resolve in history. Required focused/static/build/browser checks pass. The working tree contains only the pre-existing untracked runtime/research artifacts outside the summary/tracking closeout.
