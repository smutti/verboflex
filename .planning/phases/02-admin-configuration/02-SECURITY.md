---
phase: 2
slug: admin-configuration
status: verified
threats_total: 154
threats_closed: 148
threats_open_below_threshold: 6
# threats_open counts only OPEN threats at or above workflow.security_block_on.
threats_open: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
created: 2026-09-01
verified: 2026-09-01
---

# Phase 2 — Security

> Per-phase security contract for Admin Configuration. This audit reconciles all plan-time STRIDE registers, execution summaries, the final code/security review, and the independent phase verifier.

## Audit Result

Phase 2 is **THREAT-SECURE at the configured gate**: no Critical or High threat remains open. All 148 unique planned threat IDs have a mitigation recorded in their source plan, a matching execution summary, and a passing final verifier. Six review warnings remain open below the configured `high` blocking threshold and are retained explicitly in this document.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Administrator browser → FastAPI | Browser identity, role projection, UUIDs, versions, and mutation intent are untrusted until backend authorization and currentness checks pass. | Bearer tokens, admin commands, bounded API payloads |
| Operator CLI → user service | Local bootstrap/reset/deactivation commands can change login authority and race remote administration. | Corporate email, role changes, one-time credentials |
| FastAPI/service → PostgreSQL | Application and direct-SQL callers can attempt to mutate revision graphs and authority state. | Users, roles, products, revisions, repositories, mappings |
| Candidate graph → active graph | Publication changes the immutable configuration that downstream import work may trust. | Version pointers, mapping identities, confirmation digests |
| API/worker/scheduler → Redis and Celery | Asynchronous preview ownership, retries, timeouts, and watchdog recovery cross process boundaries. | UUID-only job identities, terminal state, bounded diagnostics |
| VerboFlex → Bitbucket OAuth/token endpoint | Organizational client credentials cross TLS and produce an access-only generation-bound lease. | Encrypted secret at rest, access token in memory, expiry/scope |
| VerboFlex → Bitbucket read API | Opaque repository, branch, cursor, commit, and path values cross an external-provider boundary. | Repository metadata and bounded localization bytes |
| Repository bytes → parsers/preview | Untrusted XML, JSON, Qt, and iOS content crosses bounded format parsers. | Encoded source bytes, layout candidates, samples and digests |
| OpenAPI → generated client → SPA | The public contract controls which admin and credential fields may reach browser code. | Closed schemas, generated types, bounded status projections |
| Router/local form state → navigation | Dirty candidate values must not be discarded or replayed by stale navigation transactions. | Unsaved form state, captured router transaction, focus target |
| Source/build configuration → containers | Locks, manifests, image selectors, Compose overlays, and Nginx policy determine deployed behavior. | Packages, images, environment configuration, security headers |
| Source/evidence → reviewer/verifier | Review and completion authority must remain bound to the exact current source digest. | Sanitized test results, review findings, source digests |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation and Evidence | Status |
|-----------|----------|-----------|----------|-------------|-------------------------|--------|
| T-02-01 | Elevation of privilege | Multiple Phase 2 surfaces | high | mitigate | Consolidated controls defined by Plans 02-01, 02-02, 02-15–02-17, 02-19, and 02-20; matching summaries and `02-VERIFICATION.md` confirm execution. | closed |
| T-02-02 | Tampering | Multiple Phase 2 surfaces | high | mitigate | Consolidated controls defined by Plans 02-01–02-03, 02-08–02-10, 02-18, and 02-20; matching summaries and `02-VERIFICATION.md` confirm execution. | closed |
| T-02-03 | Spoofing, Spoofing/Tampering | Multiple Phase 2 surfaces | high | mitigate | Consolidated controls defined by Plans 02-04–02-06, 02-19, and 02-20; matching summaries and `02-VERIFICATION.md` confirm execution. | closed |
| T-02-04 | Tampering, SSRF/Tampering | Multiple Phase 2 surfaces | high | mitigate | Consolidated controls defined by Plans 02-06–02-09, 02-12, 02-18, and 02-20; matching summaries and `02-VERIFICATION.md` confirm execution. | closed |
| T-02-05 | Denial of service | Multiple Phase 2 surfaces | high | mitigate | Consolidated controls defined by Plans 02-07, 02-11–02-14, and 02-20; matching summaries and `02-VERIFICATION.md` confirm execution. | closed |
| T-02-06 | Tampering | Multiple Phase 2 surfaces | high | mitigate | Consolidated controls defined by Plans 02-10, 02-11, 02-13, 02-14, 02-19, and 02-20; matching summaries and `02-VERIFICATION.md` confirm execution. | closed |
| T-02-07 | Information disclosure | Multiple Phase 2 surfaces | high | mitigate | Consolidated controls defined by Plans 02-01, 02-04–02-07, 02-11, and 02-13–02-20; matching summaries and `02-VERIFICATION.md` confirm execution. | closed |
| T-02-21-01 | Information disclosure | API responses, logs, persistence | high | mitigate | Closed response schemas, encrypted persistence and deterministic seeded-secret scans. Evidence: `02-21-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-21-02 | Elevation of privilege | OAuth scope | high | mitigate | Constant exact `repository` request plus granted-scope validation and capability audit. Evidence: `02-21-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-21-03 | Spoofing | token endpoint | high | mitigate | Allowlisted HTTPS origin and mock tests rejecting redirects/untrusted token URLs. Evidence: `02-21-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-21-04 | Tampering | expiry/generation | high | mitigate | Singleton row lock, authoritative expiry check and one-winner renewal tests. Evidence: `02-21-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-21-05 | Denial of service | concurrent renewal | medium | mitigate | Bounded skew/retry, one serialized acquisition and bounded errors. Evidence: `02-21-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-21-SC | Tampering | dependencies | high | mitigate | No install is introduced; existing locked/provenance-audited packages only. Evidence: `02-21-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-22-01 | Information disclosure | OpenAPI, generated client, DOM/history | high | mitigate | Negative schema/type assertions and seeded-secret browser scan. Evidence: `02-22-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-22-02 | Spoofing | callback/redirect | high | mitigate | No browser authorization redirect or callback operation exists. Evidence: `02-22-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-22-03 | Tampering | stale public status | medium | mitigate | Mutation invalidation/refetch and deterministic expiry/recovery tests. Evidence: `02-22-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-22-04 | Denial of service | duplicate connect actions | medium | mitigate | Separate pending state and disabled active mutation. Evidence: `02-22-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-22-SC | Tampering | dependencies | high | mitigate | No install is introduced; regenerate with the approved locked toolchain. Evidence: `02-22-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-23-01 | Denial of service | last active administrator | high | mitigate | Global authority lock, survivor predicate and cross-entry-point concurrency test. Evidence: `02-23-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-23-02 | Elevation of privilege | role membership/identity | high | mitigate | User UUID no-change invariant and service-owned membership authorization. Evidence: `02-23-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-23-03 | Information disclosure | CLI/reset output | high | mitigate | Bounded errors plus seeded-secret log/output scans. Evidence: `02-23-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-23-04 | Repudiation | CLI mutation | medium | mitigate | Preserve audit actor/source metadata and deterministic domain outcomes. Evidence: `02-23-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-23-SC | Tampering | dependencies | high | mitigate | No install is introduced; existing locked packages only. Evidence: `02-23-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-24-01 | Tampering | product/revision pointers | high | mitigate | Composite foreign keys and cross-owner negative tests. Evidence: `02-24-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-24-02 | Tampering | active mapping children | high | mitigate | PostgreSQL triggers for every child table/field and direct-SQL tests. Evidence: `02-24-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-24-03 | Elevation of privilege | trigger bypass | high | mitigate | No bypass marker/config exists; publication ordering and unrelated-row adversarial tests. Evidence: `02-24-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-24-04 | Denial of service | trigger locking | medium | mitigate | Stable lock order and concurrent publication regression. Evidence: `02-24-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-24-SC | Tampering | dependencies | high | mitigate | No install is introduced; Alembic/SQLAlchemy are already approved and locked. Evidence: `02-24-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-25-01 | Tampering | active revision during edit | high | mitigate | Deep clone into new IDs plus database active-child guards. Evidence: `02-25-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-25-02 | Tampering | partial clone | high | mitigate | Single transaction and full graph equality/count tests. Evidence: `02-25-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-25-03 | Spoofing | product identity normalization | medium | mitigate | A-01 canonicalization and publish-time uniqueness. Evidence: `02-25-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-25-04 | Elevation of privilege | stale/unconfirmed publication | high | mitigate | Product lock, current-preview/confirmation validation and rollback tests. Evidence: `02-25-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-25-05 | Denial of service | concurrent clone/publish | medium | mitigate | Stable Product lock and idempotent one-candidate/one-winner behavior. Evidence: `02-25-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-25-SC | Tampering | dependencies | high | mitigate | No install is introduced; existing locked packages only. Evidence: `02-25-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-26-01 | Elevation of privilege | revision mapping read | high | mitigate | Product active/candidate pointer validation plus admin dependency. Evidence: `02-26-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-26-02 | SSRF/Tampering | exact branch request | high | mitigate | Server-owned repository origin, encoded path and existing safe adapter. Evidence: `02-26-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-26-03 | Information disclosure | cursors/provider response | medium | mitigate | Opaque API cursors and bounded response projection. Evidence: `02-26-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-26-04 | Denial of service | pagination amplification | medium | mitigate | Existing A-03 budgets and one exact branch request instead of list scans. Evidence: `02-26-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-26-05 | Tampering | stale OAuth lease | high | mitigate | Plan 21 expiry/generation lease is mandatory for discovery. Evidence: `02-26-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-26-SC | Tampering | dependencies | high | mitigate | No install is introduced; generated client uses approved locked tooling. Evidence: `02-26-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-27-01 | Elevation of privilege | admin routes | high | mitigate | Existing admin route guard plus real 401/403 regression. Evidence: `02-27-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-27-02 | Tampering | stale/duplicate candidate | high | mitigate | Returned candidate ID, refresh sequence and one-candidate request-count tests. Evidence: `02-27-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-27-03 | Spoofing | current navigation state | low | accept | Location-derived `aria-current`; incorrect styling has no authority impact and is regression-tested. Evidence: `02-27-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-27-04 | Denial of service | duplicate candidate/navigation | medium | mitigate | Pending disable, idempotent backend command and request-count tests. Evidence: `02-27-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-27-05 | Information disclosure | long values/errors | medium | mitigate | Bounded safe response copy and no secret-bearing workspace fields. Evidence: `02-27-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-27-SC | Tampering | dependencies | high | mitigate | No install is introduced; existing shadcn/router/client patterns only. Evidence: `02-27-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-28-01 | Tampering | stale cursor generation | high | mitigate | Query-key generation isolation, abort/ignore stale responses and tests. Evidence: `02-28-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-28-02 | Denial of service | pagination amplification | high | mitigate | One-action/one-page bound, A-03 ceilings, request-count assertions. Evidence: `02-28-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-28-03 | Tampering | configured branch selection | high | mitigate | Exact branch query, identity-bound generation, and index-101 round-trip tests. Evidence: `02-28-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-28-04 | Information disclosure | provider cursor | medium | mitigate | Browser sees only opaque API cursor, never provider continuation URL. Evidence: `02-28-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-28-SC | Tampering | dependencies | high | mitigate | No install is introduced; only existing React and generated-client dependencies are used. Evidence: `02-28-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-29-01 | Denial of service | permanently running jobs | high | mitigate | Finite threshold, periodic watchdog and process-loss smoke. Evidence: `02-29-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-29-02 | Tampering | late/stale task result | high | mitigate | Attempt/generation/current-state compare-and-set and race tests. Evidence: `02-29-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-29-03 | Denial of service | watchdog scan amplification | medium | mitigate | Indexed bounded batch, SKIP LOCKED and validated interval. Evidence: `02-29-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-29-04 | Repudiation | timeout/retry history | medium | mitigate | Preserve terminal original, stable error code/timestamps and new retry identity. Evidence: `02-29-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-29-05 | Information disclosure | worker/provider error | medium | mitigate | Reuse the existing closed time_limit_exceeded code; no provider body/token or source-of-cause response field. Evidence: `02-29-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-29-SC | Tampering | dependencies | high | mitigate | No install is introduced; approved Celery/Redis stack only. Evidence: `02-29-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-30-01 | Tampering | SPEC/CONTEXT/coverage parsers | high | mitigate | Keyed semantic comparison preserves exact identifiers, statuses, dispositions and reasons. Evidence: `02-30-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-30-02 | Elevation of privilege | final coverage claim | high | mitigate | Reject count-only proxies, unresolved paths/symbols, deferred scope and missing executable evidence. Evidence: `02-30-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-30-03 | Repudiation | finding/gap mapping | medium | mitigate | Freeze CR-01..CR-10, WR-01..WR-02 and G1..G6 with explicit closing plan/task and node. Evidence: `02-30-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-30-04 | Denial of service | audit collection | low | accept | Source inventories are bounded local files and named test collection is finite. Evidence: `02-30-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-30-SC | Tampering | dependencies | high | mitigate | No install; use only existing locked parser/test tooling. Evidence: `02-30-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-31-01 | Tampering | branch parameter encoding | high | mitigate | Query-parameter contract and reserved-character API/client tests. Evidence: `02-31-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-31-02 | Information disclosure | generated schemas | high | mitigate | Closed response types and provider-field negative contract assertions. Evidence: `02-31-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-31-03 | Tampering | schema drift | medium | mitigate | Existing deterministic generation and byte-stable api:check. Evidence: `02-31-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-31-SC | Tampering | dependencies | high | mitigate | No install; existing pinned generator and lockfile only. Evidence: `02-31-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-32-01 | Tampering | revision selection | high | mitigate | Product-first state selection and exact active_revision ID/version request tests. Evidence: `02-32-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-32-02 | Elevation of privilege | stale confirmation | high | mitigate | Backend current-preview predicate plus blocked request-negative E2E. Evidence: `02-32-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-32-03 | Repudiation | reactivation/edit confusion | medium | mitigate | Separate named actions/routes and exact request trace assertions. Evidence: `02-32-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-32-SC | Tampering | dependencies | high | mitigate | No install; existing generated client and component patterns only. Evidence: `02-32-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-33-01 | Elevation of privilege | Workspace aggregates | high | mitigate | Principal-role gate plus non-admin request spies and real route tests. Evidence: `02-33-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-33-02 | Information disclosure | admin data in ordinary route | high | mitigate | Zero-call matrix and no cached/admin-derived rendering for non-admins. Evidence: `02-33-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-33-03 | Spoofing | current navigation state | low | accept | Location-derived aria-current; regression-tested and no backend authority impact. Evidence: `02-33-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-33-SC | Tampering | dependencies | high | mitigate | No install; existing router, session, generated-client, and shadcn patterns only. Evidence: `02-33-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-34-01 | Elevation of privilege | partial mapping readiness | high | mitigate | Terminal-cursor requirement and 51st mapping blocker E2E. Evidence: `02-34-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-34-02 | Tampering | stale page/poll generation | high | mitigate | Abort/generation identity and superseded-response tests. Evidence: `02-34-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-34-03 | Denial of service | duplicate page loads | medium | mitigate | One-action/one-cursor request counts and stable ID deduplication. Evidence: `02-34-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-34-SC | Tampering | dependencies | high | mitigate | No install; consumes Plan 28 hook and Plan 31 generated client. Evidence: `02-34-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-35-01 | Information Disclosure | live-provider stdout/stderr and failures | high | mitigate | Redact credentials at construction and assert sentinel secrets never appear in captured output. Evidence: `02-35-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-35-02 | Elevation of Privilege | requested Bitbucket grant/scope | high | mitigate | Require the production service to submit client_credentials with exact repository scope and architecture-test the absence of workspace enumeration and broader OAuth flows. Evidence: `02-35-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-35-03 | Tampering | repeated credential generations | high | mitigate | Drive all state changes through the authenticated production API and assert only the terminal generation remains authoritative. Evidence: `02-35-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-35-SC | Tampering | npm/pip/cargo installs | low | accept | This plan installs no packages and uses the existing project toolchain. Evidence: `02-35-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-36-01 | Denial of Service | watchdog stale-job selector | high | mitigate | Add and EXPLAIN-test the state/started_at access path used by the explicit bounded selector in Plan 02-29. Evidence: `02-36-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-36-02 | Tampering | migration upgrade/downgrade | medium | mitigate | Preserve row identities/counts and drop only the named index on downgrade. Evidence: `02-36-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-36-03 | Repudiation | Celery task correlation | medium | mitigate | Keep PreviewJob.id as the sole durable task identity and test the absence of schema/model drift. Evidence: `02-36-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-36-SC | Tampering | npm/pip/cargo installs | low | accept | This plan installs no packages and uses existing SQLAlchemy/Alembic/PostgreSQL tooling. Evidence: `02-36-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-37-01 | Elevation of privilege | CLI/API/admin UI | high | mitigate | Cross-entry authority tests, non-admin request-negative E2E and backend guards. Evidence: `02-37-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-37-02 | Information disclosure | credentials/logs/traces | high | mitigate | Seeded-secret scans over payload, DOM, logs, traces, screenshots and evidence. Evidence: `02-37-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-37-03 | Elevation of privilege | Bitbucket scope/verbs | high | mitigate | Exact-scope production exchange and provider spy rejecting every resource write. Evidence: `02-37-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-37-04 | Tampering | product graph/publication | high | mitigate | Composite integrity, active immutability and atomic publish E2E. Evidence: `02-37-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-37-05 | Denial of service | pagination/preview worker | high | mitigate | Exact boundary counts, indexed bounded watchdog and killed-worker recovery. Evidence: `02-37-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-37-06 | Repudiation | source-bound evidence | medium | mitigate | Capture and recheck one digest around every gauntlet layer. Evidence: `02-37-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-37-SC | Tampering | dependencies | high | mitigate | No install; existing lock/provenance/license/container audit remains mandatory. Evidence: `02-37-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-38-01 | Repudiation | review findings | high | mitigate | Fresh complete-diff review with current symbol/test/result citations and digest binding. Evidence: `02-38-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-38-02 | Tampering | evidence/source digest | high | mitigate | Review-mode and final-mode source-state verification before report acceptance. Evidence: `02-38-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-38-03 | Elevation of privilege | Phase completion gate | high | mitigate | Require `critical: 0` and exact verifier `status: passed`; every other state stops. Evidence: `02-38-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-38-04 | Information disclosure | review/evidence output | medium | mitigate | Reuse gauntlet secret scan and record only sanitized commands, counts, statuses and digests. Evidence: `02-38-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-38-SC | Tampering | dependencies | high | mitigate | No install; canonical lock/provenance audit must remain green in the official gauntlet. Evidence: `02-38-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-39-01 | Tampering | Compose scheduler authority | high | mitigate | Render both overlays and require exact environment/image/restart equality with backend and worker. Evidence: `02-39-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-39-02 | Denial of service | preview watchdog | high | mitigate | Kill the owning worker in each deployment overlay and require bounded scheduler terminalization plus isolated retry. Evidence: `02-39-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-39-03 | Repudiation | overlay smoke evidence | medium | mitigate | Record explicit staging and production results from isolated projects in the mandatory gauntlet layer. Evidence: `02-39-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-39-04 | Information disclosure | Compose/log evidence | high | mitigate | Owner-only env files, value-free contract diagnostics, existing multi-surface secret scan, and unconditional cleanup. Evidence: `02-39-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-39-SC | Tampering | package graph | high | mitigate | No install or lockfile change; retain the official dependency/provenance gauntlet unchanged. Evidence: `02-39-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-40-01 | Spoofing | product/revision/mapping identity | high | mitigate | Composite ownership FKs plus exact active pointer/version and inactive-state checks. Evidence: `02-40-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-40-02 | Tampering | published graph | critical | mitigate | Sidecar-only confirmation, existing 0009 triggers, before/after graph snapshots, and zero candidate clone. Evidence: `02-40-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-40-03 | Replay | stale preview confirmation | high | mitigate | Scope-domain identity, current generation, exact commits, latest attempt, detector/layout/result digest, and explicit actor confirmation. Evidence: `02-40-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-40-04 | Elevation of privilege | reactivation predicate | high | mitigate | Product-row lock and all-mapping exact predicate; sidecar cannot authorize candidate publication or another graph. Evidence: `02-40-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-40-05 | Information disclosure | provider/job evidence | medium | mitigate | Existing bounded schemas/log guards; sidecar stores UUIDs/digests/timestamps only, never source bytes or credentials. Evidence: `02-40-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-40-06 | Denial of service | active-revalidation jobs | medium | mitigate | Existing job reuse, exact A-03 bounds, Celery hard limits, watchdog, and latest-attempt rules. Evidence: `02-40-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-40-SC | Tampering | package graph | high | mitigate | No dependency install; retain locked audits and legitimacy gate unchanged. Evidence: `02-40-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-41-01 | Spoofing / Elevation of Privilege | Quattro route recovery | high | mitigate | Dipendenza admin su ogni route e test 401/403 fail-first. Evidence: `02-41-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-41-02 | Tampering | Revision/version/mapping/commit/generation inputs | high | mitigate | Request typed, exact binding service-side e 409 per ogni deriva. Evidence: `02-41-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-41-03 | Information Disclosure | Job/eligibility responses | high | mitigate | Schemi bounded closed e test di assenza per token, source e raw provider payload. Evidence: `02-41-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-41-04 | Repudiation | Create/confirm recovery | medium | mitigate | Preservare audit identity e correlation metadata già usate dai flussi admin. Evidence: `02-41-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-41-05 | Denial of Service | Job create polling | medium | mitigate | Idempotent reuse, polling bounded e 503/retry semantics esistenti. Evidence: `02-41-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-41-SC | Tampering | Package installs | high | mitigate | Nessuna installazione package è autorizzata; api:generate usa toolchain e lockfile esistenti. Evidence: `02-41-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-42-01 | Tampering | Reactivate UI gate | high | mitigate | Eligibility server-side all-mappings predicate; UI non sintetizza currentness dal layout. Evidence: `02-42-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-42-02 | Elevation of Privilege | Recovery controls | high | mitigate | Solo client admin generated operations; 401/403 bounded e backend resta autorità. Evidence: `02-42-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-42-03 | Information Disclosure | Live region, Playwright trace | high | mitigate | Messaggi bounded e secret guard su output/trace/evidence. Evidence: `02-42-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-42-04 | Denial of Service | Job polling | medium | mitigate | Backoff bounded, terminal-state stop e cleanup su unmount già dimostrati. Evidence: `02-42-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-42-05 | Repudiation | Confirm/reactivate sequence | medium | mitigate | E2E conserva route sequence e identity snapshot senza materiale segreto. Evidence: `02-42-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-42-SC | Tampering | Package installs | high | mitigate | Nessuna installazione package o lockfile mutation è autorizzata. Evidence: `02-42-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-43-01 | Spoofing / Elevation of Privilege | Framing della SPA admin | high | mitigate | CSP frame-ancestors none più X-Frame-Options DENY verificati sul runtime. Evidence: `02-43-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-43-02 | Tampering | Built frontend image | high | mitigate | Smoke ricostruisce/interroga l'immagine e confronta valori completi/univoci. Evidence: `02-43-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-43-03 | Information Disclosure | Referrer/MIME/capability behavior | medium | mitigate | nosniff, strict-origin-when-cross-origin e Permissions-Policy restrittiva. Evidence: `02-43-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-43-04 | Denial of Service | CSP app resource loading | medium | mitigate | Policy completa consente self/data e connect-src applicativi richiesti, con smoke shell. Evidence: `02-43-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-43-05 | Repudiation | Security smoke result | low | mitigate | Gate deterministico identifica target e header senza output sensibile. Evidence: `02-43-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-43-SC | Tampering | Package installs | high | mitigate | Nessuna installazione package; solo Nginx e harness esistenti. Evidence: `02-43-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-44-01 | Tampering | Hostile opaque branch names | high | mitigate | Generated query serialization, original branch bytes, and exact returned-name equality with no trimming/case/Unicode equivalence Evidence: `02-44-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-44-02 | Tampering | Commit confusion or stale branch identity | high | mitigate | Bind repository ID + exact branch response name + returned commit before existing candidate-version or active-revision-version job authority Evidence: `02-44-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-44-03 | Tampering / Denial of Service | First-page list fallback | high | mitigate | Remove list-based resolution; issue exactly one detail request per configured side regardless of branch-list position Evidence: `02-44-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-44-04 | Elevation of Privilege / Tampering | Accidental provider write or active/candidate authority confusion | high | mitigate | Preserve generated GET-only branch operation, distinct candidate/active job operations, repository-only scope, and immutable active graph Evidence: `02-44-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-44-SC | Tampering | Dependency/generated-client supply chain | high | mitigate | Add no package; reuse the pinned generated client and require api:check plus package/lockfile zero drift Evidence: `02-44-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-45-01 | Tampering | Unsaved product/mapping state | high | mitigate | Block every router PUSH/REPLACE/POP while registry state is dirty; real page tests prove unmount cannot occur before decision and cancellation preserves exact values. Evidence: `02-45-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-45-02 | Tampering / Repudiation | Pending transaction lifecycle | high | mitigate | Snapshot the first blocker callbacks/location/token, consume proceed/reset once, invalidate on completion/unmount, and test repeated activation plus canceled-A/new-B non-replay. Evidence: `02-45-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-45-03 | Spoofing | Destination route/path identity | high | mitigate | Continue only the captured React Router transaction; never construct or trust a dialog-supplied path, and assert the exact stored URL reached once. Evidence: `02-45-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-45-04 | Denial of Service | Keyboard/focus and nested Sheet/Dialog | high | mitigate | Exact accessible Alert Dialog, Escape/cancel path, connected-trigger focus restoration, delayed Sheet close, 320px/keyboard/overflow Playwright checks. Evidence: `02-45-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-45-05 | Tampering | Document-exit bypass | high | mitigate | Aggregate dirty-only useBeforeUnload remains active for reload/tab exits; Playwright reload plus synthetic beforeunload tests cover both product and mapping registrations. Evidence: `02-45-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-45-SC | Tampering | Package/dependency supply chain | high | mitigate | No install, package manifest, lockfile, registry, or generated-client mutation is authorized; immutable-file gate blocks drift. Evidence: `02-45-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-46-01 | Repudiation / Elevation of privilege | Phase closeout attestation | high | mitigate | Require current focused/full/browser/18-layer evidence, fresh `critical: 0`, exact `status: passed`, and matching digests; every other combination stops closure. Evidence: `02-46-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-46-02 | Tampering | Source manifest and review/final digests | high | mitigate | Compute review/final digests from `phase2_source_manifest.txt`, commit canonical review before final rerun, validate review-source/report-digest, and restart on any drift. Evidence: `02-46-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-46-03 | Spoofing / Repudiation | Historical review and verifier artifacts | high | mitigate | Label existing reports stale after 02-44/02-45, dispatch fresh typed reviewer/verifier contexts, replace artifacts only with current results, and reject inherited PASS claims. Evidence: `02-46-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-46-04 | Tampering | CR-14/CR-15 evidence selection | high | mitigate | Require both focused behavior and named real-router/real-backend paths, including exact branch identity, immutable active graph, values/focus, single navigation, and zero provider writes. Evidence: `02-46-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-46-05 | Tampering / Information disclosure | Evidence ledger | high | mitigate | Record only sanitized commands, counts, statuses, names, and digests; preserve secret scan/provider audit layers and reject credential-, ciphertext-, or provider-body-shaped output. Evidence: `02-46-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-46-06 | Tampering | Package/dependency and container supply chain | high | mitigate | Authorize no install or package/lockfile/dependency mutation, run the existing audit/provenance gauntlet layer, and retain WR-04/WR-05 instead of overstating provenance. Evidence: `02-46-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-46-07 | Repudiation | Warning disposition | high | mitigate | Require WR-03..WR-08 one-to-one in fresh review and verifier, preserve OPEN Warning labels in canonical evidence, and fail verification if any is silently omitted or claimed fixed. Evidence: `02-46-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-46-08 | Tampering / Repudiation | Semantic closeout inventory parser | high | mitigate | RED→GREEN structured YAML/table parsing, exact ID sets, count/status reconciliation, valid-state transition tests, and negative controls run before the first 18-layer gauntlet. Evidence: `02-46-PLAN.md`, matching summaries, and `02-VERIFICATION.md`. | closed |
| T-02-SC | Tampering | Multiple Phase 2 surfaces | high | mitigate | Dependency-legitimacy controls defined by Plans 02-04, 02-06, 02-12, and 02-20; matching summaries and `02-VERIFICATION.md` confirm execution. | closed |

