---
phase: 1
slug: platform-foundation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-05
---

# Phase 1 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Backend: pytest 9.0.3; Frontend: Vitest 4.1.5; Smoke: Docker Compose v2.38.2 |
| **Config file** | Backend: `backend/pyproject.toml`; Frontend: `frontend/vite.config.ts`; Docker: `docker-compose.yml` |
| **Quick run command** | `cd backend && uv run pytest -q`; `cd frontend && npm run test -- --run` |
| **Full suite command** | `cd backend && uv run pytest -q && cd ../frontend && npm run test -- --run && npm run build && cd .. && docker compose up -d --build && docker compose ps` |
| **Estimated runtime** | ~120 seconds after dependencies/images are warm |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the changed tier.
- **After every plan wave:** Run backend pytest, frontend Vitest/build, and the Docker Compose smoke command relevant to that wave.
- **Before `$gsd-verify-work`:** Backend tests, frontend tests/build, Alembic upgrade, Celery smoke, and Docker Compose smoke must be green.
- **Max feedback latency:** 120 seconds for quick checks once dependencies are installed.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01-01 | 1 | PLAT-01 | - | N/A | file/smoke | `test -f backend/pyproject.toml && test -f frontend/package.json && docker compose config` | NO W0 | pending |
| 01-02-01 | 01-02 | 2 | PLAT-03 | T-API-01 | Health endpoint exposes no sensitive config | API test | `cd backend && uv run pytest tests/api/test_health.py -q` | NO W0 | pending |
| 01-02-02 | 01-02 | 2 | PLAT-04 | T-DB-01 | DB access uses SQLAlchemy/session dependency | backend test | `cd backend && uv run pytest tests/db/test_session.py -q` | NO W0 | pending |
| 01-02-03 | 01-02 | 2 | PLAT-05 | T-DB-02 | Alembic creates expected auth tables | migration smoke | `docker compose run --rm backend uv run alembic upgrade head` | NO W0 | pending |
| 01-03-01 | 01-03 | 3 | AUTH-01 | T-AUTH-01 | Login issues bearer token with expiry | API/security test | `cd backend && uv run pytest tests/auth/test_tokens.py -q` | NO W0 | pending |
| 01-03-02 | 01-03 | 3 | AUTH-04 | T-AUTH-02 | Roles attach to users and dependencies enforce them | API/model test | `cd backend && uv run pytest tests/auth/test_roles.py -q` | NO W0 | pending |
| 01-04-01 | 01-04 | 4 | PLAT-02 | T-UI-01 | Frontend shell avoids token persistence in browser storage | frontend test/build | `cd frontend && npm run test -- --run && npm run build` | NO W0 | pending |
| 01-04-02 | 01-04 | 4 | UI-01 | - | N/A | frontend test/build | `cd frontend && npm run test -- --run && npm run build` | NO W0 | pending |
| 01-04-03 | 01-04 | 4 | PLAT-06 | T-WORKER-01 | Worker runs separate from API and uses Redis broker | integration/smoke | `cd backend && uv run pytest tests/worker/test_smoke_task.py -q` | NO W0 | pending |
| 01-05-01 | 01-05 | 5 | PLAT-01..UI-01 | T-GATE-01 | Quality gate documents tests, review, and deploy smoke | full gate | `cd backend && uv run pytest -q && cd ../frontend && npm run test -- --run && npm run build && cd .. && docker compose up -d --build && docker compose ps` | NO W0 | pending |

*Status values: pending, green, red, flaky.*

---

## Wave 0 Requirements

- [ ] `backend/tests/api/test_health.py` - covers FastAPI health/OpenAPI baseline.
- [ ] `backend/tests/db/test_session.py` - covers SQLAlchemy session and settings.
- [ ] `backend/tests/auth/test_tokens.py` - covers OAuth2 bearer login, expiry, refresh, logout, and no inactive user access.
- [ ] `backend/tests/auth/test_roles.py` - covers role seed data and dependency enforcement.
- [ ] `backend/tests/worker/test_smoke_task.py` - covers Celery sample task path.
- [ ] `frontend/src/**/*.test.tsx` or `frontend/tests/` - covers auth shell/dashboard and shadcn component import.
- [ ] `docker-compose.yml`, `docker-compose.staging.yml`, `docker-compose.prod.yml` - support service smoke.
- [ ] `docs/phase-01-smoke.md` - records repeatable smoke commands and expected results.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Code review completed | Phase quality gate | Review is a human/agent review artifact rather than an automated unit behavior | Run `/gsd-code-review` after execution and record findings/resolution in Phase 1 summary. |
| Browser visual sanity of neutral dashboard | UI-01 | Vitest/build cannot fully validate visual composition | Start frontend through Docker Compose, open app, capture screenshot or note manual check in `docs/phase-01-smoke.md`. |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags in validation commands.
- [x] Feedback latency target recorded.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending execution

