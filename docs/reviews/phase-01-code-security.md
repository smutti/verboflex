# Phase 1 Fresh-Context Code and Security Review Candidate

- Review-status: OPEN
- Open-critical-high: 0
- Full-gauntlet-status: PENDING
- Reviewed-source-digest: `94a75a85d862e9bcabd96fed8cf91006853f734db5d165ca09148a98e7dd82c0`
- Review-date: 2026-08-25
- Reviewer: independent fresh-context Phase 1 code/security reviewer
- Critical: 0
- High: 0
- Medium: 1
- Low: 1

## Gate conclusion

This artifact is an **OPEN candidate**, not a closed review. The complete
`tools/gauntlet.sh --post-fix-candidate` run has **not** been executed against this
candidate, so `Full-gauntlet-status` remains `PENDING` and no full-gauntlet PASS is
claimed. In addition, `VF-SEC-008` remains an open medium finding after the canonical
cookie contract was tightened. The review must not become `CLOSED` until that source
change is made, a new digest is computed, a fresh review accepts it, and the complete
source-bound gauntlet succeeds.

## Fresh-context scope and method

The independent analysis was completed before the previous contents of this artifact
were read. Initial context was limited to the approved Phase 1 SPEC,
`tools/source_manifest.txt`, the exact review-mode source tree, and summaries
`01-02-SUMMARY.md` through `01-13-SUMMARY.md`. Builder conversations were not read.
Only afterward was the previous artifact opened to reconcile `VF-SEC-001` through
`VF-SEC-008`.

`tools/source_state.sh --review-digest` reproduced the expected clean source identity:

```text
94a75a85d862e9bcabd96fed8cf91006853f734db5d165ca09148a98e7dd82c0
```

Review mode resolved 146 unique paths and 33,773 lines: 88 implementation entries,
33 test entries, 18 configuration entries, 3 lockfiles, 4 migration entries, 9 verifier
scripts, and the source-bound deployment contract. The review traced correctness,
authentication and authorization, JWT and refresh-session lifecycle, rate limits,
Origin/CORS behavior, persistence and concurrency, frontend memory-only authority,
generated API contracts, container/service boundaries, dependency locks, and verifier
sensitivity. The review artifact itself is excluded from the review digest by design.

## OWASP ASVS 5.0.0 Level 1 mapping

All 70 Level 1 requirements from the official OWASP ASVS 5.0.0 release were screened
for the Phase 1 slice.

| Area | Applicable controls | Result |
| --- | --- | --- |
| Input, output, and business-flow validation | `V1.2.1`-`V1.2.5`, `V1.3.2`, `V2.1.1`-`V2.3.1` | PASS for the current Pydantic/ORM/React/API surfaces; XML and file-handling controls are not yet applicable |
| Browser and origin security | `V3.2.1`-`V3.5.3` | CORS, exact Origin checks, safe methods, and source-bound HSTS/TLS deployment obligations PASS; cookie hardening is PARTIAL because the tightened `__Host-` contract is unmet (`VF-SEC-008`) |
| HTTP contracts | `V4.1.1` | PASS; bounded JSON schemas and deterministic generated-client drift controls are present |
| Authentication | `V6.1.1`, `V6.2.1`-`V6.4.2` | Phase 1 password change, masking, exact verification, and rate limiting PASS the approved contract. `V6.2.4` common-password screening is not implemented and is not claimed as ASVS-conformant; it requires a future approved password-policy revision |
| Session management | `V7.2.1`-`V7.4.2` | PASS; backend verification, CSPRNG refresh tokens, rotation/replay-family revocation, expiry, logout, reset, and token-version invalidation are durable |
| Authorization | `V8.1.1`-`V8.3.1` | PASS for the current user/status slice; roles and active authority are server-derived |
| Self-contained tokens | `V9.1.1`-`V9.2.1` | PASS; signature/MAC, fixed algorithm, configured key source, required claims, exact lifetime, and expiry are checked. No issuer/audience claim is asserted because ASVS L1 does not require one and the reviewed source does not implement one |
| OAuth server behavior | `V10.4.1`-`V10.4.5` | Redirect/code controls are not applicable; refresh replay mitigation PASS. The approved first-party password grant remains an explicit design deviation from `V10.4.4`, not an ASVS-conformance claim |
| Cryptography and transport | `V11.3.1`-`V11.4.1`, `V12.1.1`-`V12.2.2` | Approved primitives PASS; the source-bound edge contract requires TLS 1.2/1.3, trusted certificates, HTTPS redirect/unreachability, and one-year HSTS (`VF-SEC-006` resolved at the repository contract boundary) |
| Data/component protection | `V13.4.1`, `V14.2.1`, `V14.3.1`, `V15.1.1`-`V15.3.1` | Runtime image, memory-only browser authority, response minimization, and runtime dependency audits PASS; `VF-SEC-007` remains explicit non-runtime dependency debt |

## Dependency audit

- `uv lock --check` resolved 111 packages, and `pip-audit` reported no known
  third-party Python vulnerabilities; only the local non-PyPI `verboflex` package was
  skipped.
- `npm audit --omit=dev --audit-level=low` reported zero runtime vulnerabilities.
- The full npm audit reports two moderate development-only paths for
  GHSA-q8mj-m7cp-5q26 through `typed-rest-client -> qs`. This is the existing
  `VF-SEC-007` low, non-blocking debt; it is neither resolved nor waived.

