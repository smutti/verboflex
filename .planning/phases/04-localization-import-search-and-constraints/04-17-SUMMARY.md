---
phase: 04-localization-import-search-and-constraints
plan: 17
subsystem: translation-search-ui
tags: [react, tanstack-virtual, accessibility, cursor-pagination, generated-api]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [07, 15, 16]
    provides: exact package approval, generated translation contracts, guarded cursor search
provides:
  - dynamically measured window-virtualized grouped result list with exact six-part rows
  - bounded canonical selector, source-language, and last-known locator summary projection
  - keyboard loading, cursor-error recovery, generation fencing, and literal-content evidence
affects: [translation-workspace-composition, detail-navigation, phase-04-ui-verification]
actuals:
  tokens: 82111
  tasks: 1
  commits: 5
tech-stack:
  added: ["@tanstack/react-virtual@3.14.10", "@tanstack/virtual-core@3.17.8 (transitive)"]
  patterns:
    - useWindowVirtualizer with measured rows, 288px estimate, overscan eight, and useFlushSync false
    - post-keyset bounded locator joins and closed canonical selector metadata
    - generated transport types remain the sole browser wire contract
key-files:
  created:
    - frontend/src/features/translations/TranslationResultList.tsx
    - frontend/src/features/translations/TranslationResultList.test.tsx
  modified:
    - backend/src/verboflex/api/v1/routes/translations.py
    - backend/src/verboflex/schemas/translations.py
    - backend/src/verboflex/services/translation_search.py
    - backend/tests/api/test_openapi_contract.py
    - backend/tests/api/test_translations.py
    - backend/tests/integration/test_translation_search.py
    - frontend/openapi.json
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/src/api/client/index.ts
    - frontend/src/api/client/types.gen.ts
    - frontend/src/features/translations/useTranslationSearch.test.ts
key-decisions:
  - "A search row receives canonical selector_kinds, nullable source_language, and one bounded last-known provenance object from the generated API; value_count never determines scalar versus structured identity."
  - "Render only the window-visible rows plus overscan, using stable opaque IDs and dynamic measurement without a nested scrollbar."
  - "Fence automatic and manual loading by request identity and cursor; only explicit load failures move focus to the owning alert."
requirements-completed: [SRCH-02, SRCH-04, SRCH-05, SRCH-06, SRCH-08]
coverage:
  - id: D1
    description: Canonical grouped row metadata is additive, closed, bounded, and projected without per-row queries.
    verification:
      - kind: integration
        ref: backend/tests/integration/test_translation_search.py#test_search_projects_canonical_row_metadata_without_per_group_queries
        status: pass
      - kind: integration
        ref: backend/tests/api/test_openapi_contract.py#test_translation_schemas_are_closed_bounded_and_non_leaking
        status: pass
    human_judgment: false
  - id: D2
    description: Window virtualization preserves server order, dynamic measurement, stable IDs, bounded DOM, and accessible positions.
    verification:
      - kind: unit
        ref: frontend/src/features/translations/TranslationResultList.test.tsx#TranslationResultList window virtualization
        status: pass
    human_judgment: false
  - id: D3
    description: Six-part rows keep literal content, structured metadata, two-line excerpts, honest statuses, and opaque detail navigation.
    verification:
      - kind: unit
        ref: frontend/src/features/translations/TranslationResultList.test.tsx#TranslationResultList six-part anatomy and safe content
        status: pass
      - kind: automated_ui
        ref: Chromium temporary Vite harness at 320/390/768/1440px with actual component and project CSS
        status: pass
    human_judgment: false
  - id: D4
    description: Automatic and keyboard continuation stop malformed cursor loops while preserving valid rows and fencing superseded callbacks.
    verification:
      - kind: unit
        ref: frontend/src/features/translations/TranslationResultList.test.tsx#TranslationResultList cursor and keyboard loading
        status: pass
    human_judgment: false
  - id: D5
    description: The exact approved TanStack adapter and locked MIT core pass audit, typing, lint, generation integrity, and browser compilation.
    verification:
      - kind: other
        ref: npm audit --audit-level=high; exact lock/version/integrity/license assertions; api:check; typecheck; lint; build
        status: pass
    human_judgment: false
duration: 18min
completed: 2026-09-06
status: complete
---

# Phase 04 Plan 17: Window-Virtualized Translation Results Summary

**Canonical grouped results now render as dynamically measured six-part rows with literal text, honest aggregate status, window scrolling, and guarded keyboard/cursor continuation.**

## Performance