*Status vocabulary: `open` · `closed` · `open — below high threshold (non-blocking)`.*

## Summary Threat Flags

Execution summaries introduced four explicit boundary flags beyond their local plan tables. Each maps to an already-registered threat family and is closed by the cited controls.

| Source | Flag | Mapped Threat | Evidence | Status |
|--------|------|---------------|----------|--------|
| `02-03-SUMMARY.md` | Administrator repository route authorization | T-02-01 | Shared database-backed admin dependency plus zero-mutation 401/403 tests | closed |
| `02-10-SUMMARY.md` | Product lifecycle route authorization | T-02-01 | Shared database-backed admin dependency plus no-mutation 401/403 tests | closed |
| `02-19-SUMMARY.md` | OAuth redirect boundary | T-02-03 | Same-tab backend authority and transient HTTPS destination validation | closed |
| `02-19-SUMMARY.md` | Confirmation/publication mutation | T-02-06 | Generated operations, exact current identities, named confirmation, backend-authoritative success | closed |

## Residual Risks Below Blocking Threshold

These findings remain open. They are not silently converted into accepted risks and do not increment `threats_open` because the configured blocking threshold is `high`.

| Risk ID | Review Ref | Category | Severity | Required Follow-up | Status |
|---------|------------|----------|----------|--------------------|--------|
| R-02-03 | WR-03 | Provider lease expiry bounds | medium | Add and test a defensible upper bound for provider `expires_in`. | open — below high threshold (non-blocking) |
| R-02-04 | WR-04 | Development dependency advisory | medium | Upgrade or otherwise close the known moderate advisory in the locked developer graph. | open — below high threshold (non-blocking) |
| R-02-05 | WR-05 | Container provenance | medium | Pin production container images by immutable digest. | open — below high threshold (non-blocking) |
| R-02-06 | WR-06 | Environment configuration integrity | medium | Add the Phase 2 settings to the canonical `.env.example`. | open — below high threshold (non-blocking) |
| R-02-07 | WR-07 | Security evidence completeness | medium | Include the executable edge-matrix JSON in the Phase 2 source manifest. | open — below high threshold (non-blocking) |
| R-02-08 | WR-08 | Deployment flow integrity | medium | Remove or repair the deprecated no-flag Compose flow that still targets removed OAuth endpoints. | open — below high threshold (non-blocking) |

