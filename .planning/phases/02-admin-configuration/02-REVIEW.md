---
phase: 02-admin-configuration
reviewed: 2026-09-01T09:26:59Z
review_date: 2026-09-01
depth: deep
asvs_level: OWASP ASVS 5.0 Level 1
scope: complete Phase 2 implementation diff and resolved review-mode manifest through Plan 02-43
diff_base: ce9fbeef86b00f594d1d06e15d3083d623c54095
reviewed_head: 99d2d0af5dfb27cc3ef47590f480ae7a33cf4d94
reviewed_source_digest: ede23c16f49301366ec9e30edc885e52c726b5d57a7bc3a796be6e9f30979d90
final_manifest_digest: 3d07af5efc811a412f85419dd6db10cf6c5804101ff545ae60669795dd020c30
files_reviewed: 287
files_reviewed_list:
  - .env.example
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
  - backend/src/verboflex/schemas/previews.py
  - backend/src/verboflex/schemas/system.py
  - backend/src/verboflex/schemas/users.py
  - backend/src/verboflex/scripts/__init__.py
  - backend/src/verboflex/scripts/export_openapi.py
  - backend/src/verboflex/security/__init__.py
  - backend/src/verboflex/security/secret_box.py
  - backend/src/verboflex/services/admin_users.py
  - backend/src/verboflex/services/bitbucket_oauth.py
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
  - backend/tests/integration/test_bitbucket_discovery.py
  - backend/tests/integration/test_bitbucket_http_adapter.py
  - backend/tests/integration/test_bitbucket_oauth.py
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
  - tools/verify_ios_preview_mutants.py
  - tools/verify_mapping_api_mutants.py
  - tools/verify_preview_job_mutants.py
  - tools/verify_product_api_mutants.py
  - tools/verify_product_publication_mutants.py
  - tools/verify_rate_limit_boundary_mutant.py
  - tools/verify_repository_api_mutants.py
findings:
  critical: 2
  warning: 6
  info: 0
  total: 8
status: issues_found
---

# Phase 2: Code and Security Review

**Reviewed:** 2026-09-01T09:26:59Z
**Depth:** deep
**ASVS target:** OWASP ASVS 5.0 Level 1
**Status:** ISSUES FOUND — CR-14, CR-15, and WR-03..WR-08 remain open

## Narrative Findings (AI reviewer)

### Summary

The complete implementation range `ce9fbeef86b00f594d1d06e15d3083d623c54095..99d2d0af5dfb27cc3ef47590f480ae7a33cf4d94` and all 287 unique paths resolved by the current review-mode manifest were freshly reviewed from source, symbols, call chains, migrations, deployment definitions, executable tests, and negative probes. Historical reviews, summaries, plans, and prior PASS claims were treated only as an inventory and were not accepted as closure evidence.

The current review-mode digest is `ede23c16f49301366ec9e30edc885e52c726b5d57a7bc3a796be6e9f30979d90`; the final manifest digest is `3d07af5efc811a412f85419dd6db10cf6c5804101ff545ae60669795dd020c30`. The executor's unchanged-source `bash tools/phase2_gauntlet.sh --gap-closure` result is PASS 18/18. Independent focused execution added 20 backend node passes, 101 frontend test passes, static/type gates, dependency audits, manifest comparison, and the malformed-expiry reproduction.

The execute:post review then read all 171 unique paths in `/tmp/verboflex_phase2_review_files.txt` at standard depth, without accepting the prior PASS as evidence. It confirmed the five existing open warnings and found two new Critical correctness/data-loss defects plus one new Warning in an executable smoke path. CR-11, CR-12, and CR-13 remain closed by their existing evidence; CR-14, CR-15, and WR-08 are additive findings and do not rewrite any earlier row or the frozen legacy inventory.

### Critical Issues

#### CR-14: Preview commit resolution truncates valid configured branches after the first 100

**Classification:** BLOCKER
**Files:** `frontend/src/features/admin/previews/ProductPreviewPage.tsx:193-241`, `frontend/src/features/admin/mappings/ProductMappingsPage.tsx:218-270`, `frontend/src/api/client/sdk.gen.ts:345-362`
**Symbol:** `resolveCommits`

