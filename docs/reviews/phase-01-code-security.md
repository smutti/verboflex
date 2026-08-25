# Phase 1 Fresh-Context Code and Security Review

- Review-status: OPEN
- Open-critical-high: 4
- Reviewed-source-digest: `0644177a7acf327004d5faba73d7545ed10aca4d0d6319fa3967ea05a4a9582d`
- Review-date: 2026-08-25
- Reviewer: fresh-context Phase 1 code/security reviewer
- Critical: 0
- High: 4
- Medium: 2
- Low: 1

## Fresh-context statement

I performed this review from a genuinely fresh context. I started only from the approved Phase 1 SPEC, `tools/source_manifest.txt`, the exact current source tree resolved by that manifest, and the Phase 1 plan summaries `01-02-SUMMARY.md` through `01-13-SUMMARY.md`. I did not consult the builder conversation or an earlier code/security review. This artifact did not exist when the review-source digest was calculated, and it is excluded from review mode by `tools/source_state.sh`.

This review is deliberately **OPEN**. The four high findings below are not accepted, waived, or closed. Each requires a TDD fix, a new fresh review-source digest, and a new fresh-context review before the Phase 1 final gauntlet/evidence round.

## Scope and source identity

| Category | Resolved paths |
| --- | ---: |
| Implementation | 36 |
| Tests | 23 |
| Configuration | 17 |
| Lockfiles | 3 |
| Migrations | 4 |
| Verifier scripts | 9 |
| **Total reviewed paths** | **92** |

The 92-path count is the unique, sorted source set resolved in review mode. The review artifact is intentionally absent from that count. Every path in that resolved set was inspected for correctness, regression risk, data and authority boundaries, dependency risk, and applicable OWASP ASVS 5.0.0 Level 1 requirements. The following independent command reproduced the required digest exactly:

```text
$ tools/source_state.sh --review-digest
0644177a7acf327004d5faba73d7545ed10aca4d0d6319fa3967ea05a4a9582d
```

The canonical categories covered the FastAPI application and auth/session services, SQLAlchemy models and Alembic migration, backend tests, the one resolved frontend E2E test, application and container configuration, OpenAPI snapshot, Python/npm lockfiles, and all verifier scripts. Finding `VF-SEC-001` explains why the nominal frontend source and unit-test rules did not actually resolve frontend paths.

## Review method

1. Parsed the approved SPEC into product-security, fail-closed, immutable-source, and evidence-gate obligations.
2. Independently ran the canonical review digest and enumerated its resolved category/path set.
3. Inspected every resolved path, tracing authentication, forced password change, JWT validation, refresh-token rotation/replay handling, logout, rate limiting, origin checks, status probes, database authority, migrations, container exposure, and verifier control flow.
4. Compared tests and mutation scopes to the production branches they claim to verify.
5. Audited gate scripts for empty pathspecs, stale/OPEN-review acceptance, controls that do not change the subject, cleanup/argument contracts, and final-digest ordering.
6. Performed lock/audit checks without installing packages. I did **not** run `tools/gauntlet.sh` in full and make no full-gauntlet-green claim.

Focused checks included review-digest reproduction, direct `git ls-files` pathspec comparison, shell control-flow inspection, `uv lock --check`, `pip-audit` against the installed locked environment, `npm audit --package-lock-only --audit-level=low --json`, and dependency-tree attribution with `npm ls typed-rest-client qs --all`.

## Applicable OWASP ASVS 5.0.0 Level 1 mapping

