# Phase 02 Deferred Items

## Open

- **Plan 02-07 — pre-existing development-only `qs` advisory:** `npm audit` reports
  GHSA-q8mj-m7cp-5q26 at moderate severity through
  `@stryker-mutator/core -> typed-rest-client@2.3.1 -> qs@6.15.1`. The dependency graph
  was not changed by Plan 02-07, the affected package is confined to mutation-test
  tooling, and `npm audit --audit-level=high` passes. Re-evaluate when Stryker updates
  its `typed-rest-client` dependency; do not apply an unreviewed lockfile override.

## Resolved

- **Plan 02-15 — frontend container omits the canonical OpenAPI schema:** resolved
  on 2026-08-28 by copying `frontend/openapi.json` into the Docker build stage before
  typecheck. The RED image build failed with TS2307; the GREEN image build, generated
  client contract, API drift gate, five-service Compose health check and isolated
  `tools/real_smoke.sh --browser-only` flow all passed. Full investigation:
  `.planning/debug/resolved/dockerized-frontend-login.md`.

- **Plan 02-04 — randomized admin-user role-order isolation:** resolved on 2026-08-27 by commit `be0a543`, which declares deterministic `User.roles` ORM ordering and adds a mapper-contract regression. Verification passed with the stable seed, adjacent admin tests 35/35, and the full randomized backend suite 344/344. Full investigation: `.planning/debug/resolved/randomized-admin-role-order.md`.
