---
phase: 03-bitbucket-import-integration
reviewed: 2026-09-03T17:25:05Z
depth: deep
asvs_level: OWASP ASVS 5.0 Level 1
blocking_threshold: High
source_digest: e5d23977e946a9ec98ad57d1fd9893c2cec7a1d364f73c54862ef68ba668c51c
reviewed_source_digest: e5d23977e946a9ec98ad57d1fd9893c2cec7a1d364f73c54862ef68ba668c51c
diff_base: 4c557f5147038c4b09dc6dcf26d7b26675884bb5
diff_head: a6e17381b3d7001722259a3cd5ece582fc30f4f4
manifest_files_reviewed: 331
diff_files_reviewed: 84
additional_diff_files_reviewed: 21
files_reviewed: 352
final_reviewed: 2026-09-03T18:10:41Z
final_review_depth: standard
final_review_files_reviewed: 65
final_review_files_reviewed_list:
  - backend/alembic/versions/0012_import_jobs.py
  - backend/alembic/versions/0013_import_rewrite_proposals.py
  - backend/alembic/versions/0014_import_source_reference_insert_guard.py
  - backend/src/verboflex/api/v1/routes/admin_bitbucket.py
  - backend/src/verboflex/api/v1/routes/admin_mappings.py
  - backend/src/verboflex/api/v1/routes/admin_products.py
  - backend/src/verboflex/core/config.py
  - backend/src/verboflex/integrations/bitbucket/client.py
  - backend/src/verboflex/integrations/bitbucket/diagnostics.py
  - backend/src/verboflex/integrations/bitbucket/urls.py
  - backend/src/verboflex/models/__init__.py
  - backend/src/verboflex/models/import_job.py
  - backend/src/verboflex/schemas/admin_bitbucket.py
  - backend/src/verboflex/schemas/admin_discovery.py
  - backend/src/verboflex/schemas/admin_products.py
  - backend/src/verboflex/schemas/imports.py
  - backend/src/verboflex/services/bitbucket_oauth.py
  - backend/src/verboflex/services/import_jobs.py
  - backend/src/verboflex/services/products.py
  - backend/src/verboflex/services/repository_discovery.py
  - backend/src/verboflex/worker/celery_app.py
  - backend/src/verboflex/worker/import_tasks.py
  - backend/tests/api/test_admin_bitbucket.py
  - backend/tests/api/test_admin_products.py
  - backend/tests/api/test_openapi_contract.py
  - backend/tests/architecture/test_background_boundaries.py
  - backend/tests/architecture/test_phase2_gap_closure.py
  - backend/tests/architecture/test_phase2_scope.py
  - backend/tests/architecture/test_phase3_gauntlet.py
  - backend/tests/architecture/test_phase3_live_provider_smoke.py
  - backend/tests/architecture/test_phase3_scope.py
  - backend/tests/architecture/test_provider_boundaries.py
  - backend/tests/integration/test_bitbucket_diagnostics.py
  - backend/tests/integration/test_bitbucket_discovery.py
  - backend/tests/integration/test_bitbucket_http_adapter.py
  - backend/tests/integration/test_bitbucket_oauth.py
  - backend/tests/integration/test_import_jobs.py
  - backend/tests/integration/test_migrations.py
  - docs/evidence/phase-03.md
  - docs/reviews/phase-03-code-security.md
  - frontend/e2e/admin-configuration.spec.ts
  - frontend/openapi.json
  - frontend/src/api/admin-client-contract.test.ts
  - frontend/src/api/client/index.ts
  - frontend/src/api/client/sdk.gen.ts
  - frontend/src/api/client/types.gen.ts
  - frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx
  - frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx
  - frontend/src/features/admin/imports/PublishedMappingImports.test.tsx
  - frontend/src/features/admin/imports/PublishedMappingImports.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx
  - frontend/src/features/admin/imports/useImportPolling.test.ts
  - frontend/src/features/admin/imports/useImportPolling.ts
  - frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx
  - frontend/src/features/admin/mappings/ProductMappingsPage.tsx
  - frontend/src/features/admin/previews/ProductPreviewPage.test.tsx
  - frontend/src/features/admin/products/ProductConfiguration.test.tsx
  - frontend/src/features/admin/products/ProductOverviewPage.tsx
  - frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx
  - frontend/src/router.test.tsx
  - tools/phase3_gauntlet.sh
  - tools/phase3_smoke.sh
  - tools/phase3_source_manifest.txt
  - tools/verify_import_job_mutants.py
