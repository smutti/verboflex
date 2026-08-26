# Phase 2: Admin Configuration — Specification

**Created:** 2026-08-26
**Ambiguity score:** 0.11 (gate: ≤ 0.20)
**Requirements:** 12 locked

## Goal

VerboFlex gains an administrator-only control plane that manages internal users, versioned product configuration, reusable Bitbucket Cloud repositories, one-format localization mappings, a single organizational OAuth connection, and live read-only validation previews without changing an active product until a complete candidate is explicitly published.

## Background

Phase 1 provides provider-independent `User`, `Role`, and `AuthSession` models, database-authoritative principals, OAuth2 bearer authentication for VerboFlex users, atomic CLI reset/deactivation authority, a Celery/Redis boundary, generated frontend API types, and a responsive authenticated shell. The only user HTTP resource is `/users/me`; no admin user API, product, repository, mapping, Bitbucket connection, discovery adapter, preview job, or admin configuration UI exists.

The original roadmap placed Bitbucket credentials and live reads in Phase 3 and canonical format parsing in Phase 4. The approved Phase 2 boundary pulls forward a minimal read-only slice: one organizational Bitbucket OAuth connection, repository/branch/source discovery, and preview-only detectors for Android XML, Qt `.ts`, JSON, and iOS `.strings`. Canonical imports, durable import baselines, stable translation identities, and write-back remain downstream.

## Requirements

1. **Administrator-only user management**: Only an authenticated active administrator can list, create, update, reset, deactivate, or reactivate internal users; all other principals receive a bounded denial without mutation.
   - Current: Phase 1 exposes only `/users/me`; bootstrap, reset, and deactivation are CLI-only authority seams.
   - Target: Paginated admin user resources expose the approved lifecycle operations and reuse database-authoritative role checks and atomic authority services.
   - Acceptance: Contract and integration tests prove admin success, non-admin and unauthenticated `401/403` denial, no denied mutation, deterministic list order, and normalized-email duplicate conflict.

2. **User and administrator invariants**: Administrative user mutations preserve immutable normalized corporate email, at least one fixed role per user, prohibition of self-removing `admin`, and at least one active administrator under concurrent requests.
   - Current: The model has normalized unique email and additive roles, but no HTTP mutation contract or transaction protecting the Phase 2 invariants.
   - Target: Display name, roles, and lifecycle are mutable only within the locked constraints; server-loaded database roles remain authoritative immediately after mutation.
   - Acceptance: Database-backed concurrent tests prove duplicate roles have set semantics, an empty role set is rejected, self-removal is rejected, and racing attempts cannot leave zero active administrators.

3. **One-time credential lifecycle**: User creation, administrative password reset, and reactivation generate a new temporary password, reveal it exactly once, require a password change, and revoke the affected user's prior authority atomically; deactivation remains reversible and immediately revokes authority.
   - Current: Phase 1 accepts a caller-supplied CLI password for bootstrap/reset and can deactivate, but does not generate or one-time reveal credentials and cannot reactivate.
   - Target: Backend-generated temporary credentials are returned only by the successful mutation response and never become recoverable; repeated or concurrent authority mutations leave only the latest committed credential/lifecycle state valid.
   - Acceptance: RED/GREEN tests prove one-time response exposure, password-policy compliance, no plaintext persistence/logging/later retrieval, `must_change_password=true`, token-version advancement, full session revocation, and rollback on failure.

4. **Versioned product lifecycle**: Administrators can create products and edit name, description, and active/inactive lifecycle through versioned candidate configuration while an active revision remains unchanged until atomic publication.
   - Current: No product or configuration-revision model exists.
   - Target: A product owns at most one active revision and a separately editable candidate; saving or validating a candidate never mutates active configuration, and deactivation suspends mappings without deleting them.
   - Acceptance: Integration tests prove create, candidate edit, explicit deactivate/reactivate, idempotent repeated save/publish, stale-write conflict, and atomic active-revision replacement.

