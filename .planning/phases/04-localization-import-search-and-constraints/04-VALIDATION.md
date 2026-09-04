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
- **At final phase gate Plan 04-20:** The fail-closed closeout validator requires fresh gauntlet/smoke evidence, zero unresolved Critical/high review findings, exact `SECURED`, exact verification frontmatter `status: passed`, manifest equality, and one matching post-gauntlet source digest.
- **Before `$gsd-verify-work`:** Backend and frontend full suites, generated-client drift, Playwright, and Docker Compose smoke must be green.
- **Max feedback latency:** 120 seconds for the per-task targeted command.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | FMT-01, FMT-07 | T-04-01–T-04-03 | Canonical contract plus Android scalar tracer proves one registry path with safe failure | TDD tracer | `uv run --project backend pytest backend/tests/unit/localization/importing/test_contracts.py backend/tests/unit/localization/importing/test_android_xml.py -q` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | FMT-01, FMT-06 | T-04-04–T-04-06 | Exact Android allowlist, plural/array/XML fidelity, resource bounds, and atomic rejection | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_android_xml.py -q` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | FMT-02, FMT-06 | T-04-07–T-04-09 | Exact Qt allowlist, numerus/variant fidelity, resource bounds, and atomic rejection | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_qt_ts.py -q` | ❌ W0 | ⬜ pending |
| 04-04-01 | 04 | 2 | FMT-03, FMT-06 | T-04-10–T-04-12 | JSON leaves are deterministic and reject duplicates/depth/size overflow | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_json.py -q` | ❌ W0 | ⬜ pending |
| 04-05-01 | 05 | 2 | FMT-04, FMT-06 | T-04-13–T-04-15 | iOS lexical parsing preserves escapes/encoding and rejects invalid input atomically | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_ios_strings.py -q` | ❌ W0 | ⬜ pending |
| 04-06-01 | 06 | 3 | FMT-01, FMT-02, FMT-03, FMT-04, FMT-06 | T-04-16–T-04-18 | Registry conformance exact supported/rejected equality and direct/separate join safety | unit + property | `uv run --project backend pytest backend/tests/unit/localization/importing/test_conformance.py -q` | ❌ W0 | ⬜ pending |
| 04-07-01 | 07 | 4 | FMT-01, FMT-02, FMT-03, FMT-04, FMT-06, CONS-03, SRCH-08 | T-04-19, T-04-20, T-04-SC | Coverage, static checks, audit/license, manifest equality, backend/worker smoke, and package approvals block persistence/install | checkpoint | `bash tools/phase4_parser_checkpoint.sh --container-smoke && bash tools/phase4_parser_checkpoint.sh --verify-evidence` | ❌ W0 | ⬜ pending |
| 04-08-01 | 08 | 5 | FMT-07, FMT-08, CONS-04 | T-04-21–T-04-23 | Base-language authority persists through confirmation, candidate clone, and publication | migration + API | `uv run --project backend pytest backend/tests/integration/test_migrations.py backend/tests/integration/test_preview_jobs.py backend/tests/integration/test_product_publication.py backend/tests/api/test_admin_previews.py -q -k base_language` | ❌ W0 | ⬜ pending |
| 04-14-01 | 14 | 5 | CONS-03, CONS-04 | T-04-42, T-04-SC | Approved exact-pinned UAX #29 dependency provides one versioned grapheme authority | unit | `uv run --project backend pytest backend/tests/unit/localization/test_grapheme_count.py -q && uv run --project backend pip check` | ❌ W0 | ⬜ pending |
| 04-09-01 | 09 | 6 | FMT-07, FMT-08 | T-04-24–T-04-26 | RED-first generated contract and Preview selection prevent publication without exact base authority | contract + component | `npm --prefix frontend run api:check && npm --prefix frontend test -- --run src/features/admin/previews/ProductPreviewPage.test.tsx` | ❌ W0 | ⬜ pending |
| 04-10-01 | 10 | 6 | FMT-07, FMT-08, CONS-01..04 | T-04-27–T-04-30 | Stable identity, ownership, staging, history, and constraint checks hold in PostgreSQL | migration + model | `uv run --project backend pytest backend/tests/integration/test_migrations.py backend/tests/unit/localization/importing/test_contracts.py -q` | ❌ W0 | ⬜ pending |
| 04-11-01 | 11 | 7 | FMT-07, FMT-08, CONS-04 | T-04-31–T-04-34 | Stale/superseded/partial imports cannot activate; refresh truth table preserves context | integration | `uv run --project backend pytest backend/tests/integration/test_translation_import_activation.py -q` | ❌ W0 | ⬜ pending |
| 04-12-01 | 12 | 8 | FMT-06, FMT-08 | T-04-35–T-04-37 | Admin parser outcome API is bounded, redacted, and retained-dataset aware | API | `uv run --project backend pytest backend/tests/api/test_admin_mappings.py backend/tests/api/test_import_jobs.py -q -k 'parser or issue or dataset'` | ❌ W0 | ⬜ pending |
| 04-13-01 | 13 | 8 | SRCH-01..SRCH-08 | T-04-38–T-04-41 | Literal search/detail is scoped; indexes roll back; cursors bind filters/dataset/order | migration + API + integration | `uv run --project backend pytest backend/tests/integration/test_migrations.py backend/tests/integration/test_translation_search.py backend/tests/api/test_translations.py -q` | ❌ W0 | ⬜ pending |
| 04-21-01 | 21 | 8 | SRCH-05, CONS-01..CONS-04 | T-04-43–T-04-44 | Dynamic inheritance, exact mutation concurrency, and every recomputation boundary share one transaction-safe service | integration | `uv run --project backend pytest backend/tests/integration/test_translation_constraints.py backend/tests/integration/test_translation_import_activation.py -q -k 'constraint or recompute or grapheme'` | ❌ W0 | ⬜ pending |
| 04-25-01 | 25 | 9 | SRCH-05, SRCH-07, CONS-01, CONS-02, CONS-05 | T-04-68–T-04-69 | Only strict role-gated maximum-length PUT/DELETE routes mutate synchronously | API | `uv run --project backend pytest backend/tests/api/test_translation_constraints.py backend/tests/api/test_translations.py -q` | ❌ W0 | ⬜ pending |
| 04-15-01 | 15 | 10 | SRCH-01..08, CONS-01..05 | T-04-45–T-04-47 | Final OpenAPI inventory and RED-first generated TypeScript client are exact and drift-free | contract | `uv run --project backend pytest backend/tests/api/test_openapi_contract.py -q && npm --prefix frontend run api:check && npm --prefix frontend test -- --run src/api/admin-client-contract.test.ts` | ❌ W0 | ⬜ pending |
| 04-16-01 | 16 | 11 | SRCH-01..05, SRCH-08 | T-04-48, T-04-65–T-04-67 | Preferences are allowlisted/principal-scoped and infinite search rejects stale generations | component/property | `npm --prefix frontend test -- --run src/features/translations/translationPreferences.test.ts src/features/translations/useTranslationSearch.test.ts` | ❌ W0 | ⬜ pending |
| 04-17-01 | 17 | 11 | SRCH-02, SRCH-04..06, SRCH-08 | T-04-49–T-04-52, T-04-SC | Exact window virtualizer and six-part rows preserve hostile content and bounded DOM | component + accessibility | `npm --prefix frontend test -- --run src/features/translations/TranslationResultList.test.tsx && npm --prefix frontend run typecheck` | ❌ W0 | ⬜ pending |
| 04-22-01 | 22 | 11 | FMT-06, FMT-08 | T-04-70–T-04-72 | Published mapping UI renders exact bounded parser failures and retained-baseline retry state | component | `npm --prefix frontend test -- --run src/features/admin/imports/PublishedMappingImports.test.tsx && npm --prefix frontend run typecheck` | ❌ W0 | ⬜ pending |
| 04-23-01 | 23 | 12 | SRCH-01..SRCH-05, SRCH-08 | T-04-73–T-04-75 | Exact five-filter search page composes memory/preferences, request races, and one virtual list | component | `npm --prefix frontend test -- --run src/features/translations/TranslationFilters.test.tsx src/features/translations/TranslationSearchPage.test.tsx && npm --prefix frontend run typecheck` | ❌ W0 | ⬜ pending |
| 04-24-01 | 24 | 13 | SRCH-01, SRCH-06, SRCH-08 | T-04-76–T-04-77 | Protected search route and Translations navigation are direct-link and keyboard safe | component | `npm --prefix frontend test -- --run src/router.test.tsx src/components/layout/AppShell.test.tsx && npm --prefix frontend run typecheck` | ❌ W0 | ⬜ pending |
| 04-18-01 | 18 | 14 | SRCH-06, SRCH-07, CONS-01..05 | T-04-53–T-04-56 | Direct/detail routing is non-enumerating and dialogs reflect server role/version authority | component + E2E | `npm --prefix frontend test -- --run src/features/translations/TranslationDetailPage.test.tsx src/features/translations/MaximumLengthDialog.test.tsx src/router.test.tsx && npm --prefix frontend run e2e -- translations.spec.ts` | ❌ W0 | ⬜ pending |
| 04-19-01 | 19 | 15 | All Phase 4 requirements | T-04-57–T-04-60 | Exact source/scope equality, fail-closed closeout parser, reversible mutants, gauntlet, and smoke block drift | architecture + adversarial | `uv run --project backend pytest backend/tests/architecture/test_phase4_scope.py backend/tests/architecture/test_phase4_closeout_gate.py -q && uv run --project backend python tools/verify_translation_mutants.py --self-test` | ❌ W0 | ⬜ pending |
| 04-20-01 | 20 | 16 | All Phase 4 requirements | T-04-01–T-04-77, T-04-SC | Structured closeout accepts only zero unresolved Critical/high, exact SECURED, exact lowercase passed, and one source digest | phase gate | `uv run --project backend python tools/verify_phase4_closeout.py --check-all --manifest tools/phase4_source_manifest.txt --evidence docs/evidence/phase-04.md --code-review docs/reviews/phase-04-code-review.md --security-review docs/reviews/phase-04-security-review.md --review-ledger .planning/phases/04-localization-import-search-and-constraints/04-REVIEW.md --verification .planning/phases/04-localization-import-search-and-constraints/04-VERIFICATION.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/fixtures/localization/` — immutable source bytes and hand-authored canonical manifests for every supported format and boundary category.
- [ ] `backend/tests/unit/localization/importing/test_contracts.py` — canonical result, selector, issue, and limit contract tests.
- [ ] `backend/tests/unit/localization/importing/test_android_xml.py`, `test_qt_ts.py`, `test_json.py`, `test_ios_strings.py`, `test_conformance.py` — adapter golden/property suites.
- [ ] `backend/tests/integration/test_translation_import_activation.py` — PostgreSQL activation, rewrite-confirmation, refresh, and concurrency fixtures.
- [ ] `backend/tests/integration/test_product_publication.py` — exact base-language candidate clone and publication preservation.
- [ ] `backend/tests/integration/test_translation_search.py` and `test_translation_constraints.py` — indexed search and recomputation integration suites with `pg_trgm` enabled.
- [ ] `backend/tests/api/test_translations.py` and `test_translation_constraints.py` — authenticated API and OpenAPI contract tests.
- [ ] `frontend/src/features/translations/` component tests and `frontend/e2e/translations.spec.ts` — route, virtual list, detail, constraint, navigation-restoration, and stale-request coverage.
- [ ] `backend/tests/architecture/test_phase4_scope.py`, `test_phase4_closeout_gate.py`, and `tools/verify_phase4_closeout.py` — exact source/scope equality and fail-closed verdict/digest fixtures.

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
