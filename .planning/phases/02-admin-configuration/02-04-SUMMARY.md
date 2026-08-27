---
phase: 02-admin-configuration
plan: 04
subsystem: bitbucket-oauth
tags: [oauth2, cryptography, fernet, postgresql, redis, tdd]

requires:
  - phase: 01-platform-foundation
    provides: Provider-independent administrator authority, PostgreSQL/Alembic, Redis, and Celery boundaries
  - phase: 02-admin-configuration
    plan: 03
    provides: Credential-free global Repository UUID registry
provides:
  - Exactly one generation-bound organizational Bitbucket OAuth connection
  - Authenticated encrypted access and refresh token persistence behind a narrow SecretBox
  - Single-use digest-only OAuth state bound to admin, session, callback, generation, and fixed SPA destination
  - Reproducible PostgreSQL migration, coverage, mutation, and secret-scan evidence
affects: [02-05-oauth-admin-api, 02-06-oauth-admin-ui, 02-07-oauth-status, 02-19-bitbucket-integration, 02-20-phase-gauntlet]

actuals:
  tokens: 16717
  tasks: 3
  commits: 10

tech-stack:
  added: [cryptography==50.0.1]
  patterns:
    - MultiFernet encryption with first-key writes and bounded all-key reads
    - SHA-256-digest-only Redis OAuth state with atomic consumption
    - Locked singleton row as durable provider-generation authority

key-files:
  created:
    - backend/alembic/versions/0004_bitbucket_connection.py
    - backend/src/verboflex/models/bitbucket_connection.py
    - backend/src/verboflex/security/__init__.py
    - backend/src/verboflex/security/secret_box.py
    - backend/src/verboflex/services/bitbucket_oauth.py
    - backend/tests/integration/test_bitbucket_oauth.py
    - tools/verify_bitbucket_oauth_mutants.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
    - backend/src/verboflex/core/config.py
    - backend/src/verboflex/models/__init__.py

key-decisions:
  - "Represent organizational OAuth authority with exactly one `id = 1` row whose monotonic generation invalidates stale provider work."
  - "Keep authenticated encryption behind SecretBox; MultiFernet writes with the first configured key and reads with every configured rotation key."
  - "Persist only the SHA-256 state digest in Redis for 600 seconds, bound to admin UUID, internal session UUID, generation, exact callback, and fixed SPA destination."
  - "Require the exact Bitbucket `repository` scope and reject replay, binding mismatch, provider failure, tampering, and decryption failure before credential mutation."

patterns-established:
  - "Secret boundary: plaintext provider credentials exist only at the in-process exchange/encryption boundary and never in model representations, Redis state, logs, errors, audit details, or schema metadata."
  - "Generation authority: every successful connection/reconnection advances one locked singleton generation for downstream stale-work rejection."
  - "OAuth callback: state is random, digest-only, single-use, expiring, and cannot carry an attacker-controlled redirect."

requirements-completed: [BITB-01]

coverage:
  - id: D1
    description: "The singleton OAuth connection persists exact-scope access and refresh tokens only as authenticated ciphertext and exposes bounded status."
    requirement: BITB-01
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_oauth.py#test_connects_single_encrypted_repository_scope_generation"
        status: pass
      - kind: mutation
        ref: "tools/verify_bitbucket_oauth_mutants.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "OAuth state is single-use, digest-only, expiring, and bound to the initiating administrator, internal session, callback, generation, and fixed destination."
    requirement: BITB-01
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_oauth.py#test_oauth_configuration_state_and_binding_rejections_fail_closed"
        status: pass
    human_judgment: false
  - id: D3
    description: "Wrong keys, ciphertext tampering, malformed keyrings, and provider failures reject with stable bounded errors and no plaintext representation or mutation."
    requirement: BITB-01
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_oauth.py#test_secret_box_rejects_wrong_key_tamper_and_plaintext_representations"
        status: pass
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_oauth.py#test_secret_box_drives_oauth_persistence_without_secret_metadata"
        status: pass
    human_judgment: false
  - id: D4
    description: "Explicit model registration supports a clean PostgreSQL upgrade, downgrade, and second upgrade with named singleton constraints."
    requirement: BITB-01
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_bitbucket_oauth.py#test_bitbucket_singleton_metadata_survives_postgresql_rehearsal"
        status: pass
    human_judgment: false

