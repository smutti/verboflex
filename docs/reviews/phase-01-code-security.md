# Phase 1 Fresh-Context Code and Security Review

- Review-status: CLOSED
- Open-critical-high: 0
- Full-gauntlet-status: PASS
- Reviewed-source-digest: `60658f82cd814c9180a9a2bb9db1da90a82cb23620c8ee5d2705e33bc969c5bc`
- Review-date: 2026-08-25
- Review-mode: fresh-context independent goal-backward and OWASP ASVS-aligned source review
- Candidate-verdict: PASS_FOR_POST_FIX_GAUNTLET
- Closure-verdict: PASS_WITH_LOW_DEV_ONLY_DEBT
- Critical: 0
- High: 0
- Medium: 0
- Low: 1

## Conclusion

The reviewed source has no open Critical, High, or Medium finding and no new
finding was introduced by the independent review or complete post-fix run.
VF-SEC-001 through VF-SEC-006 and VF-SEC-008 through VF-SEC-011 remain
resolved. VF-SEC-007 remains the sole open Low finding: a development-only
transitive `qs` advisory with no production dependency path.

The blind review first produced the candidate verdict
**PASS_FOR_POST_FIX_GAUNTLET** while this artifact remained OPEN/PENDING. A
complete post-fix candidate gauntlet then passed against the unchanged reviewed
source, and the independent reviewer reverified the source identity before
closure. The final Phase 1 source-review verdict is
**PASS_WITH_LOW_DEV_ONLY_DEBT** and this artifact is now **CLOSED/PASS**.

## Scope and source identity

The review covered the approved Phase 1 contract, the authentication and
authorization call chains, frontend session authority, generated API contract,
deployment configuration, smoke/adversarial harnesses, custom gauntlet checks,
and every path selected by `tools/source_manifest.txt` in review mode.

The canonical manifest resolved 156 clean tracked paths:

| Category | Paths |
| --- | ---: |
| implementation | 88 |
| tests | 33 |
| config | 18 |
| lockfiles | 3 |
| migrations | 4 |
| verifier-scripts | 9 |
| deployment-contract | 1 |

`bash tools/source_state.sh --review-digest` was executed twice immediately
before the candidate artifact was written and twice again immediately before
review closure. All four runs exited zero and returned exactly
`60658f82cd814c9180a9a2bb9db1da90a82cb23620c8ee5d2705e33bc969c5bc`.
The review artifact is excluded only from review-mode digest computation and is
included by the final source-set contract.

## Review lifecycle and post-fix evidence

### Phase A — blind candidate review

The fresh-context reviewer independently inspected the complete Phase 1 source
and security surface, classified the exact 23 detect-secrets detections, ran
focused source and PostgreSQL probes, and verified the newest Ruff/fail-fast and
secret-policy controls. The digest matched twice, no new finding was opened,
and the artifact was deliberately left `OPEN` with the gauntlet `PENDING` and
verdict `PASS_FOR_POST_FIX_GAUNTLET`.

### Phase B — complete post-fix candidate gauntlet

The complete post-fix candidate gauntlet finished **PASS (NON-FINAL)** against
the same review digest and without source changes. Its recorded evidence is:

| Layer | Recorded result |
| --- | --- |
| Backend and frontend tests | PASS — backend 251/251; frontend 72/72 |
| Frontend delivery | PASS — production build and Playwright 1/1 |
| Static and formatting gates | PASS — mypy, tsc, Ruff check/format, ESLint, Prettier, and Radon |
| Changed-line coverage | PASS — backend 973/973 = 100%; frontend diff has no uncovered line |
| Mutation testing | PASS — mutmut 779 Killed with zero other verdict; Stryker 153 Killed with zero survived/timeout/no-coverage/error, score 100% |
| Property suites | PASS — backend 71; frontend 3 |
| Database migrations | PASS — 3/3 |
| API contract | PASS — OpenAPI negative and positive controls |
| Secret and dependency gates | PASS — exact detect-secrets policy and dependency audits |
| Runtime/integration surface | PASS — staging, adversarial auth, Celery, and browser checks |
| Candidate source identity | PASS — final candidate-source-state check |

