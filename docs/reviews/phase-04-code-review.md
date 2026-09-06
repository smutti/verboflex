---
phase: 04-localization-import-search-and-constraints
reviewed: 2026-09-06T10:16:26Z
depth: standard
reviewer: gsd-code-reviewer
status: pending
source_digest: pending-post-gauntlet-freeze
files_reviewed: 69
files_reviewed_list:
  - backend/alembic/versions/0011_active_revision_revalidations.py
  - backend/alembic/versions/0012_import_jobs.py
  - backend/alembic/versions/0015_mapping_base_language.py
  - backend/alembic/versions/0016_canonical_translations.py
  - backend/alembic/versions/0017_translation_search_indexes.py
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
  - tools/phase4_gauntlet.sh
  - tools/phase4_inventory.py
  - tools/phase4_smoke.sh
  - tools/verify_phase4_closeout.py
  - tools/verify_phase4_npm.mjs
  - tools/verify_translation_mutants.py
findings:
  critical: 9
  warning: 0
  info: 0
  total: 9
---
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
