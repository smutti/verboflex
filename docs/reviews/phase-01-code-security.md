# Phase 1 Fresh-Context Code and Security Review Candidate

- Review-status: OPEN
- Open-critical-high: 0
- Full-gauntlet-status: PENDING
- Reviewed-source-digest: `fcb8b0839fb83f57d1934d85f4aa302480b2134c7ef0dfb788de50bac4929612`
- Review-date: 2026-08-25
- Reviewer: independent fresh-context Phase 1 code/security reviewer
- Critical: 0
- High: 0
- Medium: 2
- Low: 1

## Candidate status

This is a post-fix review **candidate**, not a closed review. No critical or high
finding remains open in the reviewed source state, but the complete post-fix
candidate gauntlet has **not** been executed. `Full-gauntlet-status` therefore
remains `PENDING`, `Review-status` remains `OPEN`, and this artifact makes no
full-gauntlet PASS claim. The final review may become `CLOSED` only after the
source-bound candidate workflow completes and any subsequently changed source is
reviewed under its new digest.

## Fresh-context method and source identity

The independent review was completed before the previous contents of this artifact
were read. Initial context was limited to the approved Phase 1 SPEC,
`tools/source_manifest.txt`, the exact review-mode source tree resolved from that
manifest, and summaries `01-02-SUMMARY.md` through `01-13-SUMMARY.md`. Builder
conversations were not consulted. Only after independent correctness, regression,
security-boundary, dependency, verifier, and ASVS analysis was complete was the
previous artifact opened to reconcile `VF-SEC-001` through `VF-SEC-007`.

The required independent digest check reproduced the expected candidate identity:

```text
$ tools/source_state.sh --review-digest
fcb8b0839fb83f57d1934d85f4aa302480b2134c7ef0dfb788de50bac4929612
```

Review mode resolved 145 unique paths and 33,669 lines. Category membership (a
path may belong to both implementation and tests) was:

| Category | Resolved entries |
| --- | ---: |
| Implementation | 88 |
| Tests | 33 |
| Configuration | 18 |
| Lockfiles | 3 |
| Migrations | 4 |
| Verifier scripts | 9 |

The review artifact is deliberately excluded from the review digest. The reviewed
tree covered the FastAPI routes and services, JWT and refresh-session authority,
password change and bootstrap flows, database models/migration, Celery/Redis
boundaries, React session state and generated API client, frontend unit/E2E tests,
Compose/Docker/nginx configuration, lockfiles, and all verifier scripts.

## Review approach

The review traced each of the seven Phase 1 endpoints through request validation,
authentication, durable authority, persistence, response/cookie behavior, and
frontend consumers. It inspected forced-password-change restrictions, access-token
claim validation, refresh rotation and replay-family revocation, logout and
password-change invalidation, transaction/concurrency behavior, Redis fail-closed
rate limits, exact Origin enforcement, CORS, data/role boundaries, generated
OpenAPI drift, container exposure, cleanup ownership, source/digest enforcement,
and backend/frontend mutation scope and verdict handling.

Focused controls executed during review were limited to non-final diagnostics:

- `tools/source_state.sh --review-digest` matched the expected digest.
- The source-manifest, infrastructure-lifecycle, mutation-verdict, and candidate-
  contract self-tests passed.
- `uv lock --check` resolved 111 packages and found the Python lock current.
- `pip-audit` found no known third-party Python vulnerabilities and skipped only
  the local non-PyPI `verboflex` project.
- `npm audit --omit=dev --audit-level=low` found zero runtime vulnerabilities.
- The full npm audit reported the development-only records described in
  `VF-SEC-007`.

These focused results are not a substitute for
`tools/gauntlet.sh --post-fix-candidate`, which was not run by this reviewer.

## OWASP ASVS 5.0.0 Level 1 mapping