The control identifiers below use the stable `v5.0.0-<requirement>` form recommended by the official [OWASP ASVS 5.0.0 release](https://github.com/OWASP/ASVS/tree/v5.0.0_release).

| ASVS L1 area | Review application | Result |
| --- | --- | --- |
| `v5.0.0-V2.2.1`, `v5.0.0-V2.2.2` | Security-decision inputs and trusted-service validation | Implemented for key auth decisions; evidence breadth affected by `VF-SEC-001` and `VF-SEC-005` |
| `v5.0.0-V3.4.1`, `v5.0.0-V3.4.2`, `v5.0.0-V3.5.1`–`V3.5.3` | HSTS, fixed/allowlisted CORS, and browser-origin request boundaries | CORS is allowlisted; TLS/HSTS deployment proof is incomplete (`VF-SEC-006`) |
| `v5.0.0-V4.1.1` | API response/content-type and generated contract integrity | Product behavior present; drift control is invalid (`VF-SEC-003`) |
| `v5.0.0-V6.1.1`, `v5.0.0-V6.2.1`–`V6.2.8`, `v5.0.0-V6.3.1`–`V6.3.2` | Password and brute-force controls | Strong implementation/tests; final evidence gate remains blocked |
| `v5.0.0-V7.2.1`–`V7.2.4`, `v5.0.0-V7.4.1`–`V7.4.2` | Backend session verification, rotation, and termination | Strong implementation/tests; mutation/adversarial coverage gaps remain |
| `v5.0.0-V8.1.1` | Function/data authorization rules | Reusable server-side authority is present for the Phase 1 surface |
| `v5.0.0-V9.1.1`–`V9.1.3`, `v5.0.0-V9.2.1` | JWT integrity, algorithm/source allowlisting, and expiry | Implemented with focused unit/property coverage |
| `v5.0.0-V10.4.4`, `v5.0.0-V10.4.5` | Approved grant boundary and refresh replay response | Password grant is a SPEC-approved Phase 1 exception; refresh rotation/replay behavior is implemented but under-mutated |
| `v5.0.0-V12.1.1`, `v5.0.0-V12.2.1`, `v5.0.0-V12.2.2` | External TLS and trusted certificates | Not established by the canonical deployment files (`VF-SEC-006`) |
| `v5.0.0-V14.2.1`, `v5.0.0-V14.3.1` | No secrets in URLs and clearing client-side authenticated data | Token transport/storage design is appropriate in reviewed backend/E2E evidence |
| `v5.0.0-V15.1.1`, `v5.0.0-V15.2.1` | Dependency remediation policy and component currency | Lock integrity is good; current moderate dev-tool advisories remain (`VF-SEC-007`) |

Gate-integrity findings also enforce the Phase 1 SPEC's stronger explicit controls at lines 403, 407, 409, 411, 413, 421, and 459. Those controls are prerequisites for making credible claims across all applicable ASVS L1 areas; they are not represented as product ASVS requirements when no direct ASVS requirement exists.

## Dependency audit observations

- `uv lock --check --directory backend` resolved 111 packages and reported the lock current.
- The installed `pip-audit 2.10.1` reported no known vulnerabilities in the locked Python environment. It skipped only the local, non-PyPI `verboflex 0.1.0` project, which is the source under review rather than a third-party package.
- Python direct runtime and development dependencies are exact-pinned in `backend/pyproject.toml`; `backend/uv.lock` records sources, versions, and artifact hashes.
- `frontend/package.json` exact-pins direct dependencies and `frontend/package-lock.json` records resolved artifacts and integrity hashes.
- A current low-threshold npm audit found no critical/high vulnerabilities and two moderate records: `typed-rest-client@2.3.1` through `@stryker-mutator/core@10.0.0`, and its nested `qs@6.15.1`, affected by GHSA-q8mj-m7cp-5q26. The chain is development-only and fixable; see `VF-SEC-007`.
- The gauntlet's npm audit threshold is `high`, so those moderate records do not fail the existing supply-chain layer. Python and npm license inventory commands exist, but no full gauntlet/license-output claim was made in this review.
- Container bases use mutable tags (`postgres:18-alpine`, `redis:7-alpine`, and language/runtime tags in Dockerfiles). This is a reproducibility observation, not a separate finding for Phase 1, because the SPEC approves those version lines and does not require digest pinning.

## Findings summary

| ID | Severity | Control | Short title | Disposition |
| --- | --- | --- | --- | --- |
| `VF-SEC-001` | high | SPEC immutable source/review gate; cross-cutting ASVS coverage | Canonical brace pathspecs silently exclude all frontend source and unit tests | OPEN — blocking |
| `VF-SEC-002` | high | SPEC review-closure/source gate | Full gauntlet never checks review CLOSED status or reviewed-source digest | OPEN — blocking |
| `VF-SEC-003` | high | SPEC drift negative control; `v5.0.0-V4.1.1` evidence | OpenAPI negative control mutates text that does not exist | OPEN — blocking |
| `VF-SEC-004` | high | SPEC adversarial smoke; `v5.0.0-V6.3.1`, `V7.4.1`, `V10.4.5` evidence | Staging/adversarial layer invokes a second harness in an always-invalid mode | OPEN — blocking |
| `VF-SEC-005` | medium | SPEC mutation scope; auth/session ASVS controls | Backend mutation gate omits stateful login, password-change, refresh, and logout logic | OPEN — remediation required before final evidence |
| `VF-SEC-006` | medium | `v5.0.0-V3.4.1`, `V12.1.1`, `V12.2.1`, `V12.2.2` | Canonical staging/production files do not establish TLS or HSTS | OPEN — deployment contract/evidence required |
| `VF-SEC-007` | low | `v5.0.0-V15.1.1`, `V15.2.1` | Current npm audit reports two moderate dev-tool vulnerability records | OPEN — update or time-bound disposition required |

## Detailed findings

### VF-SEC-001 — Canonical brace pathspecs silently exclude all frontend source and unit tests

- **Severity:** high
- **Control:** Phase 1 SPEC lines 34, 407, 409, 411, and 459; cross-cutting integrity of all frontend-applicable ASVS L1 verification
- **Path/line/evidence:** `tools/source_manifest.txt:6` contains `:(glob)frontend/src/**/*.{ts,tsx,css}` and line 8 contains `:(glob)frontend/src/**/*.test.{ts,tsx}`. `tools/source_state.sh:75-79` passes each quoted value directly to `git ls-files`; Git pathspec magic does not perform shell-style brace expansion. Both exact manifest pathspecs resolved zero paths, while `git ls-files -- 'frontend/src/**'` resolved 52 tracked frontend source paths. `tools/source_state.sh:95-100` checks only that the aggregate `implementation` and `tests` categories are nonempty, which backend paths satisfy.
- **Exploit/failure impact:** Arbitrary frontend production or unit-test changes can be absent from the review digest and final immutable digest. A stale review/gauntlet can therefore be presented for a different frontend application state, invalidating the central Phase 1 evidence boundary and concealing frontend security regressions.
- **Disposition:** OPEN — blocking; no waiver or closure is permitted.
- **Required resolution:** Replace brace expressions with Git-compatible explicit rules (for example, separate `.ts`, `.tsx`, and `.css` include rules, and explicit `.test.ts`/`.test.tsx` rules). Strengthen the manifest self-test with real per-rule/nonempty frontend assertions and a known tracked frontend canary so an individual include rule cannot resolve silently to zero.
- **Verification:** Demonstrate that every tracked in-scope `frontend/src` path is present in the resolved list; mutate a frontend production file and a frontend unit test separately and show each changes `--review-digest`; make a deliberately empty/broken frontend include rule fail the manifest self-test. Recompute the review digest and request a new fresh review.

### VF-SEC-002 — Full gauntlet never checks review CLOSED status or reviewed-source digest

- **Severity:** high
- **Control:** Phase 1 SPEC lines 409, 411, 413, 445, and 466
- **Path/line/evidence:** `tools/source_state.sh:299-310` implements `--verify-review-closed` and `--verify-review-source`. However, `tools/gauntlet.sh:429-454` only records `source_state.sh --digest` and later calls `--verify-final-before-report`; neither review check is invoked anywhere in the full-gauntlet path. The preflight at `tools/gauntlet.sh:198-199` checks only that the review path is mentioned by the manifest. Additionally, the standalone CLOSED check uses independent exact-line greps and does not reject contradictory duplicate metadata, although that weakness is currently secondary because the check is not called at all.
- **Exploit/failure impact:** A missing review, an explicitly OPEN review with unresolved critical/high findings, or a CLOSED review bound to a different source digest can enter the final source set and proceed through the full gauntlet. The gauntlet could claim PASS despite the SPEC's mandatory human-security gate never being satisfied.
- **Disposition:** OPEN — blocking; this artifact intentionally demonstrates the unsafe state because the current gauntlet would not reject it.
- **Required resolution:** Make review closure and review-source binding a fail-closed prerequisite before the initial final digest is recorded. Parse exactly one authoritative metadata value for each required field; reject missing, duplicate, contradictory, malformed, non-CLOSED, nonzero, or digest-mismatched metadata. Add negative controls for OPEN status, nonzero count, stale digest, duplicate contradictory values, and missing artifact.
- **Verification:** Each known-bad fixture must fail for its intended reason; one exact CLOSED/zero/current-digest fixture must pass; running the real gauntlet against this OPEN artifact must stop before product test layers. Recompute the digest and request a new fresh review after the fix.

### VF-SEC-003 — OpenAPI negative control mutates text that does not exist

- **Severity:** high
- **Control:** Phase 1 SPEC line 413 item 9 (generated OpenAPI/client drift with proved failing control); `v5.0.0-V4.1.1` API response-contract evidence
- **Path/line/evidence:** `tools/gauntlet.sh:354-375` copies `backend/src/verboflex/api/v1/routes/health.py`, then at line 363 replaces `health_status` with `health_status_negative_control`. The reviewed `health.py` contains no `health_status` token: its handler is `read_health` and its response body is `{"status": "ok"}`. The subject is therefore byte-identical after the supposed mutation. `npm run api:check` can pass cleanly, causing line 373 to abort with `OpenAPI drift negative control unexpectedly passed`.
- **Exploit/failure impact:** The negative control proves nothing about the drift checker and deterministically prevents the required full gauntlet from completing on clean source. If later loosened merely to ignore the failure, OpenAPI drift evidence would instead fail open.
- **Disposition:** OPEN — blocking.
- **Required resolution:** Add a TDD fixture/control that makes a deterministic, asserted OpenAPI-visible change (for example, change the actual health response schema or operation metadata), assert the target bytes changed before invoking `api:check`, restore signal-safely, and prove the check fails specifically on a generated-spec/client diff.
- **Verification:** Record before/after hashes showing the control altered its subject; the negative control must fail `api:check` with the expected diff, restoration must reproduce the original hashes, and the subsequent clean `api:check` must pass. Recompute the digest and request a new fresh review.

### VF-SEC-004 — Staging/adversarial layer invokes a second harness in an always-invalid mode

- **Severity:** high
- **Control:** Phase 1 SPEC line 413 item 11 and security cases for hostile loops, Redis failure, refresh replay, and logout; evidence for `v5.0.0-V6.3.1`, `v5.0.0-V7.4.1`, and `v5.0.0-V10.4.5`
- **Path/line/evidence:** `tools/gauntlet.sh:422-426` first runs `tools/real_smoke.sh` and then runs `tools/adversarial_auth.sh` with no argument. `tools/real_smoke.sh:399-418` already runs `adversarial_flow` against its live isolated stack and then cleans that stack. `tools/adversarial_auth.sh:278-285` explicitly rejects an empty invocation with `direct execution requires a stack owned by tools/real_smoke.sh`; its runnable integration mode is `--against-running-stack` and requires environment from the smoke owner.
- **Exploit/failure impact:** Even if the full real smoke and its embedded adversarial flow pass, the gauntlet immediately fails on the redundant invalid invocation. This makes the mandated final gauntlet incapable of reaching a clean PASS and creates ambiguous, non-auditable evidence about which adversarial run owns the stack.
- **Disposition:** OPEN — blocking.
- **Required resolution:** Establish one owner and one invocation contract. Either treat `real_smoke.sh` as the complete staging/adversarial layer, or have it expose/retain a live stack while the gauntlet invokes `adversarial_auth.sh --against-running-stack` with the complete validated environment. Add a wrapper-level test that executes the exact gauntlet layer call sequence, not just each script's internal self-test.
- **Verification:** The exact layer entrypoint must run the adversarial suite once against a live owned stack, propagate an injected adversarial failure, clean up on success/failure/signal, and return zero on the clean case. Recompute the digest and request a new fresh review.

### VF-SEC-005 — Backend mutation gate omits stateful auth/session logic

- **Severity:** medium
- **Control:** Phase 1 SPEC line 421; evidence for `v5.0.0-V6.3.1`, `v5.0.0-V7.2.4`, `v5.0.0-V7.4.1`, and `v5.0.0-V10.4.5`
- **Path/line/evidence:** `backend/pyproject.toml:73-87` limits mutmut to five files: access tokens, identity, origin, passwords, and rate limits. It omits the stateful implementations in `login.py`, `password_change.py`, `refresh_sessions.py`, `principal.py`, and the logout/session route behavior. `tools/gauntlet.sh:336-343` accepts that configured scope and reruns only access-token/password/config property tests. The SPEC requires mutation runs over handwritten auth/session/state logic with every non-equivalent mutant killed.
- **Exploit/failure impact:** Security-sensitive regressions in refresh rotation/replay-family revocation, password-change authority invalidation, login state transitions, and principal/session enforcement can survive while the mutation layer is reported green.
- **Disposition:** OPEN — medium evidence gap; must be resolved before final Phase 1 evidence even though it does not increment `Open-critical-high`.
- **Required resolution:** Expand mutation scope and test selection to the omitted handwritten auth/session/state modules, or document only demonstrably equivalent/tool-incompatible exclusions at line-level granularity. Preserve independent property-suite reruns for relevant mutants.
- **Verification:** Publish mutation results covering every in-scope handwritten auth/session/state file, show zero surviving non-equivalent mutants, and demonstrate at least one killed divergent mutant in refresh replay/family revocation and password-change authority invalidation.

### VF-SEC-006 — Canonical staging/production files do not establish TLS or HSTS

- **Severity:** medium
- **Control:** `v5.0.0-V3.4.1`, `v5.0.0-V12.1.1`, `v5.0.0-V12.2.1`, `v5.0.0-V12.2.2`; Phase 1 SPEC line 114
- **Path/line/evidence:** Base `docker-compose.yml:55-59` publishes the backend's plaintext Uvicorn HTTP port on all host interfaces. The staging and production overlays (`docker-compose.staging.yml:19-22`, `docker-compose.prod.yml:19-22`) inherit that published port and add no TLS listener or trusted reverse-proxy boundary. `docker/frontend.nginx.conf:1-11` listens only on port 80 and sets no HSTS header. The overlay's HTTPS `VITE_API_BASE_URL` expresses an intended external hostname but does not itself terminate or enforce TLS or prevent direct HTTP access to the published backend.
- **Exploit/failure impact:** If these canonical Compose files are deployed without an external edge control, credentials, bearer access tokens, and refresh-cookie traffic can traverse plaintext or bypass the intended HTTPS origin. The current source set cannot prove the SPEC/ASVS external-communication requirement.
- **Disposition:** OPEN — medium because an external ingress may exist outside this repository, but that deployment boundary is not specified or verified by canonical Phase 1 evidence.
- **Required resolution:** Encode a TLS-terminating edge with trusted certificates and HSTS, or explicitly define and verify the external ingress contract while binding the backend to a non-public interface/network and preventing direct plaintext host access. Ensure health probes remain internal.
- **Verification:** From an external client, HTTP must redirect or be unreachable, HTTPS must use an approved TLS version and trusted certificate, HSTS must be present on browser responses, and the backend's plaintext port must not be externally reachable. Add deploy-smoke assertions for these properties.

### VF-SEC-007 — Current npm audit reports moderate dev-tool vulnerability records

- **Severity:** low
- **Control:** `v5.0.0-V15.1.1`, `v5.0.0-V15.2.1`
- **Path/line/evidence:** A current `npm audit --package-lock-only --audit-level=low --json` against `frontend/package-lock.json` reported `typed-rest-client@2.3.1` and nested `qs@6.15.1` as moderate, with a fix available for GHSA-q8mj-m7cp-5q26. `npm ls typed-rest-client qs --all` attributed the affected nested copy to development-only `@stryker-mutator/core@10.0.0`; the runtime `shadcn` tree resolves `qs@6.15.3`. `tools/gauntlet.sh:417-419` uses `npm audit --audit-level=high`, so this does not fail the current gate.
- **Exploit/failure impact:** The vulnerable code is not shipped in the SPA runtime, materially reducing product exploitability, but it executes in trusted developer/CI mutation tooling and remains a supply-chain maintenance debt.
- **Disposition:** OPEN — low; does not block this review's critical/high count, but requires a time-bound disposition under the component-remediation policy.
- **Required resolution:** Upgrade the affected Stryker/tooling chain to a compatible fixed dependency when available, apply a lockfile override only after compatibility tests, or record a dated risk acceptance with owner and remediation deadline.
- **Verification:** Re-run the low-threshold package-lock audit and dependency attribution; confirm the affected `qs` range is absent or that the documented acceptance remains current. Keep high/critical audit failure behavior intact.

## Positive security observations

- Access tokens are short-lived, signed with an allowlisted configured algorithm, checked for issuer/audience/type/time claims and durable `token_version`, and never stored by the reviewed E2E flow in Web Storage.
- Refresh tokens are opaque random values stored only as hashes server-side, rotate transactionally, and revoke a family on replay. Logout and password change invalidate durable authority.
- Authentication and authenticated status rate limits use Redis and fail closed on Redis errors for authority-changing flows; user-facing errors are bounded and sanitized.
- Role authority is resolved server-side; the client receives presentation identifiers rather than becoming authoritative.
- Password hashes use Argon2 and password-change/bootstrap code avoids plaintext persistence and command-line secrets.
- Database schema constraints, normalization, uniqueness, foreign keys, and migration downgrade/upgrade paths are extensively tested.
- CORS uses configured origins rather than a wildcard, and credential support is constrained to the allowlist.
- Lockfiles contain artifact integrity data, and focused Python dependency auditing found no known third-party Python vulnerability.

These positives do not offset or close the findings above.

## Gate conclusion

The reviewed state is **not eligible** for Phase 1 review closure or final gauntlet evidence. Four high findings remain open. In particular, the canonical digest omits frontend source, the full gauntlet does not enforce the review gate, and two mandatory gauntlet layers contain deterministic control-flow failures. No claim is made that `tools/gauntlet.sh` completed successfully; it was not run in full during this review.

Required next sequence:

1. Add focused failing tests/controls for each review-driven fix.
2. Implement the minimal fixes and make those tests green.
3. Run applicable focused regressions and verifier self-tests.
4. Recompute `tools/source_state.sh --review-digest`; the digest must change.
5. Request a genuinely new fresh-context code/security review of the new canonical source set.
6. Only after that review is CLOSED with zero critical/high findings may the complete final gauntlet and evidence round begin.
