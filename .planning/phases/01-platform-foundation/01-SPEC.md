# SPEC — Phase 1 Platform Foundation

- Status: approved by the user on 2026-08-24
- Tier: 3 — authentication, session security, database migrations, and a new HTTP/JSON contract
- Scope: internal, greenfield API; the resource model is sufficient for this phase (`users`, `roles`, `auth_sessions`, and bounded system status)
- Requirements: PLAT-01, PLAT-02, PLAT-03, PLAT-04, PLAT-05, PLAT-06, AUTH-01, AUTH-04, UI-01

## Outcome

Phase 1 delivers a Docker-first VerboFlex foundation with separate backend and frontend applications, internal corporate-email/password authentication, provider-independent roles, PostgreSQL migrations, Redis/Celery background execution, a generated OpenAPI client, and a neutral authenticated application shell.

The phase is complete only when the approved behaviors below have passed the full evidence gauntlet from one final source state. Implementation follows one-behavior-at-a-time RED -> GREEN -> REFACTOR cycles. For every new API behavior, the RED run must fail on an assertion against a callable stub, not merely fail during import or test collection.

## Setup plan

- Tools to install globally: none.
- Existing toolchain to use: Python 3.14 through `uv`, Node.js 24/npm 11, Docker Engine/Compose, Git.
- Dependency installation authorized after approval:
  - `uv sync --all-groups` inside `backend/`; exact resolved versions are committed in `backend/uv.lock`.
  - `npm install`/`npm ci` inside `frontend/`; exact resolved versions are committed in `frontend/package-lock.json`.
  - The shadcn CLI is invoked at an exact project-local version and may install only the direct component dependencies enumerated below. An unexpected direct dependency requires a visible SPEC revision before installation.
  - Approval of this SPEC explicitly acknowledges the `SUS` rows and conservative registry limitations documented in `01-RESEARCH.md` under `## Package Legitimacy Audit`; it authorizes the two grouped backend/frontend installs only after the executor rechecks package names, publishers/source links, compatibility, and lockfile resolution. No `SLOP`, missing, renamed, or unlisted direct package is authorized.
- Git:
  - keep planning on the current branch until this SPEC is approved;
  - after approval, create `codex/phase-1-platform-foundation` from the approved planning state;
  - commit this SPEC and the checked Phase 1 plans as the approval checkpoint;
  - use atomic plan/TDD-slice commits; never rewrite or discard unrelated user changes.
- Files the gauntlet will add:
  - `tools/gauntlet.sh` — single fresh-run entry point;
  - `tools/source_state.sh` — reproducible Git source-state verifier that fails on relevant dirty state;
  - `tools/source_manifest.txt` — canonical immutable source-set inclusion/exclusion contract used by the verifier;
  - `tools/real_smoke.sh` — Docker, migration, API, session, and Celery real-execution harness;
  - `tools/adversarial_auth.sh` — hostile-input and replay checks against the running stack;
  - `backend/tests/` and `frontend/src/**/*.test.tsx` — executable scenario mappings;
  - `backend/tests/integration/` — PostgreSQL/Redis migration and session-concurrency checks;
  - `frontend/e2e/` — browser smoke paths for login, forced password change, refresh, and logout;
  - `docs/phase-01-smoke.md` — repeatable operational smoke instructions;
  - `docs/reviews/phase-01-code-security.md` — persisted fresh-context code review and OWASP ASVS L1 findings/resolutions;
  - `docs/evidence/phase-01.md` — final evidence report.

### New backend runtime dependencies

| Dependency | Justification |
|---|---|
| `fastapi` | HTTP API, dependency injection, OpenAPI generation, and OAuth2 bearer integration. |
| `uvicorn[standard]` | Production-capable ASGI process for local and container execution. |
| `pydantic-settings` | Typed environment configuration with explicit environment validation. |
| `sqlalchemy` | Required ORM and transaction boundary for PostgreSQL data. |
| `alembic` | Versioned schema migrations and rollback rehearsal. |
| `psycopg[binary]` | PostgreSQL driver compatible with SQLAlchemy. |
| `celery[redis]` | Required background worker and Redis transport. |
| `redis` | Explicit Redis access for rate limits and service checks. |
| `PyJWT` | Standards-based signed access-token creation and verification. |
| `pwdlib[argon2]` | Argon2 password hashing without custom cryptography. |
| `python-multipart` | OAuth2 password-form parsing. |
| `email-validator` | Standards-aware validation of corporate email identifiers. |

