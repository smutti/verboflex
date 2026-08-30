---
phase: 02-admin-configuration
reviewed: 2026-08-30T00:38:16Z
depth: deep
asvs_level: OWASP ASVS 5.0 Level 1
diff_base: ce9fbeef86b00f594d1d06e15d3083d623c54095
reviewed_head: 25ad3e21a064b845ba3b49b46909e994f754cf9e
reviewed_source_digest: f9accb511f5c7af60620cf5d209ac8b7d42b78d2b8e155fb81317855e69b0861
final_manifest_digest: 9d706927ce28271b9dfbff7d0695b9a4268cc4b4a9e75c068e6465f6774650f7
files_reviewed: 286
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
  - backend/tests/architecture/phase2_spec_edge_matrix.json
  - backend/tests/architecture/test_background_boundaries.py
  - backend/tests/architecture/test_phase2_gap_closure.py
  - backend/tests/architecture/test_phase2_live_provider_smoke.py
  - backend/tests/architecture/test_phase2_scope.py
  - backend/tests/architecture/test_phase2_spec_edge_traceability.py
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
  critical: 3
  warning: 5
  info: 0
  total: 8
status: issues_found
---

# Phase 2: Code and Security Review

**Reviewed:** 2026-08-30T00:38:16Z
**Depth:** deep
**ASVS target:** OWASP ASVS 5.0 Level 1
**Status:** issues_found — Phase 2 closure must stop

## Narrative Findings (AI reviewer)

### Summary

The complete Phase 2 implementation range `ce9fbeef86b00f594d1d06e15d3083d623c54095..25ad3e21a064b845ba3b49b46909e994f754cf9e` and the current Phase 2 manifest were reviewed from current code, not from historical PASS artifacts. The reported review digest is the review-mode digest, which excludes the canonical historical review: `f9accb511f5c7af60620cf5d209ac8b7d42b78d2b8e155fb81317855e69b0861`. The final manifest/report digest remains `9d706927ce28271b9dfbff7d0695b9a4268cc4b4a9e75c068e6465f6774650f7`.

The official gap-closure gauntlet was independently reported green at 18/18 layers on the final digest. Direct review nevertheless found three blocking defects and five warnings. Green tests do not override these current-code failures.

### Critical Issues

#### CR-11: Deployed scheduler cannot reach PostgreSQL, so lost preview jobs remain running

**Classification:** BLOCKER / Critical
**Files:** `docker-compose.staging.yml:14-32`, `docker-compose.prod.yml:14-32`, `docker-compose.yml:96-107`
**Symbols:** `services.scheduler`, `x-deployment-environment`

**Issue:** The base file adds the Celery beat scheduler, but neither deployment overlay overrides it. Rendered staging and production configurations therefore leave `scheduler` with `VERBOFLEX_APP_ENV=local` and the base passwordless database URL, while the same overlays configure PostgreSQL for SCRAM and give only `backend` and `worker` the password-bearing deployment URL. The scheduler cannot execute `reconcile_stale_preview_jobs`; a worker-killed `running` job can remain non-terminal indefinitely in staging/production. The current worker-loss smoke uses `prepare_base_stack`, so its green result does not exercise either deployment overlay.

**Fix:** Add `scheduler` to both overlays with `environment: *deployment-environment`, the deployed image tag, and `restart: unless-stopped`. Add rendered-config assertions for all three backend processes and run the worker-loss smoke through both overlays.

#### CR-12: Routine OAuth generation changes can permanently block product reactivation

**Classification:** BLOCKER / Critical
**Files:** `backend/src/verboflex/services/preview_jobs.py:391-421`, `backend/src/verboflex/services/preview_jobs.py:667-685`, `frontend/src/features/admin/previews/ProductPreviewPage.tsx:673-707`, `frontend/src/features/admin/previews/ProductPreviewPage.tsx:927-938`, `frontend/src/features/admin/previews/ProductPreviewPage.tsx:1060-1078`
**Symbols:** `_locked_mapping`, `is_current_preview_confirmation`, `PublishedMappingConfirmation`, `ProductPreviewPage`

**Issue:** Reactivation correctly requires a confirmation bound to the current Bitbucket connection generation. Reconnect and automatic client-credentials renewal increment that generation. Once an inactive product's published confirmation becomes stale, the backend rejects reactivation, but preview creation accepts only `product.candidate_revision_id` and rejects a published active revision. The reactivation UI renders read-only badges instead of `MappingPreview`, so it exposes no validation action. The product is left inactive with no supported way to create a current confirmation for the exact active revision. The real E2E test explicitly proves the stale state is blocked, but stops without proving a recovery path.

