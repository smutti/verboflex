---
status: resolved
trigger: "ho questo errore"
created: 2026-09-06T12:43:41Z
updated: 2026-09-06T23:03:22Z
mode: tdd-fix
---

# Draft import banner and failed live preview

## Symptoms

User reports two screenshots during Phase 04 UAT test 1: draft Mappings shows Published imports unavailable; Preview shows Validation has not run and publication disabled. Later live logs show the user submitted validation twice.

## Current Focus

hypothesis: Confirmed traversal defect: rootless discovery spends its 50-page budget on one request per directory instead of using Bitbucket Cloud's bounded recursive `max_depth` source listing.
test: Add a failing integration test in which a Babel-style localization tree is nested below more than 50 unrelated directories and no localization root is configured.
expecting: Rootless discovery requests a recursive listing and returns the nested MOKO resources without requiring a mapping edit; an explicit root remains authoritative.
next_action: Complete. The user can reopen Preview; the durable succeeded job and duplicate report are now recoverable without keeping the page open.

## Evidence

- Product is_active=false, active_revision_id absent; candidate mapping exists.
- Repeated authenticated GET published/mapping-imports returns 404 while product/candidate mapping/repository APIs return 200.
- ProductMappingsPage.tsx renders PublishedMappingImports unconditionally. Component treats missing SDK data as generic failure. list_published_mapping_imports deliberately rejects inactive/unpublished authority.
- Two preview jobs persist failed/processing_failed. Real Bitbucket branch and source requests return 200; both scans stop after exactly 50 source-directory GETs.
- SOURCE_DISCOVERY_BUDGET.max_pages is 50; discover_repository_sources_for_record traverses the whole repository breadth-first and raises limit_exceeded before request 51. No source file body requests observed before these failures.
- execute_preview_job converts all non-timeout exceptions into processing_failed and discards their safe failure category. Logs do not record the original exception: budget exhaustion is strongly supported, but the caught exception type was not directly captured.
- Screenshot source branch is master; default PR target is stable/feature/bravoplus-0.7.x. Import reads the source branch, not the default target. Do not change these user choices automatically.
- The 2026-09-06 20:30 UTC durable job `6ad265a5-9f73-4fec-90b7-0a210cecc17f` confirms product `test`, repository `comelit/babel`, branch `master`, diagnostic `repository_scan_limit_reached`, and a null mapping-side localization root.
- Existing read-only Babel evidence already verified `babel/src/commonMain/moko-resources` at commit `6102ff5a2ba6a50bbf1d24f75f6e2a7fb3e7c625`: 19 files were reachable within budget and duplicate diagnostics completed.
- TDD red: the rootless Babel fixture failed because `list_repository_source_page` received no `max_depth` argument.
- TDD green: 197 focused source/import/preview integration tests passed after adding recursive rootless discovery.
- Live rootless discovery against `comelit/babel:master` at commit `6102ff5a2ba6a50bbf1d24f75f6e2a7fb3e7c625` returned 19 MOKO files, 3,570,592 bytes, all under `babel/src/commonMain/moko-resources`, while the mapping root remained null.
- Durable end-to-end preview job `78ba5fe4-9b2c-4c58-ac8a-22e40405bd8f` reached `succeeded`; its complete duplicate report contains 145 groups and no issue codes.
- The isolated Phase 4 backend gate passed all 1,683 tests with Redis, PostgreSQL, Celery worker and coverage. Full mypy, Ruff lint and Ruff format gates also passed.

## Resolution

root_cause: Rootless discovery manually visited every directory breadth-first, consuming its 50-page budget before reaching the nested Babel MOKO resources. Bitbucket's recursive source-listing capability was not used.
fix: Added validated `max_depth` support to the Bitbucket source URL and adapter. Rootless discovery now requests one recursively paginated tree at depth 12 and ignores returned directory placeholders; an explicit localization root retains the existing scoped traversal and remains authoritative. Updated stale OpenAPI route inventory assertions from the preceding navigation fix.
verification: 197 focused integration tests; isolated 1,683-test backend gate with real Redis/PostgreSQL/Celery; full mypy/Ruff/format; rebuilt healthy backend and worker containers; live rootless Babel discovery and durable preview job succeeded. Duplicate diagnostics correctly remain a separate blocking result.
files_changed: backend source discovery URL/client/service, source/import/preview integration tests, two stale route-inventory assertions, and this resolved debug record. The preceding durable preview recovery changes remain part of the same uncommitted worktree.
