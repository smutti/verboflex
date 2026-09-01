---
phase: 02-admin-configuration
reviewed: 2026-09-01T17:34:00Z
review_date: 2026-09-01
depth: deep
asvs_level: OWASP ASVS 5.0 Level 1
scope: complete Phase 2 implementation diff and resolved review-mode manifest through Plan 02-46
diff_base: ce9fbeef86b00f594d1d06e15d3083d623c54095
reviewed_head: 7af1d1063ab6a795a42f0e26175fc2196ba6eda5
reviewed_source_digest: f12c23d7aa7655027b189b7793227403575e5393e92ed08ae9009db9dda1e1ca
final_manifest_digest: 522197df9eebf96ae0cff46df9bc357f74a60152efe00cac2892aec22ef47241
files_reviewed: 290
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
  - backend/tests/architecture/phase2_spec_edge_matrix.json
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
  critical: 0
  warning: 6
  info: 0
  total: 6
status: issues_found
review_inventory:
  CR-01: {disposition: closed, severity: critical}
  CR-02: {disposition: closed, severity: critical}
  CR-03: {disposition: closed, severity: critical}
  CR-04: {disposition: closed, severity: critical}
  CR-05: {disposition: closed, severity: critical}
  CR-06: {disposition: closed, severity: critical}
  CR-07: {disposition: closed, severity: critical}
  CR-08: {disposition: closed, severity: critical}
  CR-09: {disposition: closed, severity: critical}
  CR-10: {disposition: closed, severity: critical}
  CR-11: {disposition: closed, severity: critical}
  CR-12: {disposition: closed, severity: critical}
  CR-13: {disposition: closed, severity: critical}
  CR-14: {disposition: closed, severity: critical}
  CR-15: {disposition: closed, severity: critical}
  WR-01: {disposition: closed, severity: warning}
  WR-02: {disposition: closed, severity: warning}
  WR-03: {disposition: open, severity: warning}
  WR-04: {disposition: open, severity: warning}
  WR-05: {disposition: open, severity: warning}
  WR-06: {disposition: open, severity: warning}
  WR-07: {disposition: open, severity: warning}
  WR-08: {disposition: open, severity: warning}
---

# Phase 2: Code and Security Review

**Reviewed:** 2026-09-01T17:34:00Z
**Depth:** deep
**ASVS target:** OWASP ASVS 5.0 Level 1
**Status:** ISSUES FOUND — zero Critical/High-equivalent findings; WR-03..WR-08 remain open

## Narrative Findings (AI reviewer)

### Summary

This replacement review covers the 290-path union of the independently resolved review-mode source manifest and the non-artifact implementation diff `ce9fbeef86b00f594d1d06e15d3083d623c54095..7af1d1063ab6a795a42f0e26175fc2196ba6eda5`. I reviewed the current API-to-service-to-database and API-to-worker-to-provider call chains, generated OpenAPI/client seams, deployment inputs, router-native navigation state, executable test contracts, and supply-chain provenance. Prior review and verification prose was not used as closure proof.

The independently recomputed review digest is `f12c23d7aa7655027b189b7793227403575e5393e92ed08ae9009db9dda1e1ca`; the final manifest digest is `522197df9eebf96ae0cff46df9bc357f74a60152efe00cac2892aec22ef47241`. The resolved manifest itself contains 289 paths; the changed executable edge-matrix JSON supplies the 290th reviewed path through the diff union. The review-scope path-set hash is `cace5d1c0e585502520afbc04a55b1a5065191cee23892a8fc2ed7d15f5debb0`.

No Critical or project High-equivalent defect was found. In particular, CR-14 now closes on the same exact-detail authority for candidate and active-revision jobs, followed by an independent exact branch/commit comparison in the worker before parsing. CR-15 closes on one application-scoped `useBlocker` transaction owner: the transition is captured before route commit, document exit is handled separately by `useBeforeUnload`, cancellation keeps values and restores a still-connected trigger, and discard consumes only the captured transaction. Six reproducible, nonblocking defects remain open as WR-03..WR-08; therefore `issues_found` is deliberate.

### Warnings

#### WR-03: Provider `expires_in` is not upper-bounded

