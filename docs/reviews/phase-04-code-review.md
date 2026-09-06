---
phase: 04-localization-import-search-and-constraints
reviewed: 2026-09-06T11:03:00Z
depth: standard
reviewer: gsd-code-reviewer
status: pending
source_digest: sha256:71d41b57dcf7d1bac376166c936212a360afb54c8aa99d4fbca6dd3321c54659
files_reviewed: 76
files_reviewed_list:
  - backend/alembic/versions/0011_active_revision_revalidations.py
  - backend/alembic/versions/0012_import_jobs.py
  - backend/alembic/versions/0015_mapping_base_language.py
  - backend/alembic/versions/0016_canonical_translations.py
  - backend/alembic/versions/0017_translation_search_indexes.py
  - backend/alembic/versions/0018_constraint_generation.py
  - backend/alembic/versions/0019_unicode_search_indexes.py
  - backend/alembic/versions/0020_bounded_key_identities.py
  - backend/pyproject.toml
  - backend/src/verboflex/api/v1/router.py
  - backend/src/verboflex/api/v1/routes/admin_mappings.py
  - backend/src/verboflex/api/v1/routes/admin_previews.py
  - backend/src/verboflex/api/v1/routes/translation_constraints.py
  - backend/src/verboflex/api/v1/routes/translations.py
  - backend/src/verboflex/localization/graphemes.py
  - backend/src/verboflex/localization/importing/__init__.py
  - backend/src/verboflex/localization/importing/android_xml.py
  - backend/src/verboflex/localization/importing/core.py
  - backend/src/verboflex/localization/importing/ios_strings.py
  - backend/src/verboflex/localization/importing/json.py
  - backend/src/verboflex/localization/importing/qt_ts.py
  - backend/src/verboflex/localization/importing/registry.py
  - backend/src/verboflex/main.py
  - backend/src/verboflex/models/__init__.py
  - backend/src/verboflex/models/import_job.py
  - backend/src/verboflex/models/product_mapping.py
  - backend/src/verboflex/models/translation.py
  - backend/src/verboflex/models/translation_constraint.py
  - backend/src/verboflex/schemas/imports.py
  - backend/src/verboflex/schemas/previews.py
  - backend/src/verboflex/schemas/translation_constraints.py
  - backend/src/verboflex/schemas/translations.py
  - backend/src/verboflex/services/import_jobs.py
  - backend/src/verboflex/services/preview_jobs.py
  - backend/src/verboflex/services/products.py
  - backend/src/verboflex/services/translation_constraints.py
  - backend/src/verboflex/services/translation_imports.py
  - backend/src/verboflex/services/translation_search.py
  - backend/src/verboflex/worker/import_tasks.py
  - frontend/package.json
  - frontend/src/components/layout/AppShell.tsx
  - frontend/src/components/ui/alert-dialog.tsx
  - frontend/src/components/ui/alert.tsx
  - frontend/src/components/ui/badge.tsx
  - frontend/src/components/ui/button.tsx
  - frontend/src/components/ui/dialog.tsx
  - frontend/src/components/ui/input.tsx
  - frontend/src/components/ui/label.tsx
  - frontend/src/components/ui/select.tsx
  - frontend/src/components/ui/sheet.tsx
  - frontend/src/components/ui/skeleton.tsx
  - frontend/src/components/ui/tooltip.tsx
  - frontend/src/features/admin/imports/PublishedMappingImports.tsx
  - frontend/src/features/admin/imports/useImportPolling.ts
  - frontend/src/features/admin/previews/ProductPreviewPage.tsx
  - frontend/src/features/translations/MaximumLengthDialog.tsx
  - frontend/src/features/translations/TranslationDetailPage.tsx
  - frontend/src/features/translations/TranslationFilters.tsx
  - frontend/src/features/translations/TranslationResultList.tsx
  - frontend/src/features/translations/TranslationSearchPage.tsx
  - frontend/src/features/translations/TranslationsWorkspace.tsx
  - frontend/src/features/translations/translationDetailAuthority.ts
  - frontend/src/features/translations/translationFilterLabels.ts
  - frontend/src/features/translations/translationPreferences.ts
  - frontend/src/features/translations/useTranslationSearch.ts
  - frontend/src/router.tsx
  - tools/phase4_gate.py
  - tools/phase4_gauntlet.sh
  - tools/phase4_inventory.py
  - tools/phase4_parser_checkpoint.sh
  - tools/phase4_smoke.py
  - tools/phase4_smoke.sh
  - tools/phase4_smoke_browser.mjs
  - tools/verify_phase4_closeout.py
  - tools/verify_phase4_npm.mjs
  - tools/verify_translation_mutants.py
findings:
  critical: 6
  warning: 6
  info: 0
  total: 12
---
# Phase 04 code review — pending remediation and completion

## Narrative Findings (AI reviewer)