files_reviewed_list:
  - .env.example
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/STATE.md
  - .planning/WINDOWS.md
  - .planning/phases/03-bitbucket-import-integration/03-01-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-01-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-02-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-02-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-03-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-03-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-04-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-04-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-05-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-05-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-06-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-06-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-07-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-07-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-08-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-08-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-09-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-09-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-10-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-10-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-11-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-11-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-12-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-12-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-13-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-13-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-14-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-14-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-15-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-15-SUMMARY.md
  - .planning/phases/03-bitbucket-import-integration/03-16-PLAN.md
  - .planning/phases/03-bitbucket-import-integration/03-CONTEXT.md
  - .planning/phases/03-bitbucket-import-integration/03-UI-SPEC.md
  - .planning/phases/03-bitbucket-import-integration/COVERAGE.md
  - .planning/phases/03-bitbucket-import-integration/deferred-items.md
  - backend/.python-version
  - backend/alembic.ini
  - backend/alembic/env.py
  - backend/alembic/versions/0001_auth_foundation.py
  - backend/alembic/versions/0002_product_revisions.py
  - backend/alembic/versions/0003_repositories.py
  - backend/alembic/versions/0004_bitbucket_connection.py
  - backend/alembic/versions/0005_product_mappings.py
  - backend/alembic/versions/0006_preview_jobs.py
  - backend/alembic/versions/0007_preview_confirmations.py
  - backend/alembic/versions/0008_bitbucket_client_credentials.py
  - backend/alembic/versions/0009_product_graph_integrity.py
  - backend/alembic/versions/0010_preview_watchdog_index.py
  - backend/alembic/versions/0011_active_revision_revalidations.py
  - backend/alembic/versions/0012_import_jobs.py
  - backend/alembic/versions/0013_import_rewrite_proposals.py
  - backend/alembic/versions/0014_import_source_reference_insert_guard.py
  - backend/alembic/versions/__init__.py
  - backend/pyproject.toml
  - backend/src/verboflex/__init__.py
  - backend/src/verboflex/api/v1/router.py
  - backend/src/verboflex/api/v1/routes/__init__.py
  - backend/src/verboflex/api/v1/routes/admin_bitbucket.py
  - backend/src/verboflex/api/v1/routes/admin_discovery.py
  - backend/src/verboflex/api/v1/routes/admin_mappings.py
  - backend/src/verboflex/api/v1/routes/admin_previews.py
  - backend/src/verboflex/api/v1/routes/admin_products.py
  - backend/src/verboflex/api/v1/routes/admin_repositories.py
  - backend/src/verboflex/api/v1/routes/admin_users.py
  - backend/src/verboflex/api/v1/routes/auth.py
  - backend/src/verboflex/api/v1/routes/health.py
  - backend/src/verboflex/api/v1/routes/system.py
  - backend/src/verboflex/api/v1/routes/users.py
  - backend/src/verboflex/audit/__init__.py
  - backend/src/verboflex/audit/events.py
  - backend/src/verboflex/auth/__init__.py
  - backend/src/verboflex/auth/access_tokens.py
  - backend/src/verboflex/auth/identity.py
  - backend/src/verboflex/auth/login.py
  - backend/src/verboflex/auth/origin.py
  - backend/src/verboflex/auth/password_change.py
  - backend/src/verboflex/auth/passwords.py
  - backend/src/verboflex/auth/principal.py
  - backend/src/verboflex/auth/rate_limits.py
  - backend/src/verboflex/auth/refresh_sessions.py
  - backend/src/verboflex/cli.py
  - backend/src/verboflex/core/config.py
  - backend/src/verboflex/db/__init__.py
  - backend/src/verboflex/db/base.py
  - backend/src/verboflex/db/session.py
  - backend/src/verboflex/integrations/__init__.py
  - backend/src/verboflex/integrations/bitbucket/__init__.py
  - backend/src/verboflex/integrations/bitbucket/client.py
  - backend/src/verboflex/integrations/bitbucket/diagnostics.py
  - backend/src/verboflex/integrations/bitbucket/urls.py
  - backend/src/verboflex/localization/__init__.py
  - backend/src/verboflex/localization/preview/__init__.py
  - backend/src/verboflex/localization/preview/android_xml.py
  - backend/src/verboflex/localization/preview/core.py
  - backend/src/verboflex/localization/preview/ios_strings.py
  - backend/src/verboflex/localization/preview/json.py
  - backend/src/verboflex/localization/preview/qt_ts.py
  - backend/src/verboflex/localization/preview/registry.py
  - backend/src/verboflex/main.py
  - backend/src/verboflex/models/__init__.py
  - backend/src/verboflex/models/auth_session.py
  - backend/src/verboflex/models/bitbucket_connection.py
  - backend/src/verboflex/models/import_job.py
  - backend/src/verboflex/models/preview_job.py
  - backend/src/verboflex/models/product.py
  - backend/src/verboflex/models/product_mapping.py
  - backend/src/verboflex/models/repository.py
  - backend/src/verboflex/models/role.py
  - backend/src/verboflex/models/user.py
  - backend/src/verboflex/schemas/admin_bitbucket.py
  - backend/src/verboflex/schemas/admin_discovery.py
  - backend/src/verboflex/schemas/admin_mappings.py
  - backend/src/verboflex/schemas/admin_products.py
  - backend/src/verboflex/schemas/admin_repositories.py
  - backend/src/verboflex/schemas/admin_users.py
  - backend/src/verboflex/schemas/auth.py
  - backend/src/verboflex/schemas/imports.py
  - backend/src/verboflex/schemas/previews.py
  - backend/src/verboflex/schemas/system.py
  - backend/src/verboflex/schemas/users.py
  - backend/src/verboflex/scripts/__init__.py
  - backend/src/verboflex/scripts/export_openapi.py
  - backend/src/verboflex/security/__init__.py
  - backend/src/verboflex/security/secret_box.py
  - backend/src/verboflex/services/admin_users.py
  - backend/src/verboflex/services/bitbucket_oauth.py
  - backend/src/verboflex/services/import_jobs.py
  - backend/src/verboflex/services/mappings.py
  - backend/src/verboflex/services/pr_grouping.py
  - backend/src/verboflex/services/preview_jobs.py
  - backend/src/verboflex/services/products.py
  - backend/src/verboflex/services/publication.py
  - backend/src/verboflex/services/repositories.py
  - backend/src/verboflex/services/repository_discovery.py
  - backend/src/verboflex/services/system_status.py
  - backend/src/verboflex/worker/__init__.py
  - backend/src/verboflex/worker/celery_app.py
  - backend/src/verboflex/worker/import_tasks.py
  - backend/src/verboflex/worker/preview_tasks.py
  - backend/src/verboflex/worker/tasks.py
  - backend/tests/__init__.py
  - backend/tests/api/test_admin_bitbucket.py
  - backend/tests/api/test_admin_discovery.py
  - backend/tests/api/test_admin_mappings.py
  - backend/tests/api/test_admin_products.py
  - backend/tests/api/test_admin_repositories.py
  - backend/tests/api/test_admin_users.py
  - backend/tests/api/test_cors.py
  - backend/tests/api/test_health.py
  - backend/tests/api/test_me.py
  - backend/tests/api/test_openapi_contract.py
  - backend/tests/api/test_rate_limits.py
  - backend/tests/api/test_system_status.py
  - backend/tests/architecture/test_background_boundaries.py
  - backend/tests/architecture/test_phase2_gap_closure.py
  - backend/tests/architecture/test_phase2_live_provider_smoke.py
  - backend/tests/architecture/test_phase2_scope.py
  - backend/tests/architecture/test_phase2_spec_edge_traceability.py
  - backend/tests/architecture/test_phase3_gauntlet.py
  - backend/tests/architecture/test_phase3_live_provider_smoke.py
  - backend/tests/architecture/test_phase3_scope.py
  - backend/tests/architecture/test_preview_job_mutation_verifier.py
  - backend/tests/architecture/test_provider_boundaries.py
  - backend/tests/auth/__init__.py
  - backend/tests/auth/test_access_tokens.py
  - backend/tests/auth/test_bootstrap_admin.py
  - backend/tests/auth/test_login.py
  - backend/tests/auth/test_logout.py
  - backend/tests/auth/test_password_change.py
  - backend/tests/auth/test_passwords.py
  - backend/tests/auth/test_refresh.py
  - backend/tests/auth/test_roles.py
  - backend/tests/core/test_config.py
  - backend/tests/integration/__init__.py
  - backend/tests/integration/test_admin_user_concurrency.py
  - backend/tests/integration/test_bitbucket_diagnostics.py
  - backend/tests/integration/test_bitbucket_discovery.py
  - backend/tests/integration/test_bitbucket_http_adapter.py
  - backend/tests/integration/test_bitbucket_oauth.py
  - backend/tests/integration/test_import_jobs.py
  - backend/tests/integration/test_migrations.py
  - backend/tests/integration/test_preview_jobs.py
  - backend/tests/integration/test_product_graph_integrity.py
  - backend/tests/integration/test_product_publication.py
  - backend/tests/integration/test_refresh_concurrency.py
  - backend/tests/integration/test_repository_registry.py
  - backend/tests/test_cli.py
  - backend/tests/unit/localization/preview/test_android_xml.py
  - backend/tests/unit/localization/preview/test_ios_strings.py
  - backend/tests/unit/localization/preview/test_json.py
  - backend/tests/unit/localization/preview/test_qt_ts.py
  - backend/tests/unit/services/__init__.py
  - backend/tests/unit/services/test_admin_users.py
  - backend/tests/unit/services/test_mappings.py
  - backend/tests/unit/services/test_pr_grouping.py
  - backend/tests/unit/test_product_names.py
  - backend/tests/worker/test_smoke_task.py
  - backend/uv.lock
  - docker-compose.prod.yml
  - docker-compose.staging.yml
  - docker-compose.yml
  - docker/backend.Dockerfile
  - docker/frontend.Dockerfile
  - docker/frontend.nginx.conf
  - docs/evidence/phase-03.md
  - frontend/.prettierignore
  - frontend/components.json
  - frontend/e2e/admin-configuration.spec.ts
  - frontend/e2e/auth-shell.spec.ts
  - frontend/eslint.config.js
  - frontend/index.html
  - frontend/openapi-ts.config.ts
  - frontend/openapi.json
  - frontend/package-lock.json
  - frontend/package.json
  - frontend/playwright.config.ts
  - frontend/src/App.test.tsx
  - frontend/src/App.tsx
  - frontend/src/api/admin-client-contract.test.ts
  - frontend/src/api/client/client.gen.ts
  - frontend/src/api/client/client/client.gen.ts
  - frontend/src/api/client/client/index.ts
  - frontend/src/api/client/client/types.gen.ts
  - frontend/src/api/client/client/utils.gen.ts
  - frontend/src/api/client/core/auth.gen.ts
  - frontend/src/api/client/core/bodySerializer.gen.ts
  - frontend/src/api/client/core/params.gen.ts
  - frontend/src/api/client/core/pathSerializer.gen.ts
  - frontend/src/api/client/core/queryKeySerializer.gen.ts
  - frontend/src/api/client/core/serverSentEvents.gen.ts
  - frontend/src/api/client/core/types.gen.ts
  - frontend/src/api/client/core/utils.gen.ts
  - frontend/src/api/client/index.ts
  - frontend/src/api/client/sdk.gen.ts
  - frontend/src/api/client/types.gen.ts
  - frontend/src/api/config.ts
  - frontend/src/components/layout/AppShell.test.tsx
  - frontend/src/components/layout/AppShell.tsx
  - frontend/src/components/layout/ServiceStatus.tsx
  - frontend/src/components/navigation/DirtyFormNavigationGuard.test.tsx
  - frontend/src/components/navigation/DirtyFormNavigationGuard.tsx
  - frontend/src/components/ui/alert-dialog.tsx
  - frontend/src/components/ui/alert.tsx
  - frontend/src/components/ui/badge.tsx
  - frontend/src/components/ui/button.tsx
  - frontend/src/components/ui/checkbox.tsx
  - frontend/src/components/ui/dialog.tsx
  - frontend/src/components/ui/dropdown-menu.tsx
  - frontend/src/components/ui/form.tsx
  - frontend/src/components/ui/input.tsx
  - frontend/src/components/ui/label.tsx
  - frontend/src/components/ui/radio-group.tsx
  - frontend/src/components/ui/select.tsx
  - frontend/src/components/ui/separator.tsx
  - frontend/src/components/ui/sheet.tsx
  - frontend/src/components/ui/sidebar.tsx
  - frontend/src/components/ui/skeleton.tsx
  - frontend/src/components/ui/sonner.tsx
  - frontend/src/components/ui/table.tsx
  - frontend/src/components/ui/tabs.tsx
  - frontend/src/components/ui/textarea.tsx
  - frontend/src/components/ui/tooltip.tsx
  - frontend/src/features/admin/AdminAccessDenied.tsx
  - frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx
  - frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx
  - frontend/src/features/admin/imports/PublishedMappingImports.test.tsx
  - frontend/src/features/admin/imports/PublishedMappingImports.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx
  - frontend/src/features/admin/imports/useImportPolling.test.ts
  - frontend/src/features/admin/imports/useImportPolling.ts
  - frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx
  - frontend/src/features/admin/mappings/ProductMappingsPage.tsx
  - frontend/src/features/admin/previews/ProductPreviewPage.test.tsx
  - frontend/src/features/admin/previews/ProductPreviewPage.tsx
  - frontend/src/features/admin/previews/usePreviewPolling.test.ts
  - frontend/src/features/admin/previews/usePreviewPolling.ts
  - frontend/src/features/admin/products/ProductConfiguration.test.tsx
  - frontend/src/features/admin/products/ProductDetailLayout.tsx
  - frontend/src/features/admin/products/ProductOverviewPage.tsx
  - frontend/src/features/admin/products/ProductWizardPage.tsx
  - frontend/src/features/admin/products/ProductsPage.tsx
  - frontend/src/features/admin/repositories/ProductRepositoriesPage.test.tsx
  - frontend/src/features/admin/repositories/ProductRepositoriesPage.tsx
  - frontend/src/features/admin/useCursorCollection.test.ts
  - frontend/src/features/admin/useCursorCollection.ts
  - frontend/src/features/admin/users/TemporaryPasswordDialog.tsx
  - frontend/src/features/admin/users/UserDialog.tsx
  - frontend/src/features/admin/users/UsersPage.test.tsx
  - frontend/src/features/admin/users/UsersPage.tsx
  - frontend/src/features/admin/users/userRoles.ts
  - frontend/src/features/auth/ChangePasswordPage.test.tsx
  - frontend/src/features/auth/ChangePasswordPage.tsx
  - frontend/src/features/auth/LoginPage.test.tsx
  - frontend/src/features/auth/LoginPage.tsx
  - frontend/src/features/auth/session.property.test.ts
  - frontend/src/features/auth/session.test.tsx
  - frontend/src/features/auth/session.tsx
  - frontend/src/features/auth/storage-guard.test.ts
  - frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx
  - frontend/src/features/workspace/WorkspaceOverviewPage.tsx
  - frontend/src/hooks/use-mobile.ts
  - frontend/src/index.css
  - frontend/src/lib/utils.ts
  - frontend/src/main.test.ts
  - frontend/src/main.tsx
  - frontend/src/pages/Dashboard.tsx
  - frontend/src/router.test.tsx
  - frontend/src/router.tsx
  - frontend/src/styles/theme.test.ts
  - frontend/stryker.config.mjs
  - frontend/tsconfig.json
  - frontend/vite.config.ts
  - tools/adversarial_auth.sh
  - tools/equivalent_mutants.txt
  - tools/frontend_coverage_exclusions.txt
  - tools/gauntlet.sh
  - tools/mutmut-property.toml
  - tools/phase2_compose_flow.py
  - tools/phase2_gauntlet.sh
  - tools/phase2_live_provider.py
  - tools/phase2_mock_provider.py
  - tools/phase2_smoke.sh
  - tools/phase2_source_manifest.txt
  - tools/phase3_gauntlet.sh
  - tools/phase3_smoke.sh
  - tools/phase3_source_manifest.txt
  - tools/real_smoke.sh
  - tools/source_manifest.txt
  - tools/source_state.sh
  - tools/tests/test_adversarial_auth.sh
  - tools/tests/test_gauntlet.sh
  - tools/tests/test_real_smoke.sh
  - tools/tests/test_source_state.sh
  - tools/verify_android_preview_mutants.py
  - tools/verify_bitbucket_discovery_mutants.py
  - tools/verify_bitbucket_http_adapter_mutants.py
  - tools/verify_bitbucket_oauth_mutants.py
  - tools/verify_equivalent_mutants.py
  - tools/verify_import_job_mutants.py
  - tools/verify_ios_preview_mutants.py
  - tools/verify_mapping_api_mutants.py
  - tools/verify_preview_job_mutants.py
  - tools/verify_product_api_mutants.py
  - tools/verify_product_publication_mutants.py
  - tools/verify_rate_limit_boundary_mutant.py
  - tools/verify_repository_api_mutants.py
