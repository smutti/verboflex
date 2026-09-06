---
phase: 04-localization-import-search-and-constraints
plan: 18
subsystem: translation-detail-and-constraints-ui
tags: [react, accessibility, optimistic-concurrency, playwright, fastapi]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [17, 23, 24, 25]
    provides: virtualized search, in-memory workspace snapshots, generated constraint operations
provides:
  - complete inert grouped detail with structured selectors, provenance, bounded history and read-only review context
  - role-gated versioned maximum-length dialogs with request authority and explicit conflict recovery
  - desktop/mobile search, detail, constraint and Back-navigation acceptance journeys
affects: [phase-04-quality-gate, translation-review, write-back]
tech-stack:
  added: []
  patterns:
    - server-owned explicit rule versions and bounded revision metadata
    - synchronous request guard plus abort/generation/identity checks after every await
    - public virtualizer measurement snapshots retained only in authenticated workspace memory
key-files:
  created:
    - frontend/src/features/translations/TranslationDetailPage.tsx
    - frontend/src/features/translations/translationDetailAuthority.ts
    - frontend/src/features/translations/TranslationDetailPage.test.tsx
    - frontend/src/features/translations/MaximumLengthDialog.tsx
    - frontend/src/features/translations/MaximumLengthDialog.test.tsx
    - frontend/e2e/translations.spec.ts
  modified:
    - backend/src/verboflex/schemas/translations.py
    - backend/src/verboflex/services/translation_search.py
    - backend/src/verboflex/api/v1/routes/translations.py
    - backend/tests/api/test_translations.py
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json
    - frontend/src/api/client/index.ts
    - frontend/src/api/client/types.gen.ts
    - frontend/src/features/translations/TranslationSearchPage.tsx
    - frontend/src/features/translations/TranslationResultList.tsx
    - frontend/src/features/translations/TranslationResultList.test.tsx
    - frontend/src/features/translations/useTranslationSearch.ts
    - frontend/src/features/translations/useTranslationSearch.test.ts
    - frontend/src/router.tsx
    - frontend/src/router.test.tsx
key-decisions:
  - "Project existing persisted explicit rule/version, canonical selector fields and latest 50 revision metadata through the existing authorized detail endpoint; never infer frontend authority."
  - "A successful constraint write followed by failed detail refresh is reported honestly as saved/removed; only projection reload is offered, never a duplicate write."
  - "Invalidate cached result authority while retaining query, filters and navigation in workspace memory; retain measured virtual rows for unchanged Back navigation."
requirements-completed: [SRCH-06, SRCH-07, CONS-01, CONS-02, CONS-03, CONS-04, CONS-05]
actuals:
  tokens: 99252
  tasks: 3
  commits: 11
duration: 29min
completed: 2026-09-06
status: complete
---

# Phase 04 Plan 18: Grouped Detail and Versioned Maximum Dialogs Summary

Complete inert translation detail now exposes authoritative rules, structured selectors and bounded history; role-gated dialogs safely create, edit and remove limits without losing search context or imported text.

## Performance

- Started: 2026-09-06T08:53:45Z
- Completed: 2026-09-06T09:22:00Z
- Tasks: 3; implementation/test files: 21.
- Actual tokens use realized diff characters / 4 (397005 / 4 rounded up), including official regenerated schema/client artifacts, not harness usage.

## Task Commits

1. Task 1 prerequisite RED: `b64b8c1` — require authoritative detail rules and selectors.
2. Task 1 prerequisite GREEN: `62e2ab3` — project explicit constraint authority, selectors and bounded history.
3. Task 1 UI RED: `4585410` — specify inert grouped detail and authenticated routes.
4. Task 1 UI GREEN: `1769450` — render complete detail, provenance and history.
5. Task 2 dialog RED: `495ffff` — specify concurrency, validation and recovery.
6. Task 2 integration RED: `a002602` — retain navigation while invalidating search authority.
7. Task 2 GREEN: `d44142d` — versioned race-safe maximum dialogs.
8. Task 3 browser RED: `d31c5da` — browser journeys expose measured-scroll restoration drift.
9. Task 3 GREEN: `ee53881` — preserve measured search navigation and pass browser journeys.

## Verification

