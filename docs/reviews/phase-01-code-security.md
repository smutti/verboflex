# Phase 1 Fresh-Context Code and Security Review

- Review-status: OPEN
- Open-critical-high: 0
- Full-gauntlet-status: PENDING
- Reviewed-source-digest: `14f4e2795d168b488a33a9fca1a8a8fe746d0ec9df29dd640ab883a98427f709`
- Review-date: 2026-08-25
- Review-mode: fresh-context independent goal-backward and OWASP ASVS-aligned source review
- Candidate-verdict: PASS_FOR_POST_FIX_GAUNTLET
- Closure-verdict: PENDING
- Critical: 0
- High: 0
- Medium: 0
- Low: 1

## Conclusion

The reviewed source has no open Critical, High, or Medium finding and no SPEC
gap requiring escalation. F-01 through F-08 and VF-SEC-001 through VF-SEC-006,
VF-SEC-008 through VF-SEC-017 are resolved. VF-SEC-007 remains the sole open
Low finding: a development-only transitive `qs` advisory with no production
dependency path.

This fresh source-bound review records the candidate verdict
**PASS_FOR_POST_FIX_GAUNTLET**. The artifact deliberately remains
**OPEN/PENDING**: the complete post-fix gauntlet has not yet been run against
this reviewed digest, so this review makes no full-gauntlet PASS or closure
claim.

## Scope and source identity

The review covered the approved Phase 1 contract, the authentication and
authorization call chains, frontend session authority, generated API contract,
deployment configuration, smoke/adversarial harnesses, custom gauntlet checks,
and every path selected by `tools/source_manifest.txt` in review mode.

The canonical manifest resolved 161 clean tracked paths:

| Category | Paths |
| --- | ---: |
| implementation | 88 |
| tests | 33 |
| config | 19 |
| lockfiles | 3 |
| migrations | 4 |
| verifier-scripts | 13 |
| deployment-contract | 1 |

`bash tools/source_state.sh --review-digest` was executed twice consecutively
immediately before this candidate artifact was written. Both runs exited zero
and returned exactly
`14f4e2795d168b488a33a9fca1a8a8fe746d0ec9df29dd640ab883a98427f709`.
The review artifact is excluded only from review-mode digest computation and is
included by the final source-set contract.

## Review lifecycle and candidate evidence

### Phase A — blind candidate review

The fresh-context reviewer independently inspected the complete Phase 1 source
and security surface, classified the exact 23 detect-secrets detections, ran
focused source, PostgreSQL, frontend, dependency, archived-RED, production
Cobertura, cleanup, and exact-secret-policy probes, and revalidated F-01 through
F-08 plus VF-SEC-012 through VF-SEC-017. The digest matched twice, no new
material finding was opened, and the artifact is deliberately left `OPEN` with
the gauntlet `PENDING` and verdict `PASS_FOR_POST_FIX_GAUNTLET`.

### Candidate revalidation history and human decisions

- The prior source-review candidate at review digest
  `6bbff02fa710c8fcd1fef51d72da712ab781862a7830bf9bfcfbd3a5a1f6ad29`
  remains historical only. The exact equivalent-mutant gate added afterward
  invalidated that digest and produced the current review digest above.
- The earlier candidate at review digest
  `45681aed630a5b5863a2723c1413c29f6055101499d442b2148224c6081636c3`
  remains historical only. Subsequent coverage-gate tests and fixes invalidated
  it and produced the current review digest above.
- The subsequent post-fix candidate attempt at review digest
  `763557c2e5b719516105322a773cb141dca92ead7f91ef23db0814f79fb4ba42`
  exposed TypeScript TS2345 at the four deferred service-status resolutions in
  `AppShell.test.tsx` (then lines 244/245/302/303). The human graded the finding
  behavioural Medium. It is resolved without a production change or broad cast:
  the test now names `Awaited<ReturnType<typeof readSystemStatus<false>>>`, which
  exactly matches the generated SDK's default `ThrowOnError = false` and the
  production call site that supplies no override. On the current digest the
  focused AppShell suite passed 11/11, frontend typecheck passed, and the
  production build passed. The failed candidate attempt remains historical and
  is not represented as a full-gauntlet PASS.