5. **Organizational Bitbucket OAuth connection**: VerboFlex maintains exactly one organization-wide Bitbucket Cloud OAuth 2.0 connection for v1 with connect, reconnect, revoke, and bounded status operations.
   - Current: No Bitbucket client, OAuth callback, provider credential store, or connection-status API exists.
   - Target: Administrators can establish and replace the single connection; access and refresh credentials are encrypted at rest, backend-only, independently revocable, omitted from logs and API schemas, and unrelated to VerboFlex user authentication.
   - Acceptance: OAuth state/callback/reconnect/revoke tests prove state validation, safe repetition, atomic token rotation, immediate rejection after revoke, bounded status projection, and absence of provider secrets from OpenAPI, responses, browser state, persistence snapshots, and captured logs.

6. **Reusable repository registry**: Administrators can register reusable Bitbucket Cloud repositories uniquely by normalized `workspace + repository_slug` and reuse them across products without sharing product-specific mapping settings.
   - Current: No repository registry exists.
   - Target: A global repository stores canonical provider identity and an optional descriptive name; product-specific branches, topology, format, and preview state remain on mappings/revisions.
   - Acceptance: Migration and API tests prove normalized composite uniqueness under concurrent creation, rejection of blank identifiers, deterministic lists, reuse by two products, and isolation when either product changes its mapping.

7. **One-format localization mapping**: Each product mapping represents exactly one automatically detected localization format/layout, supports either `direct` or `separate` key-and-translation topology, and stores one source branch, one or more allowed target branches, and exactly one default target from that set.
   - Current: No mapping model or mapping validation exists.
   - Target: `direct` mappings use one repository side; `separate` mappings explicitly link key and translation repository sides. Administrators select from detected layouts but do not maintain globs, file lists, or language extraction templates.
   - Acceptance: Schema and service tests reject missing sides, extra sides, malformed or empty required target sets, default targets outside the normalized allowed set, duplicate mapping identity, mixed formats/layouts within one mapping, and branches absent from the live provider result. Duplicate allowed-target inputs normalize and collapse deterministically to one set member; the default must be a member after normalization, and repeating the identical normalized mapping configuration is a non-mutating no-op.

8. **Fixed PR grouping contract**: Pull-request behavior is fixed to group compatible future translation changes by repository and target branch.
   - Current: PROD-05 requires configurable PR behavior, but no option has been implemented or locked.
   - Target: Phase 2 records the single v1 rule: all compatible languages/files for the same repository/target pair share a group; a group never crosses either boundary, and a future submitter may choose only an allowed target.
   - Acceptance: Pure contract tests prove equal repository+target pairs group together regardless of language/file ordering, any repository or target difference splits groups, empty input produces no group, and repeated evaluation is stable.

9. **Live branch and localization preview**: An administrator can list live branches and start a bounded read-only preview that automatically detects Android XML, Qt `.ts`, JSON, or iOS `.strings` and returns detected files, format, language, sample keys, and sample translations.
   - Current: The worker boundary exists, but there is no Bitbucket source reader, branch resource, preview task, or format detector.
   - Target: Provider reads use the source commit selected by the job; safely bounded reads may complete synchronously and scans/parsing that can exceed an HTTP budget run as Celery jobs with queryable state. Multiple detected layouts become separate candidates, never one mixed mapping.
   - Acceptance: Provider-mock and fixture tests prove paginated branch discovery, all four format candidates, deterministic file/language/sample order, empty/unsupported/malformed/ambiguous outcomes, retry-safe job identity, and preview results bound to repository, branch, commit, candidate revision, and one detected layout.

10. **Fail-closed confirmation and publication**: A product can be activated or a candidate revision published only when every mapping has a current successful preview explicitly confirmed by an administrator.
    - Current: No product activation or validation authority exists.
    - Target: Empty, ambiguous, invalid, failed, stale, unconfirmed, or OAuth-disconnected preview state blocks activation/publication without changing the active revision; repeating publication of the already-active revision is a no-op.
    - Acceptance: Transactional tests prove all-mappings quantification, zero-mapping rejection, confirmation bound to exact preview digest/commit/revision, stale concurrent publication conflict, one-winner atomic publication, and preservation of the prior active revision on every failure.