**Issue:** Preview creation resolves each configured source branch by requesting only the first branch page with `cursor: null, limit: 100`, then searching that page locally. Branch names are opaque and the mapping workflow deliberately supports a configured branch beyond the first 100 by calling the exact `getAdminRepositoryBranch` endpoint. A valid saved mapping whose source branch is on page 101 or later therefore always throws before candidate validation or active-revision revalidation can start. This blocks preview confirmation, publication, and reactivation for a configuration the same UI and API accept.

**Executable evidence:** The existing 100/101 Playwright boundary proves the mapping workflow restores the 101st configured branch through the exact detail endpoint, while `ProductPreviewPage.test.tsx:723-739` asserts only the truncated first-page request. The generated client exposes `getAdminRepositoryBranch`, but `resolveCommits` does not use it. **Current result: OPEN — BLOCKER.**

**Fix:** Resolve every configured source branch through `getAdminRepositoryBranch` (and require the returned exact name), for direct, separate, and active-revalidation flows. Add a preview regression where the configured branch is absent from page one but the exact detail read returns branch 101 and its commit.

#### CR-15: Dirty forms lose data on ordinary SPA navigation

**Classification:** BLOCKER
**Files:** `frontend/src/features/admin/products/ProductWizardPage.tsx:347-370`, `frontend/src/components/layout/AppShell.tsx:88-102`, `frontend/src/features/admin/mappings/ProductMappingsPage.tsx:305-332`, `frontend/src/features/admin/mappings/ProductMappingsPage.tsx:849-909`
**Symbols:** `ProductWizardPage`, `RoutedDestination`, `ProductMappingsPage`

**Issue:** The product wizard guards only `beforeunload` and `popstate`. React Router `<Link>` navigation uses same-document history navigation and does not fire either event before unmounting the route, so clicking Workspace, Products, Users, or Bitbucket silently discards dirty product details. The mapping form maintains unsaved repository/branch/target state but installs no route or unload guard at all. The current `popstate` handler also runs after the history position has changed and attempts recovery with `history.forward()`, rather than blocking the transition before data is lost.

**Executable evidence:** The current browser E2E covers page reload only (`beforeunload`), and the unit test manually dispatches `popstate`; neither clicks a real routed shell link. Source tracing from `RoutedDestination` to `ProductWizardPage` shows no React Router blocker between the `<Link>` and route unmount. **Current result: OPEN — BLOCKER.**

**Fix:** Derive dirty state for both product and mapping forms and register a React Router navigation blocker that opens the existing named Alert Dialog before any SPA transition, retaining values and focus on `Keep editing` and proceeding only on `Discard changes`. Keep `beforeunload` for document exits. Add real-router tests that click shell/product links from each dirty form and exercise both choices.

### Warnings

#### WR-03: Provider `expires_in` is not upper-bounded

**Classification:** WARNING
**File:** `backend/src/verboflex/services/bitbucket_oauth.py:516-533`, `backend/src/verboflex/services/bitbucket_oauth.py:345-363`
**Symbols:** `_require_client_credentials_response`, `_persist_access_only`

**Issue:** Any positive Python integer is accepted for `expires_in`. A malformed large provider value passes validation and then raises `OverflowError` in `timedelta(seconds=expires_in)`, escaping the bounded OAuth error surface as an HTTP 500. The same path affects initial connect and automatic renewal.

**Executable evidence:** The focused review probe passed `10**100` through `_require_client_credentials_response` (`validator_accepted_unbounded_positive True`) and the exact persistence arithmetic raised `OverflowError`. **Current result: OPEN — WARNING.**

**Fix:** Define an explicit maximum provider lifetime, reject booleans and values outside `1..MAX_TOKEN_LIFETIME_SECONDS` as `OAuthConnectionUnavailable`, and add boundary/overflow API tests.

#### WR-04: The locked developer dependency graph contains a known moderate advisory

**Classification:** WARNING
**Files:** `frontend/package.json:35-40`, `frontend/package-lock.json:13008-13009`
**Symbol:** `@stryker-mutator/core -> typed-rest-client -> qs`

**Issue:** `npm audit --json` reports two moderate vulnerability records on the same development-only chain: `@stryker-mutator/core@10.0.0 -> typed-rest-client@2.3.1 -> qs@6.15.1` (GHSA-q8mj-m7cp-5q26). The production-only audit is clean, so this is not a deployed runtime vulnerability, but the repository's full dependency inventory is not advisory-free.

