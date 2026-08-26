---
phase: 01-platform-foundation
plan: 05
subsystem: auth
tags: [postgresql, sqlalchemy, alembic, argon2, tdd, concurrency]

requires:
  - phase: 01-platform-foundation
    plan: 04
    provides: Typed PostgreSQL settings and the secure deployment baseline
provides:
  - Reversible provider-independent users, roles, user-role, and refresh-session schema
  - Normalized corporate-email and Unicode Argon2 password primitives
  - Atomic first-admin bootstrap and administrative password-reset CLI
affects: [oauth2, refresh-rotation, authorization, admin-operations]

actuals:
  tokens: 15240
  tasks: 2
  commits: 22

tech-stack:
  added: []
  patterns:
    - Serialize first-admin creation with a PostgreSQL transaction advisory lock
    - Persist only Argon2 password hashes and opaque refresh-token hashes
    - Invalidate durable authority by incrementing token_version and revoking sessions atomically

key-files:
  created:
    - backend/alembic/versions/0001_auth_foundation.py
    - backend/src/verboflex/models/user.py
    - backend/src/verboflex/models/role.py
    - backend/src/verboflex/models/auth_session.py
    - backend/src/verboflex/auth/identity.py
    - backend/src/verboflex/auth/passwords.py
    - backend/src/verboflex/cli.py
    - backend/tests/integration/test_migrations.py
    - backend/tests/auth/test_bootstrap_admin.py
    - backend/tests/auth/test_passwords.py
  modified:
    - backend/pyproject.toml

key-decisions:
  - "Corporate-email normalization trims only the database-aligned ASCII whitespace set, lowercases, validates, and remains provider-independent."
  - "A PostgreSQL transaction advisory lock serializes the empty-user decision so concurrent bootstrap attempts leave exactly one admin."
  - "Administrative reset locks the selected user, rehashes the password, forces a password change, increments token_version, and revokes only that user's live sessions in one transaction."
  - "Passwords enter the CLI only through getpass or stdin; argv, defaults, logs, and plaintext persistence are forbidden."

patterns-established:
  - "Auth persistence: migration constraints and SQLAlchemy metadata express the same provider-independent authority model."
  - "Privileged CLI: normalize and validate before opening authority-changing transactions, then fail with non-secret diagnostics."

requirements-completed: [PLAT-04, PLAT-05, AUTH-01, AUTH-04]

coverage:
  - id: D1
    description: A clean PostgreSQL database upgrades, downgrades, and upgrades to the exact auth schema without residual state
    requirement: PLAT-05
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_migrations.py#test_auth_schema_upgrades_downgrades_and_upgrades_reversibly"
        status: pass
    human_judgment: false
  - id: D2
    description: SQLAlchemy persists provider-independent users, exact roles, many-to-many assignments, and hashed refresh-session lineage
    requirement: PLAT-04
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_migrations.py"
        status: pass
    human_judgment: false
  - id: D3
    description: The first admin and reset credentials are managed atomically through a non-secret Argon2 CLI boundary
    requirement: AUTH-01
    verification:
      - kind: integration
        ref: "backend/tests/auth/test_bootstrap_admin.py"
        status: pass
      - kind: other
        ref: "python -m verboflex.cli bootstrap-admin/reset-password PostgreSQL smoke"
        status: pass
    human_judgment: false
  - id: D4
    description: The exact admin, product_manager_reviewer, translator, and viewer roles are seeded once each
    requirement: AUTH-04
    verification:
      - kind: integration
        ref: "backend/tests/integration/test_migrations.py#assert_auth_schema"
        status: pass
    human_judgment: false

duration: 29 min
completed: 2026-08-24
status: complete
---

# Phase 1 Plan 5: Durable Authentication Foundation Summary

**VerboFlex now has a reversible PostgreSQL authentication schema and a concurrency-safe, non-secret CLI for establishing and recovering the first internal administrator.**

## Performance

- **Duration:** 29 min
- **Started:** 2026-08-24T15:40:00Z
- **Completed:** 2026-08-24T16:09:00Z
- **Tasks:** 2
- **Files modified:** 19 before plan close-out metadata

## Accomplishments

- Added a reversible Alembic migration for users, the four exact roles, many-to-many user roles, and hashed refresh-session rotation families, with PostgreSQL constraints, indexes, and foreign-key behavior rehearsed on real databases.
- Added one canonical corporate-email seam and a 12-128 Unicode-character password policy backed by Argon2, including property and deterministic boundary tests.
- Added atomic first-admin bootstrap protected against concurrent creation and an administrative reset that rehashes credentials, forces password change, increments token authority, and revokes only live sessions belonging to the selected user.
- Exposed bootstrap/reset through `argparse` with secrets accepted only from terminal `getpass` or stdin and never from argv, defaults, output, or plaintext storage.

## Task Commits

Task 1 preserves migration RED/GREEN/REFACTOR chronology:

- **Reversible schema RED:** `f08a59f`, `f0a6292`
- **Reversible schema GREEN:** `627ad9f`
- **Schema refactor:** `c4a247a`

