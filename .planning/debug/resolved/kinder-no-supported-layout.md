---
status: resolved
trigger: "anche per kinder non funziona"
created: 2026-09-08
updated: 2026-09-08
resolved: 2026-09-08
diagnose_only: false
---

# Symptoms

- expected: Running preview validation for the Kinder product automatically discovers its supported localization source layout and exposes strings for confirmation/import.
- actual: The preview job reported `Succeeded`, but returned no layout candidates and blocked confirmation/publish.
- error: `No supported localization layout was found in this source branch.`
- reproduction: Open the Kinder product, select Preview, and run validation for Mapping 1 on `dario/maxiz`.

# Evidence

- 2026-09-08: Worker logs proved that source discovery reached commit `9e30519358a2daa72c462e9317676ebec9f9ad66` and downloaded 13 files under `resources/translationsLangs/maxi_*.ts`.
- 2026-09-08: Safe structural inspection showed standard Qt TS 2.0 documents with `<!DOCTYPE TS>`, `utf8="true"`, locations, unfinished/empty translations, and language attributes more specific than some filename tokens.
- 2026-09-08: The original detector rejected the standard doctype before inspecting the document and required a smaller preview-only Qt grammar than the canonical importer.
- 2026-09-08: Live verification after the fix detected one exact layout, 13 languages, and 6,448 canonical values with no parser issues.
- 2026-09-08: Replacement preview job `49ca2a05-bcce-4bed-af1e-029201a45b50` succeeded with one 13-language layout candidate and no error.

# Eliminated

- hypothesis: Bitbucket source discovery cannot traverse the Kinder repository.
  evidence: The worker fetched all relevant Qt files successfully and remained within source budgets.
- hypothesis: The configured branch or commit is unavailable.
  evidence: Bitbucket resolved `dario/maxiz` and returned the immutable commit successfully.

# Resolution

- root_cause: The preview parser rejected the standard declaration-only Qt doctype and legacy-but-valid Qt TS 2.0 structures used by Kinder. Its filename-to-language matching also required exact equality, while Kinder uses names such as `maxi_en.ts` with `language="en_US"` and `maxi_zhs.ts` with `language="zh_HK"`.
- fix: Safely mask only the plain Qt `<!DOCTYPE TS>` prolog while leaving entities, internal subsets, external identifiers, repeated doctypes, and misplaced doctypes for `defusedxml` to reject. Align preview/import support for TS 2.0, locations, unfinished/empty translations, legacy `utf8`, context-scoped repeated source text, and deterministic filename layout templates. Bump the detector version so stale successful jobs cannot be reused.
- verification: 435 localization unit tests and all 88 preview-job integration tests passed; Ruff and mypy passed. The live Kinder branch produced one 13-language layout and 6,448 canonical values, and a new durable preview job succeeded.
- files_changed: `backend/src/verboflex/localization/qt_doctype.py`, `backend/src/verboflex/localization/preview/qt_ts.py`, `backend/src/verboflex/localization/importing/qt_ts.py`, `backend/src/verboflex/services/preview_jobs.py`, Qt fixtures and regression tests.