**Executable evidence:** `npm audit --json` exited 1 with `moderate: 2`; `npm audit --omit=dev --json` exited 0 with zero vulnerabilities; `npm ls qs typed-rest-client --all` resolved the affected chain. **Current result: OPEN — WARNING.**

**Fix:** Update the owning toolchain or add a compatible audited override, regenerate the lockfile, and make the full-graph audit policy explicit rather than allowing moderate advisories silently.

#### WR-05: Container provenance is mutable despite locked language dependencies

**Classification:** WARNING
**Files:** `docker/backend.Dockerfile:3-5`, `docker/backend.Dockerfile:22`, `docker/frontend.Dockerfile:3`, `docker/frontend.Dockerfile:17`, `docker-compose.yml:36`, `docker-compose.yml:51`
**Issue:** Python, Node, Nginx, PostgreSQL, Redis, and uv images are selected only by mutable tags. Rebuilding the reviewed source digest can therefore consume different container bytes without any repository change.

**Executable evidence:** The provenance inventory `rg -n '^(FROM|\s*image:)' docker/*.Dockerfile docker-compose*.yml` found tags without `@sha256:` for all base/service images. **Current result: OPEN — WARNING.**

**Fix:** Pin every build and runtime image to an approved immutable digest, retain readable version tags beside the digest, and automate reviewed digest updates.

#### WR-06: The canonical environment example cannot configure the Phase 2 runtime

**Classification:** WARNING
**Files:** `.env.example:1-13`, `docker-compose.yml:21-27`
**Issue:** The example omits all three required Bitbucket client-credentials/encryption settings and all preview execution/watchdog bounds. Copying the canonical example makes Compose fail immediately without explaining the keyring format or the new controls.

**Executable evidence:** `rg -n '^VERBOFLEX_(BITBUCKET|PREVIEW)' .env.example` returned no configured variables while `docker-compose.yml:21-27` requires/seeds those seven settings. **Current result: OPEN — WARNING.**

**Fix:** Add secret-safe placeholders and format guidance for the required OAuth/keyring variables and document every preview limit with its validated bounds. Keep real values out of the repository.

#### WR-07: The source manifest omits an executable Phase 2 test contract

**Classification:** WARNING
**Files:** `tools/phase2_source_manifest.txt:1-36`, `backend/tests/architecture/phase2_spec_edge_matrix.json:1`
**Issue:** `phase2_spec_edge_matrix.json` changed in the reviewed implementation range and is executable input to `test_phase2_spec_edge_traceability.py`, but the manifest includes backend tests only through `backend/tests/**/*.py`. A change to the matrix does not change either the review digest or final manifest digest, weakening source-to-evidence binding.

**Executable evidence:** Resolving `tools/phase2_source_manifest.txt` produced 287 unique paths and omitted the JSON, while `backend/tests/architecture/test_phase2_spec_edge_traceability.py:21` loads it as `MATRIX_PATH`. **Current result: OPEN — WARNING.**

**Fix:** Include the exact JSON contract (or all deliberate backend test data) in the manifest, add a self-test that compares changed executable test inputs with resolved manifest membership, then rerun review and the official gauntlet on the new digest.

#### WR-08: The advertised default Compose flow calls removed OAuth endpoints

**Classification:** WARNING
**File:** `tools/phase2_compose_flow.py:478-482`, `tools/phase2_compose_flow.py:530-546`
**Symbol:** `main`

**Issue:** The no-flag mode still advertises `phase2_compose_flow.py BACKEND_URL EMAIL TEMP_PASSWORD`, then calls `/api/v1/admin/bitbucket/oauth/start` and `/api/v1/admin/bitbucket/oauth/callback`. Those authorization-code endpoints were removed when Phase 2 adopted client credentials; the current OpenAPI exposes only connect, reconnect, status, and revoke. The documented default verifier therefore deterministically receives 404 before reaching repository, mapping, preview, or publication assertions.

**Executable evidence:** Comparing the two literal paths with `frontend/openapi.json` found neither route. The maintained worker-loss and gap-boundary modes already use `POST /api/v1/admin/bitbucket/connect`, but the default path is not invoked by the current gauntlet, so its breakage is masked. **Current result: OPEN — WARNING.**

