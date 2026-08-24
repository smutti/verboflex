---
phase: 1
slug: platform-foundation
status: revised
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-05
updated: 2026-08-24
---

# Phase 1 — Validation Strategy

## Test infrastructure

| Property | Value |
|---|---|
| Selected runtime | Python 3.14.7 via uv (`python3` on PATH is 3.9.6); Node 24.15.0/npm 11.16.0 |
| Observed tools | uv 0.11.12; Docker 29.7.2; Docker Compose 5.3.1 |
| Frameworks | pytest 9.1.1 observed; Vitest 4.1.11 observed; Playwright 1.62.1 observed; exact compatible versions are authoritative in `uv.lock`/`package-lock.json` |
| Config | `backend/pyproject.toml`; `frontend/package.json`; `frontend/openapi-ts.config.ts`; `frontend/stryker.config.mjs`; Compose base/overlays |
| Fast feedback | Backend: `cd backend && uv run pytest <focused-path> -q`; frontend: `cd frontend && npm run test -- --run <focused-path>` |
| Full phase gate | `tools/gauntlet.sh` |

## Sampling policy

- Before every API test, the final-signature route stub is callable and returns 501; RED must fail on a behavior assertion, never import, collection, or 404.
- After every RED/GREEN/REFACTOR commit, run the focused command in the task row below.
- After each plan, run all tests for its changed tier; run type/lint/build after frontend plans.
- Slow PostgreSQL concurrency, Docker, Playwright, mutation, audit, and full gauntlet checks run only after the corresponding focused suites are green.
- A fresh-context code and OWASP ASVS L1 review closes every critical/high finding before the final run; each fix recomputes the digest and reruns the full gauntlet.
- Final evidence compares the immutable source-set digest, including the closed review artifact, before writing the report; report/log/runtime/build outputs are excluded from that source set.
- Independent verification is blind-first: exactly four task inputs, append-only attacks/findings before draft EVIDENCE disclosure, human finding grades, two rounds by default, and source-specific `passed|failed|blocked|not performed` recording.

## Per-task validation map

