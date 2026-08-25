# Phase 1 Fresh-Context Security Candidate Review

- Review-status: OPEN
- Open-critical-high: 0
- Full-gauntlet-status: PENDING
- Reviewed-source-digest: `effffb6ecc6fa115b02d93970c01e761ac5d41edc206e327055fa8291388bcf4`
- Review-date: 2026-08-25
- Reviewer-context: independent fresh-context security reviewer; no builder conversation or reasoning read
- Candidate-verdict: PASS_FOR_POST_FIX_GAUNTLET
- Critical: 0
- High: 0
- Medium: 0
- Low: 1

## Candidate conclusion

The reviewed source is a valid security candidate for the post-fix gauntlet. No critical,
high, or medium finding remains open. `VF-SEC-009` is resolved in implementation, focused
tests, mutation testing, and the real staging smoke: logout revokes the complete refresh
family, and both the pre-rotation access token A1 and successor access token A2 receive 401.

This artifact deliberately remains **OPEN** and does not claim the full gauntlet passed.
`Full-gauntlet-status` remains **PENDING** until the source-bound post-fix candidate gauntlet
runs from its first layer against this exact digest. The only open item is the previously
known low, development-only dependency debt `VF-SEC-007`; it is non-blocking for candidate
validation but remains mandatory to resolve or explicitly own before ship.

## Fresh-context scope and source identity

The review used only the approved Phase 1 contract (`01-SPEC.md` and `01-14-PLAN.md`), the
canonical `tools/source_manifest.txt`, the exact manifest-resolved source and tests, the
source-bound deployment contract, and earlier summaries only as an index. The previous
review artifact was consulted only to reconcile the stable identifiers `VF-SEC-001` through
`VF-SEC-009`; builder discussion and reasoning were not read.

Before any review artifact write, the canonical command returned the exact expected digest:

```text
$ bash tools/source_state.sh --review-digest
effffb6ecc6fa115b02d93970c01e761ac5d41edc206e327055fa8291388bcf4
```

The same digest was reproduced after focused tests, real staging smoke, dependency audits,
and mutation runs. The review-mode source is clean; the pre-existing untracked
`.planning/milestone.lock` was neither read nor modified. The candidate artifact itself is
outside the canonical review digest and is the only repository file written by this review.

## Findings

### Open

#### VF-SEC-007 — development-only `typed-rest-client -> qs` advisory

- **Severity:** low in the VerboFlex Phase 1 threat model; npm reports the upstream advisory
  as moderate.
- **Status:** OPEN, NON-BLOCKING FOR CANDIDATE, BLOCKING BEFORE SHIP WITHOUT DISPOSITION.
- **Evidence:** `npm audit --omit=dev --json` reports 0 vulnerabilities. Full `npm audit
  --json` reports 0 critical, 0 high, 2 moderate entries representing one transitive path:
  `typed-rest-client -> qs`. The affected package is not in the production dependency graph
  or runtime container.
- **Risk:** development tooling could be exposed to the `qs.stringify` denial-of-service
  condition if an affected code path processed attacker-controlled comma-format arrays with
  `encodeValuesOnly`; no such production Phase 1 path exists.
- **Required pre-ship action:** upgrade/override to a compatible fixed graph, or record a
  dated owner, expiry, and explicit risk decision followed by re-review. This review grants
  no waiver.

### New critical/high/medium findings

None.

## VF-SEC resolution and verification matrix

