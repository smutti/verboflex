---
phase: 04
slug: localization-import-search-and-constraints
status: validated
nyquist_compliant: true
wave_0_complete: true
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
| 04-01-01 | 01 | 1 | FMT-01, FMT-07 | T-04-01–T-04-03 | Canonical contract plus Android scalar tracer proves one registry path with safe failure | TDD tracer | `uv run --project backend pytest backend/tests/unit/localization/importing/test_contracts.py backend/tests/unit/localization/importing/test_android_xml.py -q` | ✅ exists | ✅ automated green |
| 04-02-01 | 02 | 2 | FMT-01, FMT-06 | T-04-04–T-04-06 | Exact Android allowlist, plural/array/XML fidelity, resource bounds, and atomic rejection | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_android_xml.py -q` | ✅ exists | ✅ automated green |
| 04-03-01 | 03 | 2 | FMT-02, FMT-06 | T-04-07–T-04-09 | Exact Qt allowlist, numerus/variant fidelity, resource bounds, and atomic rejection | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_qt_ts.py -q` | ✅ exists | ✅ automated green |
| 04-04-01 | 04 | 2 | FMT-03, FMT-06 | T-04-10–T-04-12 | JSON leaves are deterministic and reject duplicates/depth/size overflow | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_json.py -q` | ✅ exists | ✅ automated green |
| 04-05-01 | 05 | 2 | FMT-04, FMT-06 | T-04-13–T-04-15 | iOS lexical parsing preserves escapes/encoding and rejects invalid input atomically | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_ios_strings.py -q` | ✅ exists | ✅ automated green |
| 04-06-01 | 06 | 3 | FMT-01, FMT-02, FMT-03, FMT-04, FMT-06 | T-04-16–T-04-18 | Registry conformance exact supported/rejected equality and direct/separate join safety | unit + property | `uv run --project backend pytest backend/tests/unit/localization/importing/test_conformance.py -q` | ✅ exists | ✅ automated green |
| 04-07-01 | 07 | 4 | FMT-01, FMT-02, FMT-03, FMT-04, FMT-06, CONS-03, SRCH-08 | T-04-19, T-04-20, T-04-SC | Coverage, static checks, audit/license, manifest equality, backend/worker smoke, and package approvals block persistence/install | checkpoint | `bash tools/phase4_parser_checkpoint.sh --container-smoke && bash tools/phase4_parser_checkpoint.sh --verify-evidence` | ✅ exists | ✅ automated green |
| 04-08-01 | 08 | 5 | FMT-07, FMT-08, CONS-04 | T-04-21 | Base-language authority has bounded migration-safe storage with explicit legacy null | migration | `uv run --project backend pytest backend/tests/integration/test_migrations.py -q -k 'base_language or head'` | ✅ exists | ✅ automated green |
| 04-26-01 | 26 | 6 | FMT-07, FMT-08, CONS-04 | T-04-22 | Exact candidate language binds confirmation, digest, currentness, revalidation, and admin API authority | service + API | `uv run --project backend pytest backend/tests/integration/test_preview_jobs.py backend/tests/api/test_admin_previews.py -q -k base_language` | ✅ exists | ✅ automated green |
| 04-27-01 | 27 | 7 | FMT-07, FMT-08, CONS-04 | T-04-23 | Candidate clone and atomic publication preserve exact base-language authority without historical mutation | integration | `uv run --project backend pytest backend/tests/integration/test_product_publication.py backend/tests/integration/test_preview_jobs.py -q -k 'base_language or clone or publication'` | ✅ exists | ✅ automated green |
| 04-14-01 | 14 | 5 | CONS-03, CONS-04 | T-04-42, T-04-SC | Approved exact-pinned UAX #29 dependency provides one versioned grapheme authority | unit | `uv run --project backend pytest backend/tests/unit/localization/test_grapheme_count.py -q && uv run --project backend pip check` | ✅ exists | ✅ automated green |
| 04-09-01 | 09 | 7 | FMT-07, FMT-08 | T-04-24–T-04-26 | RED-first generated contract and Preview selection prevent publication without exact base authority | contract + component | `npm --prefix frontend run api:check && npm --prefix frontend test -- --run src/features/admin/previews/ProductPreviewPage.test.tsx` | ✅ exists | ✅ automated green |
| 04-10-01 | 10 | 6 | FMT-07, FMT-08, CONS-01..04 | T-04-27–T-04-30 | Stable identity, ownership, staging, history, and constraint checks hold in PostgreSQL | migration + model | `uv run --project backend pytest backend/tests/integration/test_migrations.py backend/tests/unit/localization/importing/test_contracts.py -q` | ✅ exists | ✅ automated green |
| 04-11-01 | 11 | 8 | FMT-07, FMT-08, CONS-04 | T-04-31–T-04-34 | Stale/superseded/partial imports cannot activate; refresh truth table preserves context | integration | `uv run --project backend pytest backend/tests/integration/test_translation_import_activation.py -q` | ✅ exists | ✅ automated green |
| 04-12-01 | 12 | 9 | FMT-06, FMT-08 | T-04-35–T-04-37 | Admin parser outcome API is bounded, redacted, and retained-dataset aware | API | `uv run --project backend pytest backend/tests/api/test_admin_mappings.py backend/tests/api/test_import_jobs.py -q -k 'parser or issue or dataset'` | ✅ exists | ✅ automated green |
| 04-13-01 | 13 | 9 | SRCH-01..SRCH-08 | T-04-38–T-04-41 | Literal search/detail is scoped; external pg_trgm is preflighted; project indexes roll back symmetrically; cursors bind filters/dataset/order | migration + API + integration | `uv run --project backend pytest backend/tests/integration/test_migrations.py backend/tests/integration/test_translation_search.py backend/tests/api/test_translations.py -q` | ✅ exists | ✅ automated green |
| 04-21-01 | 21 | 9 | SRCH-05, CONS-01..CONS-04 | T-04-43–T-04-44 | Dynamic inheritance, exact mutation concurrency, and every recomputation boundary share one transaction-safe service | integration | `uv run --project backend pytest backend/tests/integration/test_translation_constraints.py backend/tests/integration/test_translation_import_activation.py -q -k 'constraint or recompute or grapheme'` | ✅ exists | ✅ automated green |
| 04-25-01 | 25 | 10 | SRCH-05, SRCH-07, CONS-01, CONS-02, CONS-05 | T-04-68–T-04-69 | Only strict role-gated maximum-length PUT/DELETE routes mutate synchronously | API | `uv run --project backend pytest backend/tests/api/test_translation_constraints.py backend/tests/api/test_translations.py -q` | ✅ exists | ✅ automated green |
| 04-15-01 | 15 | 11 | SRCH-01..08, CONS-01..05 | T-04-45–T-04-47 | Final OpenAPI inventory and RED-first generated TypeScript client are exact and drift-free | contract | `uv run --project backend pytest backend/tests/api/test_openapi_contract.py -q && npm --prefix frontend run api:check && npm --prefix frontend test -- --run src/api/admin-client-contract.test.ts` | ✅ exists | ✅ automated green |
| 04-16-01 | 16 | 12 | SRCH-01..05, SRCH-08 | T-04-48, T-04-65–T-04-67 | Preferences are allowlisted/principal-scoped and infinite search rejects stale generations | component/property | `npm --prefix frontend test -- --run src/features/translations/translationPreferences.test.ts src/features/translations/useTranslationSearch.test.ts` | ✅ exists | ✅ automated green |
| 04-17-01 | 17 | 12 | SRCH-02, SRCH-04..06, SRCH-08 | T-04-49–T-04-52, T-04-SC | Exact window virtualizer and six-part rows preserve hostile content and bounded DOM | component + accessibility | `npm --prefix frontend test -- --run src/features/translations/TranslationResultList.test.tsx && npm --prefix frontend run typecheck` | ✅ exists | ✅ automated green |
| 04-22-01 | 22 | 12 | FMT-06, FMT-08 | T-04-70–T-04-72 | Published mapping UI renders bounded parser failures, retained-baseline retry state, and exceptional admin-only base-language recovery | component | `npm --prefix frontend test -- --run src/features/admin/imports/PublishedMappingImports.test.tsx && npm --prefix frontend run typecheck` | ✅ exists | ✅ automated green |
| 04-23-01 | 23 | 13 | SRCH-01..SRCH-05, SRCH-08 | T-04-73–T-04-75 | Exact five-filter search page composes memory/preferences, request races, and one virtual list | component | `npm --prefix frontend test -- --run src/features/translations/TranslationFilters.test.tsx src/features/translations/TranslationSearchPage.test.tsx && npm --prefix frontend run typecheck` | ✅ exists | ✅ automated green |
| 04-24-01 | 24 | 14 | SRCH-01, SRCH-06, SRCH-08 | T-04-76–T-04-77 | Protected search route and Translations navigation are direct-link and keyboard safe | component | `npm --prefix frontend test -- --run src/router.test.tsx src/components/layout/AppShell.test.tsx && npm --prefix frontend run typecheck` | ✅ exists | ✅ automated green |
| 04-18-01 | 18 | 15 | SRCH-06, SRCH-07, CONS-01..05 | T-04-53–T-04-56 | Detail includes pending/comment placeholders; dialogs enforce abortable non-dismissable request authority | component + E2E | `npm --prefix frontend test -- --run src/features/translations/TranslationDetailPage.test.tsx src/features/translations/MaximumLengthDialog.test.tsx src/router.test.tsx && npm --prefix frontend run e2e -- translations.spec.ts` | ✅ exists | ✅ automated green |
| 04-19-01 | 19 | 16 | All Phase 4 requirements | T-04-57–T-04-60 | Exact source/scope equality, deterministic API coverage assertion, post-install supply-chain checks, fail-closed closeout parser, reversible mutants, gauntlet, and smoke block drift | architecture + adversarial | `uv run --project backend pytest backend/tests/architecture/test_phase4_scope.py backend/tests/architecture/test_phase4_closeout_gate.py -q && uv run --project backend python tools/verify_translation_mutants.py --self-test` | ✅ exists | ✅ automated green |
| 04-20-01 | 20 | 17 | All Phase 4 requirements | T-04-01–T-04-77, T-04-SC | Structured closeout accepts only zero unresolved Critical/high, exact SECURED, exact lowercase passed, and one source digest | phase gate | `uv run --project backend python tools/verify_phase4_closeout.py --check-all --manifest tools/phase4_source_manifest.txt --evidence docs/evidence/phase-04.md --code-review docs/reviews/phase-04-code-review.md --security-review docs/reviews/phase-04-security-review.md --review-ledger .planning/phases/04-localization-import-search-and-constraints/04-REVIEW.md --verification .planning/phases/04-localization-import-search-and-constraints/04-VERIFICATION.md` | ✅ exists | ⚠️ review/security green; all-check awaits human UAT |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `backend/tests/fixtures/localization/` — immutable source bytes and hand-authored canonical manifests for every supported format and boundary category.
- [x] `backend/tests/unit/localization/importing/test_contracts.py` — canonical result, selector, issue, and limit contract tests.
- [ ] `backend/tests/unit/localization/importing/test_android_xml.py`, `test_qt_ts.py`, `test_json.py`, `test_ios_strings.py`, `test_conformance.py` — adapter golden/property suites.
- [x] `backend/tests/integration/test_translation_import_activation.py` — PostgreSQL activation, rewrite-confirmation, refresh, and concurrency fixtures.
- [x] `backend/tests/integration/test_product_publication.py` — exact base-language candidate clone and publication preservation.
- [ ] `backend/tests/integration/test_translation_search.py` and `test_translation_constraints.py` — indexed search and recomputation integration suites against an infrastructure-pre-enabled `pg_trgm`, including absent/unusable precondition failures.
- [ ] `backend/tests/api/test_translations.py` and `test_translation_constraints.py` — authenticated API and OpenAPI contract tests.
- [ ] `frontend/src/features/translations/` component tests and `frontend/e2e/translations.spec.ts` — route, virtual list, detail, constraint, navigation-restoration, and stale-request coverage.
- [ ] `backend/tests/architecture/test_phase4_scope.py`, `test_phase4_closeout_gate.py`, and `tools/verify_phase4_closeout.py` — exact source/scope equality and fail-closed verdict/digest fixtures.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Bitbucket import smoke | FMT-07, FMT-08 | Requires workspace credentials and a disposable repository/branch | Import a mapped disposable branch, verify the active dataset and provenance, then change one external value and confirm only the affected translation returns to Draft. |
| Responsive and assistive-technology review | SRCH-06, SRCH-07, SRCH-08, CONS-05 | Final visual/focus behavior benefits from a real browser and screen-reader pass | Exercise desktop and narrow widths, keyboard navigation, focus restoration after back navigation, virtualized-row announcements, and all constraint dialog error states. |