- The next complete candidate attempt, bound to review digest
  `8a3e5bf647ed0be78dc5826001c98123b889ed0fc3a65ffd2df36eddf2bca46a`
  and final-mode digest
  `30728d19029d1db0c7f91841ba47d9a0f18543c58e57740c3185878844ffc302`,
  reached the real browser smoke but failed because a page-global Escape
  dispatch left the Navigation dialog visibly `data-state=open` for the full
  five-second assertion window. The human graded this behavioural Medium as
  VF-SEC-017. Commit `e6c88d9` then strengthened the existing RED to four cycles
  at 768px and four at 375px and dispatched Escape through the dialog's sole
  visible focused control, but made no production-source correction. That
  harness-only attempt was insufficient: the exact candidate run preserved at
  `/tmp/verboflex-phase01-round2.8TTofh/candidate-nav.log` failed again at the
  768px second cycle, with the focused-control Escape dispatched and the sheet
  still visibly `data-state=open` for the full five-second window. This was the
  same unresolved VF-SEC-017, not a new finding, and neither failed candidate is
  represented as a full-gauntlet PASS.
- Commit `7f93715` is the production GREEN for VF-SEC-017. `AppShell` now owns
  Sheet open state independently from Tooltip open state and forces the
  icon-control tooltip closed whenever the Sheet opens, while retaining the
  official tooltip for the icon-only trigger. The focused AppShell suite proves
  two open/Escape cycles, absence of the tooltip inside the open Sheet, real
  dialog closure, and trigger-focus restoration. The unchanged strengthened
  E2E still performs all eight focused-control cycles. The browser-only staging
  run at
  `/tmp/verboflex-phase01-round2.8TTofh/navigation-green-component.log` passed
  all eight cycles and scoped cleanup. This is not test gaming: the separate
  `e6c88d9` candidate supplied the exact failing RED, no assertion was weakened,
  no production behavior was mocked, and no retry, wait, skip, or timeout
  inflation was introduced.
- The reported cleanup/unbound concern was human-graded as a false positive.
  A production-identity execution of the real `changed_line_coverage` function
  exited zero, ran cleanup, and left no `verboflex-gauntlet-postgres-*` or
  `verboflex-gauntlet-redis-*` container and no Celery gauntlet worker. An
  earlier invalid direct-source probe had changed `$0` and therefore resolved
  `REPO_ROOT` to the parent directory; its failure is not production evidence,
  and its two exactly named containers were removed before the valid probe.
- The detect-secrets line drift was human-graded behavioural and resolved by
  rebinding only nine line numbers. The policy still contains exactly 23 rows;
  every path, plugin, hashed fingerprint, classification, and both negative
  controls remain unchanged. No file-wide, plugin-wide, count-only, or other
  waiver was added.

### Exact equivalent-mutant decision and proof

The human-approved disposition is exact and narrow: only
`logout_rate_limit_user_id__mutmut_18` (`join(User, None)`) and
`logout_rate_limit_user_id__mutmut_20` (`join(User)`) are equivalent mutants.
SQLAlchemy 2.0.52 infers the sole `AuthSession.user_id -> User.id` foreign-key
relationship for both variants. With the PostgreSQL dialect, the explicit
production join and both variants compile byte-identically and contain exactly
one `JOIN users ON users.id = auth_sessions.user_id`. The deliberately
divergent `join(User, true())` control compiles `JOIN users ON true` and is
rejected.

The production mutation gate requires exactly 893 total verdicts: exactly 891
non-equivalent mutants killed, exactly the two named survivors, and zero
`no_tests`, skipped, suspicious, timeout, interrupted, segfault, or other
unclassified verdicts. Exact-result controls reject a missing survivor, any
additional survivor, 890/3 statistics, a broadened mapping row, and a diff that
changes anything beyond the two reviewed join forms. The source manifest binds
`tools/gauntlet.sh`, `tools/equivalent_mutants.txt`, and
`tools/verify_equivalent_mutants.py` through the `tools/**` verifier-script
rule, so none of the checker inputs sits outside the candidate digest.