findings:
  critical: 0
  warning: 10
  info: 0
  total: 10
status: issues_found
closeout_blocked: false
---

# Phase 3: Code Review Report

**Reviewed:** 2026-09-03T17:25:05Z
**Depth:** deep
**ASVS level:** OWASP ASVS 5.0 Level 1
**Files reviewed:** 352 (331 canonical manifest paths plus 21 additional Phase 3 diff paths; the diff itself contains 84 paths)
**Status:** issues_found — no blocker at the configured High threshold

## Narrative Findings (AI reviewer)

### Summary

This is a fresh adversarial review bound to source digest `e5d23977e946a9ec98ad57d1fd9893c2cec7a1d364f73c54862ef68ba668c51c`, independently reproduced with `tools/source_state.sh` and `tools/phase3_source_manifest.txt`. The scope is the union of all 331 manifest-selected paths and all 84 paths changed from exact base `4c557f5147038c4b09dc6dcf26d7b26675884bb5` through exact head `a6e17381b3d7001722259a3cd5ece582fc30f4f4`: 352 unique paths. The 21 diff-only additions were retained, and lockfiles, configuration, deployment files, every migration, verifier scripts, tests, generated API artifacts, evidence, and planning contracts were not silently filtered.

Methodology combined language-aware review of every selected path and the full base-to-head diff with cross-module import/call-chain tracing, API/schema/type-boundary comparison, PostgreSQL constraint/trigger/lock-order analysis, provider-method and URL-allowlist tracing, credential/log-dataflow inspection, focused anti-pattern scans, and dependency review. Fresh checks included Ruff, mypy, ESLint, TypeScript typecheck, `npm audit --json --omit=optional`, `pip-audit`, `git diff --check`, and independent digest reproduction. The complete post-remediation gauntlet is recorded as 14/14 in 367 seconds (backend 952/952, frontend 356/356, backend mutants 6/6, frontend mutants 25/25, browser 2/2, architecture/provider 116/116, API coverage 56 rows, zero provider-resource writes, clean cleanup); it was treated as supporting evidence rather than proof.

