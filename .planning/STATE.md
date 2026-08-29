---
gsd_state_version: 1.0
current_phase: 02
current_phase_name: Admin Configuration
status: executing
stopped_at: Completed 02-32-PLAN.md
last_updated: "2026-08-29T20:44:35.048Z"
last_activity: 2026-08-29
last_activity_desc: Phase 02 execution started
state_head: bdecb9d2fb34e54d2ad82ae6faa923fc8337b36b
progress:
  total_phases: 9
  completed_phases: 1
  total_plans: 53
  completed_plans: 48
  percent: 11
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-24)

**Core value:** Product teams can quickly find, review, constrain, modify, comment on, and approve translations, then send approved changes back through the standard Bitbucket Cloud pull request workflow.
**Current focus:** Phase 02 — Admin Configuration

## Current Position

Phase: 02 (Admin Configuration) — EXECUTING
Plan: 33 of 38
Status: Ready to execute
Last activity: 2026-08-29 — Phase 02 execution started

Progress: [█░░░░░░░░░] 11%

## Performance Metrics

**Velocity:**

- Total plans completed: 15
- Average duration: 1h58min
- Total execution time: 29.4 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Platform Foundation | 15/15 | 29.4h | 1h58min |

**Recent Trend:**

- Last 5 plans: none
- Trend: N/A

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 1 min | 2 tasks | 1 files |
| Phase 01 P02 | 18 min | 2 tasks | 20 files |
| Phase 01 P03 | 51 min | 2 tasks | 32 files |
| Phase 01 P04 | 24 min | 2 tasks | 9 files |
| Phase 01 P05 | 29 min | 2 tasks | 19 files |
| Phase 01 P06 | 38 min | 3 tasks | 10 files |
| Phase 01 P07 | 33 min | 3 tasks | 12 files |
| Phase 01 P08 | 33min | 3 tasks | 13 files |
| Phase 01 P09 | 19min | 2 tasks | 17 files |
| Phase 01 P10 | 31min | 2 tasks | 26 files |
| Phase 01 P11 | 8min | 2 tasks | 3 files |
| Phase 01 P12 | 24min | 2 tasks | 12 files |
| Phase 01 P13 | 35min | 2 tasks | 18 files |
| Phase 01 P14 | 4h45min | 3 tasks | 64 files |
| Phase 01 P15 | 18h56min | 2 tasks | 35 files |
| Phase 02 P01 | 35min | 2 tasks | 11 files |
| Phase 02 P02 | 42min | 3 tasks | 14 files |
| Phase 02 P03 | 15min | 3 tasks | 12 files |
| Phase 02 P04 | 32min | 3 tasks | 11 files |
| Phase 02 P05 | 26min | 2 tasks | 15 files |
| Phase 02 P06 | 20min | 2 tasks | 11 files |
| Phase 02 P07 | 37min | 2 tasks | 18 files |
| Phase 02 P08 | 65min | 3 tasks | 16 files |
| Phase 02 P09 | 2h27min | 2 tasks | 11 files |
| Phase 02 P10 | 28min | 2 tasks | 11 files |
| Phase 02 P11 | 2h 14m | 2 tasks | 18 files |
| Phase 02 P12 | 32min | 2 tasks | 16 files |
| Phase 02 P13 | 35m | 2 tasks | 11 files |
| Phase 02 P14 | 1h07m | 2 tasks | 16 files |
| Phase 02 P15 | 18min | 2 tasks | 1 files |
| Phase 02 P16 | 37min | 2 tasks | 6 files |
| Phase 02 P17 | 42min | 2 tasks | 11 files |
| Phase 02 P18 | 1h22m | 2 tasks | 10 files |
| Phase 02 P19 | 32min | 3 tasks | 9 files |
| Phase 02 P20 | 13h40min | 3 tasks | 19 files |
| Phase 02-admin-configuration P21 | 26min | 3 tasks | 12 files |
| Phase 02-admin-configuration P23 | 13min | 2 tasks | 5 files |
| Phase 02-admin-configuration P22 | 19min | 2 tasks | 9 files |
| Phase 02-admin-configuration P24 | 25min | 2 tasks | 10 files |
| Phase 02-admin-configuration P35 | 29min | 2 tasks | 7 files |
| Phase 02-admin-configuration P25 | 21min | 2 tasks | 9 files |
| Phase 02-admin-configuration P26 | 2h 20m | 2 tasks | 16 files |
| Phase 02 P36 | 6min | 2 tasks | 3 files |
| Phase 02 P29 | 35min | 3 tasks | 12 files |
| Phase 02-admin-configuration P31 | 10min | 2 tasks | 2 files |
| Phase 02-admin-configuration P27 | 33m | 2 tasks | 6 files |
| Phase 02-admin-configuration P28 | 24m | 2 tasks | 8 files |
| Phase 02 P32 | 26min | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- V1 targets Bitbucket Cloud only.
- Frontend and backend are separate applications.
- Frontend uses React, Vite, TypeScript, and shadcn/ui.
- Backend uses Python, FastAPI, OAuth2, PostgreSQL, SQLAlchemy, and Alembic.
- V1 authentication uses internal accounts with corporate email as the unique login identifier and password credentials managed by VerboFlex.
- The first admin is created through a CLI bootstrap command; password reset is admin-managed and requires a password change on first login.
- Microsoft Entra ID/OIDC authentication remains a future integration; the internal role model must stay provider-independent.
- Background work uses Celery and Redis.
- V1 supports Android XML, Qt `.ts`, JSON, and iOS `.strings`.
- V1 uses simple draft/approved/rejected review states and per-translation comments.
- Every phase closes with tests, code review, and deploy/build smoke verification.
- Figma, extra validators, external identity, and complex approval gates are deferred.
- [Phase 01]: Phase 1 dependency installs are limited to the explicitly approved SPEC allowlists; any unexpected direct dependency requires a visible SPEC revision.
- [Phase 01]: Use uv_build 0.11.12 as the sole bounded PEP 517 backend for the installable src layout.
- [Phase 01]: Pin approved redis-py to 6.4.0, the newest release compatible with Celery and Kombu's redis<6.5 bound.
- [Phase 01]: Keep every non-health Phase 1 API route as a final-signature callable 501 seam until its dedicated TDD plan.
- [Phase 01]: Exact-pin TypeScript 6.0.3 for compatibility with the approved generated-client toolchain.
- [Phase 01]: Patch the generator graph through a js-yaml 4.3.1 transitive override while preserving the direct dependency allowlist.
- [Phase 01]: Keep generated client configuration in src/api/config.ts with same-origin fallback and included credentials.
- [Phase 01]: Typed deployed settings reject missing, sentinel, or sub-32-byte signing material and insecure refresh cookies; CORS accepts exact origins only.
- [Phase 01]: API and worker share one backend image but run distinct one-process commands and health checks; named overlays stay provider-neutral and fail closed.
- [Phase 01]: Corporate-email normalization trims only the database-aligned ASCII whitespace set, lowercases, validates, and remains provider-independent.
- [Phase 01]: A PostgreSQL transaction advisory lock serializes the empty-user decision so concurrent bootstrap attempts leave exactly one admin.
- [Phase 01]: Administrative reset locks the selected user, rehashes the password, forces a password change, increments token_version, and revokes only that user's live sessions in one transaction.
- [Phase 01]: Passwords enter the CLI only through getpass or stdin; argv, defaults, logs, and plaintext persistence are forbidden.
- [Phase 01]: JWT authority uses explicit HS256, required claims, a five-second tolerance, and exact purpose-specific lifetimes.
- [Phase 01]: Login rate limiting is Redis-authoritative before lookup and Argon2 and fails closed with 503.
- [Phase 01]: Protected authority always reconciles active state, token_version, sessions, password policy, and roles with PostgreSQL.
- [Phase 01]: Refresh plaintext uses 32 random bytes, is never persisted, and is exposed only through the scoped HttpOnly cookie.
- [Phase 01]: Refresh credentials use 32 random bytes, are stored only as SHA-256 digests, and replay revokes the full session family. — Limits bearer exposure and turns predecessor reuse into durable theft containment.
- [Phase 01]: Cookie-authenticated mutations enforce exact Origin before Redis and PostgreSQL; absent Origin remains valid for non-browser clients. — Prevents ambient-cookie CSRF without excluding CLI or service callers.
- [Phase 01]: Logout remains available during Redis outage, while refresh and password change fail closed before expensive or durable work. — Users can always shed authority without weakening authority replacement endpoints.
- [Phase 01]: Successful password replacement advances token_version, revokes every current-user session, clears the refresh cookie, and requires a fresh login. — No authority issued under the old credential survives or is silently replaced.
- [Phase 01]: Health uses bounded local limiting; ordinary reads use Redis with bounded local outage fallback; sensitive auth actions remain Redis fail-closed. — Preserves diagnostic availability without weakening credential or authority mutation boundaries.
- [Phase 01]: Limiter identity uses normalized server authority or the validated server-observed peer and never trusts forwarded headers implicitly. — Prevents callers from rotating keys through spoofed proxy headers before an explicit trusted-proxy policy exists.
- [Phase 01]: Service status projects only approved enums through independently timeout-bounded database, Redis, and worker probes. — Keeps operations useful without leaking addresses, credentials, exceptions, stacks, task identifiers, or raw inspect output.
- [Phase 01]: Celery tasks are JSON-only, named, non-eager, and executed by a distinct Redis-backed worker process outside HTTP routes. — Establishes the reusable background-work boundary required by later import and pull-request phases.
- [Phase 01]: Freeze explicit stable operation IDs and regenerate only from canonical FastAPI OpenAPI.
- [Phase 01]: Browser authority is React-memory-only and async transitions are versioned so logout invalidates stale responses.
- [Phase 01]: Guard credential persistence with narrow AST checks and fail-control fixtures.
- [Phase 01]: Use the current official shadcn 4.19.0 new-york-v4 Radix source with direct exact-pinned radix-ui and next-themes. — Matches the user's final modern-source approval while retaining the superseded conservative decision in append-only history.
- [Phase 01]: Limit Plan 01-10 registry ownership to thirteen approved UI primitives, components.json, utils.ts, and the official use-mobile hook. — Makes the 16-file supply-chain boundary mechanically auditable and excludes unrelated registry components.
- [Phase 01]: Use ESLint and @eslint/js 9.39.5 for the approved lint graph. — It is the newest exact version compatible with eslint-plugin-jsx-a11y 6.10.2 without forcing peer resolution.
- [Phase 01]: Keep official shadcn sources unchanged and enforce the approved visual contract through the global theme boundary.
- [Phase 01]: Defer next-themes provider integration until a selectable or dark theme is approved; the official Sonner fallback works without it.
- [Phase 01]: Route authority is a pure projection of SessionState; URLs, roles, and client-controlled values never grant access. — Keeps the backend-derived state machine authoritative for every direct navigation.
- [Phase 01]: Generated-client failures become sanitized rejected session actions so pages can announce one generic response without backend diagnostics. — Preserves non-enumerating UI feedback and retains the existing signed-out or restricted authority.
- [Phase 01]: Successful forced password replacement clears browser authority and returns to signed-out login. — Matches the backend contract that revokes old authority and requires fresh login.
- [Phase 01]: Render the ordinary shell only from generated authenticated identity, status, and logout operations; server roles remain authoritative. — Prevents client-created authority and keeps failures bounded.
- [Phase 01]: Use a fixed sidebar at 1024px and shadcn Sheet navigation below 1024px. — Matches the approved desktop versus tablet/mobile layout contract.
- [Phase 01]: Use a non-self-referential review digest plus a separate canonical digest that includes the CLOSED review artifact.
- [Phase 01]: Keep default gauntlet fail-closed on CLOSED/PASS and expose a distinct explicitly non-final post-fix candidate mode.
- [Phase 01]: Require every non-equivalent backend/frontend auth-session mutant killed with no score waiver or ignored mutation.
- [Phase 01]: Bind accepted secret-scan false positives to exact path, line, plugin, and hashed fingerprint.
- [Phase 01]: Retain VF-SEC-007 as visible Low dev-only debt requiring ship-time upgrade or time-bounded acceptance.
- [Phase 01]: Keep __Host-verboflex_refresh Secure in every environment; Microsoft Entra/OIDC remains deferred.
- [Phase 01]: Human-grade every material blind finding; behavioural remediation requires TDD, a new digest, the full gauntlet, and fresh verification.
- [Phase 01]: Accept exactly two equivalent backend join mutants only through exact mapping and identical PostgreSQL SQL proof; kill all 891 non-equivalent mutants.
- [Phase 01]: Use the explicitly authorized Round 3 exception after Round 2 remediation; no further verifier round is authorized.
- [Phase 02]: Keep the Phase 1 User UUID as the sole identity while roles remain additive many-to-many authority memberships. — Role changes must not create another identity or email-role anchor.
- [Phase 02]: Serialize administrative authority mutations with the existing global advisory lock and locked actor/target revalidation. — Self-admin and last-active-admin invariants must survive concurrent requests.
- [Phase 02]: Treat normalized identical display-name and role updates as true non-mutating no-ops. — No-op submissions must not advance token_version, revoke sessions, or rewrite role relationships.
- [Phase 02]: Keep existing CLI entry points as wrappers over the shared admin-user service. — This preserves verboflex.cli compatibility while giving HTTP and CLI one transaction authority.
- [Phase 02]: Apply A-01 in application code and persist its name_key so global product identity never depends on locale-sensitive database collation. — Keeps equality deterministic across PostgreSQL locales and every API consumer.
- [Phase 02]: Keep an immutable active product revision and a distinct editable candidate revision. — Candidate failures and partial work cannot mutate live configuration.
- [Phase 02]: Require expected candidate version and preserve revision identity for semantic no-ops. — Makes concurrent edits explicit while identical saves stay truly non-mutating.
- [Phase 02]: Bind opaque product cursors to the status filter and order by name_key then Product UUID. — Keeps pagination stable, canonical, and independent of client-side sorting.
- [Phase 02]: Retain D-07: one global Repository UUID is uniquely identified by normalized lowercase workspace plus repository slug.
- [Phase 02]: Keep duplicate repository registration as a bounded conflict; get-by-UUID and list are the separate reuse paths.
- [Phase 02]: Order repository collections by normalized descriptive-name key with workspace/slug fallback, then workspace, slug, and Repository UUID.
- [Phase 02]: Exclude provider reads, tokens, credentials, branches, and product mapping state from the repository registry boundary.
- [Phase 02]: Use one locked id=1 Bitbucket connection row with monotonic generation as downstream stale-work authority.
- [Phase 02]: Encrypt provider tokens only behind a MultiFernet SecretBox with first-key writes, rotation-key reads, and bounded failures.
- [Phase 02]: Store OAuth state only as an atomic single-use SHA-256 digest bound to admin, session, generation, callback, and fixed SPA destination.
- [Phase 02]: Require exact Bitbucket repository scope; any later capability expansion needs an explicit plan decision.
- [Phase 02]: Guarantee Bitbucket revocation locally by advancing the locked generation and deleting both ciphertexts; do not claim an unverified provider revoke operation.
- [Phase 02]: Authorize the Bitbucket callback from consumed OAuth state rather than an ambient bearer token, then redirect only to /admin/bitbucket.
- [Phase 02]: Keep exact repository read scope and expose only the four approved public connection statuses through closed schemas.
- [Phase 02]: Expose only repository metadata, branch list/detail, and commit-bound source tree/raw reads; reject every other Bitbucket endpoint family before credential acquisition.
- [Phase 02]: Use one pooled HTTPX client with redirects, ambient proxy trust, content decoding, and hidden retries disabled or constrained at construction.
- [Phase 02]: Treat a generation change during a response as revocation and discard the provider result even after an HTTP success.
- [Phase 02]: Preserve Bitbucket branch spelling and provider order; expose pagination only through a bounded application-owned opaque cursor.
- [Phase 02]: Resolve branch authority once, then use only the immutable commit hash for every source tree and raw read.
- [Phase 02]: Treat every A-03 budget, continuation, encoding, redirect, or generation violation as a typed blocking failure rather than returning partial data.
- [Phase 02]: Keep raw provider source bytes backend-only; public discovery responses expose only commit, path, size, and aggregate byte metadata.
- [Phase 02]: Retain D-12: one ProductRepositoryMapping identity has exactly one explicit direct or separate topology.
- [Phase 02]: Store branch, target, default, and selected-layout configuration on the candidate mapping; global Repository reuse shares none of it.
- [Phase 02]: Expose only guarded mapping list/create/update in Plan 08; Separate writes remain Plan 09 and no mapping delete lifecycle exists.
- [Phase 02]: Bind canonical mapping cursors to the candidate revision and exact topology/repository/C-collated branch/NULLS-LAST/UUID tuple.
- [Phase 02]: Fix future PR grouping identity to exact Repository UUID plus exact target branch; mapping, file, language, and product never alter the group key.
- [Phase 02]: For Separate mappings, configuration preview targets the Translations repository; Direct targets its sole repository, and only configured allowed/default target branches are exposed.
- [Phase 02]: Use the Product row lock as the sole publication, deactivation, and reactivation linearization point.
- [Phase 02]: Keep absent preview confirmation as the explicit preview_confirmation_required blocker until Plan 02-14 supplies the digest predicate.
- [Phase 02]: Project publication blockers as one closed ordered 409 vocabulary, while stale identities and versions use an empty-blocker lifecycle conflict.
- [Phase 02]: Return lifecycle success only from a fresh post-commit product projection; provider writes and canonical translation mutations remain absent.
- [Phase 02]: Preview currentness requires complete live candidate, mapping, repository-side, connection-generation, detector/layout, digest, and attempt identity while historical results remain inspectable.
- [Phase 02]: The pre-detector preview contract rejects source, credential, provider, Celery, canonical-row, and confirmation data before persistence.
- [Phase 02]: Android preview accepts only strict UTF-8 with an optional UTF-8 BOM and plain direct-child string elements; every unsupported construct fails closed.
- [Phase 02]: One preview candidate represents exactly one Android res root and repository side at confidence 1.0 without canonical identity or confirmation authority.
- [Phase 02]: The 1 MiB/file, 20 MiB total, 32-language, 10-sample/language, and 100-sample ceilings are exact blocking boundaries.
- [Phase 02]: Provider reads remain commit-bound and mutation-free while parsing and persistence stay behind the durable Celery worker boundary.
- [Phase 02]: iOS preview locale identity requires exactly one bounded locale.lproj directory component and stores a canonical locale plus locale path template. — This matches the platform layout while preventing missing or competing path locales from becoming confirmable.
- [Phase 02]: The iOS adapter is a bounded strict decoder and state-machine lexer with immutable spans and no serialization interface. — Preview needs hostile-input detection and samples only; canonical parsing and format-preserving writes remain later-phase authority.
- [Phase 02]: The durable preview worker invokes one four-format registry while the Plan 12 Android processor name remains a compatibility delegate. — All formats share one deterministic overlap-rejecting path without breaking the existing worker seam.
- [Phase 02]: A confirmation is current only when its complete candidate, job, mapping, repository side, connection generation, commit, detector, layout, and result digest identity still matches. — Historical or partial preview evidence must never authorize publication.
- [Phase 02]: The Product row lock remains the sole all-mapping publication and reactivation linearization point. — All candidate digests are rechecked before one atomic active-revision transition.
- [Phase 02]: Reactivation of an unchanged published revision uses the same exact current-confirmation predicate. — A relaxed reactivation path would allow stale work to restore authority.
- [Phase 02]: Keep the existing pinned api:generate and api:check scripts unchanged; deterministic regeneration plus git diff is the drift authority.
- [Phase 02]: Freeze the complete set of 29 Phase 2 admin operation IDs and require uniqueness before UI consumption.
- [Phase 02]: Treat the already-current Plan 02-14 generated outputs as canonical regression armor; no generated or dependency file needed a committed edit.
- [Phase 02]: Project Administration visibility only from server-loaded SessionState roles; UI role checks never authorize mutations.
- [Phase 02]: Render exact Products, Users, and Bitbucket destinations from one shared responsive navigation model.
- [Phase 02]: Keep product detail navigation URL-backed in Overview, Repositories, Mappings, Preview order while Plans 18 and 19 own feature data.
- [Phase 02]: Generated administrator user operations remain the sole wire authority; visible rows change only from backend responses.
- [Phase 02]: Temporary plaintext remains local to the acknowledgement dialog and is synchronously cleared before parent closure.
- [Phase 02]: Reset, deactivate, and reactivate use named confirmations that preserve server-owned row and dialog state on denial.
- [Phase 02]: Keep repository registration limited to Workspace, Repository slug, and an optional descriptive name; credentials remain outside every product form.
- [Phase 02]: Populate source, target, Keys, and Translations branch controls only from generated live discovery responses and invalidate superseded reads by generation.
- [Phase 02]: Represent allowed targets as a checkbox set and permit Default target only when it is a member of that set.
- [Phase 02]: Require named confirmation before clearing topology-specific values and expose no mapping delete or manual path, glob, locale, file, or format controls.
- [Phase 02]: Accept only transient HTTPS OAuth destinations without user info or fragments and navigate in the same tab.
- [Phase 02]: Use the complete preview authority tuple as polling identity so stale jobs cannot replace current state.
- [Phase 02]: Require explicit current exact-layout confirmation and backend success before publication changes UI lifecycle state.
- [Phase 02]: Issue live Bitbucket authority only through client credentials and accept it only when effective scope is exactly repository.
- [Phase 02]: Keep live credentials in an ignored owner-only file, tokens memory-only, and evidence limited to counts, timings, and SHA-256 identities.
- [Phase 02]: Retry only Docker's exact address-in-use race with at most three complete isolated attempts; every other failure remains fatal.
- [Phase 02]: Persist client-credentials authority as encrypted access-only material while retaining legacy paired rows only for reversible migration compatibility.
- [Phase 02]: Treat provider expiry as authoritative and serialize renewal under the singleton lock; failed renewal advances and clears the expired generation.
- [Phase 02]: Expose direct administrator connect and reconnect with a six-field no-store status and no callback, workspace, generation, or credential surface.
- [Phase 02]: Preserve the canonical User UUID across role plurality and concurrency — Roles remain fixed-vocabulary set membership and never create role-specific identity.
- [Phase 02]: Route HTTP and CLI deactivation through one survivor authority — The global advisory lock, target lock, and prospective survivor predicate now guard both entry points.
- [Phase 02]: Retry generated credential policy collisions within a bounded loop — Rejected candidates never mutate authority or appear in responses or logs.
- [Phase 02]: Connect and reconnect are direct generated API mutations that never navigate and always refetch bounded public status after success.
- [Phase 02]: Bitbucket acquisition failures expose fixed recovery guidance while provider diagnostics and credential-bearing fields remain outside browser-visible state.
- [Phase 02]: Only the active connect or reconnect control is disabled; revoke retains independent confirmation and pending authority.
- [Phase 02]: Reject legacy cross-owner product and preview graphs before migration; never silently reparent data. — Ownership cannot be inferred safely, and bounded failure preserves operator control.
- [Phase 02]: Keep active and published historical revision graphs immutable with no trigger bypass. — Old and new published configurations must remain authoritative regardless of caller or pointer changes.
- [Phase 02]: Lock affected revisions then owning Products in stable order before child mutation. — This serializes candidate edits with publication without caller-specific settings.
- [Phase 02]: Flush publication metadata before switching Product pointers inside the same transaction. — The database trigger sees a candidate metadata transition while rollback preserves atomic publication.
- [Phase 02]: Keep the live provider probe behind authenticated VerboFlex APIs; only production service code may acquire or hold a provider token.
- [Phase 02]: Replace exactly three obsolete OAuth coverage keys while preserving the other 41 keys and dispositions.
- [Phase 02]: Keep candidate edit identity on ProductRevision until atomic publication promotes it to Product.
- [Phase 02]: Clone the complete active mapping graph with fresh identities while clearing all preview confirmation authority.
- [Phase 02]: Publish metadata, canonical identity, active pointer, candidate clear, and activation under one Product lock and transaction without trigger bypass.
- [Phase 02-admin-configuration]: Authorize revision mapping reads only through both the Product active/candidate pointer and the ProductRevision owner; reads never lock, clone, or mutate the graph.
- [Phase 02-admin-configuration]: Treat branch_name as a required opaque query value and resolve it through exactly one expiry-safe adapter detail request without listing or normalization.
- [Phase 02-admin-configuration]: Keep provider continuation URLs server-side while preserving deterministic application items and next_cursor through OpenAPI and generated clients.
- [Phase 02]: Index only running PreviewJob rows by state and started_at while retaining id as the deterministic query tiebreaker and sole Celery identity. — This matches the bounded watchdog predicate without inventing task_id or widening identity.
- [Phase 02]: Use transaction-local sequential-scan disabling for watchdog EXPLAIN coverage. — This proves the named partial index is usable without relying on a brittle global PostgreSQL planner choice.
- [Phase 02]: Terminalize only exact running PreviewJob UUID, attempt, and connection-generation identities; PreviewJob.id remains the sole Celery identity.
- [Phase 02]: Use hard limit plus grace as the inclusive stale threshold with a validated scan interval and finite terminalization bound.
- [Phase 02]: Run Celery Beat separately from worker capacity so process loss cannot remove durable reconciliation.
- [Phase 02]: Treat access-only unexpired client-credentials generations as the current Bitbucket preview credential shape.
- [Phase 02]: Treat the Plan 26 schema and generated operations as inherited canonical behavior; do not fabricate a RED gate by reverting or hand-editing generated artifacts.
- [Phase 02]: Prove reserved branch spelling at the generated runtime URL boundary by decoding branch_name from the query while asserting the pathname contains only repository identity.
- [Phase 02]: Keep provider continuation and credential exclusions property-based so the legitimate repository workspace field remains available while Bitbucket status workspace stays forbidden.
- [Phase 02]: Plan 02-27: Existing-product edit loads are read-only; active-only products create exactly one candidate only through a genuinely changed details PATCH.
- [Phase 02]: Plan 02-27: Candidate and mapping identities remain server-owned and are restored unchanged across deep-link, refresh, and browser history traversal.
- [Phase 02]: Plan 02-27: Mobile wizard targets use literal 44px minimums and Playwright-native ARIA, keyboard, overflow, and 200% reflow verification.
- [Phase 02]: Treat the product current-candidate endpoint as the mapping query identity so a successful local version increment does not invalidate its own saved row.
- [Phase 02]: Resolve configured branches through one exact generated-client request per unique opaque value and merge them after listed API order without changing paged loaded counts.
- [Phase 02]: Bound automatic wizard revision-mapping restoration to 50 pages and fail closed on repeated cursors or page-limit exhaustion.

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 2 implementation must preserve the resolved A-01 product-name contract, A-02 preview encoding/shape matrix, A-03 operational bounds, and the explicit dependency-legitimacy checkpoints.
- Phase 3 must define import-grade capability checks and recovery behavior without silently expanding the Phase 2 read-only OAuth scope.
- Phase 7 must define the exact Qt `.ts` and other format-preserving edit contract while extending, not duplicating, the Phase 4 golden parser corpus.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260828-q9p | Center the Create product wizard and keep desktop step labels on one line | 2026-08-28 | 0ca9ac2 | [260828-q9p-centrare-il-wizard-create-product-e-mant](./quick/260828-q9p-centrare-il-wizard-create-product-e-mant/) |

### Roadmap Evolution

- Phase 7 edited: moved parser fixtures to Phase 4 and retained write-back fixtures
- Phase 4 edited: added complete golden parser fixtures and stable canonical identity
- Phase 3 edited: narrowed to import-grade capability validation, durable source references, and errors
- Phase 2 edited: expanded admin scope with organizational OAuth, read-only discovery, and preview

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Design context | Figma screen linkage | v2 | Initialization |
| Validation | Placeholder/plural/forbidden-character/line-count constraints | v2 | Initialization |
| Identity | External OAuth2/OIDC provider integration | v2 | Initialization |
| Workflow | Per-product approval gates | v2 | Initialization |
| Repository provider | Bitbucket Server/Data Center | v2 | Initialization |

## Session Continuity

Last session: 2026-08-29T20:44:34.995Z
Stopped at: Completed 02-32-PLAN.md
Resume file: None
