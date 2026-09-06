---
phase: 04-localization-import-search-and-constraints
reviewed: 2026-09-06T12:16:13Z
depth: standard
reviewer: gsd-code-reviewer
status: passed
source_digest: sha256:2df3766ead7f1aea3597a8ad8b99205f14508a4189109996149265a163017b3a
files_reviewed: 172
files_reviewed_list:
  - backend/alembic/versions/0011_active_revision_revalidations.py
  - backend/alembic/versions/0012_import_jobs.py
  - backend/alembic/versions/0015_mapping_base_language.py
  - backend/alembic/versions/0016_canonical_translations.py
  - backend/alembic/versions/0017_translation_search_indexes.py
  - backend/alembic/versions/0018_constraint_generation.py
  - backend/alembic/versions/0019_unicode_search_indexes.py
  - backend/alembic/versions/0020_bounded_key_identities.py
  - backend/alembic/versions/0021_retained_baseline_constraint_epoch.py
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
  - backend/tests/api/test_admin_mappings.py
  - backend/tests/api/test_admin_previews.py
  - backend/tests/api/test_openapi_contract.py
  - backend/tests/api/test_phase4_failure_boundaries.py
  - backend/tests/api/test_translation_constraints.py
  - backend/tests/api/test_translation_error_union.py
  - backend/tests/api/test_translation_structure_roundtrip.py
  - backend/tests/api/test_translations.py
  - backend/tests/architecture/test_background_boundaries.py
  - backend/tests/architecture/test_phase2_gap_closure.py
  - backend/tests/architecture/test_phase2_scope.py
  - backend/tests/architecture/test_phase3_scope.py
  - backend/tests/architecture/test_phase4_checkpoint_redaction.py
  - backend/tests/architecture/test_phase4_closeout_gate.py
  - backend/tests/architecture/test_phase4_gauntlet.py
  - backend/tests/architecture/test_phase4_license_policy.py
  - backend/tests/architecture/test_phase4_scope.py
  - backend/tests/architecture/test_translation_mutation_verifier.py
  - backend/tests/fixtures/localization/android/invalid_cases.json
  - backend/tests/fixtures/localization/android/manifest.json
  - backend/tests/fixtures/localization/android/scalar.expected.json
  - backend/tests/fixtures/localization/android/scalar.xml
  - backend/tests/fixtures/localization/android/valid_structured.expected.json
  - backend/tests/fixtures/localization/android/valid_structured.xml
  - backend/tests/fixtures/localization/conformance/direct.json
  - backend/tests/fixtures/localization/conformance/manifest.json
  - backend/tests/fixtures/localization/conformance/separate.json
  - backend/tests/fixtures/localization/ios/invalid_cases.json
  - backend/tests/fixtures/localization/ios/manifest.json
  - backend/tests/fixtures/localization/ios/valid.expected.json
  - backend/tests/fixtures/localization/ios/valid.strings
  - backend/tests/fixtures/localization/json/invalid_cases.json
  - backend/tests/fixtures/localization/json/manifest.json
  - backend/tests/fixtures/localization/json/valid_nested.expected.json
  - backend/tests/fixtures/localization/json/valid_nested.json
  - backend/tests/fixtures/localization/qt/invalid_cases.json
  - backend/tests/fixtures/localization/qt/manifest.json
  - backend/tests/fixtures/localization/qt/valid_structured.expected.json
  - backend/tests/fixtures/localization/qt/valid_structured.ts
  - backend/tests/integration/test_bounded_key_identities.py
  - backend/tests/integration/test_confirmed_layout_refresh.py
  - backend/tests/integration/test_constraint_activation_race.py
  - backend/tests/integration/test_constraint_generation_migration.py
  - backend/tests/integration/test_import_jobs.py
  - backend/tests/integration/test_import_status_activation_race.py
  - backend/tests/integration/test_migrations.py
  - backend/tests/integration/test_phase4_search_regressions.py
  - backend/tests/integration/test_preview_jobs.py
  - backend/tests/integration/test_product_publication.py
  - backend/tests/integration/test_retained_baseline_constraint_epoch.py
  - backend/tests/integration/test_structured_group_deletion.py
  - backend/tests/integration/test_translation_constraints.py
  - backend/tests/integration/test_translation_import_activation.py
  - backend/tests/integration/test_translation_search.py
  - backend/tests/unit/localization/importing/test_android_xml.py
  - backend/tests/unit/localization/importing/test_conformance.py
  - backend/tests/unit/localization/importing/test_contracts.py
  - backend/tests/unit/localization/importing/test_ios_strings.py
  - backend/tests/unit/localization/importing/test_json.py
  - backend/tests/unit/localization/importing/test_output_budget.py
  - backend/tests/unit/localization/importing/test_qt_ts.py
  - backend/tests/unit/localization/importing/test_structure_bounds.py
  - backend/tests/unit/localization/test_grapheme_count.py
  - backend/tests/unit/services/test_mappings.py
  - backend/tests/unit/test_phase4_parser_input_authority.py
  - backend/tests/unit/test_phase4_public_error_boundaries.py
  - backend/tests/unit/test_phase4_service_boundaries.py
  - backend/tests/unit/test_phase4_worker_boundaries.py
  - backend/tests/unit/test_preview_connection_authority.py
  - backend/uv.lock
  - frontend/e2e/admin-configuration.spec.ts
  - frontend/e2e/translations.spec.ts
  - frontend/openapi.json
  - frontend/package-lock.json
  - frontend/package.json
  - frontend/src/api/admin-client-contract.test.ts
  - frontend/src/api/client/index.ts
  - frontend/src/api/client/sdk.gen.ts
  - frontend/src/api/client/types.gen.ts
  - frontend/src/components/layout/AppShell.test.tsx
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
  - frontend/src/features/admin/imports/PublishedMappingImports.test.tsx
  - frontend/src/features/admin/imports/PublishedMappingImports.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx
  - frontend/src/features/admin/imports/useImportPolling.test.ts
  - frontend/src/features/admin/imports/useImportPolling.ts
  - frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx
  - frontend/src/features/admin/previews/ProductPreviewPage.test.tsx
  - frontend/src/features/admin/previews/ProductPreviewPage.tsx
  - frontend/src/features/translations/MaximumLengthDialog.test.tsx
  - frontend/src/features/translations/MaximumLengthDialog.tsx
  - frontend/src/features/translations/TranslationDetailPage.test.tsx
  - frontend/src/features/translations/TranslationDetailPage.tsx
  - frontend/src/features/translations/TranslationFilters.test.tsx
  - frontend/src/features/translations/TranslationFilters.tsx
  - frontend/src/features/translations/TranslationResultList.test.tsx
  - frontend/src/features/translations/TranslationResultList.tsx
  - frontend/src/features/translations/TranslationSearchPage.test.tsx
  - frontend/src/features/translations/TranslationSearchPage.tsx
  - frontend/src/features/translations/TranslationsWorkspace.tsx
  - frontend/src/features/translations/translationDetailAuthority.ts
  - frontend/src/features/translations/translationFilterLabels.ts
  - frontend/src/features/translations/translationPreferences.test.ts
  - frontend/src/features/translations/translationPreferences.ts
  - frontend/src/features/translations/useTranslationSearch.test.ts
  - frontend/src/features/translations/useTranslationSearch.ts
  - frontend/src/router.test.tsx
  - frontend/src/router.tsx
  - tools/phase4_gate.py
  - tools/phase4_gauntlet.sh
  - tools/phase4_inventory.py
  - tools/phase4_parser_checkpoint.sh
  - tools/phase4_smoke.py
  - tools/phase4_smoke.sh
  - tools/phase4_smoke_browser.mjs
  - tools/phase4_source_manifest.txt
  - tools/tests/test_phase4_smoke.py
  - tools/tests/test_phase4_smoke.sh
  - tools/verify_phase4_closeout.py
  - tools/verify_phase4_npm.mjs
  - tools/verify_translation_mutants.py
findings:
  critical: 6
  warning: 10
  info: 0
  total: 16
---
# Phase 04 — Independent code review

## Narrative Findings (AI reviewer)

All sixteen classified findings have independently inspected corrections and passing behavioral regressions. The final bounded CR-15/CR-16 recheck proves Product-first constraint serialization and permits only exact, authentic retained-baseline epoch changes. No unresolved source BLOCKER remains. This code review passes on the exact source and completed automated delivery evidence below; it does not waive the separate human UAT or mark the phase complete.

Severity normalization: six high (CR-01/03/07/08/09/11), ten medium (CR-02/04/05/06/10/12/13/14/15/16), zero critical-impact findings. All sixteen carry BLOCKER classifications because they violated required behavior or the closeout trust boundary. The historical frontmatter `critical` bucket includes high impact; `warning` includes medium impact. Counts retain discovered findings, not current unresolved defects. Historical first-pass nine-Critical bucket was five high/four medium, not nine critical-impact findings.

## Scope and method

Exact prephase base: `d987d5f48273d49234b07aacb3fa185337a1b4f2`. Final observed source revision: `231e5b1e2e574af8c38873ddcdb31e0ebca75c58`; last production changes `4ee6ee0` and `231e5b1`. The source digest includes tracked/unignored backend/frontend/tools, tests, generated artifacts, locks and delivery configuration; it excludes review/evidence/planning to avoid self-reference. The current digest was independently reread after the completed gauntlet and matches the evidence and review ledgers.

The full diff inventory is **172 paths**, reconciled to the frontmatter list with no missing or extra path. This is a cumulative standard per-file source/diff review: new implementation and test files were read; changes to pre-existing large services/tests were read with called-function, fixture and import context. Earlier selective inspection was extended across all omitted generated/client, package/lock, delivery-control and behavioral-test paths. It is not a claim of a fresh audit of every unchanged line of the prephase application.

