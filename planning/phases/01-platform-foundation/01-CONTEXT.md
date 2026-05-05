# Phase 1: Platform Foundation - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 establishes the runnable foundation for VerboFlex: separate frontend and backend applications, FastAPI backend scaffolding, OAuth2 authentication foundation, PostgreSQL with SQLAlchemy and Alembic, Redis/Celery background-job baseline, React/Vite/TypeScript frontend with shadcn/ui, and a phase quality gate that proves tests, code review, and deploy/build smoke verification can run.

This phase must not implement product/repository configuration, Bitbucket integration, localization parsers, search, translation review, comments, constraints, or pull request workflows beyond placeholders needed to prove the foundation is wired correctly.

</domain>

<decisions>
## Implementation Decisions

### Auth Session Policy
- **D-01:** Use OWASP-aligned OAuth2 behavior for Phase 1 rather than inventing a custom session model.
- **D-02:** Establish an internal username/password OAuth2 token flow for v1, with a clean boundary for future external OAuth2/OIDC identity provider integration.
- **D-03:** Use short-lived bearer/JWT access tokens with explicit expiry.
- **D-04:** Include a refresh/session strategy in the design; downstream planning should choose concrete lifetimes and rotation behavior from OWASP guidance.
- **D-05:** Do not persist auth tokens in browser `localStorage`.
- **D-06:** Where cookies are used, require secure cookie attributes such as `HttpOnly`, `Secure`, and `SameSite` as appropriate to the deployment.
- **D-07:** Backend role checks must be enforced on protected API endpoints; frontend hiding/disabling controls is not sufficient authorization.

### Run and Deploy Baseline
- **D-08:** Use Docker as the execution and deployment baseline.
- **D-09:** Provide staging and production-oriented configurations/environments from Phase 1, even if they initially run the same application slice.
- **D-10:** Phase 1 smoke verification must prove the Dockerized frontend, backend, PostgreSQL, Redis, Celery worker, and Alembic migrations can run.
- **D-11:** Deploy/build smoke verification should be command-driven and documented so later quality-gate plans can repeat it.

### First App Shell
- **D-12:** After login, show a neutral landing dashboard rather than forcing admin setup or review workflow first.
- **D-13:** Design the dashboard shell so later phases can customize visible content based on the logged-in user's roles, usage, or context.
- **D-14:** Keep the initial shell focused on navigation, identity/session status, and empty states for future modules; do not add Phase 2+ capabilities in Phase 1.

### Frontend/API Contract
- **D-15:** The React frontend should consume FastAPI through a generated OpenAPI client.
- **D-16:** The FastAPI OpenAPI schema becomes part of the frontend/backend contract from the foundation phase.
- **D-17:** Planning should include local commands that regenerate the client from the backend schema and fail visibly when the contract drifts.

### the agent's Discretion
- The agent may choose exact package/module layout, naming conventions, token lifetime values, OpenAPI client generator, and Docker file organization, provided the choices preserve the decisions above and remain easy to test locally.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/PROJECT.md` - Project constraints, stack decisions, deferred scope, and quality-gate requirement.
- `.planning/REQUIREMENTS.md` - Phase 1 requirement IDs: PLAT-01..PLAT-06, AUTH-01, AUTH-04, UI-01.
- `.planning/ROADMAP.md` - Phase 1 goal, success criteria, and plan structure.
- `.planning/STATE.md` - Current project state and active concerns.

### Research
- `.planning/research/SUMMARY.md` - Recommended phase ordering, stack summary, and Phase 1 research flags.
- `.planning/research/STACK.md` - Versioned stack choices: React/Vite/shadcn frontend, FastAPI backend, Celery/Redis, PostgreSQL, SQLAlchemy, Alembic.
- `.planning/research/ARCHITECTURE.md` - Separated frontend/backend architecture and project structure guidance.
- `.planning/research/PITFALLS.md` - Security, background-job, and write-back pitfalls to avoid.

### OWASP Auth and Session Guidance
- `https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html` - Authentication best practices and relationship to session management.
- `https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html` - Session ID handling, cookie attributes, and storage guidance.
- `https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html` - OAuth2 protocol and token replay prevention guidance.
- `https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html` - JWT caveats, explicit expiry, and token storage considerations.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet. The repository currently contains planning artifacts and `AGENTS.md`, not implementation code.

### Established Patterns
- Planning docs are local-only under `.planning/`.
- Root `AGENTS.md` carries the project stack, constraints, and GSD workflow guidance.
- Phase quality gates are now an explicit project and roadmap constraint.

### Integration Points
- New implementation should create the initial `frontend/` and `backend/` directories.
- Backend should expose OpenAPI early enough for the generated frontend client.
- Docker configuration should connect frontend, backend, PostgreSQL, Redis, Celery, and Alembic migration flow.

</code_context>

<specifics>
## Specific Ideas

- The first post-login experience should be a neutral dashboard that can later adapt to the logged-in user's role or usage.
- Staging and production should exist as named deployment/configuration targets from the foundation phase.
- The OpenAPI client should be generated, not hand-written.
- "Standard OWASP behavior" is a locked auth/security reference for Phase 1 planning.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Platform Foundation*
*Context gathered: 2026-05-05*
