# Phase 1 Fresh-Context Code and Security Review

- Review-status: OPEN
- Open-critical-high: 0
- Full-gauntlet-status: PENDING
- Reviewed-source-digest: `01837816f8be716621dd639b4f7c2a659cea542800e77c8e82114a1a4967735e`
- Review-date: 2026-08-25
- Reviewer: independent fresh-context Phase 1 code/security reviewer
- Critical: 0
- High: 0
- Medium: 1
- Low: 1

## Gate conclusion

The host-cookie remediation is correct and `VF-SEC-008` is resolved. The review remains
**OPEN**, however, because one independently discovered medium session-termination finding
(`VF-SEC-009`) remains unresolved. The full candidate gauntlet was not executed by this
reviewer, `Full-gauntlet-status` is therefore `PENDING`, and this artifact is not `CLOSED`.

## Fresh-context scope and method

The independent analysis was completed before the prior contents of this artifact were read.
Initial context was limited to the approved `01-SPEC.md`, `tools/source_manifest.txt`, the
exact review-mode source tree, and summaries `01-02-SUMMARY.md` through
`01-13-SUMMARY.md`; builder conversations were not read. Only after freezing the independent
findings was the previous artifact opened to reconcile `VF-SEC-001` through `VF-SEC-008`.

`tools/source_state.sh --review-digest` reproduced the expected clean identity:

```text
01837816f8be716621dd639b4f7c2a659cea542800e77c8e82114a1a4967735e
```

Review mode resolved 146 unique paths: backend/frontend implementation, tests, configuration,
lockfiles, migrations, verifier scripts, and the source-bound deployment contract. The review
traced correctness, authentication and authorization, JWT and refresh-session lifecycle,
rate limiting, Origin/CORS, persistence/concurrency, frontend memory-only authority, generated
API contracts, container boundaries, dependency locks, and verifier sensitivity. The review
artifact itself is excluded from the review digest by design.

## Open finding

### VF-SEC-009 — logout after refresh leaves the pre-rotation access token usable

- **Severity:** medium
- **Status:** OPEN
- **Applicable control:** OWASP ASVS 5.0.0 `V7.4.1` (session termination must prevent
  further use of the terminated session).
- **Evidence:** login binds its access token to the initial `AuthSession` row
  (`backend/src/verboflex/auth/login.py:92-109`). Refresh marks that predecessor only as
  `used_at` and creates a successor (`backend/src/verboflex/auth/refresh_sessions.py:85-115`).
  Logout revokes only the row selected by the current refresh cookie
  (`backend/src/verboflex/auth/refresh_sessions.py:149-167`). Principal resolution rejects
  missing, revoked, or expired rows but does not reject `used_at` predecessors or another
  revoked row in the same family (`backend/src/verboflex/auth/principal.py:55-63`).
- **Concrete sequence:** login produces `A1/R1` on row `S1`; refresh of `R1` leaves
  `S1.used_at != null` and produces `A2/R2` on `S2`; logout with `R2` revokes only `S2`.
  Until its 15-minute JWT expiry, `A1` still resolves through non-revoked `S1` and can call
  protected endpoints. Existing unit and real-smoke assertions validate `A2` after logout,
  not `A1` (`backend/tests/auth/test_logout.py:61-94`, `tools/real_smoke.sh:342-358`).
- **Impact:** a copied access token from immediately before rotation remains usable after the
  user logs out, contrary to the documented immediate revocation contract. The exposure is
  bounded by the 15-minute access-token lifetime, so this is medium rather than high.
- **Required remediation:** make logout terminate the complete refresh family (or otherwise
  make every access token in that family fail durable principal reconciliation), then add a
  detecting test for `login -> refresh -> logout -> A1=401 and A2=401`. Apply the fix through
  RED/GREEN, recompute the review digest, obtain a fresh-context review, and rerun the complete
  source-bound candidate gauntlet.

## OWASP ASVS 5.0.0 Level 1 mapping

All 70 Level 1 requirements from the official OWASP ASVS 5.0.0 release were screened for the
Phase 1 slice.

| Area | Applicable controls | Result |
| --- | --- | --- |
| Input/output and business flow | `V1.2.1`-`V1.2.5`, `V1.3.2`, `V2.1.1`-`V2.3.1` | PASS for current Pydantic/ORM/React surfaces; XML/file controls are not yet applicable |
| Browser/origin security | `V3.2.1`-`V3.5.3` | PASS: safe React text rendering, exact CORS/Origin checks, sensitive POST methods, and corrected host-only Secure cookie |
| HTTP contract | `V4.1.1` | PASS: bounded JSON schemas and deterministic generated-client drift checks |
| Authentication | `V6.1.1`, `V6.2.1`-`V6.4.2` | Approved password/rate-limit contract passes; `V6.2.4` common-password screening is not implemented and is not claimed as conformant, requiring a future approved policy revision |
| Session management | `V7.2.1`-`V7.4.2` | PARTIAL: backend verification, entropy, rotation/replay, expiry, reset, and deactivation pass; logout termination fails `V7.4.1` via `VF-SEC-009` |
| Authorization | `V8.1.1`-`V8.3.1` | PASS for current user/status resources; roles and active authority are server-derived |
| Self-contained tokens | `V9.1.1`-`V9.2.1` | PASS: signature, fixed algorithm, configured key, required claims, exact lifetime, and expiry are verified |
| OAuth behavior | `V10.4.1`-`V10.4.5` | Redirect/code controls are not applicable; replay mitigation passes; the approved first-party password grant remains an explicit `V10.4.4` design deviation, not a conformance claim |
| Cryptography/transport | `V11.3.1`-`V12.2.2` | PASS at repository boundary: approved primitives plus source-bound TLS 1.2/1.3, trusted-certificate, HTTPS, and one-year HSTS deployment obligations |
| Data/components | `V13.4.1`, `V14.2.1`, `V14.3.1`, `V15.1.1`-`V15.3.1` | Runtime image, memory-only browser authority, response minimization, and runtime audits pass; `VF-SEC-007` remains development-only dependency debt |