- Started: 2026-09-06T07:46:51Z
- Completed: 2026-09-06T08:05:00Z
- Duration: 18min
- Tasks: 1, including the necessary generated-summary prerequisite repair
- Implementation/test/generated files: 14
- Actual tokens: 82,111, calculated as ceiling of realized implementation diff characters divided by four; generator-owned one-line OpenAPI export accounts for much of this figure.

## Accomplishments

- Added a real `useWindowVirtualizer` list with `estimateSize: () => 288`, `overscan: 8`, `useFlushSync: false`, dynamic `measureElement`, and opaque group keys. It keeps server order and uses the page scrollbar.
- Preserved the exact key, language, source excerpt, translated excerpt, state/length status, and Open details anatomy at mobile and desktop widths. Text remains literal with automatic direction and authoritative language tags; excerpts clamp to two visual lines without a row reveal control.
- Added server-owned selector types, mapping source language, and one bounded leading-member locator to search summaries, so single-value structured groups and deleted provenance are represented correctly.
- Added 27 component tests including real virtualizer measurement, cleanup, bounded rendering, mixed states, partial limits, Unicode/markup, manual keyboard loading, repeated/empty cursor integration, generation races, and user-triggered error focus.

## Task Commits and TDD Gate Compliance

1. `667c58c` — **RED prerequisite:** tests failed on missing `selector_kinds` in both service result and public schema.
2. `b0d4b01` — **GREEN prerequisite:** canonical summary metadata, bounded post-page joins, public response wiring, generated client, and exact API fixture update.
3. `3c3982f` — **RED list:** complete list contract suite failed because the component did not yet exist; no package was installed before this observed failure.
4. `7f07a8a` — **GREEN list:** exact approved adapter installation and window-virtualized rows with passing 27-test evidence.
5. `e14bb5d` — **REFACTOR:** extracted pure row metadata and accessible-label presentation; focused tests, types, and lint remained green.

Both RED commits precede their matching GREEN commits; the optional REFACTOR follows GREEN.

## Verification

- Backend search integration, translation API, and OpenAPI contract: **33 passed**. The new integration assertion proves exactly two search-service database statements and distinguishes single structured values from scalar values, including deleted groups.
- Existing generated-client and cursor-hook suites: **40 passed**.
- Result-list suite: **27 passed** using the actual installed virtualizer with browser geometry/ResizeObserver simulation.
- TypeScript, ESLint, changed-file Prettier, backend Ruff, and strict mypy across **103 source files**: passed.
- `npm --prefix frontend run api:check`: passed with no generated schema/client drift.
- `npm --prefix frontend run build`: passed. Route mounting is owned by Plan 04-23; the actual new component was additionally compiled and exercised through the temporary Vite browser harness.
- Chromium smoke with actual project CSS at **320, 390, 768, 1440 pixels**: no page overflow; exact stacked/six-column section order; computed two-line clamp and 42px excerpt height at 21px line height; 44px links; 11–16 mounted rows from 100 loaded; page scrolling advanced row positions; no browser runtime errors. Temporary screenshots: `/tmp/verboflex-plan17-{320,390,768,1440}.png`. Harness/server/browser closed after verification.
- `npm --prefix frontend audit --audit-level=high`: passed. Exact adapter `3.14.10`, transitive core `3.17.8`, canonical npm resolved URLs, SHA-512 integrity, and **MIT licenses** verified from the lockfile.
- `detect-secrets-hook --no-verify` over authored production surfaces and new list tests: passed.
- Stub scan, tracked-file deletion check, and working-tree ownership check: passed.

## Decisions Made

- `selector_kinds` is a closed one-to-six-member list of actual canonical selector kinds. A one-value plural or JSON path stays structured; no browser inference or detail-fetch fan-out is permitted.
- `source_language` is nullable and comes from the verified current mapping's base language. The browser never assigns the translation locale to source content merely for convenience.
- Summary provenance contains only repository name, configured branch, and path for the leading member. Locator joins occur after the existing 51-row keyset lookahead; cursor/order/filter semantics and the two-statement service cost remain unchanged.
- Errors from superseded callbacks cannot enter another request identity. Automatic loading remains silent; an explicit keyboard/click loading failure focuses its alert.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added the absent canonical result-row metadata contract**

