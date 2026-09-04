---
phase: 03-bitbucket-import-integration
reviewed: 2026-09-04T10:44:54Z
depth: standard
asvs_level: OWASP ASVS 5.0 Level 1
blocking_threshold: High
source_digest: 64bdc9a3e5c4085036c78732b4285609dd3a00c6c307b7c33f40149b5fb0684b
reviewed_source_digest: 64bdc9a3e5c4085036c78732b4285609dd3a00c6c307b7c33f40149b5fb0684b
diff_base: ecf2880
diff_head: 65e7316cd2dda7132cc2f805f2dd3a7fa6b47ff7
files_reviewed: 8
files_reviewed_list:
  - backend/tests/architecture/test_phase3_gauntlet.py
  - frontend/src/features/admin/imports/PublishedMappingImports.test.tsx
  - frontend/src/features/admin/imports/PublishedMappingImports.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx
  - frontend/src/features/admin/imports/mutationAuthority.test.ts
  - frontend/src/features/admin/imports/mutationAuthority.ts
  - tools/phase3_gauntlet.sh
historical_post_remediation_reviewed: 2026-09-04T07:57:33Z
historical_post_remediation_review_depth: standard
historical_post_remediation_diff_base: fdcc48b
historical_post_remediation_diff_head: 0ebd82c2f025a5a219fcf8b86db8c7944ef7a0be
historical_post_remediation_source_digest: 0227a4fbd295caf78a676cb798e5cabf378710884d1418a5262df7bf33512534
historical_post_remediation_files_reviewed: 10
historical_post_remediation_files_reviewed_list:
  - backend/tests/architecture/test_phase3_gauntlet.py
  - frontend/e2e/admin-configuration.spec.ts
  - frontend/src/features/admin/imports/PublishedMappingImports.test.tsx
  - frontend/src/features/admin/imports/PublishedMappingImports.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx
  - frontend/src/features/admin/imports/mutationAuthority.test.ts
  - frontend/src/features/admin/imports/mutationAuthority.ts
  - frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx
  - tools/phase3_gauntlet.sh
historical_nyquist_reviewed: 2026-09-03T21:04:31Z
historical_nyquist_review_depth: standard
historical_nyquist_diff_base: 90ed776
historical_nyquist_diff_head: fdcc48b0beb0fa9bf6dc4bd8e5fa178924536ac7
historical_nyquist_source_digest: 2b1b22590d42d8333b41547dddb90d8a484b5fe08dbaed5032c86877b8831b9c
historical_nyquist_files_reviewed: 10
historical_nyquist_files_reviewed_list:
  - backend/src/verboflex/services/bitbucket_oauth.py
  - backend/tests/integration/test_bitbucket_oauth.py
  - backend/tests/architecture/test_phase3_gauntlet.py
  - frontend/src/features/admin/imports/PublishedMappingImports.tsx
  - frontend/src/features/admin/imports/PublishedMappingImports.test.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx
  - frontend/e2e/admin-configuration.spec.ts
  - tools/phase3_source_manifest.txt
  - tools/phase3_gauntlet.sh
historical_deep_reviewed: 2026-09-03T17:25:05Z
historical_deep_review_depth: deep
historical_manifest_files_reviewed: 331
historical_diff_files_reviewed: 84
historical_additional_diff_files_reviewed: 21
historical_files_reviewed: 352
historical_final_reviewed: 2026-09-03T18:10:41Z
historical_final_review_depth: standard
historical_final_review_files_reviewed: 65
historical_final_review_files_reviewed_list:
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
historical_deep_files_reviewed_list:
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
  warning: 4
  info: 0
  total: 4
status: issues_found
closeout_blocked: false
nyquist_closeout_ready: true
resolved_warning_ids:
  - WR-01
  - WR-02
  - WR-03
  - WR-04
  - WR-09
  - WR-10
  - WR-11
  - WR-12
  - WR-13
  - WR-14
open_warning_ids:
  - WR-05
  - WR-06
  - WR-07
  - WR-08
---

# Phase 3: Code Review Report

**Reviewed:** 2026-09-04T10:44:54Z
**Depth:** standard final lifecycle-remediation review
**ASVS level:** OWASP ASVS 5.0 Level 1
**Files reviewed:** 8 explicitly scoped implementation, test, and gauntlet files
**Status:** issues_found — zero Critical/High findings; WR-11 through WR-14 are resolved and only the carried WR-05 through WR-08 warnings remain open

## Narrative Findings (AI reviewer)