## Reconciliation of VF-SEC-001 through VF-SEC-008

| ID | Severity | Status | Verified resolution evidence |
| --- | --- | --- | --- |
| `VF-SEC-001` | high | RESOLVED | Manifest rules cover frontend production/tests and empty required categories fail closed |
| `VF-SEC-002` | high | RESOLVED | Final/candidate metadata require exact singleton status/count/digest values and reject stale or duplicate values |
| `VF-SEC-003` | high | RESOLVED | OpenAPI negative control mutates a real symbol, observes drift, and verifies restoration |
| `VF-SEC-004` | high | RESOLVED | Real smoke owns one isolated stack and propagates the single adversarial-auth invocation result |
| `VF-SEC-005` | medium | RESOLVED | Mutmut covers handwritten backend auth/session modules; Stryker covers the frontend session provider; survivor verdicts fail closed |
| `VF-SEC-006` | medium | RESOLVED | `deployment-contract` is a required manifest category; TLS runbook mutation invalidates the digest; staging/production ports remain loopback-only and the edge TLS/HSTS obligations are explicit |
| `VF-SEC-007` | low | OPEN, NON-BLOCKING | Development-only `typed-rest-client -> qs` advisory must be remediated or receive a dated owner/risk decision and re-review before ship; no waiver is implied |
| `VF-SEC-008` | medium | RESOLVED | Exact `__Host-verboflex_refresh` is read/set/deleted with unconditional `Secure`, `Path=/`, no `Domain`; login/refresh/logout/password-change tests and real/adversarial smoke reject both legacy names |

### Host-cookie verification (`VF-SEC-008`)

- Source uses only `__Host-verboflex_refresh`; set and delete both use unconditional
  `Secure`, `Path=/`, `HttpOnly`, and `SameSite=Lax`, with no `Domain`
  (`backend/src/verboflex/api/v1/routes/auth.py:38-68`). This remains true when local
  configuration sets `VERBOFLEX_REFRESH_COOKIE_SECURE=false` because cookie emission no longer
  delegates `Secure` to that setting.
- Login reads/emits the host cookie, rotation replaces it, logout deletes it, and password
  change deletes it. Backend tests assert exact attributes and absence of
  `verboflex_refresh`, `__Secure-verboflex_refresh`, the old narrow path, and `Domain`
  (`backend/tests/auth/test_login.py:148-193`, `backend/tests/auth/test_refresh.py:198-242`,
  `backend/tests/auth/test_logout.py:61-107`).
- `tools/real_smoke.sh:284-358`, `tools/adversarial_auth.sh`, and
  `docs/phase-01-smoke.md:49-58` use the same cookie name and include negative legacy-name and
  attribute checks. The generated OpenAPI has no cookie-schema drift because this HttpOnly
  transport detail is expressed at the route boundary rather than in a response body.

### Source-bound TLS deployment contract (`VF-SEC-006`)

`tools/source_manifest.txt` makes `docs/phase-01-smoke.md` a required
`deployment-contract`; review/final mode requires that category. The runbook requires trusted
certificates, TLS 1.2/1.3, HTTP redirect or unreachability, one-year HSTS, and forwarding only
to loopback (`docs/phase-01-smoke.md:13-25`). Staging/production inherit loopback publication
from base Compose. `tools/tests/test_source_state.sh` mutates the TLS runbook and proves the
digest fails. Environment-specific certificate/HSTS observation remains an explicit operator
edge-smoke obligation; this review does not claim it ran.

## API review gates

Scope: internal, greenfield Phase 1 HTTP/JSON surface.

- Boring: PASS; seven stable `/api/v1` operations use conventional methods/statuses.
- Compatibility: PASS for the corrected first-party cookie consumer set; generated OpenAPI
  drift and browser/smoke callers use the same source state.
- Authentication/authorization: PARTIAL solely for `VF-SEC-009`; bearer claims otherwise
  reconcile against current user, token-version, session, and database role state.
- Idempotency: logout target state is idempotent; refresh is one-time and replay revokes the
  family; password replacement is guarded and atomic.
- Blast radius: exact rate limits and bounded probes are present; collection/pagination and
  expensive-field gates are not applicable to this bounded Phase 1 surface.
- No implementation leakage: PASS; identity/status responses expose only approved fields and
  stable enum states.

## Dependency disposition

The locked runtime graphs remain without a known runtime advisory according to the existing
repository audit gates. `VF-SEC-007` remains **LOW, OPEN, NON-BLOCKING** because the full npm
development graph includes the existing moderate `typed-rest-client -> qs` advisory path.
Before ship it must be upgraded/overridden to a compatible fixed version or receive a dated
owner/risk decision followed by re-review.

## Final status

Open findings are **0 critical, 0 high, 1 medium, and 1 low**. `VF-SEC-009` blocks review
closure. `VF-SEC-007` is non-blocking for candidate validation but mandatory pre-ship debt.
The full candidate gauntlet has not been executed by this reviewer, and this review is not
`CLOSED`.
