---
status: resolved
trigger: "ma non puoi rinfrescare il token in automatico, altrimenti il tool è inutile"
created: "2026-09-07T20:15:00Z"
updated: "2026-09-07T21:47:57Z"
resolved: "2026-09-07T21:47:57Z"
source_commit: 59de492
---

# Bitbucket token automatic refresh

## Symptoms

- expected: A connected Bitbucket OAuth credential renews its access token automatically. Manual reauthorization is required only when the provider authority is missing, revoked, malformed, or rejected.
- actual: After the displayed access-token lifetime, the administration UI reported `Reauthorization required` for every capability and only offered reconnect/revoke actions.
- errors: No raw provider error was shown; the UI reported only the reauthorization state.
- timeline: Observed on 2026-09-07 after a connection established at 07:34 UTC expired at 09:34 UTC.
- reproduction: Connect Bitbucket, allow the access token to expire, then open the Bitbucket administration status page.

## Current Focus

- hypothesis: Confirmed and fixed: repository leases renewed client-credentials authority on demand, but `public_status()` classified its expiry without invoking the same renewal boundary.
- test: Complete.
- expecting: Status and repository work share one server-side renewal path; no reconnect is needed for ordinary expiry.
- next_action: none
- reasoning_checkpoint: Root cause verified against production code and the live local connection.
- tdd_checkpoint: RED observed; focused and regression suites GREEN.

## Evidence

- timestamp: 2026-09-07T20:17:00Z
  observation: `acquire_repository_read_lease()` already called `_renew_access_token_if_needed()`, while `public_status()` returned `reauthorization_required` at the expiry boundary without a token exchange.
- timestamp: 2026-09-07T20:18:00Z
  observation: Current Bitbucket integration uses OAuth client credentials, so renewal is a backend token re-exchange using configured client authority; the provider does not issue a refresh token for this grant.
- timestamp: 2026-09-07T20:20:00Z
  observation: The new API boundary test failed because `expires_at` remained unchanged, then passed after status was wired into automatic renewal at the existing 60-second skew boundary.
- timestamp: 2026-09-07T21:43:00Z
  observation: All 24 focused Bitbucket OAuth/API tests and the Phase 2 executable-evidence check passed; all 1,679 non-worker-smoke backend tests passed.
- timestamp: 2026-09-07T21:47:00Z
  observation: The live local connection automatically moved from the expired `2026-09-07T09:34:03Z` authority to `connected` with expiry `2026-09-07T23:47:44Z`, without reconnect.

## Eliminated

- hypothesis: The import worker lacked any automatic renewal path.
  reason: Repository lease acquisition already renewed expiring client-credentials generations under a row lock.
- hypothesis: A provider refresh token needed to be persisted.
  reason: The approved Bitbucket grant is client credentials; renewal correctly performs a new server-side token exchange with the configured client ID and secret.

## Resolution

- root_cause: `BitbucketOAuthService.public_status()` treated token expiry as terminal reauthorization even though the client-credentials grant remained renewable by the backend.
- fix: Status now renews within the existing 60-second skew, shares the row-locked exchange path with repository leases, reports transient provider failures as unavailable, preserves expired authority for automatic retry, and never leases the stale token.
- verification: TDD red/green; 25 focused Bitbucket and architecture tests; Ruff formatting/lint; strict mypy; 1,679-test backend regression suite; live Docker provider renewal.
- files_changed: `backend/src/verboflex/services/bitbucket_oauth.py`, `backend/tests/api/test_admin_bitbucket.py`, `backend/tests/integration/test_bitbucket_oauth.py`