| Task | Plan / wave | Requirements | Type | Automated validation |
|---|---:|---|---|---|
| Backend package audit acknowledgment | 01-01 / 1 | PLAT-01, PLAT-03, AUTH-01 | manual blocking-human | Human verifies Python SUS rows, publishers/sources, compatibility, and no SLOP/unlisted direct package. |
| Frontend package audit acknowledgment | 01-01 / 1 | PLAT-02, UI-01 | manual blocking-human | Human verifies npm SUS rows, publishers/sources, compatibility, and no SLOP/unlisted direct package. |
| Backend project scaffold | 01-02 / 2 | PLAT-01, PLAT-03 | tracer | `cd backend && uv run python -c "from verboflex.main import app; assert app.openapi()['info']['title'] == 'VerboFlex API'" && uv run mypy src` |
| Endpoint stubs and health | 01-02 / 2 | PLAT-03, AUTH-01 | TDD | `cd backend && uv run pytest tests/api/test_health.py -q` |
| Frontend project/generated client | 01-03 / 3 | PLAT-01, PLAT-02, PLAT-03 | tracer | `cd frontend && npm run api:generate && npm run typecheck` |
| Generated health UI | 01-03 / 3 | PLAT-02, PLAT-03 | TDD | `cd frontend && npm run test -- --run src/App.test.tsx && npm run api:check && npm run build` |
| Secure settings | 01-04 / 4 | PLAT-01 | TDD | `cd backend && uv run pytest tests/core/test_config.py -q` |
| Docker topologies | 01-04 / 4 | PLAT-01, PLAT-06 | config | `docker compose config >/dev/null && docker compose -f docker-compose.yml -f docker-compose.staging.yml config >/dev/null && docker compose -f docker-compose.yml -f docker-compose.prod.yml config >/dev/null` |
| Reversible auth migration | 01-05 / 5 | PLAT-04, PLAT-05, AUTH-04 | TDD/integration | `cd backend && uv run pytest tests/integration/test_migrations.py -q` |
| Bootstrap/reset/password primitives | 01-05 / 5 | AUTH-01, AUTH-04 | TDD/property | `cd backend && uv run pytest tests/auth/test_bootstrap_admin.py tests/auth/test_passwords.py -q` |
| Scoped access tokens | 01-06 / 6 | AUTH-01 | TDD/property | `cd backend && uv run pytest tests/auth/test_access_tokens.py -q` |
| Ordinary/restricted login | 01-06 / 6 | AUTH-01 | API TDD | `cd backend && uv run pytest tests/auth/test_login.py -q` |
| Current identity/roles | 01-06 / 6 | AUTH-04 | API TDD | `cd backend && uv run pytest tests/auth/test_roles.py tests/api/test_me.py -q` |
| Refresh/replay/concurrency | 01-07 / 7 | AUTH-01 | API TDD/integration | `cd backend && uv run pytest tests/auth/test_refresh.py tests/integration/test_refresh_concurrency.py -q` |
| Idempotent logout | 01-07 / 7 | AUTH-01 | API TDD | `cd backend && uv run pytest tests/auth/test_logout.py -q` |
| Atomic password change/revocation | 01-07 / 7 | AUTH-01 | API TDD | `cd backend && uv run pytest tests/auth/test_password_change.py -q` |
| Complete rate policies | 01-08 / 8 | PLAT-03, AUTH-01 | API TDD | `cd backend && uv run pytest tests/api/test_rate_limits.py tests/auth/test_login.py tests/auth/test_refresh.py -q` |
| Bounded system status | 01-08 / 8 | PLAT-03, AUTH-01 | API TDD | `cd backend && uv run pytest tests/api/test_system_status.py -q` |
| Celery/Redis task boundary | 01-08 / 8 | PLAT-06 | TDD/integration | `cd backend && uv run pytest tests/worker/test_smoke_task.py tests/architecture/test_background_boundaries.py -q` |
| Full OpenAPI generation/drift | 01-09 / 9 | PLAT-02, PLAT-03 | TDD/contract | `cd backend && uv run pytest tests/api/test_openapi_contract.py -q && cd ../frontend && npm run api:check && npm run typecheck` |
| Memory-only session state | 01-09 / 9 | AUTH-01 | TDD/property | `cd frontend && npm run test -- --run src/features/auth/session.test.tsx src/features/auth/session.property.test.ts src/features/auth/storage-guard.test.ts` |
| Form/feedback/action shadcn components | 01-10 / 10 | PLAT-02, UI-01 | static | `cd frontend && npm run typecheck && npm run lint` |
| Navigation/disclosure/loading shadcn components | 01-10 / 10 | PLAT-02, UI-01 | static | `cd frontend && npm run typecheck && npm run lint` |
| Exact UI tokens | 01-11 / 11 | PLAT-02, UI-01 | static/build | `cd frontend && npm run lint && npm run build` |
| Theme drift detector | 01-11 / 11 | PLAT-02, UI-01 | TDD/static | `cd frontend && npm run test -- --run src/styles/theme.test.ts && npm run build` |
| Auth route guards | 01-12 / 12 | AUTH-01 | TDD | `cd frontend && npm run test -- --run src/router.test.tsx` |
| Login/change-password forms | 01-12 / 12 | AUTH-01, UI-01 | TDD | `cd frontend && npm run test -- --run src/features/auth/LoginPage.test.tsx src/features/auth/ChangePasswordPage.test.tsx` |
| Dashboard identity/status shell | 01-13 / 13 | AUTH-04, UI-01 | TDD | `cd frontend && npm run test -- --run src/components/layout/AppShell.test.tsx && npm run typecheck` |
| Responsive/auth browser path | 01-13 / 13 | PLAT-02, AUTH-01, UI-01 | TDD/E2E | `cd frontend && npm run test -- --run src/components/layout/AppShell.test.tsx && npm run build && npm run e2e -- --grep "auth shell"` |
| Immutable digest and fail-closed gates | 01-14 / 14 | all Phase 1 | TDD/tooling | `bash -n tools/source_state.sh tools/gauntlet.sh && tools/source_state.sh --self-test-manifest && tools/gauntlet.sh --preflight` |
| Docker/adversarial smoke | 01-14 / 14 | PLAT-01..06, AUTH-01/04, UI-01 | TDD/smoke | `bash -n tools/real_smoke.sh tools/adversarial_auth.sh && tools/real_smoke.sh --preflight && tools/adversarial_auth.sh --self-test` |
| Fresh-context code and ASVS L1 review/revision | 01-14 / 14 | all Phase 1 | manual review/automated gate | `test -s docs/reviews/phase-01-code-security.md && tools/source_state.sh --verify-review-closed && tools/source_state.sh --verify-review-source && tools/gauntlet.sh`; critical/high findings block and every fix forces a new digest/full run. |
| Final unchanged-source gauntlet | 01-15 / 15 | all Phase 1 | gauntlet/manual UI | `tools/gauntlet.sh && tools/source_state.sh --verify-final-before-report` plus consolidated human UI check. |
| Blind verification and digest-bound evidence | 01-15 / 15 | all Phase 1 | independent/manual protocol | Read `verifier.md` in full; give exactly contract, SPEC, exact repo state/digest, and gauntlet; freeze blind attacks/findings before revealing draft EVIDENCE; `test -s docs/evidence/phase-01.md && tools/source_state.sh --verify-report-digest` only for `passed` or explicit `not performed` downgrade. |