**Fix:** Replace the authorization-code sequence with the current client-credentials connect contract and update its assertions, or remove the dead default mode and usage text. Add the retained mode as an explicit gauntlet node so API drift fails the executable evidence layer.

### Current CR/WR Inventory Re-audit

Every historical row was resolved against current production symbols and executable current tests. “PASS” below records tests actually run in this review unless explicitly identified as part of the upstream official 18/18 result.

| Row | Current disposition | Final production file and symbol | Executable current evidence | Current result |
|---|---|---|---|---|
| CR-01 | CLOSED | `docker-compose.yml` — `x-backend-common.environment` shared by backend/worker/scheduler | `test_base_compose_inherits_exact_provider_settings_without_secret_output` | PASS in focused backend 17-node run; rendered values stayed out of diagnostics |
| CR-02 | CLOSED | `BitbucketOAuthTokenExchange.exchange_client_credentials`; `BitbucketOAuthService._require_client_credentials_response` | `test_client_credentials_provider_exchange_is_exact_and_bounded` | PASS focused; exact HTTPS token URL, Basic client authentication, `grant_type=client_credentials`, no redirects, response cap, Bearer and exact `repository` scope |
| CR-03 | CLOSED; callback/authorization-code/refresh authority absent | `BitbucketOAuthService`; admin Bitbucket connect/reconnect/status/revoke routes | `test_client_credentials_service_has_no_callback_or_refresh_authority` | PASS focused; no callback, redirect, authorization-code, browser-token, or refresh-token route/service surface |
| CR-04 | CLOSED for normal scope/status/expiry/generation authority; WR-03 remains | `public_status`, `acquire_repository_read_lease`, `_renew_access_token_if_needed`, `_persist_access_only` | `test_client_credentials_persists_access_only_encrypted_generation`; `test_client_credentials_expiry_renews_once_for_concurrent_leases` | 2/2 PASS focused; access-only encrypted state, exact scope, expiry and one serialized renewal are authoritative |
| CR-05 | CLOSED | `products.save_product_candidate`, `_clone_active_revision_graph`; `publication._promote_candidate_identity` | `test_existing_product_edit_clones_complete_graph_once_and_isolates_candidate_identity` | PASS focused; stable product UUID, complete fresh-ID candidate graph, active bytes unchanged, identity promoted only at publication |
| CR-06 | CLOSED | `publication.reactivate_product`; `preview_jobs.active_revision_revalidation_is_current`; `ProductPreviewPage`/`PublishedMappingRecovery` | `test_inactive_active_revision_can_revalidate_confirm_and_reactivate_without_graph_mutation`; Playwright “unchanged active revision reactivation…” | Backend node PASS focused; full real-backend recovery E2E PASS in 18/18 gauntlet with no candidate/provider-write shortcut |
| CR-07 | CLOSED | `ProductWizardPage` persistent previous/next/step controls | `ProductConfiguration.test.tsx` — “keeps all five wizard steps reachable through persistent 320px keyboard and pointer controls” | PASS within focused 4-file/92-test frontend run |
| CR-08 | CLOSED | `useCursorCollection`; `ProductPreviewPage` terminal-cursor collection and partial-state gating | `useCursorCollection.test.ts`; `ProductPreviewPage.test.tsx` — “waits for mapping 51…” | PASS within focused frontend run; append/dedup/supersession and 51st-row lifecycle gating execute |
| CR-09 | CLOSED | `reconcile_stale_preview_jobs`; `_claim_current_running_attempt`; Celery `preview-stale-job-watchdog` | `test_retry_after_watchdog_timeout_isolated_from_old_worker_completion`; `test_worker_loss_smoke_proves_bounded_terminalization_and_retry` | 2/2 PASS focused; actual worker-kill terminalization/retry PASS in staging and production during the 18/18 gauntlet |
| CR-10 | CLOSED across HTTP, CLI, and bootstrap-era entry paths | `ADMIN_AUTHORITY_LOCK_KEY`, `_lock_admin_authority`, `_require_admin_survivor`, `_deactivate_user_under_admin_authority_lock`, `deactivate_user_by_email`; HTTP create/update/deactivate/reactivate services | `test_cross_entry_cli_and_http_deactivation_preserve_one_active_admin_and_both_uuids`; `test_cli_sole_admin_deactivation_fails_without_changing_authority` | 2/2 PASS focused; all authority-reducing paths share one advisory lock and survivor predicate |
| CR-11 | CLOSED | base/staging/production `services.scheduler`; `create_celery_app.beat_schedule`; `reconcile_stale_preview_jobs`; dual-overlay `run_worker_loss_dual_overlay` | `test_deployment_overlays_give_scheduler_exact_worker_authority`; `test_compose_runs_preview_scheduler_as_a_separate_shared_service`; `test_worker_loss_smoke_exercises_staging_and_production_overlays` | 3/3 PASS focused; executor's dual-overlay KILL→`timed_out/time_limit_exceeded`→replacement success smoke PASS |
| CR-12 | CLOSED | `create_or_reuse_active_revision_revalidation_job`, `confirm_active_revision_revalidation`, `active_revision_revalidation_is_current`, `get_active_revision_revalidation_eligibility`; immutable sidecar model/migration; `PublishedMappingRecovery` | `test_active_revision_revalidation_never_mutates_published_graph`; `test_active_revision_revalidation_api_is_admin_only_exact_and_read_only`; active-revalidation frontend tests and real-backend Playwright recovery | Backend nodes PASS focused; frontend 92 tests PASS; gauntlet E2E confirms generation drift recovery, exact server eligibility, sidecar evidence, byte-identical published graph, and no provider writes |
| CR-13 | CLOSED | `docker/frontend.nginx.conf` `server` block — complete CSP with `frame-ancestors 'none'`, `X-Frame-Options: DENY`, nosniff/referrer/permissions headers with `always` | `test_frontend_built_image_smoke_enforces_anti_framing_headers`; runtime root and SPA-fallback header probe in `phase2_smoke.sh` | Focused contract PASS; built-image runtime header smoke PASS in the 18/18 gauntlet |
| WR-01 | CLOSED | `WorkspaceOverviewPage`; `AppShell` React Router location-authoritative links | `WorkspaceOverviewPage.test.tsx` | 1 file / 9 tests PASS focused; admin summary/actions remain role-projected and bounded |
| WR-02 | CLOSED | migration `0009_product_graph_integrity` composite ownership FKs plus `verboflex_guard_active_revision_child`; migration `0011` immutable revalidation sidecar | `test_published_graph_is_immutable_but_candidate_graph_remains_editable`; `test_active_revision_revalidation_never_mutates_published_graph` | 2/2 PASS across focused runs; database rejects cross-product ownership and every published graph child mutation |
| WR-03 | **OPEN — WARNING** | `_require_client_credentials_response`; `_persist_access_only` | focused malformed `expires_in=10**100` probe | Validator accepted the value; persistence raised `OverflowError`; bounded upper limit is still absent |
| WR-04 | **OPEN — WARNING** | locked frontend dev dependency chain `@stryker-mutator/core -> typed-rest-client -> qs` | `npm audit --json`; `npm audit --omit=dev --json`; `npm ls ...` | Full graph: 2 moderate records; production graph: 0; current severity Warning |
| WR-05 | **OPEN — WARNING** | Dockerfile `FROM` and Compose `image` selectors | immutable-image inventory command | Python/uv/Node/Nginx/PostgreSQL/Redis selectors still lack `@sha256:` pins; current severity Warning |
| WR-06 | **OPEN — WARNING** | `.env.example`; `docker-compose.yml` required OAuth/keyring and preview settings | environment-key comparison probe | Example still has 0/7 Phase 2 provider/watchdog keys; current severity Warning |
| WR-07 | **OPEN — WARNING** | `tools/phase2_source_manifest.txt`; executable `phase2_spec_edge_matrix.json` loaded by `test_phase2_spec_edge_traceability.py` | resolved-manifest membership comparison | JSON contract remains outside both review and final digest inputs; current severity Warning |
| CR-14 | **OPEN — BLOCKER** | `ProductPreviewPage.resolveCommits`; exact repository-branch generated client | 100/101 mapping E2E plus preview first-page request trace | Valid configured branches beyond the first 100 cannot start candidate or active-revision preview validation |
| CR-15 | **OPEN — BLOCKER** | `ProductWizardPage` dirty listeners; `AppShell.RoutedDestination`; `ProductMappingsPage` form state | real-router call-chain trace plus existing reload-only/manual-event tests | Router Link navigation can unmount dirty forms without the required discard confirmation |
| WR-08 | **OPEN — WARNING** | `phase2_compose_flow.main` default no-flag mode | literal route comparison against current OpenAPI | Advertised default smoke calls removed OAuth start/callback routes and deterministically stops at 404 |

