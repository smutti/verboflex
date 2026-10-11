# Product membership verification

2026-10-11 · branch `codex/product-ownership` · base commit
`ed7e376a13a4508c1646874400b59392cb420f55` · [issue #7](https://github.com/smutti/verboflex/issues/7).

This report follows the temporary-credential revision of
[the specification](product-membership-spec.md). The earlier unshipped email
invitation design and its tests were replaced at the user's request. Separate
specification approval: not obtained (autonomous run under implementation
authorization). Independent agent verification: not performed.

## Reproduce

Use the locked dependencies and Docker in [application-ci.md](application-ci.md):

```sh
backend/.venv/bin/python tools/product_membership_gate.py --artifacts /tmp/verboflex-team-verification
```

`--focused` runs lint, types, build, MCP contract, delegation mutation, 62 focused
acceptance/property/adversarial tests with a hard coverage threshold, and browser
fixtures. The default also runs complete backend/frontend/MCP suites and the
built-stack smoke. All databases, providers, accounts and credentials in these
checks are synthetic. The browser fixture mocks HTTP boundaries; the backend
acceptance tests exercise registered ASGI routes with real PostgreSQL transactions.
The built smoke exercises actual HTTP/API/Celery/provider-fixture flows.

The gate records a source-tree hash excluding this report. Verified source-tree
SHA-256: `acc1983fe3f4edffee7b4b54d3e4e9b289b0ec5eee6d1dddadcb51a98d67dbea`.
The coverage scratch database was removed before this clean-tree hash; source
files were unchanged from the verification runs at that point.
No application dependencies or lock files changed. Final run artifacts are
`/tmp/verboflex-credentials-backend`, `/tmp/verboflex-credentials-gate`,
`/tmp/team-credentials-vitest.log`, `/tmp/verboflex-credentials-mcp.log` and
`/tmp/verboflex-credentials-smoke.log`; these are local evidence, not repository
dependencies. The command above reproduces the checks from the repository.

## Results

| Check | Result |
| --- | --- |
| Complete backend regression | 3,399 passed, zero failures/errors/skips, 742.84 seconds; randomized seed `1324517366`; owned PostgreSQL/Redis/Celery resources cleaned up |
| Focused team acceptance and properties | 62 passed |
| New access/service/API coverage | 202/202 statements and 54/54 branches; hard 100% gate passed |
| Delegation mutation (`mutmut 3.7.0`) | 20/20 selected mutants killed by the four Hypothesis properties alone; clean baseline and forced-failure control passed |
| Frontend | 59 files, 1,034 tests passed, shuffled with seed `11102026`; ESLint, TypeScript and build passed |
| MCP connector | 40 passed; generated contract matches OpenAPI |
| Browser/layout | Owner/admin Team and temporary credential dialog at 1280px and 320px; provisioning payload, persistent dialog, explicit dismissal and overflow checks passed; six screenshots, narrow dialog and desktop admin layout inspected |
| Formatting | All 69 changed backend Python files pass Ruff formatting; new frontend files formatted with Prettier |
| Built application smoke | Five product/branch/commit/PR happy flows and all 17 fault groups passed, including HTTP configuration, account revocation, lost replies, killed workers, exact localization bytes and content-free logs; owned resource cleanup passed |
| Secrets/dependencies | No added dependencies or lock changes; changed files contain no private-key blocks or GitHub/AWS credential signatures; synthetic credential fixtures reviewed |
| Migration | Backfill, no implicit owner, no membership for future products, safe empty downgrade and refusal after recorded activity passed |

Coverage is scoped to the three named new backend modules, not the entire diff
or frontend. Mutation covers the pure delegation policy, not SQL or password
provisioning as a whole. The existing bundle-size warning remains. Legacy tools
have mixed formatting outside the configured backend formatter scope; they were
not reformatted wholesale. No production deployment, native assistive-technology
certification, independent security review or separate-organization isolation
is claimed.

## Contract-to-check mapping

| Behavior / failure mode | Executable evidence |
| --- | --- |
| Only admin appoints/removes owners; operational delegation stays local | `test_product_access.py`, owner/admin HTTP tests and forged service-input rejection |
| Fresh temporary credential, hash-only storage, no replay retrieval | `test_new_account_returns_one_time_temporary_password_and_rejects_replay` |
| Restricted first login, forced change, temporary-password rejection afterward | `test_first_login_requires_change_and_invalidates_temporary_password` |
| Existing account identity/password/session preserved, including pending password change | `test_existing_account_joins_without_changing_identity_password_or_sessions`, pending-change account case |
| Concurrent adds reveal one password; stale updates conflict | Concurrent provisioning test and concurrent role-change/versioned-removal tests |
| Disabled accounts, inactive/deleted/foreign products, injected privileged fields denied | Parametrized adversarial API tests in `test_product_team_edges.py` |
| Account/member creation is transactional | Missing-role configuration and audit-receipt failure rollback tests |
| Removed/re-added membership does not revive old authority | Re-add/stamp test, removed/regranted submission review case, existing writeback/send-authority suites |
| Cross-product content, mentions and notifications stay scoped | Read/write/revocation acceptance tests plus existing search/workspace/dashboard/discussion suites |
| Old access and retained evidence survive migration/maintenance | Membership migration rehearsal and maintenance/history regression suites |
| One-time UI, clipboard, no storage, refresh and dismissal | Six Team Vitest cases, existing temporary-password-dialog tests, browser fixtures |
| API/SDK/MCP contract | Exact OpenAPI surface, mutation inventory, generated client/contract |

## Corrections and limits

The initial two credential API tests were observed failing with 405 before the
new POST endpoint existed, then passing after implementation. Updated UI tests
failed against the previous invitation component before the replacement was
implemented. Later adversarial assertions were added against existing behavior;
this is not strict red-first TDD for every acceptance scenario.

The first isolated attempt ran before PostgreSQL was ready; the retry exposed
the intended missing endpoint. A deleted-product fixture initially omitted the
required deletion actor/inactive state; it was corrected to a valid deleted row.
A standalone mutation-inventory run lacked Redis and correctly returned 503 from
the existing password-change limiter; the complete infrastructure run passed
that inventory with Redis available. No application check was relaxed.

The earlier implementation also exposed and fixed administrator-member protection
and the maintenance database guard allowlist. Legacy test factories explicitly
seed product memberships; no production authorization fallback was introduced.
An old schema fails closed with sanitized authentication 503 before product reads.

Verification completed before commit, push and PR creation. No application
deployment, production migration or real credential delivery was performed.
Deploy API/workers together with migration
0044 when the feature is released; see [the operating guide](product-membership.md).


## Pull request preparation

The feature commit was replayed onto `main` at
`ac6f92619f7ad40606b34eb2a4f38e7e64d5b277` to exclude the unrelated backup runtime
change already tracked in PR #6. The only tree differences from the tested base
are that separate change's backup script, backup tests and four CI workflow
lines; feature code, tests and generated contracts are identical. The full-suite
results above therefore identify the original verification tree, not a second
full-suite run after rebasing. Generated OpenAPI/client and MCP drift checks were
repeated for PR preparation.

PR source-tree SHA-256 (excluding this report):
`35eb9e30d7ccdd75837880599028015286f3b5cbe3ac35cf52d26fb73e9ff891`.