**Fix:** Add a dedicated read-only active-revision revalidation authority for inactive products (with the same exact revision/version/mapping/commit/generation binding), expose it in the reactivation UI, and add a real reconnect-or-renewal → revalidate → confirm → reactivate E2E test. Do not mutate or clone the published graph to obtain this recovery path.

#### CR-13: The shipped administrator SPA is frameable

**Classification:** BLOCKER / Critical
**Files:** `docker/frontend.nginx.conf:1-12`, `frontend/index.html:1-12`
**Symbol:** Nginx `server` block

**Issue:** The runtime Nginx configuration sends neither CSP `frame-ancestors` nor `X-Frame-Options`, and the document supplies no equivalent policy. An attacker can frame the authenticated administrator interface and mount clickjacking interactions against destructive admin actions. This violates the ASVS Level 1 web-frontend anti-framing boundary.

**Fix:** Send `Content-Security-Policy` with at least `frame-ancestors 'none'` (and a complete application CSP) on every SPA response; add `X-Frame-Options: DENY` as legacy defense. Add a runtime header smoke against the built Nginx image.

### Warnings

#### WR-03: Provider `expires_in` is not upper-bounded

**Classification:** WARNING
**File:** `backend/src/verboflex/services/bitbucket_oauth.py:516-533`, `backend/src/verboflex/services/bitbucket_oauth.py:345-363`
**Symbols:** `_require_client_credentials_response`, `_persist_access_only`

**Issue:** Any positive Python integer is accepted for `expires_in`. A malformed large provider value passes validation and then raises `OverflowError` in `timedelta(seconds=expires_in)`, escaping the bounded OAuth error surface as an HTTP 500. The same path affects initial connect and automatic renewal.

**Fix:** Define an explicit maximum provider lifetime, reject booleans and values outside `1..MAX_TOKEN_LIFETIME_SECONDS` as `OAuthConnectionUnavailable`, and add boundary/overflow API tests.

#### WR-04: The locked developer dependency graph contains a known moderate advisory

**Classification:** WARNING
**Files:** `frontend/package.json:35-40`, `frontend/package-lock.json:13008-13009`
**Symbol:** `@stryker-mutator/core -> typed-rest-client -> qs`

**Issue:** `npm audit --audit-level=high` reports two moderate findings for the locked development graph; the affected `qs` 6.15.1 instance is introduced by the mutation-test toolchain. The production-only audit is clean, so this is not a deployed runtime vulnerability, but the repository's full dependency inventory is not advisory-free.

**Fix:** Update the owning toolchain or add a compatible audited override, regenerate the lockfile, and make the full-graph audit policy explicit rather than allowing moderate advisories silently.

#### WR-05: Container provenance is mutable despite locked language dependencies

**Classification:** WARNING
**Files:** `docker/backend.Dockerfile:3-5`, `docker/backend.Dockerfile:22`, `docker/frontend.Dockerfile:3`, `docker/frontend.Dockerfile:17`, `docker-compose.yml:36`, `docker-compose.yml:51`
**Issue:** Python, Node, Nginx, PostgreSQL, Redis, and uv images are selected only by mutable tags. Rebuilding the reviewed source digest can therefore consume different container bytes without any repository change.

**Fix:** Pin every build and runtime image to an approved immutable digest, retain readable version tags beside the digest, and automate reviewed digest updates.

#### WR-06: The canonical environment example cannot configure the Phase 2 runtime

**Classification:** WARNING
**Files:** `.env.example:1-13`, `docker-compose.yml:21-27`
**Issue:** The example omits all three required Bitbucket client-credentials/encryption settings and all preview execution/watchdog bounds. Copying the canonical example makes Compose fail immediately without explaining the keyring format or the new controls.

**Fix:** Add secret-safe placeholders and format guidance for the required OAuth/keyring variables and document every preview limit with its validated bounds. Keep real values out of the repository.

#### WR-07: The source manifest omits an executable Phase 2 test contract

**Classification:** WARNING
**Files:** `tools/phase2_source_manifest.txt:1-36`, `backend/tests/architecture/phase2_spec_edge_matrix.json:1`
**Issue:** `phase2_spec_edge_matrix.json` changed in the reviewed implementation range and is executable input to `test_phase2_spec_edge_traceability.py`, but the manifest includes backend tests only through `backend/tests/**/*.py`. A change to the matrix does not change either the review digest or final manifest digest, weakening source-to-evidence binding.

