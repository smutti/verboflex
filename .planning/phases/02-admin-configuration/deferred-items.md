# Phase 02 Deferred Items

## Open

- **Plan 02-25 — pre-existing Ruff format drift outside the candidate/publication
  scope:** repository-wide `ruff format --check src tests` reports formatting changes
  in `tests/architecture/test_phase2_live_provider_smoke.py`,
  `tests/integration/test_admin_user_concurrency.py`, and
  `tests/unit/services/test_admin_users.py`. These files are unchanged from the Plan
  02-25 starting revision; all Plan 02-25 files pass the scoped format gate.

- **Plan 02-24 — pre-existing full-suite failures outside the product-graph scope:** the
  719-test backend sweep reached 711 passes and 8 failures. Two product-schema/order
  regressions caused by Plan 02-24 were fixed and now pass. The six remaining failures
  are unchanged preview-worker adapter wiring (`get_redis_client` absent at the starting
  revision), two test-infrastructure checks for the unpublished Redis test port 56379,
  one Bitbucket credential-row expectation, and two legacy CLI deactivation expectations
  that conflict with the already-present last-admin survivor invariant. All Plan 02-24
  task, migration, graph, publication, repository, static, and targeted regression gates
  pass; these unrelated failures were not modified.

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
