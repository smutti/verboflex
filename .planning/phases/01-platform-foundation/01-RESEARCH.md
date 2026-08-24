# Phase 1: Platform Foundation - Research

**Researched:** 2026-05-05
**Decision update:** 2026-08-24 (internal authentication flow)
**Domain:** Split web application foundation, OAuth2/JWT auth, Dockerized FastAPI/React stack
**Confidence:** HIGH

## User Constraints

- **D-01:** Use OWASP-aligned OAuth2 behavior for Phase 1 rather than inventing a custom session model.
- **D-02:** Establish an internal email/password OAuth2 token flow for v1. Use corporate email as the unique login identifier, create the first admin and perform Phase 1 administrative password resets through CLI commands, require a password change after bootstrap/reset, and keep a clean boundary for future Microsoft Entra ID or other external OAuth2/OIDC identity provider integration.
- **D-03:** Use short-lived bearer/JWT access tokens with explicit expiry.
- **D-04:** Include a refresh/session strategy in the design; downstream planning should choose concrete lifetimes and rotation behavior from OWASP guidance.
- **D-05:** Do not persist auth tokens in browser `localStorage`.
- **D-06:** Where cookies are used, require secure cookie attributes such as `HttpOnly`, `Secure`, and `SameSite` as appropriate to the deployment.
- **D-07:** Backend role checks must be enforced on protected API endpoints; frontend hiding/disabling controls is not sufficient authorization.
- **D-07a:** Password changes, administrative resets, account deactivation, and logout revoke the affected refresh sessions.
- **D-08:** Use Docker as the execution and deployment baseline.
- **D-09:** Provide staging and production-oriented configurations/environments from Phase 1, even if they initially run the same application slice.
- **D-10:** Phase 1 smoke verification must prove the Dockerized frontend, backend, PostgreSQL, Redis, Celery worker, and Alembic migrations can run.
- **D-11:** Deploy/build smoke verification should be command-driven and documented so later quality-gate plans can repeat it.
- **D-12:** After login, show a neutral landing dashboard rather than forcing admin setup or review workflow first.
- **D-13:** Design the dashboard shell so later phases can customize visible content based on the logged-in user's roles, usage, or context.
- **D-14:** Keep the initial shell focused on navigation, identity/session status, and empty states for future modules; do not add Phase 2+ capabilities in Phase 1.
- **D-15:** The React frontend should consume FastAPI through a generated OpenAPI client.
- **D-16:** The FastAPI OpenAPI schema becomes part of the frontend/backend contract from the foundation phase.
- **D-17:** Planning should include local commands that regenerate the client from the backend schema and fail visibly when the contract drifts.

## Project Constraints from AGENTS.md

- Separate `frontend/` and `backend/` applications are mandatory. [CITED: AGENTS.md]
- Frontend stack is React, Vite, TypeScript, and shadcn/ui installed as project-owned component code. [CITED: AGENTS.md]
- Backend stack is Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic, Celery, and Redis. [CITED: AGENTS.md]
- Authentication uses OAuth2 bearer tokens with internal users and multiple roles. [CITED: AGENTS.md]
- Every phase must include targeted tests, code review, and build/deploy smoke verification. [CITED: AGENTS.md]
- v1 must not implement Bitbucket, localization parsing, search, constraints, comments, review workflow, or PR behavior during Phase 1 beyond placeholders needed by the foundation. [CITED: 01-CONTEXT.md]

## Summary