**Fix:** Include the exact JSON contract (or all deliberate backend test data) in the manifest, add a self-test that compares changed executable test inputs with resolved manifest membership, then rerun review and the official gauntlet on the new digest.

### Original CR/WR Inventory Re-audit

Every historical row was resolved against current production symbols and executable current tests. “PASS” below records tests actually run in this review unless explicitly identified as part of the upstream official 18/18 result.

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

### ASVS 5.0 Level 1 Coverage

| Security domain | Current-code coverage | Verdict |
|---|---|---|
| Authentication and session authority | Signed purpose-bound JWTs, current DB user/session/token-version checks, restricted password-change authority, Argon2 passwords, refresh rotation/revocation, Redis rate limits | PASS |
| Authorization and last-active-admin safety | Every admin route depends on DB-loaded `admin`; HTTP and CLI authority-reducing mutations share one transaction advisory lock and survivor predicate | PASS |
| OAuth client credentials | Exact client-credentials grant, exact `repository` scope, access-only durable state, expiry/generation validation, reconnect/revoke, no callback/browser token surface | WARNING — WR-03 |
| Credential secrecy and cryptography | Backend-only settings, MultiFernet encryption at rest, repr-hidden transient leases, no-store credential responses, secret-free audit/error projections | PASS |
| Provider URL, redirect, continuation, path, and budget bounds | HTTPS exact host and endpoint families, redirects disabled, source continuation path equality, traversal rejection, bounded pages/entries/depth/files/bytes, post-read lease recheck | PASS |
| Product ownership, immutability, and publication | Composite ownership FKs, published/active child triggers, deep candidate clone, current exact confirmation predicate, atomic promotion and stable UUID | PASS |
| Pagination completeness | Opaque server cursors plus frontend all-page collection before lifecycle authority; failure keeps actions disabled | PASS |
| Preview stale/worker-loss recovery | CAS terminalization and retry isolation are implemented, but the deployed scheduler cannot access the database | FAIL — CR-11 |
| Inactive product recovery | Current active confirmations can reactivate, but generation-stale active revisions cannot be revalidated | FAIL — CR-12 |
| Provider-write and canonical-write exclusion | Provider adapter exposes GET only; URL allowlist excludes write endpoints; Phase 2 stores only preview/configuration authority and no canonical translations | PASS |
| Logs, errors, and secrets | Bounded public provider errors, no provider body/token projection, no browser credential storage, generated passwords no-store and one-view | PASS |
| Browser response hardening | Runtime Nginx lacks anti-framing policy | FAIL — CR-13 |
| Dependency provenance and deployment | Python/production npm audits are clean, but dev advisory, mutable image tags, incomplete env example, and manifest omission remain | WARNING — WR-04 through WR-07 |

### Verification Performed

- Upstream official command: `bash tools/phase2_gauntlet.sh --gap-closure` — reported PASS, 18/18 layers, on final digest `9d706927ce28271b9dfbff7d0695b9a4268cc4b4a9e75c068e6465f6774650f7`; not rerun as a substitute for inspection.
- Digest commands: review mode returned `f9accb511f5c7af60620cf5d209ac8b7d42b78d2b8e155fb81317855e69b0861`; final mode returned `9d706927ce28271b9dfbff7d0695b9a4268cc4b4a9e75c068e6465f6774650f7`.
- Focused backend tests: 12 selected OAuth, graph, publication, watchdog, admin-concurrency, CLI, and Compose-contract nodes — 12 passed; 2 additional preview/product lifecycle nodes — 2 passed.
- Focused frontend tests: product configuration, preview/reactivation, cursor collection, and workspace overview — 4 files, 78 tests passed.
- Static gates: Ruff passed; `mypy src` passed across 81 source files; TypeScript typecheck and frontend ESLint passed.
- Dependency checks: `uv lock --check` passed; `pip-audit` found no known third-party Python vulnerabilities; production npm audit found 0; full npm graph reported the WR-04 moderate advisory.
- Deployment probes: rendered staging and production Compose configurations without printing secret values. Both showed deployed backend/worker authority but a local, passwordless scheduler; this is the CR-11 reproduction.
- Focused malformed-expiry probe: current validator accepted an unbounded positive `expires_in`, and datetime persistence overflowed; this is the WR-03 reproduction.
- Manifest comparison: one changed executable test input was absent from the resolved review manifest; this is WR-07.

### Closure Decision

**STOP. Phase 2 must not close while CR-11, CR-12, or CR-13 remains unresolved.** The current status is `issues_found`; no historical PASS claim or green gauntlet result downgrades a demonstrated Critical defect.

---

_Reviewed: 2026-08-30T00:38:16Z_
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: deep_