The backend CLI uses Python standard-library `argparse` and `getpass`; no CLI framework is added.

### New backend build dependencies

| Dependency | Justification |
|---|---|
| `uv_build>=0.11.12,<0.12.0` | PEP 517 build backend required to install the approved `src/verboflex` package under `uv run`; the bound matches the installed uv 0.11.12 tool and prevents an unreviewed backend-minor upgrade. |

### New backend development dependencies

| Dependency | Justification |
|---|---|
| `pytest`, `pytest-cov`, `httpx` | Unit, contract, integration, and HTTP tests with branch coverage. |
| `mypy`, `ruff` | Static types, lint, import checks, and formatting. |
| `hypothesis` | Property-based validation of email normalization, passwords, tokens, and session state transitions. |
| `pytest-randomly` | Order-dependence and deterministic-seed checks. |
| `mutmut` | AST-based mutation testing of handwritten backend/auth logic. |
| `diff-cover` | Fail-closed changed-line coverage checks from Cobertura reports. |
| `pip-audit`, `pip-licenses` | Python vulnerability and license inventory. |
| `detect-secrets` | Repository secret scanning with a recorded negative control. |
| `radon` | Enforced complexity ceiling for handwritten Python. |

### New frontend runtime dependencies

| Dependency | Justification |
|---|---|
| `react`, `react-dom` | Project-selected SPA runtime. |
| `react-router-dom` | Explicit `/login`, `/change-password`, and authenticated-shell routing. |
| `react-hook-form`, `zod`, `@hookform/resolvers` | Accessible shadcn form state and executable client-side validation. |
| `lucide-react`, `class-variance-authority`, `clsx`, `tailwind-merge` | Standard shadcn component composition and icons. |
| `@radix-ui/react-slot`, `@radix-ui/react-label`, `@radix-ui/react-tooltip`, `@radix-ui/react-dropdown-menu`, `@radix-ui/react-separator`, `@radix-ui/react-dialog` | Accessible primitives used by the approved shadcn components. |
| `sonner` | Approved shadcn toast implementation for connection feedback. |

### New frontend development dependencies

| Dependency | Justification |
|---|---|
| `vite`, `@vitejs/plugin-react`, `typescript` | Project-selected build and type toolchain. |
| `@types/react`, `@types/react-dom` | Official DefinitelyTyped declarations required for the approved React/ReactDOM TypeScript scaffold; React does not bundle these declarations and Testing Library exposes them only as optional peers. |
| `tailwindcss`, `@tailwindcss/vite`, `tw-animate-css`, `shadcn` | Project-owned shadcn/Tailwind component generation and styles. |
| `@hey-api/openapi-ts` | Exact-version generated TypeScript client from FastAPI OpenAPI. |
| `vitest`, `@vitest/coverage-v8`, `jsdom` | Unit/component tests and machine-readable branch coverage. |
| `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom` | User-visible and accessible React behavior tests. |
| `eslint`, `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`, `eslint-plugin-jsx-a11y` | Static frontend correctness and accessibility checks. |
| `prettier` | Deterministic frontend formatting. |
| `@stryker-mutator/core`, `@stryker-mutator/vitest-runner` | Mutation testing of handwritten frontend session logic. |
| `fast-check` | Property-based tests for frontend session-state transitions. |
| `@playwright/test` | Real browser authentication and responsive-shell smoke tests. |

## HTTP/JSON contract

All endpoints use `/api/v1`. This is the version prefix already selected by the Phase 1 architecture research; Phase 1 adds no multi-version negotiation machinery.

### Common rules