OAuth acquisition requires exact `pullrequest:write`, confines accepted scope material to the explicit implication closure, stores access-only encrypted credentials, and forces legacy generations through reauthorization. Executable provider-resource traffic remains GET-only through Phase 8: branch creation, source commit, and pull-request creation are declarative/rejected identities, while the OAuth token endpoint is the separately bounded POST. D-15 diagnostics retain only validated event/category/status/correlation/timing fields; negative dataflow and tests exclude provider bodies, tokens, client secrets, authorization headers, source text, unsafe URLs/paths, and traceback context. The five admin import operations remain Admin-authorized with closed schemas and opaque revision/filter-bound cursor contracts. The exact 26 UI identities, bounded polling/recovery states, smoke redaction/method audit, and cleanup contracts were also traced without a proven Critical/High bypass.

All three requested provenance remediations hold on this digest. Migration 0014 takes an execution row lock and accepts INSERT only while the execution is exactly `running`; `finish_import_execution()` flushes references before terminalization. UPDATE now rejects any `execution_id` change before ownership evaluation, so a row cannot be reparented into a terminal execution; the committed PostgreSQL RED/GREEN regression exercises that path. For separate mappings with mixed descendant/diverged sides, `classify_source_movement()` gathers and validates a complete delta for every non-equal side before constructing confirmation authority.