duration: 32min
completed: 2026-08-27
status: complete
---

# Phase 02 Plan 04: Encrypted Bitbucket OAuth Foundation Summary

**A single generation-bound organizational Bitbucket connection now uses digest-only OAuth state and authenticated encrypted token storage, with fail-closed PostgreSQL and mutation evidence.**

## Performance

- **Active duration:** 32 min, excluding package-legitimacy and tracer-approval waits
- **Started:** 2026-08-27T07:09:25Z
- **Completed:** 2026-08-27T07:41:14Z
- **Tasks:** 3, including the three independently approved package-provenance dispositions
- **Files modified:** 11 implementation, migration, dependency, test, and evidence artifacts
- **Actual estimate scale:** 16,717 tokens (66,868 realized diff characters / 4)

## Accomplishments

- Added one named-constraint PostgreSQL singleton whose monotonic generation is the durable authority for later Bitbucket work.
- Added single-use 32-byte OAuth state stored only as a SHA-256 digest for 600 seconds and atomically consumed with complete initiator and callback binding.
- Added a narrow MultiFernet-backed `SecretBox` with redacted representation, configured rotation reads, and stable wrong-key/tamper rejection.
- Persisted only encrypted access and refresh tokens while bounding API state, logs, exceptions, audit metadata, and schema/provider diagnostic material.
- Proved clean upgrade → downgrade → upgrade, 100% changed-line coverage, five killed security mutants, zero scanned secrets, and no known dependency vulnerabilities.

## Package Legitimacy Dispositions

The user approved each package independently before implementation:

| Package | Disposition | Plan 02-04 outcome |
|---------|-------------|--------------------|
| `httpx==0.28.1` | Approved for official project identity, Python 3.14, and Linux-container compatibility | Already present in the backend graph; not newly promoted by this plan. |
| `defusedxml==0.7.1` | Approved for official project identity, Python 3.14, and Linux-container compatibility | Already present in the backend graph; not newly promoted by this plan. |
| `cryptography==50.0.1` | Approved for official PyCA provenance, Python 3.14, and Linux-container compatibility | Added as the exact runtime dependency and verified at runtime as `50.0.1`. |

## Task Commits

Each TDD and evidence gate was committed atomically:

1. **Task 2 RED: encrypted OAuth tracer contract** — `8fada64` (test)
2. **Task 2 GREEN: encrypted OAuth connection tracer** — `490f81c` (feat)
3. **Task 3 RED: secret-storage hardening contract** — `6b9f788` (test)
4. **Task 3 GREEN: authenticated secret storage** — `f54c033` (feat)
5. **Task 3 REFACTOR: OAuth rejection test contexts** — `e6d62ca` (refactor)
6. **Task 3 format correction: singleton constraints** — `8f24188` (style)
7. **Task 3 evidence: reproducible OAuth mutation proof** — `a1071b8` (test)
8. **Task 3 evidence: fail-closed branch coverage** — `5eac903` (test)
9. **Task 3 format correction: mutation runner** — `3265f25` (style)
10. **Task 3 secret-scan fixture classification** — `b114db6` (test)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 2 RED:** the exact tracer command failed on the missing encrypted OAuth behavior (`8fada64`).
- **Task 2 GREEN:** the unchanged tracer command passed after the minimal singleton, migration, settings, digest-only state, and encrypted persistence landed (`490f81c`).
- **Task 2 REFACTOR:** the unchanged tracer command passed again and no cleanup was justified, so no empty refactor commit was created; the user explicitly approved the tracer feedback gate.
- **Task 3 RED:** `cd backend && uv run pytest -q tests/integration/test_bitbucket_oauth.py -x` failed with `ModuleNotFoundError: No module named 'verboflex.security'` while the Task 2 tracer still passed (`6b9f788`).
- **Task 3 GREEN:** the unchanged exact command passed 4/4 after `SecretBox`, explicit metadata registration, and service integration landed (`f54c033`).
- **Task 3 REFACTOR:** the unchanged exact command remained 4/4 after test context cleanup (`e6d62ca`).
- **Final exact proof:** the same unchanged Task 3 command passes 5/5 after fail-closed coverage armor.