Task 2 preserves one-behavior-at-a-time RED/GREEN chronology:

- **Email normalization:** RED `60b296c`, GREEN `efe6e58`
- **Unicode password and Argon2:** RED `f406da3`, GREEN `81089de`, REFACTOR `1b283cc`
- **Atomic first-admin bootstrap:** RED `da57896`, GREEN `6c163f2`
- **Administrative reset and revocation:** RED `6f46127`, GREEN `f69b768`
- **Non-secret CLI:** RED `eb0bca8`, GREEN `bbd3c6b`, REFACTOR `d19d265`
- **Regression and mutation armor:** `06cf58d`, `007228d`, `e04056d`, `e8dd36b`, `b343597`, `240fb7e`

## RED/GREEN Evidence

- The migration RED connected to an isolated real PostgreSQL database and failed because the four expected tables were absent; it did not fail during import, collection, or infrastructure setup.
- The migration GREEN exercised upgrade to head, downgrade to base, and a second upgrade, then repeated the rehearsal with exact schema, role, constraint, index, cascade, restrict, and duplicate-email assertions.
- Bootstrap RED demonstrated missing create behavior, missing only-if-empty protection, and a concurrent race; GREEN serialized independent transactions and left exactly one active admin.
- Reset RED demonstrated the old hash, token version, password-change flag, and live sessions remained unchanged; GREEN changed all four authority dimensions in one transaction.
- CLI RED demonstrated missing protected-input dispatch and absence of reset wiring; GREEN passed the password through getpass/stdin only and returned non-secret outcomes.
- Throwaway mutants for a forbidden `--password` option, missing `AuthSession` metadata, disabled reset dispatch, and destructive stdin whitespace trimming were each killed and restored before proceeding.
- Tool-generated mutants exposed four meaningful gaps: non-ASCII email-boundary trimming, the inclusive 128-character password boundary, cross-user session isolation, and preservation of earlier revocation timestamps. Commit `240fb7e` added focused regression coverage; all four exact mutant IDs were then killed.
- The password property suite alone killed the 128-character off-by-one mutant through an explicit Hypothesis boundary example, then passed against clean source.

## TDD Gate Compliance

- Every planned behavior began with a collected behavioral assertion failure and has a later GREEN implementation commit.
- Bootstrap and reset retain separate RED and GREEN commits as required.
- No test was skipped, weakened, or broadened to manufacture GREEN.
- Final auth/persistence coverage is 100% statements and 100% branches across identity, password, CLI, database, and model modules; entrypoint-only `python -m` wiring is explicitly mapped to the exclusion allowed by the Phase 1 SPEC.

## Files Created/Modified

- `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_auth_foundation.py` - Callable migration environment and reversible security schema.
- `backend/src/verboflex/db/` - Declarative metadata, engine construction, and rollback-safe request session boundary.
- `backend/src/verboflex/models/` - Provider-independent users, roles, user-role assignments, and hashed refresh-session lineage.
- `backend/src/verboflex/auth/` - Canonical email normalization, Unicode password validation, Argon2 hashing, and verification.
- `backend/src/verboflex/cli.py` - Transactional bootstrap/reset services and protected-input command dispatcher.
- `backend/tests/integration/test_migrations.py` - Real-PostgreSQL reversible schema and constraint rehearsal.
- `backend/tests/auth/test_bootstrap_admin.py` - Bootstrap race, rollback, reset revocation, CLI, masking, and failure-boundary contracts.
- `backend/tests/auth/test_passwords.py` - Email normalization, malformed identity, Unicode length property, Argon2, and hash failure contracts.
- `backend/pyproject.toml` - Copies Alembic assets into the mutation runner sandbox; no dependency change.

## Decisions Made

- Advisory locking is transaction-scoped and protects the predicate "no user exists" across independent bootstrap transactions; table-level assumptions are not delegated to application timing.
- Email normalization and the database check constraint share the same surrounding ASCII whitespace set, while malformed or non-ASCII-padded identifiers fail with a generic diagnostic.
- Password length counts Python Unicode characters, retains spaces, applies no unapproved composition rule, and is inclusive at 12 and 128.
- Reset revokes only previously live sessions belonging to the selected user, preserving both other users' authority and earlier revocation audit timestamps.
- Microsoft Entra/OIDC fields remain absent; later external identity integration can map onto the internal provider-independent user and role model.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Copied migration assets into the mutmut sandbox**
- **Found during:** final Tier-3 mutation gate
- **Issue:** The clean mutation runner could import the source and tests but failed before mutation because its isolated tree omitted `alembic.ini` and the migration directory.
- **Fix:** Added only those existing project assets to mutmut's `also_copy` list; no dependency or application behavior changed.
- **Files modified:** `backend/pyproject.toml`
- **Verification:** mutmut clean tests, forced-fail control, and 272 generated mutants executed successfully.
- **Committed in:** `240fb7e`