**Classification:** WARNING
**File:** `backend/src/verboflex/services/bitbucket_oauth.py:345-363`, `backend/src/verboflex/services/bitbucket_oauth.py:516-533`
**Symbols:** `_require_client_credentials_response`, `_persist_access_only`

**Issue:** The response validator rejects nonpositive and boolean expiry values but has no maximum. Consequently, an arbitrarily large provider integer reaches `acquired_at + timedelta(seconds=expires_in)` and can raise `OverflowError`. That exception occurs after validation, outside `_exchange_and_validate`'s provider-error conversion, so both connect and lease renewal can escape the intended bounded unavailable result.

**Evidence:** On current HEAD, `_require_client_credentials_response` accepted `expires_in=10**100`; applying the accepted value to the production `timedelta` expression raised `OverflowError: Python int too large to convert to C int`. **Disposition: OPEN — WARNING.**

**Fix:** Introduce a documented `MAX_PROVIDER_TOKEN_LIFETIME_SECONDS`, accept only non-boolean integers in `1..MAX_PROVIDER_TOKEN_LIFETIME_SECONDS`, and map date-arithmetic failures to `OAuthConnectionUnavailable`. Cover max, max+1, and enormous integers at service and route boundaries.

#### WR-04: The locked developer dependency graph contains a known moderate advisory

**Classification:** WARNING
**Files:** `frontend/package.json:35-40`, `frontend/package-lock.json:12991-13018`
**Symbol:** `@stryker-mutator/core -> typed-rest-client -> qs`

**Issue:** The mutation-testing toolchain pins `typed-rest-client@2.3.1`, which pins affected `qs@6.15.1` under GHSA-q8mj-m7cp-5q26. This chain is development-only, so it is not present in the deployed frontend bundle, but CI and contributor environments still execute a dependency graph with a known denial-of-service defect.

**Evidence:** Fresh full-graph `npm audit --json` exits 1 with two moderate records (`qs` plus its parent `typed-rest-client`); `npm audit --omit=dev --json` exits 0 with zero vulnerabilities. `npm ls` resolves `@stryker-mutator/core@10.0.0 -> typed-rest-client@2.3.1 -> qs@6.15.1`. **Disposition: OPEN — WARNING.**

**Fix:** Upgrade the Stryker/typed-rest-client chain to a release that resolves an unaffected `qs`, or add a verified compatible override; regenerate the lockfile and enforce an explicit full-graph advisory threshold in CI.

#### WR-05: Container provenance is mutable despite locked language dependencies

**Classification:** WARNING
**Files:** `docker/backend.Dockerfile:3-5`, `docker/backend.Dockerfile:22`, `docker/frontend.Dockerfile:3`, `docker/frontend.Dockerfile:17`, `docker-compose.yml:36`, `docker-compose.yml:51`, `docker-compose.staging.yml:20-32`, `docker-compose.prod.yml:20-32`
**Issue:** Every upstream build/runtime base and both data-service images are tag-only; deployment application images are tag-only as well. The reviewed source and lockfile digests therefore do not identify the container bytes that a later build or deployment will consume.

**Evidence:** The current `FROM`/Compose `image:` inventory contains uv, Python, Node, Nginx, PostgreSQL, Redis, and VerboFlex image selectors with no `@sha256:` reference. **Disposition: OPEN — WARNING.**

**Fix:** Record approved registry digests for all upstream and deployable images, use `tag@sha256:...` selectors, and update those digests through a reviewed automation path.

#### WR-06: The canonical environment example cannot configure the Phase 2 runtime

**Classification:** WARNING
**Files:** `.env.example:1-13`, `docker-compose.yml:21-27`
**Issue:** `.env.example` ends after the Phase 1 refresh-cookie setting. It does not expose the three required Bitbucket client-credential/encryption inputs or the four preview execution/watchdog controls consumed by Compose, so the documented copy-and-fill entry point cannot configure Phase 2.

**Evidence:** The example contains zero `VERBOFLEX_BITBUCKET_*` or `VERBOFLEX_PREVIEW_*` keys, whereas `docker-compose.yml:21-27` consumes seven. The first three are required substitutions. **Disposition: OPEN — WARNING.**

**Fix:** Add non-secret placeholders and generation/format comments for the client ID, client secret, and Fernet keyring; add documented defaults and validated ranges for the four preview timing settings.