The exact Compose projects
`verboflex_phase01_smoke_8378_1787657687` and
`verboflex_phase01_smoke_9118_1787657860` were removed after the run. The
reported cleanup found zero remaining project containers, volumes, images, or
workers. The source tree was unchanged; the unrelated untracked milestone lock
was not part of the reviewed source and was left untouched.

### Phase C — independent reviewer closure

After receiving the complete-run evidence, the reviewer re-read the candidate
artifact, recomputed the non-self-referential review digest twice, confirmed the
same exact value, and promoted only the review metadata and evidence record.
The closure/source-state contract was then checked against the closed artifact.

## Open finding

### VF-SEC-007 — Low — dev-only transitive `qs` advisory

**Status:** OPEN Low, accepted as nonblocking for Phase 1 source-review closure.
Before ship, update the development dependency chain to a non-vulnerable `qs`
version or record an explicit time-bounded risk acceptance with owner and
expiry. Re-run the complete dependency audit at ship time; any runtime path,
severity increase, or additional advisory makes the finding blocking.

`pip-audit` reports no known vulnerability in published backend dependencies and
`npm audit --omit=dev --audit-level=low` reports zero frontend runtime
vulnerabilities. The complete npm audit reports GHSA-q8mj-m7cp-5q26 through the
development-only `typed-rest-client -> qs` chain. The affected package is not in
the production frontend dependency tree or bundle. This remains visible rather
than being silently waived.

**ASVS alignment:** V14 Configuration / dependency hygiene.

## Historical finding disposition

