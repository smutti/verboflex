---
phase: 02-admin-configuration
reviewed: 2026-08-29T10:13:31Z
depth: standard
files_reviewed: 148
files_reviewed_list:
  - backend/alembic/versions/0002_product_revisions.py
  - backend/alembic/versions/0003_repositories.py
  - backend/alembic/versions/0004_bitbucket_connection.py
  - backend/alembic/versions/0005_product_mappings.py
  - backend/alembic/versions/0006_preview_jobs.py
  - backend/alembic/versions/0007_preview_confirmations.py
  - backend/pyproject.toml
  - backend/src/verboflex/api/v1/router.py
  - backend/src/verboflex/api/v1/routes/admin_bitbucket.py
  - backend/src/verboflex/api/v1/routes/admin_discovery.py
  - backend/src/verboflex/api/v1/routes/admin_mappings.py
  - backend/src/verboflex/api/v1/routes/admin_previews.py
  - backend/src/verboflex/api/v1/routes/admin_products.py
  - backend/src/verboflex/api/v1/routes/admin_repositories.py
  - backend/src/verboflex/api/v1/routes/admin_users.py
  - backend/src/verboflex/audit/__init__.py
  - backend/src/verboflex/audit/events.py
  - backend/src/verboflex/auth/principal.py
  - backend/src/verboflex/cli.py
  - backend/src/verboflex/core/config.py
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
  - backend/src/verboflex/models/bitbucket_connection.py
  - backend/src/verboflex/models/preview_job.py
  - backend/src/verboflex/models/product.py
  - backend/src/verboflex/models/product_mapping.py
  - backend/src/verboflex/models/repository.py
  - backend/src/verboflex/models/user.py
  - backend/src/verboflex/schemas/admin_bitbucket.py
  - backend/src/verboflex/schemas/admin_discovery.py
  - backend/src/verboflex/schemas/admin_mappings.py
  - backend/src/verboflex/schemas/admin_products.py
  - backend/src/verboflex/schemas/admin_repositories.py
  - backend/src/verboflex/schemas/admin_users.py
  - backend/src/verboflex/schemas/previews.py
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
  - backend/src/verboflex/worker/celery_app.py
  - backend/src/verboflex/worker/preview_tasks.py
  - backend/tests/api/test_admin_bitbucket.py
  - backend/tests/api/test_admin_discovery.py
  - backend/tests/api/test_admin_mappings.py
  - backend/tests/api/test_admin_products.py
  - backend/tests/api/test_admin_repositories.py
  - backend/tests/api/test_admin_users.py
  - backend/tests/api/test_openapi_contract.py
  - backend/tests/architecture/test_phase2_live_provider_smoke.py
  - backend/tests/architecture/test_phase2_scope.py
  - backend/tests/architecture/test_provider_boundaries.py
  - backend/tests/integration/test_admin_user_concurrency.py
  - backend/tests/integration/test_bitbucket_discovery.py
  - backend/tests/integration/test_bitbucket_http_adapter.py
  - backend/tests/integration/test_bitbucket_oauth.py
  - backend/tests/integration/test_migrations.py
  - backend/tests/integration/test_preview_jobs.py
  - backend/tests/integration/test_product_publication.py
  - backend/tests/integration/test_repository_registry.py
  - backend/tests/unit/localization/preview/test_android_xml.py
  - backend/tests/unit/localization/preview/test_ios_strings.py
  - backend/tests/unit/localization/preview/test_json.py
  - backend/tests/unit/localization/preview/test_qt_ts.py
  - backend/tests/unit/services/__init__.py
  - backend/tests/unit/services/test_admin_users.py
  - backend/tests/unit/services/test_mappings.py
  - backend/tests/unit/services/test_pr_grouping.py
  - backend/tests/unit/test_product_names.py
  - backend/uv.lock
  - docker-compose.yml
  - docker/frontend.Dockerfile
  - docs/evidence/phase-02.md
  - docs/reviews/phase-02-code-security.md
  - frontend/e2e/admin-configuration.spec.ts
  - frontend/e2e/auth-shell.spec.ts
  - frontend/openapi.json
  - frontend/src/api/admin-client-contract.test.ts
  - frontend/src/api/client/index.ts
  - frontend/src/api/client/sdk.gen.ts
  - frontend/src/api/client/types.gen.ts
  - frontend/src/components/layout/AppShell.test.tsx
  - frontend/src/components/layout/AppShell.tsx
  - frontend/src/components/ui/alert-dialog.tsx
  - frontend/src/components/ui/checkbox.tsx
  - frontend/src/components/ui/dialog.tsx
  - frontend/src/components/ui/radio-group.tsx
  - frontend/src/components/ui/select.tsx
  - frontend/src/components/ui/table.tsx
  - frontend/src/components/ui/tabs.tsx
  - frontend/src/components/ui/textarea.tsx
  - frontend/src/features/admin/AdminAccessDenied.tsx
  - frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx
  - frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx
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
  - frontend/src/features/admin/repositories/ProductRepositoriesPage.tsx
  - frontend/src/features/admin/users/TemporaryPasswordDialog.tsx
  - frontend/src/features/admin/users/UserDialog.tsx
  - frontend/src/features/admin/users/UsersPage.test.tsx
  - frontend/src/features/admin/users/UsersPage.tsx
  - frontend/src/features/admin/users/userRoles.ts
  - frontend/src/router.test.tsx
  - frontend/src/router.tsx
  - tools/gauntlet.sh
  - tools/phase2_compose_flow.py
  - tools/phase2_gauntlet.sh
  - tools/phase2_live_provider.py
  - tools/phase2_mock_provider.py
  - tools/phase2_smoke.sh
  - tools/phase2_source_manifest.txt
  - tools/source_state.sh
  - tools/verify_android_preview_mutants.py
  - tools/verify_bitbucket_discovery_mutants.py
  - tools/verify_bitbucket_http_adapter_mutants.py
  - tools/verify_bitbucket_oauth_mutants.py
  - tools/verify_ios_preview_mutants.py
  - tools/verify_mapping_api_mutants.py
  - tools/verify_preview_job_mutants.py
  - tools/verify_product_api_mutants.py
  - tools/verify_product_publication_mutants.py
  - tools/verify_repository_api_mutants.py