#### WR-07: The source manifest omits an executable Phase 2 test contract

**Classification:** WARNING
**Files:** `tools/phase2_source_manifest.txt:1-36`, `backend/tests/architecture/phase2_spec_edge_matrix.json:1`
**Issue:** `test_phase2_spec_edge_traceability.py` reads `phase2_spec_edge_matrix.json` as executable test data, yet the manifest includes only `backend/tests/**/*.py`. The JSON is therefore outside both immutable source digests even though changing it changes semantic-gate behavior.

**Evidence:** Exact manifest resolution returns 289 paths and excludes the JSON; `MATRIX_PATH` loads it at test runtime. It is present in this 290-path review only because the diff-union rule adds it, and modifying it still leaves both reported digests unchanged. **Disposition: OPEN — WARNING.**

**Fix:** Add the JSON path (or an intentional test-data glob) to the manifest and add a manifest-coverage assertion for executable non-code fixtures. Then regenerate both digests and rerun the canonical gates.

#### WR-08: The advertised default Compose flow calls removed OAuth endpoints

**Classification:** WARNING
**File:** `tools/phase2_compose_flow.py:478-482`, `tools/phase2_compose_flow.py:530-546`
**Symbol:** `main`

**Issue:** The positional/no-flag branch still begins its provider setup with the removed authorization-code start/callback pair. Current server and generated contracts expose only status, connect, reconnect, and local revoke, so this advertised verifier path stops at a 404 before exercising its remaining lifecycle checks.

**Evidence:** Neither literal OAuth route exists in current OpenAPI. The maintained `run_gap_boundaries` and worker-loss modes use `/admin/bitbucket/connect`; the supported `tools/phase2_gauntlet.sh --gap-closure` dispatches those modes and never invokes the no-flag branch. This defect remains deferred rather than closed by the passing gauntlet. **Disposition: OPEN — WARNING.**

**Fix:** Migrate the positional flow to the current client-credentials connect/status contract or remove the obsolete branch and usage. If retained, invoke it explicitly from the gauntlet so endpoint drift becomes a failing evidence node.

### Current CR/WR Inventory Re-audit

Every authoritative row was resolved against the current production symbol and current executable evidence on the recorded digest. Closed rows are not current findings; the six open Warning rows are the complete current finding set.

