---
phase: 2
slug: admin-configuration
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-26
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for TDD feedback sampling during execution. Every API behavior begins with a focused failing test, records RED evidence, receives the minimum implementation, then records GREEN evidence with the same command before refactoring.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend framework** | pytest 9.1.1, Hypothesis 6.165.10, pytest-cov, mutmut |
| **Frontend framework** | Vitest 4.1.11, Testing Library, fast-check 4.9.0, Stryker 10.0.0, Playwright 1.62.1 |
| **Config files** | `backend/pyproject.toml`, `frontend/vite.config.ts`, `frontend/playwright.config.ts`, `frontend/stryker.config.mjs` |
| **Backend quick run** | `cd backend && uv run pytest -q <focused-node-id> -x` |
| **Backend full suite** | `cd backend && uv run pytest -q` |
| **Frontend quick run** | `cd frontend && npm test -- --run <focused-test-file>` |
| **Frontend full suite** | `cd frontend && npm test -- --run && npm run typecheck && npm run build` |
| **End-to-end suite** | `cd frontend && npm run e2e` |
| **Estimated quick runtime** | under 60 seconds for a focused target |

---

## Sampling Rate

- **Before each API implementation task:** Run the focused target and preserve the expected RED failure.
- **After every task commit:** Run the same focused command to prove GREEN; run adjacent tests when a shared invariant changes.
- **After every plan wave:** Run the complete relevant backend or frontend suite, coverage, and generated-client drift check.
- **Before `$gsd-verify-work`:** Full backend/frontend suites, static gates, migration cycle, smoke tests, and targeted mutation tests must be green.
- **Max feedback latency:** 60 seconds for the focused RED/GREEN loop. Tests exceeding this budget belong in a separate integration or phase gate.

---

## Per-Task Verification Map

The planner must replace the provisional `TBD` plan/wave cells with final task coordinates without weakening the listed coverage.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TDD-01 | TBD | TBD | PROD-01 | T-02-02 | Deterministic NFKC/name-key normalization and database uniqueness reject ambiguous identities | unit + migration + concurrency | `cd backend && uv run pytest -q tests/unit/test_product_names.py tests/integration/test_migrations.py -x` | ❌ W0 | ⬜ pending |
| TDD-02 | TBD | TBD | AUTH-02, AUTH-03 | T-02-01, T-02-07 | Non-admin calls cannot mutate state; one-time credentials never persist or leak; at least one active admin remains | unit + API + PostgreSQL concurrency | `cd backend && uv run pytest -q tests/unit/services/test_admin_users.py tests/api/test_admin_users.py tests/integration/test_admin_user_concurrency.py -x` | ❌ W0 | ⬜ pending |
| TDD-03 | TBD | TBD | PROD-02–PROD-07, PROD-09 | T-02-02 | Repository reuse stays product-isolated; topology, branch, target, version, and grouping invariants fail closed | unit + property + integration | `cd backend && uv run pytest -q tests/unit/services/test_mappings.py tests/integration/test_repository_registry.py -x` | ❌ W0 | ⬜ pending |
| TDD-04 | TBD | TBD | PROD-01, PROD-08 | T-02-02, T-02-06 | Publication is atomic, requires every current confirmation, and rejects stale competing writers without changing active state | integration + concurrency | `cd backend && uv run pytest -q tests/integration/test_product_publication.py -x` | ❌ W0 | ⬜ pending |
| TDD-05 | TBD | TBD | BITB-01 | T-02-03, T-02-07 | OAuth state is bound/single-use; exact read scope is enforced; credentials are encrypted, revocable, and redacted | unit + provider-mock + integration | `cd backend && uv run pytest -q tests/integration/test_bitbucket_oauth.py -x` | ❌ W0 | ⬜ pending |
| TDD-06 | TBD | TBD | BITB-03, BITB-04 | T-02-04, T-02-05 | Provider URLs, redirects, pagination, time, depth, count, and byte budgets are bounded and read-only | provider-mock + property + boundary | `cd backend && uv run pytest -q tests/integration/test_bitbucket_client.py -x` | ❌ W0 | ⬜ pending |
| TDD-07 | TBD | TBD | PROD-08, PROD-09 | T-02-05 | Each supported layout proves exact format/encoding/locale shape; malformed, unsupported, mixed, or ambiguous content is non-confirmable | golden fixtures + unit + property | `cd backend && uv run pytest -q tests/unit/localization/preview -x` | ❌ W0 | ⬜ pending |
| TDD-08 | TBD | TBD | PROD-08 | T-02-05, T-02-06 | Durable preview identity prevents stale completion/confirmation; samples and status are deterministic and bounded | worker integration | `cd backend && uv run pytest -q tests/integration/test_preview_jobs.py -x` | ❌ W0 | ⬜ pending |
| TDD-09 | TBD | TBD | UI-03 | T-02-01, T-02-07 | Admin guards, accessible validation, one-time reveal, polling timeout, retry, and stale-form preservation match the API contract | Vitest + Playwright | `cd frontend && npm test -- --run src/features/admin && npm run e2e -- admin-configuration.spec.ts` | ❌ W0 | ⬜ pending |

