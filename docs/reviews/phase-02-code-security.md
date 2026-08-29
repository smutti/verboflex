# Phase 2 Code and Security Review

- Review-status: CLOSED
- Open-critical-high: 0
- Full-gauntlet-status: PENDING
- Reviewed-source-digest: `9e63e9bcf79d17a990c6b99ae81488177a48f55f5784fa45360646967ebaac7f`
- Review-standard: OWASP ASVS 5.0 Level 1
- Review-scope: Complete Phase 2 diff from `ce9fbeef86b00f594d1d06e15d3083d623c54095`
- Review-date: 2026-08-29

## Verdict

No Critical or High severity blocker remains open. The Phase 2 administrative configuration slice is bounded to users, product revisions, repository registration, encrypted Bitbucket OAuth, candidate mappings, deterministic read-only discovery/preview, and publication of the currently confirmed candidate. The provider adapter exposes only reviewed GET operations. Both the mocked deployment proof and the human-authorized disposable live smoke record zero repository writes; the latter performs one bounded OAuth token exchange before five audited GET requests.

One Moderate development-only dependency advisory remains explicitly deferred in `.planning/phases/02-admin-configuration/deferred-items.md`: Stryker's transitive `qs` dependency. Production dependency audit remains clean, no approved runtime dependency has an unreviewed provenance, and the deferred item is not concealed by this review.

## Failure Model and Dispositions

| Failure mode | Severity | Evidence or disposition |
| --- | --- | --- |
| Viewer or reviewer reaches an admin mutation | High | Backend role dependencies remain authoritative; route and service mutation proofs kill admin-to-viewer guard mutations; frontend checks are navigation projection only. Closed. |
| OAuth bearer or refresh token reaches logs, browser persistence, API schemas, or plaintext storage | High | SecretBox ciphertext model, redacted representations, schema exclusion tests, storage/log guards, secret scan, and Compose log scan. Closed. |
| Revoked/disconnected provider lease becomes an unbounded 500 or stale write | High | The Task 1 regression test proves lease acquisition maps to the bounded disconnected response; provider operations are read-only and the mock audit observes zero writes. Closed. |
| Stale discovery/preview result overwrites a newer candidate | High | Candidate revision, connection generation, detector version, input digest, attempt, and repository-side identities are checked end to end; polling ignores superseded responses. Closed. |
| Parser accepts hostile or malformed localization input | High | Size/key/depth/entity/encoding limits plus property tests and Android/iOS/JSON/Qt detector mutation proofs. Closed. |
| Migration upgrade or rollback leaves an incomplete Phase 2 schema | High | Disposable PostgreSQL upgrade-to-head, full downgrade-to-base, and re-upgrade cycle with exact table/constraint assertions. Closed. |
| Browser, worker, or live smoke performs provider mutation during configuration | High | Static architecture provider boundary, transport verb scan, runtime TLS provider spy, and a live audit transport that rejects non-GET REST requests before delegation. Mock and live evidence both record zero repository writes. Closed. |
| Duplicate publication or retry creates inconsistent durable state | High | Current-candidate confirmation, idempotency, conflict checks, durable job attempts, and publication mutation proof. Closed. |
| Generated API client diverges from the backend contract | Moderate | Canonical OpenAPI regeneration and checked-in client drift gate. Closed. |
| Responsive admin workflow becomes unusable | Moderate | Keyboard/focus assertions and Playwright at 320, 768, 1024, and 1440 pixel widths. Closed. |

## ASVS 5.0 L1 Review

| ASVS area | Result | Reviewed controls |
| --- | --- | --- |
| V1 Encoding and sanitization | PASS | Pydantic validation, bounded path/branch normalization, format-aware parsers, and escaped UI rendering; no raw HTML sink introduced. |
| V2 Validation and business logic | PASS | Versioned drafts, named confirmation, current identity checks, bounded polling, idempotency, and transaction rollback paths. |
| V3 Web frontend security | PASS | Bearers remain memory-only; admin navigation does not substitute for server authorization; sensitive values are excluded from storage and logs. |
| V4 API and web service | PASS | Generated contract drift check, bounded error vocabulary, cursor binding, request limits, and no deferred Phase 3 endpoints. |
| V5 File handling | PASS | Provider reads are size limited and localization inputs are parsed without local arbitrary file access or executable content. |
| V6 Authentication | PASS | Existing OAuth2 bearer authority is preserved; Bitbucket OAuth state is single-use and bound to a short-lived flow. |
| V7 Session management | PASS | Existing access/refresh lifecycle remains intact; provider token leases are generation-bound and revoked connections fail closed. |
| V8 Authorization | PASS | Every admin route uses backend role enforcement; service-level identities and current-version preconditions prevent confused-deputy writes. |
| V9 Self-contained tokens | PASS | Application JWT handling is unchanged; provider tokens are opaque, encrypted at rest, redacted, and not exposed in response models. |
| V10 OAuth and OIDC | PASS | Exact callback, state, scopes, token exchange, refresh rotation, disconnect, and bounded error handling are covered without weakening TLS. |
| V11 Cryptography | PASS | AES-GCM envelope through the approved SecretBox keyring; no custom primitive or plaintext persistence. |
| V12 Secure communication | PASS | Provider traffic requires HTTPS; mock execution uses a locally trusted TLS CA; production verification is not disabled. |
| V13 Configuration | PASS | Required secrets and callback settings are validated, Compose separates API/worker processes, and deployment logs are checked for leakage. |
| V14 Data protection | PASS | Temporary passwords and provider tokens use redacted data classes and narrow response shapes; audit records exclude secret material. |