- `npm --prefix frontend test -- --run src/features/translations src/router.test.tsx`: **162 passed**, 8 suites. Includes 27 dialog, 13 detail, 36 router and 23 search-hook tests plus filter/list/search-page suites.
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:4178 npm --prefix frontend run e2e -- translations.spec.ts`: **13 passed** in production preview, desktop 1440×900 and mobile 320×800, reduced motion.
- `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint`, `npm --prefix frontend run build`, `npm --prefix frontend run api:check`: **passed**. Build retains the pre-existing large-chunk advisory.
- Backend `uv run pytest tests/api/test_translations.py tests/api/test_openapi_contract.py tests/integration/test_translation_search.py -q`: **35 passed**.
- Focused Ruff for changed Python source/tests and mypy for the three changed source files: **passed**.
- `git diff --check`: passed; changed production files contain no TODO/FIXME, unsafe HTML rendering or unwired feature stubs.

### Acceptance coverage

| Contract | Evidence |
| --- | --- |
| SRCH-06: full scalar/plural/array/numerus/length/JSON selectors, inert Unicode text, missing/deleted/partial metadata, provenance/history | TranslationDetailPage.test.tsx; bounded-history API test; both viewport journeys |
| SRCH-07: current read-only review state and exact Phase 4 context | Detail/router suites and all eight direct-role browser cases |
| CONS-01/02: inclusive bounds and four-role authorization affordances | MaximumLengthDialog.test.tsx; generated versioned API; direct-role browser cases |
| CONS-03/04/05: inheritance, authoritative count/status, over-limit Draft retention | Detail fixtures, save/edit/remove browser journeys, backend projection tests |
| Pending ref guard, duplicate dispatch, abort, supersession, stale callbacks, explicit conflict replacement, error/trigger focus | 27 dialog cases plus browser pending/conflict/focus assertions |
| Query/filter/cursor retry and Back row/scroll restoration, content-free storage | Both search browser journeys and search/list suites |
| Eight UI consideration categories, 50 applicable instances and three open axes | Named inventory in translations.spec.ts with companion owner suites from Plans 09, 17, 22–24 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing critical functionality] Bounded server detail projection prerequisite**
- Existing generated detail omitted base language, explicit maximum/version, structured selector fields and revision history required by the approved UI.
- Added these from existing persisted authority through the existing scoped detail query and closed response schema. History reads at most 51 records per value, returns latest 50 and an explicit remainder flag. No new endpoint, table, role or mutation was introduced.
- Tests failed on missing authority first, then passed after implementation and official client regeneration (`b64b8c1`, `62e2ab3`).
- The old-coder-api skill and breaking-change reference guided closed additive compatibility, non-enumerating errors, bounded projection and generated-client verification. WINDOW 67 is fixed.

**2. [Rule 1 — Bug] Virtualized Back scroll drift**
- Browser RED found correct focus but scroll drift of 1236px desktop/768px mobile because dynamic measured rows were lost on route unmount.
- Used public `takeSnapshot`/`initialMeasurementsCache` with viewport scoping; wait for initial results before restoring scroll. Content and measurements remain workspace-memory-only. All 13 browser cases pass (`ee53881`). WINDOW 66 is fixed.

**3. [Rule 2 — Missing critical functionality] Honest post-write refresh failure recovery**
- A completed write followed by a failed detail read must not be reported as a failed mutation or permit duplicate submission. Dialog keeps committed authority locked, states that the maximum was saved/removed, and allows only a fresh projection reload. Covered by focused dialog tests (`d44142d`).

## Decisions and Scope

- Translation text, review, comments and provider/write-back mutation remain absent. The exact `Pending change: None` and `Comments: No comments yet` fields are intentional Phase 4 read-only contract values, not unwired feature stubs.
- Missing optional metadata is visible; malformed mandatory authority is a bounded error. Imported content uses text nodes, never HTML execution or content-bearing storage.
- No new dependencies. Official React effect cleanup, Radix dialog callback and TanStack virtualizer snapshot documentation informed lifecycle/focus/scroll integration.
- Shared requirements remain unmarked globally: the ready-ids gate returned **0/7**, because later plans still own their phase-wide acceptance.

## Deferred Issues

The existing 12 backend-wide parser mypy errors are already recorded by Plan 04-08 in `deferred-items.md`; Plan 19 owns cleanup. This plan's three changed Python files pass mypy. No duplicate ledger entry was added.

## Threat Review

Existing detail API→DOM and role-aware mutation boundaries were reviewed against T-04-53 through T-04-56. Added projection is bounded, scoped and inert; mutation role enforcement remains backend-owned; no new endpoint/auth/file-access surface was introduced.

## Self-Check: PASSED

All six created feature/test files exist. All nine RED/GREEN task commits exist in order. No tracked-file deletions occurred. Focused backend/frontend, generated-client, production build and dedicated browser verification passed.
