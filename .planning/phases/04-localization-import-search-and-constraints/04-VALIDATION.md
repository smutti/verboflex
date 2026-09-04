---
phase: 04
slug: localization-import-search-and-constraints
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-04
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Backend: pytest 9.1.1 + Hypothesis 6.165.10; frontend: Vitest 4.1.11 + Testing Library + fast-check 4.9.0; E2E: Playwright 1.62.1 |
| **Config file** | `backend/pyproject.toml`, `frontend/vite.config.ts`, `frontend/playwright.config.ts` |
| **Quick run command** | `uv run --project backend pytest backend/tests/unit/localization -q` or `npm --prefix frontend test -- --run src/features/translations` for the touched application |
| **Full suite command** | `uv run --project backend pytest && npm --prefix frontend run test:coverage && npm --prefix frontend run api:check && npm --prefix frontend run build` |
| **Estimated runtime** | Targeted: under 120 seconds; full suite: approximately 5–10 minutes |

---

## Sampling Rate

- **After every task commit:** Run the row-specific automated command below.
- **After every plan wave:** Run the complete suite for every application touched in the wave.
- **At the parser checkpoint:** All parser, golden-corpus, property, coverage, security, and backend smoke checks must pass before import persistence starts.
- **Before `$gsd-verify-work`:** Backend and frontend full suites, generated-client drift, Playwright, and Docker Compose smoke must be green.
- **Max feedback latency:** 120 seconds for the per-task targeted command.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | FMT-01, FMT-07 | T-04-01–T-04-05 | Canonical contract plus Android scalar tracer proves one registry path with safe failure | TDD tracer | `uv run --project backend pytest backend/tests/unit/localization/importing/test_contracts.py backend/tests/unit/localization/importing/test_android_xml.py -q` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | FMT-01, FMT-06 | T-04-06–T-04-09 | Android plural/array/XML input is faithful, bounded, and atomic | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_android_xml.py -q` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | FMT-02, FMT-06 | T-04-10–T-04-12 | Qt numerus/variant/XML input is faithful, bounded, and atomic | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_qt_ts.py -q` | ❌ W0 | ⬜ pending |
| 04-04-01 | 04 | 2 | FMT-03, FMT-06 | T-04-13–T-04-15 | JSON leaves are deterministic and reject duplicates/depth/size overflow | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_json.py -q` | ❌ W0 | ⬜ pending |
| 04-05-01 | 05 | 2 | FMT-04, FMT-06 | T-04-16–T-04-18 | iOS lexical parsing preserves escapes/encoding and rejects invalid input atomically | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_ios_strings.py -q` | ❌ W0 | ⬜ pending |
| 04-06-01 | 06 | 3 | FMT-01, FMT-02, FMT-03, FMT-04, FMT-06 | T-04-01–T-04-18 | Registry conformance and direct/separate joins cannot manufacture or partially merge data | unit + property | `uv run --project backend pytest backend/tests/unit/localization/importing/test_conformance.py -q` | ❌ W0 | ⬜ pending |
| 04-07-01 | 07 | 4 | FMT-01, FMT-02, FMT-03, FMT-04, FMT-06, CONS-03, SRCH-08 | T-04-19, T-04-20, T-04-SC | Parser evidence and both package identities are blocking before persistence/install | checkpoint | `uv run --project backend pytest backend/tests/unit/localization/importing -q` | ❌ W0 | ⬜ pending |
| 04-08-01 | 08 | 5 | FMT-07, FMT-08, CONS-04 | T-04-21–T-04-23 | Base-language authority is persisted and confirmation-bound | migration + API | `uv run --project backend pytest backend/tests/integration/test_migrations.py backend/tests/integration/test_preview_jobs.py -q -k 'base_language or preview'` | ❌ W0 | ⬜ pending |
| 04-09-01 | 09 | 6 | FMT-07, FMT-08 | T-04-24–T-04-26 | Generated contract and Preview selection prevent publication without exact base authority | contract + component | `npm --prefix frontend run api:check && npm --prefix frontend test -- --run src/features/admin/previews/ProductPreviewPage.test.tsx` | ❌ W0 | ⬜ pending |
| 04-10-01 | 10 | 6 | FMT-07, FMT-08, CONS-01..04 | T-04-27–T-04-30 | Stable identity, ownership, staging, history, and constraint checks hold in PostgreSQL | migration + model | `uv run --project backend pytest backend/tests/integration/test_migrations.py backend/tests/unit/localization/importing/test_contracts.py -q` | ❌ W0 | ⬜ pending |
| 04-11-01 | 11 | 7 | FMT-07, FMT-08, CONS-04 | T-04-31–T-04-34 | Stale/superseded/partial imports cannot activate; refresh truth table preserves context | integration | `uv run --project backend pytest backend/tests/integration/test_translation_import_activation.py -q` | ❌ W0 | ⬜ pending |
| 04-12-01 | 12 | 8 | FMT-06, FMT-08 | T-04-35–T-04-37 | Admin outcome projection is bounded/redacted and retained-dataset recovery is explicit | API + component | `uv run --project backend pytest backend/tests/api/test_admin_mappings.py -q && npm --prefix frontend test -- --run src/features/admin/imports/PublishedMappingImports.test.tsx` | ❌ W0 | ⬜ pending |
| 04-13-01 | 13 | 8 | SRCH-01..SRCH-08 | T-04-38–T-04-41 | Literal search/detail is scoped; keyset cursors bind filters/dataset/order and do not enumerate | migration + API + integration | `uv run --project backend pytest backend/tests/integration/test_translation_search.py backend/tests/api/test_translations.py -q` | ❌ W0 | ⬜ pending |
| 04-14-01 | 14 | 9 | SRCH-05, SRCH-07, CONS-01..05 | T-04-42–T-04-44, T-04-SC | One grapheme authority and versioned role-gated mutations recompute projections atomically | unit + API + integration | `uv run --project backend pytest backend/tests/unit/localization/test_grapheme_count.py backend/tests/integration/test_translation_constraints.py backend/tests/api/test_translation_constraints.py -q` | ❌ W0 | ⬜ pending |
| 04-15-01 | 15 | 10 | SRCH-01..08, CONS-01..05 | T-04-38–T-04-44 | OpenAPI operation inventory and generated TypeScript client are exact and drift-free | contract | `uv run --project backend pytest backend/tests/api/test_openapi_contract.py -q && npm --prefix frontend run api:check` | ❌ W0 | ⬜ pending |
| 04-16-01 | 16 | 11 | SRCH-01..05, SRCH-08 | T-04-45–T-04-48 | Preferences are allowlisted/principal-scoped and infinite search rejects stale generations | component/property | `npm --prefix frontend test -- --run src/features/translations/translationPreferences.test.ts src/features/translations/useTranslationSearch.test.ts` | ❌ W0 | ⬜ pending |
| 04-17-01 | 17 | 12 | SRCH-01..SRCH-08 | T-04-49–T-04-52, T-04-SC | Virtual semantic list renders hostile text inertly and routes all authenticated roles | component + accessibility | `npm --prefix frontend test -- --run src/features/translations/TranslationResultList.test.tsx src/features/translations/TranslationSearchPage.test.tsx src/router.test.tsx` | ❌ W0 | ⬜ pending |
| 04-18-01 | 18 | 13 | SRCH-06, SRCH-07, CONS-01..05 | T-04-53–T-04-56 | Complete detail is non-enumerating and constraint dialogs reflect server role/version authority | component + E2E | `npm --prefix frontend test -- --run src/features/translations/TranslationDetailPage.test.tsx src/features/translations/MaximumLengthDialog.test.tsx` | ❌ W0 | ⬜ pending |
| 04-19-01 | 19 | 14 | All Phase 4 requirements | T-04-57–T-04-60 | Exact source equality, static boundaries, reversible mutants, gauntlet, and bounded smoke block drift | architecture + adversarial | `uv run --project backend pytest backend/tests/architecture/test_phase4_scope.py -q && uv run --project backend python tools/verify_translation_mutants.py --self-test` | ❌ W0 | ⬜ pending |
| 04-20-01 | 20 | 15 | All Phase 4 requirements | T-04-01–T-04-64, T-04-SC | Fresh code/security review and independent goal verifier cannot pass stale or incomplete evidence | phase gate | `bash tools/phase4_gauntlet.sh && bash tools/phase4_smoke.sh` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/fixtures/localization/` — immutable source bytes and hand-authored canonical manifests for every supported format and boundary category.
- [ ] `backend/tests/unit/localization/importing/test_contracts.py` — canonical result, selector, issue, and limit contract tests.
- [ ] `backend/tests/unit/localization/importing/test_android_xml.py`, `test_qt_ts.py`, `test_json.py`, `test_ios_strings.py`, `test_conformance.py` — adapter golden/property suites.
- [ ] `backend/tests/integration/test_translation_import_activation.py` — PostgreSQL activation, rewrite-confirmation, refresh, and concurrency fixtures.
- [ ] `backend/tests/integration/test_translation_search.py` and `test_translation_constraints.py` — indexed search and recomputation integration suites with `pg_trgm` enabled.
- [ ] `backend/tests/api/test_translations.py` and `test_translation_constraints.py` — authenticated API and OpenAPI contract tests.
- [ ] `frontend/src/features/translations/` component tests and `frontend/e2e/translations.spec.ts` — route, virtual list, detail, constraint, navigation-restoration, and stale-request coverage.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Bitbucket import smoke | FMT-07, FMT-08 | Requires workspace credentials and a disposable repository/branch | Import a mapped disposable branch, verify the active dataset and provenance, then change one external value and confirm only the affected translation returns to Draft. |
| Responsive and assistive-technology review | SRCH-06, SRCH-07, SRCH-08, CONS-05 | Final visual/focus behavior benefits from a real browser and screen-reader pass | Exercise desktop and narrow widths, keyboard navigation, focus restoration after back navigation, virtualized-row announcements, and all constraint dialog error states. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verification or explicit Wave 0 dependencies.
- [ ] Sampling continuity: no three consecutive tasks without automated verification.
- [ ] Wave 0 covers all missing references.
- [ ] No watch-mode flags are used.
- [ ] Per-task feedback latency remains below 120 seconds.
- [ ] Parser checkpoint passes before persistence/search execution begins.
- [ ] `nyquist_compliant: true` is set in frontmatter after validation.

**Approval:** planned and Nyquist-compliant; Wave 0 artifacts are created test-first by their owning plans and remain pending execution.