- Review-status: CLOSED
- Open-critical-high: 0
- Full-gauntlet-status: PASS
- Reviewed-source-digest: `e5d23977e946a9ec98ad57d1fd9893c2cec7a1d364f73c54862ef68ba668c51c`

### Final standard review addendum

The mandatory final pass was completed on 2026-09-03T18:10:41Z over the 65 files supplied by the Phase 3 closeout workflow. The earlier digest-bound deep/ASVS review remains intact above: its source digest was independently reproduced again as `e5d23977e946a9ec98ad57d1fd9893c2cec7a1d364f73c54862ef68ba668c51c`, so its provenance, closed remediation evidence, and eight original warnings still apply to the same source bytes. The final pass reviewed the explicitly supplied source, migration, test, generated-contract, evidence, and verifier paths, including `docs/reviews/phase-03-code-security.md`, which is intentionally outside the self-excluding review digest.

No BLOCKER/Critical issue was proven. The final pass found two additional WARNING defects (WR-09 and WR-10), bringing the combined report total to ten warnings. These findings do not change `Open-critical-high: 0`, `Review-status: CLOSED`, or the recorded ASVS blocking-threshold decision; they do require follow-up for correct recovery and accessible error focus.

## Closed Remediation Findings

- **Late INSERT/finalization race:** closed. `backend/alembic/versions/0014_import_source_reference_insert_guard.py:25-38` locks the target execution and requires exact `running`; `backend/src/verboflex/services/import_jobs.py:1703-1728` flushes provenance before setting `succeeded`.
- **Cross-execution UPDATE reparenting:** closed. `backend/alembic/versions/0014_import_source_reference_insert_guard.py:40-44` makes `execution_id` immutable, and `backend/tests/integration/test_migrations.py:776-823` proves the terminal reparent attempt fails in PostgreSQL.
- **Mixed descendant/diverged delta omission:** closed. `backend/src/verboflex/services/import_jobs.py:537-567` requests and validates diffstat for every non-equal side, including descendants paired with a diverged side.

