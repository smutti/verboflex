# Phase 1 Fresh-Context Code and Security Candidate Review

- Review-status: OPEN
- Open-critical-high: 0
- Full-gauntlet-status: PENDING
- Reviewed-source-digest: `c2003b39145c5279d4a4a63e364d7bc71e0c0627881f4763a8a394b1ee2e7c77`
- Review-date: 2026-08-25
- Reviewer-context: independent fresh-context review; builder conversation and reasoning were not read
- Candidate-verdict: BLOCKED_BY_OPEN_MEDIUM_FINDINGS
- Critical: 0
- High: 0
- Medium: 2
- Low: 1

## Candidate conclusion

This source state is **not ready for the post-fix gauntlet**. No critical or high finding is
open, but two independently reproduced medium findings remain: refresh rate limiting is keyed
by the rotating cookie instead of a stable session/family identity (`VF-SEC-010`), and the HTTP
authentication contracts do not bound credential lengths before parsing and password
verification (`VF-SEC-011`). Both conflict with explicit Phase 1 security contracts and can
amplify resource-exhaustion attempts.

The report deliberately remains OPEN and does not claim that the full gauntlet passed. The
full-gauntlet status remains PENDING. The only admitted low item remains the known development-
only dependency debt `VF-SEC-007`, but it is not the reason this candidate is blocked.

## Scope and source identity

The blind review used the approved `01-SPEC.md`, `01-14-PLAN.md`, the canonical
`tools/source_manifest.txt`, its manifest-resolved source and tests, the source-bound runbook,
and earlier summaries only as an index. The previous review artifact was opened only after the
blind inspection, solely to reconcile stable IDs `VF-SEC-001` through `VF-SEC-009`.

Before this artifact write, the canonical review digest was reproduced twice and matched the
required value on both runs:

```text
c2003b39145c5279d4a4a63e364d7bc71e0c0627881f4763a8a394b1ee2e7c77
c2003b39145c5279d4a4a63e364d7bc71e0c0627881f4763a8a394b1ee2e7c77
```

The pre-existing untracked `.planning/milestone.lock` was neither read nor modified. This
canonical review artifact is the only file written by this review and is excluded from the
review-mode digest by design.

## Open findings

### VF-SEC-010 — rotating refresh cookie defeats the session-and-IP rate-limit key

- **Severity:** medium.
- **Status:** OPEN, BLOCKING CANDIDATE ADVANCEMENT.
- **Contract:** `01-SPEC.md` requires refresh to be limited to 30/minute per session-and-IP
  before token rotation.
- **Evidence:** `backend/src/verboflex/api/v1/routes/auth.py:153-158` supplies
  `refresh_cookie` as the limiter identity. Every successful rotation issues a different
  opaque cookie, so the next request uses a fresh Redis key. Invalid requests can likewise
  manufacture new cookie identities before the indexed session lookup.
- **Reproduction:** an in-process Redis probe allowed all 31 calls made from one IP with 31
  distinct identities (`unique-identities-allowed=31`, 32 total keys including the control),
  while the 31st call with one stable identity was denied. This demonstrates that the counter
  works but the route supplies an unstable authority.
- **Impact:** a valid session can perform serial rotations without the specified aggregate cap;
  arbitrary cookie values can spread pre-database attempts over unbounded keys. This weakens
  the resource-exhaustion control and permits Redis-key cardinality growth.
- **Required fix:** derive the limit from a stable server-owned session/family identity without
  performing rotation first, and add tests proving 31 sequential rotations in one family plus
  distinct invalid tokens from one IP cannot evade the bounded policy.

### VF-SEC-011 — authentication request fields are unbounded at the HTTP boundary

- **Severity:** medium.
- **Status:** OPEN, BLOCKING CANDIDATE ADVANCEMENT.
- **Contract:** `01-SPEC.md` defines passwords as 12-128 characters and the API blast radius as
  bounded payloads; its edge-case set explicitly includes overlong identifiers and passwords.
- **Evidence:** OpenAPI reports `maxLength=None` for OAuth `username` and `password`, and for
  `ChangePasswordRequest.current_password` and `.new_password`. The latter schema uses plain
  `str` fields at `backend/src/verboflex/schemas/auth.py:23-27`; login is parsed through the
  unconstrained OAuth2 form. `password_change.py:114-122` verifies the unbounded current
  password with Argon2 before the new-password policy is applied. Login similarly verifies the
  submitted password at `login.py:73-76` after request parsing.
- **Impact:** authenticated and anonymous callers can make the application parse, normalize,
  hash, or verify oversized credential material before a schema boundary rejects it. Per-
  identity limiting does not bound the size of one request, and variable identifiers can spread
  attempts across keys.
- **Required fix:** place explicit request-contract limits on all credential fields (including
  the 128-character password maximum and a defensible email bound), reject oversized input
  before Argon2/database work, export the constraints to OpenAPI, and add boundary/over-boundary
  tests for form and JSON endpoints.

### VF-SEC-007 — development-only `typed-rest-client -> qs` advisory

