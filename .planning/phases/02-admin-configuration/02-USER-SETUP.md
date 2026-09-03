# Phase 02: User Setup Required

**Generated:** 2026-08-29
**Phase:** 02-admin-configuration
**Status:** Incomplete

Complete these items before using the production Bitbucket connection. Automated tests use an injectable provider exchange and do not require real credentials.

## Environment Variables

| Status | Variable | Source | Add to |
|--------|----------|--------|--------|
| [ ] | `VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID` | Bitbucket workspace settings → OAuth consumers → client identifier | Backend deployment secret store |
| [ ] | `VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET` | Bitbucket workspace settings → OAuth consumers → client secret | Backend deployment secret store |
| [ ] | `VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING` | Operator-managed Fernet keyring; active key first | Backend deployment secret store |

Do not put any of these values in repository files, browser configuration, logs, screenshots, or issue trackers.

## Dashboard Configuration

- [ ] **Create or select the VerboFlex OAuth consumer**
  - Location: Bitbucket workspace settings → OAuth consumers
  - Use: Production server-to-server read authority

- [ ] **Grant exactly repository scope**
  - Location: Bitbucket OAuth consumer permissions
  - Set to: `repository`
  - Notes: Do not grant write, branch, pull-request, webhook, account, email, workspace-administration, or other scopes.

## Verification

After exporting the three variables in the backend runtime environment, verify their presence without printing their values:

```bash
cd backend
uv run python -c 'from verboflex.core.config import Settings; settings = Settings(); assert settings.bitbucket_oauth_client_id and settings.bitbucket_oauth_client_secret and settings.bitbucket_token_encryption_keyring; print("Bitbucket client-credentials configuration present")'
```

Expected results:

- The command reports that configuration is present without revealing any value.
- An administrator's direct Connect operation succeeds only when Bitbucket grants exactly `repository` scope.
- Public status contains scope, timestamps, and expiry only; it never contains credentials or ciphertext.

---

**Once all items complete:** Mark status as "Complete" at top of file.