The final pass confirms two new functional BLOCKER findings (CR-10, CR-12) and independently reproduces the security auditor's high BLOCKER CR-11. Earlier CR-01 through CR-09 have identifiable source corrections, but none is being closed by inference from its fix commit or reported test success. Both reports remain pending. No production or test source was modified by this reviewer.

The impact-severity totals are normalized: six high findings (CR-01/03/07/08/09/11), six medium findings (CR-02/04/05/06/10/12), and no critical-impact findings. The frontmatter critical bucket includes high impact; warning includes medium impact. All twelve are release BLOCKER classifications because they concern required behavior or gate integrity. Historical first-pass counts and proof below are retained explicitly as history.

## Scope and evidence status

Exact base: `d987d5f48273d49234b07aacb3fa185337a1b4f2`. Observed source revision: `2b3b0d6661d896984629c51fd536becbd421d46d`. The frontmatter digest is an observed source snapshot, not a claim of a post-gauntlet freeze. The fresh run started against this digest has been interrupted for confirmed defects; replacement evidence is required after fixes.

The exact scoped diff currently contains 165 backend/frontend/tools/config paths. The 76-file list preserves the previous 69-file partial review inventory and adds seven omitted migration/delivery files inspected in this pass. It includes focused cross-boundary inspection of large existing modules and must not be interpreted as completion of standard full-file review. The earlier approximate 91-file production estimate did not count the complete tests/fixtures/generated/lock scope.

Fully read in this continuation: canonical core/registry; translation search and constraint services; three new migrations; search hook, search page, result list, workspace, preferences, detail-authority helper and maximum-length dialog; gate runner and smoke Python/browser/shell delivery code; parser checkpoint script. Focused reads include Android tail rejection, reconciliation transitions, response schema, preview confirmation helpers, the complete import-job diff, and regression fixture/setup sections. The hook continuation guard removal was traced through every internal state write: validated snapshot/page creates the cursor; query changes clear it synchronously; filter/token changes enter initial loading; post-await generation, identity and cursor guards remain.

Required context inspected includes AGENTS.md, .planning/config.json (no configured agent skills), the agent-skills bootstrap, Phase 04 CONTEXT, UI-SPEC, RESEARCH, Plan 20, source manifest, existing reports and closeout validator. No project .codex/skills or .agents/skills directory exists. No structural pre-pass was supplied. Long context/tool reads included truncation; the remaining full-read completion must be reconciled rather than presumed.

## Current finding disposition

| ID | File/line | Severity | Classification | Proof | Impact | Resolution | Remediation |
|---|---|---|---|---|---|---|---|
| CR-11 | `tools/verify_phase4_closeout.py:132` | high | BLOCKER | Independently invoked validate_document with SECURED, a valid-looking digest and only T1/high/mitigate/placeholder.py:1/resolved. It returned SECURED with zero required threat IDs. | The promised automated gate can accept omitted high threats; T-04-62/T-04-64 and Plan 20 exact security replay fail. | open | Compare exact registered T-04-01..77 plus T-04-SC set, cardinality and declared severity; reject duplicate, unknown, omitted and downgraded rows. Test each case; bind to actual source/evidence. |
| CR-10 | `backend/src/verboflex/services/translation_search.py:421,449,791` | medium | BLOCKER | Production search/detail on a disposable migrated PostgreSQL fixture with two array values, one tombstoned, returned active_groups=0, deleted_groups=1, detail_deleted=True, retained_active_values=1. | Removing one variant hides the live siblings from normal search and disables the group's constraint UI. Tombstoned minimum UUID also disagrees with mutation's minimum-live anchor. | open | Keep stable canonical/group authority; mark group deleted only when key/all members are deleted; base current filters on live members; permit the stable group anchor only while live members remain. Regress actual parser refresh, default search, detail and constraint mutation for leading/nonleading removed variants. |
| CR-12 | `frontend/src/features/translations/TranslationSearchPage.tsx:450,461`; `frontend/src/features/translations/useTranslationSearch.ts:280` | medium | BLOCKER | Back restores a saved snapshot while options await. The editable pending query is passed as initialQuery, but validScope checks only product/language and restoreSnapshot returns snapshot.query. A read-only transpile/VM probe returned enteredQuery=new, restoredQuery=old. | User input entered during options loading is overwritten with the old query and old results. | open | Invalidate old snapshot pages/query authority whenever the current query differs; retain the new input and request fresh results. Add a deferred-options Back-navigation component regression. |

## Earlier corrections observed, awaiting independent regression closure