- JSON fields use `snake_case`; timestamps are UTC RFC 3339 strings; identifiers are opaque UUID strings.
- Protected endpoints require `Authorization: Bearer <access-token>` over TLS outside local development.
- Access tokens are HS256 JWTs with `sub`, `exp`, `iat`, `purpose`, and `token_version`; ordinary tokens also carry `sid`. The configured signing secret must be at least 32 random bytes, and staging/production must refuse startup with a missing, placeholder, or short secret.
- Ordinary access tokens expire after 15 minutes. Password-change-only tokens expire after 5 minutes.
- Refresh tokens are 256-bit opaque random values. Only SHA-256 token hashes are stored. Ordinary refresh sessions expire after 7 days and rotate on every successful refresh.
- Refresh cookies are named `verboflex_refresh`, use `HttpOnly`, `SameSite=Lax`, `Path=/api/v1/auth`, and use `Secure` in staging/production. Local HTTP may explicitly disable only `Secure` through environment configuration.
- Cookie-authenticated requests reject a present `Origin` that is not in the configured exact-origin allowlist. CORS with credentials never uses `*`.
- Passwords accept Unicode and spaces, must contain 12-128 characters, must differ from the current password, and must not equal the normalized login email. Composition rules are not invented. Passwords are stored only as Argon2 hashes.
- Authentication failures never disclose whether an email exists, is inactive, or has a wrong password.
- A user's `token_version` is checked on every protected request. Password change, administrative reset, or deactivation increments it and revokes all refresh sessions. Logout revokes the current session.
- Rate limits are enforced before password verification or token rotation. Login is limited to 5 attempts/minute per normalized-email-and-IP key; refresh to 30/minute per session-and-IP key; password change/logout to 10/minute per authenticated user; ordinary protected reads to 120/minute per user; anonymous health to 60/minute per IP. `429` includes `Retry-After` and `X-RateLimit-Remaining`.
- Redis unavailability fails closed with `503` on login, refresh, and password change. Anonymous health and authenticated system status remain diagnosable through bounded process-local limits.

### Endpoints

| Method and path | Actor/action/resource | Request | Success | Defined errors |
|---|---|---|---|---|
| `GET /api/v1/health` | Anonymous read of public liveness | none | `200 {"status":"ok"}` | `429` rate limit |
| `POST /api/v1/auth/token` | Anonymous login creating own session | OAuth2 form: `username=<email>&password=<password>` | `200` with `access_token`, `token_type: "bearer"`, `expires_in`, `must_change_password`; normal login also rotates in a refresh cookie | `401 {"detail":"Invalid credentials"}`, `429`, `503` |
| `POST /api/v1/auth/refresh` | Cookie holder rotates own session | refresh cookie, empty body | `200` with ordinary access-token fields and a new refresh cookie | `401 {"detail":"Invalid refresh session"}`, `403 {"detail":"Origin not allowed"}`, `429`, `503` |
| `POST /api/v1/auth/logout` | Cookie holder revokes own current session | refresh cookie optional, empty body | idempotent `204`, always clears refresh cookie | `403` invalid origin, `429` |
| `POST /api/v1/auth/change-password` | Authenticated user changes own password | JSON `current_password`, `new_password` | `204`, revokes all sessions, invalidates access tokens, clears refresh cookie | `400 {"detail":"Current password is incorrect"}`, `401`, `422` password policy, `429`, `503` |
| `GET /api/v1/users/me` | Authenticated user reads own identity | bearer token | `200` with `id`, `email`, `display_name`, sorted `roles`, `must_change_password` | `401`, `403 {"detail":"Password change required"}`, `429` |
| `GET /api/v1/system/status` | Authenticated user reads bounded service status | bearer token | `200` with `api`, `database`, `redis`, `worker` enum values and `checked_at` | `401`, `403` password change required, `429` |

The role identifiers are exactly `admin`, `product_manager_reviewer`, `translator`, and `viewer`. The API returns role identifiers, while the UI presents human-readable labels.

### API gate resolution

| Gate | Decision before implementation |
|---|---|
| Boring | Pass by design: stable nouns, standard verbs/status codes, JSON except the standard OAuth2 form endpoint. |
| Compatibility | N/A: greenfield surface; OpenAPI drift becomes blocking after the first checked-in schema/client. |
| Authentication | Short-lived bearer JWT plus rotating, revocable opaque refresh session; no browser-persisted token. |
| Authorization | Server resolves the user/session; callers cannot submit roles, owner IDs, or user IDs. `is_active`, token version, password-change purpose, and role dependencies are server-enforced. |
| Idempotency | Health, identity, and status are reads; logout is idempotent. Change-password is a guarded target-state replacement and cannot apply twice. Login duplicates are low-stakes and capped; refresh replay is rejected and revokes the family rather than repeating an effect. No idempotency-key store is introduced in Phase 1. |
| Blast radius | Bounded payloads, no lists or fan-out jobs in HTTP, Redis-backed limits, headers on `429`, inactive-user killswitch. |
| Pagination | N/A: Phase 1 exposes no collection endpoint. |
| Expensive fields | Service probes live in their own bounded endpoint and use strict timeouts; `/users/me` remains constant-cost. |
| No implementation leakage | Clients see identity, roles, and stable service states, not table IDs, Redis keys, Celery task internals, or polling jobs. |

## Failure model and detecting layer

