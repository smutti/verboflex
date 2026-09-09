# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## real-repository-format-imports — preview discovery diverged from canonical parsers
- **Date:** 2026-09-09
- **Error patterns:** Real Android, nested JSON, Qt TS, or iOS Base layouts return `No supported layout`; repositories with more than 32 languages are rejected.
- **Root cause(s):** Preview detectors duplicated stricter grammars, Android unrelated XML invalidated the whole resource root, regional/Base locale paths were incomplete, and preview/API contracts imposed a separate 32-language cap.
- **Fix:** Reuse canonical Android/Qt parsing for preview semantics, support nested JSON and regional/Base locales, prefer an explicit base-language `.lproj` over `Base.lproj`, and remove the dedicated language cap while retaining file/byte/sample budgets.
- **Files changed:** Localization preview/import adapters, preview schema/job confirmation boundary, generated OpenAPI client artifacts, and focused regression tests.
- **Why not caught:** Earlier tests covered detection or parsing in isolation, not real repository trees and the complete preview-to-duplicate-quarantine chain.
- **Recurrence guard:** Multi-format regressions plus live public-repository probes, including 52-language Qt input and Base/en iOS peers.

---

## babel-no-supported-layout — complete duplicate groups incorrectly suppressed a valid MOKO layout
- **Date:** 2026-09-08
- **Error patterns:** Babel preview succeeds but returns zero candidates; UI says `No supported layout`; complete duplicate report exists
- **Root cause(s):** Preview cleared candidates on any duplicate group and canonical import converted the report to a blocking parser issue under a superseded contract.
- **Fix:** Quarantine every occurrence of duplicate identities, import unique values, preserve last valid values on refresh, and render duplicate diagnostics as warnings.
- **Files changed:** canonical registry/diagnostics, MOKO preview worker, import/reconciliation services, duplicate-report persistence/migration, preview and diagnostic UI.
- **Why not caught:** Earlier tests enforced whole-mapping blocking and did not cover a valid large MOKO layout containing both unique and duplicated identities.
- **Recurrence guard:** Live Babel evidence plus parser, preview-worker, activation-retention, migration, and frontend warning tests.

---

## admin-sidebar-spacing — CSS Grid stretches navigation tracks through a tall flex sidebar
- **Date:** 2026-08-28
- **Error patterns:** Desktop sidebar destinations spread vertically across the viewport; main page layout remains normal; no runtime error
- **Root cause(s):** The `lg:flex` desktop aside cross-axis stretches its grid nav to full height. With default `align-content: normal`, the nav's implicit auto rows absorb that height and the nested Administration grid stretches its four rows again.
- **Fix:** Add `content-start` to the shared `WorkspaceNavigation` nav so implicit tracks remain compact at the top.
- **Files changed:** frontend/src/components/layout/AppShell.tsx, frontend/e2e/auth-shell.spec.ts
- **Why not caught:** AppShell JSDOM tests cover semantic navigation, responsive utilities, containment, and active routes but do not execute or assert browser layout geometry.
- **Recurrence guard:** The isolated Playwright auth-shell smoke asserts a compact desktop group at 1440x900, including the Overview-to-Administration gap and heading/link heights.
---

## dockerized-frontend-login — frontend image omits canonical OpenAPI input
- **Date:** 2026-08-28
- **Error patterns:** Compose frontend image fails `tsc --noEmit`, TS2307 for `../../openapi.json`, manual Vite workaround needed for port 8080
- **Root cause(s):** `docker/frontend.Dockerfile` copied `frontend/src` but not the root-level canonical `frontend/openapi.json` imported by the generated-client contract test.
- **Fix:** Copy `frontend/openapi.json` to `/app/openapi.json` before the frontend source and build step.
- **Files changed:** docker/frontend.Dockerfile
- **Why not caught:** Local production builds could see the repository-root schema; only the isolated Docker build context exposed the missing input.
- **Recurrence guard:** `tools/real_smoke.sh --browser-only` must build the frontend image and complete the Playwright auth shell against an isolated Compose stack.
---

## web-login-rejected — Vite dev server posts auth requests to itself
- **Date:** 2026-08-28
- **Error patterns:** valid local admin password, generic login failure, no backend login request, frontend `/api/v1/auth/token` returns 404
- **Root cause(s):** Vite was launched without `VITE_API_BASE_URL`; `frontend/src/api/config.ts` fell back to `/`, while `vite.config.ts` had no API proxy, so the browser posted to port 8080 instead of the backend on port 8000.
- **Fix:** Launch local Vite with `VITE_API_BASE_URL=http://localhost:8000`; consider a durable development proxy or environment contract separately.
- **Files changed:** none; operational configuration only
- **Why not caught:** Frontend unit/build checks use generated-operation mocks or explicit build configuration and did not exercise the manually launched dev server environment.
- **Recurrence guard:** Local smoke must assert the effective browser token endpoint reaches the backend rather than returning the frontend server's 404.
---