Required context includes AGENTS.md, config, agent-skills bootstrap, complete Phase 04 CONTEXT/UI-SPEC/RESEARCH/Plan 20, source manifest and prior reviews. No project skills or structural pre-pass were present. GSD code review governed the read-only source scope and report disposition; API-contract review guidance prompted the real wire-versus-generated 422 check (CR-13). The existing graph was only a navigation aid, not proof.

No production/test files, shared application data or provider state were changed by this reviewer. Diagnostic database fixtures create/drop only uniquely named disposable test databases. Reports are the only owned edits. Package/network tools were not used to write externally.

## Normalized findings and resolution

File/line references in these rows identify the first independently observed defect; the remediation column identifies corrected source and executable recheck. Historical proofs below retain their original source snapshots.

| ID | File/line | Severity | Classification | Proof | Impact | Resolution | Remediation |
|---|---|---|---|---|---|---|---|
| CR-01 | `backend/src/verboflex/localization/importing/android_xml.py:413,492` | high | BLOCKER | Both collection loops pass the item to _mixed_content but do not validate item.tail. Direct production-registry reproduction with <item>A</item>LOST yields success and A; LOST is absent from canonical structure. | Unsupported source content is silently accepted, violating FMT-01 and D-04/D-05. | resolved | 9f2312c; four plural/array non-whitespace tail registry cases return no values and unsupported_structure; peer-file atomic and conformance cases pass (R1). Original remediation retained in historical proof below. |
| CR-03 | `backend/src/verboflex/services/translation_constraints.py:270,327` | high | BLOCKER | DELETE physically removes the rule; the next create always sets version=1. A stale client holding version 1 can subsequently replace or delete the newly created different rule. | Concurrent edits are silently lost despite the conflict contract; a stale destructive request acts on a different rule incarnation. | resolved | 05dfbe9 / migration 0018; durable key generation survives deletion; both stale PUT/DELETE after recreate conflict without changing new maximum 8; migration generation test passes (R1/R3). Original remediation retained in historical proof below. |
| CR-07 | `backend/src/verboflex/schemas/translations.py:165` | high | BLOCKER | TranslationValueResponse permits 128 structure nodes; Android permits 4096 and Qt permits 256 locations plus other nodes. _value_response passes all nodes to the smaller schema. | Accepted imported records can raise response-model ValidationError outside the route's service try block, preventing detail and constraint workflows; violates FMT-07/SRCH-06/SRCH-07. | resolved | 497b431; shared 16,384-node response bound preserves parser-valid Android/Qt/iOS structures through authenticated real detail (R3), with exact OpenAPI assertion. Original remediation retained in historical proof below. |
| CR-08 | `backend/src/verboflex/services/import_jobs.py:2793,2804` | high | BLOCKER | _confirmed_parser_inputs loops candidate.files from the persisted PreviewJob. New current-snapshot files are omitted; moved/deleted preview files cause an empty input result and failed import. | Production refresh cannot faithfully import file additions or preserve identities across key moves, despite synthetic reconciliation tests; violates D-05/D-08 and FMT-08. | resolved | 268d9c5; confirmed layout constrains current immutable snapshot membership; actual worker refresh accepts move/new locale and rejects malformed new files while retaining previous dataset (R1). Original remediation retained in historical proof below. |
| CR-09 | `frontend/src/features/admin/previews/ProductPreviewPage.tsx:183,204` | high | BLOCKER | Both response-match helpers compare confirmation.preview_digest with the original result.digest. The backend now returns a different _complete_preview_digest that includes the selected base_language; the preview result digest omits that field. | A successful confirmation is always displayed as failure and never calls onConfirmed(true); publication/revalidation recovery remains blocked in the real browser. | resolved | a691ab3; unequal c-preview/d-language-bound confirmation digests accepted only with matching job/mapping/candidate/base and active-generation authority; draft and active real component regressions pass (R2). Original remediation retained in historical proof below. |
| CR-11 | `tools/verify_phase4_closeout.py:132` | high | BLOCKER | Independently invoked validate_document with SECURED, a valid-looking digest and only T1/high/mitigate/placeholder.py:1/resolved. It returned SECURED with zero required threat IDs. | The promised automated gate can accept omitted high threats; T-04-62/T-04-64 and Plan 20 exact security replay fail. | resolved | af0b9da; validator compares all 78 registered IDs exactly once and authoritative severity/disposition from plans, rejecting omission, duplicate, fabricated/downgraded rows and inconsistent plan duplicates. Independently passed R3. |
| CR-02 | `backend/src/verboflex/services/translation_imports.py:508` | medium | BLOCKER | The external target-change branch is conditional on current review_state == approved. A rejected target with changed translated_text bypasses all reset branches and is updated with rejected. | D-10 and Plan 11 explicitly require every uncorrelated external translated-text change to become Draft; review state describes superseded content. | resolved | 6acf763; real PostgreSQL rejected target refresh keeps key/value UUID and prior Ciao revision, accepts Nuovo as Draft (R3). Original remediation retained in historical proof below. |
| CR-04 | `backend/src/verboflex/services/translation_search.py:590` | medium | BLOCKER | Recomputation resolves the base rule across scope/raw_key, including the Keys repository. Detail joins base_rule only on the target anchor.key_id, which belongs to the Translations repository. | The API reports base_maximum=null despite inherited effective limits. MaximumLengthDialog falsely says removing an override leaves no limit, violating D-19 and authoritative mutation presentation. | resolved | 2022ea9; scope/raw-key base lookup agrees with recomputation across Keys/Translations repositories; base 3, override 8, removal restores base 3 (R1); API/detail/dialog projection suites pass (R4/R5). Original remediation retained in historical proof below. |
| CR-05 | `backend/src/verboflex/services/translation_search.py:305` | medium | BLOCKER | Cursor JSON embeds position.stable_key in full before enforcing 2048 characters. Direct _encode_cursor with 1600 ASCII key characters raises TranslationSearchInputError although raw keys allow 1,048,576 characters. | A normal page ending in such a key returns 422 instead of 50 results and continuation; violates SRCH-08/D-17. | resolved | 9cdb137 / 2b3b0d6; signed v2 cursor carries filter hash and bounded rank/locale/UUID, SQL resolves exact current seek key; long-key paging and maximum Unicode/escaped-filter wire invariant pass (R1). Original remediation retained in historical proof below. |
| CR-06 | `backend/src/verboflex/services/translation_search.py:378` | medium | BLOCKER | normalize_search_query uses Python casefold; SQL uses lower plus only the sharp-s replacement. Independent local PostgreSQL SELECT for the ligature ﬀ returns ﬀ while Python casefold returns ff. | Searching an imported key by its identical ligature text returns no match; Unicode casefold/ranking promises in D-15 and Plan 13 fail. | resolved | 676f71c / migration 0019; PostgreSQL 18 pg_unicode_fast casefold aligns all fields; ligature/final-sigma exact/prefix/partial plus index migration cases pass (R1). Original remediation retained in historical proof below. |
| CR-10 | `backend/src/verboflex/services/translation_search.py:421,449,791` | medium | BLOCKER | Production search/detail on a disposable migrated PostgreSQL fixture with two array values, one tombstoned, returned active_groups=0, deleted_groups=1, detail_deleted=True, retained_active_values=1. | Removing one variant hides the live siblings from normal search and disables the group's constraint UI. Tombstoned minimum UUID also disagrees with mutation's minimum-live anchor. | resolved | 1ecc596 / 64a5e38; actual two-language Android refresh tombstones the minimum UUID but preserves live group/search/constraint authority; active query/state/violation ignores retired matches, all-mode retains history; all-target deletion rejects mutation. Independently passed R1/R4. |
| CR-12 | `frontend/src/features/translations/TranslationSearchPage.tsx:450,461`; `frontend/src/features/translations/useTranslationSearch.ts:280` | medium | BLOCKER | Back restores a saved snapshot while options await. The editable pending query is passed as initialQuery, but validScope checks only product/language and restoreSnapshot returns snapshot.query. A read-only transpile/VM probe returned enteredQuery=new, restoredQuery=old. | User input entered during options loading is overwritten with the old query and old results. | resolved | 645219c; current query must equal saved snapshot query before restoration; real Back + deferred options tests exercise changed query and cleared query, request fresh results, and retain unchanged Back restoration. Independently passed R2. |
| CR-13 | `backend/src/verboflex/api/v1/routes/translations.py:54`; `backend/src/verboflex/api/v1/routes/translation_constraints.py:66`; `frontend/src/api/client/types.gen.ts:4431` | medium | BLOCKER | Plain FastAPI routes return framework validation detail arrays, but all three 422 schemas/generated errors declared only domain detail strings; actual invalid page_size/body tests expose mismatch. | Typed API consumers receive an undocumented error shape for valid framework rejection; schema contract and runtime disagree. | resolved | 47a33ad: explicit anyOf domain error plus HTTPValidationError for search/PUT/DELETE only; six real HTTP validation/domain cases, exact schema refs, generated-client unions independently checked and passed (R3). |