findings:
  critical: 10
  warning: 2
  info: 0
  total: 12
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-08-29T10:13:31Z
**Depth:** standard
**Files Reviewed:** 148
**Status:** issues_found

## Narrative Findings (AI reviewer)

### Summary

The complete canonical Phase 2 scope was reviewed, including migrations, backend services and routes, provider/OAuth boundaries, worker execution, generated API contracts, React administration flows, Docker configuration, tests, gauntlets, and signed evidence. The implementation has strong local validation and stale-authority controls, but ten release-blocking functional or security defects remain. Most importantly, the shipped local stack cannot receive the Bitbucket configuration, the approved client-credentials grant is not the grant implemented by production, the OAuth callback returns to the wrong origin, published-product editing and reactivation are unreachable, and durable preview jobs can remain permanently running after a worker loss.

The existing green tests do not disprove these findings: the Compose OAuth flow asserts a relative `Location` without following it, the live-provider proof substitutes a different grant and credential authority, and the reactivation/browser fixtures return a candidate mapping page in a backend state where the real candidate endpoint rejects.

## Critical Issues

### CR-01: The shipped Compose stack cannot receive any Bitbucket configuration

**File:** `docker-compose.yml:9-20`  
**Related:** `backend/src/verboflex/core/config.py:36-40`, `backend/src/verboflex/api/v1/routes/admin_bitbucket.py:67-79`