### Original CR/WR Inventory Re-audit

This table is the frozen legacy semantic baseline consumed by `test_phase2_gap_closure.py`; it is retained byte-for-byte for regression compatibility and is **not** the current review disposition. The authoritative fresh 20-row assessment is the immediately preceding Current CR/WR Inventory Re-audit table and the frontmatter findings count. In particular, its historical CR-06 and CR-09 partial/blocking wording has been superseded by current CR-11/CR-12 closure evidence.

| Row | Current disposition | Final production file and symbol | Executable current evidence | Current result |
|---|---|---|---|---|
| CR-01 | CLOSED for the original base-Compose omission | `docker-compose.yml` — `x-backend-common.environment` | `backend/tests/architecture/test_phase2_live_provider_smoke.py::test_base_compose_inherits_exact_provider_settings_without_secret_output` | PASS in official 18/18; rendered config independently confirmed credentials on backend/worker/scheduler |
| CR-02 | CLOSED | `backend/src/verboflex/services/bitbucket_oauth.py` — `BitbucketOAuthTokenExchange.exchange_client_credentials`, `_require_client_credentials_response` | `backend/tests/integration/test_bitbucket_oauth.py::test_client_credentials_provider_exchange_is_exact_and_bounded` | PASS in focused 12-test run |
| CR-03 | CLOSED; callback/redirect authority removed | `backend/src/verboflex/services/bitbucket_oauth.py` — `BitbucketOAuthService`; `backend/src/verboflex/api/v1/routes/admin_bitbucket.py` — connect/reconnect/status/revoke routes | `backend/tests/integration/test_bitbucket_oauth.py::test_client_credentials_service_has_no_callback_or_refresh_authority` | PASS in focused 12-test run |
| CR-04 | CLOSED for normal expiry/renewal/status; WR-03 remains for malformed upper bound | `backend/src/verboflex/services/bitbucket_oauth.py` — `acquire_repository_read_lease`, `_renew_access_token_if_needed`, `public_status` | `backend/tests/integration/test_bitbucket_oauth.py::test_client_credentials_expiry_renews_once_for_concurrent_leases` | PASS in focused 12-test run |
| CR-05 | CLOSED | `backend/src/verboflex/services/products.py` — `save_product_candidate`, `_clone_active_revision_graph`; `backend/src/verboflex/services/publication.py` — `_promote_candidate_identity` | `backend/tests/api/test_admin_products.py::test_existing_product_edit_clones_complete_graph_once_and_isolates_candidate_identity` | PASS in focused 12-test run |
| CR-06 | PARTIAL / BLOCKING via CR-12 | `backend/src/verboflex/services/publication.py` — `reactivate_product`; `frontend/src/features/admin/previews/ProductPreviewPage.tsx` — `ProductPreviewPage`, `PublishedMappingConfirmation` | `backend/tests/integration/test_product_publication.py::test_current_confirmations_are_the_atomic_publication_and_reactivation_bridge`; `frontend/e2e/admin-configuration.spec.ts` — “unchanged active revision reactivation uses real backend state and blocks stale confirmation” | Current-confirmation path PASS; stale-generation recovery absent |
| CR-07 | CLOSED | `frontend/src/features/admin/products/ProductWizardPage.tsx` — `ProductWizardPage` persistent mobile controls | `frontend/src/features/admin/products/ProductConfiguration.test.tsx` — “keeps all five wizard steps reachable through persistent 320px keyboard and pointer controls” | PASS within focused 78-test Vitest run |
| CR-08 | CLOSED | `frontend/src/features/admin/useCursorCollection.ts` — `useCursorCollection`; `frontend/src/features/admin/previews/ProductPreviewPage.tsx` — automatic terminal-cursor collection | `frontend/src/features/admin/useCursorCollection.test.ts` — cursor append/supersession tests; `frontend/src/features/admin/previews/ProductPreviewPage.test.tsx` — “waits for mapping 51...” | PASS within focused 78-test Vitest run |
| CR-09 | PARTIAL / BLOCKING via CR-11 | `backend/src/verboflex/services/preview_jobs.py` — `reconcile_stale_preview_jobs`; `backend/src/verboflex/worker/celery_app.py` — `preview-stale-job-watchdog` | `backend/tests/integration/test_preview_jobs.py::test_watchdog_watchdog_and_late_success_race_has_one_legal_terminal_winner`, `::test_retry_after_watchdog_timeout_isolated_from_old_worker_completion`; rendered staging/prod Compose probe | Service tests PASS; deployment probe FAILS scheduler authority |
| CR-10 | CLOSED | `backend/src/verboflex/services/admin_users.py` — `ADMIN_AUTHORITY_LOCK_KEY`, `_deactivate_user_under_admin_authority_lock`, `_require_admin_survivor`; CLI `deactivate_user_by_email` | `backend/tests/integration/test_admin_user_concurrency.py::test_cross_entry_cli_and_http_deactivation_preserve_one_active_admin_and_both_uuids`; `backend/tests/test_cli.py::test_cli_sole_admin_deactivation_fails_without_changing_authority` | PASS in focused 12-test run |
| WR-01 | CLOSED | `frontend/src/features/workspace/WorkspaceOverviewPage.tsx` — `WorkspaceOverviewPage`; `frontend/src/components/layout/AppShell.tsx` — location-authoritative navigation | `frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx` — bounded summary/recovery suite | PASS within focused 78-test Vitest run |
| WR-02 | CLOSED | `backend/alembic/versions/0009_product_graph_integrity.py` — `fk_products_*_owned_revision`, `fk_preview_jobs_owned_*`, `verboflex_guard_active_revision_child` | `backend/tests/integration/test_product_graph_integrity.py::test_published_graph_is_immutable_but_candidate_graph_remains_editable` | PASS in focused 12-test run |