- **Severity:** low in the Phase 1 threat model; npm labels the upstream advisory moderate.
- **Status:** OPEN, NON-BLOCKING FOR CANDIDATE, BLOCKING BEFORE SHIP WITHOUT DISPOSITION.
- **Evidence:** `npm audit --omit=dev --json` reports zero vulnerabilities. Full `npm audit
  --json` reports two moderate entries representing one transitive development-only path,
  `typed-rest-client -> qs`; it is absent from the production dependency graph and runtime
  image. Python `pip-audit` reports no known dependency vulnerability.
- **Required pre-ship action:** upgrade or override to a fixed compatible graph, or record a
  dated owner, expiry, and explicit risk decision followed by re-review. No waiver is granted.

## VF-SEC resolution and verification matrix

| ID | Severity | Candidate status | Independent evidence |
| --- | --- | --- | --- |
| `VF-SEC-001` | high | RESOLVED | The canonical manifest covers production, tests, lock/config, migrations, verifier scripts, smoke/runbook, and review categories. Manifest and source-state negative controls passed. |
| `VF-SEC-002` | high | RESOLVED | Candidate verification requires one OPEN status, zero open critical/high, one PENDING gauntlet status, and the exact current digest; duplicate/stale/false-pass controls passed. |
| `VF-SEC-003` | high | RESOLVED | The OpenAPI negative control mutates a real route symbol, observes generated drift, restores exact bytes, and fails before the positive drift check. The new in-process exporter test parses both direct and `__main__` output, compares their JSON to `app.openapi()`, while the separate subprocess test still byte-compares the checked-in schema; it does not mask drift. |
| `VF-SEC-004` | high | RESOLVED | The reviewed smoke harness has unique Compose/database names, protected temporary files, exact exit propagation, readiness timeouts, cleanup traps, and resource-leak assertions. Its preflight and failure-path self-tests passed; the full source-bound gauntlet remains pending. |
| `VF-SEC-005` | medium | RESOLVED | Backend mutation: 741 killed, 0 survived/timeout/suspicious/uncovered. Frontend `session.tsx`: 153 killed, 0 survived/timeout/no-coverage/error, 100.00% mutation score. Mutation scope has zero survivors. |
| `VF-SEC-006` | medium | RESOLVED | `deployment-contract` is required by the source manifest, and tool tests prove a runbook mutation invalidates identity. Staging/production publish application ports only on loopback; the runbook requires trusted TLS 1.2/1.3, HTTP redirect or unreachability, one-year HSTS, and loopback-only origin forwarding. Live edge observation is intentionally not claimed here. |
| `VF-SEC-007` | low | OPEN, NON-BLOCKING | Runtime npm and Python audits are clean; the development graph retains the `typed-rest-client -> qs` advisory documented above. |
| `VF-SEC-008` | medium | RESOLVED | The only application cookie name is exact `__Host-verboflex_refresh`; set/delete are unconditional `Secure`, `Path=/`, `HttpOnly`, `SameSite=Lax`, with no `Domain`. Tests reject legacy cookie names and scopes. |
| `VF-SEC-009` | medium | RESOLVED | Logout locks the presented row and revokes every row sharing its server-owned family. The PostgreSQL family test issues A1, rotates to A2, logs out, asserts all family rows revoked, and obtains exact 401 for both A1 and A2. |
| `VF-SEC-010` | medium | OPEN, BLOCKING | The refresh route keys the 30/minute limiter with a value that changes on every rotation; the independent 31-call probe demonstrated evasion. |
| `VF-SEC-011` | medium | OPEN, BLOCKING | OpenAPI and source inspection show no maximum lengths on the four credential inputs before parsing/Argon2 work. |

## OWASP ASVS L1 mapping

This is a Phase 1 control mapping, not an ASVS certification. Status is based on the reviewed
repository boundary; managed-edge observations remain outside this candidate review.

| ASVS control family | Status | Reviewed evidence and residual finding |
| --- | --- | --- |
| V2 Authentication | PARTIAL | Argon2 password storage, 12-128 policy, forced change, non-enumerating failure, current-password verification, and credential rate limiting are covered. Unbounded HTTP credential fields remain `VF-SEC-011`. |
| V3 Session Management | PARTIAL | Opaque hashed refresh sessions, rotation, replay-family revocation, exact host cookie attributes, A1/A2 logout invalidation, expiry, and concurrent fail-closed behavior are covered. The rotating refresh limiter identity remains `VF-SEC-010`. |
| V4 Access Control | PASS | User, active state, token version, session ownership, password-change purpose, and roles are resolved from durable server state; forged client roles and cross-user sessions fail closed. |
| V5 Validation, Sanitization and Encoding | PARTIAL | Strict JSON schemas, email normalization, JWT claim typing, UUID/purpose/lifetime checks, exact Origin validation, and bounded response enums are covered. Missing credential maximum lengths remain `VF-SEC-011`. |
| V7 Error Handling and Logging | PASS | Authentication errors are non-enumerating, internal details and secrets are redacted, shell tracing is disabled, and secret-bearing temporary artifacts are permission-restricted and cleaned. |
| V9 Communications | PASS AT REPOSITORY BOUNDARY | Staging/production bind origins to loopback and the source-bound runbook requires TLS 1.2/1.3, redirect or unreachable HTTP, and one-year HSTS. Live certificate/HSTS observation is not claimed. |
| V13 API and Web Service | PARTIAL | Exact OpenAPI operations/errors/security, bearer boundaries, CORS/Origin behavior, drift controls, and 429 headers are tested. Refresh rate-limit semantics and input bounds remain `VF-SEC-010`/`VF-SEC-011`. |
| V14 Configuration | PARTIAL, NON-BLOCKING LOW DEBT | Production dependency audits are clean, immutable locks and source binding are enforced, and staging/production reject unsafe secrets/origins. Development-only `VF-SEC-007` remains open. |

