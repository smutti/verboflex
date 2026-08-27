---
phase: 02-admin-configuration
plan: 06
subsystem: bitbucket-http-adapter
tags: [httpx, bitbucket, oauth2, ssrf, tdd]

requires:
  - phase: 02-admin-configuration
    plan: 04
    provides: Encrypted organizational Bitbucket credentials and approved HTTPX provenance
  - phase: 02-admin-configuration
    plan: 05
    provides: Generation-serialized reconnect, refresh, and immediate local revocation
provides:
  - Pooled read-only Bitbucket HTTPX adapter bound to the current credential generation
  - Exact HTTPS api.bitbucket.org endpoint-family allowlist for the ten approved integration rows
  - Stale-response discard across reconnect and revoke races
  - Architecture and mutation evidence that the adapter cannot expose provider mutation capabilities
affects: [02-07-admin-bitbucket-ui, 02-19-bitbucket-integration, 02-20-phase-gauntlet]

actuals:
  tokens: 11010
  tasks: 2
  commits: 7

tech-stack:
  added:
    - httpx==0.28.1 promoted from development-only to exact runtime dependency
  patterns:
    - Validate every initial and provider-supplied URL before acquiring or forwarding a bearer token
    - Acquire a generation lease before transport and reject its result after any generation change
    - Keep provider capability equal to an explicit endpoint-family allowlist rather than a generic HTTP client

key-files:
  created:
    - backend/src/verboflex/integrations/__init__.py
    - backend/src/verboflex/integrations/bitbucket/__init__.py
    - backend/src/verboflex/integrations/bitbucket/client.py
    - backend/src/verboflex/integrations/bitbucket/urls.py
    - backend/tests/architecture/test_provider_boundaries.py
    - tools/verify_bitbucket_http_adapter_mutants.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
    - backend/src/verboflex/core/config.py
    - backend/src/verboflex/services/bitbucket_oauth.py
    - backend/tests/integration/test_bitbucket_http_adapter.py

key-decisions:
  - "Expose only repository metadata, branch list/detail, and commit-bound source tree/raw reads; reject every other Bitbucket endpoint family before credential acquisition."
  - "Use one pooled HTTPX client with redirects, ambient proxy trust, content decoding, and hidden retries disabled or constrained at construction."
  - "Treat a generation change during a response as revocation: discard the provider result even if the HTTP request itself succeeded."

patterns-established:
  - "Provider URL boundary: parsed HTTPS URLs must target exact api.bitbucket.org with no userinfo or explicit port and must match one approved read endpoint family."
  - "Provider response boundary: status, media type, JSON shape, size, and credential generation are validated before data can reach a caller."
  - "Capability boundary: architecture tests freeze the adapter's public methods and reject write verbs and excluded Bitbucket resource families."

requirements-completed: [BITB-03, BITB-04]

coverage:
  - id: D1
    description: "All approved Bitbucket reads cross one pooled, bounded, redirect-free, identity-encoded transport without automatic retry or ambient proxy authority."
    requirement: BITB-03
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_http_adapter.py"
        status: pass
      - kind: other
        ref: "backend/tests/architecture/test_provider_boundaries.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Initial, redirect, and pagination URLs fail closed unless they are exact approved HTTPS api.bitbucket.org read endpoints, before bearer-token forwarding."
    requirement: BITB-03
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_http_adapter.py"
        status: pass
      - kind: other
        ref: "tools/verify_bitbucket_http_adapter_mutants.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Reconnect or revoke before or during a response invalidates the generation lease and discards the stale result."
    requirement: BITB-04
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_http_adapter.py"
        status: pass
      - kind: other
        ref: "tools/verify_bitbucket_http_adapter_mutants.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "The adapter exposes no repository search/list, account, tag/ref, write, branch-create, commit, pull-request, webhook, admin, pipeline, issue, or download capability outside the ten approved COVERAGE INTEGRATE rows."
    requirement: BITB-04
    verification:
      - kind: other
        ref: "backend/tests/architecture/test_provider_boundaries.py"
        status: pass
      - kind: other
        ref: "tools/verify_bitbucket_http_adapter_mutants.py"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-27
status: complete
---

# Phase 02 Plan 06: Safe Bitbucket Provider Transport Summary

**A generation-bound HTTPX adapter now limits Bitbucket access to the ten approved read integrations, rejects hostile or excluded URLs before credential forwarding, and discards responses invalidated by reconnect or revoke.**

## Performance

- **Active duration:** 20 min, excluding the completed tracer approval wait
- **Started:** 2026-08-27T10:20:26Z
- **Completed:** 2026-08-27T10:40:34Z
- **Tasks:** 2
- **Files modified:** 11 runtime, configuration, lock, test, architecture, and evidence artifacts
- **Actual estimate scale:** 11,010 tokens (44,038 realized diff characters / 4)