| ID | Severity | Candidate status | Independent verification evidence |
| --- | --- | --- | --- |
| `VF-SEC-001` | high | RESOLVED | `tools/source_manifest.txt` covers backend/frontend production and tests, config, lockfiles, migrations, verifier scripts, `docs/phase-01-smoke.md`, and the persisted source review. `source_state.sh --self-test-manifest` and gauntlet preflight passed; empty required categories and included-file changes fail closed. |
| `VF-SEC-002` | high | RESOLVED | `source_state.sh` requires exactly one review status/count/digest and the candidate contract requires `OPEN`, zero critical/high, and `PENDING`; duplicate, stale, and false-PASS controls fail. `gauntlet.sh --self-test-candidate-contract` passed. |
| `VF-SEC-003` | high | RESOLVED | The OpenAPI negative control mutates a real route symbol, requires observed generated drift, restores source/client bytes, and fails for the expected reason before the positive drift check. Preflight sensitivity passed. |
| `VF-SEC-004` | high | RESOLVED | `real_smoke.sh` created one uniquely named staging Compose project, propagated the single adversarial harness exit status, passed end-to-end, then removed its containers, volumes, images, and protected temporary files. No matching resource remained after cleanup. |
| `VF-SEC-005` | medium | RESOLVED | Backend mutation scope includes handwritten auth/session/rate-limit/config logic. Current run reported 741 killed, 0 survived/timed-out/suspicious, including a fresh execution of all four new `revoke_refresh_session` mutants. Stryker mutated `session.tsx`: 153 killed, 0 survived/no-coverage/error, 100.00% score at a 100% break threshold. |
| `VF-SEC-006` | medium | RESOLVED | `deployment-contract` is a required manifest category and `tools/tests/test_source_state.sh` proves a `docs/phase-01-smoke.md` mutation invalidates review identity. Staging/production application ports inherit loopback-only publication; the runbook requires trusted TLS 1.2/1.3, HTTP redirect or unreachability, one-year HSTS, and loopback-only origin forwarding. Environment-specific certificate/HSTS observation remains an explicit later edge-smoke obligation, not a claim of this review. |
| `VF-SEC-007` | low | OPEN, NON-BLOCKING | Runtime npm graph and Python audit have no known vulnerability; the full npm development graph retains the `typed-rest-client -> qs` advisory described above. |
| `VF-SEC-008` | medium | RESOLVED | The only application cookie name is exact `__Host-verboflex_refresh`. Set and delete use unconditional `Secure`, `Path=/`, `HttpOnly`, `SameSite=Lax`, and no `Domain`. Login, refresh, logout, password-change tests and real/adversarial smoke use the host cookie and reject legacy `verboflex_refresh`/`__Secure-verboflex_refresh` emission. |
| `VF-SEC-009` | medium | RESOLVED | `revoke_refresh_session` locks the presented session and updates every non-revoked row with the same server-owned `family_id`. `test_logout_after_rotation_invalidates_every_access_token_in_the_family` proves both A1 and A2 are 401 and all family rows revoked. The real staging flow independently passed `pre-rotation-revoked-access=401` and `successor-revoked-access=401`; the four generated revocation mutants were killed. |

## Adversarial security checks

### Host cookie and legacy authority

- `backend/src/verboflex/api/v1/routes/auth.py` owns one constant:
  `__Host-verboflex_refresh`.
- Both `set_cookie` and `delete_cookie` unconditionally emit `Secure`, `Path=/`,
  `HttpOnly`, and `SameSite=Lax`; no `Domain` argument exists.
- Temporary/password-change-only login emits no refresh cookie. Ordinary login and refresh
  emit only the host cookie. Logout and password change delete only that exact host cookie.
- Backend tests assert the exact attributes and reject the legacy unprefixed, `__Secure-`,
  and old narrow-path variants. Real smoke repeats the header-level checks.

### Origin and CORS

- Cookie-authenticated refresh/logout validate a present `Origin` against the exact configured
  scheme/host/port allowlist before Redis or PostgreSQL mutation.
- Hostile Origin receives exact 403 `{"detail":"Origin not allowed"}` and cannot rotate or
  revoke authority.
- FastAPI CORS credentials are enabled only with the concrete configured origins; methods and
  headers are bounded and no credentialed wildcard is emitted. CORS unit tests and real
  adversarial smoke passed.

### Rotation, reuse, concurrency, and logout family semantics

- Refresh tokens are 32-byte URL-safe opaque values; only SHA-256 hashes are persisted.
- Rotation locks the predecessor row, marks it used, creates one same-family successor, and
  binds A2 to the successor session.
- Reuse of a consumed predecessor revokes the whole family. Real PostgreSQL concurrency tests
  require exactly one 200 and one 401 and leave every family member revoked.