## Warnings

### WR-01: OAuth token lifetime is not upper-bounded before datetime arithmetic

**Classification:** WARNING  
**File:** `backend/src/verboflex/services/bitbucket_oauth.py:600-623`  
**Supporting path:** `backend/src/verboflex/services/bitbucket_oauth.py:465-483`

**Evidence:** `_require_client_credentials_response()` rejects non-positive and non-integer lifetimes but has no upper-bound predicate at lines 618-620. `_persist_access_only()` then performs `acquired_at + timedelta(seconds=expires_in)` at line 479 after the exchange wrapper at lines 453-463 has already returned.

**Issue:** Token validation accepts every positive integer `expires_in`. A syntactically valid but oversized provider value can make `timedelta(seconds=expires_in)` or the datetime addition raise `OverflowError` outside the exchange-validation wrapper, yielding an unhandled connection/reconnection failure instead of the closed OAuth error contract.

**Fix:** Enforce an explicit maximum provider lifetime before persistence and translate arithmetic overflow to `OAuthConnectionUnavailable`. Add boundary tests for the maximum, maximum-plus-one, and integers beyond Python datetime/timedelta limits.

### WR-02: A stale start-import response can overwrite a newly selected product

**Classification:** WARNING  
**File:** `frontend/src/features/admin/imports/PublishedMappingImports.tsx:596-648`  
**Supporting path:** `frontend/src/features/admin/imports/PublishedMappingImports.tsx:430-529`

**Evidence:** The POST at lines 618-621 receives no `signal`; after it resolves, lines 625-629 unconditionally toast and call the render-captured loader. That loader increments the one shared generation, aborts the currently registered controller, and writes its captured product's collection at lines 430-485. The dependency-change cleanup at lines 525-528 aborts only the collection controller, not the pending POST.

**Issue:** `startImport()` has neither an abort signal nor a mutation generation/product identity check. If props change while its POST is pending, the old closure can resume and invoke its old `loadCompleteCollection(true)`; that shared loader increments the component generation, aborts the current product's fetch, requests the old product, and writes the old product's rows into the still-mounted component. Failure/pending state updates are likewise keyed only by mapping ID.

**Fix:** Bind each mutation to a product/access-token identity and generation, pass an `AbortSignal` to the generated request, abort on dependency change/unmount, and check current identity before toast, refresh, failure, focus, or pending-state updates. Add a deferred-response test that rerenders from product A to B during the POST and proves A cannot cancel or overwrite B.

### WR-03: Rewrite confirmation's identity guard compares two values from the same stale closure

**Classification:** WARNING  
**File:** `frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx:340-399`