## Findings and dispositions

| ID | Severity | Status | Disposition |
| --- | --- | --- | --- |
| `VF-SEC-001` | high | RESOLVED | Git-compatible manifest rules and per-rule nonempty checks cover frontend production/test paths |
| `VF-SEC-002` | high | RESOLVED | Exact duplicate-safe final/candidate metadata and digest binding fail closed |
| `VF-SEC-003` | high | RESOLVED | OpenAPI negative control mutates a real symbol, proves drift, and proves restoration |
| `VF-SEC-004` | high | RESOLVED | Real smoke owns one isolated stack and invokes adversarial auth once with propagated status |
| `VF-SEC-005` | medium | RESOLVED | Backend auth/session mutation scope is complete and frontend session mutation breaks below 100% |
| `VF-SEC-006` | medium | RESOLVED | Deployment contract is category-required and source-bound; negative control proves changes invalidate the digest; services are loopback-only and edge TLS/HSTS obligations are explicit |
| `VF-SEC-007` | low | OPEN, NON-BLOCKING | Development-only advisory must be remediated or explicitly time-bounded and re-reviewed before ship; no waiver is implied |
| `VF-SEC-008` | medium | OPEN | Current cookie remains `__Secure-verboflex_refresh` with `Path=/api/v1/auth`; the tightened canonical contract requires `__Host-verboflex_refresh`, `Secure`, `Path=/`, and no `Domain` |

### Resolution evidence for VF-SEC-001 through VF-SEC-005

- `VF-SEC-001`: the canonical manifest resolves the full frontend TypeScript, TSX,
  CSS, unit-test, and E2E tree, while `source_state.sh` rejects each empty include.
- `VF-SEC-002`: final mode requires exactly `CLOSED/0/current-digest`; candidate mode
  requires exactly `OPEN/0/PENDING/current-digest`. Duplicate, missing, stale, and
  false-state controls are rejected.
- `VF-SEC-003`: the OpenAPI control changes the existing health handler, confirms a
  byte change and a generated diff, then validates source/client restoration.
- `VF-SEC-004`: `real_smoke.sh` owns unique loopback ports, stack lifecycle, and
  cleanup, and calls the adversarial harness against the running stack exactly once.
- `VF-SEC-005`: mutmut covers all handwritten auth/session modules and rejects any
  nonempty surviving-mutant verdict; its negative control injects a survivor. Stryker
  mutates the frontend session provider with `related: false` and `break: 100`.
  Actual zero-survivor execution remains part of the pending candidate gauntlet and is
  not claimed by this review.

### VF-SEC-006 resolution verification

`tools/source_manifest.txt` now has a required `deployment-contract` category bound to
`docs/phase-01-smoke.md`; `source_state.sh` requires the category in review/final mode.
`tools/tests/test_source_state.sh` mutates the TLS runbook and proves the review digest
fails for the intended dirty-source reason. Staging and production inherit backend and
frontend host publication on `127.0.0.1`, preventing direct remote plaintext bypass.
The source-bound runbook requires a same-host edge with trusted certificates, TLS 1.2
or 1.3, HTTP redirect/unreachability, `Strict-Transport-Security` for at least one year,
and forwarding only to loopback. Environment-specific certificate/HSTS observation is
still an operator deployment obligation; the repository does not claim to have run it.

### VF-SEC-007 non-blocking disposition

`VF-SEC-007` remains **OPEN, NON-BLOCKING**, not resolved and not waived. The advisory
is confined to the development mutation toolchain and the shipped SPA runtime audit is
clean. Before milestone shipping, the dependency must be upgraded/overridden to a
compatible fixed version or receive a dated owner/risk decision followed by review.
Until then it stays visible debt.

### VF-SEC-008 open medium finding

- **Evidence:** `backend/src/verboflex/api/v1/routes/auth.py` consistently reads, sets,
  and deletes `__Secure-verboflex_refresh`; staging/production add `Secure`, and the
  cookie uses `HttpOnly`, `SameSite=Lax`, and `Path=/api/v1/auth`. OpenAPI, backend
  tests, real smoke, adversarial smoke, and the deployment runbook use that same name.
  The unprefixed `verboflex_refresh` legacy name is not emitted.
- **Gap:** the canonical contract now requires `__Host-verboflex_refresh`, `Secure`,
  `Path=/`, and no `Domain`. `__Host-` cannot be combined with the current narrow path,
  so the otherwise coherent `__Secure-` remediation does not satisfy the new contract.
- **Impact:** the stronger browser-enforced host-only invariant is absent and the
  implementation is contract-incompatible. Existing prefix, Secure deployment mode,
  origin checks, loopback binding, and rotation reduce exploitability, so severity
  remains medium rather than high.
- **Required resolution:** rename the cookie to `__Host-verboflex_refresh`, make
  `Secure` unconditional for every emission/deletion, set `Path=/`, omit `Domain`, and
  update schema, backend tests, browser/smoke/adversarial checks, and negative controls
  to prove neither the unprefixed nor prior `__Secure-` name is emitted. This source
  change invalidates the digest and requires a new fresh review and full candidate
  gauntlet.

## Final status

Open findings are **0 critical, 0 high, 1 medium, and 1 low**. `VF-SEC-008` blocks
review closure. `VF-SEC-007` is explicitly non-blocking for candidate validation but
must be dispositioned before ship. The full candidate gauntlet has not been executed,
and this review is not `CLOSED`.