- Logout now revokes the complete family named by the presented current cookie. Lock ordering
  makes refresh/logout races fail closed: logout-first makes refresh reject revoked state;
  refresh-first commits the successor before family revocation sees and revokes it.
- Real smoke proved A1 and A2 both unusable after logout, not merely the successor.

### Rate limits and Redis failure policy

- Login is limited before password verification using a hash of normalized email and the
  server-observed client IP; raw authority is not stored in Redis keys.
- Refresh, logout, and password change use hashed identities and their approved 30/10/10
  limits. Exhaustion returns positive `Retry-After` and `X-RateLimit-Remaining: 0`.
- Login, refresh, and password change fail closed when Redis is unavailable. Logout remains
  available to remove authority, and anonymous health remains bounded by a capped local
  limiter. Focused tests, adversarial self-tests, and real smoke passed.

### Secret and audit-output redaction

- Smoke/adversarial scripts never enable shell tracing and do not print generated passwords,
  JWT secrets, refresh cookies, bearer tokens, or Authorization headers.
- Runtime directories are mode 700; environment, login, and password-change files are mode
  600; HTTP bodies/headers stay in those isolated directories and are removed by traps.
- CLI password input is stdin/getpass only, never a normal command-line argument, and success
  or error output does not echo the supplied secret.
- Redis rate-limit keys hash raw identity/cookie material. API error bodies remain bounded and
  non-enumerating. The real smoke and adversarial harness completed without secret output.

### Source binding and TLS/HSTS boundary

- The digest is computed from sorted path/content hashes across every required manifest
  category and rejects untracked, staged, unstaged, missing, or empty included source.
- `docs/phase-01-smoke.md` is a required `deployment-contract`, so TLS/HSTS contract edits
  invalidate the review digest; the negative control passed.
- Staging/production are explicitly application-origin stacks behind a managed edge, with
  plaintext container ports published only to `127.0.0.1`. The edge must enforce trusted
  TLS 1.2/1.3, HTTP redirect or unreachability, and
  `Strict-Transport-Security: max-age=31536000; includeSubDomains`.
- This review verifies the repository boundary and source binding only. It does not claim an
  environment-specific certificate or HSTS observation.

## Verification record

| Check | Result |
| --- | --- |
| `bash tools/source_state.sh --review-digest` before review | PASS; exact expected digest |
| source manifest self-test and gauntlet preflight | PASS |
| candidate contract and mutation-verdict negative controls | PASS |
| real-smoke and adversarial preflights/self-tests | PASS |
| focused auth/CORS/rate tests without required PostgreSQL fixture | 29 passed; 38 setup errors due only to absent `127.0.0.1:55432`; superseded by isolated real-stack and mutation PostgreSQL runs |
| `bash tools/real_smoke.sh` | PASS; browser 1/1, adversarial PASS, A1 401, A2 401, Celery result 5, cleanup complete |
| backend mutation | PASS; 741 killed, zero non-equivalent survivors; all four new family-revocation mutants freshly killed |
| frontend Stryker | PASS; 153 killed, 0 survived/no-coverage/error, score 100.00% |
| `uv run pip-audit` | PASS; no known vulnerabilities (local project is correctly not a PyPI dependency) |
| `npm audit --omit=dev --json` | PASS; runtime 0 critical/high/moderate/low |
| full `npm audit --json` | EXPECTED DEBT; development-only `typed-rest-client -> qs` path, recorded as `VF-SEC-007` |
| `bash tools/source_state.sh --review-digest` after verification | PASS; unchanged exact expected digest |
| complete `tools/gauntlet.sh --post-fix-candidate` | PENDING; intentionally not claimed by this candidate review |

## Final candidate status

Open findings: **0 critical, 0 high, 0 medium, 1 low**.

Security candidate verdict: **PASS_FOR_POST_FIX_GAUNTLET**. Review closure and a full-gauntlet
PASS are explicitly withheld until the separate post-fix candidate gauntlet completes against
the exact reviewed source state.