**Evidence:** Line 346 assigns `expectedIdentity` from the render-local `importIdentity`; the comparisons at lines 364, 381, and 393 compare it with that same render-local constant. Unlike comparison loading at lines 280-331, confirmation passes no `AbortSignal` and checks neither `requestGenerationRef.current` nor a live identity ref before callbacks, toast, close, and `finally` state updates.

**Issue:** `expectedIdentity` and `importIdentity` are captured by the same render, so the checks at lines 364, 381, and 393 cannot detect a later prop/dialog identity. Confirmation also lacks an abort signal. An old completion can therefore invoke `onConfirmed`, publish success UI, close a newer dialog, or clear a newer operation's pending state after navigation/rerender.

**Fix:** Store the latest identity in a ref, allocate a dedicated confirmation generation and `AbortController`, and compare the captured identity/generation with the live refs before every side effect, including `finally`. Add a test that changes product/import identity while confirmation is pending and proves the old result performs no callback, close, toast, focus, or state update.

### WR-04: The canonical digest excludes an executable test registry

**Classification:** WARNING  
**File:** `tools/phase3_source_manifest.txt:9-12`  
**Supporting paths:** `backend/tests/architecture/test_phase2_spec_edge_traceability.py:17-22`, `backend/tests/architecture/test_phase2_spec_edge_traceability.py:104-109`, `backend/tests/architecture/phase2_spec_edge_matrix.json:1`

**Evidence:** The only backend test include is `backend/tests/**/*.py` at manifest line 9. The tracked JSON file is therefore absent from the independently resolved 331-path manifest, while the test binds `MATRIX_PATH` to that file at line 21 and parses it as its literal semantic registry at lines 104-109.

**Issue:** The manifest includes Python test files but excludes the tracked JSON matrix consumed as executable semantic test input. That registry can be weakened or changed without changing the supposedly immutable review digest, even though the Phase 3 gauntlet runs the consuming test.

**Fix:** Add the exact JSON registry or a bounded test-fixture glob to the canonical manifest, and extend the source-state self-test with a non-Python test-input mutation negative control. Re-run the full gauntlet and obtain a new digest/review.

### WR-05: The locked frontend development graph has two moderate vulnerabilities

**Classification:** WARNING  
**File:** `frontend/package-lock.json:12991-13010`  
**Supporting path:** `frontend/package.json:35-40`

**Evidence:** The fresh `npm audit --json --omit=optional` result for this digest reports `qs` and `typed-rest-client` as two moderate vulnerabilities, zero High/Critical, and fixes available. The lockfile pins `typed-rest-client@2.3.1` and its nested `qs@6.15.1` at lines 12991-13010; the chain is reached through the development mutation tooling listed at package lines 35-40. A fresh `pip-audit` reported no known Python vulnerabilities.

**Issue:** The current `npm audit --json --omit=optional` reports two moderate findings: vulnerable `qs@6.15.1` and its `typed-rest-client@2.3.1` parent, with fixes available. This is a development/mutation-tool chain rather than a production dependency, so it is below the configured High blocking threshold, but it weakens the build/test supply chain.

**Fix:** Upgrade the Stryker/typed-rest-client chain or apply a compatible override to `qs>=6.16.0`, regenerate the lockfile with the pinned package manager, and rerun audit, tests, and mutation gates. (`pip-audit` found zero known Python vulnerabilities at review time.)

### WR-06: The included Phase 2 Compose verifier is no longer executable against the current API

**Classification:** WARNING  
**File:** `tools/phase2_compose_flow.py:89-107`  
**Supporting paths:** `tools/phase2_compose_flow.py:530-547`, `backend/src/verboflex/api/v1/routes/admin_bitbucket.py:154-218`

**Evidence:** The script asserts `scope_profile == "repository"` and the old read-only label at lines 106-107, then POSTs `/oauth/start` and follows an OAuth callback at lines 530-546. Current routes expose only `/connect`, `/reconnect`, and `/revoke` at `admin_bitbucket.py:154-218`, and the public schema fixes `repository_and_pull_request` as the profile.

**Issue:** The verifier still requires the legacy `repository` scope label and calls the removed `/oauth/start` and callback flow. Current production uses client-credentials `/connect` and `/reconnect` with `repository_and_pull_request`. The script is inside the canonical Phase 3 source set but is not exercised by the Phase 3 gauntlet, so a developer invoking the advertised verifier gets a deterministic contract failure unrelated to product health.

**Fix:** Update the flow to the current client-credentials endpoints/schema and safe mock provider, or explicitly retire/remove it and replace every caller/documented entry point. Add a lightweight gauntlet check that every retained top-level verifier can at least validate its current API shape.

### WR-07: The environment template omits settings required by the default Compose stack

**Classification:** WARNING  
**File:** `.env.example:1-13`  
**Supporting path:** `docker-compose.yml:21-27`

**Evidence:** `.env.example` ends at line 13 without any Bitbucket or import variables. Default Compose interpolation makes all three Bitbucket variables mandatory at lines 21-23 and exposes only the preview limits at lines 24-27; `Settings` separately defines four import time/watchdog variables at `backend/src/verboflex/core/config.py:50-53` that Compose does not forward.