| CR-14 | `backend/src/verboflex/services/import_jobs.py:1038,1315` | medium | BLOCKER | Real worker activation between job and mapping/scope reads mixed a stale running job with the new active dataset, causing detail HTTP 500 or collection current/not_created. | Routine polling fails during a successful import; the status API contradicts its active dataset. | resolved | ec6fd68 takes Product SHARE before both polling authority snapshots, matching worker Product-first locking. Four actual HTTP detail/collection × same/cross-product interleavings prove coherent results and only same-product blocking; R7 independently passed. |
| CR-15 | `backend/src/verboflex/services/translation_constraints.py:449,457`; `backend/src/verboflex/services/import_jobs.py:1852,1862` | medium | BLOCKER | Actual constraint service locks scope then mapping; actual activation locks Product then mapping then scope. A migrated PostgreSQL fixture and deterministic after-lock barriers produced psycopg DeadlockDetected, with process 85607 waiting on transaction 203680 held by 85608 and the reverse wait on 203679. | An ordinary constraint save concurrent with refresh fails HTTP 503; activation may instead be chosen as the deadlock victim. This is an actual cyclic wait, not a speculative order difference or a defect caused by polling SHARE. | resolved | 4ee6ee0: Product SHARE precedes scope/mapping; fresh product/scope/key/anchor reads fence concurrent activation, inactive product and changed published revision. Real PUT/DELETE × same/cross-product worker interleavings assert blocking occurs before the worker mapping lock and both operations finish; inactive/unpublished preloads are rejected (R8). |
| CR-16 | `backend/alembic/versions/0016_canonical_translations.py:63,1001`; `backend/src/verboflex/services/translation_constraints.py:290` | medium | BLOCKER | Without threads or concurrent worker activity, activate JSON, start/stage a refresh, read the retained group successfully, then call put_translation_constraint. Its dataset_version update raises psycopg ForeignKeyViolation: localization scope activation authority violation. The ANY UPDATE trigger requires job=current/current_execution=active execution even when only the retained dataset epoch changes. | Every changed constraint save against the visible retained baseline fails while refresh is running; Product lock serialization alone cannot correct this mismatch. | resolved | 231e5b1 / migration 0021: only full-row-identical authority with exact +1 epoch and authentic succeeded baseline plus coherent current job/execution enters the exception. Original activation predicate and downgrade remain intact. Queued/running/failed/reconciliation PUT/DELETE/no-op, every authority-column tamper, wrong epoch/baseline/sequence and two down/up cycles pass; original isolated running-refresh reproduction now succeeds (R8). |

## Subsystem adversarial checks

- **Parsers and resources:** all four format adapters, immutable typed selector contracts, registry joins, safe taxonomy, explicit golden byte/structure fixtures and bounded output. `CanonicalValueBuffer` accounts incremental canonical UTF-8 JSON expansion (source bytes + 20 MiB, at most 40 MiB mapping) in adapters, peer aggregation and post-join output. Budget overflow is an atomic error; no silent truncation. Android tails and large API structures were corrected rather than waived.
- **Persistence and concurrency:** migrations 0015–0021, stable natural-key/FK ownership, immutable staging/history, exact manifest/provenance, atomic normal/rewrite activation, last-success rollback, mapping clone, move/rename, orphan tombstone non-revival and external state transitions. Product-first shared constraint locking prevents the reproduced activation inversion and refreshes tentative authority before mutation. Migration 0021 permits exact retained-baseline epoch changes without widening activation identity authority; migration 0018 preserves a durable optimistic epoch; 0020 bounds raw-key indexes without changing exact text; downgrade failure remains transactional when older index limits cannot represent current data.
- **Search and constraints:** bound SQL and escaped literal patterns, Unicode casefold/index agreement, scope/dataset/filter cursor binding, exact database anchor resolution, fixed page bounds, stable minimum UUID across mixed deletions, and canonical live-member eligibility. Cross-side base-rule projection agrees with recomputation. No-op mutation and rollback do not advance the dataset epoch; changed rule state does.
- **API/generated contracts:** every new route uses current bearer authority; exact all-role read and Admin/PM-reviewer mutation matrix. Missing/inaccessible/non-anchor IDs do not enumerate. Closed public schemas expose no source bytes/provider diagnostics. Checked-in OpenAPI, SDK exports/types, strict request/response bounds and all three framework/domain 422 unions were compared against actual HTTP behavior.
- **Frontend/accessibility:** pending/current generations, token/filter/debounce transitions, Back snapshot validity, stale success/failure no-ops, current options, principal-scoped preference allowlist, bounded virtual DOM/dynamic measurement, keyboard load/retry and focus restoration. Detail and dialogs retain entered values on conflict, require explicit replacement/removal, prevent duplicate/pending dismissal, keep untrusted text inert and preserve full readable content. Shared shadcn changes retain contract sizes, reduced motion and semantics.
- **Delivery and packages:** all gate/smoke/source-inventory/mutation/npm/license tools and tests reviewed. Exact `regex==2026.9.3`, `@tanstack/react-virtual@3.14.10` and transitive virtual-core pins/official registry lock integrity match the approved phase contract. The automated security gate now binds all 78 threat rows to registered severity/disposition, including consistent shared T-04-SC duplicates in plans. T-04-20 raw checkpoint failure logging was independently rechecked after 5758d65: only label/exit/digest is emitted and its owned raw log is removed (R6).
- **Tests and scope:** new assertions exercise returned values, persistence, currentness, role denial, retries and real API shapes rather than merely function existence. Inventory equality tests are treated only as inventory; behavioral suites provide the proof. E2E uses an explicit mocked API for browser composition and is not represented as a live Bitbucket end-to-end import. Translation editing, comments, review-state mutation and provider writes remain deferred.

The FE guard refactor `ea8a414` was traced through state writers: validated snapshot/page establishes cursor authority; query edits clear it synchronously; filter/token changes enter initial loading; post-await generation/identity/cursor checks remain. The outgoing encoder branch removed by `2b3b0d6` was unreachable for SQL-issued rank 0..3, canonical ASCII locale ≤12, UUID and two SHA-256 digests; maximum Unicode query/escaped filter data is hashed, not embedded. Decoder's untrusted 2048-character bound remains.

## Requirement and decision trace

All **20 requirements and 23 decisions** below were traced through shipped source and meaningful test assertions. “Reviewed” is independent code disposition; the same-digest automated full gate/smoke has passed. Human judgment remains separately required. No row is inferred from a plan-completion checkbox. Module entry points are exact manifest selectors; behavioral evidence describes what their assertions actually exercise.