| ID | Severity | Status | Verified disposition and evidence |
| --- | --- | --- | --- |
| VF-SEC-001 | Medium | RESOLVED | `tools/source_manifest.txt` binds implementation, tests, configuration, lockfiles, migrations, verifier scripts, deployment contract, and final review artifact. Empty/missing/category/parser/dirty-path controls fail closed; the manifest self-test passed. |
| VF-SEC-002 | Medium | RESOLVED | Candidate metadata was single-valued and source-bound while OPEN/PENDING. After the complete unchanged-source gauntlet, `source_state.sh` separately enforced CLOSED/zero-critical-high/PASS and the reviewed-source digest, preventing either the candidate or closure artifact from masquerading as another state. |
| VF-SEC-003 | Medium | RESOLVED | The current FastAPI OpenAPI export is byte-identical to `frontend/openapi.json`; generated client drift is checked and the controlled OpenAPI mutation is restored before the real comparison. Auth request limits and response/security contracts are present in the committed schema. |
| VF-SEC-004 | Medium | RESOLVED | Real-smoke and adversarial tools use private temporary directories/files, generated one-run secrets, explicit timeouts, exact Compose project/image identifiers, stdin/getpass secret entry, scoped cleanup traps, and preflight negative controls. No review-owned container or temporary secret artifact remained. |
| VF-SEC-005 | Medium | RESOLVED | Backend mutation scope is the nine handwritten auth/session modules listed in `backend/pyproject.toml`; frontend scope is `frontend/src/features/auth/session.tsx` with threshold 100. The complete post-fix run produced mutmut 779 Killed with zero other verdict and Stryker 153 Killed with zero survived/timeout/no-coverage/error, score 100%. The gate rejects any non-Killed backend verdict and any Stryker result below 100. |
| VF-SEC-006 | Medium | RESOLVED | Compose exposes application ports on loopback only and does not publish PostgreSQL/Redis. The runbook requires a trusted TLS edge, TLS 1.2/1.3, HTTP redirect or unreachability, HSTS, hostname/certificate validation, and loopback-only forwarding. Live edge proof remains a separate later gate. |
| VF-SEC-007 | Low | OPEN | One Moderate npm advisory is confined to the dev-only `typed-rest-client -> qs` chain. Backend and frontend runtime audits are clean; explicit ship-time disposition is retained. |
| VF-SEC-008 | Medium | RESOLVED | Login and refresh emit only `__Host-verboflex_refresh` with `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, and no `Domain`; temporary login emits no refresh cookie. Logout and password change delete the same exact host cookie scope. Tests and smoke reject legacy `__Secure-verboflex_refresh`, unprefixed names, wrong path, or Domain. |
| VF-SEC-009 | Medium | RESOLVED | Logout resolves the presented session, locks it, and revokes every member of its server-owned family. The R0 -> R1 test and real smoke prove both pre-rotation A1 and successor A2 fail with the exact 401 after logout; repeated logout returns the same empty 204 and matching deletion cookie. |
| VF-SEC-010 | Medium | RESOLVED | Refresh limiting derives identity from durable `AuthSession.family_id` plus the validated peer IP. R1/R2 share a key; all malformed or unknown tokens collapse to `invalid-refresh-session` plus IP; real-family and sentinel keys differ and raw authority is absent from Redis keys. Request 31 returns exact 429 before rotation, and invalid Redis state/outage returns exact 503 without mutation or successor cookie. |
| VF-SEC-011 | Medium | RESOLVED | Login username/password/client_id/client_secret/scope limits are enforced by FastAPI form parsing; password-change current/new limits are checked before bearer decoding, Redis evaluation, durable mutation, or Argon2. The committed OpenAPI publishes 320/128/320/128/1024 and 128/128 maxima. Independent request probes returned 422 for all five oversized login/OAuth cases with zero Redis calls, and focused password-change tests preserve the exact stable 422 envelope and durable state. |

## Security and correctness review

### Authentication and bootstrap

- Bootstrap normalizes the email, validates password policy, obtains a
  PostgreSQL transaction advisory lock, requires an empty user table and the
  seeded admin role, and creates one active forced-change administrator. The CLI
  exposes no password option and reads through getpass or one non-echoed stdin
  line. Concurrent/second bootstrap and rollback paths are covered.
- Login applies finite HTTP form bounds before route work, normalizes the email,
  limits normalized-email plus server-observed IP before user lookup or Argon2,
  performs dummy Argon2 verification for unknown identities, and returns one
  non-enumerating 401 for unknown, inactive, or incorrect credentials.
- Deployed settings restrict JWT to HS256, require at least 32 secret bytes,
  reject common placeholder markers, require Secure cookies, and validate exact
  HTTP origins before serving.

### Access and refresh authority

- JWT decoding fixes the algorithm, requires subject/iat/exp/purpose/version,
  validates claim types, enforces purpose-specific exact lifetime and session-id
  semantics, and then revalidates active user, token version, durable session,
  expiry, revocation, password-change flag, and server-loaded roles.
- Ordinary access tokens require a durable session ID. Forced-change tokens
  carry no session ID and cannot reach ordinary protected endpoints. Password
  replacement increments token version and revokes every still-live session for
  that user in the same database transaction.
- Refresh material is 32 random bytes, persists only as SHA-256, rotates under a
  predecessor row lock, keeps a stable server-owned family ID, and revokes the
  complete family on replay. The PostgreSQL concurrency contract permits exactly
  one successor and denies/revokes replayed authority.

### Cookie, origin, CORS, and logout boundary

- The cookie contract uses the host-only `__Host-` namespace correctly:
  `Secure`, `Path=/`, no Domain, plus `HttpOnly` and `SameSite=Lax`. Set and
  delete operations use the same name and scope; legacy cookie names are never
  read or emitted.
- Cookie-authenticated mutations reject any present Origin outside the exact
  configured allowlist before Redis or PostgreSQL mutation. Absent Origin
  remains supported for non-browser clients. CORS permits credentials only for
  explicit origins, GET/POST, Authorization, and Content-Type; it uses no
  credentialed wildcard.
- Logout intentionally remains available when Redis is unavailable, clears the
  browser cookie, and revokes the complete durable refresh family when the
  supplied cookie resolves. Missing, malformed, unknown, repeated, and valid
  logout responses remain non-enumerating.

### Rate limits and bounded work

- Login is limited at 5/minute per normalized-email plus validated peer IP;
  refresh at 30/minute per stable family/sentinel plus IP; logout at 10/minute;
  password change at 10/minute per cryptographically verified user plus IP;
  ordinary reads at 120/minute per durable principal; health at 60/minute per
  validated peer.
- Redis scripts perform atomic INCR/EXPIRE, validate the two-element numeric
  response, bound Retry-After to a positive value, and hash raw identifiers out
  of keys. Security-sensitive login, refresh, and password-change actions fail
  closed on unavailable/invalid Redis state. The diagnostic local fallback is a
  locked bounded LRU map rather than an attacker-unbounded dictionary.
- Oversized credential requests are rejected before expensive password work and
  before Redis evaluation. Rate-limit exhaustion is also proven to occur before
  Argon2 verification or refresh/password durable mutation.

### API, OpenAPI, and frontend session authority

- The seven-operation API surface, exact methods/status families, OAuth2 bearer
  markers, error models, form/JSON bounds, operation IDs, canonical export, and
  generated client are guarded against drift.
- Browser access tokens exist only in React memory. Refresh authority remains in
  the Secure HttpOnly cookie and every generated call uses central
  `credentials: "include"`. Principal identity and roles come only from
  `/users/me`; the frontend does not decode bearer claims or invent authority.
- The state machine confines checking, signed-out, forced-change, and ordinary
  routes. A monotonic operation token prevents late login/identity/refresh or
  password-change completions from restoring React authority after logout or a
  newer transition. Logout clears React authority before the network call, even
  if that call fails.
- The AST credential-storage guard rejects access/refresh/password material in
  Web Storage, IndexedDB, URLs, logs, or analytics and has both known-good and
  known-bad controls.

### Infrastructure, source state, and smoke

- Backend runtime is non-root, frontend is a production static build, app ports
  are loopback-bound, and data services are internal-only. Staging/production
  use SCRAM PostgreSQL auth and fail configuration on empty/placeholder/short JWT
  material or insecure refresh-cookie configuration.
- Source-state hashing covers sorted paths plus file digests, verifies every
  required category, rejects missing/untracked/staged/unstaged inputs, and
  distinguishes review-mode from final-mode source identity. Layer records must
  match the exact ordered list before a success message can be printed.
- The smoke path covers migration upgrade/downgrade/upgrade, protected bootstrap,
  health/readiness, Celery result 5, temporary login/change/login, exact cookie
  attributes, me/status, rotation, family logout A1/A2 invalidation, browser
  reload/storage/viewports/logout, hostile tokens/origin, replay/concurrency,
  brute-force boundary, non-enumeration, and Redis outage behavior.

## Latest gate verification

### Static-check failure propagation and Ruff formatting

`run_required_checks` invokes each named check in order and immediately returns
the exact first non-zero status. `backend_static_checks` itself links `ruff check`
and `ruff format --check` with `&&`, so either Ruff step becomes the wrapper's
first failure. The repository negative control returns 42 at the middle check and
proves the following check is not invoked.

An additional isolated probe used the real `backend_static_checks` function with
a fake Ruff executable: lint returned zero, format returned 42, the wrapper
returned 42, and neither frontend checks nor complexity ran. Current real Ruff
checks also passed:

- `uv run ruff check src tests`: PASS.
- `uv run ruff format --check src tests`: PASS — 58 files already formatted.

### Detect-secrets exact policy and 23/23 classification

The gauntlet converts every detection to the exact tuple
`path|line|plugin|hashed-fingerprint`, sorts the result, and compares it byte for
byte with the source-bound audited policy. There is no plugin-wide, file-wide, or
count-only waiver for any of the 23 accepted detections. A missing, changed,
moved, retyped, re-fingerprinted, or additional detection fails the comparison.

The normal scanner omits dependency lockfiles and `.planning/` from its command
line; an independent scan of all 195 tracked files, including those paths,
returned the same 23 detections and zero additional detection. Thus those scope
exclusions hide no current candidate finding and are not used to waive any of
the 23 entries below.

| # | Bound detection | Classification |
| ---: | --- | --- |
| 1 | `src/verboflex/auth/access_tokens.py|16|Secret Keyword|3591079abcc3407a2c2ed76661ec29a7ec0d1cb8` | False positive: public error constant `password change required`; no credential value. |
| 2 | `src/verboflex/auth/access_tokens.py|17|Secret Keyword|06c49c9b4bd885fbdc2a04cc3f65b214292b0da9` | False positive: missing-JWT-secret diagnostic; no secret is embedded. |
| 3 | `src/verboflex/auth/access_tokens.py|19|Secret Keyword|411a5e3d10eceaebc65194fdafdd05fb8e432e38` | False positive: public token-purpose/session diagnostic. |
| 4 | `src/verboflex/auth/password_change.py|25|Secret Keyword|443fe4e817f15f5b62b02db228cd59ec2d5cfc8f` | False positive: generic invalid-access diagnostic. |
| 5 | `src/verboflex/auth/password_change.py|26|Secret Keyword|3b8788b039ebfe732e34b976cabe8fe87a3ceb17` | False positive: generic incorrect-current-password diagnostic. |
| 6 | `src/verboflex/auth/password_change.py|55|Secret Keyword|42213dc7f2ef60d5d6744c00f091a46b2161dda5` | False positive: public password-policy message. |
| 7 | `src/verboflex/auth/principal.py|28|Secret Keyword|3591079abcc3407a2c2ed76661ec29a7ec0d1cb8` | False positive: public forced-change diagnostic. |
| 8 | `src/verboflex/auth/principal.py|29|Secret Keyword|82bde2d99285779d940c36fdcdb9c3e9afa40d2f` | False positive: public forced-change response detail. |
| 9 | `src/verboflex/auth/refresh_sessions.py|19|Base64 High Entropy String|e582429052cdb908833560f6f7582d232de37c4d` | False positive: the literal public base64url alphabet used for syntax validation, not generated authority. |
| 10 | `tests/api/test_rate_limits.py|189|Secret Keyword|5ac066cfb3bcf9973a0b40daeb7f5606103c1bd3` | False positive: local HTTP password fixture. |
| 11 | `tests/api/test_system_status.py|109|Basic Auth Credentials|e5e9fa1ba31ecd1ae84f75caaa474f3a663f05f4` | False positive: deliberately fake database URL inside a redaction test; the test proves it is not exposed. |
| 12 | `tests/auth/test_bootstrap_admin.py|136|Secret Keyword|985a4d67132193977275067aca18c13f8c8371c8` | False positive: isolated bootstrap password fixture. |
| 13 | `tests/auth/test_bootstrap_admin.py|147|Secret Keyword|d36b093dec485bfd20ef697ca6c1ad79e1ac9210` | False positive: isolated second-bootstrap password fixture. |
| 14 | `tests/auth/test_bootstrap_admin.py|235|Secret Keyword|3da24dfed48aa2721da14e6f79e588440b934675` | False positive: isolated reset-password fixture. |
| 15 | `tests/auth/test_bootstrap_admin.py|295|Secret Keyword|028e59d8204d08fecd6aad12434b872fe4319f6d` | False positive: isolated replacement-password fixture. |
| 16 | `tests/auth/test_bootstrap_admin.py|410|Secret Keyword|5d9dec21ffdbb45c64f0ea2b1abf3b25c2afc728` | False positive: isolated unknown-account reset fixture. |
| 17 | `tests/auth/test_bootstrap_admin.py|445|Secret Keyword|1123e04e3b43d460543f1b0bf94e67a0a636b2cc` | False positive: in-memory secret-reader fixture proving CLI input routing. |
| 18 | `tests/auth/test_bootstrap_admin.py|548|Secret Keyword|cdd076c21ce35f40d40b6c16d12bd40876050a6f` | False positive: in-memory protected-input fixture. |
| 19 | `tests/auth/test_bootstrap_admin.py|626|Secret Keyword|18468712bc6eede8cb7adf8932b073bf56773a11` | False positive: explicit `non-secret-test-hash` rollback fixture. |
| 20 | `tests/auth/test_login.py|45|Secret Keyword|e7e0ea25217b715c566268c0607e48acef3b9ccf` | False positive: local valid-password fixture for isolated databases. |
| 21 | `tests/auth/test_password_change.py|188|Secret Keyword|a95b347855753c3b784594a28fa00ec116430d1c` | False positive: deliberately wrong current-password test input. |
| 22 | `tests/auth/test_password_change.py|36|Secret Keyword|bc27f09f74d82f81b559a27a26bd03f580960364` | False positive: isolated current-password fixture. |
| 23 | `tests/auth/test_password_change.py|37|Secret Keyword|ba8d4568d2e2f6531c78080cedddb3a16f08afd5` | False positive: isolated replacement-password fixture. |

All **23/23 are false positives**. No real secret was found.

The detector negative control supplies a syntactically real AWS access-key
fixture and must fail. The exact-policy negative control adds a new unreviewed
tuple and must fail. Both passed their expected-failure assertions, while the
fresh repository scan matched the exact 23-row policy.

## ASVS-oriented result

| ASVS area | Review result | Evidence |
| --- | --- | --- |
| V2 Authentication | PASS | Bounded credential parsing, Argon2 and dummy verification, non-enumerating login, bootstrap/reset safeguards, forced-change authority. |
| V3 Session Management | PASS | Exact host cookie, hashed opaque refresh values, rotation, replay-family revocation, logout-family revocation, durable access-session binding, concurrency invariant. |
| V4 Access Control | PASS | Durable active user/version/session checks, server-derived roles, forced-change purpose isolation, reusable role dependency. |
| V5 Validation | PASS | Exact origin allowlist, bounded form/JSON credential inputs, normalized email, strict JWT claim/lifetime/type validation, generated schema bounds. |
| V7 Error Handling and Logging | PASS | Stable non-enumerating envelopes, no stack/connection/hash leakage, secret-input and storage/logging guards, bounded outage behavior. |
| V9 Communications | PASS AT REPOSITORY BOUNDARY | Loopback-only app publication, Secure cookie, explicit managed TLS/HSTS contract. Live certificate/redirect/HSTS proof remains pending. |
| V13 API and Web Service | PASS | Exact OpenAPI surface, explicit credentialed CORS, deterministic 401/403/422/429/503 behavior, server-side limits and authorization. |
| V14 Configuration | PASS WITH LOW DEBT | Deployed secret/cookie validation and runtime audits pass; VF-SEC-007 remains tracked Low dev-only debt with an explicit ship-time disposition. |

## Fresh verification record

| Check | Result |
| --- | --- |
| Canonical review digest, two immediate pre-write runs | PASS — exact `60658f82cd814c9180a9a2bb9db1da90a82cb23620c8ee5d2705e33bc969c5bc` twice |
| Canonical manifest resolution | PASS — 156 clean paths across every required review-mode category |
| Manifest self-test | PASS |
| Gauntlet preflight | PASS |
| Real-smoke preflight | PASS |
| Adversarial-auth self-test | PASS |
| Ruff lint and format | PASS — lint clean; 58 files already formatted |
| Actual Ruff-format failure propagation probe | PASS — returned 42 and skipped frontend/complexity checks |
| Required-check repository negative control | PASS — exact first error propagated; later check did not run |
| OpenAPI current export | PASS — byte-identical to committed schema |
| Focused PostgreSQL security selection | PASS — 11/11, including exact cookie, family logout, stable refresh limiter, request-31/Redis ordering, bounded inputs, and OpenAPI limits |
| Independent login/OAuth oversize HTTP probe | PASS — five 422 responses, zero Redis calls |
| Detect-secrets exact policy | PASS — 23/23 exact tuple match |
| Detect-secrets full tracked-tree cross-check | PASS — 195 files, the same 23 detections, zero extra detection |
| Detect-secrets true-key and unreviewed-tuple negative controls | PASS — both failed as required |
| Backend mutation verdict state | PASS — configured nine-module scope; complete run 779 Killed, zero other verdict |
| Frontend mutation result state | PASS — configured session scope; complete run 153/153 Killed, zero survived/timeout/no-coverage/error, score 100% |
| Backend dependency audit | PASS — no known vulnerability in published packages |
| Frontend production dependency audit | PASS — zero vulnerabilities |
| Frontend complete dependency audit | EXPECTED LOW DEBT — VF-SEC-007 only |
| Full post-fix candidate gauntlet | PASS (NON-FINAL run) — unchanged-source evidence recorded in the review lifecycle table |
| Closure digest, two immediate pre-write runs | PASS — exact `60658f82cd814c9180a9a2bb9db1da90a82cb23620c8ee5d2705e33bc969c5bc` twice |
| Closed-review metadata contract | PASS — `Review-status: CLOSED`, zero open Critical/High, and `Full-gauntlet-status: PASS` |
| Closed-review source binding | PASS — artifact references the exact non-self-referential review digest |

## Final disposition

- Critical / High / Medium / Low: **0 / 0 / 0 / 1**
- Open Critical/High: **0**
- Candidate verdict: **PASS_FOR_POST_FIX_GAUNTLET**
- Closure verdict: **PASS_WITH_LOW_DEV_ONLY_DEBT**
- Full-gauntlet status: **PASS**
- Review status: **CLOSED**

VF-SEC-007 remains deliberately visible and open at Low severity. Its ship-time
disposition is mandatory: upgrade the development dependency chain or record a
time-bounded risk acceptance, then rerun the dependency audit. This closure does
not waive that debt or any future live deployment/TLS evidence required by the
release process.