## Findings Closed During Finalization

### P2-FINAL-01 — provider lease acquisition escaped bounded error mapping

- Severity: High
- Status: CLOSED
- Found by: Mock-provider Compose flow after local disconnect
- Risk: A disconnected provider state returned HTTP 500 instead of the approved bounded conflict response.
- Resolution: Move lease acquisition inside the adapter's reviewed exception boundary and retain the provider-disconnected regression test.
- Verification: Focused adapter suite, full backend suite, runtime provider spy, and mocked Compose flow.

### P2-FINAL-02 — final architecture exclusion checks were not centralized

- Severity: Moderate
- Status: CLOSED
- Found by: Final scope review
- Risk: Deferred routes/models or provider write verbs could enter Phase 2 without one explicit plan-level failure.
- Resolution: Add `backend/tests/architecture/test_phase2_scope.py` covering OpenAPI paths, model set, provider verbs, and frontend destinations.
- Verification: Architecture/provider-spy gauntlet layer.

### P2-FINAL-03 — disposable live smoke required a fail-closed execution boundary

- Severity: High
- Status: CLOSED
- Found by: Task 3 live-provider preparation review
- Risk: Loading credentials or calling a representative repository without an exact-scope, GET-only, bounded, non-secret harness could broaden authority or leak source/token material.
- Resolution: Add a mode-0600 owner-only dotenv parser, exact callback and token-scope checks, redirect rejection for the token exchange, a validated GET-only audit transport, fixed A-03 page/entry/depth/raw-size ceilings, digest/count-only output, and an in-memory generation revoke that erases the token and rejects the prior lease.
- Verification: Three fail-closed architecture tests, six existing adapter tests, and the authorized live run: 5 GET requests, zero repository writes, 37 branches, 1 tree page, 12 entries, one 106-byte bounded raw read, and successful local generation invalidation. No credential, token, repository path, or raw content was persisted in evidence.
- Checker note: The dummy `client-secret` fixture is bound to its exact test path, line, and detector type; every unreviewed secret-scan result remains fatal.

## Scope and Capability Diff

- Network: Adds Bitbucket Cloud OAuth and read-only repository/source discovery through one bounded adapter. No provider write verb is approved in Phase 2.
- Files: Reads localization blobs received from the provider into bounded memory; no arbitrary local filesystem path is accepted from an API request.
- Subprocess: Production code adds no subprocess execution. Test and deployment harnesses use Docker, Alembic, Celery, Playwright, and pinned project tooling.
- Database: Adds migrations `0002` through `0007`; upgrade/downgrade/re-upgrade is rehearsed against disposable PostgreSQL.
- Secrets: Adds encrypted provider credentials and ephemeral OAuth flow state. The disposable live token remains memory-only, is erased by local generation revoke, and is excluded from logs and evidence. No raw credential is permitted in logs, reprs, response schemas, browser persistence, or evidence.

## Review Limits

- The disposable live Bitbucket smoke ran only after the user confirmed the client-credentials grant and exact `repository` authority. Its evidence is limited to digests, counts, duration, and the zero-write/local-revoke assertions; provider-side revocation is still not claimed.
- The final differential coverage gate is scoped to Plan 02-20 against `50664a2`; prior Phase 2 plan summaries retain their own 100% changed-production-line and branch proofs. The final full randomized suites still execute the complete accumulated source and test set.
- The complete candidate gauntlet must be repeated after replacing the obsolete checkpoint assertion with the exact live-pass evidence contract. The final exact entry point then rechecks the closed review, unchanged source digest, and signed evidence report before closure.