| Row | Disposition | Severity | Current production symbols | Current evidence / required fix |
|---|---|---|---|---|
| CR-01 | CLOSED | CRITICAL | Compose `x-backend-common` plus overlay environment merges | Rendered base/staging/prod configurations give API, worker, and scheduler the provider and watchdog settings; fail-closed deployed configuration tests pass without echoing secret values. |
| CR-02 | CLOSED | CRITICAL | `BitbucketOAuthTokenExchange.exchange_client_credentials`; `_require_client_credentials_response` | Exact token URL, Basic client authentication, `grant_type=client_credentials`, effective `repository` scope, no redirect, and bounded response parsing are covered by provider and mutation tests. |
| CR-03 | CLOSED | CRITICAL | Admin Bitbucket status/connect/reconnect/revoke routes; `BitbucketOAuthService` | Current OpenAPI has only the four access-only lifecycle operations; browser responses never contain access/refresh tokens, and callback/refresh-token authority is absent. |
| CR-04 | CLOSED | CRITICAL | `acquire_repository_read_lease`; `_renew_access_token_if_needed`; `_persist_access_only`; `require_current_repository_read_lease` | Encrypted generation changes, serialized renewal, post-I/O generation checks, expiry, and local revoke are exercised by integration/mutation coverage. WR-03 is the separate malformed-lifetime robustness gap. |
| CR-05 | CLOSED | CRITICAL | `products._clone_active_revision_graph`; `publication._promote_candidate_identity` | Editing a published product creates a complete fresh-ID candidate graph, and publication promotes only the locked exact candidate identity; clone/isolation and mutation tests pass. |
| CR-06 | CLOSED | CRITICAL | `publication.reactivate_product`; active-revision revalidation service; `PublishedMappingRecovery` | Inactive published products revalidate through sidecar evidence without creating or changing a candidate; real-backend reactivation evidence passes with no provider write. |
| CR-07 | CLOSED | CRITICAL | `ProductWizardPage` persistent mobile Back/Next controls | The five-step wizard remains keyboard/pointer reachable from step 1 through 5 and back at 320px; current focused product tests and browser evidence pass. |
| CR-08 | CLOSED | CRITICAL | `useCursorCollection`; preview terminal-cursor readiness | Collection generations reject stale responses, append/deduplicate pages, and do not declare completeness until `next_cursor` is null; the 51st-mapping browser boundary passes. |
| CR-09 | CLOSED | CRITICAL | `reconcile_stale_preview_jobs`; `_claim_current_running_attempt`; Beat `preview-stale-job-watchdog` | The watchdog locks a bounded stale batch and CAS-terminalizes exact UUID/attempt/generation rows; staging and production worker-loss flows time out the old attempt and isolate the retry. |
| CR-10 | CLOSED | CRITICAL | `ADMIN_AUTHORITY_LOCK_KEY`; `_deactivate_user_under_admin_authority_lock`; `_require_admin_survivor` | HTTP and CLI destructive transitions share the same advisory lock and database survivor predicate; concurrent last-admin cases pass. |
| CR-11 | CLOSED | CRITICAL | `create_celery_app.beat_schedule`; base/staging/prod `scheduler` services | Celery Beat is a distinct deployed service with the same backend authority as the worker; rendered-deployment and worker-loss execution prove the scheduler-owned watchdog is live. |
| CR-12 | CLOSED | CRITICAL | active-revalidation create/confirm/currentness services; immutable confirmation migration; `PublishedMappingRecovery` | Server-owned eligibility, active-pointer/version/current-connection checks, immutable sidecar confirmation, and byte-identical published graph recovery pass integration and browser evidence. |
| CR-13 | CLOSED | CRITICAL | `docker/frontend.nginx.conf` header policy | Built root and SPA-fallback responses include complete CSP with `frame-ancestors 'none'`, DENY framing, nosniff, referrer, and permissions headers. |
| CR-14 | CLOSED | CRITICAL | `configuredPreviewSourceSides`; `resolveConfiguredBranchCommit`; generated `getAdminRepositoryBranch`; both preview create calls; worker `_process_preview` | Candidate direct/separate and active direct/separate paths resolve branch 101 through exact detail, require returned-name equality, and fail closed per side. The worker independently re-resolves each stored branch and rejects a commit mismatch before detection. Focused preview coverage passed in the fresh 115-test run; current provider evidence is five GETs and zero writes. |
| CR-15 | CLOSED | CRITICAL | `DirtyFormNavigationProvider`; `useBlocker`; `useBeforeUnload`; product/mapping `useDirtyFormNavigationGuard`; `MobileNavigationCommitObserver` | One provider captures the pre-transition router transaction; keep/reset and discard/proceed consume it once, dirty-to-clean/unmount clear it, and connected focus restoration is deferred through dialog close. Product and mapping fingerprints retain values. Fresh real-router/preview/product/mapping unit corroboration passed 4 files / 115 tests; the committed browser layer covers Link, Back, reload, and 320px Sheet focus. |
| WR-01 | CLOSED | WARNING | `WorkspaceOverviewPage`; routed `AppShell` destinations | Role-projected overview state, retry/error handling, and location-authoritative desktop/mobile navigation are covered by the current frontend suite. |
| WR-02 | CLOSED | WARNING | migrations `0009_product_graph_integrity`; `0011_active_revision_revalidations` | Composite ownership, published-child immutability, and sidecar-only recovery migration tests pass on current schema. |
| WR-03 | OPEN | WARNING | `_require_client_credentials_response`; `_persist_access_only` | The accepted `10**100` expiry reproduces `OverflowError`; enforce a maximum and bounded arithmetic as specified above. |
| WR-04 | OPEN | WARNING | Stryker -> `typed-rest-client@2.3.1` -> `qs@6.15.1` | Full audit reproduces two moderate records while production audit is clean; update or safely override the dev chain. |
| WR-05 | OPEN | WARNING | Dockerfile `FROM`; Compose `image:` selectors | No upstream or deployable selector is digest-pinned; adopt approved `tag@sha256` references. |
| WR-06 | OPEN | WARNING | `.env.example`; Compose Phase 2 environment | Zero of seven provider/watchdog settings are documented in the example; add safe placeholders, formats, and bounds. |
| WR-07 | OPEN | WARNING | source manifest; test `MATRIX_PATH` JSON | The executable JSON is absent from both source digests and appears only through this diff union; include test data in the manifest and assert coverage. |
| WR-08 | OPEN | WARNING | `phase2_compose_flow.main` positional branch | Removed OAuth start/callback paths remain. Update or delete this deferred branch; supported `--gap-closure` does not invoke it. |