### ASVS 5.0 Level 1 Coverage and Authorities

The primary review authority is OWASP ASVS 5.0.0 Level 1. The Phase 2 research's named supporting authorities were also checked at their implemented seams: OAuth client credentials and security guidance (RFC 6749/RFC 9700 where applicable), official Atlassian Bitbucket Cloud OAuth/scope/REST contracts, `cryptography` MultiFernet authenticated encryption, Celery task/time-limit delivery semantics, SQLAlchemy/PostgreSQL transaction and constraint authority, and the format authorities cited for RFC 8259 JSON, Android XML, Qt TS, and Apple `.strings`. The client-credentials replacement means there is intentionally no browser authorization-code callback/state authority in the final product.

| Named ASVS 5 domain | Current-code coverage | Verdict |
|---|---|---|
| V2 Validation and Business Logic | Pydantic closed schemas; exact cursor/path/scope/status validation; transactional admin/product/publication invariants; fail-closed revalidation eligibility | PASS, with WR-03 malformed-expiry upper-bound warning |
| V5 File Handling | GET-only commit-bound source reads; exact provider host/path families; no redirects; strict path traversal rejection; byte/page/file/depth/count ceilings; defused XML and strict decoders | PASS |
| V6 Authentication | Signed purpose-bound internal bearer tokens, Argon2 passwords, one-time generated credentials, current user/session/token-version loading, deployed signing-secret validation | PASS |
| V7 Session Management | Refresh rotation/revocation, token-version advance, authority transaction session revocation, memory-only frontend bearer and Secure/HttpOnly refresh cookie | PASS |
| V8 Authorization | All 34 admin handlers consume `AdminPrincipal`; database-loaded current roles are authoritative; last-admin lock/survivor predicate spans HTTP and CLI; revalidation routes are admin-only | PASS |
| V10 OAuth | Backend-only exact client-credentials exchange, exact `repository` effective scope, access-only encrypted generations, expiry/status/reconnect/local-revoke semantics, post-provider generation recheck | PASS, with WR-03 warning |
| V11 Cryptography | Pydantic `SecretStr`, MultiFernet authenticated encryption/key rotation, encrypted provider token at rest, no custom cipher, redacted repr and no-store public projections | PASS |
| V16 Logging and Error Handling | Bounded public error enums/messages, provider body/token exclusion, secret-free diagnostics/audit probes, no callback/query credentials, captured-log negative tests | PASS |
| Cross-domain product graph authority | Composite ownership FKs, published and active-child triggers, deep candidate clone, immutable sidecar recovery, atomic publication/reactivation | PASS |
| Cross-domain pagination completeness | Mapping/list collection is complete, but preview commit resolution truncates provider branches to the first 100 | FAIL — CR-14 |
| Cross-domain worker-loss recovery | Durable CAS terminalization, separate Beat scheduler with deployment parity, dual-overlay real process-kill/retry isolation | PASS |
| Cross-domain browser response hardening | Runtime complete CSP, `frame-ancestors 'none'`, XFO DENY, nosniff, referrer and permissions headers on root/fallback | PASS |
| Provider-write and canonical-write exclusion | Provider adapter publicly exposes only bounded GET operations; URL allowlist excludes write endpoints; OpenAPI and mock/live audit expose zero provider/canonical write authority | PASS |
| Dependency provenance and evidence binding | Python and production npm audits clean; dev advisory, mutable image provenance, incomplete environment example, and JSON manifest omission remain | WARNING — WR-04..WR-07 |

