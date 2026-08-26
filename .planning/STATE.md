---
gsd_state_version: 1.0
current_phase: 2
current_phase_name: Admin Configuration
status: planning
stopped_at: Phase 01 complete, ready to plan Phase 2
last_updated: "2026-08-26T08:05:05.601Z"
last_activity: 2026-08-26
last_activity_desc: Phase 01 complete, transitioned to Phase 2
state_head: 7b33e59bd719ee257ed34a28833bfc2ced53a50e
progress:
  total_phases: 9
  completed_phases: 1
  total_plans: 15
  completed_plans: 15
  percent: 11
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-24)

**Core value:** Product teams can quickly find, review, constrain, modify, comment on, and approve translations, then send approved changes back through the standard Bitbucket Cloud pull request workflow.
**Current focus:** Phase 02 — Admin Configuration

## Current Position

Phase: 2 — Admin Configuration
Plan: Not started
Status: Ready to plan
Last activity: 2026-08-26 — Phase 01 complete, transitioned to Phase 2

Progress: [█░░░░░░░░░] 11%

## Performance Metrics

**Velocity:**

- Total plans completed: 15
- Average duration: 1h58min
- Total execution time: 29.4 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Platform Foundation | 15/15 | 29.4h | 1h58min |

**Recent Trend:**