| No inferred rename framing | FMT-07, FMT-08 / Plan 04-11 prohibition | Flagged judgment-tier requirement needs per-item human resolution | Review deletion plus a new equal-text key: confirm separate identities and no inferred-rename presentation. |
| Readable and retainable over-limit content | CONS-05 / Plan 04-18 prohibition | Flagged values judgment cannot be resolved by DOM assertions alone | Confirm full over-limit text remains readable and retainable in Draft, with no destructive-removal framing. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verification or explicit Wave 0 dependencies.
- [x] Sampling continuity: no three consecutive tasks without automated verification.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags are used.
- [ ] Per-task feedback latency remains below 120 seconds.
- [x] Parser checkpoint passes before persistence/search execution begins.
- [x] `nyquist_compliant: true` is set in frontmatter after validation.

**Validation:** automated behavioral coverage verified against the final source-bound run. All 20 Phase 4 requirements have executable passing checks. Human UAT and the two judgment-tier prohibitions remain outstanding; no phase completion or all-check pass is claimed. Historical per-task feedback timing was not exhaustively reconstructed; the final full backend suite took 153.17 seconds and is not a per-task latency claim.

## Validation Audit — 2026-09-06

Source digest: `sha256:2df3766ead7f1aea3597a8ad8b99205f14508a4189109996149265a163017b3a`. Evidence: `docs/evidence/phase-04.md` and `docs/evidence/phase-04-run.json`; full `bash tools/phase4_gauntlet.sh` exit 0, including all previous-phase backend/frontend suites and fresh isolated deployment smoke. Exact source mapping is `tools/phase4_source_manifest.txt` (20 requirements, 23 decisions, 52 edges, two prohibitions, 8 UI categories / 50 instances / 3 axes). Independent code review traced every requirement/decision and independently replayed targeted behavior; goal verification preserves the exact per-item map.

| Metric | Verified result |
|---|---|
| Requirement coverage | 20 covered; 0 missing automated behavior tests |
| Backend | 1,614 passed; changed executable lines 3,285/3,285 |
| Frontend | 590 passed; changed executable lines 842/842 |
| Parser | 1,817 statements / 704 branches, 100% |
| Mutation / browser / smoke | 12 source probes killed and restored; 21 browser journeys passed; four formats / four roles built-stack smoke passed |
| TDD execution hook | `gsd-tools.cjs check tdd.review-checkpoint 04 --raw`: passed, block false, 21 TDD plans, zero violations |
| Structured intermediate review gates | `--check-code-review` and `--check-security` pass at the same digest |
| Manual checks | 4 still pending: live provider, native assistive review, two judgment prohibitions |

All automated defects found during review were corrected test-first, including query restoration, error-schema union, coherent import polling, constraint/activation lock order and retained-baseline epoch updates. Failed and interrupted runs remain documented rather than relabeled. The completed UI audit is 24/24 for its inspected automated/visual scope; it explicitly does not certify native 200% zoom or a screen-reader session. Nyquist compliance here certifies available automated coverage, not human acceptance. Plan 04-20's strict `--check-all` must remain nonzero until the human-needed verification status is resolved.
