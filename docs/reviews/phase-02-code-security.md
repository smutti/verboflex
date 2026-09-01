# Phase 2 Code and Security Review

- Review-status: CLOSED
- Open-critical-high: 0
- Full-gauntlet-status: PASS
- Reviewed-source-digest: `ede23c16f49301366ec9e30edc885e52c726b5d57a7bc3a796be6e9f30979d90`
- Review-standard: OWASP ASVS 5.0 Level 1
- Review-scope: Complete Phase 2 diff `ce9fbeef86b00f594d1d06e15d3083d623c54095..99d2d0af5dfb27cc3ef47590f480ae7a33cf4d94` through Plan 02-43
- Review-date: 2026-09-01
- Structured-review: `.planning/phases/02-admin-configuration/02-REVIEW.md`

## Verdict

The fresh independent review reports zero unresolved Critical or High-equivalent findings on the current review-mode digest. CR-01 through CR-13 are CLOSED on current production symbols and executable evidence. WR-01 and WR-02 are CLOSED. WR-03 through WR-07 remain explicitly OPEN at Warning severity and are not represented as fixed.

The official pre-review gap-closure gauntlet passed all 18 layers on the unchanged final source. The canonical-source rerun and the independent verifier remain separately recorded in `docs/evidence/phase-02-gap-closure.md`; no historical review, verifier, plan statement, or stale digest is used as closure authority.

## Current Finding Inventory

| Row | Disposition | Current production authority | Executable current evidence |
| --- | --- | --- | --- |
| CR-01 | CLOSED | Base Compose provider environment shared by backend, worker, and scheduler | Exact base-Compose inheritance contract passed |
| CR-02 | CLOSED | Exact bounded Bitbucket client-credentials token exchange | Exact exchange contract passed |
| CR-03 | CLOSED | Client-credentials-only service and connect/reconnect/status/revoke routes | No callback, authorization-code, browser-token, or refresh authority contract passed |
| CR-04 | CLOSED; WR-03 remains | Access-only encrypted generation, exact scope/status, expiry, and serialized renewal | Persistence and concurrent-renewal contracts passed |
| CR-05 | CLOSED | Stable Product identity, complete candidate graph clone, atomic publication promotion | Candidate isolation contract passed |
| CR-06 | CLOSED | Exact active-revision revalidation and locked reactivation authority | Revalidate, confirm, reactivate without graph mutation passed |
| CR-07 | CLOSED | Persistent mobile wizard navigation controls | 320px keyboard/pointer five-step contract passed |
| CR-08 | CLOSED | Opaque cursor collection and terminal-page lifecycle gating | 51st-row completeness and supersession contracts passed |
| CR-09 | CLOSED | Durable watchdog CAS terminalization and retry isolation | Watchdog and worker-loss recovery contracts passed |
| CR-10 | CLOSED | Shared last-admin advisory lock and survivor predicate across HTTP and CLI | Cross-entry concurrency and sole-admin denial contracts passed |
| CR-11 | CLOSED | Scheduler parity in base, staging, and production; separate Celery Beat; dual-overlay recovery | Scheduler contracts and staging/production KILL-to-timeout-to-retry smoke passed |
| CR-12 | CLOSED | Immutable active-revalidation sidecar, exact eligibility, admin recovery API and UI | Graph immutability, API/service, frontend, and real-backend recovery E2E passed |
| CR-13 | CLOSED | Runtime CSP `frame-ancestors 'none'`, X-Frame-Options DENY, and defensive headers | Built-Nginx root and SPA-fallback header smoke passed |
| WR-01 | CLOSED | Role-projected workspace and location-authoritative shell navigation | Workspace bounded-state suite passed |
| WR-02 | CLOSED | Composite ownership FKs, published-child triggers, and immutable revalidation sidecar | Graph-integrity and sidecar immutability contracts passed |
| WR-03 | **OPEN — WARNING** | Provider `expires_in` has no explicit upper bound | `10**100` is accepted before persistence raises `OverflowError` |
| WR-04 | **OPEN — WARNING** | Development-only Stryker dependency chain includes vulnerable `qs` | Full npm graph reports two moderate records; production graph reports zero |
| WR-05 | **OPEN — WARNING** | Container image selectors use mutable tags | Dockerfile/Compose provenance inventory finds no `@sha256:` pins |
| WR-06 | **OPEN — WARNING** | `.env.example` omits Phase 2 provider/watchdog settings | Environment-key comparison finds zero of seven settings |
| WR-07 | **OPEN — WARNING** | Source manifest omits the executable Phase 2 edge-matrix JSON | Resolved manifest omits the JSON loaded by the traceability test |

## ASVS 5.0 Level 1 Disposition

| Security authority | Result | Reviewed boundary |
| --- | --- | --- |
| Validation and business logic | PASS with WR-03 | Closed schemas, exact cursors/paths/scopes/status, transactional invariants, fail-closed revalidation |
| File handling and provider reads | PASS | GET-only commit-bound reads, redirect/path rejection, bounded pages/files/depth/bytes, strict format parsers |
| Authentication and sessions | PASS | Purpose-bound bearer tokens, Argon2 passwords, refresh rotation/revocation, current database authority |
| Authorization | PASS | Server-enforced admin dependencies, cross-entry last-admin lock, admin-only recovery routes |
| OAuth | PASS with WR-03 | Backend-only client credentials, exact repository scope, access-only encrypted generations, expiry/revoke/reconnect checks |
| Cryptography and data protection | PASS | MultiFernet authenticated encryption, secret redaction, no-store public projections, memory-only frontend bearer |
| Logging and error handling | PASS | Bounded public errors, provider body/token exclusion, secret-free diagnostics and audit output |
| Product graph authority | PASS | Composite ownership, published graph immutability, atomic publication/reactivation, immutable recovery sidecar |
| Pagination and asynchronous recovery | PASS | All-page collection before lifecycle actions, durable CAS terminalization, scheduler parity, dual-overlay worker-loss recovery |
| Browser response hardening | PASS | Complete runtime CSP, anti-framing, nosniff, referrer and permissions headers |
| Provider-write exclusion | PASS | Adapter exposes bounded GET operations only; runtime audits observe zero provider writes |
| Dependency and evidence provenance | WARNING | WR-04 through WR-07 remain open and visible |

## Fresh Verification Performed

- Official pre-review command: `bash tools/phase2_gauntlet.sh --gap-closure` — PASS, 18/18 layers.
- Fresh review scope: 287 unique current review-manifest paths and the complete 279-file Phase 2 implementation diff.
- Focused backend review: 20/20 nodes passed.
- Focused frontend review: 5 files, 101/101 tests passed.
- Static review gates: Ruff, mypy across 81 source files, TypeScript, and ESLint passed.
- Dependency review: `uv lock --check` and `pip-audit` passed; production npm audit reports zero; the full development graph retains WR-04.
- Fresh review digest after the structured report was written: `ede23c16f49301366ec9e30edc885e52c726b5d57a7bc3a796be6e9f30979d90`.

## Review Limits

- The optional live-provider smoke remains intentionally skipped without explicit opt-in and local provider configuration. Current mock-live-provider execution performs five audited GETs and zero writes; no provider-side revocation claim is made.
- WR-03 through WR-07 are non-blocking at their fresh assessed Warning severity, remain scheduled work, and are not hidden by the CLOSED Critical/High gate.
- `Reviewed-source-digest` is the review-mode digest, which deliberately excludes this canonical review to avoid self-reference. The final-mode digest after this canonical artifact is committed is recorded in the gap-closure evidence.