## randomized-admin-role-order — ORM role collections sometimes reload outside the fixed domain order
- **Date:** 2026-08-27
- **Error patterns:** pytest-randomly role-order assertion failures, persisted `target.roles` differs from `FIXED_ROLE_ORDER`, passes in isolation, randomized full-suite failure
- **Root cause(s):** `User.roles` declared a many-to-many collection without SQLAlchemy `order_by`; PostgreSQL association query order was unspecified, so persisted reloads could differ from `FIXED_ROLE_ORDER` even though the service response projection was sorted.
- **Fix:** Added `order_by="Role.name"` to the `User.roles` SQLAlchemy relationship.
- **Files changed:** backend/src/verboflex/models/user.py, backend/tests/unit/services/test_admin_users.py
- **Why not caught:** No deterministic gate existed for ORM collection ordering; the behavioral combination test depended on incidental PostgreSQL ordering, while lint and type checks cannot infer the relationship's runtime order contract.
- **Recurrence guard:** Regression test `backend/tests/unit/services/test_admin_users.py::test_user_roles_relationship_declares_fixed_role_order` requires `User.roles` to declare `Role.name` ordering.
---

## phase3-nyquist-regressions — Six import-boundary regressions escaped happy-path Phase 3 gates
- **Date:** 2026-09-03
- **Error patterns:** raw OverflowError for oversized OAuth lifetime, obsolete deferred completion mutates current UI, committed baseline reported failed after refresh failure, executable JSON registry absent from source digest, mobile row error does not receive visible focus
- **Root cause(s):** `_persist_access_only` performed unchecked timedelta/datetime arithmetic outside the closed OAuth boundary; import-start and rewrite-confirmation completions trusted captured rather than live authority; confirmation state coupled a committed mutation to collection refresh; the source manifest omitted an executable JSON registry; responsive focus registered only the desktop alert and ran before conditional refs committed
- **Fix:** Compute and validate expiry before persistence; fence async completion with live identity and request ownership; represent server commit independently from refresh; include the JSON registry in the canonical manifest; register both responsive alerts and consume focus after commit; rebind the gauntlet's exact mutation targets to their relocated semantic lines
- **Files changed:** backend/src/verboflex/services/bitbucket_oauth.py, frontend/src/features/admin/imports/PublishedMappingImports.tsx, frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx, frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx, tools/phase3_source_manifest.txt, tools/phase3_gauntlet.sh
- **Why not caught:** Existing unit, type, lint, build, and closeout gates exercised normal provider values and live-request UI flows but lacked executable expiry-neighbor, authority-supersession, commit-versus-refresh, executable-registry membership, and responsive-focus tests; review warnings remained non-blocking prose.
- **Recurrence guard:** Test-first commit `7cae046` adds exact backend, manifest, async-authority, refresh-separation, and mobile-focus regressions; `tools/phase3_gauntlet.sh` binds them and exact mutation ownership into the canonical 14-layer gate, verified 14/14 with 25/25 frontend mutants killed.
---

## phase3-post-remediation-review-gaps — Canonical selectors and mutation lifecycles remained incomplete after remediation
- **Date:** 2026-09-04
- **Error patterns:** mobile focus regression omitted from canonical Playwright grep, Stryker omitted live-authority request-token committed-state predicates, access-token-only rerender retained pending confirmation, unmount allowed deferred mutation effects
- **Root cause(s):** The canonical Playwright and Stryker selectors did not own the new browser and authority predicates; rewrite confirmation identity excluded access-token authority and did not invalidate its controller/token on replacement or unmount; published import mutations lacked lifecycle-owned AbortSignals and left pending tokens authoritative after unmount.
- **Fix:** Added stable `PW3-C27` three-test browser selection; extracted marker-owned mutation authority predicates with complete truth tables; added access-token identity, dedicated AbortControllers, request-token invalidation, and no-effect deferred lifecycle tests; made the gauntlet reject exact mutation ownership drift.
- **Files changed:** backend/tests/architecture/test_phase3_gauntlet.py, frontend/e2e/admin-configuration.spec.ts, frontend/src/features/admin/imports/PublishedMappingImports.tsx, frontend/src/features/admin/imports/PublishedMappingImports.test.tsx, frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx, frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx, frontend/src/features/admin/imports/mutationAuthority.ts, frontend/src/features/admin/imports/mutationAuthority.test.ts, frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx, tools/phase3_gauntlet.sh
- **Why not caught:** The existing canonical gate ran unit, mutation, and browser checks, but its selectors omitted the mobile-focus regression and live-authority/request-token/committed-state predicates; no deferred access-token-replacement or unmount tests existed, and static checks cannot prove async lifecycle revocation.
- **Recurrence guard:** The deferred lifecycle regressions assert aborted signals and zero obsolete effects; `mutationAuthority.test.ts` covers predicate truth-table neighbors; `test_phase3_gauntlet.py` requires exact marker and browser ownership; `tools/phase3_gauntlet.sh` enforces exact 42/42 frontend mutation kills and three Playwright tests inside the 14-layer gate.
---