Phase 1 should build a conventional split-app foundation: `backend/` owns the FastAPI API, SQLAlchemy models, Alembic migrations, auth/token logic, and Celery worker; `frontend/` owns the Vite React SPA, shadcn/ui components, generated API client, auth shell, and neutral dashboard. Docker Compose should be the canonical run path for local, staging, and production-like smoke checks. [CITED: https://fastapi.tiangolo.com/deployment/docker/] [CITED: https://docs.docker.com/compose/how-tos/multiple-compose-files/]

Use uv for backend dependency locking and execution because it is available locally and its project model gives `pyproject.toml`, `.python-version`, and `uv.lock` as reproducible inputs. [VERIFIED: `uv --version` -> 0.11.12] [CITED: https://docs.astral.sh/uv/guides/projects/] Use npm for the frontend because Node and npm are available locally and shadcn/ui documents Vite setup through npm-compatible commands. [VERIFIED: `node --version` -> v24.15.0, `npm --version` -> 11.16.0] [CITED: https://ui.shadcn.com/docs/installation/vite]

**Primary recommendation:** Scaffold a Docker-first split application with uv-managed FastAPI backend, npm-managed Vite frontend, server-side OAuth2/JWT auth plus rotated refresh sessions, generated `@hey-api/openapi-ts` client, and a repeatable phase quality gate.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| OAuth2 password login and token issuance | API / Backend | Database | FastAPI owns authentication endpoints, password verification, JWT signing, and refresh-session persistence. |
| Role model and authorization checks | API / Backend | Database | Backend enforcement is required; roles are durable records and dependencies enforce access. |
| Token presentation and session UI | Browser / Client | API / Backend | SPA keeps only the short-lived access token in memory and uses backend refresh endpoint for continuity. |
| OpenAPI contract | API / Backend | Browser / Client | FastAPI generates the schema; frontend consumes generated client output. |
| Neutral dashboard shell | Browser / Client | API / Backend | The shell is a UI concern, backed by `/me` identity/role data. |
| SQLAlchemy models and migrations | Database / Storage | API / Backend | Alembic owns schema evolution, SQLAlchemy metadata is the source for app models. |
| Celery smoke task | API / Backend | Redis | Backend defines and enqueues tasks; Redis brokers and stores task results. |
| Docker run/deploy baseline | Infrastructure | API / Backend, Browser / Client | Compose connects all services and provides local/staging/prod-oriented run paths. |

## Standard Stack

### Core

| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| Python | 3.14.7 selected/available via uv | Backend runtime | Bare system `python3` is 3.9.6; `.python-version` and uv select 3.14.7 for the project. |
| uv | 0.11.12 local | Backend dependency/project management | Provides `pyproject.toml`, `.python-version`, `uv.lock`, and `uv run`. [CITED: https://docs.astral.sh/uv/guides/projects/] |
| FastAPI | 0.141.1 observed | HTTP API and OpenAPI | Exact compatible version is frozen by `uv.lock`; see Package Legitimacy Audit. |
| SQLAlchemy | 2.0.52 observed | ORM | Exact compatible version is frozen by `uv.lock`. |
| Alembic | 1.19.1 observed | Migrations | Exact compatible version is frozen by `uv.lock`. |
| psycopg | 3.3.4 | PostgreSQL driver | Current PostgreSQL driver for SQLAlchemy connection URLs. [VERIFIED: PyPI] |
| Celery | 5.6.3 | Background worker | Celery officially documents Redis broker/result backend support. [CITED: https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html] |
| Redis Python client | 8.1.0 observed | Celery Redis support | Exact compatible version is frozen by `uv.lock`. |
| React | 19.2.8 observed | SPA runtime | Exact compatible version is frozen by `package-lock.json`. |
| Vite | 8.2.2 observed | Dev/build tooling | Exact compatible version is frozen by `package-lock.json`. |
| TypeScript | 7.0.2 observed | Frontend type system | Exact compatible version is frozen by `package-lock.json`. |
| shadcn CLI | 4.19.0 observed | UI component installation | Exact audited version is invoked project-locally. |
| Docker Compose | 5.3.1 local | Service orchestration | Required Docker baseline and multi-compose staging/prod overlays. |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| pydantic-settings | 2.15.0 observed | Environment settings | Exact compatible version is frozen by `uv.lock`. |
| PyJWT | 2.13.0 observed | JWT signing/verification | Use for signed access tokens. |
| pwdlib[argon2] | 0.3.1 observed | Password hashing | FastAPI docs recommend `pwdlib` and Argon2. |
| python-multipart | 0.0.32 observed | OAuth2 form parsing | Required for `OAuth2PasswordRequestForm`. |
| pytest | 9.1.1 observed | Backend tests | Exact compatible version is frozen by `uv.lock`. |
| httpx | 0.28.1 | Test HTTP client | Used by FastAPI/Starlette testing patterns and direct API integration checks. |
| Vitest | 4.1.11 observed | Frontend tests | Vite-native test runner. |
| @testing-library/react | 16.3.2 | Component tests | Verify dashboard/auth shell behavior without browser E2E overhead. |
| @hey-api/openapi-ts | 0.99.0 observed | Generated API SDK/client | Exact pin required because it is pre-1.0. |
| @hey-api/client-fetch | bundled/default plugin | Fetch API client | Use generated fetch client and runtime config for base URL/auth. [CITED: https://heyapi.dev/openapi-ts/clients/fetch] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| uv | pip + requirements.txt | Simpler but less reproducible; loses `uv.lock` and `uv run` consistency. |
| @hey-api/openapi-ts | openapi-typescript + openapi-fetch | Lighter type-only path, but user requested a generated client and Hey API generates SDK/client code. |
| JWT access + opaque refresh session | Long-lived JWT only | Simpler but weaker revocation/session control and worse fit for OWASP-aligned session behavior. |
| Docker Compose overlays | Separate unrelated compose files | Overlays let staging/prod reuse base service definitions and reduce drift. |

## Package Legitimacy Audit

> Required because Phase 1 installs Python and npm packages. Checked on 2026-08-24 with the GSD registry seam and independently confirmed with `python3.14 -m pip index versions <package>` or `npm view <package> version`. The audit covers every direct dependency authorized by `01-SPEC.md`; transitive dependencies remain constrained by the committed lockfiles and final vulnerability/license audits.

The GSD PyPI adapter cannot obtain weekly download counts, so it conservatively classifies every Python package as `SUS` even when the package exists and exposes project metadata. The npm adapter marks a current release `SUS` when it is less than 30 days old or its download count is unavailable. These are blocking human-verification items, not `SLOP` findings. Exact compatible versions will be selected for Python 3.14/Node 24 and frozen in `uv.lock`/`package-lock.json`; no unlisted direct package may be installed without a SPEC revision.

### Python packages

| Package | Registry version observed | Latest release / age signal | Downloads | Source metadata | Verdict | Disposition |
|---|---:|---|---|---|---|---|
| `fastapi` | 0.141.1 | 2026-07-29 / <30d | unavailable to adapter | github.com/fastapi/fastapi | SUS | Flagged — human approval required |
| `uvicorn` | 0.52.4 | 2026-08-19 / <30d | unavailable to adapter | github.com/Kludex/uvicorn | SUS | Flagged — human approval required |
| `pydantic-settings` | 2.15.0 | 2026-08-07 / <30d | unavailable to adapter | github.com/pydantic/pydantic-settings | SUS | Flagged — human approval required |
| `sqlalchemy` | 2.0.52 | 2026-08-11 / <30d | unavailable to adapter | sqlalchemy.org | SUS | Flagged — human approval required |
| `alembic` | 1.19.1 | 2026-08-08 / <30d | unavailable to adapter | github.com/sqlalchemy/alembic | SUS | Flagged — human approval required |
| `psycopg` | 3.3.4 | 2026-05-01 / >30d | unavailable to adapter | psycopg.org | SUS | Flagged — human approval required |
| `celery` | 5.6.3 | 2026-03-26 / >30d | unavailable to adapter | docs.celeryq.dev | SUS | Flagged — human approval required |
| `redis` | 8.1.0 | 2026-07-30 / <30d | unavailable to adapter | github.com/redis/redis-py | SUS | Flagged — human approval required |
| `PyJWT` | 2.13.0 | 2026-05-21 / >30d | unavailable to adapter | github.com/jpadilla/pyjwt | SUS | Flagged — human approval required |
| `pwdlib` | 0.3.1 | 2026-08-12 / <30d | unavailable to adapter | github.com/frankie567/pwdlib | SUS | Flagged — human approval required |
| `python-multipart` | 0.0.32 | 2026-06-04 / >30d | unavailable to adapter | github.com/Kludex/python-multipart | SUS | Flagged — human approval required |
| `email-validator` | 2.3.0 | 2025-08-26 / >30d | unavailable to adapter | github.com/JoshData/python-email-validator | SUS | Flagged — human approval required |
| `pytest` | 9.1.1 | 2026-06-19 / >30d | unavailable to adapter | github.com/pytest-dev/pytest | SUS | Flagged — human approval required |
| `pytest-cov` | 7.1.0 | 2026-03-21 / >30d | unavailable to adapter | none in PyPI metadata | SUS | Flagged — verify publisher/source before install |
| `httpx` | 0.28.1 | 2024-12-06 / >30d | unavailable to adapter | github.com/encode/httpx | SUS | Flagged — human approval required |
| `mypy` | 2.3.1 | 2026-08-15 / <30d | unavailable to adapter | mypy-lang.org | SUS | Flagged — human approval required |
| `ruff` | 0.16.4 | 2026-08-20 / <30d | unavailable to adapter | docs.astral.sh/ruff | SUS | Flagged — human approval required |
| `hypothesis` | 6.165.10 | 2026-08-16 / <30d | unavailable to adapter | none in PyPI metadata | SUS | Flagged — verify publisher/source before install |
| `pytest-randomly` | 4.1.0 | 2026-04-20 / >30d | unavailable to adapter | none in PyPI metadata | SUS | Flagged — verify publisher/source before install |
| `mutmut` | 3.7.0 | 2026-07-31 / <30d | unavailable to adapter | github.com/boxed/mutmut | SUS | Flagged — human approval required |
| `diff-cover` | 10.5.1 | 2026-08-16 / <30d | unavailable to adapter | github.com/Bachmann1234/diff-cover | SUS | Flagged — human approval required |
| `pip-audit` | 2.10.1 | 2026-06-10 / >30d | unavailable to adapter | github.com/pypa/pip-audit | SUS | Flagged — human approval required |
| `pip-licenses` | 5.5.5 | 2026-03-28 / >30d | unavailable to adapter | none in PyPI metadata | SUS | Flagged — verify publisher/source before install |
| `detect-secrets` | 1.5.0 | 2024-05-06 / >30d | unavailable to adapter | github.com/Yelp/detect-secrets | SUS | Flagged — human approval required |
| `radon` | 6.0.1 | 2023-03-26 / >30d | unavailable to adapter | github.com/rubik/radon | SUS | Flagged — human approval required |

### npm packages

| Package | Registry version observed | Latest release / age signal | Downloads/week | Source repo | Verdict | Disposition |
|---|---:|---|---:|---|---|---|
| `react` | 19.2.8 | >30d | 170,480,639 | github.com/react/react | OK | Approved |
| `react-dom` | 19.2.8 | >30d | 159,631,504 | github.com/react/react | OK | Approved |
| `react-router-dom` | 7.18.2 | <30d | 42,644,027 | github.com/remix-run/react-router | SUS | Flagged — human approval required |
| `react-hook-form` | 7.86.0 | <30d | 59,949,398 | github.com/react-hook-form/react-hook-form | SUS | Flagged — human approval required |
| `zod` | 4.4.3 | >30d | 265,744,393 | github.com/colinhacks/zod | OK | Approved |
| `@hookform/resolvers` | 5.9.1 | <30d | 50,943,846 | github.com/react-hook-form/resolvers | SUS | Flagged — human approval required |
| `lucide-react` | 1.34.0 | <30d | 96,054,697 | github.com/lucide-icons/lucide | SUS | Flagged — human approval required |
| `class-variance-authority` | 0.7.1 | >30d | 64,279,699 | github.com/joe-bell/cva | OK | Approved |
| `clsx` | 2.1.1 | >30d | 120,733,677 | github.com/lukeed/clsx | OK | Approved |
| `tailwind-merge` | 3.6.0 | >30d | 82,644,022 | github.com/dcastil/tailwind-merge | OK | Approved |
| `@radix-ui/react-slot` | 1.3.3 | >30d | 174,163,038 | github.com/radix-ui/primitives | OK | Approved |
| `@radix-ui/react-label` | 2.1.15 | >30d | 57,630,615 | github.com/radix-ui/primitives | OK | Approved |
| `@radix-ui/react-tooltip` | 1.2.16 | >30d | 58,492,481 | github.com/radix-ui/primitives | OK | Approved |
| `@radix-ui/react-dropdown-menu` | 2.1.24 | >30d | 58,328,475 | github.com/radix-ui/primitives | OK | Approved |
| `@radix-ui/react-separator` | 1.1.15 | >30d | 57,419,445 | github.com/radix-ui/primitives | OK | Approved |
| `@radix-ui/react-dialog` | 1.1.23 | >30d | 72,282,918 | github.com/radix-ui/primitives | OK | Approved |
| `sonner` | 2.0.8 | <30d | 51,906,228 | github.com/emilkowalski/sonner | SUS | Flagged — human approval required |
| `vite` | 8.2.2 | <30d | 169,369,863 | github.com/vitejs/vite | SUS | Flagged — human approval required |
| `@vitejs/plugin-react` | 6.1.0 | <30d | 83,483,737 | github.com/vitejs/vite-plugin-react | SUS | Flagged — human approval required |
| `typescript` | 7.0.2 | >30d | 269,606,477 | github.com/microsoft/TypeScript | OK | Approved |
| `tailwindcss` | 4.3.3 | >30d | 125,155,069 | github.com/tailwindlabs/tailwindcss | OK | Approved |
| `@tailwindcss/vite` | 4.3.3 | >30d | 46,022,969 | github.com/tailwindlabs/tailwindcss | OK | Approved |
| `tw-animate-css` | 1.4.0 | >30d | 38,303,711 | github.com/Wombosvideo/tw-animate-css | OK | Approved |
| `shadcn` | 4.19.0 | <30d | 8,179,709 | github.com/shadcn-ui/ui | SUS | Flagged — human approval required |
| `@hey-api/openapi-ts` | 0.99.0 | >30d | 4,316,910 | github.com/hey-api/hey-api | OK | Approved; exact pre-1.0 version must be pinned |
| `vitest` | 4.1.11 | <30d | 93,297,210 | github.com/vitest-dev/vitest | SUS | Flagged — human approval required |
| `@vitest/coverage-v8` | 4.1.11 | <30d | 35,214,441 | github.com/vitest-dev/vitest | SUS | Flagged — human approval required |
| `jsdom` | 30.0.1 | <30d | 94,597,810 | github.com/jsdom/jsdom | SUS | Flagged — human approval required |
| `@testing-library/react` | 16.3.2 | >30d | 54,661,785 | github.com/testing-library/react-testing-library | OK | Approved |
| `@testing-library/user-event` | 14.6.6 | <30d | 48,658,310 | github.com/testing-library/user-event | SUS | Flagged — human approval required |
| `@testing-library/jest-dom` | 7.0.1 | <30d | 61,215,754 | github.com/testing-library/jest-dom | SUS | Flagged — human approval required |
| `eslint` | 10.9.0 | <30d | 157,876,271 | github.com/eslint/eslint | SUS | Flagged — human approval required |
| `@eslint/js` | 10.0.1 | >30d | 141,529,920 | github.com/eslint/eslint | OK | Approved |
| `typescript-eslint` | 8.67.0 | <30d | 87,927,852 | github.com/typescript-eslint/typescript-eslint | SUS | Flagged — human approval required |
| `eslint-plugin-react-hooks` | 7.1.1 | >30d | 97,785,728 | github.com/facebook/react | OK | Approved |
| `eslint-plugin-react-refresh` | 0.5.4 | <30d | 41,443,200 | github.com/ArnaudBarre/eslint-plugin-react-refresh | SUS | Flagged — human approval required |
| `eslint-plugin-jsx-a11y` | 6.10.2 | >30d | 44,758,896 | github.com/jsx-eslint/eslint-plugin-jsx-a11y | OK | Approved |
| `prettier` | 3.9.6 | >30d | 131,193,178 | github.com/prettier/prettier | OK | Approved |
| `@stryker-mutator/core` | 10.0.0 | <30d | 2,183,317 | github.com/stryker-mutator/stryker-js | SUS | Flagged — human approval required |
| `@stryker-mutator/vitest-runner` | 10.0.0 | <30d | 1,407,341 | github.com/stryker-mutator/stryker-js | SUS | Flagged — human approval required |
| `fast-check` | 4.9.0 | >30d | unavailable to adapter | github.com/dubzzz/fast-check | SUS | Flagged — human approval required |
| `@playwright/test` | 1.62.1 | <30d | unavailable to adapter | github.com/microsoft/playwright | SUS | Flagged — human approval required |

**Packages removed due to `SLOP` verdict:** none.

**Packages flagged as suspicious `SUS`:** all Python packages because PyPI download evidence is unavailable to the GSD adapter; the npm rows explicitly marked `SUS` because of release age or unavailable download evidence. The planner must place a blocking human-verification checkpoint before the grouped backend and frontend installs. Approval of the dependency setup in `01-SPEC.md` may satisfy those checkpoints only when the approval explicitly acknowledges this audit.

## Architecture Patterns

### System Architecture Diagram

```text
Browser SPA
  -> generated API client
  -> FastAPI /api/v1 endpoints
      -> auth dependencies and role checks
      -> SQLAlchemy session
      -> PostgreSQL
      -> Celery enqueue endpoint or service
          -> Redis broker/result backend
          -> Celery worker
Docker Compose
  -> frontend, backend, worker, postgres, redis
  -> dev/staging/prod overlays and smoke commands
```

### Recommended Project Structure

```text
.
├── backend/
│   ├── .python-version
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── src/verboflex/
│   │   ├── main.py
│   │   ├── core/config.py
│   │   ├── db/base.py
│   │   ├── db/session.py
│   │   ├── models/
│   │   ├── api/v1/
│   │   ├── auth/
│   │   ├── worker/celery_app.py
│   │   └── scripts/export_openapi.py
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── api/client/
│   │   ├── components/ui/
│   │   ├── components/layout/
│   │   ├── features/auth/
│   │   ├── pages/Dashboard.tsx
│   │   └── main.tsx
│   └── tests/
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── docker-compose.staging.yml
├── docker-compose.prod.yml
├── .env.example
└── docs/phase-01-smoke.md
```

### Pattern 1: Backend Settings

Use `pydantic-settings` with explicit env names and safe defaults only for local development. Required production/staging values should be absent from `.env.example` or set to obvious placeholders. [CITED: https://fastapi.tiangolo.com/advanced/settings/]

Required settings for Phase 1:
- `APP_ENV=local|staging|production`
- `DATABASE_URL=postgresql+psycopg://verboflex:verboflex@postgres:5432/verboflex`
- `REDIS_URL=redis://redis:6379/0`
- `JWT_SECRET_KEY=<replace-me>`
- `JWT_ALGORITHM=HS256`
- `ACCESS_TOKEN_EXPIRE_MINUTES=15`
- `REFRESH_TOKEN_EXPIRE_DAYS=7`
- `CORS_ORIGINS=http://localhost:5173`

### Pattern 2: OAuth2 Password Flow with Refresh Session

Use FastAPI `OAuth2PasswordBearer` and `OAuth2PasswordRequestForm` for login. [CITED: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/] Issue:
- a 15-minute signed JWT access token returned in JSON as `{ "access_token": "...", "token_type": "bearer" }`
- a 7-day opaque refresh token stored server-side as a hash in `auth_sessions` and delivered as `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/api/v1/auth`
- refresh-token rotation on every refresh
- logout that revokes the current refresh session

The frontend must store the access token in memory only. It must not use `localStorage` or `sessionStorage` for tokens. On reload, it may call `/api/v1/auth/refresh` to receive a new access token if the refresh cookie is valid.

### Pattern 3: Role Model

Create a simple internal role model in Phase 1:
- `users`: `id`, `email`, `display_name`, `hashed_password`, `is_active`, `must_change_password`, `created_at`, `updated_at`
- `roles`: `id`, `name`, `created_at`
- `user_roles`: `user_id`, `role_id`
- initial roles: `admin`, `product_manager_reviewer`, `translator`, `viewer`
- protected `/api/v1/users/me` returns identity plus roles
- dependency shape: `require_roles("admin")`, `require_roles("admin", "product_manager_reviewer")`
- a CLI bootstrap command creates the first admin without shipping default credentials
- administrative password reset sets `must_change_password` and revokes existing refresh sessions

This satisfies AUTH-04 and creates the enforcement path future phases will reuse.

### Pattern 4: Generated OpenAPI Client

Add a backend script that imports the FastAPI app and writes `openapi.json`. Then run Hey API generation from the frontend. The generated files should live under `frontend/src/api/client/` and be treated as generated output. Use an npm script that fails if regeneration changes tracked files during CI/smoke checks.

Recommended scripts:

```json
{
  "scripts": {
    "api:schema": "cd ../backend && uv run python -m verboflex.scripts.export_openapi > ../frontend/openapi.json",
    "api:generate": "openapi-ts",
    "api:check": "npm run api:schema && npm run api:generate && git diff --exit-code -- src/api/client openapi.json"
  }
}
```

### Pattern 5: Docker Compose Overlays

Use `docker-compose.yml` for shared services and `docker-compose.staging.yml` / `docker-compose.prod.yml` for environment-specific overrides. Docker documents multiple compose files for layered configuration. [CITED: https://docs.docker.com/compose/how-tos/multiple-compose-files/] Include service healthchecks for Postgres, Redis, backend, and frontend because Docker Compose supports service healthcheck declarations. [CITED: https://docs.docker.com/reference/compose-file/services/#healthcheck]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom salting/hash code | `pwdlib[argon2]` | FastAPI docs recommend secure password hashing and Argon2 support. |
| JWT implementation | Manual base64/signature parsing | PyJWT | JWT verification has expiry and signature edge cases. |
| API client | Hand-written fetch wrappers per endpoint | `@hey-api/openapi-ts` | User locked generated OpenAPI client; generated SDK catches schema drift. |
| Migrations | Manual SQL files without version metadata | Alembic | Alembic tracks database revisions and integrates with SQLAlchemy metadata. |
| Background job runner | Threads inside FastAPI process | Celery + Redis | Long-running imports/PR work must not run in HTTP handlers. |
| UI primitives | Custom button/input/dialog/table primitives | shadcn/ui components | User selected shadcn/ui; installed components are project-owned and accessible. |

## Common Pitfalls

### Pitfall 1: Treating Frontend Controls as Authorization
**What goes wrong:** Hidden buttons become the only protection.  
**Why it happens:** Early scaffolds implement route guards before API dependencies.  
**How to avoid:** Build `get_current_user()` and `require_roles()` dependencies in Phase 1 and use them on protected sample endpoints.  
**Warning signs:** Tests only assert UI state and no backend 401/403 behavior.

### Pitfall 2: Token Persistence in Browser Storage
**What goes wrong:** Access tokens stored in `localStorage` are exposed to XSS.  
**Why it happens:** SPA examples often persist tokens for convenience.  
**How to avoid:** Store access token in memory; use an `HttpOnly` refresh cookie with rotation and revocation.  
**Warning signs:** `localStorage.setItem("token"` or `sessionStorage.setItem("token"` exists in frontend code.

### Pitfall 3: OpenAPI Client Drift
**What goes wrong:** Frontend compiles against stale generated code.  
**Why it happens:** OpenAPI export and client generation are manual and untested.  
**How to avoid:** Add `api:schema`, `api:generate`, and `api:check` scripts in Phase 1.  
**Warning signs:** Backend endpoint changes do not produce frontend diffs.

### Pitfall 4: Alembic Not Wired to SQLAlchemy Metadata
**What goes wrong:** `alembic revision --autogenerate` misses models.  
**Why it happens:** `env.py` does not import `Base.metadata` and all model modules.  
**How to avoid:** Create `db/base.py` and import model modules before setting `target_metadata`.  
**Warning signs:** Initial migration does not create `users`, `roles`, `user_roles`, or `auth_sessions`.

### Pitfall 5: One Container Running API and Worker Together
**What goes wrong:** Worker lifecycle, scaling, and health checks become tied to the API process.  
**Why it happens:** Initial Dockerfile starts multiple processes.  
**How to avoid:** Use one backend image but separate `backend` and `worker` services with different commands. FastAPI Docker docs describe one process per container as the normal deployment model. [CITED: https://fastapi.tiangolo.com/deployment/docker/]

## Code Examples

### Backend Access Token Shape

```python
# Source: FastAPI OAuth2 JWT docs
class Token(BaseModel):
    access_token: str
    token_type: str
```

### Hey API Runtime Client Config

```ts
// Source: Hey API Fetch client docs
import type { CreateClientConfig } from "./client/client.gen";

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: import.meta.env.VITE_API_BASE_URL,
});
```

## State of the Art

| Old Approach | Current Approach | Evidence | Impact |
|--------------|------------------|----------|--------|
| FastAPI examples using `passlib` by default | FastAPI OAuth2 JWT docs currently show PyJWT and `pwdlib` with Argon2 | [CITED: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/] | Prefer `pwdlib[argon2]` for Phase 1 password hashing. |
| Handwritten TypeScript clients | Generate SDK/client from OpenAPI | [CITED: https://fastapi.tiangolo.com/advanced/generate-clients/] [CITED: https://heyapi.dev/openapi-ts/get-started] | Add generation scripts before real endpoints grow. |
| Single compose file for every environment | Base compose plus overrides | [CITED: https://docs.docker.com/compose/how-tos/multiple-compose-files/] | Create staging/prod overlays in Phase 1. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The first execution will allow adding uv-managed backend files and npm-managed frontend files rather than requiring a different internal package policy. | Summary / Standard Stack | Low; user already selected the language/framework stack and local uv/npm are available. |

## Resolved Scope Decisions

1. **Deployment target:** Docker Compose local plus staging- and production-oriented overlays are sufficient for Phase 1. A cloud/provider-specific hosting target remains undecided and out of scope; no provider adapter is required by this phase.
2. **Identity provider:** Internal corporate-email/password authentication is the Phase 1 implementation. Microsoft Entra ID and other external OAuth2/OIDC providers are deferred to ENT-01; PostgreSQL role mapping remains provider-independent.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Backend | YES | 3.14.7 selected/available via uv; bare `python3` is 3.9.6 | Docker Python image |
| uv | Backend dependency management | YES | 0.11.12 | pip + requirements, not recommended |
| Node | Frontend | YES | v24.15.0 | Docker Node image |
| npm | Frontend dependencies/scripts | YES | 11.16.0 | Docker Node image |
| Docker | Run/deploy baseline | YES | 29.7.2 | None for Phase 1 smoke |
| Docker Compose | Multi-service smoke | YES | 5.3.1 | None for Phase 1 smoke |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Backend: pytest 9.1.1 observed; Frontend: Vitest 4.1.11 observed; Smoke: Docker Compose 5.3.1 |
| Config file | Backend: `backend/pyproject.toml`; Frontend: `frontend/vite.config.ts`; Docker: `docker-compose.yml` |
| Quick run command | `cd backend && uv run pytest -q` and `cd frontend && npm run test -- --run` |
| Full suite command | `cd backend && uv run pytest -q && cd ../frontend && npm run test -- --run && npm run build && cd .. && docker compose up -d --build && docker compose ps` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| PLAT-01 | Separate `frontend/` and `backend/` apps exist with independent package files | file/assertion | `test -f backend/pyproject.toml && test -f frontend/package.json` | NO - Wave 0 |
| PLAT-02 | React/Vite/TypeScript app renders shell and has shadcn/ui components | frontend unit/build | `cd frontend && npm run test -- --run && npm run build` | NO - Wave 0 |
| PLAT-03 | FastAPI exposes `/api/v1/health` and OpenAPI schema | backend API | `cd backend && uv run pytest tests/api/test_health.py -q` | NO - Wave 0 |
| PLAT-04 | SQLAlchemy connects to PostgreSQL settings and session dependency | backend unit/integration | `cd backend && uv run pytest tests/db/test_session.py -q` | NO - Wave 0 |
| PLAT-05 | Alembic upgrades initial schema | migration/smoke | `docker compose run --rm backend uv run alembic upgrade head` | NO - Wave 0 |
| PLAT-06 | Celery worker executes sample task through Redis | integration/smoke | `cd backend && uv run pytest tests/worker/test_smoke_task.py -q` | NO - Wave 0 |
| AUTH-01 | Login, access/refresh/logout, forced password change, and protected identity enforce the approved authority model | backend API/security | `cd backend && uv run pytest tests/auth/test_access_tokens.py tests/auth/test_login.py tests/auth/test_refresh.py tests/auth/test_logout.py tests/auth/test_password_change.py tests/api/test_me.py -q` | NO - Wave 0 |
| AUTH-04 | Roles `admin`, `product_manager_reviewer`, `translator`, `viewer` exist and can attach to users | backend model/API | `cd backend && uv run pytest tests/auth/test_roles.py -q` | NO - Wave 0 |
| UI-01 | shadcn/ui primitives are installed and imported by app shell | frontend unit/build | `cd frontend && npm run test -- --run && npm run build` | NO - Wave 0 |

### Sampling Rate

- **Per task commit:** Run the quick command for the touched tier.
- **Per wave merge:** Run backend pytest, frontend Vitest/build, and relevant Docker Compose smoke.
- **Phase gate:** Full suite green plus documented `docs/phase-01-smoke.md` before `$gsd-verify-work`.

### Wave 0 Gaps

- [ ] `backend/tests/` with pytest config and initial API/auth/db/worker tests.
- [ ] `frontend/src/**/*.test.tsx` or `frontend/tests/` with Vitest and Testing Library.
- [ ] `docker-compose.yml` plus staging/prod overlays and smoke documentation.
- [ ] Generated OpenAPI client drift check script.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | FastAPI OAuth2 password flow, `pwdlib[argon2]`, inactive-user checks |
| V3 Session Management | yes | Short-lived access JWT, opaque rotated refresh token, server-side session revocation, secure cookie attributes |
| V4 Access Control | yes | FastAPI dependencies enforcing role requirements server-side |
| V5 Input Validation | yes | Pydantic request/response models and typed settings |
| V6 Cryptography | yes | PyJWT for token signing; no custom crypto; generated secrets from environment |
| V10 API | yes | OpenAPI schema generation, explicit 401/403 tests, CORS config |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stolen browser token via XSS | Information Disclosure | Keep access token in memory only; no `localStorage`/`sessionStorage`; short TTL. |
| Refresh token replay | Spoofing | Store only hashed opaque refresh token; rotate on use; revoke on logout. |
| CSRF on refresh endpoint | Spoofing | `SameSite=Lax`, path-limited refresh cookie, Origin/Referer validation for state-changing auth endpoints. |
| Unauthorized role escalation | Elevation of Privilege | Role changes not implemented in Phase 1; protected endpoints use backend role dependencies. |
| SQL injection | Tampering | SQLAlchemy bound parameters and Pydantic validated input. |
| Secret leakage in Docker/env files | Information Disclosure | `.env.example` placeholders only; real `.env` ignored; production/staging require explicit `JWT_SECRET_KEY`. |

## Sources

### Primary (HIGH confidence)

- https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ - FastAPI OAuth2 password flow, JWT, PyJWT, and password hashing pattern.
- https://fastapi.tiangolo.com/tutorial/sql-databases/ - FastAPI relational database patterns.
- https://fastapi.tiangolo.com/advanced/generate-clients/ - FastAPI OpenAPI SDK generation guidance.
- https://fastapi.tiangolo.com/deployment/docker/ - FastAPI container deployment guidance.
- https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html - Celery Redis broker/result backend.
- https://alembic.sqlalchemy.org/en/latest/tutorial.html - Alembic migration setup.
- https://ui.shadcn.com/docs/installation/vite - shadcn/ui Vite installation.
- https://vite.dev/guide/ - Vite React/TypeScript setup.
- https://docs.docker.com/compose/how-tos/multiple-compose-files/ - Compose overlays.
- https://docs.docker.com/reference/compose-file/services/#healthcheck - Compose healthchecks.
- https://docs.astral.sh/uv/guides/projects/ - uv project structure and lockfile.
- https://docs.astral.sh/uv/guides/integration/docker/ - uv with Docker.
- https://heyapi.dev/openapi-ts/get-started - Hey API OpenAPI TypeScript generation.
- https://heyapi.dev/openapi-ts/clients/fetch - Generated fetch client configuration.
- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html - OWASP session/cookie guidance.
- https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html - OWASP OAuth2 guidance.
- https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html - OWASP JWT caveats and storage risks.
- https://docs.pytest.org/en/stable/getting-started.html - pytest usage.
- https://vitest.dev/guide/ - Vitest usage.

### Version Checks

Current registry observations are maintained once in `## Package Legitimacy Audit`; project execution selects compatible versions and freezes them in `uv.lock` and `package-lock.json`. Local tools verified for planning: bare `python3` 3.9.6, uv-selected Python 3.14.7, uv 0.11.12, Node 24.15.0, npm 11.16.0, Docker 29.7.2, and Docker Compose 5.3.1.

### Secondary (MEDIUM confidence)

- None used.

### Tertiary (LOW confidence)

- None used.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - user selected the stack and current package versions were checked against npm/PyPI.
- Architecture: HIGH - split app, Docker Compose, FastAPI, Alembic, Celery, and generated OpenAPI client are directly supported by official docs.
- Security: MEDIUM-HIGH - OWASP guidance is clear, but exact refresh-token implementation must be validated by tests during execution.
- UI foundation: MEDIUM-HIGH - shadcn/ui Vite setup is documented, but Phase 1 still needs a UI-SPEC before planning because the roadmap marks this as a UI phase.

**Research date:** 2026-05-05
**Valid until:** 2026-06-04 for stable architecture; package versions should be refreshed before implementation if more than 7 days pass.

## RESEARCH COMPLETE