- Found during Task 1 prerequisite inspection.
- The frozen generated search summary lacked selector kinds, source language, and provenance required by the UI-SPEC. Guessing from `value_count` would mislabel single structured values, and assigning target language to source text would be incorrect.
- The orchestrator authorized a narrow additive prerequisite repair within Phase 4. Extended the existing server projection and bounded response schema, wired the existing route, regenerated OpenAPI/client through the pinned generator, and updated exact fixtures/tests. No operation, database table, migration, provider call, or browser DTO was added.
- Files: translation schema/service/route, three backend test owners, generated OpenAPI/client, and cursor-hook test fixture.
- Verification: 33 backend/API/schema tests; 40 adjacent browser tests; two-statement assertion; Ruff/mypy; deterministic `api:check`.
- Commits: `667c58c`, `b0d4b01`.
- Broken-windows register entry **65** records this deviation and is **fixed**.

## API Scope and Gates

The `old-coder-api` skill informed the prerequisite repair. Step 0: existing **internal** HTTP/JSON surface, with backend and browser shipped together; the existing canonical key/language group supports the additional metadata directly. Compatibility was reviewed before modification.

| Gate | Result |
|---|---|
| Boring | PASS — existing GET and established field naming; no new operation |
| Compatibility | PASS — additive response fields only; strict first-party fixtures and generator consumers updated together |
| Authentication | PASS — existing bearer contract and role tests pass |
| Authorization | PASS — existing server-side active-product scope and tests retained |
| Idempotency | N/A — read-only projection |
| Blast radius | Query-cost PASS — two statements, fixed 50-group response, six selector kinds, one bounded locator; existing endpoint-specific rate-limit guarantees were not re-audited in this bounded repair |
| Pagination | PASS — unchanged signed cursor, filters, stable order, and 51-row lookahead |
| Expensive fields | PASS — no per-row requests; locator/repository/mapping joins restricted to bounded page |
| No implementation leakage | PASS — closed safe presentation fields, recursive schema privacy test, no credentials or provider bodies |

## Threat Review

- T-04-49: stable opaque keys, dynamic row observation/cleanup, replacement-generation tests, and callback fencing prevent cross-row content reuse.
- T-04-50: React text nodes only, encoded opaque-ID links, no auto-linking/storage, malicious markup and Unicode tests.
- T-04-51: generated 50-item cursor hook, overscan-eight automatic trigger, duplicate guard, retained valid rows, explicit retry, and bounded DOM evidence.
- T-04-52: canonical selector/state/count/deletion fields produce exact honest labels.
- T-04-SC: Plan 04-07 human approval, exact pin, canonical npm integrity, MIT licenses, and high-severity audit pass.

## Threat Flags

| Flag | File | Description |
|---|---|---|
| threat_flag: response_projection | backend/src/verboflex/schemas/translations.py | Prerequisite added bounded selector/source-language/locator summary fields at the existing authenticated API boundary; reviewed and verified through closed-schema, privacy, authorization, and query-cost tests. |

## Issues Encountered

- First component execution exposed two test-query ambiguities: multiple listitems and duplicated visible/live-region count copy. Queries were made specific; the production behavior was correct.
- The test ResizeObserver fixture required complete typed entry fields, and automatic load dispatch was scheduled in a cancellable microtask to comply with the existing React effects lint rule.
- Two existing moderate `qs` / `typed-rest-client` advisories and the existing Vite chunk-size advisory remain outside this plan; recorded in `deferred-items.md`. Both required audit/build commands pass.

## Known Stubs

None. Nullable source/provenance fields represent missing canonical data explicitly. The list is complete and ready for the planned workspace composition; route wiring remains Plan 04-23's responsibility.

## Authentication Gates / User Setup

None. The exact dependency approval was already recorded in Plan 04-07 and did not require renewed confirmation.

## Integration Handoff

`TranslationResultList` accepts `items`, `nextCursor`, `requestIdentity`, `loadingMore`, `loadMoreError`, `onLoadMore`, `onRetryLoadMore`, and optional `onOpenDetails(translationGroupId)`. Pass the corresponding values from `useTranslationSearch`; use `onOpenDetails` to retain the feature-memory navigation snapshot. Links expose `data-translation-group-id` for focus restoration. The list owns loaded-count/live announcements and continuation errors/actions. Plan 04-23 owns mounting the route and restoring its scroll/focus context.

Shared requirement IDs are not marked globally complete early: the SDK reported **0/5 ready**, because later owning plans are still outstanding.

## Self-Check: PASSED

- Both new component/test files and all 12 modified implementation/generated/test files exist.
- All five implementation commits resolve in repository history in the required order.
- No tracked file was deleted; unrelated `.gsd/`, agent history, milestone lock, research cache, and graph output remained untouched.
- All required verification commands passed, and no required verification was skipped.