## Verification and Gauntlet Evidence

- Exact Task 3/plan command: **5 passed**.
- Exact dependency check: **`cryptography 50.0.1`**.
- PostgreSQL migrations plus real Redis/Celery worker smoke: **7 passed**.
- Full backend suite with deterministic collection order: **343 passed**.
- Default `pytest-randomly` run: **341 passed, 2 out-of-scope admin-user ordering failures**; the same parametrized test passes **15/15** in isolation and is recorded in `deferred-items.md`.
- Ruff lint and formatting: **89 files checked, pass**.
- mypy: **51 backend source files plus the strict mutation tool, pass**.
- Differential coverage against `34c52d4`: **100% (197/197 changed OAuth source lines)**; all OAuth production modules report 100% statement/branch coverage.
- Full-repository coverage is 99%; the 15 uncovered lines are pre-existing admin-user/API paths outside this plan.
- Mutation checker negative control passed; all five reviewed security mutants were killed (**5/5**): state digest, generation binding, exact repository scope, plaintext persistence, and bounded decryption failure.
- `detect-secrets` returned **0 findings** across every changed dependency, migration, source, test, and evidence artifact; the sole fake test credential is marked as an exact inline allowlist fixture.
- `pip-audit` found **no known vulnerabilities**; the local `verboflex` package was the sole expected non-PyPI skip. `pip-licenses` confirmed `cryptography 50.0.1` as `Apache-2.0 OR BSD-3-Clause` from the official PyCA project URL.
- Stub scan found no production placeholder, TODO, FIXME, or empty UI-bound value.

## Security Contract Review

- The browser receives no provider credential and can only observe bounded connection state, generation, scope profile, and fixed post-callback destination.
- Redis contains only a SHA-256 state digest and JSON binding metadata; neither raw state nor OAuth/client/provider secrets are stored there.
- The provider exchange boundary accepts the client secret only in process; raw provider response/error bodies are converted to bounded internal failures and never persisted or logged.
- SQLAlchemy and Alembic expose ciphertext columns only; model, `SecretBox`, status, binding, and error representations contain no token plaintext.
- Callback validation consumes state before exchange and rejects replay, expiry, tampering, wrong admin/session/generation/callback, non-string code, wrong scope, and open redirect without credential mutation.

## Files Created/Modified

- `backend/src/verboflex/models/bitbucket_connection.py` and `backend/alembic/versions/0004_bitbucket_connection.py` — singleton generation authority, encrypted columns, named checks, and reversible PostgreSQL schema.
- `backend/src/verboflex/security/secret_box.py` and `backend/src/verboflex/security/__init__.py` — narrow authenticated encryption boundary and bounded errors.
- `backend/src/verboflex/services/bitbucket_oauth.py` — state creation/consumption, exchange authority, exact scope, encryption, locking, and bounded status.
- `backend/src/verboflex/core/config.py` and `backend/src/verboflex/models/__init__.py` — typed OAuth/keyring settings and explicit mapped-class registration.
- `backend/pyproject.toml` and `backend/uv.lock` — exact `cryptography==50.0.1` runtime dependency and resolved graph.
- `backend/tests/integration/test_bitbucket_oauth.py` — complete tracer, hostile-state, secret-box, metadata, logging, schema, and PostgreSQL rehearsal evidence.
- `tools/verify_bitbucket_oauth_mutants.py` — fail-closed negative control and five targeted OAuth security mutations.

## Decisions Made