| Failure mode | Harm | Required detecting layer |
|---|---|---|
| Wrong, expired, tampered, or stale-version JWT is accepted | Unauthorized access | JWT contract/property tests, mutation testing, adversarial API smoke |
| Temporary-password user reaches normal resources | Bootstrap/reset credential bypass | Restricted-token endpoint tests and browser route tests |
| Refresh token is stored in plaintext, fails to rotate, or replay remains valid | Persistent session theft | Database invariant tests, rotation/replay concurrency tests on PostgreSQL, secret/state inspection |
| Logout, password change, reset, or deactivation leaves usable sessions | Continued unauthorized access | Revocation contract tests across access and refresh tokens |
| Login errors enumerate accounts | Targeted attack information | Parametrized response-equivalence tests and timing observation noted as a non-proof |
| Brute-force loop is unbounded | Credential attack and resource exhaustion | Rate-limit tests, hostile loop smoke, fail-closed Redis test |
| Cross-site origin can use refresh cookie | Session/CSRF abuse | Origin allowlist contract tests and browser smoke |
| Migration partially applies or cannot roll back on a clean database | Broken deployment or data loss risk | PostgreSQL upgrade -> downgrade -> upgrade rehearsal and schema assertions |
| API and generated frontend client drift | Runtime frontend failure | checked-in OpenAPI schema/client plus fail-on-diff command |
| API request runs background work inline | HTTP latency/resource exhaustion | Architecture test and real Celery worker smoke |
| Staging/production accepts placeholder secrets or insecure cookies | Deployable insecure configuration | settings tests and Compose configuration smoke |
| Frontend stores bearer/refresh tokens in Web Storage | XSS-amplified credential theft | frontend behavior tests plus lint AST restrictions with a proved negative control |
| Test checker passes without examining targets or compares a report that it creates itself | False evidence | immutable source-set manifest/digest plus negative controls for custom scripts, changed-line threshold, secret scan, and drift check |

## Scenarios