## Focused adversarial verification

### Current coverage-only commit

The three added tests exercise real fail-closed branches and are not tautologies:

- A signed JWT with non-string `sub` reaches `_claims_from_payload`; implementation checks
  `isinstance(subject, str)` before UUID parsing and raises the exact invalid-token exception.
- A durable `AuthSession` whose `user_id` differs from the JWT subject reaches
  `_require_current_session` and is rejected before a principal can be returned.
- Direct and `runpy(..., run_name="__main__")` exporter output must both be valid JSON and
  semantically equal to `app.openapi()`. Independent subprocess generation remains
  byte-compared with `frontend/openapi.json`, preserving the drift detector.

The complete backend coverage run used isolated PostgreSQL and Redis services and reported
**245 passed**, **952/952 lines (100.00%)**, and **158/158 branches (100.00%)**. This directly
covers the three newly reachable branches. Frontend tests independently reported 72/72 passed.

### Authentication and authority boundaries

- JWT purpose, lifetime, token version, UUID fields, current user, current session ownership,
  revocation, expiry, active state, and durable role loading fail closed.
- Refresh tokens are 32-byte opaque random values; only SHA-256 hashes are stored. Rotation
  locks the predecessor, creates one same-family successor, and reuse revokes the family.
  PostgreSQL concurrency tests require one 200 and one 401 and leave the family revoked.
- Logout family invalidation proves both predecessor access token A1 and successor access token
  A2 return exact 401 after logout.
- Cookie refresh/logout enforce an exact configured Origin before Redis/database mutation.
  CORS uses explicit origins, credentials, bounded methods/headers, and no wildcard.
- Login, password change, and ordinary-read rate-limit primitives, failure headers, Redis
  fail-closed behavior, and bounded local diagnostics are covered; `VF-SEC-010` is the isolated
  semantic gap in how refresh supplies the identity.

### Redaction, source binding, and transport boundary

- Harnesses do not enable xtrace or print passwords, JWT secrets, cookies, bearer tokens, or
  Authorization headers. Runtime directories are mode 700 and secret-bearing files mode 600;
  traps remove them. CLI password input is stdin/getpass only.
- Redis keys hash raw identities. API errors are bounded and non-enumerating, and browser tests
  prove no token persistence in localStorage, sessionStorage, IndexedDB, URLs, logs, or analytics.
- Source-state tests passed for required categories, tracked/untracked dirt, included changes,
  exact digest binding, candidate metadata, and the runbook/TLS deployment contract.
- The repository boundary requires loopback-only application origins behind a managed TLS edge.
  Environment-specific certificate and HSTS observation remains a later deployment check.

## Verification record

| Check | Result |
| --- | --- |
| review digest before write, twice | PASS; both equal `c2003b39145c5279d4a4a63e364d7bc71e0c0627881f4763a8a394b1ee2e7c77` |
| backend tests and coverage | PASS; 245/245, 952/952 lines, 158/158 branches |
| current commit's JWT/session/OpenAPI tests | PASS within the complete suite; implementation and causal assertions inspected |
| backend mutation | PASS; 741/741 killed, zero survivor/timeout/suspicious/uncovered |
| frontend tests and mutation | PASS; 72/72 tests, 153/153 mutants killed, zero survivor/timeout/no-coverage/error |
| source-state, gauntlet, real-smoke, adversarial harness self-tests | PASS |
| runtime npm audit and Python audit | PASS; zero known dependency vulnerabilities |
| full npm audit | EXPECTED LOW DEBT; `VF-SEC-007` |
| refresh stable-session limit probe | FAIL AS DESIGNED; reproduced `VF-SEC-010` |
| credential schema maximum-length inspection | FAIL AS DESIGNED; reproduced `VF-SEC-011` |
| complete `tools/gauntlet.sh --post-fix-candidate` | PENDING; intentionally not run or claimed by this review |

## Final candidate status

Open findings: **0 critical, 0 high, 2 medium, 1 low**.

Security candidate verdict: **BLOCKED_BY_OPEN_MEDIUM_FINDINGS**. The next valid step is to fix
`VF-SEC-010` and `VF-SEC-011`, add their regressions, regenerate the OpenAPI/client artifacts,
obtain a new reviewed digest, and repeat a fresh candidate review. Review closure and full
gauntlet PASS remain explicitly withheld.