**2. [Rule 1 - Correctness] Hardened meaningful boundaries found by mutation**
- **Found during:** final Tier-3 mutation gate
- **Issue:** Generated mutants demonstrated missing deterministic checks for the upper password boundary and session-revocation scoping/preservation.
- **Fix:** Added explicit property examples plus independent cross-user and existing-revocation integration contracts; also locked normalization to the approved ASCII boundary.
- **Files modified:** `backend/tests/auth/test_passwords.py`, `backend/tests/auth/test_bootstrap_admin.py`
- **Verification:** All four concrete mutant IDs changed from survived to killed; focused tests remain green.
- **Committed in:** `240fb7e`

---

**Total deviations:** 2 auto-fixed issues (1 blocking test-tool configuration, 1 correctness hardening). **Impact:** Assurance increased without expanding product scope or adding dependencies.

## Issues Encountered

- The first fail-closed coverage run reported 88%, revealing untested error and rollback paths. Focused behavioral tests raised it to 99.12%; the only remaining line was entrypoint-only wiring, mapped explicitly under the SPEC exclusion. The final thresholded run reports 100% statements and branches.
- The complete mutmut diagnostic generated 272 mutants: after bounded hardening, 187 were killed, 69 survived, and 16 pre-existing export-entrypoint mutants had no tests. Remaining survivors are primarily diagnostic/help-string changes, SQL case equivalence, ORM default equivalence, and pre-existing engine/entrypoint scope. They were not chased with artificial assertions; the plan threat register assigns the full mutation audit to Phase 9.
- The scoped secret scan flagged eight deliberate test credential fixtures. Each flagged line was inspected as non-production test input; the production source/config scan reported zero findings and the AWS-key negative control was detected.

## Verification Results

- `uv run pytest -q` - 65 passed with randomized order.
- Thresholded PostgreSQL/auth suite - 33 passed; 100% statements and branches across 202 statements and 20 branches.
- Real PostgreSQL migration rehearsal - upgrade, downgrade, upgrade plus exact roles/constraints/indexes; clean isolated database lifecycle.
- Concurrent bootstrap stress - 5/5 independent reruns passed with exactly one administrator per run.
- Real `python -m verboflex.cli` smoke - bootstrap and reset both exited 0, persisted one user, incremented token_version to 1, and emitted neither generated secret.
- `uv run mypy src tests` - no issues across 30 files.
- `uv run ruff check src tests alembic` / `uv run ruff format --check src tests alembic` - pass; 33 files formatted.
- `uv run radon cc ...` - average A 1.875; highest block `main` at B6.
- `uv run pip-audit` - no known vulnerabilities; local non-PyPI package intentionally skipped.
- `uv run pip-licenses` - dependency license inventory completed; no dependency was added by this plan.
- `detect-secrets` - known-bad AWS control detected; zero production findings; eight inspected test-fixture findings.
- `npm run api:check` - generated OpenAPI client remains drift-free.
- Source boundary scan - no Microsoft/Entra/OIDC/provider fields, `--password` option, plaintext token field, or refresh-token value exists in plan production files.
- Temporary container `verboflex-plan-0105-postgres` - explicitly stopped, removed, and verified absent after final PostgreSQL verification.

## Security Evidence

- **T-03-01 / elevation:** PostgreSQL advisory-lock concurrency contract and five repeated race runs leave one admin.
- **T-03-02 / disclosure:** passwords enter through getpass/stdin only, Argon2 is persisted, real CLI output contains no secret, and production secret scan is clean.
- **T-03-03 / tampering:** real PostgreSQL upgrade/downgrade/upgrade and rollback contracts pass against exact schema metadata.
- **T-03-04 / spoofing:** property-based idempotence, malformed/non-ASCII boundary rejection, application normalization, database check, and uniqueness constraints agree.
- **T-03-05 / repudiation:** token version and session revocation state are durable; the accepted full audit deferral remains assigned to Phase 9 by the plan.

## API Gate Resolution

- **Scope:** no HTTP method, path, request, response, status, authentication, authorization, pagination, idempotency, rate-limit, version, or deprecation signature changed.
- **Compatibility:** pass; the generated OpenAPI schema/client remains byte-for-byte drift-free.
- **Foundation:** the schema and internal role identifiers now underpin the planned OAuth2 endpoints without exposing provider-specific identity fields.

## Known Stubs

None. The changed files contain no placeholder, TODO, FIXME, skipped test, or incomplete data seam.

## User Setup Required

None. Administrators supply credentials interactively or through protected stdin when running the CLI; no default credential or external identity-provider configuration exists.

## Next Phase Readiness

- Plan 01-06 can issue OAuth2 access tokens against stable normalized users, exact internal roles, and token-version authority.
- Plan 01-07 can implement refresh rotation/replay and logout using the persisted family lineage and revocation fields.
- No unresolved blocker or temporary PostgreSQL resource remains.

## Self-Check: PASSED

- All 19 plan source/test/config artifacts exist and all 22 pre-close-out commits resolve.
- Final test, coverage, static, security, supply-chain, compatibility, CLI smoke, concurrency, and cleanup checks passed after the last source edit.
- The worktree contains only this plan close-out metadata plus the orchestrator-owned, intentionally uncommitted `.planning/milestone.lock`.

---
*Phase: 01-platform-foundation*
*Completed: 2026-08-24*
---