## Accepted Risks Log

No accepted risks. The six residual findings above remain open and tracked rather than accepted.

## Security Audit 2026-09-01

| Metric | Count |
|--------|-------|
| Unique plan-time threats | 148 |
| Summary threat flags mapped to existing threats | 4 |
| Closed planned threats | 148 |
| Open below-threshold residual risks | 6 |
| Open Critical/High blocking threats | 0 |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open Below Threshold | Blocking Open | Run By |
|------------|---------------|--------|----------------------|---------------|--------|
| 2026-09-01 | 154 | 148 | 6 | 0 | Codex / `gsd-secure-phase` ASVS L1 |

## Evidence

- `02-01-PLAN.md` through `02-46-PLAN.md`: plan-time trust boundaries and STRIDE registers.
- `02-01-SUMMARY.md` through `02-46-SUMMARY.md`: completed implementation and test evidence.
- `02-REVIEW.md`: Critical 0, six retained Warning findings.
- `02-VERIFICATION.md`: `status: passed`, 8/8 roadmap success criteria, 15/15 requirements, `behavior_unverified: 0`.
- `docs/evidence/phase-02-gap-closure.md`: final gauntlet, regression reseal, source-digest, review, and verifier evidence.

## Sign-Off

- [x] All planned threats have a disposition.
- [x] All Critical/High planned mitigations have execution evidence.
- [x] Summary threat flags are incorporated.
- [x] No risk was silently accepted.
- [x] Six below-threshold residual risks remain explicitly tracked.
- [x] `threats_open: 0` confirmed at `block_on: high`.
- [x] `status: verified` set in frontmatter.

**Approval:** verified 2026-09-01