| Finding | Source observation at reviewed snapshot | Remaining verification |
|---|---|---|
| CR-01 | Android plural/array item branches reject non-whitespace tails before constructing values. | Re-run both real registry tail cases and mapping atomic-failure regressions. |
| CR-02 | Target-change logic no longer gates reset on Approved; only proven Approved correlation bypasses Draft. | Recheck rejected changed target and retained history/context in real activation. |
| CR-03 | Durable key generation survives DELETE; migration 0018 lifts prior-key epoch and versions to bounded BIGINT. | Recheck ABA PUT/DELETE and migration tests, including distinct language rules. |
| CR-04 | Detail base rule lookup now uses scope plus raw key across repository sides. | Recheck separate-side inheritance and override removal API/UI projections. |
| CR-05 | Cursor contains filter digest and UUID/rank/language anchor, not raw key; decoder retains 2048 bound and database validates anchor. | Recheck 51 long-key groups, Unicode/escaped filter boundaries and final encoder invariant tests. |
| CR-06 | Search uses PostgreSQL Unicode casefold for query/key/source/display; migration 0019 aligns expressions. | Recheck ligature/final-sigma tiers and migration/index behavior on PostgreSQL 18. |
| CR-07 | API structure cap references canonical MAX_CANONICAL_STRUCTURE_NODES. | Recheck parser-valid large structure through authenticated API and regenerated client. |
| CR-08 | Worker derives current file membership from confirmed immutable layout, not original preview file list. | Recheck move/add/remove/unsupported-new-file production refresh and separate mapping atomicity. |
| CR-09 | Browser checks language-bound confirmation digest shape and exact identities without comparing with original unbound digest. | Recheck realistic unequal-digest draft and active confirmation tests. |

Additional source review: migration 0020 bounds unique natural-key indexes with a full raw-key digest while preserving raw text and transactional downgrade failure. CanonicalValueBuffer bounds incremental UTF-8 JSON expansion in nested adapter buffers, peer-file aggregation, separate-side shared budget and post-join expansion. Exact budget/fidelity tests were inspected selectively; their full independent review/run remains outstanding. Constraint mutation now increments dataset_version when effective state changes, closing the earlier cursor-invalidation candidate in source.

## Requirement and decision trace

These are exact manifest entry points, not PASS assertions. Every row remains pending final source/test completion and fresh execution evidence; CR-10 additionally blocks active structured-group behavior and CR-12 blocks browser query continuity.

| Kind | ID | Delivery source | Executable test entry points | Disposition |
|---|---|---|---|---|
| DECISION | D-01 | `backend/src/verboflex/localization/importing/android_xml.py` | `backend/tests/unit/localization/importing/test_android_xml.py` | pending |
| DECISION | D-02 | `backend/src/verboflex/localization/importing/android_xml.py` | `backend/tests/unit/localization/importing/test_android_xml.py` | pending |
| DECISION | D-03 | `backend/src/verboflex/localization/importing/core.py` | `backend/tests/unit/localization/importing/test_contracts.py` | pending |
| DECISION | D-04 | `backend/src/verboflex/localization/importing/registry.py` | `backend/tests/unit/localization/importing/test_conformance.py` | pending |
| DECISION | D-05 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
| DECISION | D-06 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
| DECISION | D-07 | `backend/src/verboflex/models/translation.py` | `backend/tests/integration/test_migrations.py`, `backend/tests/unit/localization/importing/test_contracts.py` | pending |
| DECISION | D-08 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
| DECISION | D-09 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
| DECISION | D-10 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
| DECISION | D-11 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
| DECISION | D-12 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
| DECISION | D-13 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
| DECISION | D-14 | `frontend/src/features/translations/TranslationSearchPage.tsx` | `frontend/src/features/translations/TranslationSearchPage.test.tsx` | pending |
| DECISION | D-15 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | pending |
| DECISION | D-16 | `frontend/src/features/translations/TranslationSearchPage.tsx` | `frontend/src/features/translations/TranslationSearchPage.test.tsx` | pending |
| DECISION | D-17 | `frontend/src/features/translations/useTranslationSearch.ts` | `frontend/src/features/translations/useTranslationSearch.test.ts` | pending |
| DECISION | D-18 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | pending |
| DECISION | D-19 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | pending |
| DECISION | D-20 | `backend/src/verboflex/localization/graphemes.py` | `backend/tests/unit/localization/test_grapheme_count.py` | pending |
| DECISION | D-21 | `backend/src/verboflex/api/v1/routes/translation_constraints.py` | `backend/tests/api/test_translation_constraints.py` | pending |
| DECISION | D-22 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | pending |
| DECISION | D-23 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | pending |
| REQ | CONS-01 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | pending |
| REQ | CONS-02 | `backend/src/verboflex/api/v1/routes/translation_constraints.py` | `backend/tests/api/test_translation_constraints.py` | pending |
| REQ | CONS-03 | `backend/src/verboflex/localization/graphemes.py` | `backend/tests/unit/localization/test_grapheme_count.py` | pending |
| REQ | CONS-04 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | pending |
| REQ | CONS-05 | `backend/src/verboflex/api/v1/routes/translation_constraints.py` | `backend/tests/api/test_translation_constraints.py` | pending |
| REQ | FMT-01 | `backend/src/verboflex/localization/importing/android_xml.py` | `backend/tests/unit/localization/importing/test_android_xml.py` | pending |
| REQ | FMT-02 | `backend/src/verboflex/localization/importing/qt_ts.py` | `backend/tests/unit/localization/importing/test_qt_ts.py` | pending |
| REQ | FMT-03 | `backend/src/verboflex/localization/importing/json.py` | `backend/tests/unit/localization/importing/test_json.py` | pending |
| REQ | FMT-04 | `backend/src/verboflex/localization/importing/ios_strings.py` | `backend/tests/unit/localization/importing/test_ios_strings.py` | pending |
| REQ | FMT-06 | `backend/src/verboflex/localization/importing/registry.py` | `backend/tests/unit/localization/importing/test_conformance.py` | pending |
| REQ | FMT-07 | `backend/src/verboflex/models/translation.py` | `backend/tests/integration/test_migrations.py`, `backend/tests/unit/localization/importing/test_contracts.py` | pending |
| REQ | FMT-08 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
| REQ | SRCH-01 | `frontend/src/features/translations/TranslationSearchPage.tsx` | `frontend/src/features/translations/TranslationSearchPage.test.tsx` | pending |
| REQ | SRCH-02 | `frontend/src/features/translations/TranslationSearchPage.tsx` | `frontend/src/features/translations/TranslationSearchPage.test.tsx` | pending |
| REQ | SRCH-03 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | pending |
| REQ | SRCH-04 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | pending |
| REQ | SRCH-05 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | pending |
| REQ | SRCH-06 | `frontend/src/features/translations/TranslationDetailPage.tsx` | `frontend/src/features/translations/TranslationDetailPage.test.tsx`, `frontend/src/features/translations/MaximumLengthDialog.test.tsx`, `frontend/e2e/translations.spec.ts` | pending |
| REQ | SRCH-07 | `frontend/src/features/translations/TranslationDetailPage.tsx` | `frontend/src/features/translations/TranslationDetailPage.test.tsx`, `frontend/src/features/translations/MaximumLengthDialog.test.tsx`, `frontend/e2e/translations.spec.ts` | pending |
| REQ | SRCH-08 | `frontend/src/features/translations/useTranslationSearch.ts` | `frontend/src/features/translations/useTranslationSearch.test.ts` | pending |

