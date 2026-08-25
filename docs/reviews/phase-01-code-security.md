# Phase 1 Fresh-Context Code and Security Candidate Review

- Review-status: OPEN
- Open-critical-high: 0
- Full-gauntlet-status: PENDING
- Reviewed-source-digest: `9d8930798b065c864ce1f86a99612f0c0c416e84edb217fdc5c5339f0e10b3de`
- Review-date: 2026-08-25
- Review-mode: fresh-context independent adversarial source review
- Candidate-verdict: PASS_FOR_POST_FIX_GAUNTLET
- Critical: 0
- High: 0
- Medium: 0
- Low: 1

## Candidate conclusion

The current source candidate has no open Critical, High, or Medium finding. The two
previously blocking findings, VF-SEC-010 and VF-SEC-011, are resolved in source and
covered by focused PostgreSQL-backed tests plus an independent HTTP-boundary probe.
VF-SEC-007 remains open as non-runtime, dev-only dependency debt at Low severity.

The candidate verdict is **PASS_FOR_POST_FIX_GAUNTLET**. This artifact is deliberately
OPEN and the full post-fix gauntlet is deliberately PENDING. It does not claim a
CLOSED review, a completed live TLS exercise, or a full-gauntlet PASS.

## Scope and source identity

The blind inspection used `.planning/phases/01-platform-foundation/01-SPEC.md`,
`01-14-PLAN.md`, the 01-02 through 01-13 summaries only as an index, and every
source/test/configuration path resolved by `tools/source_manifest.txt`. The
manifest resolved to 147 unique tracked paths. The previous review artifact was
opened only after the blind source inspection, to reconcile the VF-SEC identifiers.

`bash tools/source_state.sh --review-digest` was run twice immediately before
writing. Both runs exited 0 and returned the exact digest recorded above. The review
artifact itself is excluded from that digest by the canonical manifest contract.

## Open finding

### VF-SEC-007 — Low — dev-only transitive `qs` advisory

`npm audit --omit=dev` reports zero runtime vulnerabilities. The complete audit
still reports the known Moderate advisory GHSA-q8mj-m7cp-5q26 through the dev-only
`typed-rest-client -> qs` chain. It is not bundled into the production frontend and
does not create a Phase 1 runtime exploit path. It remains open at Low severity for
explicit ship-time disposition rather than being silently waived.

## Resolved findings

### VF-SEC-010 — refresh rate-limit identity and ordering

Disposition: **RESOLVED**.

- `backend/src/verboflex/auth/refresh_sessions.py` derives a refresh rate-limit
  identity from the server-owned `AuthSession.family_id`, not from the presented
  bearer value. Successors copy the predecessor family identifier, so R1, R2, and
  every later successor share one stable family identity.
- Malformed tokens and well-formed-but-unknown tokens both collapse to the constant
  `invalid-refresh-session`. They cannot create attacker-controlled cardinality.
  `enforce_auth_action_rate_limit` combines that bounded identity with the validated
  peer IP and hashes the composite before constructing the Redis key.
- In `backend/src/verboflex/api/v1/routes/auth.py`, the refresh limiter runs before
  `rotate_refresh_session`. Request 31 returns the exact 429 contract without
  consuming or rotating the refresh token.
- A Redis failure raises the exact 503 authentication-unavailable response and does
  not rotate the token or set a successor cookie.
- `test_refresh_rate_limit_key_is_stable_for_family_and_bounded_for_invalid_tokens`
  proves equal keys for R1/R2, equal sentinel keys for distinct invalid tokens, and
  separation between a real family and the invalid sentinel. Focused tests also
  prove request-31 ordering and the Redis failure path.

The lookup needed to resolve a well-formed token to server-owned family identity
precedes Redis, but no rotation or durable session mutation does. That is consistent
with the required “rate before rotation” boundary.

### VF-SEC-011 — bounded authentication inputs at the HTTP boundary

Disposition: **RESOLVED**.

- `BoundedOAuth2PasswordRequestForm` enforces `username.max_length=320`,
  `password.max_length=128`, `client_id.max_length=320`,
  `client_secret.max_length=128`, and `scope.max_length=1024`.
