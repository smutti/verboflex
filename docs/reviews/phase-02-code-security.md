# Phase 2 Code and Security Review

- Review-status: CLOSED
- Open-critical-high: 0
- Full-gauntlet-status: PASS
- Reviewed-source-digest: `2e93097910a805663c7ccad721f4f629b478bdd01efca95541c8509c5f0354a9`
- Review-standard: OWASP ASVS 5.0 Level 1
- Review-scope: Complete Phase 2 diff `ce9fbeef86b00f594d1d06e15d3083d623c54095..7af1d1063ab6a795a42f0e26175fc2196ba6eda5`, all 290 full-review paths, and the test-only semantic-transition delta through `542903d39b11617c1985574eb4a5f7d32f9038cf`
- Review-date: 2026-09-01
- Structured-review: `.planning/phases/02-admin-configuration/02-REVIEW.md`

## Verdict

The fresh independent deep review reports zero unresolved Critical or project High-equivalent findings on the current review-mode digest. CR-01 through CR-15 are CLOSED on current production symbols and executable evidence. WR-01 and WR-02 are CLOSED. WR-03 through WR-08 remain explicitly OPEN at Warning severity and are not represented as fixed.

The typed reviewer therefore truthfully reports `status: issues_found` with `critical: 0`, `warning: 6`, `info: 0`, and `total: 6`. That warning-bearing typed status is separate from this canonical Critical/High closeout authority: `Review-status: CLOSED` and `Open-critical-high: 0`.

The post-transition official gauntlet passed all 18 layers on the unchanged application source before this canonical artifact was updated. A later test-only semantic-transition delta changed no production, runtime, schema, API, generated, dependency, configuration, or manifest behavior; a fresh typed delta review found no new Critical/High-equivalent issue and the focused semantic audit passed 8/8. Historical review, verifier, plan, or PASS prose is not closure authority.

## Current Finding Inventory

| Row | Disposition | Current production authority | Executable current evidence |
| --- | --- | --- | --- |
| CR-01 | CLOSED | Base Compose provider environment shared by backend, worker, and scheduler | Semantic/runtime and architecture/provider layers passed; base Compose readiness passed |
| CR-02 | CLOSED | `BitbucketOAuthTokenExchange.exchange_client_credentials`; exact response validation | Mutation proof and mock provider passed exact client-credentials grant and `repository` scope |
| CR-03 | CLOSED | Client-credentials-only service and connect/reconnect/status/revoke routes | No callback, authorization-code, browser-token, or refresh authority remains in OpenAPI/runtime |
| CR-04 | CLOSED; WR-03 remains | `acquire_repository_read_lease`, `_renew_access_token_if_needed`, `_persist_access_only`, `public_status` | Access-only encrypted generations and serialized renewal passed; malformed lifetime remains Warning-only |
| CR-05 | CLOSED | `_clone_active_revision_graph`; `_promote_candidate_identity` | Complete candidate isolation and atomic publication mutation contracts passed |
| CR-06 | CLOSED | `reactivate_product`; `active_revision_revalidation_is_current`; `PublishedMappingRecovery` | Real-backend reactivation passed with immutable active graph and zero provider writes |
| CR-07 | CLOSED | Persistent mobile wizard Back/Next controls | Five-step 320px keyboard/pointer browser contract passed |
| CR-08 | CLOSED | `useCursorCollection`; terminal-cursor preview readiness | 51st-row completeness, deduplication, supersession, and lifecycle gating passed |
| CR-09 | CLOSED | `reconcile_stale_preview_jobs`; `preview-stale-job-watchdog` | Staging and production worker-loss recovery passed bounded timeout and replacement retry |
| CR-10 | CLOSED | `ADMIN_AUTHORITY_LOCK_KEY`; shared admin survivor predicate | Cross-entry HTTP/CLI last-admin concurrency and mutation contracts passed |
| CR-11 | CLOSED | Celery Beat schedule and base/staging/production scheduler services | Scheduler parity and both deployment-overlay recovery paths passed |
| CR-12 | CLOSED | Active-revision revalidation job, confirmation, currentness, and UI recovery | Exact server eligibility, immutable sidecar, frontend, and real-backend E2E passed |
| CR-13 | CLOSED | Runtime Nginx CSP and defensive response headers | Built root and SPA fallback passed anti-framing and complete defensive-header probes |
| CR-14 | CLOSED | `configuredPreviewSourceSides`, `resolveConfiguredBranchCommit`, generated `getAdminRepositoryBranch` | Candidate and active direct/separate branch-101 detail paths, exact name equality, fail-closed cases, browser proof, and five-GET/zero-write audit passed |
| CR-15 | CLOSED | `DirtyFormNavigationProvider`, `useBlocker`, `useBeforeUnload`, product/mapping registration, mobile commit observer | Real-router Link/PUSH/Back, reload separation, Keep editing/Escape/Discard once, stale-intent isolation, value/focus preservation, and 320px Sheet paths passed |
| WR-01 | CLOSED | Role-projected workspace and location-authoritative shell navigation | Full frontend and focused router/shell suites passed |
| WR-02 | CLOSED | Composite ownership, published-child triggers, immutable revalidation sidecar | Migrations, graph integrity, and sidecar immutability passed |
| WR-03 | **OPEN — WARNING** | Provider `expires_in` has no explicit upper bound | `10**100` passes validation before persistence raises `OverflowError` |
| WR-04 | **OPEN — WARNING** | Development-only Stryker chain includes vulnerable `qs` | Full npm graph reports two moderate records; production graph reports zero |
| WR-05 | **OPEN — WARNING** | Container image selectors use mutable tags | Dockerfile/Compose inventory finds no `@sha256:` pins |
| WR-06 | **OPEN — WARNING** | `.env.example` omits Phase 2 provider/watchdog settings | Environment-key comparison finds zero of seven settings |
| WR-07 | **OPEN — WARNING** | Source manifest omits the executable Phase 2 edge-matrix JSON | The JSON is reviewed through the diff but remains outside both source digests |
| WR-08 | **OPEN — WARNING** | `phase2_compose_flow.main` default no-flag mode calls removed OAuth endpoints | Current OpenAPI lacks those routes; supported `--gap-closure` does not invoke this deferred broken path |