### Verification Performed

- Upstream official command: `bash tools/phase2_gauntlet.sh --gap-closure` — PASS 18/18 on final manifest digest `3d07af5efc811a412f85419dd6db10cf6c5804101ff545ae60669795dd020c30`; used as full-suite/deployment corroboration, never as a substitute for source inspection.
- Fresh digest commands: review mode returned `ede23c16f49301366ec9e30edc885e52c726b5d57a7bc3a796be6e9f30979d90`; final mode returned `3d07af5efc811a412f85419dd6db10cf6c5804101ff545ae60669795dd020c30`; HEAD remained `99d2d0af5dfb27cc3ef47590f480ae7a33cf4d94`.
- Focused backend execution: 17 selected OAuth, graph, active-revalidation, watchdog, admin-concurrency, CLI, scheduler/overlay, worker-loss-contract, and anti-framing nodes — 17 passed; 3 supplemental graph/provider-write nodes — 3 passed. Total: **20 passed**.
- Focused frontend execution: product configuration, preview/reactivation, cursor collection, and Bitbucket connection — 4 files / 92 tests passed; workspace overview — 1 file / 9 tests passed. Total: **5 files / 101 tests passed**.
- Static gates: Ruff passed; `mypy src` passed across 81 source files; TypeScript typecheck and frontend ESLint passed.
- Dependency checks: `uv lock --check` passed; `pip-audit` found no known third-party Python vulnerabilities; production npm audit found 0; full npm graph reported 2 moderate records on the single WR-04 development dependency chain.
- Deployment evidence: focused rendered-Compose tests prove backend/worker/scheduler authority equality without secret diagnostics; the current official smoke killed the worker only after durable `running`, observed scheduler-owned bounded terminalization, restarted the worker, and proved a new successful attempt plus immutable original row in both staging and production overlays.
- Runtime header evidence: focused architecture contract passed; the official built-Nginx probe confirmed the exact CSP and defensive headers on both `/` and SPA fallback responses.
- Focused malformed-expiry probe: current validator accepted an unbounded positive `expires_in`, and datetime persistence overflowed; this is the WR-03 reproduction.
- Manifest comparison: the current resolved manifest contains 287 unique paths but excludes the executable `phase2_spec_edge_matrix.json` input; this is WR-07.
- Execute:post standard review: all 171 manifest paths were read and checked; focused Vitest execution passed 3 files / 84 tests, TypeScript typecheck and ESLint passed, backend Ruff passed, and mypy passed across 81 source files. The passing suites do not cover the CR-14 branch-101 preview path or the CR-15 real Router Link transition.
- API drift probe: the default `phase2_compose_flow.py` OAuth start/callback literals are absent from the current OpenAPI; this is WR-08.

### Closure Decision

**Critical gate: FAIL.** CR-01..CR-13 retain their prior closed dispositions, but CR-14 and CR-15 are open on current production symbols; `findings.critical: 2`. WR-03..WR-08 remain explicitly **OPEN — WARNING**. No source, canonical review/evidence, or verifier artifact was changed by this review.

---

_Reviewed: 2026-09-01T09:26:59Z_
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: deep_