11. **Guided admin experience**: The authenticated shell provides global user administration plus a guided product wizard and focused overview, repository, mapping, and preview sections with actionable validation and background-job states.
    - Current: `AppShell` contains a workspace placeholder and one dashboard navigation item.
    - Target: Admin routes are visible to administrators, render empty/loading/success/validation/error/conflict states, use the generated client and owned shadcn primitives, and never treat route visibility as authorization.
    - Acceptance: Component and Playwright tests cover direct navigation, responsive sidebar/Sheet navigation, empty collections, validation focus/announcements, one-time temporary-password display, preview polling, reconnect/retry, stale conflict, and preserved form state after recoverable errors.

12. **Read-only phase boundary and quality gate**: Phase 2 preview adapters produce no canonical translation import, durable import baseline, format-preserving write, source commit, or pull request; the phase closes only after targeted TDD, review, and build/deploy smoke verification pass.
    - Current: Phase 1 established quality tooling and background seams; the roadmap still assigns overlapping Bitbucket read and parser work to Phases 3 and 4.
    - Target: Phase 2 owns configuration-time OAuth/read/detection only; Phase 3 owns import-oriented capability validation, durable source references, resilience, and actionable operational errors; Phase 4 owns canonical parsing, translation identity, and complete format fixtures.
    - Acceptance: Architecture tests prove preview paths cannot write provider or canonical translation state, API work follows observable RED→GREEN evidence, and the phase evidence records targeted tests, code review, frontend/backend builds, migrations, worker smoke, and deploy smoke as passing.

## Boundaries

**In scope:**
- Admin-only HTTP APIs and UI for internal user lifecycle and multiple fixed roles.
- Backend-generated one-time temporary passwords for create/reset/reactivate.
- Product records with active and candidate configuration revisions.
- One global reusable repository registry and product-specific mappings.
- `direct` and `separate` mapping topologies, exactly one detected format/layout per mapping.
- One source branch, allowed target branches, and one default target per mapping.
- Fixed repository+target-branch PR grouping configuration.
- Exactly one organizational Bitbucket Cloud OAuth connection for v1.
- Live repository metadata, branch listing, source browsing, and read-only preview detection.
- Minimal preview adapters for Android XML, Qt `.ts`, JSON, and iOS `.strings`.
- Guided shadcn admin wizard/details and background preview states.
- TDD evidence, review, migration/build/worker/deploy smoke gates for the completed slice.

**Out of scope:**
- Microsoft Entra ID or any external identity provider for VerboFlex users — internal email/password authentication remains the v1 contract.
- Multiple named Bitbucket connections — v1 deliberately has one organizational connection.
- Administrator-authored globs, file lists, language templates, or mixed-format mappings — discovery is automatic and each mapping represents one format/layout.
- Canonical translation records, stable translation identity, durable import baselines, or import refresh — Phase 3/4 responsibilities.
- Full format-preserving parser/serializer implementations and golden write-back fixtures — later parser/write-back phases.
- Translation search, editing, constraints, review states, comments, and approval — Phases 5–6.
- Provider writes, source branch creation, commits, pull requests, or retry/idempotency for PR jobs — Phases 7–8.
- General audit-history implementation — PLAT-07 remains Phase 9, although Phase 2 entities retain ordinary creation/update metadata.
- Bitbucket Server/Data Center, Figma, advanced validation, machine translation, and complex approval gates — explicitly deferred project scope.

## Constraints