## Diagnostic commands and results

- Read-only production-service probe used the existing search_session_factory fixture to create a uniquely named test database on the test PostgreSQL instance. It seeded one two-value group, tombstoned one sibling and called search_translations/get_translation_group. Result: active_groups=0, deleted_groups=1, detail_deleted=True, retained_active_values=1. The fixture dropped only its owned database; the user's application stack was untouched.
- Read-only Node/TypeScript transpile+VM probe loaded the actual hook and called restoreSnapshot with a valid old snapshot and new initialQuery. Result: enteredQuery=new, restoredQuery=old.
- Read-only Python runpy probe invoked the actual closeout validator with one unregistered security row. Result: accepted_verdict=SECURED, required_threats_present=0.
- `uv run --project backend python tools/verify_phase4_closeout.py --digest` returned the frontmatter digest at the observed revision.
- Full gauntlet and smoke are owned by Plan 19. No fresh passing final run is claimed here.

## Remaining standard-review scope

Before any passing verdict: complete full reads of large existing import/preview/product services beyond changed-function inspection; finish detail-page remainder and complete preview surface; review generated SDK/types/OpenAPI and lock identities as contract/config artifacts; read all changed behavioral tests/fixtures for reliability and false-positive coverage; reconcile the full source manifest/UI contracts. The current proof-bearing fixes must then be independently exercised. This is a deliberate incomplete handoff to free the reviewer slot for the requested frontend correction, not completion of the final code review.

The following 89 exact diff files are not in the cumulative inspected-file list. Selective probes/read fragments do not promote them to reviewed status:

- `backend/tests/api/test_admin_mappings.py`
- `backend/tests/api/test_admin_previews.py`
- `backend/tests/api/test_openapi_contract.py`
- `backend/tests/api/test_phase4_failure_boundaries.py`
- `backend/tests/api/test_translation_constraints.py`
- `backend/tests/api/test_translation_structure_roundtrip.py`
- `backend/tests/api/test_translations.py`
- `backend/tests/architecture/test_background_boundaries.py`
- `backend/tests/architecture/test_phase2_gap_closure.py`
- `backend/tests/architecture/test_phase2_scope.py`
- `backend/tests/architecture/test_phase3_scope.py`
- `backend/tests/architecture/test_phase4_closeout_gate.py`
- `backend/tests/architecture/test_phase4_gauntlet.py`
- `backend/tests/architecture/test_phase4_license_policy.py`
- `backend/tests/architecture/test_phase4_scope.py`
- `backend/tests/architecture/test_translation_mutation_verifier.py`
- `backend/tests/fixtures/localization/android/invalid_cases.json`
- `backend/tests/fixtures/localization/android/manifest.json`
- `backend/tests/fixtures/localization/android/scalar.expected.json`
- `backend/tests/fixtures/localization/android/scalar.xml`
- `backend/tests/fixtures/localization/android/valid_structured.expected.json`
- `backend/tests/fixtures/localization/android/valid_structured.xml`
- `backend/tests/fixtures/localization/conformance/direct.json`
- `backend/tests/fixtures/localization/conformance/manifest.json`
- `backend/tests/fixtures/localization/conformance/separate.json`
- `backend/tests/fixtures/localization/ios/invalid_cases.json`
- `backend/tests/fixtures/localization/ios/manifest.json`
- `backend/tests/fixtures/localization/ios/valid.expected.json`
- `backend/tests/fixtures/localization/ios/valid.strings`
- `backend/tests/fixtures/localization/json/invalid_cases.json`
- `backend/tests/fixtures/localization/json/manifest.json`
- `backend/tests/fixtures/localization/json/valid_nested.expected.json`
- `backend/tests/fixtures/localization/json/valid_nested.json`
- `backend/tests/fixtures/localization/qt/invalid_cases.json`
- `backend/tests/fixtures/localization/qt/manifest.json`
- `backend/tests/fixtures/localization/qt/valid_structured.expected.json`
- `backend/tests/fixtures/localization/qt/valid_structured.ts`
- `backend/tests/integration/test_bounded_key_identities.py`
- `backend/tests/integration/test_confirmed_layout_refresh.py`
- `backend/tests/integration/test_constraint_generation_migration.py`
- `backend/tests/integration/test_import_jobs.py`
- `backend/tests/integration/test_migrations.py`
- `backend/tests/integration/test_phase4_search_regressions.py`
- `backend/tests/integration/test_preview_jobs.py`
- `backend/tests/integration/test_product_publication.py`
- `backend/tests/integration/test_translation_constraints.py`
- `backend/tests/integration/test_translation_import_activation.py`
- `backend/tests/integration/test_translation_search.py`
- `backend/tests/unit/localization/importing/test_android_xml.py`
- `backend/tests/unit/localization/importing/test_conformance.py`
- `backend/tests/unit/localization/importing/test_contracts.py`
- `backend/tests/unit/localization/importing/test_ios_strings.py`
- `backend/tests/unit/localization/importing/test_json.py`
- `backend/tests/unit/localization/importing/test_output_budget.py`
- `backend/tests/unit/localization/importing/test_qt_ts.py`
- `backend/tests/unit/localization/importing/test_structure_bounds.py`
- `backend/tests/unit/localization/test_grapheme_count.py`
- `backend/tests/unit/services/test_mappings.py`
- `backend/tests/unit/test_phase4_parser_input_authority.py`
- `backend/tests/unit/test_phase4_public_error_boundaries.py`
- `backend/tests/unit/test_phase4_service_boundaries.py`
- `backend/tests/unit/test_phase4_worker_boundaries.py`
- `backend/tests/unit/test_preview_connection_authority.py`
- `backend/uv.lock`
- `frontend/e2e/admin-configuration.spec.ts`
- `frontend/e2e/translations.spec.ts`
- `frontend/openapi.json`
- `frontend/package-lock.json`
- `frontend/src/api/admin-client-contract.test.ts`
- `frontend/src/api/client/index.ts`
- `frontend/src/api/client/sdk.gen.ts`
- `frontend/src/api/client/types.gen.ts`
- `frontend/src/components/layout/AppShell.test.tsx`
- `frontend/src/features/admin/imports/PublishedMappingImports.test.tsx`
- `frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx`
- `frontend/src/features/admin/imports/useImportPolling.test.ts`
- `frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx`
- `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx`
- `frontend/src/features/translations/MaximumLengthDialog.test.tsx`
- `frontend/src/features/translations/TranslationDetailPage.test.tsx`
- `frontend/src/features/translations/TranslationFilters.test.tsx`
- `frontend/src/features/translations/TranslationResultList.test.tsx`
- `frontend/src/features/translations/TranslationSearchPage.test.tsx`
- `frontend/src/features/translations/translationPreferences.test.ts`
- `frontend/src/features/translations/useTranslationSearch.test.ts`
- `frontend/src/router.test.tsx`
- `tools/phase4_source_manifest.txt`
- `tools/tests/test_phase4_smoke.py`
- `tools/tests/test_phase4_smoke.sh`

## Historical first-pass evidence (immutable proof context)