Threat references are provisional stable identifiers for the Phase 2 plan threat blocks:

- `T-02-01`: hidden admin API elevation.
- `T-02-02`: concurrent or partial configuration mutation.
- `T-02-03`: OAuth CSRF, replay, rotation, or revoke race.
- `T-02-04`: malicious provider pagination, redirect, or path.
- `T-02-05`: hostile/oversized source or ambiguous detector acceptance.
- `T-02-06`: stale preview publication.
- `T-02-07`: temporary password or provider-token disclosure.

---

## Wave 0 Requirements

- [ ] Add `backend/tests/unit/test_product_names.py` and schema-introspection fixtures for the A-01 matrix.
- [ ] Add `backend/tests/unit/services/test_admin_users.py`, `backend/tests/api/test_admin_users.py`, and `backend/tests/integration/test_admin_user_concurrency.py`.
- [ ] Add `backend/tests/unit/services/test_mappings.py`, `backend/tests/integration/test_repository_registry.py`, and `backend/tests/integration/test_product_publication.py`.
- [ ] Add `backend/tests/integration/test_bitbucket_oauth.py`, `backend/tests/integration/test_bitbucket_client.py`, and a provider HTTP mock with write-call spies.
- [ ] Add supported, unsupported, ambiguous, malformed, and encoding-boundary fixtures under `backend/tests/unit/localization/preview/` for Android XML, Qt TS, JSON, and iOS strings.
- [ ] Add `backend/tests/integration/test_preview_jobs.py` with Celery/Redis/PostgreSQL stale-completion and timeout fixtures.
- [ ] Add generated OpenAPI/client cases for every admin resource plus secret-negative assertions.
- [ ] Add focused admin Vitest modules under `frontend/src/features/admin/` and `frontend/e2e/admin-configuration.spec.ts`.
- [ ] Expand mutmut and Stryker targets only as the corresponding implementation modules land.
- [ ] Insert human package-legitimacy checkpoints before promoting `httpx` or installing `defusedxml` and `cryptography` as direct runtime dependencies.

Existing disposable PostgreSQL migration and two-session concurrency harnesses must be extended, not replaced.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Production Bitbucket OAuth consumer configuration | BITB-01 | Consumer permissions and callback URI live outside the repository | Verify the consumer has exactly `repository`, confirm the exact callback URI, connect with disposable credentials, inspect bounded status, then revoke locally |
| Real-provider connect/preview/revoke smoke | BITB-01, BITB-03, BITB-04, PROD-08 | CI uses provider mocks and must not require organization credentials | On localhost, connect a disposable Bitbucket grant, list branches, complete one bounded preview, confirm no provider writes, revoke, and prove subsequent reads fail closed |
| Fernet rotation deployment readiness | BITB-01 | Secret-manager key overlap is environment-owned | Supply a new primary plus previous decrypt key, rotate one encrypted credential generation, then prove old ciphertext decrypts during the window and new ciphertext uses the primary |
| Preview budget fitness against representative repositories | PROD-08 | No production repository corpus is currently available | Run preview on representative repositories and record only bounded counts/durations; do not raise limits silently if one exceeds the contract |

Provider mocks remain the automated acceptance gate; manual OAuth evidence supplements rather than replaces it.

---

## Phase Gate

- [ ] Full backend suite with configured 100% coverage.
- [ ] Full frontend Vitest suite, lint, typecheck, and production build.
- [ ] Targeted mutmut and Stryker runs cover authority, normalization, publication, OAuth scope/bounds, detector, and admin state logic.
- [ ] Ruff, strict mypy, generated OpenAPI/client drift, and secret scans pass.
- [ ] Alembic upgrade → downgrade → upgrade passes against disposable PostgreSQL.
- [ ] Docker Compose reports healthy API, PostgreSQL, Redis, and Celery worker; one mocked preview is enqueued and completed.
- [ ] Playwright desktop and mobile admin-configuration smoke passes.
- [ ] Provider spy proves zero Bitbucket write, branch-create, commit, or pull-request calls.
- [ ] Failed candidate operations preserve an identical active-revision snapshot.
- [ ] API schema, responses, browser state, logs, and persistence contain no provider tokens and no temporary password outside its single successful mutation response.

---

## Validation Sign-Off

- [ ] Final plan task IDs and waves replace every `TBD` cell.
- [ ] All tasks have an `<automated>` verify command or explicit Wave 0 dependency.
- [ ] Sampling continuity: no three consecutive implementation tasks without automated verification.
- [ ] Wave 0 covers all missing test modules and fixtures.
- [ ] No watch-mode flags are used.
- [ ] Focused feedback latency remains below 60 seconds.
- [ ] Every API slice preserves separate RED and GREEN evidence using the same command.
- [ ] `nyquist_compliant: true` is set only after validation proves the complete map.

**Approval:** pending
