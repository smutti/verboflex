# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

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