### Final lifecycle-remediation review summary

This standard review is bound to source digest `64bdc9a3e5c4085036c78732b4285609dd3a00c6c307b7c33f40149b5fb0684b` and the exact delta from `ecf2880` through `65e7316cd2dda7132cc2f805f2dd3a7fa6b47ff7`. All eight workflow-supplied implementation, test, architecture-contract, and gauntlet files were read in full and compared with the base. Independent checks passed: the Phase 3 gauntlet contract 7/7, the three focused frontend suites 35/35, and a fresh Stryker run that instrumented exactly 52 mutants at only the declared locations and killed 52/52. The Phase 3 source-state command independently reproduced the requested digest. The persistent full-gauntlet records agree: 14/14 ordered layers in 781 seconds on the same digest, with backend 958/958, frontend 368/368, backend mutation 6/6, frontend mutation 52/52, Playwright 3/3, and architecture/provider 119/119. Those records were used as supporting evidence, not as a substitute for inspection.

WR-13 is resolved. Rewrite confirmation now requires exact live identity, exact request-token ownership, the exact current controller, and a non-aborted signal before its `finally` may clear progress. The decision is evaluated before owned cleanup removes the token/controller. The deferred unmount component test observes the finalization decision itself as `false`, while the live uncommitted 409 path observes `true`; the helper truth table also retains committed, mismatched, revoked, null-controller, and aborted neighbors.

WR-14 is resolved. Start-import finalization now folds exact token/controller ownership and the non-aborted signal into live authority. Cleanup aborts and clears every pending request, so an unmounted completion makes the finalization decision `false` and cannot invoke `setPendingMappings`; the live request path retains a `true` decision and clears pending state after deleting its owned entry. Replacement requests with the same mapping ID remain protected by unique symbols and exact controller identity.

The test changes strengthen the lifecycle oracle rather than weakening visible-effect assertions: abort, callback, toast, close, refresh, and focus checks remain, and the new observers expose the formerly masked `finally` decisions directly. The gauntlet owns exactly five semantic markers, resolves them dynamically, and rejects marker/location drift. No new Critical, Warning, or Info defect was proven in the scoped delta. Four earlier nonblocking warnings (WR-05 through WR-08) remain carried forward on unchanged inputs.

- Review-status: CLOSED at the configured High threshold
- Open-critical-high: 0
- Full-gauntlet-status: PASS (14/14)
- Reviewed-source-digest: `64bdc9a3e5c4085036c78732b4285609dd3a00c6c307b7c33f40149b5fb0684b`
- Nyquist-closeout-ready: YES

### Remediation disposition

| Historical finding | Disposition on current digest | Evidence |
| --- | --- | --- |
| WR-01 | **RESOLVED** | Expiry is computed before row mutation and both timedelta/datetime overflow paths map to `OAuthConnectionUnavailable`; boundary regressions are in the full backend suite. |
| WR-02 | **RESOLVED for the reported product-authority race** | Live `{accessToken, productId, statusFilter}` identity and request-token ownership suppress obsolete product completions; the deferred product-switch regression passes. See WR-14 for unmount lifecycle scope. |
| WR-03 | **RESOLVED for the reported product/import replacement race** | Live import identity plus request token suppress callbacks, toast, close, focus, and finalization after product/import replacement; both deferred completion regressions pass. See WR-13 for access-token-only/unmount lifecycle scope. |
| WR-04 | **RESOLVED** | The executable JSON edge matrix is explicitly included, and the negative control proves its mutation changes the digest. |
| WR-09 | **RESOLVED** | Confirmation reaches committed state before refresh; false/throwing refresh cannot relabel the mutation as failed or enable resubmission. |
| WR-10 | **RESOLVED** | Desktop/mobile refs are separate, rendered geometry selects the visible target, focus runs after error-state commit, and the mobile regression is now part of the canonical browser gate. |
| WR-11 | **RESOLVED** | Stable `PW3-C27` ownership is present in the spec, exact canonical grep, architecture contract, and independent 3/3 browser run. |
| WR-12 | **RESOLVED** | Five marker-owned predicates, exact marker/location validation, truth-table neighbors, and an independent 52/52 Stryker run preserve the remediation surface. |
| WR-13 | **RESOLVED** | Rewrite `finally` requires live identity, exact token/controller ownership, and a non-aborted signal; unmount observes `false`, while live uncommitted failure observes `true`. |
| WR-14 | **RESOLVED** | Start-import `finally` uses the same live identity and exact token/controller authority as response handling; cleanup revokes it before an obsolete completion can update pending state. |