- Every HTTP API slice follows evidence-first TDD: first a focused failing test, then the minimum implementation, then a passing focused test before the next behavior.
- FastAPI/OpenAPI is canonical; the TypeScript client is regenerated rather than hand-maintained.
- PostgreSQL/SQLAlchemy/Alembic own durable state and concurrency invariants; Celery/Redis owns scans or parsing that are not safely bounded inside an HTTP request.
- Backend role checks are authoritative. UI visibility is only a projection of server-loaded roles.
- Temporary passwords and Bitbucket provider credentials are secrets: plaintext is never persisted, logged, included in OpenAPI examples, or returned after the one authorized response boundary.
- Phase 2 requests only Bitbucket OAuth scope `repository`, which the current official API requires for repository metadata, branch listing, and source browsing. Future source branch/commit writes require `repository:write`; future PR creation requires `pullrequest:write`, which currently implies `pullrequest` and `repository:write`. Phase 2 must not request future write, PR, admin, project, account, issue, wiki, or webhook scopes. Sources: [Bitbucket Cloud OAuth scopes](https://developer.atlassian.com/cloud/bitbucket/bitbucket-cloud-rest-api-scopes/), [refs API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-refs/), [source API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-source/), [pull requests API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pullrequests/).
- Changing the OAuth consumer's permission profile for later write/PR phases requires explicit reauthorization; an existing read-only token must never silently acquire new authority.
- A disconnected/expired Bitbucket connection does not mutate or deactivate the current active product revision; it blocks new preview confirmation and publication until reconnect succeeds.
- Phase 2 detectors are preview adapters, not canonical parsers. They may return bounded samples but must identify samples as partial and bind results to the source commit.

### Residual assumptions carried to planning

- **A-01 — Product names:** exact Unicode normalization, case sensitivity, and whether product display names are globally unique are unresolved. The planner must propose a falsifiable contract before the product API plan is approved. This is Edge R4/encoding.
- **A-02 — Preview encodings and JSON shapes:** the exact accepted encoding matrix and JSON localization shape conventions for minimal preview are unresolved. The planner/researcher must define supported fixtures and fail-closed unsupported behavior before detector tasks are approved. This is Edge R9/encoding.
- **A-03 — Operational bounds:** exact scan depth/file-size/file-count/time limits, preview sample count, confidence thresholds, polling cadence, pagination defaults, and user-facing copy are implementation decisions. Plans must choose explicit bounded values and tests without weakening fail-closed behavior.

## Acceptance Criteria

- [ ] Only active administrators can access or mutate Phase 2 admin resources; denied calls cause no durable or provider mutation.
- [ ] User lists are deterministic, duplicate normalized emails conflict, and zero-user/zero-role invalid states cannot be created.
- [ ] Corporate email is immutable; display name, roles, lifecycle, and password authority are the only approved administrative user changes.
- [ ] Every user retains at least one fixed role; administrators cannot remove their own admin role; concurrent mutations preserve at least one active administrator.
- [ ] Create/reset/reactivate returns one generated temporary password once, sets forced password change, and revokes all prior authority for that user atomically.
- [ ] Deactivation immediately revokes authority; reactivation is possible only with a newly generated temporary password.
- [ ] Product candidate edits never alter the active revision; publication is atomic and stale writers receive a bounded conflict.
- [ ] A product with zero mappings or any unconfirmed/invalid/stale mapping cannot be activated or published.
- [ ] Repositories are globally unique by normalized workspace+slug and can be reused without coupling product-specific configuration.
- [ ] Exactly one organizational Bitbucket OAuth connection can be connected, reconnected, revoked, and inspected through bounded status.
- [ ] Phase 2 OAuth authorization requests only `repository`; no future write/PR/admin scope is requested.
- [ ] OAuth provider credentials are encrypted/backend-only and absent from logs, OpenAPI, API responses, and browser state.
- [ ] Each mapping represents exactly one detected format/layout and has a valid direct or separate topology.
- [ ] Each mapping has exactly one source branch, at least one allowed target, and one default contained in the allowed set.
- [ ] No mapping accepts administrator-authored globs, file lists, or language extraction templates.
- [ ] PR grouping combines only equal repository+target pairs and never spans either boundary.
- [ ] Branch discovery follows Bitbucket pagination and exposes only bounded branch data required for selection.
- [ ] Preview fixtures cover Android XML, Qt `.ts`, JSON, and iOS `.strings`, including empty, malformed, unsupported, and ambiguous cases.
- [ ] Preview output is deterministically ordered, clearly labels samples as partial, and binds result/confirmation to repository, branch, commit, candidate revision, and layout.
- [ ] Repeated preview for identical input has stable identity/output and concurrent or stale jobs cannot replace a newer candidate's confirmation.
- [ ] OAuth failure or preview failure never mutates/deactivates the active product revision.
- [ ] Admin UI covers responsive navigation, empty/loading/success/error/conflict states, accessible validation, one-time password display, and preview job polling/retry.
- [ ] Preview paths perform no provider writes, canonical translation imports, durable import baselines, commits, or pull requests.
- [ ] Focused API behavior has preserved RED→GREEN TDD evidence before implementation advances.
- [ ] Targeted backend/frontend tests, migration checks, generated-client drift, code review, builds, worker smoke, and deploy smoke all pass.
- [ ] **MUST NOT** expose a temporary password after the successful create/reset/reactivate response or through persistence, logs, list/detail APIs, or later retrieval.
- [ ] **MUST NOT** mutate, deactivate, or replace the active product revision while saving, previewing, or failing a candidate revision.
- [ ] **MUST NOT** expose Bitbucket access tokens, refresh tokens, OAuth callback secrets, or client secrets to the SPA, OpenAPI, API payloads, or logs.
- [ ] **MUST NOT** propagate repository mapping, branch, layout, or preview changes between products that reuse the same global repository.
- [ ] **MUST NOT** silently choose among ambiguous layouts, combine multiple formats/layouts into one mapping, or treat unsupported content as valid.
- [ ] **MUST NOT** group future changes across repository or target-branch boundaries.
- [ ] **MUST NOT** present bounded samples as an exhaustive repository inventory; the UI/API must identify sampling and detection status.
- [ ] **MUST NOT** publish when any mapping preview is absent, stale, ambiguous, invalid, disconnected, or unconfirmed.
- [ ] **MUST NOT** let Phase 2 preview paths write provider source, canonical translation state, commits, branches, or pull requests.

## Edge Coverage

**Coverage:** 52/54 applicable edges closed · 2 unresolved · 47 explicit · 5 dismissed · 0 backstop

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | Duplicate normalized email is a conflict; user rows never merge. |
| empty | R1 | ✅ covered | Empty result is a valid list response, but mutations cannot create a zero-admin authority state. |
| ordering | R1 | ✅ covered | User lists use deterministic normalized-email order with UUID tie-break. |
| idempotency | R1 | ✅ covered | Repeated identical update is a no-op; repeated create conflicts without mutation. |
| concurrency | R1 | ✅ covered | Uniqueness and administrator authority changes are transactionally serialized. |
| adjacency | R2 | ✅ covered | Duplicate role names have set semantics and cannot add duplicate authority. |
| empty | R2 | ✅ covered | Zero assigned roles is rejected. |
| encoding | R2 | ✅ covered | Email reuses Phase 1 ASCII-trim/lower normalization; role names are fixed ASCII enums. |
| ordering | R2 | ✅ covered | Roles are projected in stable enum order. |
| idempotency | R2 | ✅ covered | Identical role/display update is non-mutating; an authority change advances revocation state once. |
| concurrency | R2 | ✅ covered | Races cannot remove the last active admin or bypass self-protection. |
| idempotency | R3 | ✅ covered | Every repeated reset/reactivation issues a fresh secret and invalidates every earlier one. |
| concurrency | R3 | ✅ covered | Same-user authority mutations serialize; only the final committed state remains valid. |
| empty | R4 | ✅ covered | Product name is required; description may be empty. |
| encoding | R4 | ⚠ UNRESOLVED | Exact Unicode normalization, case sensitivity, and global uniqueness of product names remain A-01. |
| idempotency | R4 | ✅ covered | Identical candidate save/publish does not create another effective revision. |
| concurrency | R4 | ✅ covered | Revision comparison yields one atomic winner and bounded stale conflicts. |
| idempotency | R5 | ✅ covered | Repeated callback/revoke/reconnect is safe and never resurrects superseded tokens. |
| concurrency | R5 | ✅ covered | Token rotation and revocation serialize; revoked generations are rejected. |
| adjacency | R6 | ✅ covered | Equal normalized workspace+slug denotes one repository; duplicates conflict. |
| empty | R6 | ✅ covered | Blank workspace or slug is rejected. |
| encoding | R6 | ✅ covered | Provider identifiers are ASCII-trimmed/lowercased and verified against Bitbucket canonical identity. |
| ordering | R6 | ✅ covered | Repository lists sort by descriptive name fallback then workspace/slug. |
| idempotency | R6 | ✅ covered | Repeated registration cannot create another row. |
| concurrency | R6 | ✅ covered | Database composite uniqueness closes racing registrations. |
| adjacency | R7 | ✅ covered | Duplicate allowed-target inputs normalize and collapse deterministically to one set member; the default must belong to that normalized set, while duplicate mapping identity is rejected. |
| empty | R7 | ✅ covered | Missing required repository side or target set is rejected. |
| encoding | R7 | ✅ covered | Provider branch names remain exact opaque provider values; format/topology are fixed enums. |
| ordering | R7 | ⛔ dismissed | Allowed targets are a set and default is explicit; input order has no semantic meaning. |
| idempotency | R7 | ✅ covered | Repeating the identical normalized mapping configuration is a non-mutating no-op. |
| concurrency | R7 | ✅ covered | Candidate revision conflicts prevent silent last-writer overwrite. |
| adjacency | R8 | ✅ covered | Exact repository+target equality joins; either difference splits. |
| empty | R8 | ✅ covered | Empty future change input produces no group. |
| ordering | R8 | ⛔ dismissed | Language/file order cannot alter group identity. |
| idempotency | R8 | ✅ covered | Repeated grouping over the same identities is stable. |
| concurrency | R8 | ⛔ dismissed | Phase 2 stores the grouping contract but executes no PR jobs; Phase 8 owns concurrent submission. |
| adjacency | R9 | ✅ covered | Multiple detected layouts stay separate candidates; collisions are ambiguous and fail closed. |
| empty | R9 | ✅ covered | No supported localization candidate is a blocking preview result. |
| encoding | R9 | ⚠ UNRESOLVED | Exact supported file encodings and JSON shapes remain A-02. |
| ordering | R9 | ✅ covered | Files, languages, and samples have deterministic order. |
| idempotency | R9 | ✅ covered | Same commit+revision+layout has stable preview identity and output. |
| concurrency | R9 | ✅ covered | Jobs bind commit/revision; stale completion cannot confirm a newer candidate. |
| adjacency | R10 | ✅ covered | Publication requires every mapping, never a valid subset. |
| empty | R10 | ✅ covered | Zero mappings cannot activate or publish. |
| ordering | R10 | ⛔ dismissed | All-mappings validity is order-independent. |
| idempotency | R10 | ✅ covered | Re-publishing the active revision is a no-op. |
| concurrency | R10 | ✅ covered | Compare-and-publish produces one atomic winner. |
| adjacency | R11 | ⛔ dismissed | UI sections are independent routes/panels and have no merge/touch semantics. |
| empty | R11 | ✅ covered | User, product, repository, mapping, and preview collections have explicit empty states. |
| ordering | R11 | ✅ covered | Admin lists reflect their resource's deterministic API order. |
| idempotency | R11 | ✅ covered | Repeated submission is visibly pending and delegates mutation semantics to the API. |
| concurrency | R11 | ✅ covered | Stale conflict is shown without overwriting the user's recoverable form state. |
| idempotency | R12 | ✅ covered | Repeating preview/quality checks cannot create provider or canonical writes. |
| concurrency | R12 | ✅ covered | Concurrent preview paths remain read-only and revision-bound. |

## Prohibitions (must-NOT)

**Coverage:** 9/9 applicable prohibitions resolved · 0 unresolved · 9 test · 0 judgment

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT expose a temporary password outside its single successful lifecycle response. | R3 | resolved | verification: test; descriptor deferred until the negative contract test exists. |
| MUST NOT mutate or deactivate the active revision through candidate save/preview/failure. | R4, R10 | resolved | verification: test; transactional negative integration test. |
| MUST NOT expose Bitbucket OAuth credentials or callback secrets outside the backend authority boundary. | R5 | resolved | verification: test; OpenAPI/response/log/browser/persistence scan. |
| MUST NOT couple product-specific mapping state merely because products share a repository. | R6, R7 | resolved | verification: test; two-product isolation integration test. |
| MUST NOT silently guess ambiguity or combine formats/layouts into one mapping. | R7, R9 | resolved | verification: test; ambiguous and mixed fixtures remain blocking. |
| MUST NOT group changes across repository or target-branch boundaries. | R8 | resolved | verification: test; grouping property test. |
| MUST NOT present bounded preview samples as exhaustive repository content. | R9, R11 | resolved | verification: test; response metadata and visible UI label. |
| MUST NOT publish with an absent, stale, invalid, disconnected, or unconfirmed preview. | R10 | resolved | verification: test; negative publication matrix. |
| MUST NOT write provider source or canonical translation/import/PR state from a Phase 2 preview path. | R12 | resolved | verification: test; architecture boundary and provider-spy tests. |

Canon referral: generic injection, XSS/CSRF, OAuth cryptography, GDPR retention, and generic secret-management controls remain owned by `$gsd-secure-phase` and the established security toolchain; they are not duplicated as bespoke Phase 2 prohibitions.

## Ambiguity Report

| Dimension | Score | Min | Status | Notes |
|-----------|-------|-----|--------|-------|
| Goal Clarity | 0.94 | 0.75 | ✓ | Administrative outcome and active/candidate behavior are measurable. |
| Boundary Clarity | 0.93 | 0.70 | ✓ | Phase 2–4 ownership and explicit exclusions are locked. |
| Constraint Clarity | 0.83 | 0.65 | ✓ | OAuth scopes and core invariants are exact; A-01–A-03 remain visible. |
| Acceptance Criteria | 0.82 | 0.70 | ✓ | Positive, negative, edge, TDD, and smoke gates are pass/fail. |
| **Ambiguity** | **0.11** | **≤0.20** | **✓** | Gate passed; two unresolved edges are planner assumptions, not hidden decisions. |

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| Pre-spec | Researcher / Boundary Keeper / Failure Analyst | User lifecycle, mapping topology, activation, revisions, preview, UX, and Bitbucket authentication | D-01 through D-23 in `02-CONTEXT.md` are adopted as input evidence. |
| 1 | Researcher / Boundary Keeper | One or multiple OAuth connections? | Exactly one organization-wide Bitbucket OAuth connection for v1. |
| 1 | Boundary Keeper | Can one mapping contain multiple detected formats/layouts? | No; each mapping represents exactly one format/layout, while one repository may yield multiple candidate mappings. |
| 1 | Boundary Keeper | Where is the Phase 2–4 cut after pulling live preview forward? | Phase 2 owns OAuth/live read/minimal preview; Phase 3 owns import-grade integration/baselines/errors; Phase 4 owns canonical parsing/identity/fixtures. |
| Gate | Seed Closer | Write now or continue interviewing? | Write now and flag residual assumptions explicitly. |

---

*Phase: 02-admin-configuration*
*Spec created: 2026-08-26*
*Next step: reconcile ROADMAP/REQUIREMENTS, then run `$gsd-plan-phase 2` because implementation context is already captured in `02-CONTEXT.md`.*