## Accomplishments

- Promoted the previously approved exact `httpx==0.28.1` package into runtime use and constructed one pooled asynchronous client with explicit timeouts, redirects disabled, identity encoding, no transport retry, and no ambient proxy trust.
- Added a fail-closed parsed-URL boundary that accepts only exact `api.bitbucket.org` HTTPS repository metadata, branch list/detail, and commit-bound source tree/raw reads represented by the ten approved COVERAGE INTEGRATE rows.
- Bound every request to an OAuth credential generation and rechecked that generation after the response, so reconnect or revoke discards work completed under stale authority.
- Froze the read-only public capability surface with architecture tests and a fail-closed mutation runner that killed transport, generation, scope, and URL-validation regressions.

## Task Commits

Each TDD and evidence gate was committed atomically:

1. **Task 1 RED: safe metadata transport contract** — `71448b5` (test)
2. **Task 1 GREEN: pooled generation-bound metadata transport** — `cd1a1ab` (feat)
3. **Task 2 RED: stale-generation and provider-capability contract** — `d1a8d33` (test)
4. **Task 2 GREEN: exact read endpoint-family enforcement** — `219a5fd` (feat)
5. **Plan evidence: hostile input and real lease coverage** — `2f2c94a` (test)
6. **Plan evidence: reproducible provider-boundary mutation proof** — `c1ec0e1` (test)
7. **Secret-scan fixture classification** — `019b6c3` (test)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 1 RED:** the exact `cd backend && uv run pytest -q tests/integration/test_bitbucket_http_adapter.py::test_reads_metadata_only_through_validated_current_generation -x` command failed before the safe adapter existed (`71448b5`).
- **Task 1 GREEN:** the unchanged command passed 1/1 after the minimal pooled, generation-bound metadata read was implemented (`cd1a1ab`).
- **Task 1 REFACTOR:** the unchanged command remained 1/1; no justified refactor existed, so no empty commit was created. The user approved the tracer checkpoint.
- **Task 2 RED:** the exact `cd backend && uv run pytest -q tests/integration/test_bitbucket_http_adapter.py tests/architecture/test_provider_boundaries.py -x` command failed because excluded Bitbucket endpoint families were still accepted (`d1a8d33`).
- **Task 2 GREEN:** the unchanged command passed 7/7 after the minimal exact endpoint-family validator landed (`219a5fd`).
- **Task 2 REFACTOR:** the unchanged command remained 7/7; no behavior-preserving source refactor was warranted, so no empty commit was created.
- **Final exact proof:** the unchanged Task 2 command passes 9/9 after hostile-input, real-lease, construction-policy, and mutation evidence was added.

## Verification and Gauntlet Evidence

- Exact Task 2 and plan verification command: **9 passed**.
- OAuth, administrator lifecycle, and migration regression at randomized seed `4`: **21 passed**.
- Full backend regression at randomized seed `4`, using the project PostgreSQL plus an isolated temporary Redis 7 and Celery solo worker: **367 passed in 28.13s**; the temporary worker and container were stopped and removed afterward.
- Architecture suite at randomized seed `4`: **7 passed**.
- Ruff lint: **all checks passed**; Ruff format: **100 files already formatted**.
- mypy: **60 source/evidence files, no issues**.
- Changed-line coverage against `71448b5^`: **100% (112/112 changed lines)** with `diff-cover --fail-under=100`.
- Mutation checker negative control reached its failure path; baseline passed; **10/10 mutants killed** across redirect following, ambient proxy trust, retry, HTTP verb, pre/post generation checks, scope, URL family, explicit port, and lease generation.
- `uv lock --check` resolved **112 packages**; the runtime dependency is exact `httpx 0.28.1`.
- `pip-audit` found **no known vulnerabilities**; the local `verboflex` package was the only expected non-PyPI skip.
- License gate confirmed `httpx 0.28.1` and `httpcore 1.0.9` as BSD, `defusedxml 0.7.1` as PSF, and `cryptography 50.0.1` as Apache-2.0 or BSD-3-Clause.
- `detect-secrets` returned **0 findings** over the complete changed surface.
- Frontend canonical API check passed, and no package, OpenAPI, or generated-client drift was introduced by this backend-only seam.
- Stub scan found no placeholder, TODO, FIXME, skipped test, empty UI-bound value, or unrun verification introduced by this plan.

## Security Contract Review

