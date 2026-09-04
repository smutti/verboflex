---
phase: 04
slug: localization-import-search-and-constraints
status: draft
nyquist_compliant: false
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
| 04-01-01 | 01 | 1 | FMT-07 | T-04-01 | Canonical identities exclude mutable paths and do not expose repository content in errors | unit | `uv run --project backend pytest backend/tests/unit/localization/importing/test_contracts.py -q` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | FMT-01 | T-04-02 | Android XML parsing is bounded and rejects unsafe XML constructs | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_android_xml.py -q` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | FMT-02 | Qt XML parsing is bounded and rejects unsafe XML constructs | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_qt_ts.py -q` | ❌ W0 | ⬜ pending |
| 04-04-01 | 04 | 2 | FMT-03 | JSON rejects duplicates, excessive depth, and oversized input deterministically | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_json.py -q` | ❌ W0 | ⬜ pending |
| 04-05-01 | 05 | 2 | FMT-04 | iOS strings parsing preserves encoding/escapes and rejects malformed or oversized input | unit + golden | `uv run --project backend pytest backend/tests/unit/localization/importing/test_ios_strings.py -q` | ❌ W0 | ⬜ pending |
| 04-06-01 | 06 | 3 | FMT-06 | All adapters honor identical bounds, issue redaction, selectors, and canonical output | unit + property | `uv run --project backend pytest backend/tests/unit/localization/importing/test_conformance.py -q` | ❌ W0 | ⬜ pending |
| 04-07-01 | 07 | 4 | FMT-01, FMT-02, FMT-03, FMT-04, FMT-06 | T-04-01, T-04-02 | Parser checkpoint blocks persistence work unless the complete corpus and security cases pass | quality gate | `uv run --project backend pytest backend/tests/unit/localization/importing -q` | ❌ W0 | ⬜ pending |
| 04-08-01 | 08 | 5 | FMT-07, FMT-08 | T-04-03 | Failed, stale, or superseded imports cannot replace the last valid active dataset | integration | `uv run --project backend pytest backend/tests/integration/test_translation_import_activation.py -q` | ❌ W0 | ⬜ pending |
| 04-09-01 | 09 | 6 | SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-08 | T-04-04 | Search is authorization-scoped; literal query input and opaque cursors cannot escape their filter authority | API + integration | `uv run --project backend pytest backend/tests/api/test_translations.py backend/tests/integration/test_translation_search.py -q` | ❌ W0 | ⬜ pending |
| 04-10-01 | 10 | 7 | SRCH-06, SRCH-07 | T-04-04 | Unauthorized and absent details have bounded non-enumerating responses; deleted records remain read-only | API + component | `uv run --project backend pytest backend/tests/api/test_translations.py -q -k detail && npm --prefix frontend test -- --run src/features/translations/TranslationDetailPage.test.tsx` | ❌ W0 | ⬜ pending |
| 04-11-01 | 11 | 6 | CONS-01, CONS-02, CONS-03, CONS-04, CONS-05 | T-04-05 | Constraint mutations are role-gated, concurrency-safe, and use one grapheme-count implementation | unit + API + integration | `uv run --project backend pytest backend/tests/unit/localization/test_grapheme_count.py backend/tests/api/test_translation_constraints.py backend/tests/integration/test_translation_constraints.py -q` | ❌ W0 | ⬜ pending |
| 04-12-01 | 12 | 7 | SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, SRCH-07, SRCH-08, CONS-05 | T-04-04, T-04-05 | UI exposes only authorized server projections, drops stale responses, and keeps a bounded virtual DOM | component + E2E | `npm --prefix frontend test -- --run src/features/translations && npm --prefix frontend run e2e -- translations.spec.ts` | ❌ W0 | ⬜ pending |
| 04-13-01 | 13 | 8 | FMT-01, FMT-02, FMT-03, FMT-04, FMT-06, FMT-07, FMT-08, SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, SRCH-07, SRCH-08, CONS-01, CONS-02, CONS-03, CONS-04, CONS-05 | T-04-01–T-04-05 | Final gate includes coverage, client drift, E2E, container smoke, code review, and security verification | phase gate | `uv run --project backend pytest && npm --prefix frontend run test:coverage && npm --prefix frontend run api:check && npm --prefix frontend run build` | ❌ W0 | ⬜ pending |

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

**Approval:** pending