The following retained narrative describes the first partial pass and its original source snapshot. Its old line numbers, counts and open dispositions are historical; the current sections above control the present disposition. No previous proof or remediation description has been discarded.

# Phase 04 code review — pending remediation

## Narrative Findings (AI reviewer)

Nine confirmed BLOCKER findings remain open pending independent recheck of fixes. This is an adversarial source review under the authorized GSD execute-phase workflow, not an old-coder blind verification. No implementation files were modified and no broad/shared tests were run by this reviewer.

## Scope and evidence status

Review base: `d987d5f48273d49234b07aacb3fa185337a1b4f2`; observed revision: `9f2312cbcdc3dba92b1a1c63a2d817e4f4c31692`. Other agents are adding tests and remediation. The source digest is deliberately pending until the final source freeze and fresh gauntlet/smoke. The file list records files inspected so far, including focused changed-function/cross-boundary inspection; it is not a claim that the entire approximately 91-file delivery scope has completed standard review. Remaining coverage must be reconciled against SUMMARY key-files and the actual diff before a passing verdict.

Read contracts include AGENTS.md, all D-01 through D-23 in 04-CONTEXT, parser/search/constraint contracts in 04-RESEARCH, Plan 20 Task 1, and relevant Plan 11/13 rules. The phase source manifest is the required final coverage authority. No structural pre-pass was supplied.

## Critical issues

| ID | File/line | Severity | Classification | Proof | Impact | Resolution | Remediation |
|---|---|---|---|---|---|---|---|
| CR-01 | `backend/src/verboflex/localization/importing/android_xml.py:413,492` | high | BLOCKER | Both collection loops pass the item to _mixed_content but do not validate item.tail. Direct production-registry reproduction with <item>A</item>LOST yields success and A; LOST is absent from canonical structure. | Unsupported source content is silently accepted, violating FMT-01 and D-04/D-05. | open | Reject non-whitespace tails for plural and array items; regress both through parse_canonical_snapshot and mapping atomic failure. |
| CR-02 | `backend/src/verboflex/services/translation_imports.py:508` | medium | BLOCKER | The external target-change branch is conditional on current review_state == approved. A rejected target with changed translated_text bypasses all reset branches and is updated with rejected. | D-10 and Plan 11 explicitly require every uncorrelated external translated-text change to become Draft; review state describes superseded content. | open | Reset every uncorrelated external target change to Draft, preserving only the exact proven approved-correlation exception. Regress rejected changed target, retained context and prior revision. |
| CR-03 | `backend/src/verboflex/services/translation_constraints.py:270,327` | high | BLOCKER | DELETE physically removes the rule; the next create always sets version=1. A stale client holding version 1 can subsequently replace or delete the newly created different rule. | Concurrent edits are silently lost despite the conflict contract; a stale destructive request acts on a different rule incarnation. | open | Maintain a durable generation across deletion or bind expected authority to rule identity. Regress create, delete, recreate, stale old PUT and DELETE returning conflict. |
| CR-04 | `backend/src/verboflex/services/translation_search.py:590` | medium | BLOCKER | Recomputation resolves the base rule across scope/raw_key, including the Keys repository. Detail joins base_rule only on the target anchor.key_id, which belongs to the Translations repository. | The API reports base_maximum=null despite inherited effective limits. MaximumLengthDialog falsely says removing an override leaves no limit, violating D-19 and authoritative mutation presentation. | open | Use the same unambiguous scope/raw-key base lookup in detail and recomputation; regress separate repository base default, target detail and removal copy. |
| CR-05 | `backend/src/verboflex/services/translation_search.py:305` | medium | BLOCKER | Cursor JSON embeds position.stable_key in full before enforcing 2048 characters. Direct _encode_cursor with 1600 ASCII key characters raises TranslationSearchInputError although raw keys allow 1,048,576 characters. | A normal page ending in such a key returns 422 instead of 50 results and continuation; violates SRCH-08/D-17. | open | Use a bounded signed anchor with server-resolved seek key and a digest of filters; preserve deterministic order, current dataset binding and long-key support. Regress 51 groups and Unicode/query expansion boundaries. |
| CR-06 | `backend/src/verboflex/services/translation_search.py:378` | medium | BLOCKER | normalize_search_query uses Python casefold; SQL uses lower plus only the sharp-s replacement. Independent local PostgreSQL SELECT for the ligature ﬀ returns ﬀ while Python casefold returns ff. | Searching an imported key by its identical ligature text returns no match; Unicode casefold/ranking promises in D-15 and Plan 13 fail. | open | Apply identical full Unicode normalization to query, key, source and target projections and corresponding indexes. Regress ligatures and final sigma across exact/prefix/partial tiers. |
| CR-07 | `backend/src/verboflex/schemas/translations.py:165` | high | BLOCKER | TranslationValueResponse permits 128 structure nodes; Android permits 4096 and Qt permits 256 locations plus other nodes. _value_response passes all nodes to the smaller schema. | Accepted imported records can raise response-model ValidationError outside the route's service try block, preventing detail and constraint workflows; violates FMT-07/SRCH-06/SRCH-07. | open | Align the response and canonical bounds without truncation. Regress parser-valid >128-node Android/Qt records through authenticated detail and generated schema. |
| CR-08 | `backend/src/verboflex/services/import_jobs.py:2793,2804` | high | BLOCKER | _confirmed_parser_inputs loops candidate.files from the persisted PreviewJob. New current-snapshot files are omitted; moved/deleted preview files cause an empty input result and failed import. | Production refresh cannot faithfully import file additions or preserve identities across key moves, despite synthetic reconciliation tests; violates D-05/D-08 and FMT-08. | open | Keep confirmed layout/format authority but rederive current file membership within that layout from the immutable snapshot. Regress production worker refresh with moved, added and removed files while preserving identities and atomicity. |
| CR-09 | `frontend/src/features/admin/previews/ProductPreviewPage.tsx:183,204` | high | BLOCKER | Both response-match helpers compare confirmation.preview_digest with the original result.digest. The backend now returns a different _complete_preview_digest that includes the selected base_language; the preview result digest omits that field. | A successful confirmation is always displayed as failure and never calls onConfirmed(true); publication/revalidation recovery remains blocked in the real browser. | open | Expose and validate original request digest separately from the new language-bound confirmation digest, or validate returned confirmation authority using exact identity fields and the new digest contract. Add realistic tests whose returned confirmation digest differs from the preview result, for both draft and active paths. |

