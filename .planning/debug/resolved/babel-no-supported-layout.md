---
status: resolved
trigger: "per babel ho questo errore: No supported layout — No supported localization layout was found in this source branch."
created: 2026-09-08
updated: 2026-09-08
resolved: 2026-09-08
diagnose_only: false
---

# Symptoms

- expected: Babel is discovered automatically under `babel/src/commonMain/moko-resources`; import continues for usable strings and exposes duplicate keys as warnings instead of failing.
- actual: Mapping validation finished with `No supported layout`.
- error: `No supported localization layout was found in this source branch.`
- reproduction: Open the Babel product mapping/preview and run validation against its configured source branch.

# Root Cause

The preview worker cleared every detected layout whenever duplicate groups existed, and canonical import converted a complete duplicate report into a blocking `duplicate_key` issue. The frontend then rendered the empty result as an unsupported layout. This matched the superseded 2026-09-06 blocking contract but not the user's clarified import-with-warning behavior.

# Fix

- Added a canonical quarantine parser that excludes every occurrence of a duplicated identity without selecting first or last, while retaining strict failure for malformed, unsupported, incomplete, and over-budget input.
- Preview now keeps the supported MOKO layout and its unique strings while persisting duplicate diagnostics.
- Import stages and activates the unique values. Duplicate reports persist their private layout identity so refresh reconciliation can keep the prior valid value instead of tombstoning it.
- Changed duplicate messaging from a destructive unsupported-layout failure to a visible warning with the existing admin-only diagnostic view.
- Added migration `0026_duplicate_quarantine_layout` and updated the local Docker stack.

# Verification

- 492 focused backend tests passed, including all localization unit tests and complete translation activation coverage.
- 123 focused frontend tests passed; TypeScript and ESLint passed.
- Full backend suite: 1,685 passed before the migration-head expectation was updated; the only two remaining failures were environment-only Celery smoke tests whose dedicated Redis endpoint `127.0.0.1:56379` was not running. The migration regression then passed independently.
- Live read-only Babel verification at commit `6102ff5a2ba6a50bbf1d24f75f6e2a7fb3e7c625`: 19 MOKO files, one detected layout, 145 duplicate groups, 145 repeated occurrences, 42,476 importable canonical values, zero parser issues.
- Docker backend, worker, and frontend are healthy; local schema is at migration head `0026_duplicate_quarantine_layout`.

# Files Changed

- Canonical parsing and diagnostics: `backend/src/verboflex/localization/importing/registry.py`, `backend/src/verboflex/localization/duplicate_diagnostics.py`
- Preview/import/reconciliation: `backend/src/verboflex/localization/preview/moko_xml.py`, `backend/src/verboflex/worker/preview_tasks.py`, `backend/src/verboflex/services/import_jobs.py`, `backend/src/verboflex/services/translation_imports.py`
- Persistence: `backend/src/verboflex/models/duplicate_report.py`, `backend/src/verboflex/services/duplicate_reports.py`, `backend/alembic/versions/0026_duplicate_quarantine_layout.py`
- UI: `frontend/src/features/admin/previews/ProductPreviewPage.tsx`, `frontend/src/features/admin/imports/DuplicateKeysDialog.tsx`
- Targeted unit, integration, architecture, migration, and frontend regressions.