### Historical deep-review summary (digest `e5d23977e946a9ec98ad57d1fd9893c2cec7a1d364f73c54862ef68ba668c51c`)

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

### WR-01 [RESOLVED on `2b1b2259`]: OAuth token lifetime is not upper-bounded before datetime arithmetic

**Classification:** WARNING  
**File:** `backend/src/verboflex/services/bitbucket_oauth.py:600-623`  
**Supporting path:** `backend/src/verboflex/services/bitbucket_oauth.py:465-483`

**Evidence:** `_require_client_credentials_response()` rejects non-positive and non-integer lifetimes but has no upper-bound predicate at lines 618-620. `_persist_access_only()` then performs `acquired_at + timedelta(seconds=expires_in)` at line 479 after the exchange wrapper at lines 453-463 has already returned.

**Issue:** Token validation accepts every positive integer `expires_in`. A syntactically valid but oversized provider value can make `timedelta(seconds=expires_in)` or the datetime addition raise `OverflowError` outside the exchange-validation wrapper, yielding an unhandled connection/reconnection failure instead of the closed OAuth error contract.

**Fix:** Enforce an explicit maximum provider lifetime before persistence and translate arithmetic overflow to `OAuthConnectionUnavailable`. Add boundary tests for the maximum, maximum-plus-one, and integers beyond Python datetime/timedelta limits.

### WR-02 [RESOLVED on `2b1b2259`]: A stale start-import response can overwrite a newly selected product

**Classification:** WARNING  
**File:** `frontend/src/features/admin/imports/PublishedMappingImports.tsx:596-648`  
**Supporting path:** `frontend/src/features/admin/imports/PublishedMappingImports.tsx:430-529`

**Evidence:** The POST at lines 618-621 receives no `signal`; after it resolves, lines 625-629 unconditionally toast and call the render-captured loader. That loader increments the one shared generation, aborts the currently registered controller, and writes its captured product's collection at lines 430-485. The dependency-change cleanup at lines 525-528 aborts only the collection controller, not the pending POST.

**Issue:** `startImport()` has neither an abort signal nor a mutation generation/product identity check. If props change while its POST is pending, the old closure can resume and invoke its old `loadCompleteCollection(true)`; that shared loader increments the component generation, aborts the current product's fetch, requests the old product, and writes the old product's rows into the still-mounted component. Failure/pending state updates are likewise keyed only by mapping ID.

**Fix:** Bind each mutation to a product/access-token identity and generation, pass an `AbortSignal` to the generated request, abort on dependency change/unmount, and check current identity before toast, refresh, failure, focus, or pending-state updates. Add a deferred-response test that rerenders from product A to B during the POST and proves A cannot cancel or overwrite B.

### WR-03 [RESOLVED on `2b1b2259`]: Rewrite confirmation's identity guard compares two values from the same stale closure

**Classification:** WARNING  
**File:** `frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx:340-399`

**Evidence:** Line 346 assigns `expectedIdentity` from the render-local `importIdentity`; the comparisons at lines 364, 381, and 393 compare it with that same render-local constant. Unlike comparison loading at lines 280-331, confirmation passes no `AbortSignal` and checks neither `requestGenerationRef.current` nor a live identity ref before callbacks, toast, close, and `finally` state updates.

**Issue:** `expectedIdentity` and `importIdentity` are captured by the same render, so the checks at lines 364, 381, and 393 cannot detect a later prop/dialog identity. Confirmation also lacks an abort signal. An old completion can therefore invoke `onConfirmed`, publish success UI, close a newer dialog, or clear a newer operation's pending state after navigation/rerender.

**Fix:** Store the latest identity in a ref, allocate a dedicated confirmation generation and `AbortController`, and compare the captured identity/generation with the live refs before every side effect, including `finally`. Add a test that changes product/import identity while confirmation is pending and proves the old result performs no callback, close, toast, focus, or state update.

### WR-04 [RESOLVED on `2b1b2259`]: The canonical digest excludes an executable test registry

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

### WR-09 [RESOLVED on `2b1b2259`]: A successful baseline confirmation is reported as a failed update when collection refresh fails

**Classification:** WARNING
**File:** `frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx:350-395`
**Supporting path:** `frontend/src/features/admin/imports/PublishedMappingImports.tsx:876-885`