TDD history is preserved as `3ac757c` -> `9f28dd2`: the RED commit removed the
prior `Select.join` monkeypatch/spelling test and required the new fail-closed
checker self-test; the GREEN commit added the exact mapping, compiled
PostgreSQL proof, divergent control, fresh 891/2/893 statistics contract, and
diff binding. The structural monkeypatch test is not used. Focused PostgreSQL
auth/logout selection still passes 7/7, and the mutation contract retains all
891 substantive non-equivalent kills rather than waiving the three meaningful
logout-query mutations adjacent to the two equivalent join spellings.

### Phase B — complete post-fix candidate gauntlet

**PENDING.** A complete gauntlet must run against the exact reviewed digest
above. Only after unchanged-source evidence and an independent closure check may
this artifact be promoted to CLOSED/PASS. Evidence from an earlier source
digest is historical and is not reused as current closure evidence.

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
| VF-SEC-002 | Medium | RESOLVED | Candidate metadata is single-valued, OPEN/PENDING, and bound to the exact current review digest. `source_state.sh` separately enforces candidate and closure states, preventing either artifact state from masquerading as the other; the closure contract has not been invoked for this digest. |
| VF-SEC-003 | Medium | RESOLVED | The current FastAPI OpenAPI export is byte-identical to `frontend/openapi.json`; generated client drift is checked and the controlled OpenAPI mutation is restored before the real comparison. Auth request limits and response/security contracts are present in the committed schema. |
| VF-SEC-004 | Medium | RESOLVED | Real-smoke and adversarial tools use private temporary directories/files, generated one-run secrets, explicit timeouts, exact Compose project/image identifiers, stdin/getpass secret entry, scoped cleanup traps, and preflight negative controls. No review-owned container or temporary secret artifact remained. |
| VF-SEC-005 | Medium | RESOLVED | Backend mutation scope is the nine handwritten auth/session modules listed in `backend/pyproject.toml`; frontend scope is `frontend/src/features/auth/session.tsx` with threshold 100. Freshness, zero-result, property-attribution, exact-range, and verdict fail-closed controls passed their packaged self-tests. Full mutation execution for this digest remains part of the pending post-fix gauntlet. |
| VF-SEC-006 | Medium | RESOLVED | Compose exposes application ports on loopback only and does not publish PostgreSQL/Redis. The runbook requires a trusted TLS edge, TLS 1.2/1.3, HTTP redirect or unreachability, HSTS, hostname/certificate validation, and loopback-only forwarding. Live edge proof remains a separate later gate. |
| VF-SEC-007 | Low | OPEN | One Moderate npm advisory is confined to the dev-only `typed-rest-client -> qs` chain. Backend and frontend runtime audits are clean; explicit ship-time disposition is retained. |
| VF-SEC-008 | Medium | RESOLVED | Login and refresh emit only `__Host-verboflex_refresh` with `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, and no `Domain`; temporary login emits no refresh cookie. Logout and password change delete the same exact host cookie scope. Tests and smoke reject legacy `__Secure-verboflex_refresh`, unprefixed names, wrong path, or Domain. |
| VF-SEC-009 | Medium | RESOLVED | Logout resolves the presented session, locks it, and revokes every member of its server-owned family. The R0 -> R1 test and real smoke prove both pre-rotation A1 and successor A2 fail with the exact 401 after logout; repeated logout returns the same empty 204 and matching deletion cookie. |
| VF-SEC-010 | Medium | RESOLVED | Refresh limiting derives identity from durable `AuthSession.family_id` plus the validated peer IP. R1/R2 share a key; all malformed or unknown tokens collapse to `invalid-refresh-session` plus IP; real-family and sentinel keys differ and raw authority is absent from Redis keys. Request 31 returns exact 429 before rotation, and invalid Redis state/outage returns exact 503 without mutation or successor cookie. |
| VF-SEC-011 | Medium | RESOLVED | Login username/password/client_id/client_secret/scope limits are enforced by FastAPI form parsing; password-change current/new limits are checked before bearer decoding, Redis evaluation, durable mutation, or Argon2. The committed OpenAPI publishes 320/128/320/128/1024 and 128/128 maxima. Independent request probes returned 422 for all five oversized login/OAuth cases with zero Redis calls, and focused password-change tests preserve the exact stable 422 envelope and durable state. |
| VF-SEC-012 | Medium | RESOLVED | Packaged checker self-tests run in an isolated subshell with a private temporary layer record and cannot mutate caller-owned `LAYER_RECORD`. The archived RED source at `7002e0f` failed with `packaged checker self-tests modified the caller-owned layer record`; the reviewed source passes the same isolation probe. |
| VF-SEC-013 | Medium | RESOLVED | Logout assigns the durable user-global budget only when the presented refresh session is unused, unrevoked, unexpired and belongs to an active user. Used, revoked, expired, inactive-user, malformed, and unknown credentials use the anonymous sentinel plus validated peer, preventing a stale credential from draining a live user's global logout quota. The archived RED source at `01cae15` failed all four stale-state probes; the reviewed source passes them while retaining empty 204 idempotence and family-wide revocation for live authority. |
| VF-SEC-014 | Medium | RESOLVED | Frontend production changed-line branch coverage now consumes normalized Cobertura rather than branch-permissive LCOV, binds exclusions to the exact four-row source-owned map, rejects non-canonical paths, vacuous/zero totals, extra handwritten exclusions, and a concrete 50%-branch divergent fixture. The production path passed at 100% for 152 frontend lines; backend changed-line coverage passed at 100% for 1003 lines. |
| VF-SEC-015 | Medium | RESOLVED | Source-bound TDD additions moved nine accepted detect-secrets findings. The exact policy was updated only at those nine line coordinates; all 23 paths/plugins/fingerprints and classifications are preserved byte-for-byte, a fresh repository scan matches exactly, and true-key plus unreviewed-tuple controls still fail as required. |
| VF-SEC-016 | Medium | RESOLVED | The candidate gauntlet exposed TS2345 for deferred `readSystemStatus` responses because bare `ReturnType` retained an over-broad generic result. The test-only fix specializes the generated call to `<false>`, exactly matching the production call site's SDK default. AppShell 11/11, `tsc --noEmit`, and the Vite production build pass with no broad cast and no production-source change. |
| VF-SEC-017 | Medium | RESOLVED | Human-graded behavioural navigation-overlay failure. The first harness-only correction at `e6c88d9` strengthened the RED to four focused-control Escape cycles at each of 768px and 375px but failed again at the 768px second cycle, leaving the live Sheet `data-state=open` for five seconds; the finding therefore remained open. Production GREEN `7f93715` gives Sheet and Tooltip separate controlled authority and forces the tooltip closed as the Sheet opens while preserving the official icon tooltip. AppShell 11/11 proves two open/Escape cycles, no tooltip inside the open Sheet, real closure, and trigger-focus restoration; the browser-only staging component run passed the unchanged eight-cycle E2E and cleanup. No retry, wait, skip, weakened assertion, mock, or timeout change was introduced. The failed candidates remain historical; no full-gauntlet PASS is claimed. |

## Plan 01-15 fix revalidation

| Fix | Result | Source-bound evidence |
| --- | --- | --- |
| F-01 | PASS | Login/refresh set, and logout/password-change delete, only the hard-coded `__Host-verboflex_refresh` cookie with Secure, HttpOnly, SameSite=Lax, Path=/ and no Domain. |
| F-02 | PASS | `backend/.python-version` is bound into the source manifest and the manifest negative control rejects its omission or mutation. |
| F-03 | PASS | Frontend changed-line coverage canonicalizes Cobertura source paths, enforces exact approved exclusions, and fails closed for a vacuous, unresolved, or partially covered branch set; packaged and production-path probes passed. |
| F-04 | PASS | Backend mutation execution requires a fresh isolated workspace and rejects missing, zero-total, or stale statistics; the mutation-freshness self-test passed. |
| F-05 | PASS | Property-only mutation attribution is source-bound by `tools/mutmut-property.toml`, and the frontend reducer range is exact; the property-mutation self-test passed. |
| F-06 | PASS | Packaged checker self-tests are mandatory in the candidate/full gauntlet sequence and are isolated from caller state; both sequence and isolation self-tests passed. |
| F-07 | PASS | Admin deactivation atomically marks the user inactive, increments token version, and revokes every still-live session without rewriting prior revocation timestamps; focused PostgreSQL coverage passed. |
| F-08 | PASS | Live sessions of active users share a durable user-global logout budget across session and client address; stale/invalid authority uses the anonymous peer-bounded budget and cannot exhaust that user-global key. |

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
  browser cookie, and revokes the complete durable refresh family when live
  authority resolves. Missing, malformed, unknown, used, revoked, expired,
  inactive-user, repeated, and valid logout responses remain non-enumerating
  empty 204 responses when not rate-limited, preserving idempotence.

### Rate limits and bounded work

- Login is limited at 5/minute per normalized-email plus validated peer IP;
  refresh at 30/minute per stable family/sentinel plus IP; logout at 10/minute,
  using a durable user-global key across all live sessions and client addresses
  only for active users, and otherwise the anonymous sentinel plus validated
  peer; password change at 10/minute per cryptographically verified user plus
  IP; ordinary reads at 120/minute per durable principal; health at 60/minute
  per validated peer.
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

The scanner's exact source-bound policy and its true-key and unreviewed-tuple
negative controls passed. Dependency lockfiles and `.planning/` are outside the
normal scanner command line; those scope exclusions are not policy waivers for
any of the 23 entries below.

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
| 9 | `src/verboflex/auth/refresh_sessions.py|20|Base64 High Entropy String|e582429052cdb908833560f6f7582d232de37c4d` | False positive: the literal public base64url alphabet used for syntax validation, not generated authority. |
| 10 | `tests/api/test_rate_limits.py|189|Secret Keyword|5ac066cfb3bcf9973a0b40daeb7f5606103c1bd3` | False positive: local HTTP password fixture. |
| 11 | `tests/api/test_system_status.py|109|Basic Auth Credentials|e5e9fa1ba31ecd1ae84f75caaa474f3a663f05f4` | False positive: deliberately fake database URL inside a redaction test; the test proves it is not exposed. |
| 12 | `tests/auth/test_bootstrap_admin.py|137|Secret Keyword|985a4d67132193977275067aca18c13f8c8371c8` | False positive: isolated bootstrap password fixture. |
| 13 | `tests/auth/test_bootstrap_admin.py|148|Secret Keyword|d36b093dec485bfd20ef697ca6c1ad79e1ac9210` | False positive: isolated second-bootstrap password fixture. |
| 14 | `tests/auth/test_bootstrap_admin.py|236|Secret Keyword|3da24dfed48aa2721da14e6f79e588440b934675` | False positive: isolated reset-password fixture. |
| 15 | `tests/auth/test_bootstrap_admin.py|296|Secret Keyword|028e59d8204d08fecd6aad12434b872fe4319f6d` | False positive: isolated replacement-password fixture. |
| 16 | `tests/auth/test_bootstrap_admin.py|411|Secret Keyword|5d9dec21ffdbb45c64f0ea2b1abf3b25c2afc728` | False positive: isolated unknown-account reset fixture. |
| 17 | `tests/auth/test_bootstrap_admin.py|586|Secret Keyword|1123e04e3b43d460543f1b0bf94e67a0a636b2cc` | False positive: in-memory secret-reader fixture proving CLI input routing. |
| 18 | `tests/auth/test_bootstrap_admin.py|689|Secret Keyword|cdd076c21ce35f40d40b6c16d12bd40876050a6f` | False positive: in-memory protected-input fixture. |
| 19 | `tests/auth/test_bootstrap_admin.py|767|Secret Keyword|18468712bc6eede8cb7adf8932b073bf56773a11` | False positive: explicit `non-secret-test-hash` rollback fixture. |
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
| Canonical review digest, two consecutive immediate pre-write runs | PASS — exact `14f4e2795d168b488a33a9fca1a8a8fe746d0ec9df29dd640ab883a98427f709` twice |
| Canonical manifest resolution | PASS — 161 clean paths across every required review-mode category |
| Exact equivalent-mutant gate | PASS — exact 891 killed plus the two named equivalent joins out of 893; extra/missing mappings, 890/3 statistics, broadened mapping, and divergent diff controls failed as required; byte-identical PostgreSQL SQL and `JOIN users ON true` negative control passed |
| Equivalent-gate TDD and focused auth behavior | PASS — `3ac757c` removed the forbidden structural join monkeypatch and introduced RED; `9f28dd2` supplied GREEN; focused PostgreSQL auth/logout selection passed 7/7 |
| Manifest self-test | PASS |
| Packaged gauntlet, real-smoke, and adversarial-auth self-tests | PASS |
| Packaged checker sequence/isolation self-tests | PASS — mandatory invocation and private layer-record ownership enforced |
| Frontend coverage, mutation freshness, and property-mutation self-tests | PASS — exact exclusion-map, Cobertura path, vacuity, partial-branch, stale-result, and survivor controls rejected as required |
| VF-SEC-012 archived RED probe | PASS — source at `7002e0f` exited 1 with caller-layer-record corruption; reviewed source passes |
| VF-SEC-013 archived RED probe | PASS — source at `01cae15` failed exactly the used, inactive-user, revoked, and expired stale-token cases |
| Current PostgreSQL cookie/deactivation/logout selection | PASS — 23/23, including exact set/delete cookie scope, live user-global budget, four anonymous peer-bounded stale states, deactivation, family revocation, and idempotence |
| Ruff lint and format | PASS — lint clean; 58 files already formatted |
| Backend typing | PASS — mypy checked 36 source files |
| Production changed-line coverage and cleanup | PASS — packaged Cobertura normalization, exact four-row exclusions, non-vacuity, and concrete partial-branch controls passed on the current source; the prior production-identity run passed backend 100% over 1003 lines and frontend 100% over 152 lines and left no gauntlet container or Celery worker. The current delta spans production `AppShell.tsx`, its unit coverage, and the strengthened E2E, and supplies no new RED evidence against cleanup, so the human-graded cleanup false positive is not reopened. |
| Frontend AppShell unit focus | PASS — 11/11 on the current digest; the earlier complete 75/75 candidate unit run remains historical rather than a current full-gauntlet claim |
| Frontend typecheck and production build | PASS — generated `ThrowOnError = false` result shape is accepted without broad casts; Vite transformed 1948 modules |
| Responsive navigation regression | PASS — the strengthened harness-only RED at `e6c88d9` reproduced VF-SEC-017 at the 768px second focused-control cycle. Production GREEN `7f93715` separates Sheet/Tooltip authority; AppShell 11/11 proves two reopen/Escape cycles and tooltip exclusion, and the browser-only staging component run exercised four cycles at each of 768px and 375px with one visible focused control, real dialog closure, and trigger focus restoration. No wait/retry/timeout inflation. |
| Detect-secrets exact policy | PASS — 23/23 exact tuple match |
| Detect-secrets true-key and unreviewed-tuple negative controls | PASS — both failed as required |
| Backend dependency audit | PASS — no known vulnerability in published packages |
| Frontend production dependency audit | PASS — zero vulnerabilities |
| Frontend complete dependency audit | EXPECTED LOW DEBT — VF-SEC-007 only |
| Full post-fix candidate gauntlet | PENDING — preceding attempts exposed the resolved TS2345 and navigation-dispatch findings; no PASS is claimed for this digest |
| Independent closure check | PENDING — artifact remains OPEN/PENDING |

## Final disposition

- Critical / High / Medium / Low: **0 / 0 / 0 / 1**
- Open Critical/High: **0**
- Candidate verdict: **PASS_FOR_POST_FIX_GAUNTLET**
- Closure verdict: **PENDING**
- Full-gauntlet status: **PENDING**
- Review status: **OPEN**

VF-SEC-007 remains deliberately visible and open at Low severity. Its ship-time
disposition is mandatory: upgrade the development dependency chain or record a
time-bounded risk acceptance, then rerun the dependency audit. This candidate
review neither closes that debt nor substitutes for the pending complete
post-fix gauntlet, independent closure check, or future live deployment/TLS
evidence required by the release process.