### CR-01: Android collection item tails silently discarded

**Classification:** BLOCKER

**File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/localization/importing/android_xml.py:413,492`

**Issue:** Both collection loops pass the item to _mixed_content but do not validate item.tail. Direct production-registry reproduction with <item>A</item>LOST yields success and A; LOST is absent from canonical structure. Unsupported source content is silently accepted, violating FMT-01 and D-04/D-05.

**Fix:** Reject non-whitespace tails for plural and array items; regress both through parse_canonical_snapshot and mapping atomic failure.

### CR-02: External changes to rejected targets retain Rejected

**Classification:** BLOCKER

**File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/services/translation_imports.py:508`

**Issue:** The external target-change branch is conditional on current review_state == approved. A rejected target with changed translated_text bypasses all reset branches and is updated with rejected. D-10 and Plan 11 explicitly require every uncorrelated external translated-text change to become Draft; review state describes superseded content.

**Fix:** Reset every uncorrelated external target change to Draft, preserving only the exact proven approved-correlation exception. Regress rejected changed target, retained context and prior revision.

### CR-03: Delete and recreate reuses optimistic versions

**Classification:** BLOCKER

**File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/services/translation_constraints.py:270,327`

**Issue:** DELETE physically removes the rule; the next create always sets version=1. A stale client holding version 1 can subsequently replace or delete the newly created different rule. Concurrent edits are silently lost despite the conflict contract; a stale destructive request acts on a different rule incarnation.

**Fix:** Maintain a durable generation across deletion or bind expected authority to rule identity. Regress create, delete, recreate, stale old PUT and DELETE returning conflict.

### CR-04: Separate mapping detail loses base-rule authority

**Classification:** BLOCKER

**File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/services/translation_search.py:590`

**Issue:** Recomputation resolves the base rule across scope/raw_key, including the Keys repository. Detail joins base_rule only on the target anchor.key_id, which belongs to the Translations repository. The API reports base_maximum=null despite inherited effective limits. MaximumLengthDialog falsely says removing an override leaves no limit, violating D-19 and authoritative mutation presentation.

**Fix:** Use the same unambiguous scope/raw-key base lookup in detail and recomputation; regress separate repository base default, target detail and removal copy.

### CR-05: Accepted long keys overflow outgoing cursors

**Classification:** BLOCKER

**File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/services/translation_search.py:305`

**Issue:** Cursor JSON embeds position.stable_key in full before enforcing 2048 characters. Direct _encode_cursor with 1600 ASCII key characters raises TranslationSearchInputError although raw keys allow 1,048,576 characters. A normal page ending in such a key returns 422 instead of 50 results and continuation; violates SRCH-08/D-17.

**Fix:** Use a bounded signed anchor with server-resolved seek key and a digest of filters; preserve deterministic order, current dataset binding and long-key support. Regress 51 groups and Unicode/query expansion boundaries.

### CR-06: Database normalization disagrees with full Unicode casefold

**Classification:** BLOCKER

**File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/services/translation_search.py:378`

**Issue:** normalize_search_query uses Python casefold; SQL uses lower plus only the sharp-s replacement. Independent local PostgreSQL SELECT for the ligature ﬀ returns ﬀ while Python casefold returns ff. Searching an imported key by its identical ligature text returns no match; Unicode casefold/ranking promises in D-15 and Plan 13 fail.