```gherkin
Feature: Runnable platform foundation
  Scenario: health endpoint is constant and non-sensitive
    Given the FastAPI application is running
    When GET /api/v1/health is requested without credentials
    Then the response is exactly 200 with JSON {"status":"ok"}
    And no database URL, Redis URL, secret, version, or environment value is returned

  Scenario: initial schema migrates and reverses on PostgreSQL
    Given an empty PostgreSQL database
    When Alembic runs upgrade head, downgrade base, and upgrade head
    Then each command exits zero
    And users, roles, user_roles, and auth_sessions exist after the final upgrade
    And the four exact role identifiers exist once each

  Scenario: first admin is bootstrapped without a default credential
    Given an empty migrated database and a password supplied interactively or through stdin
    When the bootstrap CLI receives admin@example.com and display name Admin User
    Then exactly one active admin user is created with normalized email admin@example.com
    And the password is stored as an Argon2 hash
    And must_change_password is true
    And no default password appears in source, logs, or example environment files

  Scenario: bootstrap cannot create a second first admin
    Given any user already exists
    When the first-admin bootstrap command is run again
    Then it exits non-zero with a non-secret diagnostic
    And no user or role assignment changes

Feature: Internal OAuth2 authentication
  Scenario: active user receives an ordinary session
    Given active user person@example.com has a non-temporary valid password
    When POST /api/v1/auth/token submits the exact email and password as OAuth2 form data
    Then the response is 200 with bearer token type, expires_in 900, and must_change_password false
    And the access token expires in 15 minutes within clock tolerance
    And a hashed seven-day refresh session is stored
    And the response sets the configured HttpOnly SameSite=Lax refresh cookie

  Scenario: corporate email identifiers normalize consistently
    Given a user is stored as person@example.com
    When login uses PERSON@EXAMPLE.COM with surrounding ASCII whitespace
    Then it resolves the same account and succeeds
    And property tests show normalization is idempotent for all accepted generated emails

  Scenario: invalid, unknown, and inactive credentials are indistinguishable
    Given one active account, one inactive account, and one unknown email
    When login is attempted with a wrong password, the unknown email, or the inactive account
    Then every response is exactly 401 with JSON {"detail":"Invalid credentials"}
    And every response includes WWW-Authenticate Bearer
    And no refresh session or cookie is created

  Scenario: bootstrapped or reset credentials receive only password-change access
    Given a valid user with must_change_password true
    When the temporary credential is submitted to POST /api/v1/auth/token
    Then the response is 200 with expires_in 300 and must_change_password true
    And no refresh cookie or refresh session is created
    And the token can call only POST /api/v1/auth/change-password
    And GET /api/v1/users/me returns 403 with JSON {"detail":"Password change required"}

  Scenario: required password change revokes all old authority
    Given a temporary-password user and a valid password-change token
    When POST /api/v1/auth/change-password submits the correct current password and New secure phrase 2026!
    Then the response is 204 and clears the refresh cookie
    And must_change_password becomes false
    And the Argon2 password hash changes
    And token_version increments and all refresh sessions are revoked
    And every previously issued access or refresh token is rejected
    And a fresh login with the new password receives an ordinary session

  Scenario: rejected password changes are atomic
    Given an authenticated user
    When the current password is wrong, or the new password is under 12 characters, over 128 characters, equal to the current password, or equal to the normalized email
    Then the API returns the defined 400 or 422 response
    And password hash, token_version, must_change_password, and sessions do not change

  Scenario: refresh rotates exactly once
    Given a valid ordinary refresh cookie and allowed Origin
    When POST /api/v1/auth/refresh is called
    Then the response is 200 with a new 15-minute access token and a different refresh cookie
    And the previous token hash is marked used
    And exactly one active successor exists in the same session family
    And no plaintext refresh token is stored

  Scenario: refresh replay revokes the session family
    Given a refresh token has already rotated successfully
    When the old token is submitted again, including by two concurrent requests
    Then no request creates more than one active successor
    And the response to replay is 401 with JSON {"detail":"Invalid refresh session"}
    And every token in that session family is revoked

  Scenario: logout is idempotent and revokes the current session
    Given a valid ordinary session
    When POST /api/v1/auth/logout is called twice
    Then both responses are 204 and clear the refresh cookie
    And the session is revoked after the first call
    And its access and refresh tokens can no longer reach protected resources

  Scenario: tampered, expired, stale, and wrong-purpose tokens are rejected
    Given signed tokens that are expired, signature-tampered, have a stale token_version, identify an inactive user, or have password_change purpose
    When each token calls a normal protected endpoint
    Then each response is 401 except password_change purpose which is 403 Password change required
    And no protected response body is disclosed

Feature: API authorization and incident controls
  Scenario: current identity returns provider-independent roles
    Given an active user has admin and translator roles
    When GET /api/v1/users/me is called with an ordinary token
    Then the response is 200 with the user's own opaque id, normalized email, display name, must_change_password false, and roles ["admin", "translator"]
    And no password hash, token version, session hash, or internal join identifier is returned

  Scenario: role dependencies deny a caller without an allowed role
    Given the reusable server-side role dependency allows admin only
    When it resolves a viewer principal and an admin principal
    Then the viewer is denied with 403 and the admin is allowed
    And changing a role claim client-side cannot grant access because roles are loaded from the database

  Scenario: login rate limit blocks a brute-force loop before verification
    Given Redis is available and no prior attempts exist for target@example.com and one client IP
    When six invalid login attempts occur within one minute
    Then the first five return 401 and the sixth returns 429 Rate limit exceeded
    And the sixth response includes positive Retry-After and X-RateLimit-Remaining 0
    And password verification is not called for the blocked attempt

  Scenario: security-sensitive auth fails closed when Redis is unavailable
    Given Redis is unavailable
    When login, refresh, or password change is attempted
    Then each response is 503 without validating credentials or mutating sessions
    And GET /api/v1/health remains bounded and returns its constant liveness response

  Scenario: untrusted origins cannot use cookie authentication
    Given a valid refresh cookie and allowed origins contain https://app.verboflex.example
    When refresh or logout includes Origin https://attacker.example
    Then the response is 403 with JSON {"detail":"Origin not allowed"}
    And the session does not rotate or revoke
    And no credentialed CORS wildcard is emitted

  Scenario: service status is bounded and does not leak implementation details
    Given an ordinary authenticated user and configured probe timeouts
    When GET /api/v1/system/status is called
    Then the response is 200 with api online and database, redis, worker each one of online, unavailable, or pending plus checked_at
    And no connection string, host, port, exception, task id, or stack trace is returned
    And each external probe obeys its configured timeout

Feature: Background execution
  Scenario: sample work executes outside the HTTP process
    Given PostgreSQL, Redis, backend, and Celery worker are running through Docker Compose
    When the documented smoke command queues the sample add job with 2 and 3
    Then a Celery worker returns exactly 5 within the smoke timeout
    And no FastAPI request handler executes the task body inline

Feature: Generated frontend contract and application shell
  Scenario: OpenAPI client is generated and drift is blocking
    Given the FastAPI application exposes the approved OpenAPI document
    When the frontend schema and client generation commands run twice
    Then the second run produces no tracked diff
    And changing a route or response schema without regenerating makes api:check exit non-zero

  Scenario: successful login reaches the neutral dashboard
    Given the login page is open and the backend accepts an ordinary user
    When the user submits a valid corporate email and password
    Then the UI calls the generated token client, keeps the access token in memory, loads /users/me, and navigates to /
    And the page shows Workspace overview, identity, role labels, service status, and the approved empty-state copy

  Scenario: temporary credentials force the password-change route
    Given login returns must_change_password true and a password-change-only access token
    When the response is handled by the SPA
    Then the user is routed to /change-password and cannot render the dashboard
    And a successful password change clears in-memory authority and returns the user to /login

  Scenario: browser reload restores only through the refresh cookie
    Given an ordinary session exists and the access token is held only in memory
    When the browser reloads the authenticated route
    Then the SPA calls /auth/refresh with credentials, stores only the returned access token in memory, calls /users/me, and renders the dashboard
    And localStorage and sessionStorage contain no access or refresh token

  Scenario: failed login and API outage are actionable and non-enumerating
    Given the login API returns invalid credentials or the API cannot be reached
    When the user submits the form or retries connectivity
    Then the UI shows the exact approved generic auth or API error copy
    And it never indicates whether the account exists or is inactive

  Scenario: application shell is accessible and responsive
    Given the login, password-change, loading, error, desktop dashboard, and mobile dashboard states
    When automated accessibility checks and keyboard/browser smoke tests run
    Then every input has a visible associated label, errors are announced without color alone, focus order is visible and logical, icon-only controls have labels and tooltips, and status has text
    And no approved viewport contains horizontal text overflow, nested cards, decorative hero content, or a radius over 8px

Feature: Deployable environments and evidence
  Scenario: staging and production configuration reject insecure defaults
    Given the staging or production Compose overlay
    When configuration is rendered with a missing, placeholder, or short JWT secret or with an insecure refresh cookie setting
    Then startup/config validation exits non-zero before serving requests
    And no real secret is committed to the repository

  Scenario: full Docker smoke proves the application slice
    Given clean locked dependencies and Docker Compose
    When tools/real_smoke.sh runs against the staging-oriented stack
    Then migrations complete, backend and frontend become healthy, the first admin is bootstrapped from stdin, login/change-password/login/refresh/me/logout work, and the Celery job returns 5
    And tools/gauntlet.sh passes against one immutable source-set digest
    And the evidence report is written only after the final pre-report digest comparison succeeds
```