## ASVS 5.0 Level 1 Disposition

| Security authority | Result | Reviewed boundary |
| --- | --- | --- |
| Validation and business logic | PASS with WR-03 | Closed schemas, exact cursor/path/scope/status validation, transactional invariants, fail-closed revalidation |
| File handling and provider reads | PASS | GET-only commit-bound reads, redirect/path rejection, bounded pages/files/depth/bytes, strict format parsers |
| Authentication and sessions | PASS | Purpose-bound bearer tokens, Argon2 passwords, refresh rotation/revocation, current database authority |
| Authorization | PASS | Server-enforced admin dependencies, last-admin lock, admin-only recovery routes |
| OAuth | PASS with WR-03 | Backend-only client credentials, exact repository scope, access-only encrypted generations, expiry/revoke/reconnect checks |
| Cryptography and data protection | PASS | MultiFernet authenticated encryption, redaction, no-store projections, memory-only frontend bearer |
| Logging and error handling | PASS | Bounded public errors, provider/token exclusion, secret-free diagnostics and evidence |
| Product graph authority | PASS | Composite ownership, published graph immutability, atomic publication/reactivation, immutable sidecar |
| Router data-loss protection | PASS | One router-owned transaction, exact decisions, separate document exit, stale cleanup, focus/value preservation |
| Pagination and asynchronous recovery | PASS | All-page collection, durable CAS terminalization, scheduler parity, dual-overlay recovery |
| Browser response hardening | PASS | Complete runtime CSP, anti-framing, nosniff, referrer, and permissions headers |
| Provider-write exclusion | PASS | Read-only adapter and runtime audit observed five GETs and zero writes |
| Dependency and evidence provenance | WARNING | WR-04 through WR-08 remain open and visible |

## Fresh Verification Performed

- Exact semantic audit after both supported live transitions (Critical-to-warning review and `gaps_found`-to-`passed` verifier): 8/8 passed.
- Official post-transition application command before the test-only delta: `bash tools/phase2_gauntlet.sh --gap-closure` — PASS, 18/18 layers.
- Fresh typed digest-delta review: commit `542903d` changed only the live verifier-state assertion; the fail-closed parser and all inventory/status mutants remain enforced, with zero new Critical/High-equivalent findings.
- Fresh reviewer scope: 290 unique current review paths plus the complete Phase 2 implementation diff.
- Full suites: backend 807/807, frontend 304/304, backend properties 200/200, frontend properties 3/3.
- Changed-source coverage: backend 641/641 and frontend 746/746 lines, both 100%.
- Mutation, migration, OpenAPI/client drift, static, secret, supply-chain, and architecture/provider gates passed under their declared thresholds.
- Mock provider production browser smoke: 8/8 with five audited GETs and zero writes; both deployment-overlay worker-loss paths passed.
- Fresh review digest after the test-only delta: `2e93097910a805663c7ccad721f4f629b478bdd01efca95541c8509c5f0354a9`.

## Review Limits

- The optional live-provider smoke remains intentionally skipped without explicit opt-in and local provider configuration; no live-provider claim is fabricated.
- WR-03 through WR-08 are nonblocking at their fresh Warning severity and remain scheduled work. WR-08 is explicitly deferred, not fixed.
- `Reviewed-source-digest` is the review-mode digest and deliberately excludes this canonical review to avoid self-reference. The final digest after this artifact is committed is recorded in the gap-closure evidence.