- Last 5 plans: none
- Trend: N/A

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 1 min | 2 tasks | 1 files |
| Phase 01 P02 | 18 min | 2 tasks | 20 files |
| Phase 01 P03 | 51 min | 2 tasks | 32 files |
| Phase 01 P04 | 24 min | 2 tasks | 9 files |
| Phase 01 P05 | 29 min | 2 tasks | 19 files |
| Phase 01 P06 | 38 min | 3 tasks | 10 files |
| Phase 01 P07 | 33 min | 3 tasks | 12 files |
| Phase 01 P08 | 33min | 3 tasks | 13 files |
| Phase 01 P09 | 19min | 2 tasks | 17 files |
| Phase 01 P10 | 31min | 2 tasks | 26 files |
| Phase 01 P11 | 8min | 2 tasks | 3 files |
| Phase 01 P12 | 24min | 2 tasks | 12 files |
| Phase 01 P13 | 35min | 2 tasks | 18 files |
| Phase 01 P14 | 4h45min | 3 tasks | 64 files |
| Phase 01 P15 | 18h56min | 2 tasks | 35 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- V1 targets Bitbucket Cloud only.
- Frontend and backend are separate applications.
- Frontend uses React, Vite, TypeScript, and shadcn/ui.
- Backend uses Python, FastAPI, OAuth2, PostgreSQL, SQLAlchemy, and Alembic.
- V1 authentication uses internal accounts with corporate email as the unique login identifier and password credentials managed by VerboFlex.
- The first admin is created through a CLI bootstrap command; password reset is admin-managed and requires a password change on first login.
- Microsoft Entra ID/OIDC authentication remains a future integration; the internal role model must stay provider-independent.
- Background work uses Celery and Redis.
- V1 supports Android XML, Qt `.ts`, JSON, and iOS `.strings`.
- V1 uses simple draft/approved/rejected review states and per-translation comments.
- Every phase closes with tests, code review, and deploy/build smoke verification.
- Figma, extra validators, external identity, and complex approval gates are deferred.
- [Phase 01]: Phase 1 dependency installs are limited to the explicitly approved SPEC allowlists; any unexpected direct dependency requires a visible SPEC revision.
- [Phase 01]: Use uv_build 0.11.12 as the sole bounded PEP 517 backend for the installable src layout.
- [Phase 01]: Pin approved redis-py to 6.4.0, the newest release compatible with Celery and Kombu's redis<6.5 bound.
- [Phase 01]: Keep every non-health Phase 1 API route as a final-signature callable 501 seam until its dedicated TDD plan.
- [Phase 01]: Exact-pin TypeScript 6.0.3 for compatibility with the approved generated-client toolchain.
- [Phase 01]: Patch the generator graph through a js-yaml 4.3.1 transitive override while preserving the direct dependency allowlist.
- [Phase 01]: Keep generated client configuration in src/api/config.ts with same-origin fallback and included credentials.
- [Phase 01]: Typed deployed settings reject missing, sentinel, or sub-32-byte signing material and insecure refresh cookies; CORS accepts exact origins only.
- [Phase 01]: API and worker share one backend image but run distinct one-process commands and health checks; named overlays stay provider-neutral and fail closed.
- [Phase 01]: Corporate-email normalization trims only the database-aligned ASCII whitespace set, lowercases, validates, and remains provider-independent.
- [Phase 01]: A PostgreSQL transaction advisory lock serializes the empty-user decision so concurrent bootstrap attempts leave exactly one admin.
- [Phase 01]: Administrative reset locks the selected user, rehashes the password, forces a password change, increments token_version, and revokes only that user's live sessions in one transaction.
- [Phase 01]: Passwords enter the CLI only through getpass or stdin; argv, defaults, logs, and plaintext persistence are forbidden.
- [Phase 01]: JWT authority uses explicit HS256, required claims, a five-second tolerance, and exact purpose-specific lifetimes.
- [Phase 01]: Login rate limiting is Redis-authoritative before lookup and Argon2 and fails closed with 503.
- [Phase 01]: Protected authority always reconciles active state, token_version, sessions, password policy, and roles with PostgreSQL.
- [Phase 01]: Refresh plaintext uses 32 random bytes, is never persisted, and is exposed only through the scoped HttpOnly cookie.
- [Phase 01]: Refresh credentials use 32 random bytes, are stored only as SHA-256 digests, and replay revokes the full session family. — Limits bearer exposure and turns predecessor reuse into durable theft containment.
- [Phase 01]: Cookie-authenticated mutations enforce exact Origin before Redis and PostgreSQL; absent Origin remains valid for non-browser clients. — Prevents ambient-cookie CSRF without excluding CLI or service callers.
- [Phase 01]: Logout remains available during Redis outage, while refresh and password change fail closed before expensive or durable work. — Users can always shed authority without weakening authority replacement endpoints.
- [Phase 01]: Successful password replacement advances token_version, revokes every current-user session, clears the refresh cookie, and requires a fresh login. — No authority issued under the old credential survives or is silently replaced.
- [Phase 01]: Health uses bounded local limiting; ordinary reads use Redis with bounded local outage fallback; sensitive auth actions remain Redis fail-closed. — Preserves diagnostic availability without weakening credential or authority mutation boundaries.
- [Phase 01]: Limiter identity uses normalized server authority or the validated server-observed peer and never trusts forwarded headers implicitly. — Prevents callers from rotating keys through spoofed proxy headers before an explicit trusted-proxy policy exists.
- [Phase 01]: Service status projects only approved enums through independently timeout-bounded database, Redis, and worker probes. — Keeps operations useful without leaking addresses, credentials, exceptions, stacks, task identifiers, or raw inspect output.
- [Phase 01]: Celery tasks are JSON-only, named, non-eager, and executed by a distinct Redis-backed worker process outside HTTP routes. — Establishes the reusable background-work boundary required by later import and pull-request phases.
- [Phase 01]: Freeze explicit stable operation IDs and regenerate only from canonical FastAPI OpenAPI.
- [Phase 01]: Browser authority is React-memory-only and async transitions are versioned so logout invalidates stale responses.
- [Phase 01]: Guard credential persistence with narrow AST checks and fail-control fixtures.
- [Phase 01]: Use the current official shadcn 4.19.0 new-york-v4 Radix source with direct exact-pinned radix-ui and next-themes. — Matches the user's final modern-source approval while retaining the superseded conservative decision in append-only history.
- [Phase 01]: Limit Plan 01-10 registry ownership to thirteen approved UI primitives, components.json, utils.ts, and the official use-mobile hook. — Makes the 16-file supply-chain boundary mechanically auditable and excludes unrelated registry components.
- [Phase 01]: Use ESLint and @eslint/js 9.39.5 for the approved lint graph. — It is the newest exact version compatible with eslint-plugin-jsx-a11y 6.10.2 without forcing peer resolution.
- [Phase 01]: Keep official shadcn sources unchanged and enforce the approved visual contract through the global theme boundary.
- [Phase 01]: Defer next-themes provider integration until a selectable or dark theme is approved; the official Sonner fallback works without it.
- [Phase 01]: Route authority is a pure projection of SessionState; URLs, roles, and client-controlled values never grant access. — Keeps the backend-derived state machine authoritative for every direct navigation.
- [Phase 01]: Generated-client failures become sanitized rejected session actions so pages can announce one generic response without backend diagnostics. — Preserves non-enumerating UI feedback and retains the existing signed-out or restricted authority.
- [Phase 01]: Successful forced password replacement clears browser authority and returns to signed-out login. — Matches the backend contract that revokes old authority and requires fresh login.
- [Phase 01]: Render the ordinary shell only from generated authenticated identity, status, and logout operations; server roles remain authoritative. — Prevents client-created authority and keeps failures bounded.
- [Phase 01]: Use a fixed sidebar at 1024px and shadcn Sheet navigation below 1024px. — Matches the approved desktop versus tablet/mobile layout contract.
- [Phase 01]: Use a non-self-referential review digest plus a separate canonical digest that includes the CLOSED review artifact.
- [Phase 01]: Keep default gauntlet fail-closed on CLOSED/PASS and expose a distinct explicitly non-final post-fix candidate mode.
- [Phase 01]: Require every non-equivalent backend/frontend auth-session mutant killed with no score waiver or ignored mutation.
- [Phase 01]: Bind accepted secret-scan false positives to exact path, line, plugin, and hashed fingerprint.
- [Phase 01]: Retain VF-SEC-007 as visible Low dev-only debt requiring ship-time upgrade or time-bounded acceptance.
- [Phase 01]: Keep __Host-verboflex_refresh Secure in every environment; Microsoft Entra/OIDC remains deferred.
- [Phase 01]: Human-grade every material blind finding; behavioural remediation requires TDD, a new digest, the full gauntlet, and fresh verification.
- [Phase 01]: Accept exactly two equivalent backend join mutants only through exact mapping and identical PostgreSQL SQL proof; kill all 891 non-equivalent mutants.
- [Phase 01]: Use the explicitly authorized Round 3 exception after Round 2 remediation; no further verifier round is authorized.

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 3 must decide Bitbucket Cloud credential type and least-privilege scope model.
- Phase 4 must clarify JSON shape conventions and Qt `.ts` edit scope.
- Phase 8 must define exact allowed product-specific PR grouping options.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Design context | Figma screen linkage | v2 | Initialization |
| Validation | Placeholder/plural/forbidden-character/line-count constraints | v2 | Initialization |
| Identity | External OAuth2/OIDC provider integration | v2 | Initialization |
| Workflow | Per-product approval gates | v2 | Initialization |
| Repository provider | Bitbucket Server/Data Center | v2 | Initialization |

## Session Continuity

Last session: 2026-08-26T08:03:23.736Z
Stopped at: Phase 01 complete, ready to plan Phase 2
Resume file: None