**Issue:** Both API and worker inherit the fixed `x-backend-common.environment` map, but that map contains none of `VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID`, `VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET`, `VERBOFLEX_BITBUCKET_OAUTH_CALLBACK_URI`, or `VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING`. Compose does not implicitly pass arbitrary host variables into a service. The OAuth service therefore fails construction and the normal local application always projects Bitbucket as `Unavailable`. The smoke passes only because `tools/phase2_smoke.sh` generates a private override that injects the missing variables; users starting the documented base stack do not get that override.

**Fix:** Add an explicit, secret-safe configuration contract for both `backend` and `worker` (prefer Docker secrets or an owner-only env file), validate all four values during startup, and add a base-Compose smoke that starts with a disposable configuration without the test-only override.

### CR-02: The approved client-credentials grant is not implemented by production

**File:** `backend/src/verboflex/services/bitbucket_oauth.py:122-151`  
**Related:** `backend/src/verboflex/services/bitbucket_oauth.py:742-760`, `tools/phase2_live_provider.py:279-324`, `docs/evidence/phase-02.md:129-146`

**Issue:** Production only exchanges `authorization_code` and `refresh_token` grants and rejects a token response without a refresh token. The live provider checkpoint that was approved and signed instead obtains `grant_type=client_credentials`, accepts only an access token, and replaces the production credential service with an in-memory authority. Consequently the exact credential mode verified against Bitbucket is absent from the application, while the production authorization-code/refresh path has never been exercised against the live provider. The signed live PASS therefore cannot establish that the global Bitbucket connection works with the credentials the user configured.

**Fix:** Choose one grant as the production contract. For the approved global server-to-server client-credentials model, implement acquisition/expiry renewal in the backend and remove the browser authorization-code callback. If authorization code is retained, require a compatible client configuration and run the real start → provider authorization → callback → encrypted persistence → repository-read journey before closing the phase.

### CR-03: OAuth completion redirects to the API origin instead of the frontend

**File:** `backend/src/verboflex/api/v1/routes/admin_bitbucket.py:227-230`  
**Related:** `backend/src/verboflex/core/config.py:39`, `backend/src/verboflex/services/bitbucket_oauth.py:496-499`, `docker-compose.yml:58-60`, `docker-compose.yml:95-101`

**Issue:** The callback responds with the relative path `/admin/bitbucket`. In the shipped topology the callback is served by `localhost:8000` and the SPA by `localhost:8080`, so the browser resolves the redirect to `http://localhost:8000/admin/bitbucket`, where no FastAPI route exists. The Compose proof at `tools/phase2_compose_flow.py:188-194` only compares the header and never follows the redirect, masking the broken journey.

**Fix:** Configure and allowlist an absolute frontend return URL (for example `http://localhost:8080/admin/bitbucket` locally and HTTPS in deployed environments), or place API and SPA behind one reverse-proxy origin. Extend the browser smoke to follow the actual provider callback and assert the rendered Bitbucket page.

### CR-04: Access-token expiry permanently breaks reads while the UI still reports Connected

**File:** `backend/src/verboflex/services/bitbucket_oauth.py:348-417`  
**Related:** `backend/src/verboflex/services/bitbucket_oauth.py:501-560`, `frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx:259-344`

**Issue:** `public_status` and `_require_readable_connection` never compare `provider_expires_at` with the current time. The service has refresh logic, but no route, task, lease path, or caller invokes it. After the access token expires, repository reads return a provider reauthorization error, while the Bitbucket page continues to show `Connected` and does not render `Reconnect Bitbucket`. The stored refresh token is therefore unusable and normal recovery requires the misleading revoke-then-connect sequence.

**Fix:** Refresh before lease acquisition under generation authority, or mark the connection `reauthorization_required` when expired and expose a bounded recovery action. Persist provider 401/invalid-grant transitions so status and available UI actions reflect durable reality. Add exact-expiry and concurrent-refresh integration tests.

### CR-05: Published-product editing is unreachable and candidate creation does not copy the active graph

**File:** `frontend/src/router.tsx:163-189`  
**Related:** `frontend/src/features/admin/products/ProductWizardPage.tsx:105-119`, `frontend/src/features/admin/products/ProductOverviewPage.tsx:220-276`, `backend/src/verboflex/services/products.py:195-219`