| Kind | ID | Delivery source | Executable test entry points | Behavioral evidence | Disposition |
|---|---|---|---|---|---|
| DECISION | D-01 | `backend/src/verboflex/localization/importing/android_xml.py` | `backend/tests/unit/localization/importing/test_android_xml.py` | All four adapters preserve scalar/structured variants; Qt/Android variants and JSON nested leaves have golden assertions. | reviewed; automated delivery passed |
| DECISION | D-02 | `backend/src/verboflex/localization/importing/android_xml.py` | `backend/tests/unit/localization/importing/test_android_xml.py` | Typed sibling selectors remain distinct; grouped search/detail return each value, including mixed live/deleted siblings (CR-10). | reviewed; automated delivery passed |
| DECISION | D-03 | `backend/src/verboflex/localization/importing/core.py` | `backend/tests/unit/localization/importing/test_contracts.py` | Canonical selector bytes preserve ordered typed fields; raw keys remain unsplit, case-sensitive, and bounded-index hashing retains exact text. | reviewed; automated delivery passed |
| DECISION | D-04 | `backend/src/verboflex/localization/importing/registry.py` | `backend/tests/unit/localization/importing/test_conformance.py` | Markup/text/tails/attributes are represented or rejected; CR-01 tail cases and canonical output-budget failures never produce partial values. | reviewed; automated delivery passed |
| DECISION | D-05 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | Malformed/unsupported input yields no staged active values; activation failure retains dataset/baseline, including newly discovered malformed files. | reviewed; automated delivery passed |
| DECISION | D-06 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | Both repository sides stage and activate together; registry one-side failure returns no joined values. | reviewed; automated delivery passed |
| DECISION | D-07 | `backend/src/verboflex/models/translation.py` | `backend/tests/integration/test_migrations.py`, `backend/tests/unit/localization/importing/test_contracts.py` | Natural-key uniqueness and FKs cover scope/repository/branch/key/language/selector; moves and semantic mapping clones keep UUIDs. | reviewed; automated delivery passed |
| DECISION | D-08 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | Path-only move retains UUID/state/constraint/history; key rename produces unrelated new Draft plus tombstone. | reviewed; automated delivery passed |
| DECISION | D-09 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | Deleted groups remain detail-readable with provenance/history; active group uses all-members deletion, not any-member deletion. | reviewed; automated delivery passed |
| DECISION | D-10 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | Uncorrelated changed Approved or Rejected targets become Draft, retain UUIDs and previous revision (CR-02). | reviewed; automated delivery passed |
| DECISION | D-11 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | Only exact persisted correlation plus value-revision match preserves Approved; equal untracked current text does not. | reviewed; automated delivery passed |
| DECISION | D-12 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | Source change returns targets to Draft without replacing target text or deleting review history. | reviewed; automated delivery passed |
| DECISION | D-13 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | Immutable correlation fields/digests and execution provenance remain future seams; no provider write or future workflow route is exposed. | reviewed; automated delivery passed |
| DECISION | D-14 | `frontend/src/features/translations/TranslationSearchPage.tsx` | `frontend/src/features/translations/TranslationSearchPage.test.tsx` | Principal-scoped remembered product is checked against live options; unauthorized/stale choice falls back to All products. | reviewed; automated delivery passed |
| DECISION | D-15 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | Literal key/source/display matching uses PostgreSQL full casefold; exact precedes prefix/partial and wildcard characters remain literal (CR-06). | reviewed; automated delivery passed |
| DECISION | D-16 | `frontend/src/features/translations/TranslationSearchPage.tsx` | `frontend/src/features/translations/TranslationSearchPage.test.tsx` | Remembered language is revalidated for current product; changing product clears unavailable language before search. | reviewed; automated delivery passed |
| DECISION | D-17 | `frontend/src/features/translations/useTranslationSearch.ts` | `frontend/src/features/translations/useTranslationSearch.test.ts` | 50-group signed cursors bind scope/filter/dataset and bounded SQL anchor; frontend generations and query-aware Back invalidate stale chains (CR-05/12). | reviewed; automated delivery passed |
| DECISION | D-18 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | Exactly five filters; active state/violation/query matching ignores deleted siblings while complete group history stays accessible (CR-10). | reviewed; automated delivery passed |
| DECISION | D-19 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | Base rule dynamically crosses matching repository-side keys; target override remains independent and deletion restores inheritance (CR-04). | reviewed; automated delivery passed |
| DECISION | D-20 | `backend/src/verboflex/localization/graphemes.py` | `backend/tests/unit/localization/test_grapheme_count.py` | Pinned regex extended graphemes count combining/ZWJ/flag/CRLF without normalization; markup is excluded from display count. | reviewed; automated delivery passed |
| DECISION | D-21 | `backend/src/verboflex/api/v1/routes/translation_constraints.py` | `backend/tests/api/test_translation_constraints.py` | Real HTTP role matrix grants Admin/PM-reviewer only; viewer/translator read and cannot write. | reviewed; automated delivery passed |
| DECISION | D-22 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | Over-limit content remains readable Draft; server projection sets approval/submission eligibility false; no deferred workflow mutation is enabled. | reviewed; automated delivery passed |
| DECISION | D-23 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | Import, base/override PUT/DELETE and edit seam share transactional recomputation; changed rules advance dataset epoch, no-op/rollback do not. | reviewed; automated delivery passed |
| REQ | CONS-01 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | Inclusive strict integer 0..1,048,576 rule creation, typed server authority and role enforcement. | reviewed; automated delivery passed |
| REQ | CONS-02 | `backend/src/verboflex/api/v1/routes/translation_constraints.py` | `backend/tests/api/test_translation_constraints.py` | Transactional PUT/DELETE, no-op idempotency, concurrent winner/conflict and generation surviving delete/recreate (CR-03). | reviewed; automated delivery passed |
| REQ | CONS-03 | `backend/src/verboflex/localization/graphemes.py` | `backend/tests/unit/localization/test_grapheme_count.py` | Actual extended-grapheme counts and inherited/explicit effective maximum yield authoritative per-value status. | reviewed; automated delivery passed |
| REQ | CONS-04 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | Real import activation and future edit recompute plus base/override mutation fan-out, rollback and no-op epoch checks. | reviewed; automated delivery passed |
| REQ | CONS-05 | `backend/src/verboflex/api/v1/routes/translation_constraints.py` | `backend/tests/api/test_translation_constraints.py` | Generated/detail projection keeps actual/maximum/source/status and zero/no-limit distinct; dialog refreshes only current backend authority. | reviewed; automated delivery passed |
| REQ | FMT-01 | `backend/src/verboflex/localization/importing/android_xml.py` | `backend/tests/unit/localization/importing/test_android_xml.py` | Android golden scalar/plural/array/inline/CDATA/escape values, hostile structure and tail rejection (CR-01). | reviewed; automated delivery passed |
| REQ | FMT-02 | `backend/src/verboflex/localization/importing/qt_ts.py` | `backend/tests/unit/localization/importing/test_qt_ts.py` | Qt ID/source/context/numerus/length variants, lifecycle tombstones and metadata golden cases; malformed/unknown shapes rejected. | reviewed; automated delivery passed |
| REQ | FMT-03 | `backend/src/verboflex/localization/importing/json.py` | `backend/tests/unit/localization/importing/test_json.py` | Strict JSON duplicate/encoding/depth/value checks, ordered nested typed paths and exact raw leaf keys. | reviewed; automated delivery passed |
| REQ | FMT-04 | `backend/src/verboflex/localization/importing/ios_strings.py` | `backend/tests/unit/localization/importing/test_ios_strings.py` | iOS UTF-8/BOM-qualified UTF-16, comments, escapes and lexical spans are preserved; malformed constructs rejected. | reviewed; automated delivery passed |
| REQ | FMT-06 | `backend/src/verboflex/localization/importing/registry.py` | `backend/tests/unit/localization/importing/test_conformance.py` | Explicit checked-in expected canonical fixtures for all formats, cross-side joins, atomic failures and one-over bounds; expectations not regenerated by parser. | reviewed; automated delivery passed |
| REQ | FMT-07 | `backend/src/verboflex/models/translation.py` | `backend/tests/integration/test_migrations.py`, `backend/tests/unit/localization/importing/test_contracts.py` | Migrated canonical keys/values/locators/revisions retain required product/repository/branch/path/format/text/state; API accepts canonical structure cap (CR-07). | reviewed; automated delivery passed |
| REQ | FMT-08 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | Production refresh rederives current layout membership and preserves identity on moves; reconciliation/history/tombstones and stale activation tests (CR-02/08). | reviewed; automated delivery passed |
| REQ | SRCH-01 | `frontend/src/features/translations/TranslationSearchPage.tsx` | `frontend/src/features/translations/TranslationSearchPage.test.tsx` | All-role navigation and live authorized product options; principal preference discard; server active-product filtering. | reviewed; automated delivery passed |
| REQ | SRCH-02 | `frontend/src/features/translations/TranslationSearchPage.tsx` | `frontend/src/features/translations/TranslationSearchPage.test.tsx` | Exact available language filtering, safe product-language revalidation and group identity. | reviewed; automated delivery passed |
| REQ | SRCH-03 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | Literal key/source/translation matching and full-Unicode ranking, including long raw keys. | reviewed; automated delivery passed |
| REQ | SRCH-04 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | Any-current-member state filtering with honest mixed summary and full detail. | reviewed; automated delivery passed |
| REQ | SRCH-05 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | Server effective no-max/within/over-limit filters and per-value precision; deleted siblings cannot alone match active group (CR-10). | reviewed; automated delivery passed |
| REQ | SRCH-06 | `frontend/src/features/translations/TranslationDetailPage.tsx` | `frontend/src/features/translations/TranslationDetailPage.test.tsx`, `frontend/src/features/translations/MaximumLengthDialog.test.tsx`, `frontend/e2e/translations.spec.ts` | Opaque group routes from search; inaccessible/non-anchor IDs fail without enumeration; Back restores focus/pages unless invalidated. | reviewed; automated delivery passed |
| REQ | SRCH-07 | `frontend/src/features/translations/TranslationDetailPage.tsx` | `frontend/src/features/translations/TranslationDetailPage.test.tsx`, `frontend/src/features/translations/MaximumLengthDialog.test.tsx`, `frontend/e2e/translations.spec.ts` | Complete selectors, source/target, state/provenance/history and constraints; explicit comments/pending absence; inert mixed-script rendering. | reviewed; automated delivery passed |
| REQ | SRCH-08 | `frontend/src/features/translations/useTranslationSearch.ts` | `frontend/src/features/translations/useTranslationSearch.test.ts` | Fixed 50 + lookahead paging and bounded window DOM, stable keys, manual retry/load, malformed/repeated cursor guards and Back query continuity. | reviewed; automated delivery passed |

## Independent diagnostic and regression evidence

All observed on 2026-09-06. These focused invocations complement, and do not substitute for, Plan 19's final full gauntlet/smoke. Counts are per invocation and may overlap.

- **R1:** `backend/.venv/bin/python -m pytest backend/tests/unit/localization/importing backend/tests/unit/localization/test_grapheme_count.py backend/tests/unit/test_phase4_service_boundaries.py backend/tests/integration/test_phase4_search_regressions.py backend/tests/integration/test_bounded_key_identities.py backend/tests/integration/test_constraint_generation_migration.py backend/tests/integration/test_confirmed_layout_refresh.py backend/tests/integration/test_structured_group_deletion.py -q` — exit 0, **294 passed in 16.85s**.
- **R2:** from frontend, `npm test -- --run src/features/translations/TranslationSearchPage.test.tsx src/features/translations/useTranslationSearch.test.ts src/features/admin/previews/ProductPreviewPage.test.tsx` — exit 0, **122 passed / 3 files in 8.34s**; includes corrected unequal confirmation digests and both deferred-options Back query regressions.
- **R3:** `backend/.venv/bin/python -m pytest backend/tests/integration/test_translation_constraints.py backend/tests/integration/test_translation_import_activation.py backend/tests/api/test_translation_structure_roundtrip.py backend/tests/api/test_translation_error_union.py backend/tests/api/test_openapi_contract.py backend/tests/architecture/test_phase4_closeout_gate.py -q` — exit 0, **157 passed in 9.20s**; includes ABA PUT/DELETE, changed Rejected state, large parser-to-HTTP structure and all 78 exact threat metadata guards.
- **R4:** `backend/.venv/bin/python -m pytest backend/tests/integration/test_structured_group_deletion.py backend/tests/api/test_translations.py backend/tests/api/test_translation_constraints.py backend/tests/architecture/test_phase4_scope.py -q` — exit 0, **60 passed in 7.31s**; includes stronger 64a5e38 historical-only violation regression.
- **R5:** from frontend, `npm test -- --run src/features/translations/TranslationResultList.test.tsx src/features/translations/TranslationDetailPage.test.tsx src/features/translations/MaximumLengthDialog.test.tsx src/features/admin/imports/PublishedMappingImports.test.tsx` — exit 0, **120 passed / 4 files in 1.27s**.
- **R6:** `backend/.venv/bin/python -m pytest backend/tests/architecture/test_phase4_checkpoint_redaction.py -q` — exit 0, **1 passed in 0.08s**; extracts actual shell function, verifies exact safe stderr/digest, absence of canary and deletion of its raw output file.
- **R7:** `backend/.venv/bin/python -m pytest backend/tests/integration/test_import_status_activation_race.py backend/tests/integration/test_import_jobs.py backend/tests/api/test_admin_mappings.py -q` — exit 0, **95 passed in 16.38s**; includes all four same/cross-product real HTTP polling interleavings.
- **CR-15 independent RED:** disposable activation fixture with initial real JSON activation and a staged successor. Real `get_translation_group` then `put_translation_constraint` runs in one thread; an after-cursor barrier holds its scope lock until the actual `finish_import_execution` thread holds its mapping lock. PostgreSQL `handle_error` captured `DeadlockDetected` and the cyclic transaction wait graph above. No source or test edits were made. The fixture database was dropped.
- **CR-16 independent RED:** same initialized/staged fixture but no worker, concurrency or event hook. Real group read succeeds; real constraint PUT fails `ForeignKeyViolation`, trigger function line 28. This isolates retained-baseline authority from deadlocking and excludes transient retry as an explanation. The fixture database was dropped.
- **R8:** `backend/.venv/bin/python -m pytest backend/tests/integration/test_constraint_activation_race.py backend/tests/integration/test_retained_baseline_constraint_epoch.py backend/tests/integration/test_translation_constraints.py backend/tests/integration/test_translation_import_activation.py backend/tests/integration/test_structured_group_deletion.py backend/tests/integration/test_import_status_activation_race.py -q` — exit 0, **108 passed in 11.38s**. Independently rerunning the original isolated CR-16 production-service probe also returned `ISOLATED_RUNNING_REFRESH constraint succeeded`; its disposable database was dropped. This bounded recheck covers all three newly added paths and the modified service; unchanged previously reviewed scope was not reopened.
- Read-only defect probes: mixed-deletion production PostgreSQL group returned active_groups=0/deleted_groups=1/detail_deleted=True despite one live member; actual hook transpile probe restored old query over new input; actual validator accepted fabricated T1-only SECURED. These are historical RED proofs, not current behavior.
- Latest `backend/.venv/bin/python tools/verify_phase4_closeout.py --digest` yielded the frontmatter digest after 231e5b1 and the completed mutation window.