- URL validation happens before OAuth credential lease acquisition; invalid scheme, userinfo, explicit port, host, path, redirect, or pagination link cannot receive the bearer token.
- Transport construction denies redirects, environment-derived proxy authority, content transformation, and automatic retries; timeouts are explicit for connect, read, write, and pool phases.
- Provider failures expose bounded sanitized errors without access tokens, refresh tokens, raw provider bodies, or untrusted response diagnostics.
- The post-response generation check turns reconnect and local revoke into an immediate authorization barrier for in-flight work.
- The public adapter surface is read-only and maps only to the ten approved repository integrations; generic request methods and provider mutations are absent and architecture-tested.

## Files Created/Modified

- `backend/src/verboflex/integrations/bitbucket/client.py` — pooled read-only HTTPX transport, response bounds, sanitized failures, pagination, and generation checks.
- `backend/src/verboflex/integrations/bitbucket/urls.py` — central exact-host and endpoint-family URL validator.
- `backend/src/verboflex/core/config.py` — explicit provider transport timeout and response-size limits.
- `backend/src/verboflex/services/bitbucket_oauth.py` — current-generation credential lease consumed by the adapter.
- `backend/pyproject.toml` and `backend/uv.lock` — exact approved HTTPX runtime dependency and reproducible lock.
- `backend/tests/integration/test_bitbucket_http_adapter.py` — safe transport, hostile input, redirects, pagination, scope, malformed response, and stale-generation evidence.
- `backend/tests/architecture/test_provider_boundaries.py` — frozen method, HTTP verb, endpoint-family, and construction-policy boundary.
- `tools/verify_bitbucket_http_adapter_mutants.py` — fail-closed negative control and ten reproducible provider-boundary mutants.

## Decisions Made

- Endpoint-family validation is explicit and exhaustive; future Bitbucket capabilities require a deliberate COVERAGE contract and validator change instead of inheriting generic HTTP access.
- A successful provider response has no authority after the credential generation changes; correctness is determined both before request dispatch and after response completion.
- HTTPX remains private transport infrastructure. Repository integration plans consume typed read methods rather than receiving the pooled client or arbitrary request primitive.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Closed evidence gaps around hostile input, real leases, and transport construction**
- **Found during:** Plan gauntlet
- **Issue:** The planned behavioral tests proved the central path but did not yet execute every security-relevant changed line or freeze all construction invariants that make redirects, proxies, and retries impossible.
- **Fix:** Added hostile URL/response cases, actual OAuth service lease variants, decrypt failure evidence, and architecture assertions for the HTTPX construction policy.
- **Files modified:** `backend/tests/integration/test_bitbucket_http_adapter.py`, `backend/tests/architecture/test_provider_boundaries.py`
- **Verification:** Changed-line coverage is 112/112; full backend regression is 367/367; mutation proof kills 10/10.
- **Committed in:** `2f2c94a`, `c1ec0e1`

**2. [Rule 3 - Blocking Quality] Classified an explicit fake basic-auth URL fixture without weakening the secret gate**
- **Found during:** Secret scan
- **Issue:** The intentionally hostile `user:password@host` test fixture matched the repository's secret detector even though it contained no credential.
- **Fix:** Constructed the fake credential text from explicit fragments and annotated the exact line as an allowlisted test secret; runtime input and rejection assertion are unchanged.
- **Files modified:** `backend/tests/integration/test_bitbucket_http_adapter.py`
- **Verification:** The hostile URL test still passes and `detect-secrets` reports zero findings over the changed surface.
- **Committed in:** `019b6c3`

---

**Total deviations:** 2 auto-fixed (1 missing critical evidence boundary, 1 blocking quality classification)
**Impact on plan:** Both changes strengthen reproducibility and security evidence without broadening the approved provider capability surface.

## Issues Encountered

- The final randomized backend run required an isolated Redis and Celery worker in addition to the existing project PostgreSQL. Both were started for the gauntlet and removed after the 367-test pass; no runtime container or port residue remains.

## Authentication Gates

None. The user-approved tracer verification checkpoint was planned flow and required no provider credentials.

## Known Stubs

None.

## User Setup Required

None for this adapter. Live Bitbucket credentials and final local OAuth verification remain explicitly deferred to the phase's dedicated end-to-end plan.

## Next Phase Readiness

- Plan 02-07 can build the administrator connection UI against the existing lifecycle API without exposing provider transport internals.
- Later repository read plans can use the bounded adapter for only the approved metadata, branch, and commit-bound source operations.
- No open blocker, stub, skipped test, unrun verification, secret finding, dependency vulnerability, or generated-client drift remains.

## Self-Check: PASSED

- Every runtime, configuration, lock, test, architecture, evidence, and summary artifact listed above exists.
- All seven plan commits exist on `codex/phase-2-admin-configuration` in valid Task 1 and Task 2 RED then GREEN order; both no-change REFACTOR gates were rerun with unchanged commands.
- Coverage metadata maps BITB-03 and BITB-04 to four machine-proven deliverables with no human-judgment dependency.