### ASVS 5.0 Level 1 Coverage and Authorities

The primary authority is OWASP ASVS 5.0.0 Level 1 at the project High blocking threshold. Supporting checks covered OAuth client credentials (RFC 6749/RFC 9700 where applicable), Atlassian Bitbucket Cloud scope/REST contracts, MultiFernet authenticated encryption, Celery delivery/time-limit behavior, PostgreSQL/SQLAlchemy transaction and constraint authority, and the named localization format contracts.

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
| Cross-domain exact-detail authority | Mapping/list collection is complete; candidate and active preview commit resolution use exact branch detail, exact returned-name equality, role-bound commits, and fail-closed side completeness | PASS — CR-14 CLOSED |
| Cross-domain dirty-navigation authority | Shared data-router blocker captures Link/PUSH/POP before transition; document exit remains a separate `beforeunload` path; product/mapping values and connected trigger focus survive cancellation | PASS — CR-15 CLOSED |
| Cross-domain worker-loss recovery | Durable CAS terminalization, separate Beat scheduler with deployment parity, dual-overlay real process-kill/retry isolation | PASS |
| Cross-domain browser response hardening | Runtime complete CSP, `frame-ancestors 'none'`, XFO DENY, nosniff, referrer and permissions headers on root/fallback | PASS |
| Provider-write and canonical-write exclusion | Provider adapter publicly exposes only bounded GET operations; URL allowlist excludes write endpoints; OpenAPI and mock/live audit expose zero provider/canonical write authority | PASS |
| Dependency provenance and evidence binding | Python requirements and production npm audit are clean; dev advisory, mutable image provenance, incomplete environment example, and JSON manifest omission remain | WARNING — WR-04..WR-07 |

### Verification Performed

- Source binding was recomputed directly with `tools/source_state.sh`: review `f12c23d7aa7655027b189b7793227403575e5393e92ed08ae9009db9dda1e1ca`, final `522197df9eebf96ae0cff46df9bc357f74a60152efe00cac2892aec22ef47241`, HEAD `7af1d1063ab6a795a42f0e26175fc2196ba6eda5`.
- The exact 290-path union was independently resolved from every manifest include/exclude plus every eligible Phase 2 diff path; its sorted path-set SHA-256 is `cace5d1c0e585502520afbc04a55b1a5065191cee23892a8fc2ed7d15f5debb0`.
- Fresh focused frontend corroboration of exact-detail, shared real-router guard, product, and mapping authority: **4 files / 115 tests passed**.
- Focused semantic audit after this report replacement: `uv run pytest -q tests/architecture/test_phase2_gap_closure.py -x` — **8 passed**.
- The current committed exact-digest evidence supplied to this review reports the official gap-closure gauntlet **PASS 18/18**: semantic 34/34, backend 807/807, frontend 304/304, property 200+3, changed scope backend 641/frontend 746 at 100%, all mutation inventories, architecture/provider 57/57, browser 8/8, exactly five provider GETs/zero writes, both deployment worker-loss recoveries, cleanup, and unchanged final digest. Direct symbol tracing corroborated the boundaries for which that evidence is cited.
- Fresh dependency checks reproduced two moderate development records and zero production npm vulnerabilities. Fresh negative probes reproduced the unbounded expiry overflow, all mutable container selectors, the 0/7 environment-example gap, the executable JSON manifest omission, and the no-flag verifier's absent OpenAPI routes.

### Closure Decision

**Critical gate: PASS.** CR-01..CR-15 and WR-01..WR-02 are closed against current production authority. WR-03..WR-08 are the complete open set and remain **OPEN — WARNING**. There is no Critical/project High blocker, but the report remains `issues_found` until those six quality/robustness defects are addressed. No source, runtime, test, configuration, manifest, dependency, evidence, or canonical code-security report was changed by this review.

---

_Reviewed: 2026-09-01T17:34:00Z_
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: deep_