- One `id = 1` row is the only organizational connection and generation linearization point; downstream provider work must carry and revalidate its generation.
- `SecretBox` is the only token encryption/decryption abstraction; callers never manipulate Fernet primitives or serialize plaintext representations.
- State storage remains digest-only and callback destinations remain server-fixed; neither browser input nor OAuth state can select a redirect path.
- OAuth scope comparison is exact (`repository`), leaving later write-capability expansion to an explicit future decision.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical evidence] Added reproducible mutation proof and closed fail-closed branches**
- **Found during:** Task 3 final evidence gate
- **Issue:** Initial differential coverage was 95% and ordinary passing tests alone did not prove the highest-risk security assertions could detect behavioral regressions.
- **Fix:** Added hostile configuration/state branches and a fail-closed mutation runner with a negative control and five reviewed mutants.
- **Files modified:** `backend/tests/integration/test_bitbucket_oauth.py`, `tools/verify_bitbucket_oauth_mutants.py`
- **Verification:** Differential coverage is 100% (197/197) and all five mutants are killed.
- **Committed in:** `a1071b8`, `5eac903`

**2. [Rule 3 - Blocking quality gate] Applied repository formatting and exact secret-fixture classification**
- **Found during:** Task 3 final lint and secret-scan gates
- **Issue:** Task 2 constraint formatting and the new mutation tool were not canonical under Ruff; `detect-secrets` correctly flagged the explicit fake client-secret assertion.
- **Fix:** Applied formatting without behavior changes and marked only the exact fake assertion with an inline test-fixture allowlist.
- **Files modified:** `backend/src/verboflex/models/bitbucket_connection.py`, `backend/alembic/versions/0004_bitbucket_connection.py`, `tools/verify_bitbucket_oauth_mutants.py`, `backend/tests/integration/test_bitbucket_oauth.py`
- **Verification:** Ruff lint/format passes, the exact OAuth suite passes 5/5, and the secret scan reports zero findings.
- **Committed in:** `8f24188`, `3265f25`, `b114db6`

---

**Total deviations:** 2 auto-fixed (one missing critical evidence requirement and one blocking quality gate).
**Impact on plan:** Both additions strengthen evidence and repository hygiene without changing the approved OAuth architecture or external capability boundary.

## Issues Encountered

- Context7 was unavailable; version-specific Fernet and MultiFernet behavior was verified against official `cryptography` documentation before implementation.
- Initial changed-line coverage was 95%; meaningful fail-closed tests raised the exact OAuth source surface to 100%.
- The default randomized full suite exposed a pre-existing admin-user role-order isolation defect. No Phase 02 Plan 04 source or test touches that subsystem; the deterministic full suite passes 343/343 and the defect is recorded in `deferred-items.md`.
- Verification used an ephemeral Redis 7 container and a Celery solo worker; both were stopped after the final evidence run.

## Authentication Gates

None.

## Known Stubs

None.

## User Setup Required

None for this mocked foundation. Live Bitbucket client registration and credentials remain explicitly deferred to the later integration/gauntlet plan.

## Next Phase Readiness

- Plan 02-05 can expose the guarded administrator connect/reconnect/revoke/status API over this singleton service boundary.
- Later provider jobs can reject stale work by comparing the captured connection generation to the locked singleton generation.
- `BITB-01` is marked complete in the shared requirement ledger after this plan's executable foundation evidence passed.

## Self-Check: PASSED

- All 11 implementation, migration, dependency, test, and evidence artifacts listed above exist.
- All ten Task 2 and Task 3 commits exist on `codex/phase-2-admin-configuration` in valid RED → GREEN → RED → GREEN → REFACTOR order.
- Exact focused, dependency, PostgreSQL migration, worker, deterministic full regression, lint, format, type, changed-line coverage, mutation-control, dependency-audit, license, secret-scan, and stub-scan claims were rerun after the final test change.
- The randomized-suite defect is explicitly deferred rather than hidden or fixed outside this plan.
- No tracked deletion, unresolved plan stub, unrun plan verification, or unintended generated artifact remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-27*
---