## Delivery and consolidated gate

**Automated delivery passed:** the fresh full `bash tools/phase4_gauntlet.sh` at source `231e5b1` completed all 27 command records with exit zero and finalized only after source-digest equality and cleanup. The reviewer independently inspected `result.json`, command results, changed-line/parser logs and the actual built-stack smoke log, then reread the exact source digest unchanged.

Evidence directory: `/var/folders/0t/8j9ddhjn68393k7yzdpwnjl80000gp/T/verboflex-phase04-gate-92tdd_0i`. Durable phase evidence is `docs/evidence/phase-04.md` and `docs/evidence/phase-04-run.json`. The final run contains **1,614 backend tests**, **590 frontend tests**, backend changed lines **3,285/3,285**, frontend changed lines **842/842**, parser **1,817 statements / 704 branches at 100%**, **12/12 killed reversible mutants**, **21 responsive browser journeys**, and the fresh **four-format/four-role real Docker smoke in 62 seconds** with cleanup and redaction checks passed. Full type/lint/format/build, generated-client drift and declared supply-chain controls also exited zero.

Historical failures remain evidence, not waivers: df90536 failed real Android import polling (CR-14), and ec6fd68's full passing run predated independent CR-15/CR-16 discovery. All three now have independently checked corrections and are included in the final same-digest gate. The bounded final pass reviewed the Product-first lock/authority changes, migration 0021 and both new test files without reopening unrelated, previously reviewed source.

Final validator: `backend/.venv/bin/python tools/verify_phase4_closeout.py --check-code-review --manifest tools/phase4_source_manifest.txt --evidence docs/evidence/phase-04.md --code-review docs/reviews/phase-04-code-review.md --review-ledger .planning/phases/04-localization-import-search-and-constraints/04-REVIEW.md` — **exit 0**, `status: passed`, `artifacts: 3`, exact frontmatter digest. Independent structure/inventory checks confirmed identical reports and all 172 changed paths, without omission or duplication; `git diff --check` passed. Security's all-78-row independent report and the goal-backward verifier remain separately owned artifacts. This **passed code-review status is not phase completion**: outstanding human UAT and human-only judgment must remain `human_needed`; no manual criterion is waived.

## Historical review snapshots — preserved proof, not current disposition

The quoted material below is the previous partial/interim report body, preserved verbatim as historical evidence. Its old counts, line numbers, open findings and remaining-scope statements applied to those snapshots. The normalized current finding table and exact 172-path inventory above supersede their disposition; the quotation prevents old unresolved tables from being interpreted as current finding rows.