## phase3-lifecycle-finalization — Async import finalizers retained state authority after unmount
- **Date:** 2026-09-04
- **Error patterns:** post-unmount setConfirmationProgress, post-unmount setPendingMappings, async finally, unchanged identity after cleanup, WR-13, WR-14
- **Root cause(s):** WR-13 rewrite finalization checked only unchanged identity and uncommitted state after cleanup cleared its controller/token; WR-14 published-import finalization checked only unchanged authority identity after cleanup aborted and cleared its pending controller/token.
- **Fix:** Added a marker-owned exact live-controller predicate; extended Published authority with exact current request ownership; evaluated both finalization decisions before owned cleanup; required exact controller/token/live identity plus uncommitted state before either React state synchronization.
- **Files changed:** backend/tests/architecture/test_phase3_gauntlet.py, frontend/src/features/admin/imports/PublishedMappingImports.tsx, frontend/src/features/admin/imports/PublishedMappingImports.test.tsx, frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx, frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx, frontend/src/features/admin/imports/mutationAuthority.ts, frontend/src/features/admin/imports/mutationAuthority.test.ts, tools/phase3_gauntlet.sh
- **Why not caught:** Existing unmount tests proved aborted signals and suppressed callbacks, toasts, close, focus, and refresh effects, but did not directly observe async-finally state synchronization. React can ignore a post-unmount setter, and the mutation registry owned no exact controller-lifecycle predicate.
- **Recurrence guard:** The two component suites directly assert false post-unmount and true live-boundary finalization decisions; `mutationAuthority.test.ts` covers controller/token/identity/commit truth-table neighbors; the architecture contract and gauntlet retain exactly five semantic markers and require 52/52 owned frontend mutants killed inside the canonical 14-layer gate.
---

## xliff-real-world-imports — strict adapter misclassified real XLIFF metadata and inline semantics
- **Date:** 2026-09-09
- **Error patterns:** `No supported localization layout was found`, valid XLIFF schemaLocation or skeleton rejected, invalid XLIFF inline/order documents accepted, `.xlf` and `.xliff` reconciliation fails
- **Root cause(s):** The strict XLIFF adapter implemented a namespace-free structural subset and tag-vocabulary checks but omitted explicitly allowed XML/XSI attributes, the core 2.1 skeleton, group/target-order/inline relationship validation; the import rewrite suffix tuple was not extended when XLIFF was registered; the local Docker image still exposed the pre-XLIFF enum.
- **Fix:** Added bounded XML/XSI namespace rules, skeleton href/content alternatives, inherited xml:space and language validation, target-order uniqueness, sc/ec pairing and copy semantics, canReorder sequence/hierarchy checks, and `.xlf`/`.xliff` at every rewrite-validation boundary; rebuilt backend/worker images and upgraded the local database.
- **Files changed:** backend/src/verboflex/localization/importing/xliff.py, backend/src/verboflex/services/import_jobs.py, backend/tests/unit/localization/importing/test_xliff.py, backend/tests/integration/test_import_jobs.py, backend/alembic/versions/0026_duplicate_quarantine_layout.py
- **Why not caught:** Earlier parser tests used simplified fixtures and no registry contract covered every rewrite-validation boundary; source-level tests also could not detect the stale Docker image.
- **Recurrence guard:** Regression coverage in `backend/tests/unit/localization/importing/test_xliff.py` and `backend/tests/integration/test_import_jobs.py`, plus the public-corpus probe rejecting all 122 Microsoft core-invalid fixtures and the Docker runtime/migration smoke.
---