**Issue:** The wizard contains an update path only when `initialProduct` is supplied, but production routing mounts it only at `products/new` and never supplies that prop. Existing-product routes expose Overview, Repositories, Mappings, and Preview, with no edit/start-draft action. At the API level, PATCHing a published product creates only a bare `ProductRevision`; it does not copy active mappings, sides, or target configuration, even though the locked Phase 2 contract requires candidate creation to copy the active graph. It also updates the global product name immediately, before publication. An administrator therefore cannot start a mapping-only draft through the UI, and a details edit through the API produces a blank configuration instead of an editable copy.

**Fix:** Add an explicit, routed “start/edit draft” workflow. Transactionally clone revision-owned mapping structure from the active revision while invalidating preview confirmation authority that is revision-bound. Store candidate-visible name/description in the candidate revision (or otherwise defer externally visible rename) and publish them atomically with the graph. Test an existing published product from UI through one mapping change and publication.

### CR-06: Product reactivation is unreachable against the real backend contract

**File:** `frontend/src/features/admin/previews/ProductPreviewPage.tsx:687-714`  
**Related:** `frontend/src/features/admin/previews/ProductPreviewPage.tsx:780-795`, `backend/src/verboflex/services/mappings.py:433-462`

**Issue:** The preview page always requests `listAdminCandidateMappings` before it can detect reactivation. Reactivation is defined by `candidate_revision === null` and an existing active revision, but the backend candidate-list service rejects exactly that state with “candidate unavailable.” The page enters its generic error state before `isReactivation` can become true, so the Reactivate button can never render against the real API. Browser tests hide this by mocking a successful candidate mapping response while returning `candidate_revision: null`.

**Fix:** Expose a read-only active-revision mapping/preview projection for reactivation, or make the preview endpoint explicitly revision-scoped. Select the appropriate revision endpoint after loading the product, and replace the impossible mock with a contract test against the real backend.

### CR-07: The five-step wizard has no navigation beyond step 2 on mobile

**File:** `frontend/src/features/admin/products/ProductWizardPage.tsx:252-282`  
**Related:** `frontend/src/features/admin/products/ProductWizardPage.tsx:343-357`, `frontend/e2e/admin-configuration.spec.ts:669-730`

**Issue:** All step buttons are hidden below the `md` breakpoint and the mobile replacement is display-only progress text. After “Save and continue” moves the user to Repositories, the embedded repository page has no Next/Back controls, leaving steps 3–5 unreachable at 320px. The E2E “five-step” journey is run only at 1024px; the separate viewport loop checks the product list, not the wizard.

**Fix:** Add persistent mobile Previous/Next controls (with dirty-state handling and disabled rules) or an accessible mobile step selector. Run the complete five-step journey at 320px and assert that every step is reachable by keyboard and touch.

### CR-08: Repository, mapping, and branch pagination is silently discarded by the admin UI

**File:** `frontend/src/features/admin/repositories/ProductRepositoriesPage.tsx:85-106`  
**Related:** `frontend/src/features/admin/mappings/ProductMappingsPage.tsx:219-258`, `frontend/src/features/admin/mappings/ProductMappingsPage.tsx:281-302`, `frontend/src/features/admin/previews/ProductPreviewPage.tsx:137-186`, `frontend/src/features/admin/previews/ProductPreviewPage.tsx:687-714`

**Issue:** These flows always request only the first page (50 repositories/mappings and 100 branches) and ignore `next_cursor`. Items after those boundaries cannot be selected, edited, previewed, or re-used. Worse, preview commit resolution searches only the first 100 branches; a configured branch beyond that page is reported as missing even though the backend has an exact branch-resolution capability. Preview publication readiness is also calculated over only the first 50 mappings, so the UI can claim its loaded subset is complete while the backend evaluates the full revision.