**Evidence:** The server mutation completes and returns a valid updated import at lines 351-379. The dialog then awaits the parent collection refresh at line 380. If that separate GET path returns `false`, lines 384-386 set the generic confirmation error; the rendered message at lines 519-524 states that the baseline could not be updated and instructs the administrator to run the import again. The parent callback confirms that the boolean represents only `loadCompleteCollection(true)`, not the already completed mutation. The dialog tests cover a successful refresh and a 409 mutation but do not cover `onConfirmed()` resolving `false`.

**Issue:** The API has already atomically confirmed the new baseline before the refresh begins. Reporting that committed operation as failed gives the administrator false state and leaves the confirmation dialog open with an action that can only become stale on retry. This can drive unnecessary imports and obscures the actual recovery action: refresh the view, not reconfirm the baseline.

**Fix:** Model mutation success and collection-refresh failure as distinct states. Once a valid confirmation response is received, mark the confirmation successful and prevent resubmission; if refresh fails, show a bounded message such as “Baseline updated; current status could not be refreshed” with a status-refresh/close path. Add a regression test where confirmation succeeds and `onConfirmed()` resolves `false`, asserting that the UI never claims the baseline update failed and cannot submit the same proposal again.

### WR-10 [RESOLVED on `2b1b2259`]: Mobile import failures attempt to focus the hidden desktop error

**Classification:** WARNING
**File:** `frontend/src/features/admin/imports/PublishedMappingImports.tsx:585-642`
**Supporting paths:** `frontend/src/features/admin/imports/PublishedMappingImports.tsx:719-803`, `frontend/src/features/admin/imports/PublishedMappingImports.tsx:805-870`

**Evidence:** `mutationErrorRefs` stores one element per mapping and the failure handler focuses that element at lines 640-642. Only the desktop `RowError` installs `focusRef` at lines 749-752. The mobile `RowError` at lines 841-847 installs no ref, while the desktop table remains mounted under `hidden ... md:block` and is therefore `display:none` on the mobile breakpoint.

**Issue:** At mobile widths, a mutation or post-acceptance refresh failure renders the visible mobile alert but attempts to focus its hidden desktop duplicate. Browsers cannot reliably move focus into a `display:none` subtree, so keyboard and assistive-technology users are not taken to the visible row-local error. The current mobile test checks layout/action sizing only and does not exercise failure focus in a real browser viewport.

**Fix:** Keep a ref to the active responsive error (or render one shared row error instead of two mounted duplicates) and focus only an element whose layout is visible. Add a mobile-viewport browser regression that rejects the mutation and verifies `document.activeElement` is the visible mobile alert.

## Post-remediation disposition for WR-11 through WR-14

### WR-11 [RESOLVED on `0227a4fb`]: The canonical browser layer omitted the mobile focus regression

**Classification:** WARNING — resolved
**File:** `tools/phase3_gauntlet.sh:404-429`
**Supporting paths:** `backend/tests/architecture/test_phase3_gauntlet.py:49-101`, `frontend/e2e/admin-configuration.spec.ts:1823-1859`

**Resolution evidence:** The browser regression has the stable browser-only ID `PW3-C27`; the canonical selector is exactly `UI3-C23|UI3-C26|PW3-C27`; and the architecture contract requires that exact ordered set and a matching test title for every ID. Independent discovery listed exactly those three tests, and independent isolated Vite execution passed 3/3.

**Historical issue:** On digest `2b1b2259`, the test had no stable owned ID and the canonical grep selected only UI3-C23/UI3-C26, so the 14-layer gate could pass while the mobile-focus regression was omitted.

**Outcome:** Resolved without expanding the locked UI3 consideration namespace or weakening the focus assertion.

### WR-12 [RESOLVED on `0227a4fb`, retained on `64bdc9a3`]: Canonical mutation ownership omitted the authority and committed-state fix sites

**Classification:** WARNING — resolved
**File:** `tools/phase3_gauntlet.sh:311-397`
**Supporting paths:** `backend/tests/architecture/test_phase3_gauntlet.py:51-122`, `frontend/src/features/admin/imports/mutationAuthority.ts:1-44`, `frontend/src/features/admin/imports/mutationAuthority.test.ts:11-142`