## Wave 0 artifacts

No implementation test files exist yet. Each listed producer must create its test before production code in its plan:

- 01-02: `backend/tests/api/test_health.py` and backend pytest/type configuration.
- 01-03: `frontend/src/App.test.tsx` and frontend Vitest/type/build configuration.
- 01-04: `backend/tests/core/test_config.py` and Compose render seam.
- 01-05: `backend/tests/integration/test_migrations.py`, `tests/auth/test_bootstrap_admin.py`, `tests/auth/test_passwords.py`.
- 01-06: `tests/auth/test_access_tokens.py`, `test_login.py`, `test_roles.py`, `tests/api/test_me.py`.
- 01-07: `tests/auth/test_refresh.py`, `test_logout.py`, `test_password_change.py`, `tests/integration/test_refresh_concurrency.py`.
- 01-08: `tests/api/test_rate_limits.py`, `test_system_status.py`, `tests/worker/test_smoke_task.py`, `tests/architecture/test_background_boundaries.py`.
- 01-09: `tests/api/test_openapi_contract.py`, frontend session/property/storage tests.
- 01-10: enumerated owned shadcn component files plus type/lint seams.
- 01-11: `frontend/src/styles/theme.test.ts` with a proved drift negative control.
- 01-12: router, login, and change-password component tests.
- 01-13: shell component test and `frontend/e2e/auth-shell.spec.ts`.
- 01-14: source-manifest/checker negative controls, smoke/adversarial self-tests, and `docs/reviews/phase-01-code-security.md` closure checks.
- 01-15: final digest/report checks and `docs/evidence/phase-01.md`.

## Contract constants under validation

- Exact roles: `admin`, `product_manager_reviewer`, `translator`, `viewer`.
- Refresh cookie: `verboflex_refresh`, `HttpOnly`, `SameSite=Lax`, `Path=/api/v1/auth`, Secure in staging/production.
- Access TTL 900 seconds; password-change TTL 300 seconds; refresh expiry seven days.
- No token in localStorage/sessionStorage/IndexedDB/URL/logs/analytics.

## Manual-only gates

| Gate | Timing | Reason |
|---|---|---|
| Backend/frontend package audit | Plan 01-01 | Supply-chain trust requires human acknowledgment; never auto-approved. |
| Consolidated UI review | Plan 01-15 final run | Visual hierarchy, focus visibility, responsive composition, and exact copy require human judgment after automated checks. |
| Fresh-context code + ASVS L1 review | Plan 01-14 before final evidence | Persisted review covers the canonical source set; unresolved critical/high findings block and every fix requires a new digest/full gauntlet. |
| Independent Tier 3 verification | Plan 01-15 after final gauntlet | Verifier reads `verifier.md` fully; blind phase gets exactly contract, SPEC, exact repo state/digest, and gauntlet. Builder discussion, draft EVIDENCE, raw logs/case study, and separate review-artifact handoff are withheld. Blind attack record is append-only; human grades findings; two-round default cap; fail-closed four-state verdict. |

## Sign-off

- [x] Every one of the 34 revised plan tasks maps to an automated command or explicit manual gate.
- [x] Focused commands precede slow E2E/Docker/mutation/full-gauntlet checks.
- [x] API RED tests require callable 501 stubs.
- [x] Framework/tool versions are current observations; lockfiles are authoritative after resolution.
- [x] Immutable source-set digest/report ordering is represented in validation.
- [x] Fresh-context code/ASVS L1 review precedes final evidence and remains separate from independent Tier 3 verification.
- [x] Independent verification follows the four-input blind-first protocol, delayed EVIDENCE comparison, human grading, two-round cap, and source-specific finalization rules.
- [x] No three consecutive implementation tasks lack automated feedback.

**Approval:** pending SPEC approval and execution.