**Fix:** Implement cursor accumulation or explicit Load More controls for every collection. For an already configured source branch, add/use an exact branch-detail API rather than scanning a page. Derive publication eligibility and mapping counts from a server-owned full-revision summary. Add fixtures at 51 mappings/repositories and 101 branches.

### CR-09: Worker loss or hard timeout leaves durable preview jobs permanently running

**File:** `backend/src/verboflex/services/preview_jobs.py:818-917`  
**Related:** `backend/src/verboflex/worker/preview_tasks.py:127-150`, `backend/src/verboflex/worker/celery_app.py:19-36`

**Issue:** A job is committed as `running` before provider processing begins. Only a returned result, a caught exception, or the soft-time-limit conversion writes a terminal state. Celery’s hard limit kills the child process and a worker crash can occur after the running commit; neither path executes `_finish_preview_job`. There is no stale-running reconciler, and tasks are not configured for late acknowledgement/recovery. Retrying the UUID also does nothing because `_start_preview_job` accepts only `queued`. The API will therefore poll a durable `running` row forever.

**Fix:** Add a durable watchdog/reconciler that atomically marks attempts older than the hard deadline `timed_out` and permits a new attempt. Configure appropriate acknowledgement/worker-lost behavior, but do not rely on Celery callbacks alone for recovery. Test by terminating the worker process after the running transition and verifying a terminal state plus retry.

### CR-10: The privileged CLI can deactivate the last active administrator

**File:** `backend/src/verboflex/services/admin_users.py:413-431`  
**Related:** `backend/src/verboflex/cli.py:99-106`, `backend/src/verboflex/cli.py:153-170`

**Issue:** HTTP lifecycle operations serialize on `ADMIN_AUTHORITY_LOCK_KEY` and enforce `_require_admin_survivor`, but `deactivate_user_by_email` bypasses both protections. The CLI exposes that function directly, so it can deactivate the only active administrator. Bootstrap then refuses because users still exist, reset-password does not reactivate the account, and there is no CLI reactivation command. A single supported command can therefore lock every administrator out with no supported recovery path.

**Fix:** Apply the same advisory lock and last-active-admin invariant to CLI deactivation. If break-glass recovery is required, add a narrowly scoped, audited reactivation command that issues fresh password authority; cover CLI/API cross-concurrency and last-admin recovery tests.

## Warnings

### WR-01: Workspace overview is an inert button and is always marked current

**File:** `frontend/src/components/layout/AppShell.tsx:139-159`

**Issue:** “Workspace overview” is rendered as a plain button with no link or click handler and unconditional `aria-current="page"`. From any admin route it cannot navigate home, and assistive technology may see both the workspace button and an admin destination as current.

**Fix:** Render it through the same routed destination abstraction as other navigation items, link to `/`, compute `aria-current` from `useLocation`, and close the mobile sheet on navigation.

### WR-02: Database constraints do not enforce revision ownership across the product graph

**File:** `backend/alembic/versions/0002_product_revisions.py:108-123`  
**Related:** `backend/alembic/versions/0002_product_revisions.py:124-149`, `backend/alembic/versions/0005_product_mappings.py:64-75`, `backend/alembic/versions/0006_preview_jobs.py:94-110`

**Issue:** Product revision pointers reference only `product_revisions.id`, so the database can point a product at another product’s revision. Preview jobs independently reference product, revision, and mapping without enforcing that they form one graph. The “published revision immutable” trigger protects only the revision row; mappings, sides, targets, layout selection, and confirmation rows attached to a published revision remain database-mutable. Current services usually enforce ownership, but maintenance scripts, future services, or a defect can persist a graph that the database accepts and the API later treats as authoritative.

**Fix:** Add composite ownership keys/foreign keys where practical (`product_id, revision_id` and `revision_id, mapping_id`), and enforce published-graph immutability for revision-owned child tables with database constraints/triggers. Add negative migration tests that attempt cross-product pointers, mismatched preview identities, and child mutation under a published revision.

---

_Reviewed: 2026-08-29T10:13:31Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_