## Edge Coverage

- Empty, malformed, non-email, overlong, mixed-case, and whitespace-padded login identifiers.
- Empty, Unicode, whitespace-containing, boundary-length, and overlong passwords.
- Duplicate emails under normalization and concurrent first-admin bootstrap attempts.
- Expiry boundaries and clock skew for both token purposes.
- Missing cookie, malformed cookie, expired session, used token, revoked family, concurrent refresh, and database transaction rollback.
- Missing, `null`, malformed, wildcard, allowed, and hostile `Origin`/CORS cases.
- Redis and PostgreSQL unavailable or slow; worker unavailable and probe timeout.
- Inactive users, users without roles, multi-role users, and client-forged role claims.
- Browser reload, failed refresh, double logout, double form submission, slow API, mobile navigation, and keyboard-only operation.
- Clean migration upgrade/downgrade/upgrade and generated-client drift negative controls.

## Must NOT

- Must not integrate Microsoft Entra ID/OIDC or create external-provider configuration in Phase 1.
- Must not implement products, repositories, Bitbucket operations, localization formats, search, review, comments, constraints, audit workflows, or pull requests.
- Must not store passwords, refresh tokens, Bitbucket-style secrets, or JWT signing keys in plaintext or source control.
- Must not persist access or refresh tokens in browser `localStorage`, `sessionStorage`, IndexedDB, URLs, logs, or analytics.
- Must not ship default credentials, accept a bootstrap password as a normal command-line argument, or echo a password read from stdin.
- Must not reveal account existence, inactive state, password hashes, session hashes, stack traces, connection details, or internal database identifiers through auth/API errors.
- Must not trust roles, user IDs, owners, token versions, or password-change flags supplied by a client.
- Must not allow a password-change-only token to call ordinary protected endpoints.
- Must not run Celery task bodies, migrations, or other long-running work inside HTTP handlers.
- Must not hand-write frontend API request/response types that duplicate the generated OpenAPI client.
- Must not use credentialed CORS wildcards or permit insecure staging/production refresh cookies.
- Must not weaken, skip, broaden, or edit an assertion together with implementation to obtain GREEN.
- Must not report a gauntlet layer as passed unless it ran against the final unchanged source state; unavailable or substituted layers remain explicit.