All 70 Level 1 requirements in the official
[OWASP ASVS 5.0.0 release](https://github.com/OWASP/ASVS/tree/v5.0.0)
were screened for applicability to the Phase 1 slice.

| ASVS L1 area | Phase 1 application | Review result |
| --- | --- | --- |
| `V1.2.1`-`V1.2.5`, `V1.3.1`-`V1.3.2` | Context-safe React rendering, JSON responses, ORM queries, no dynamic execution | PASS for the current inputs and output sinks |
| `V1.5.1`, `V5.2.1`-`V5.3.2` | XML/file upload and file-path handling | Not applicable to the Phase 1 platform-foundation endpoints |
| `V2.1.1`, `V2.2.1`-`V2.3.1` | Pydantic/service validation and ordered auth flows | PASS; security decisions are enforced server-side |
| `V3.2.1`-`V3.2.2` | Browser response context and text rendering | PASS for current JSON/static-text surfaces; external-edge hardening remains coupled to `VF-SEC-006` |
| `V3.3.1` | Secure cookie naming and attributes | PARTIAL: Secure/HttpOnly/SameSite/path are enforced, but the mandatory prefix is missing (`VF-SEC-008`) |
| `V3.4.1`-`V3.5.3` | HSTS, CORS, CSRF/origin, and safe HTTP methods | CORS/origin/method controls PASS; HSTS evidence remains OPEN (`VF-SEC-006`) |
| `V4.1.1` | Correct API media types and contract drift | PASS; deterministic OpenAPI negative control is source-changing and restoration-checked |
| `V4.4.1` | WebSocket TLS | Not applicable; no WebSocket surface exists |
| `V6.1.1`, `V6.2.1`-`V6.4.2` | Password policy/change, exact verification, masking, anti-automation, account defaults | PASS against the approved Phase 1 password/rate-limit contract; no registration, hint, activation-code, or secret-question flow exists |
| `V7.2.1`-`V7.4.2` | Backend session verification, rotation, expiry, replay, and termination | PASS; durable token-version and refresh-family invalidation are backend-authoritative |
| `V8.1.1`-`V8.3.1` | Function/data authorization | PASS for the current status/auth slice; role authority is resolved by the backend |
| `V9.1.1`-`V9.2.1` | JWT signature, algorithm/key source, and time claims | PASS with strict claim and algorithm allowlisting |
| `V10.4.1`-`V10.4.3` | Redirect URI and authorization-code behavior | Not applicable; Phase 1 has no redirect/code flow |
| `V10.4.4` | Grant restriction | Documented design deviation: the approved Phase 1 SPEC mandates the first-party OAuth2 password-token flow; no broader authorization-server grant surface is exposed |
| `V10.4.5` | Refresh replay mitigation | PASS; one-time rotation and family revocation are transactionally enforced and concurrency-tested |
| `V11.3.1`-`V11.4.1` | Approved cryptography/hash primitives | PASS for Argon2, HMAC/JWT, SHA-256 token hashing, and CSPRNG tokens |
| `V12.1.1`, `V12.2.1`-`V12.2.2` | TLS versions, HTTPS-only external service, trusted certificates | OPEN at the external ingress evidence boundary (`VF-SEC-006`) |
| `V13.4.1` | Source-control metadata exposure | PASS for reviewed runtime images/configuration |
| `V14.2.1`, `V14.3.1` | Secret transport and client-side auth-data clearing | PASS; tokens are not placed in URLs/Web Storage and client auth state clears on termination/failure |
| `V15.1.1`-`V15.3.1` | Component remediation, current dependencies, response minimization | Runtime audits PASS; dev-tooling debt has the explicit `VF-SEC-007` disposition |

## Dependency audit

- Backend direct dependencies are exact-pinned and `backend/uv.lock` carries
  artifact hashes. `uv lock --check` passed and `pip-audit` reported no known
  third-party vulnerability.
- Frontend direct dependencies are exact-pinned and the package lock carries
  resolved artifact integrity. The runtime-only audit reported zero
  vulnerabilities.
- The full npm audit reports GHSA-q8mj-m7cp-5q26 through development-only
  `@stryker-mutator/core@10.0.0 -> typed-rest-client@2.3.1 -> qs@6.15.1`.
  It is not shipped in the SPA runtime; its disposition is recorded below.
- The gauntlet rejects high/critical npm advisories and audits Python packages;
  the present low-threshold dev-tool record does not satisfy the gate's blocking
  threshold.

## Findings and dispositions

| ID | Severity | Status | Disposition |
| --- | --- | --- | --- |
| `VF-SEC-001` | high | RESOLVED | Explicit Git-compatible frontend rules plus per-rule nonempty enforcement cover production and unit-test paths |
| `VF-SEC-002` | high | RESOLVED | Normal and candidate gauntlets enforce exact, duplicate-safe review metadata and current digest binding |
| `VF-SEC-003` | high | RESOLVED | OpenAPI negative control mutates an existing symbol, proves byte change/drift reason, and proves restoration |
| `VF-SEC-004` | high | RESOLVED | The real-smoke harness owns the stack and invokes adversarial auth exactly once; wrapper status propagation is tested |
| `VF-SEC-005` | medium | RESOLVED | Backend mutation scope covers handwritten stateful auth/session modules and frontend Stryker covers session state at 100% |
| `VF-SEC-006` | medium | OPEN | Plaintext services are loopback-bound, but TLS/HSTS proof is not bound into the reviewed source digest |
| `VF-SEC-007` | low | OPEN, NON-BLOCKING | Dev-tool-only advisory; remediation is required before milestone shipping, with no waiver implied |
| `VF-SEC-008` | medium | OPEN | Refresh cookie lacks the ASVS-required `__Secure-` or `__Host-` name prefix |

### VF-SEC-001 resolution verification

`tools/source_manifest.txt:6-12` now uses separate Git-compatible `.ts`, `.tsx`,
`.css`, `.test.ts`, and `.test.tsx` rules. `tools/source_state.sh:76-82` fails each
individual empty include rule, and `tools/tests/test_source_state.sh:16-22`
replays that assertion against the real manifest. Review mode resolved the current
frontend tree, including handwritten session code, generated client code, unit
tests, and E2E tests. The previous frontend omission is closed.

### VF-SEC-002 resolution verification

`tools/source_state.sh:188-235` requires exactly one value for status/count/digest,
enforces `CLOSED/0/current-digest` for the final path and
`OPEN/0/PENDING/current-digest` for the candidate path. Its negative fixtures cover
OPEN, nonzero, duplicate, missing, stale, and false candidate metadata.
`tools/gauntlet.sh:510-524` calls these contracts before recording the source digest,
and both normal and candidate workflows recheck the final source state. The review
gate now fails closed.

### VF-SEC-003 resolution verification

`tools/gauntlet.sh:404-430` changes the existing `read_health` handler name, asserts
the subject hash changed, requires `api:check` to fail on an actual generated diff,
restores both source and generated outputs under a trap, and asserts all restoration
hash/diff checks. The focused OpenAPI negative-control self-test is wired by
`tools/tests/test_gauntlet.sh:18-19`. The formerly nonexistent mutation target is
closed.

### VF-SEC-004 resolution verification

`tools/gauntlet.sh:478-507` runs only `real_smoke.sh`, exactly once, and proves both
single execution and failure-code propagation. `tools/real_smoke.sh:384-396`
invokes `adversarial_auth.sh --against-running-stack` while its uniquely named
Compose stack is alive. The invalid second direct invocation was removed. Stack and
container names/ports are per-run and loopback-bound; cleanup targets only owned
resources. The previous deterministic harness failure is closed.

### VF-SEC-005 resolution verification

`backend/pyproject.toml:73-101` now mutates access-token, identity, login, origin,
password-change, password, principal, rate-limit, and refresh-session modules and
selects logout, refresh, concurrency, password-change, login, principal, and config
tests. `frontend/stryker.config.mjs:4-22` mutates the handwritten session provider
with `related: false` and a 100% break threshold. `tools/gauntlet.sh:373-393`
rejects any nonempty surviving-mutant verdict and reruns property tests. The prior
scope omission is closed; the actual candidate mutation run remains part of the
pending full candidate gauntlet.

### VF-SEC-006 — TLS/HSTS evidence remains source-unbound

- **Severity:** medium
- **Controls:** ASVS `V3.4.1`, `V12.1.1`, `V12.2.1`, `V12.2.2`; Phase 1 TLS
  termination boundary
- **Evidence:** `docker-compose.yml:55-60` and `:88-101` now publish backend and
  frontend only on `127.0.0.1`, so the earlier direct public-plaintext exposure is
  materially mitigated. Staging/production configure Secure cookies and HTTPS API
  origins. However, `docker/frontend.nginx.conf:1-11` still serves HTTP without
  HSTS, so TLS/HSTS must be supplied by an external ingress. The only automated
  ingress-contract assertion in `tools/tests/test_real_smoke.sh:27` is a textual
  grep for `TLS termination boundary` in `docs/phase-01-smoke.md`; that document is
  absent from `tools/source_manifest.txt` and therefore absent from this review
  digest. It can change independently of the reviewed source and does not
  demonstrate TLS versions, certificate trust, HTTP rejection/redirect, or HSTS.
- **Impact:** an operator can satisfy the source-bound candidate checks while the
  external edge contract is stale, removed, or not deployed. Loopback binding keeps
  this below high severity, but ASVS TLS/HSTS evidence is not yet auditable against
  the candidate identity.
- **Required resolution:** bind a concrete ingress/deployment contract and its
  verifier into `tools/source_manifest.txt`, then test externally that plaintext is
  unreachable or redirected, TLS 1.2/1.3 with a trusted certificate is used, and
  browser responses contain an HSTS policy of at least one year. Any fix changes
  the source digest and requires a new fresh-context review.

### VF-SEC-007 — explicit dev-tool advisory disposition

- **Severity:** low
- **Status:** OPEN, NON-BLOCKING; **not accepted as resolved and not waived**.
- **Scope:** GHSA-q8mj-m7cp-5q26 is reachable only through the development mutation
  tool chain. `npm audit --omit=dev --audit-level=low` is clean, so the affected
  package is not in the shipped SPA runtime.
- **Disposition:** this does not increment `Open-critical-high` and does not by
  itself prevent candidate validation. It **must** be upgraded/overridden to a
  compatible fixed dependency, or re-reviewed with a dated owner/risk acceptance,
  before milestone shipping. Until then it remains an open low finding; no silent
  acceptance or closure is claimed.
- **Verification:** rerun the low-threshold full npm audit and dependency
  attribution after updating the lockfile, while retaining high/critical gate
  failure behavior.

### VF-SEC-008 — refresh cookie lacks the ASVS security prefix

- **Severity:** medium
- **Control:** ASVS 5.0.0 `V3.3.1`
- **Evidence:** `backend/src/verboflex/api/v1/routes/auth.py:42`, `:49`, and `:62`
  read, set, and delete `verboflex_refresh`. The cookie correctly uses Secure in
  staging/production, HttpOnly, SameSite=Lax, and the narrow `/api/v1/auth` path,
  but its name has neither the required `__Secure-` nor `__Host-` prefix.
- **Impact:** the browser-enforced prefix invariant that prevents an insecure
  origin from setting a security-labelled cookie is absent. Existing attributes
  and loopback deployment reduce exploitability, so this is medium rather than
  high.
- **Required resolution:** consistently rename the cookie to a `__Secure-` name
  (compatible with the required narrow path), update set/read/delete behavior and
  all backend, browser, smoke, OpenAPI-adjacent fixtures, and add a negative test
  that staging/production cannot emit the legacy unprefixed name. A `__Host-` name
  is not compatible with the current `/api/v1/auth` path because that prefix
  requires `Path=/`.
- **Verification:** focused login/refresh/logout/password-change tests must assert
  the exact prefixed name and attributes, adversarial/browser smoke must rotate and
  clear it correctly, and the post-fix digest must trigger another fresh review.

## Positive boundary observations

- Access tokens are short-lived and strictly validate signature, configured
  algorithm, issuer, audience, type, subject, time claims, and durable token
  version; frontend memory is the only bearer-token store.
- Refresh tokens are opaque CSPRNG values stored only as hashes, rotate
  transactionally, and revoke their family on replay. Logout, password change, and
  authority versioning enforce durable invalidation.
- Redis-backed login/status limits and origin checks fail closed on authority-
  changing flows, while error responses remain bounded and sanitized.
- Role and data authority remain server-side; SQLAlchemy parameterization,
  constraints, and transaction boundaries avoid frontend authority and direct
  query construction.
- Staging/production reject placeholder secrets/insecure cookie mode, and Compose
  host publication is restricted to loopback.
- The generated OpenAPI/client drift control, owned smoke lifecycle, candidate
  metadata contract, source cleanliness checks, and backend/frontend mutation
  scopes now address the prior high-risk verifier failures.

## Gate conclusion

The reviewed digest has zero open critical/high findings and is eligible only for
the non-final post-fix candidate validation step. It is **not** a CLOSED review.
The complete candidate gauntlet has not yet run, and no PASS evidence is claimed.
`VF-SEC-006` and `VF-SEC-008` require source changes and therefore a new digest and
new fresh-context review; `VF-SEC-007` remains an explicitly open, non-blocking low
dependency debt until its shipping disposition is satisfied.
