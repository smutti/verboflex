---
status: investigating
trigger: "ho questo errore"
created: 2026-09-06T12:43:41Z
updated: 2026-09-06T12:43:41Z
mode: diagnose-only
---

# Draft import banner and failed live preview

## Symptoms

User reports two screenshots during Phase 04 UAT test 1: draft Mappings shows Published imports unavailable; Preview shows Validation has not run and publication disabled. Later live logs show the user submitted validation twice.

## Current Focus

hypothesis: Two distinct paths: draft-only product requests published imports, and live repository discovery reaches its global 50-page budget.
test: Compare local service state, HTTP request logs and existing code without changing application/provider data.
expecting: Draft-only authority returns 404; both preview scans terminate at the same discovery bound.
next_action: Obtain implementation direction, then RED/GREEN regression for draft-only composition and bounded preview discovery/error reporting. Do not simply remove safety budgets or hide arbitrary 404 responses.

## Evidence

- Product is_active=false, active_revision_id absent; candidate mapping exists.
- Repeated authenticated GET published/mapping-imports returns 404 while product/candidate mapping/repository APIs return 200.
- ProductMappingsPage.tsx renders PublishedMappingImports unconditionally. Component treats missing SDK data as generic failure. list_published_mapping_imports deliberately rejects inactive/unpublished authority.
- Two preview jobs persist failed/processing_failed. Real Bitbucket branch and source requests return 200; both scans stop after exactly 50 source-directory GETs.
- SOURCE_DISCOVERY_BUDGET.max_pages is 50; discover_repository_sources_for_record traverses the whole repository breadth-first and raises limit_exceeded before request 51. No source file body requests observed before these failures.
- execute_preview_job converts all non-timeout exceptions into processing_failed and discards their safe failure category. Logs do not record the original exception: budget exhaustion is strongly supported, but the caught exception type was not directly captured.
- Screenshot source branch is master; default PR target is stable/feature/bravoplus-0.7.x. Import reads the source branch, not the default target. Do not change these user choices automatically.

## Resolution

root_cause: Confirmed draft-only frontend composition error; strongly supported whole-repository preview discovery budget exhaustion with generic error masking.
fix: Not applied; current request diagnosed only.
verification: Existing live logs, persisted state and source inspection. No new provider requests, jobs, test fixtures, source changes or deployment performed.
files_changed: Planning/debug/UAT records only.