## Gauntlet and completion gate

The immutable source set is the sorted path/content set of Phase 1 implementation, tests, configuration, dependency lockfiles, database migrations, verifier scripts, and the closed `docs/reviews/phase-01-code-security.md` artifact. It excludes `docs/evidence/phase-01.md`, raw command logs, coverage/mutation reports, runtime data, caches, and build artifacts. `tools/source_manifest.txt` defines and tests those boundaries. Raw logs must be stored outside the source set.

Before the final signed gauntlet/evidence round, a genuinely fresh context must review the entire canonical source set for code correctness and applicable OWASP ASVS L1 controls, persist findings/dispositions/resolutions in `docs/reviews/phase-01-code-security.md`, and block while any critical/high finding remains. Every review-driven source fix follows TDD, invalidates the prior digest, and requires a recomputed digest plus a complete gauntlet rerun before review closure. The closed review artifact is then included in the final immutable source set. This review/revision gate is separate from, and precedes, independent Tier 3 verification.

For the final round, the initial digest is compared immediately after the gauntlet and before the evidence report is written; the report records that digest, and the independent verifier recomputes it from the same manifest.

The final `tools/gauntlet.sh` must fail closed and run, in order:

1. source-state cleanliness plus immutable manifest/category validation and initial digest;
2. backend full tests including PostgreSQL/Redis integration tests and randomized order;
3. frontend Vitest suite in shuffled order plus Playwright browser smoke;
4. mypy and TypeScript type checks;
5. Ruff, ESLint, Prettier, and complexity ceilings;
6. changed-line branch coverage at 100% for handwritten Phase 1 backend/frontend code, excluding generated OpenAPI code, migrations, shadcn-owned component source, and entrypoint-only wiring with an explicit mapping;
7. mutmut and Stryker mutation runs over handwritten auth/session/state logic, with every non-equivalent mutant killed; Hypothesis/fast-check property suites are rerun independently against relevant mutants;
8. Alembic PostgreSQL upgrade -> downgrade -> upgrade rehearsal;
9. OpenAPI generation drift check with a proved failing negative control;
10. `pip-audit`, `npm audit`, Python/npm license inventories, and `detect-secrets` with a proved failing negative control;
11. staging-oriented Docker real smoke and `tools/adversarial_auth.sh`;
12. final pre-report source-set digest comparison proving included source did not change during verification.

### Independent verification protocol

Independent verification is separate from the Plan 01-14 code/ASVS review and is not a gauntlet layer. Before claiming it was performed, the verifier must read `/Users/smutti/.codex/skills/old-coder/references/verifier.md` in full. Missing instructions, missing tooling, or inability to obtain a fresh context produces `blocked`, never a skip or pass.

The blind phase receives exactly four task-specific inputs:

1. the complete human-approved task contract: the original request plus every explicitly approved requirement, scope change, and SPEC revision, without surrounding builder discussion, reasoning, defences, or unapproved explanation;
2. this approved SPEC;
3. the repository at the exact immutable source state/digest being verified;
4. `tools/gauntlet.sh` as the single entry point.

The builder conversation, draft EVIDENCE, raw logs, and verifier case study are withheld during the blind phase. The closed Plan 01-14 review artifact is not a fifth input; if tracked, it is naturally readable as part of the exact repository state. The verifier may inspect the implementation freely, but fixes nothing.

The blind verifier runs and attacks in this order: (1) confirm run/environment/source freshness and execute the entry point; (2) compare SPEC to the complete contract; (3) attack tests for gaming and construct divergent mutants not chosen by the builder; (4) run known-bad fail controls against every custom checker and assess semantic coverage; (5) audit mapping in both directions. Before reporting a surviving mutant, the verifier must demonstrate a concrete input on which mutant and original diverge. It records append-only the observed source state, actual numbers, full attack list including attacks that found nothing, canary result if used, and initial findings.

