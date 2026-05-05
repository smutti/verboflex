# Phase 1: Platform Foundation - Research

**Researched:** 2026-05-05
**Domain:** Split web application foundation, OAuth2/JWT auth, Dockerized FastAPI/React stack
**Confidence:** HIGH

## User Constraints

- **D-01:** Use OWASP-aligned OAuth2 behavior for Phase 1 rather than inventing a custom session model.
- **D-02:** Establish an internal username/password OAuth2 token flow for v1, with a clean boundary for future external OAuth2/OIDC identity provider integration.
- **D-03:** Use short-lived bearer/JWT access tokens with explicit expiry.
- **D-04:** Include a refresh/session strategy in the design; downstream planning should choose concrete lifetimes and rotation behavior from OWASP guidance.
- **D-05:** Do not persist auth tokens in browser `localStorage`.
- **D-06:** Where cookies are used, require secure cookie attributes such as `HttpOnly`, `Secure`, and `SameSite` as appropriate to the deployment.
- **D-07:** Backend role checks must be enforced on protected API endpoints; frontend hiding/disabling controls is not sufficient authorization.
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

Use uv for backend dependency locking and execution because it is available locally and its project model gives `pyproject.toml`, `.python-version`, and `uv.lock` as reproducible inputs. [VERIFIED: `uv --version` -> 0.10.3] [CITED: https://docs.astral.sh/uv/guides/projects/] Use npm for the frontend because Node and npm are available locally and shadcn/ui documents Vite setup through npm-compatible commands. [VERIFIED: `node --version` -> v24.3.0, `npm --version` -> 11.4.2] [CITED: https://ui.shadcn.com/docs/installation/vite]

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
| Python | 3.14.2 local | Backend runtime | Matches local runtime and current project stack. [VERIFIED: `python3 --version`] |
| uv | 0.10.3 local | Backend dependency/project management | Provides `pyproject.toml`, `.python-version`, `uv.lock`, and `uv run`. [CITED: https://docs.astral.sh/uv/guides/projects/] |
| FastAPI | 0.136.1 | HTTP API and OpenAPI | Official security, SQL, Docker, and SDK-generation docs fit this phase. [VERIFIED: PyPI] |
| SQLAlchemy | 2.0.49 | ORM | Standard pairing with Alembic and PostgreSQL. [VERIFIED: PyPI] |
| Alembic | 1.18.4 | Migrations | Official migration tool for SQLAlchemy. [VERIFIED: PyPI] |
| psycopg | 3.3.4 | PostgreSQL driver | Current PostgreSQL driver for SQLAlchemy connection URLs. [VERIFIED: PyPI] |
| Celery | 5.6.3 | Background worker | Celery officially documents Redis broker/result backend support. [CITED: https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html] |
| Redis Python client | 7.4.0 | Celery Redis support | Current redis-py package required by Celery Redis transport. [VERIFIED: PyPI] |
| React | 19.2.5 | SPA runtime | Project-selected frontend stack. [VERIFIED: npm registry] |
| Vite | 8.0.10 | Dev/build tooling | Official Vite docs include React TypeScript templates. [CITED: https://vite.dev/guide/] |
| TypeScript | 6.0.3 | Frontend type system | Required for generated client and React code. [VERIFIED: npm registry] |
| shadcn CLI | 4.7.0 | UI component installation | Current CLI for installing project-owned shadcn/ui components. [VERIFIED: npm registry] |
| Docker Compose | v2.38.2 local | Service orchestration | Required Docker baseline and multi-compose staging/prod overlays. [VERIFIED: `docker compose version`] |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| pydantic-settings | 2.14.0 | Environment settings | Use for typed backend config (`DATABASE_URL`, `REDIS_URL`, token TTLs, CORS, environment). |
| PyJWT | 2.12.1 | JWT signing/verification | Use for signed access tokens. FastAPI docs use PyJWT in JWT auth examples. [CITED: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/] |
| pwdlib[argon2] | 0.3.0 | Password hashing | FastAPI docs recommend `pwdlib` and Argon2 for password hashing. [CITED: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/] |
| python-multipart | 0.0.27 | OAuth2 form parsing | Required for `OAuth2PasswordRequestForm` form submissions. |
| pytest | 9.0.3 | Backend tests | FastAPI test client and service/unit test runner. [CITED: https://docs.pytest.org/en/stable/getting-started.html] |
| httpx | 0.28.1 | Test HTTP client | Used by FastAPI/Starlette testing patterns and direct API integration checks. |
| Vitest | 4.1.5 | Frontend tests | Vite-native test runner. [CITED: https://vitest.dev/guide/] |
| @testing-library/react | 16.3.2 | Component tests | Verify dashboard/auth shell behavior without browser E2E overhead. |
| @hey-api/openapi-ts | 0.97.1 | Generated API SDK/client | Generates TypeScript SDK/client from FastAPI OpenAPI; docs warn exact pinning because it is pre-1.0. [CITED: https://heyapi.dev/openapi-ts/get-started] |
| @hey-api/client-fetch | bundled/default plugin | Fetch API client | Use generated fetch client and runtime config for base URL/auth. [CITED: https://heyapi.dev/openapi-ts/clients/fetch] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| uv | pip + requirements.txt | Simpler but less reproducible; loses `uv.lock` and `uv run` consistency. |
| @hey-api/openapi-ts | openapi-typescript + openapi-fetch | Lighter type-only path, but user requested a generated client and Hey API generates SDK/client code. |
| JWT access + opaque refresh session | Long-lived JWT only | Simpler but weaker revocation/session control and worse fit for OWASP-aligned session behavior. |
| Docker Compose overlays | Separate unrelated compose files | Overlays let staging/prod reuse base service definitions and reduce drift. |

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
- a 7-day opaque refresh token stored server-side as a hash in `auth_sessions` and delivered as `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/api/v1/auth/refresh`
- refresh-token rotation on every refresh
- logout that revokes the current refresh session

The frontend must store the access token in memory only. It must not use `localStorage` or `sessionStorage` for tokens. On reload, it may call `/api/v1/auth/refresh` to receive a new access token if the refresh cookie is valid.

### Pattern 3: Role Model

Create a simple internal role model in Phase 1:
- `users`: `id`, `email`, `display_name`, `hashed_password`, `is_active`, `created_at`, `updated_at`
- `roles`: `id`, `name`, `created_at`
- `user_roles`: `user_id`, `role_id`
- initial roles: `admin`, `product_manager`, `translator`, `viewer`
- protected `/api/v1/users/me` returns identity plus roles
- dependency shape: `require_roles("admin")`, `require_roles("admin", "product_manager")`

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

## Open Questions

1. **Final hosting target**
   - What we know: Docker, staging, and production-oriented configs are required now.
   - What's unclear: The eventual platform for staging/production deployment is not specified.
   - Recommendation: Phase 1 should provide Docker Compose staging/prod overlays and smoke commands, not cloud-provider-specific deployment.

2. **External identity provider**
   - What we know: v1 uses internal users with OAuth2 bearer-token authentication; external OIDC is deferred.
   - What's unclear: Future provider details.
   - Recommendation: Keep auth services behind interfaces and preserve internal role mapping in PostgreSQL.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Backend | YES | 3.14.2 | Docker Python image |
| uv | Backend dependency management | YES | 0.10.3 | pip + requirements, not recommended |
| Node | Frontend | YES | v24.3.0 | Docker Node image |
| npm | Frontend dependencies/scripts | YES | 11.4.2 | Docker Node image |
| Docker | Run/deploy baseline | YES | 28.3.2 | None for Phase 1 smoke |
| Docker Compose | Multi-service smoke | YES | v2.38.2 | None for Phase 1 smoke |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Backend: pytest 9.0.3; Frontend: Vitest 4.1.5; Smoke: Docker Compose v2.38.2 |
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
| AUTH-01 | OAuth2 token endpoint returns bearer token and protected endpoint requires it | backend API/security | `cd backend && uv run pytest tests/auth/test_tokens.py -q` | NO - Wave 0 |
| AUTH-04 | Roles `admin`, `product_manager`, `translator`, `viewer` exist and can attach to users | backend model/API | `cd backend && uv run pytest tests/auth/test_roles.py -q` | NO - Wave 0 |
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

- `npm view vite version` -> 8.0.10
- `npm view react version` -> 19.2.5
- `npm view typescript version` -> 6.0.3
- `npm view shadcn version` -> 4.7.0
- `npm view @hey-api/openapi-ts version` -> 0.97.1
- `npm view vitest version` -> 4.1.5
- `npm view @testing-library/react version` -> 16.3.2
- `python3 -m pip index versions fastapi` -> 0.136.1
- `python3 -m pip index versions celery` -> 5.6.3
- `python3 -m pip index versions alembic` -> 1.18.4
- `python3 -m pip index versions sqlalchemy` -> 2.0.49
- `python3 -m pip index versions psycopg` -> 3.3.4
- `python3 -m pip index versions redis` -> 7.4.0
- `python3 -m pip index versions pydantic-settings` -> 2.14.0
- `python3 -m pip index versions pyjwt` -> 2.12.1
- `python3 -m pip index versions pwdlib` -> 0.3.0
- `python3 -m pip index versions python-multipart` -> 0.0.27
- `python3 -m pip index versions pytest` -> 9.0.3
- `python3 -m pip index versions httpx` -> 0.28.1

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

