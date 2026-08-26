# Phase 1: Platform Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 1-Platform Foundation
**Areas discussed:** Auth session policy, Run and deploy baseline, First app shell, Frontend/API contract

---

## Auth Session Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Internal username/password OAuth2 token flow | Establish v1 internal users with OAuth2 bearer/JWT behavior. | ✓ |
| External OIDC first | Integrate an external identity provider immediately. | |
| Agent decides | Leave auth/session details to planning. | |

**User's choice:** Standard behavior documented in OWASP.
**Notes:** Interpreted as OWASP-aligned OAuth2/session handling: short-lived bearer/JWT access tokens, explicit expiry, refresh/session strategy, secure token storage, no localStorage token persistence, secure cookie attributes where cookies are used, backend role checks, and future OIDC compatibility without implementing external identity in Phase 1.

---

## Run and Deploy Baseline

| Option | Description | Selected |
|--------|-------------|----------|
| Docker Compose only | Local-only verification. | |
| Production-like Docker build | Container build without explicit environment split. | |
| Staging and production Docker baseline | Dockerized app with staging and production-oriented configuration targets. | ✓ |

**User's choice:** Use Docker; have production and staging.
**Notes:** Phase 1 smoke verification should prove frontend, backend, PostgreSQL, Redis, Celery, and Alembic migrations work through the Dockerized baseline.

---

## First App Shell

| Option | Description | Selected |
|--------|-------------|----------|
| Admin setup first | Send users directly to setup/configuration. | |
| Review dashboard first | Send users directly to translation review. | |
| Neutral landing dashboard | Start with a general dashboard that later adapts by user role/context. | ✓ |

**User's choice:** Neutral landing dashboard, maybe customizable based on the logged-in user's use.
**Notes:** Phase 1 should build the shell and empty states, not Phase 2+ admin or review capabilities.

---

## Frontend/API Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Generated OpenAPI client | Generate the frontend API client from FastAPI's OpenAPI schema. | ✓ |
| Hand-written API client | Maintain the frontend API wrapper manually. | |
| Agent decides | Leave client strategy to planning. | |

**User's choice:** Generated OpenAPI client.
**Notes:** The OpenAPI schema should be treated as the contract between frontend and backend from Phase 1.

---

## the agent's Discretion

- Exact package/module layout.
- Exact OpenAPI client generator.
- Concrete token lifetime values and rotation mechanics, as long as they follow OWASP-aligned behavior.
- Docker file and environment-file organization.

## Deferred Ideas

None.