**Fix:** Apply identical full Unicode normalization to query, key, source and target projections and corresponding indexes. Regress ligatures and final sigma across exact/prefix/partial tiers.

### CR-07: Detail structure cap rejects parser-valid records

**Classification:** BLOCKER

**File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/schemas/translations.py:165`

**Issue:** TranslationValueResponse permits 128 structure nodes; Android permits 4096 and Qt permits 256 locations plus other nodes. _value_response passes all nodes to the smaller schema. Accepted imported records can raise response-model ValidationError outside the route's service try block, preventing detail and constraint workflows; violates FMT-07/SRCH-06/SRCH-07.

**Fix:** Align the response and canonical bounds without truncation. Regress parser-valid >128-node Android/Qt records through authenticated detail and generated schema.

### CR-08: Refresh parses frozen preview filenames

**Classification:** BLOCKER

**File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/services/import_jobs.py:2793,2804`

**Issue:** _confirmed_parser_inputs loops candidate.files from the persisted PreviewJob. New current-snapshot files are omitted; moved/deleted preview files cause an empty input result and failed import. Production refresh cannot faithfully import file additions or preserve identities across key moves, despite synthetic reconciliation tests; violates D-05/D-08 and FMT-08.

**Fix:** Keep confirmed layout/format authority but rederive current file membership within that layout from the immutable snapshot. Regress production worker refresh with moved, added and removed files while preserving identities and atomicity.

### CR-09: Successful preview confirmations are rejected by the browser

**Classification:** BLOCKER (high)

**File:** `/Users/smutti/Documents/personal/verboflex/frontend/src/features/admin/previews/ProductPreviewPage.tsx:183,204`

**Issue:** Both response-match helpers compare confirmation.preview_digest with the original result.digest. The backend now returns a different _complete_preview_digest that includes the selected base_language; the preview result digest omits that field. A successful confirmation is always displayed as failure and never calls onConfirmed(true); publication/revalidation recovery remains blocked in the real browser.

**Fix:** Expose and validate original request digest separately from the new language-bound confirmation digest, or validate returned confirmation authority using exact identity fields and the new digest contract. Add realistic tests whose returned confirmation digest differs from the preview result, for both draft and active paths.

## Exact diagnostic evidence

- Read-only `uv run --project backend python -c ...` invoked the production Android registry on plural and array inputs with item tail `LOST`: both returned zero issues and display `A`.
- Read-only direct `_encode_cursor` with a 1600-character ASCII stable key raised `TranslationSearchInputError: cursor exceeds its allowed bound`.
- Read-only local PostgreSQL `SELECT lower('ﬀ'), replace(lower('ﬀ'), 'ß', 'ss')` returned `('ﬀ', 'ﬀ')`; Python `'ﬀ'.casefold()` returned `ff`.
- Other findings are traced executable control-flow or producer/consumer contract contradictions. Focused integration regressions are delegated to the implementation owners; their existence or success will not be presumed until rechecked.

## Remaining review scope

The standard review is handed back for remediation without claiming full coverage. The listed files include full reads of new parser/search/constraint/frontend modules and migration, plus focused changed-function and cross-boundary reads of large existing modules. The remaining pass must finish complete reads of large preview/import modules, delivery tools (phase4_gate.py, phase4_smoke.py, phase4_smoke_browser.mjs, phase4_parser_checkpoint.sh), generated SDK/types/OpenAPI and lock identity crosschecks, and the complete behavioral-test diff/fixtures. Current behavioral tests were inspected selectively for reconciliation, constraints and search, not exhaustively. Planning contracts were read by relevant requirements/decisions; remaining full planning/UI-SPEC and manifest reconciliation must not be represented as completed.

Severity is separate from release priority: CR-01/03/07/08/09 are high; CR-02/04/05/06 are medium. All nine remain BLOCKER because they demonstrably violate required behavior. The canonical GSD critical count records the mandatory BLOCKER tier; the normalized table carries impact severity.

## Additional checks pending disposition

Constraint mutations currently change the violation projection without changing the dataset_version used in cursor authority. Confirm whether complete dataset binding requires rejection of pre-mutation filtered cursors; do not promote this candidate to a formal finding without the explicit contract and reproduction. Android display quote/whitespace semantics and PostgreSQL long-key index entry limits also need exact contract/proof before a finding.

## Closure conditions

Keep status pending until all confirmed findings are fixed and independently rechecked; complete the remaining standard-depth source and behavioral-test review; map all 20 requirement IDs and D-01 through D-23 to source evidence; reconcile the exact reviewed file scope; and bind both review artifacts to the same fresh post-gauntlet source digest as delivery/security evidence. A passed Docker smoke or an independent UI audit does not close these code defects.