**Issue:** The template says to copy and replace placeholders, but it contains none of the three required Bitbucket client-credentials/keyring variables and none of the bounded preview/watchdog controls consumed by Compose. Following the template therefore makes Compose interpolation fail before the application starts, with no safe example for the required encrypted-token keyring shape. The Phase 3 import timing controls are likewise absent from the documented template and are not forwarded by the default Compose environment, so operators cannot tune them through the advertised path.

**Fix:** Add non-secret placeholders and concise generation instructions for `VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID`, `VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET`, and `VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING`, plus the bounded Phase 3 timing variables. Keep all real values excluded from version control.

### WR-08: Container inputs are tag-pinned but not digest-pinned

**Classification:** WARNING  
**File:** `docker/backend.Dockerfile:3-5`  
**Supporting paths:** `docker/backend.Dockerfile:22`, `docker/frontend.Dockerfile:3-17`, `docker-compose.yml:34-52`, `docker-compose.prod.yml:19-32`, `docker-compose.staging.yml:19-32`

**Evidence:** The backend uses `ghcr.io/astral-sh/uv:0.11.12` and `python:3.14-slim`; the frontend uses `node:24-alpine` and `nginx:1.29-alpine`; Compose uses `postgres:18-alpine`, `redis:7-alpine`, and `${VERBOFLEX_IMAGE_TAG}` application references. None of those references contains an `@sha256:` content digest.

**Issue:** Builder/runtime bases, PostgreSQL, Redis, and deployment application images use mutable tags. The same reviewed source and lockfiles can therefore build or deploy different bytes later, undermining reproducibility and supply-chain attribution.

**Fix:** Pin external images by immutable digest (while retaining human-readable tags if desired), deploy application images by content digest or immutable release identifier, and automate reviewed digest updates with rebuild/smoke/security gates.

### WR-09: A successful baseline confirmation is reported as a failed update when collection refresh fails

**Classification:** WARNING
**File:** `frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx:350-395`
**Supporting path:** `frontend/src/features/admin/imports/PublishedMappingImports.tsx:876-885`

**Evidence:** The server mutation completes and returns a valid updated import at lines 351-379. The dialog then awaits the parent collection refresh at line 380. If that separate GET path returns `false`, lines 384-386 set the generic confirmation error; the rendered message at lines 519-524 states that the baseline could not be updated and instructs the administrator to run the import again. The parent callback confirms that the boolean represents only `loadCompleteCollection(true)`, not the already completed mutation. The dialog tests cover a successful refresh and a 409 mutation but do not cover `onConfirmed()` resolving `false`.

**Issue:** The API has already atomically confirmed the new baseline before the refresh begins. Reporting that committed operation as failed gives the administrator false state and leaves the confirmation dialog open with an action that can only become stale on retry. This can drive unnecessary imports and obscures the actual recovery action: refresh the view, not reconfirm the baseline.

**Fix:** Model mutation success and collection-refresh failure as distinct states. Once a valid confirmation response is received, mark the confirmation successful and prevent resubmission; if refresh fails, show a bounded message such as “Baseline updated; current status could not be refreshed” with a status-refresh/close path. Add a regression test where confirmation succeeds and `onConfirmed()` resolves `false`, asserting that the UI never claims the baseline update failed and cannot submit the same proposal again.

### WR-10: Mobile import failures attempt to focus the hidden desktop error

**Classification:** WARNING
**File:** `frontend/src/features/admin/imports/PublishedMappingImports.tsx:585-642`
**Supporting paths:** `frontend/src/features/admin/imports/PublishedMappingImports.tsx:719-803`, `frontend/src/features/admin/imports/PublishedMappingImports.tsx:805-870`

**Evidence:** `mutationErrorRefs` stores one element per mapping and the failure handler focuses that element at lines 640-642. Only the desktop `RowError` installs `focusRef` at lines 749-752. The mobile `RowError` at lines 841-847 installs no ref, while the desktop table remains mounted under `hidden ... md:block` and is therefore `display:none` on the mobile breakpoint.

**Issue:** At mobile widths, a mutation or post-acceptance refresh failure renders the visible mobile alert but attempts to focus its hidden desktop duplicate. Browsers cannot reliably move focus into a `display:none` subtree, so keyboard and assistive-technology users are not taken to the visible row-local error. The current mobile test checks layout/action sizing only and does not exercise failure focus in a real browser viewport.

**Fix:** Keep a ref to the active responsive error (or render one shared row error instead of two mounted duplicates) and focus only an element whose layout is visible. Add a mobile-viewport browser regression that rejects the mutation and verifies `document.activeElement` is the visible mobile alert.

---

_Reviewed: 2026-09-03T17:25:05Z_  
_Reviewer: independent typed agent (gsd-code-reviewer)_  
_Depth: deep_  
_ASVS: OWASP ASVS 5.0 Level 1_  
_Final standard pass: 2026-09-03T18:10:41Z over 65 workflow-supplied files_