- `ChangePasswordRequest` publishes `maxLength: 128` for both
  `current_password` and `new_password`. The route performs the same bounds check
  before bearer decoding, rate limiting, database mutation, or Argon2 work.
- `frontend/openapi.json` contains those exact maximum lengths: login username 320,
  password 128, client ID 320, client secret 128, scope 1024, and current/new
  passwords 128.
- Oversized login username/password tests return 422 with no Redis call. Oversized
  current/new password tests return 422 with no Redis call and unchanged durable
  password state.
- An independent request-level probe also exercised overlong `client_id`,
  `client_secret`, and `scope`: all returned 422 before the route handler and
  before Redis. The oversized password-change probe returned the stable envelope
  `{"detail":"Password must contain 12 to 128 characters"}`.

## Security review matrix

| ID | Severity | Status | Independent disposition |
| --- | --- | --- | --- |
| VF-SEC-001 | Medium | RESOLVED | The canonical manifest binds the reviewed implementation, tests, deployment contracts, tools, runbook, generated OpenAPI, and lockfiles. Manifest self-test passes. |
| VF-SEC-002 | Medium | RESOLVED | Candidate metadata is single-valued, source-bound, OPEN, and explicitly PENDING; the candidate gate validates it against the live digest. |
| VF-SEC-003 | Medium | RESOLVED | Generated OpenAPI is checked for drift and the bounded auth schemas are present in the committed client contract. |
| VF-SEC-004 | Medium | RESOLVED | Smoke tooling uses isolated temporary state, restrictive permissions, cleanup traps, and explicit preflight validation. |
| VF-SEC-005 | Medium | RESOLVED | Current mutation runs killed 779/779 backend mutants and 153/153 frontend mutants, with zero survivors, timeouts, uncovered mutants, or errors. |
| VF-SEC-006 | Medium | RESOLVED | The runbook defines the managed TLS edge, TLS 1.2/1.3, trusted certificate, HTTP redirect/unreachability, HSTS, loopback-only forwarding, and loopback-bound application ports. Live staging proof remains a separate post-fix gate. |
| VF-SEC-007 | Low | OPEN | The remaining `qs` advisory is confined to a dev-only transitive chain; production dependency audit is clean. Ship-time disposition is still required. |
| VF-SEC-008 | Medium | RESOLVED | Refresh cookies use exactly `__Host-verboflex_refresh`, `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, and no `Domain`; clear semantics match set semantics. Tests reject legacy/wrong prefix, path, and domain variants. |
| VF-SEC-009 | Medium | RESOLVED | Logout locks the presented session and revokes the whole family. The R0→R1 scenario proves both A1 and A2 return the exact 401 contract after logout; repeated logout remains idempotent. |
| VF-SEC-010 | Medium | RESOLVED | Stable server-owned family-plus-IP rate identity, bounded invalid sentinel-plus-IP, limiter before rotation, exact 429, and Redis failure 503 are implemented and tested. |
| VF-SEC-011 | Medium | RESOLVED | Login, OAuth optional fields, and password-change inputs have finite OpenAPI/runtime bounds and reject oversize requests with 422 before Redis/Argon2 while preserving the password-change error envelope. |

## Additional adversarial review

### Authentication, replay, and concurrency

Access JWT decoding fixes the algorithm, requires and type-checks the security claims,
enforces purpose and bounded lifetime, and then revalidates durable user, session,
active-state, token-version, and role authority. Refresh rotation locks the predecessor;
a replay revokes the entire family. The PostgreSQL concurrency test produces one 200,
one exact 401, one successor, and a revoked family.

Login rate limiting uses normalized email plus validated peer IP before user lookup or
Argon2 and fails closed with 503 when Redis is unavailable. Refresh uses the stable
family/sentinel identity described above. Password change, authenticated reads, and
health checks have explicit finite limits. The local health fallback is bounded rather
than an unbounded attacker-controlled map.

### Origin, CORS, and cookie boundary

Present `Origin` values are checked against the exact configured allowlist before
state mutation; absent Origin remains compatible with non-browser clients. CORS uses
explicit origins, credentials, the GET/POST method set, and only Authorization and
Content-Type headers—no wildcard trust. Host-cookie tests cover exact namespace and
attribute semantics.

### Error handling and secret redaction

Authentication failures use stable non-enumerating envelopes. Tooling avoids shell
xtrace, creates private temporary directories/files, does not print bearer, refresh,
database, or signing secrets, and obtains CLI secrets from stdin/getpass. Frontend
guards reject credential persistence through Web Storage, IndexedDB, URL surfaces,
logs, and analytics; the guard includes both positive and negative controls.

### TLS and deployment boundary

Compose binds backend and frontend ports to loopback and does not publish PostgreSQL or
Redis. The documented production boundary terminates trusted TLS at an external managed
edge and permits only loopback forwarding to the application. Repository evidence can
verify that contract; the live-edge exercise remains intentionally pending.

### Coverage and test quality

Backend and frontend coverage commands enforce 100% line/branch/statement/function
thresholds for the governed handwritten source, with narrowly declared exclusions for
generated clients, the migration, project-owned shadcn primitives, and entrypoint-only
wiring. The fresh focused PostgreSQL run passed 10/10 security tests. Mutation
verification independently completed at 100% for both governed mutation scopes. The
full coverage and end-to-end re-execution belong to the still-PENDING post-fix
gauntlet, so this review does not promote their historical result into a current full
gauntlet PASS.

## ASVS-oriented disposition

| ASVS area | Candidate result | Evidence |
| --- | --- | --- |
| V2 Authentication | PASS | Bounded password inputs, Argon2 boundary, non-enumerating login, durable token-version checks, forced password-change restriction. |
| V3 Session Management | PASS | Exact host cookie, rotation, replay-family revocation, logout-family revocation, concurrency invariant. |
| V4 Access Control | PASS | Server-derived roles and restricted-token purpose enforcement on protected routes. |
| V5 Validation | PASS | HTTP-boundary length limits, exact Origin allowlist, strict JWT claim validation, generated OpenAPI bounds. |
| V7 Error Handling and Logging | PASS | Stable public envelopes, Redis fail-closed behavior where required, secret-redaction guards. |
| V9 Communications | PASS AT REPOSITORY BOUNDARY | Loopback-only origins and explicit TLS/HSTS edge contract; live validation remains pending. |
| V13 API and Web Service | PASS | Explicit CORS, rate limits, OpenAPI drift checks, request validation, deterministic 401/422/429/503 behavior. |
| V14 Configuration | PARTIAL, NONBLOCKING | Runtime dependency set is clean; VF-SEC-007 retains one dev-only transitive advisory at Low. |

## Fresh verification record

| Check | Result |
| --- | --- |
| Canonical review digest, two independent runs | PASS — exact `9d8930798b065c864ce1f86a99612f0c0c416e84edb217fdc5c5339f0e10b3de` both times |
| Manifest self-test | PASS |
| Gauntlet preflight | PASS |
| Real-smoke preflight | PASS |
| Adversarial-auth self-test | PASS |
| Focused PostgreSQL security selection | PASS — 10/10 |
| Independent HTTP auth-boundary probe | PASS — five login/OAuth oversize cases and one password-change oversize case returned 422; zero Redis calls |
| Backend mutation | PASS — 779 killed, 0 surviving or uncovered |
| Frontend mutation | PASS — 153 killed, 0 surviving or uncovered |
| Backend dependency integrity/audit | PASS — lock check valid, no known vulnerabilities in published packages |
| Frontend runtime dependency audit | PASS — 0 vulnerabilities |
| Frontend full dependency audit | EXPECTED LOW DEBT — VF-SEC-007 only |
| Full post-fix candidate gauntlet | PENDING |

## Final disposition

- Critical / High / Medium / Low: **0 / 0 / 0 / 1**
- Open Critical/High: **0**
- Candidate verdict: **PASS_FOR_POST_FIX_GAUNTLET**
- Full-gauntlet status: **PENDING**
- Review status: **OPEN**

The next valid promotion step is the post-fix candidate gauntlet. Only a source-bound
successful gauntlet and the required live deployment evidence may produce later
closure artifacts; this candidate review does not do so.