> # Phase 04 code review — pending remediation and completion
>
> ## Narrative Findings (AI reviewer)
>
> The final pass confirms two new functional BLOCKER findings (CR-10, CR-12) and independently reproduces the security auditor's high BLOCKER CR-11. Earlier CR-01 through CR-09 have identifiable source corrections, but none is being closed by inference from its fix commit or reported test success. Both reports remain pending. No production or test source was modified by this reviewer.
>
> The impact-severity totals are normalized: six high findings (CR-01/03/07/08/09/11), six medium findings (CR-02/04/05/06/10/12), and no critical-impact findings. The frontmatter critical bucket includes high impact; warning includes medium impact. All twelve are release BLOCKER classifications because they concern required behavior or gate integrity. Historical first-pass counts and proof below are retained explicitly as history.
>
> ## Scope and evidence status
>
> Exact base: `d987d5f48273d49234b07aacb3fa185337a1b4f2`. Observed source revision: `2b3b0d6661d896984629c51fd536becbd421d46d`. The frontmatter digest is an observed source snapshot, not a claim of a post-gauntlet freeze. The fresh run started against this digest has been interrupted for confirmed defects; replacement evidence is required after fixes.
>
> The exact scoped diff currently contains 165 backend/frontend/tools/config paths. The 76-file list preserves the previous 69-file partial review inventory and adds seven omitted migration/delivery files inspected in this pass. It includes focused cross-boundary inspection of large existing modules and must not be interpreted as completion of standard full-file review. The earlier approximate 91-file production estimate did not count the complete tests/fixtures/generated/lock scope.
>
> Fully read in this continuation: canonical core/registry; translation search and constraint services; three new migrations; search hook, search page, result list, workspace, preferences, detail-authority helper and maximum-length dialog; gate runner and smoke Python/browser/shell delivery code; parser checkpoint script. Focused reads include Android tail rejection, reconciliation transitions, response schema, preview confirmation helpers, the complete import-job diff, and regression fixture/setup sections. The hook continuation guard removal was traced through every internal state write: validated snapshot/page creates the cursor; query changes clear it synchronously; filter/token changes enter initial loading; post-await generation, identity and cursor guards remain.
>
> Required context inspected includes AGENTS.md, .planning/config.json (no configured agent skills), the agent-skills bootstrap, Phase 04 CONTEXT, UI-SPEC, RESEARCH, Plan 20, source manifest, existing reports and closeout validator. No project .codex/skills or .agents/skills directory exists. No structural pre-pass was supplied. Long context/tool reads included truncation; the remaining full-read completion must be reconciled rather than presumed.
>
> ## Current finding disposition
>
> | ID | File/line | Severity | Classification | Proof | Impact | Resolution | Remediation |
> |---|---|---|---|---|---|---|---|
> | CR-11 | `tools/verify_phase4_closeout.py:132` | high | BLOCKER | Independently invoked validate_document with SECURED, a valid-looking digest and only T1/high/mitigate/placeholder.py:1/resolved. It returned SECURED with zero required threat IDs. | The promised automated gate can accept omitted high threats; T-04-62/T-04-64 and Plan 20 exact security replay fail. | open | Compare exact registered T-04-01..77 plus T-04-SC set, cardinality and declared severity; reject duplicate, unknown, omitted and downgraded rows. Test each case; bind to actual source/evidence. |
> | CR-10 | `backend/src/verboflex/services/translation_search.py:421,449,791` | medium | BLOCKER | Production search/detail on a disposable migrated PostgreSQL fixture with two array values, one tombstoned, returned active_groups=0, deleted_groups=1, detail_deleted=True, retained_active_values=1. | Removing one variant hides the live siblings from normal search and disables the group's constraint UI. Tombstoned minimum UUID also disagrees with mutation's minimum-live anchor. | open | Keep stable canonical/group authority; mark group deleted only when key/all members are deleted; base current filters on live members; permit the stable group anchor only while live members remain. Regress actual parser refresh, default search, detail and constraint mutation for leading/nonleading removed variants. |
> | CR-12 | `frontend/src/features/translations/TranslationSearchPage.tsx:450,461`; `frontend/src/features/translations/useTranslationSearch.ts:280` | medium | BLOCKER | Back restores a saved snapshot while options await. The editable pending query is passed as initialQuery, but validScope checks only product/language and restoreSnapshot returns snapshot.query. A read-only transpile/VM probe returned enteredQuery=new, restoredQuery=old. | User input entered during options loading is overwritten with the old query and old results. | open | Invalidate old snapshot pages/query authority whenever the current query differs; retain the new input and request fresh results. Add a deferred-options Back-navigation component regression. |
>
> ## Earlier corrections observed, awaiting independent regression closure
>
> | Finding | Source observation at reviewed snapshot | Remaining verification |
> |---|---|---|
> | CR-01 | Android plural/array item branches reject non-whitespace tails before constructing values. | Re-run both real registry tail cases and mapping atomic-failure regressions. |
> | CR-02 | Target-change logic no longer gates reset on Approved; only proven Approved correlation bypasses Draft. | Recheck rejected changed target and retained history/context in real activation. |
> | CR-03 | Durable key generation survives DELETE; migration 0018 lifts prior-key epoch and versions to bounded BIGINT. | Recheck ABA PUT/DELETE and migration tests, including distinct language rules. |
> | CR-04 | Detail base rule lookup now uses scope plus raw key across repository sides. | Recheck separate-side inheritance and override removal API/UI projections. |
> | CR-05 | Cursor contains filter digest and UUID/rank/language anchor, not raw key; decoder retains 2048 bound and database validates anchor. | Recheck 51 long-key groups, Unicode/escaped filter boundaries and final encoder invariant tests. |
> | CR-06 | Search uses PostgreSQL Unicode casefold for query/key/source/display; migration 0019 aligns expressions. | Recheck ligature/final-sigma tiers and migration/index behavior on PostgreSQL 18. |
> | CR-07 | API structure cap references canonical MAX_CANONICAL_STRUCTURE_NODES. | Recheck parser-valid large structure through authenticated API and regenerated client. |
> | CR-08 | Worker derives current file membership from confirmed immutable layout, not original preview file list. | Recheck move/add/remove/unsupported-new-file production refresh and separate mapping atomicity. |
> | CR-09 | Browser checks language-bound confirmation digest shape and exact identities without comparing with original unbound digest. | Recheck realistic unequal-digest draft and active confirmation tests. |
>
> Additional source review: migration 0020 bounds unique natural-key indexes with a full raw-key digest while preserving raw text and transactional downgrade failure. CanonicalValueBuffer bounds incremental UTF-8 JSON expansion in nested adapter buffers, peer-file aggregation, separate-side shared budget and post-join expansion. Exact budget/fidelity tests were inspected selectively; their full independent review/run remains outstanding. Constraint mutation now increments dataset_version when effective state changes, closing the earlier cursor-invalidation candidate in source.
>
> ## Requirement and decision trace
>
> These are exact manifest entry points, not PASS assertions. Every row remains pending final source/test completion and fresh execution evidence; CR-10 additionally blocks active structured-group behavior and CR-12 blocks browser query continuity.
>
> | Kind | ID | Delivery source | Executable test entry points | Disposition |
> |---|---|---|---|---|
> | DECISION | D-01 | `backend/src/verboflex/localization/importing/android_xml.py` | `backend/tests/unit/localization/importing/test_android_xml.py` | pending |
> | DECISION | D-02 | `backend/src/verboflex/localization/importing/android_xml.py` | `backend/tests/unit/localization/importing/test_android_xml.py` | pending |
> | DECISION | D-03 | `backend/src/verboflex/localization/importing/core.py` | `backend/tests/unit/localization/importing/test_contracts.py` | pending |
> | DECISION | D-04 | `backend/src/verboflex/localization/importing/registry.py` | `backend/tests/unit/localization/importing/test_conformance.py` | pending |
> | DECISION | D-05 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
> | DECISION | D-06 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
> | DECISION | D-07 | `backend/src/verboflex/models/translation.py` | `backend/tests/integration/test_migrations.py`, `backend/tests/unit/localization/importing/test_contracts.py` | pending |
> | DECISION | D-08 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
> | DECISION | D-09 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
> | DECISION | D-10 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
> | DECISION | D-11 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
> | DECISION | D-12 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
> | DECISION | D-13 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
> | DECISION | D-14 | `frontend/src/features/translations/TranslationSearchPage.tsx` | `frontend/src/features/translations/TranslationSearchPage.test.tsx` | pending |
> | DECISION | D-15 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | pending |
> | DECISION | D-16 | `frontend/src/features/translations/TranslationSearchPage.tsx` | `frontend/src/features/translations/TranslationSearchPage.test.tsx` | pending |
> | DECISION | D-17 | `frontend/src/features/translations/useTranslationSearch.ts` | `frontend/src/features/translations/useTranslationSearch.test.ts` | pending |
> | DECISION | D-18 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | pending |
> | DECISION | D-19 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | pending |
> | DECISION | D-20 | `backend/src/verboflex/localization/graphemes.py` | `backend/tests/unit/localization/test_grapheme_count.py` | pending |
> | DECISION | D-21 | `backend/src/verboflex/api/v1/routes/translation_constraints.py` | `backend/tests/api/test_translation_constraints.py` | pending |
> | DECISION | D-22 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | pending |
> | DECISION | D-23 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | pending |
> | REQ | CONS-01 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | pending |
> | REQ | CONS-02 | `backend/src/verboflex/api/v1/routes/translation_constraints.py` | `backend/tests/api/test_translation_constraints.py` | pending |
> | REQ | CONS-03 | `backend/src/verboflex/localization/graphemes.py` | `backend/tests/unit/localization/test_grapheme_count.py` | pending |
> | REQ | CONS-04 | `backend/src/verboflex/services/translation_constraints.py` | `backend/tests/integration/test_translation_constraints.py` | pending |
> | REQ | CONS-05 | `backend/src/verboflex/api/v1/routes/translation_constraints.py` | `backend/tests/api/test_translation_constraints.py` | pending |
> | REQ | FMT-01 | `backend/src/verboflex/localization/importing/android_xml.py` | `backend/tests/unit/localization/importing/test_android_xml.py` | pending |
> | REQ | FMT-02 | `backend/src/verboflex/localization/importing/qt_ts.py` | `backend/tests/unit/localization/importing/test_qt_ts.py` | pending |
> | REQ | FMT-03 | `backend/src/verboflex/localization/importing/json.py` | `backend/tests/unit/localization/importing/test_json.py` | pending |
> | REQ | FMT-04 | `backend/src/verboflex/localization/importing/ios_strings.py` | `backend/tests/unit/localization/importing/test_ios_strings.py` | pending |
> | REQ | FMT-06 | `backend/src/verboflex/localization/importing/registry.py` | `backend/tests/unit/localization/importing/test_conformance.py` | pending |
> | REQ | FMT-07 | `backend/src/verboflex/models/translation.py` | `backend/tests/integration/test_migrations.py`, `backend/tests/unit/localization/importing/test_contracts.py` | pending |
> | REQ | FMT-08 | `backend/src/verboflex/services/translation_imports.py` | `backend/tests/integration/test_translation_import_activation.py` | pending |
> | REQ | SRCH-01 | `frontend/src/features/translations/TranslationSearchPage.tsx` | `frontend/src/features/translations/TranslationSearchPage.test.tsx` | pending |
> | REQ | SRCH-02 | `frontend/src/features/translations/TranslationSearchPage.tsx` | `frontend/src/features/translations/TranslationSearchPage.test.tsx` | pending |
> | REQ | SRCH-03 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | pending |
> | REQ | SRCH-04 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | pending |
> | REQ | SRCH-05 | `backend/src/verboflex/services/translation_search.py` | `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py` | pending |
> | REQ | SRCH-06 | `frontend/src/features/translations/TranslationDetailPage.tsx` | `frontend/src/features/translations/TranslationDetailPage.test.tsx`, `frontend/src/features/translations/MaximumLengthDialog.test.tsx`, `frontend/e2e/translations.spec.ts` | pending |
> | REQ | SRCH-07 | `frontend/src/features/translations/TranslationDetailPage.tsx` | `frontend/src/features/translations/TranslationDetailPage.test.tsx`, `frontend/src/features/translations/MaximumLengthDialog.test.tsx`, `frontend/e2e/translations.spec.ts` | pending |
> | REQ | SRCH-08 | `frontend/src/features/translations/useTranslationSearch.ts` | `frontend/src/features/translations/useTranslationSearch.test.ts` | pending |
>
> ## Diagnostic commands and results
>
> - Read-only production-service probe used the existing search_session_factory fixture to create a uniquely named test database on the test PostgreSQL instance. It seeded one two-value group, tombstoned one sibling and called search_translations/get_translation_group. Result: active_groups=0, deleted_groups=1, detail_deleted=True, retained_active_values=1. The fixture dropped only its owned database; the user's application stack was untouched.
> - Read-only Node/TypeScript transpile+VM probe loaded the actual hook and called restoreSnapshot with a valid old snapshot and new initialQuery. Result: enteredQuery=new, restoredQuery=old.
> - Read-only Python runpy probe invoked the actual closeout validator with one unregistered security row. Result: accepted_verdict=SECURED, required_threats_present=0.
> - `uv run --project backend python tools/verify_phase4_closeout.py --digest` returned the frontmatter digest at the observed revision.
> - Full gauntlet and smoke are owned by Plan 19. No fresh passing final run is claimed here.
>
> ## Remaining standard-review scope
>
> Before any passing verdict: complete full reads of large existing import/preview/product services beyond changed-function inspection; finish detail-page remainder and complete preview surface; review generated SDK/types/OpenAPI and lock identities as contract/config artifacts; read all changed behavioral tests/fixtures for reliability and false-positive coverage; reconcile the full source manifest/UI contracts. The current proof-bearing fixes must then be independently exercised. This is a deliberate incomplete handoff to free the reviewer slot for the requested frontend correction, not completion of the final code review.
>
> The following 89 exact diff files are not in the cumulative inspected-file list. Selective probes/read fragments do not promote them to reviewed status:
>
> - `backend/tests/api/test_admin_mappings.py`
> - `backend/tests/api/test_admin_previews.py`
> - `backend/tests/api/test_openapi_contract.py`
> - `backend/tests/api/test_phase4_failure_boundaries.py`
> - `backend/tests/api/test_translation_constraints.py`
> - `backend/tests/api/test_translation_structure_roundtrip.py`
> - `backend/tests/api/test_translations.py`
> - `backend/tests/architecture/test_background_boundaries.py`
> - `backend/tests/architecture/test_phase2_gap_closure.py`
> - `backend/tests/architecture/test_phase2_scope.py`
> - `backend/tests/architecture/test_phase3_scope.py`
> - `backend/tests/architecture/test_phase4_closeout_gate.py`
> - `backend/tests/architecture/test_phase4_gauntlet.py`
> - `backend/tests/architecture/test_phase4_license_policy.py`
> - `backend/tests/architecture/test_phase4_scope.py`
> - `backend/tests/architecture/test_translation_mutation_verifier.py`
> - `backend/tests/fixtures/localization/android/invalid_cases.json`
> - `backend/tests/fixtures/localization/android/manifest.json`
> - `backend/tests/fixtures/localization/android/scalar.expected.json`
> - `backend/tests/fixtures/localization/android/scalar.xml`
> - `backend/tests/fixtures/localization/android/valid_structured.expected.json`
> - `backend/tests/fixtures/localization/android/valid_structured.xml`
> - `backend/tests/fixtures/localization/conformance/direct.json`
> - `backend/tests/fixtures/localization/conformance/manifest.json`
> - `backend/tests/fixtures/localization/conformance/separate.json`
> - `backend/tests/fixtures/localization/ios/invalid_cases.json`
> - `backend/tests/fixtures/localization/ios/manifest.json`
> - `backend/tests/fixtures/localization/ios/valid.expected.json`
> - `backend/tests/fixtures/localization/ios/valid.strings`
> - `backend/tests/fixtures/localization/json/invalid_cases.json`
> - `backend/tests/fixtures/localization/json/manifest.json`
> - `backend/tests/fixtures/localization/json/valid_nested.expected.json`
> - `backend/tests/fixtures/localization/json/valid_nested.json`
> - `backend/tests/fixtures/localization/qt/invalid_cases.json`
> - `backend/tests/fixtures/localization/qt/manifest.json`
> - `backend/tests/fixtures/localization/qt/valid_structured.expected.json`
> - `backend/tests/fixtures/localization/qt/valid_structured.ts`
> - `backend/tests/integration/test_bounded_key_identities.py`
> - `backend/tests/integration/test_confirmed_layout_refresh.py`
> - `backend/tests/integration/test_constraint_generation_migration.py`
> - `backend/tests/integration/test_import_jobs.py`
> - `backend/tests/integration/test_migrations.py`
> - `backend/tests/integration/test_phase4_search_regressions.py`
> - `backend/tests/integration/test_preview_jobs.py`
> - `backend/tests/integration/test_product_publication.py`
> - `backend/tests/integration/test_translation_constraints.py`
> - `backend/tests/integration/test_translation_import_activation.py`
> - `backend/tests/integration/test_translation_search.py`
> - `backend/tests/unit/localization/importing/test_android_xml.py`
> - `backend/tests/unit/localization/importing/test_conformance.py`
> - `backend/tests/unit/localization/importing/test_contracts.py`
> - `backend/tests/unit/localization/importing/test_ios_strings.py`
> - `backend/tests/unit/localization/importing/test_json.py`
> - `backend/tests/unit/localization/importing/test_output_budget.py`
> - `backend/tests/unit/localization/importing/test_qt_ts.py`
> - `backend/tests/unit/localization/importing/test_structure_bounds.py`
> - `backend/tests/unit/localization/test_grapheme_count.py`
> - `backend/tests/unit/services/test_mappings.py`
> - `backend/tests/unit/test_phase4_parser_input_authority.py`
> - `backend/tests/unit/test_phase4_public_error_boundaries.py`
> - `backend/tests/unit/test_phase4_service_boundaries.py`
> - `backend/tests/unit/test_phase4_worker_boundaries.py`
> - `backend/tests/unit/test_preview_connection_authority.py`
> - `backend/uv.lock`
> - `frontend/e2e/admin-configuration.spec.ts`
> - `frontend/e2e/translations.spec.ts`
> - `frontend/openapi.json`
> - `frontend/package-lock.json`
> - `frontend/src/api/admin-client-contract.test.ts`
> - `frontend/src/api/client/index.ts`
> - `frontend/src/api/client/sdk.gen.ts`
> - `frontend/src/api/client/types.gen.ts`
> - `frontend/src/components/layout/AppShell.test.tsx`
> - `frontend/src/features/admin/imports/PublishedMappingImports.test.tsx`
> - `frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx`
> - `frontend/src/features/admin/imports/useImportPolling.test.ts`
> - `frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx`
> - `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx`
> - `frontend/src/features/translations/MaximumLengthDialog.test.tsx`
> - `frontend/src/features/translations/TranslationDetailPage.test.tsx`
> - `frontend/src/features/translations/TranslationFilters.test.tsx`
> - `frontend/src/features/translations/TranslationResultList.test.tsx`
> - `frontend/src/features/translations/TranslationSearchPage.test.tsx`
> - `frontend/src/features/translations/translationPreferences.test.ts`
> - `frontend/src/features/translations/useTranslationSearch.test.ts`
> - `frontend/src/router.test.tsx`
> - `tools/phase4_source_manifest.txt`
> - `tools/tests/test_phase4_smoke.py`
> - `tools/tests/test_phase4_smoke.sh`
>
> ## Historical first-pass evidence (immutable proof context)
>
> The following retained narrative describes the first partial pass and its original source snapshot. Its old line numbers, counts and open dispositions are historical; the current sections above control the present disposition. No previous proof or remediation description has been discarded.
>
> # Phase 04 code review — pending remediation
>
> ## Narrative Findings (AI reviewer)
>
> Nine confirmed BLOCKER findings remain open pending independent recheck of fixes. This is an adversarial source review under the authorized GSD execute-phase workflow, not an old-coder blind verification. No implementation files were modified and no broad/shared tests were run by this reviewer.
>
> ## Scope and evidence status
>
> Review base: `d987d5f48273d49234b07aacb3fa185337a1b4f2`; observed revision: `9f2312cbcdc3dba92b1a1c63a2d817e4f4c31692`. Other agents are adding tests and remediation. The source digest is deliberately pending until the final source freeze and fresh gauntlet/smoke. The file list records files inspected so far, including focused changed-function/cross-boundary inspection; it is not a claim that the entire approximately 91-file delivery scope has completed standard review. Remaining coverage must be reconciled against SUMMARY key-files and the actual diff before a passing verdict.
>
> Read contracts include AGENTS.md, all D-01 through D-23 in 04-CONTEXT, parser/search/constraint contracts in 04-RESEARCH, Plan 20 Task 1, and relevant Plan 11/13 rules. The phase source manifest is the required final coverage authority. No structural pre-pass was supplied.
>
> ## Critical issues
>
> | ID | File/line | Severity | Classification | Proof | Impact | Resolution | Remediation |
> |---|---|---|---|---|---|---|---|
> | CR-01 | `backend/src/verboflex/localization/importing/android_xml.py:413,492` | high | BLOCKER | Both collection loops pass the item to _mixed_content but do not validate item.tail. Direct production-registry reproduction with <item>A</item>LOST yields success and A; LOST is absent from canonical structure. | Unsupported source content is silently accepted, violating FMT-01 and D-04/D-05. | open | Reject non-whitespace tails for plural and array items; regress both through parse_canonical_snapshot and mapping atomic failure. |
> | CR-02 | `backend/src/verboflex/services/translation_imports.py:508` | medium | BLOCKER | The external target-change branch is conditional on current review_state == approved. A rejected target with changed translated_text bypasses all reset branches and is updated with rejected. | D-10 and Plan 11 explicitly require every uncorrelated external translated-text change to become Draft; review state describes superseded content. | open | Reset every uncorrelated external target change to Draft, preserving only the exact proven approved-correlation exception. Regress rejected changed target, retained context and prior revision. |
> | CR-03 | `backend/src/verboflex/services/translation_constraints.py:270,327` | high | BLOCKER | DELETE physically removes the rule; the next create always sets version=1. A stale client holding version 1 can subsequently replace or delete the newly created different rule. | Concurrent edits are silently lost despite the conflict contract; a stale destructive request acts on a different rule incarnation. | open | Maintain a durable generation across deletion or bind expected authority to rule identity. Regress create, delete, recreate, stale old PUT and DELETE returning conflict. |
> | CR-04 | `backend/src/verboflex/services/translation_search.py:590` | medium | BLOCKER | Recomputation resolves the base rule across scope/raw_key, including the Keys repository. Detail joins base_rule only on the target anchor.key_id, which belongs to the Translations repository. | The API reports base_maximum=null despite inherited effective limits. MaximumLengthDialog falsely says removing an override leaves no limit, violating D-19 and authoritative mutation presentation. | open | Use the same unambiguous scope/raw-key base lookup in detail and recomputation; regress separate repository base default, target detail and removal copy. |
> | CR-05 | `backend/src/verboflex/services/translation_search.py:305` | medium | BLOCKER | Cursor JSON embeds position.stable_key in full before enforcing 2048 characters. Direct _encode_cursor with 1600 ASCII key characters raises TranslationSearchInputError although raw keys allow 1,048,576 characters. | A normal page ending in such a key returns 422 instead of 50 results and continuation; violates SRCH-08/D-17. | open | Use a bounded signed anchor with server-resolved seek key and a digest of filters; preserve deterministic order, current dataset binding and long-key support. Regress 51 groups and Unicode/query expansion boundaries. |
> | CR-06 | `backend/src/verboflex/services/translation_search.py:378` | medium | BLOCKER | normalize_search_query uses Python casefold; SQL uses lower plus only the sharp-s replacement. Independent local PostgreSQL SELECT for the ligature ﬀ returns ﬀ while Python casefold returns ff. | Searching an imported key by its identical ligature text returns no match; Unicode casefold/ranking promises in D-15 and Plan 13 fail. | open | Apply identical full Unicode normalization to query, key, source and target projections and corresponding indexes. Regress ligatures and final sigma across exact/prefix/partial tiers. |
> | CR-07 | `backend/src/verboflex/schemas/translations.py:165` | high | BLOCKER | TranslationValueResponse permits 128 structure nodes; Android permits 4096 and Qt permits 256 locations plus other nodes. _value_response passes all nodes to the smaller schema. | Accepted imported records can raise response-model ValidationError outside the route's service try block, preventing detail and constraint workflows; violates FMT-07/SRCH-06/SRCH-07. | open | Align the response and canonical bounds without truncation. Regress parser-valid >128-node Android/Qt records through authenticated detail and generated schema. |
> | CR-08 | `backend/src/verboflex/services/import_jobs.py:2793,2804` | high | BLOCKER | _confirmed_parser_inputs loops candidate.files from the persisted PreviewJob. New current-snapshot files are omitted; moved/deleted preview files cause an empty input result and failed import. | Production refresh cannot faithfully import file additions or preserve identities across key moves, despite synthetic reconciliation tests; violates D-05/D-08 and FMT-08. | open | Keep confirmed layout/format authority but rederive current file membership within that layout from the immutable snapshot. Regress production worker refresh with moved, added and removed files while preserving identities and atomicity. |
> | CR-09 | `frontend/src/features/admin/previews/ProductPreviewPage.tsx:183,204` | high | BLOCKER | Both response-match helpers compare confirmation.preview_digest with the original result.digest. The backend now returns a different _complete_preview_digest that includes the selected base_language; the preview result digest omits that field. | A successful confirmation is always displayed as failure and never calls onConfirmed(true); publication/revalidation recovery remains blocked in the real browser. | open | Expose and validate original request digest separately from the new language-bound confirmation digest, or validate returned confirmation authority using exact identity fields and the new digest contract. Add realistic tests whose returned confirmation digest differs from the preview result, for both draft and active paths. |
>
> ### CR-01: Android collection item tails silently discarded
>
> **Classification:** BLOCKER
>
> **File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/localization/importing/android_xml.py:413,492`
>
> **Issue:** Both collection loops pass the item to _mixed_content but do not validate item.tail. Direct production-registry reproduction with <item>A</item>LOST yields success and A; LOST is absent from canonical structure. Unsupported source content is silently accepted, violating FMT-01 and D-04/D-05.
>
> **Fix:** Reject non-whitespace tails for plural and array items; regress both through parse_canonical_snapshot and mapping atomic failure.
>
> ### CR-02: External changes to rejected targets retain Rejected
>
> **Classification:** BLOCKER
>
> **File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/services/translation_imports.py:508`
>
> **Issue:** The external target-change branch is conditional on current review_state == approved. A rejected target with changed translated_text bypasses all reset branches and is updated with rejected. D-10 and Plan 11 explicitly require every uncorrelated external translated-text change to become Draft; review state describes superseded content.
>
> **Fix:** Reset every uncorrelated external target change to Draft, preserving only the exact proven approved-correlation exception. Regress rejected changed target, retained context and prior revision.
>
> ### CR-03: Delete and recreate reuses optimistic versions
>
> **Classification:** BLOCKER
>
> **File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/services/translation_constraints.py:270,327`
>
> **Issue:** DELETE physically removes the rule; the next create always sets version=1. A stale client holding version 1 can subsequently replace or delete the newly created different rule. Concurrent edits are silently lost despite the conflict contract; a stale destructive request acts on a different rule incarnation.
>
> **Fix:** Maintain a durable generation across deletion or bind expected authority to rule identity. Regress create, delete, recreate, stale old PUT and DELETE returning conflict.
>
> ### CR-04: Separate mapping detail loses base-rule authority
>
> **Classification:** BLOCKER
>
> **File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/services/translation_search.py:590`
>
> **Issue:** Recomputation resolves the base rule across scope/raw_key, including the Keys repository. Detail joins base_rule only on the target anchor.key_id, which belongs to the Translations repository. The API reports base_maximum=null despite inherited effective limits. MaximumLengthDialog falsely says removing an override leaves no limit, violating D-19 and authoritative mutation presentation.
>
> **Fix:** Use the same unambiguous scope/raw-key base lookup in detail and recomputation; regress separate repository base default, target detail and removal copy.
>
> ### CR-05: Accepted long keys overflow outgoing cursors
>
> **Classification:** BLOCKER
>
> **File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/services/translation_search.py:305`
>
> **Issue:** Cursor JSON embeds position.stable_key in full before enforcing 2048 characters. Direct _encode_cursor with 1600 ASCII key characters raises TranslationSearchInputError although raw keys allow 1,048,576 characters. A normal page ending in such a key returns 422 instead of 50 results and continuation; violates SRCH-08/D-17.
>
> **Fix:** Use a bounded signed anchor with server-resolved seek key and a digest of filters; preserve deterministic order, current dataset binding and long-key support. Regress 51 groups and Unicode/query expansion boundaries.
>
> ### CR-06: Database normalization disagrees with full Unicode casefold
>
> **Classification:** BLOCKER
>
> **File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/services/translation_search.py:378`
>
> **Issue:** normalize_search_query uses Python casefold; SQL uses lower plus only the sharp-s replacement. Independent local PostgreSQL SELECT for the ligature ﬀ returns ﬀ while Python casefold returns ff. Searching an imported key by its identical ligature text returns no match; Unicode casefold/ranking promises in D-15 and Plan 13 fail.
>
> **Fix:** Apply identical full Unicode normalization to query, key, source and target projections and corresponding indexes. Regress ligatures and final sigma across exact/prefix/partial tiers.
>
> ### CR-07: Detail structure cap rejects parser-valid records
>
> **Classification:** BLOCKER
>
> **File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/schemas/translations.py:165`
>
> **Issue:** TranslationValueResponse permits 128 structure nodes; Android permits 4096 and Qt permits 256 locations plus other nodes. _value_response passes all nodes to the smaller schema. Accepted imported records can raise response-model ValidationError outside the route's service try block, preventing detail and constraint workflows; violates FMT-07/SRCH-06/SRCH-07.
>
> **Fix:** Align the response and canonical bounds without truncation. Regress parser-valid >128-node Android/Qt records through authenticated detail and generated schema.
>
> ### CR-08: Refresh parses frozen preview filenames
>
> **Classification:** BLOCKER
>
> **File:** `/Users/smutti/Documents/personal/verboflex/backend/src/verboflex/services/import_jobs.py:2793,2804`
>
> **Issue:** _confirmed_parser_inputs loops candidate.files from the persisted PreviewJob. New current-snapshot files are omitted; moved/deleted preview files cause an empty input result and failed import. Production refresh cannot faithfully import file additions or preserve identities across key moves, despite synthetic reconciliation tests; violates D-05/D-08 and FMT-08.
>
> **Fix:** Keep confirmed layout/format authority but rederive current file membership within that layout from the immutable snapshot. Regress production worker refresh with moved, added and removed files while preserving identities and atomicity.
>
> ### CR-09: Successful preview confirmations are rejected by the browser
>
> **Classification:** BLOCKER (high)
>
> **File:** `/Users/smutti/Documents/personal/verboflex/frontend/src/features/admin/previews/ProductPreviewPage.tsx:183,204`
>
> **Issue:** Both response-match helpers compare confirmation.preview_digest with the original result.digest. The backend now returns a different _complete_preview_digest that includes the selected base_language; the preview result digest omits that field. A successful confirmation is always displayed as failure and never calls onConfirmed(true); publication/revalidation recovery remains blocked in the real browser.
>
> **Fix:** Expose and validate original request digest separately from the new language-bound confirmation digest, or validate returned confirmation authority using exact identity fields and the new digest contract. Add realistic tests whose returned confirmation digest differs from the preview result, for both draft and active paths.
>
> ## Exact diagnostic evidence
>
> - Read-only `uv run --project backend python -c ...` invoked the production Android registry on plural and array inputs with item tail `LOST`: both returned zero issues and display `A`.
> - Read-only direct `_encode_cursor` with a 1600-character ASCII stable key raised `TranslationSearchInputError: cursor exceeds its allowed bound`.
> - Read-only local PostgreSQL `SELECT lower('ﬀ'), replace(lower('ﬀ'), 'ß', 'ss')` returned `('ﬀ', 'ﬀ')`; Python `'ﬀ'.casefold()` returned `ff`.
> - Other findings are traced executable control-flow or producer/consumer contract contradictions. Focused integration regressions are delegated to the implementation owners; their existence or success will not be presumed until rechecked.
>
> ## Remaining review scope
>
> The standard review is handed back for remediation without claiming full coverage. The listed files include full reads of new parser/search/constraint/frontend modules and migration, plus focused changed-function and cross-boundary reads of large existing modules. The remaining pass must finish complete reads of large preview/import modules, delivery tools (phase4_gate.py, phase4_smoke.py, phase4_smoke_browser.mjs, phase4_parser_checkpoint.sh), generated SDK/types/OpenAPI and lock identity crosschecks, and the complete behavioral-test diff/fixtures. Current behavioral tests were inspected selectively for reconciliation, constraints and search, not exhaustively. Planning contracts were read by relevant requirements/decisions; remaining full planning/UI-SPEC and manifest reconciliation must not be represented as completed.
>
> Severity is separate from release priority: CR-01/03/07/08/09 are high; CR-02/04/05/06 are medium. All nine remain BLOCKER because they demonstrably violate required behavior. The canonical GSD critical count records the mandatory BLOCKER tier; the normalized table carries impact severity.
>
> ## Additional checks pending disposition
>
> Constraint mutations currently change the violation projection without changing the dataset_version used in cursor authority. Confirm whether complete dataset binding requires rejection of pre-mutation filtered cursors; do not promote this candidate to a formal finding without the explicit contract and reproduction. Android display quote/whitespace semantics and PostgreSQL long-key index entry limits also need exact contract/proof before a finding.
>
> ## Closure conditions
>
> Keep status pending until all confirmed findings are fixed and independently rechecked; complete the remaining standard-depth source and behavioral-test review; map all 20 requirement IDs and D-01 through D-23 to source evidence; reconcile the exact reviewed file scope; and bind both review artifacts to the same fresh post-gauntlet source digest as delivery/security evidence. A passed Docker smoke or an independent UI audit does not close these code defects.
>
>