Only after the blind findings are frozen append-only is the draft EVIDENCE revealed for number, mapping, and description comparison. The blind record is never rewritten; comparison only appends. A mismatch suspends the claim until source state, environment, freshness, and determinism are reconciled. The verifier reports only `passed`, `failed`, `blocked`, or `not performed` and never repairs code, tests, checkers, SPEC, or evidence. SPEC gaps go to the human.

The human—not the builder—grades every material or disputed finding. Behavioural findings, including a gate that cannot fail, require a TDD fix, new exact source state/digest, full gauntlet, and a new fresh-context verifier round. Description/mapping findings are corrected and disclosed without forcing another round. The default cap is two rounds; any additional round requires explicit recorded human approval. A state unseen by a verifier is `not performed`, even when an earlier state passed.

EVIDENCE is finalized only as follows: `passed` permits finalization; `failed` and `blocked` prohibit it; `not performed` permits only an explicit downgrade stating the reason, earlier-state/round history, last verified state and verdict, and every fix made afterward. The final report records verifier host and model family, fresh-context status, the exact four blind inputs, attack list, findings and human grades/resolutions, canary status, round count/cap/extra approval, exact verified state/verdict, and fixes after the last verified state.

## Known limits accepted by this SPEC

- Refresh rotation deliberately prefers replay safety over transparent retry after a lost refresh response. A client that loses the rotated cookie may need to sign in again.
- Response-equivalence tests reduce account-enumeration differences but do not prove network-level timing indistinguishability.
- HS256 is acceptable for this single internal backend in Phase 1; external identity-provider key discovery and asymmetric federation are deferred.
- Phase 1 proves reusable role enforcement and active-user killswitch behavior; resource-specific authorization matrices arrive with the resources in later phases.
- The browser smoke covers the supported Phase 1 viewport set, not every browser/device combination.

## Prohibitions

These are blocking planning and review constraints: no external identity provider, no Web Storage tokens, no default credentials, no plaintext secrets/tokens, no client-authoritative roles, no inline background work, no hand-written API contract duplication, and no green evidence with skipped or stale checks.

## Revisions

- 2026-08-24: Initial executable specification drafted from the approved Phase 1 context, UI contract, TDD policy, `old-coder` Tier 3 workflow, and `old-coder-api` gates. Awaiting explicit human approval; no implementation authorized yet.
- 2026-08-24: Added explicit authorization semantics for the mandatory GSD package-legitimacy audit. The audit found no `SLOP` package; conservative `SUS` results remain visible and require publisher/source/compatibility rechecks before grouped installation.
- 2026-08-24: Clarified the final-evidence invariant: verification now compares an immutable source-set digest before generating the evidence report, explicitly excludes the report/raw/runtime/build artifacts, and gives the independent verifier the manifest plus recorded digest for recomputation.
- 2026-08-24: Added a mandatory fresh-context code review and OWASP ASVS L1 revision gate before final evidence; its closed findings/resolutions artifact is part of the immutable source set, critical/high findings block, and every fix forces a new digest and full gauntlet.
- 2026-08-24: Approved explicitly by the user with the statement “Approvo la SPEC Phase 1 e l’audit delle dipendenze.” This authorizes the exact behavior contract, the audited grouped dependency installations after publisher/source/compatibility rechecks, the implementation branch, and the RED → GREEN → REFACTOR execution loop.
- 2026-08-24: Aligned independent Tier 3 verification with the full `old-coder` verifier protocol: exactly four blind inputs, append-only blind-first attacks, delayed EVIDENCE comparison, human finding grades, source-specific four-state verdicts, and a two-round default cap.
- 2026-08-24: Added `uv_build>=0.11.12,<0.12.0` as the sole backend build dependency after discovering that the approved installable `src/verboflex` layout requires a PEP 517 backend. The user explicitly approved this dependency-boundary revision with “procedi”. PyPI identifies Astral Software Inc. and the official `astral-sh/uv` repository; Python 3.14 is supported, and the bound matches the installed uv 0.11.12 backend copy.
- 2026-08-24: Added exact direct development dependencies `@types/react@19.2.18` and `@types/react-dom@19.2.5` after the frontend preflight proved that React 19.2.8 ships no TypeScript declarations and Testing Library marks both type packages as optional peers. The user explicitly approved this dependency-boundary revision with “approvo”. npm identifies the Microsoft-maintained `types` publisher account and the official `DefinitelyTyped/DefinitelyTyped` repository; `@types/react-dom@19.2.5` requires the compatible `@types/react^19.2.0` line.