**Resolution evidence:** The current gauntlet owns exactly five semantic marker pairs, including the shared exact live-controller predicate, resolves each marker to its adjacent predicate statement, merges those locations with the legacy targets, and rejects extra or missing mutated locations. The helper tests cover live/mismatched identity, owned/obsolete/undefined token, exact/mismatched/null/aborted controller, and committed/uncommitted finalization neighbors. A fresh independent Stryker run instrumented exactly 52 mutants at only Published lines 82-86/531, Rewritten line 439, polling lines 34/35/37/38, and marker lines 7/15/23/33/43; it killed 52/52 with zero survivors, timeouts, no-coverage mutants, or errors. The architecture contract independently passed 7/7.

**Historical issue:** On digest `2b1b2259`, the canonical 25-mutant selector retained only polling, action-label, cursor, and missing-data locations; live-authority, request-token, and committed-state predicates were protected only by a one-off mutation run.

**Outcome:** Resolved and retained. The lifecycle predicate added for WR-13/WR-14 is marker-owned rather than coupled to an absolute line; no mutation-test assertion was weakened.

### WR-13 [RESOLVED on `64bdc9a3`]: Rewrite confirmation finalized state after unmount

**Classification:** WARNING — resolved
**File:** `frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx:410-420`
**Supporting paths:** `frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx:280-286`, `frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx:469-487`, `frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx:315-349`, `frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx:618-664`

**Resolution evidence:** `isCurrentRequest()` now requires the exact current controller with a non-aborted signal before checking live identity and exact request token. The `finally` evaluates that ownership at line 470 before conditionally clearing its exact token/controller at lines 471-477, then supplies the captured decision to `shouldClearUncommittedConfirmation()` at lines 478-486. Cleanup aborts and nulls both authorities at lines 280-286, so the deferred unmount completion cannot reach the setter. The unmount component test directly observes the finalization predicate as `false` after the signal is aborted and retains every callback, close, toast, and focus assertion. The live uncommitted 409 test observes `true`, proving failure recovery still clears progress. The helper truth table covers live/uncommitted, committed, changed-identity, and revoked-ownership neighbors.

**Historical issue:** On digest `0227a4fb`, cleanup revoked the token/controller but the `finally` predicate considered only unchanged identity and uncommitted state. React could ignore the resulting post-unmount setter, and the component test did not observe that decision.

**Outcome:** Resolved. Exact live controller/token/identity authority gates the setter, live failure recovery remains intact, and direct component plus marker-owned mutation oracles protect the boundary.

### WR-14 [RESOLVED on `64bdc9a3`]: Start-import finalized pending state after unmount

**Classification:** WARNING — resolved
**File:** `frontend/src/features/admin/imports/PublishedMappingImports.tsx:719-731`
**Supporting paths:** `frontend/src/features/admin/imports/PublishedMappingImports.tsx:455-480`, `frontend/src/features/admin/imports/PublishedMappingImports.tsx:750-784`, `frontend/src/features/admin/imports/PublishedMappingImports.test.tsx:592-636`, `frontend/src/features/admin/imports/PublishedMappingImports.test.tsx:708-757`

**Resolution evidence:** `isCurrentRequest()` now passes `hasLivePublishedAuthority()` the conjunction of exact request-token ownership and exact live non-aborted controller ownership at lines 719-731. The `finally` captures that decision before removing only its exact owned token and invokes `setPendingMappings()` only when the decision is true at lines 763-784. Unmount cleanup aborts every controller and clears the map at lines 455-480; therefore either revoked token ownership or the aborted/missing controller makes finalization false. The deferred-unmount component test directly observes `false` while retaining abort, toast, refresh, and focus assertions. The live component path observes `true`, deletes the owned pending entry, and synchronizes pending state; the shared helper tests independently exercise exact, mismatched, null, and aborted controller boundaries.

**Historical issue:** On digest `0227a4fb`, start-import response handling used token/controller authority, but the `finally` state synchronization checked only unchanged authority identity. Cleanup left that identity unchanged, permitting a post-unmount setter call.

**Outcome:** Resolved. Cleanup revokes the same exact token/controller authority required by the final state transition, and unique request symbols prevent an obsolete completion from deleting or finalizing a replacement request for the same mapping.

---

_Reviewed: 2026-09-04T10:44:54Z_
_Reviewer: independent typed agent (gsd-code-reviewer)_
_Depth: standard final lifecycle-remediation review_
_ASVS: OWASP ASVS 5.0 Level 1_
_Historical deep review: 2026-09-03T17:25:05Z over 352 paths; historical final pass: 2026-09-03T18:10:41Z over 65 workflow-supplied files; historical Nyquist-delta review: 2026-09-03T21:04:31Z over 10 files; historical post-remediation review: 2026-09-04T07:57:33Z over 10 files_
