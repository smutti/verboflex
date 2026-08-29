# Roadmap: VerboFlex

## Overview

VerboFlex v1 builds the repository-backed localization workflow from the foundation upward: first the separated frontend/backend platform and data model, then admin configuration with read-only Bitbucket discovery, import-grade Bitbucket integration, canonical parser/import support, search and review workflows, safe write-back, pull request automation, and final hardening. The roadmap keeps Bitbucket Cloud as the source of truth while giving product managers a dense shadcn/ui-based portal for finding, reviewing, commenting on, approving, and submitting translation changes. Every phase closes with a quality gate covering targeted tests, code review, and deploy/build smoke verification for the current app slice.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Platform Foundation** - Establish separated frontend/backend apps, OAuth2 base, Postgres/Alembic schema, Redis/Celery, and shadcn/ui. (completed 2026-08-26)
- [ ] **Phase 2: Admin Configuration** - Build the admin control plane, organizational Bitbucket OAuth connection, live repository discovery, and read-only localization preview.
- [ ] **Phase 3: Bitbucket Import Integration** - Harden Bitbucket access for imports with capability validation, durable source references, resilience, and actionable errors.
- [ ] **Phase 4: Localization Parser Foundation** - Parse Android XML, Qt `.ts`, JSON, and iOS `.strings` into canonical translation records verified by complete golden fixtures.
- [ ] **Phase 5: Import, Search, and Constraints** - Import translations, preserve review context, expose search/filter APIs, and calculate max-length violations.
- [ ] **Phase 6: Review Workspace and Comments** - Deliver the task-focused translation review UI with editing, state changes, comments, and pending-change visibility.
- [ ] **Phase 7: Format-Safe Write-Back** - Prove file-location metadata, stale-source detection, and format-preserving writer behavior before PR automation.
- [ ] **Phase 8: Change Sets and Pull Requests** - Submit grouped changes through Celery jobs that create Bitbucket branches, commits, and pull requests.
- [ ] **Phase 9: Verification and Hardening** - Audit role enforcement, mutation audit metadata, UI permissions, error handling, and end-to-end readiness.

## Per-Phase Quality Gate

Every phase must complete these checks before it can be marked complete:

1. **Tests added or updated:** Unit, integration, parser fixture, API, frontend, or E2E tests appropriate to the phase scope.
2. **Code review completed:** Review changed backend, frontend, worker, migration, and test code for correctness, security, maintainability, and missing coverage.
3. **Deploy/build verification completed:** Verify the current app slice builds and starts in the closest available deployment-like path, such as Docker Compose, local production build, or staging deployment.
4. **Smoke check documented:** Record the commands/results or manual smoke checks used to verify the phase.
5. **Blocking findings resolved:** Fix critical review, test, security, or deploy failures before moving to the next phase.
6. **Fresh closeout authority:** Keep the phase incomplete until its newest code review records zero unresolved Critical findings and its newest independent verifier frontmatter is exactly `status: passed`; both must bind to the same post-gauntlet source digest.

## Phase Details

### Phase 1: Platform Foundation

**Goal**: Establish the separated application architecture and base infrastructure for all later work.
**Depends on**: Nothing (first phase)
**Requirements**: [PLAT-01, PLAT-02, PLAT-03, PLAT-04, PLAT-05, PLAT-06, AUTH-01, AUTH-04, UI-01]
**UI hint**: yes
**Success Criteria** (what must be TRUE):

  1. Developer can run separate `frontend` and `backend` applications locally.
  2. Backend exposes FastAPI health scaffolding, internal email/password OAuth2 authentication, first-admin CLI bootstrap, and PostgreSQL connectivity through SQLAlchemy.
  3. Alembic can create and upgrade the initial schema.
  4. Redis and Celery can execute a sample background job.
  5. Frontend uses React/Vite/TypeScript with shadcn/ui primitives available.
  6. Phase quality gate passes with tests, code review, and deploy/build smoke verification.

**Plans**: 15/15 plans executed

Plans:

- [x] 01-01-PLAN.md — Blocking backend/frontend package-legitimacy approvals
- [x] 01-02-PLAN.md — Locked FastAPI scaffold, callable endpoint stubs, and health
- [x] 01-03-PLAN.md — Locked Vite scaffold and generated health tracer
- [x] 01-04-PLAN.md — Secure settings and local/staging/production-oriented Docker baseline
- [x] 01-05-PLAN.md — Reversible auth schema, exact roles, and first-admin/reset CLI
- [x] 01-06-PLAN.md — OAuth2 login, access tokens, current identity, and backend roles
- [x] 01-07-PLAN.md — Refresh rotation/replay, logout, password change, and revocation
- [x] 01-08-PLAN.md — Rate limits, bounded service status, and Celery/Redis execution
- [x] 01-09-PLAN.md — Full generated OpenAPI contract and memory-only session state
- [x] 01-10-PLAN.md — Enumerated approved shadcn owned components
- [x] 01-11-PLAN.md — Exact Phase 1 theme tokens and drift test
- [x] 01-12-PLAN.md — Login/change-password routing and forms through TDD
- [x] 01-13-PLAN.md — Neutral dashboard, service status, responsive shell, and E2E
- [x] 01-14-PLAN.md — Fail-closed gauntlet/smoke plus fresh-context code and ASVS L1 review gate
- [x] 01-15-PLAN.md — Final immutable-source gauntlet, evidence, and independent-verifier handoff

### Phase 2: Admin Configuration

**Goal**: Deliver an administrator-only control plane for internal users, versioned products, reusable repositories, one-format mappings, a single organizational Bitbucket OAuth connection, and live read-only validation previews.
**Depends on**: Phase 1
**Requirements**: [AUTH-02, AUTH-03, PROD-01, PROD-02, PROD-03, PROD-04, PROD-05, PROD-06, PROD-07, PROD-08, PROD-09, BITB-01, BITB-03, BITB-04, UI-03]
**UI hint**: yes
**Success Criteria** (what must be TRUE):

  1. Admin can manage the complete reversible internal-user lifecycle with multiple roles, one-time temporary credentials, and last-active-admin invariants.
  2. Admin can create products whose candidate configuration remains isolated from the active revision until explicit atomic publication.
  3. Admin can reuse globally unique Bitbucket Cloud repositories while keeping product-specific branches, mappings, and preview state isolated.
  4. One organization-wide Bitbucket OAuth connection uses read-only `repository` scope to list branches and read source content for configuration preview.
  5. Each direct or separate mapping represents exactly one detected format/layout, one source branch, allowed targets, a default target, and the fixed repository+target PR grouping rule.
  6. Preview detects Android XML, Qt `.ts`, JSON, and iOS `.strings`, surfaces bounded samples, and fails closed on empty, invalid, ambiguous, stale, or disconnected state.
  7. Guided shadcn admin screens provide actionable user, repository, mapping, OAuth, validation, and background-job states.
  8. Phase quality gate passes with RED→GREEN TDD evidence, code review, and backend/frontend/worker/deploy smoke verification.

**Plans**: 34/38 plans executed (20 original plans, 14/18 gap-closure plans executed)

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Internal-user and additive-role administration

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Product identity, immutable revisions, and candidate APIs

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-03-PLAN.md — Global reusable repository registry and APIs

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 02-04-PLAN.md — Encrypted organizational OAuth connection foundation

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 02-05-PLAN.md — OAuth refresh, reconnect, local revoke, and API lifecycle

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 02-06-PLAN.md — Generation-bound read-only Bitbucket HTTP adapter

**Wave 7** *(blocked on Wave 6 completion)*

- [x] 02-07-PLAN.md — Live branch, commit, tree, and raw-source discovery

**Wave 8** *(blocked on Wave 7 completion)*

- [x] 02-08-PLAN.md — Direct revision-owned mapping persistence and APIs

**Wave 9** *(blocked on Wave 8 completion)*

- [x] 02-09-PLAN.md — Separate topology and fixed repository-target grouping

**Wave 10** *(blocked on Wave 9 completion)*

- [x] 02-10-PLAN.md — Atomic product publication lifecycle

**Wave 11** *(blocked on Wave 10 completion)*

- [x] 02-11-PLAN.md — Durable PostgreSQL/Celery preview-job boundary

**Wave 12** *(blocked on Wave 11 completion)*

- [x] 02-12-PLAN.md — Strict Android XML preview detector

**Wave 13** *(blocked on Wave 12 completion)*

- [x] 02-13-PLAN.md — Strict Qt TS, JSON, and iOS strings detectors

**Wave 14** *(blocked on Wave 13 completion)*

- [x] 02-14-PLAN.md — Stale-safe confirmation and publication integration

**Wave 15** *(blocked on Wave 14 completion)*

- [x] 02-15-PLAN.md — Canonical generated TypeScript admin client

**Wave 16** *(blocked on Wave 15 completion)*

- [x] 02-16-PLAN.md — Responsive guarded administrator routing and shell

**Wave 17** *(blocked on Wave 16 completion)*

- [x] 02-17-PLAN.md — Secret-safe internal-user administration UI

**Wave 18** *(blocked on Wave 17 completion)*

- [x] 02-18-PLAN.md — Product, repository, and mapping administration UI

**Wave 19** *(blocked on Wave 18 completion)*

- [x] 02-19-PLAN.md — OAuth, preview, publication, and responsive E2E UI

**Wave 20** *(blocked on Wave 19 completion)*

- [x] 02-20-PLAN.md — Phase quality gate, review, mutations, and deploy smoke

**Wave 21** *(gap closure; blocked on Wave 20 completion)*

- [x] 02-21-PLAN.md — Access-only credential migration, production client-credentials grant, expiry recovery, and bounded API status
- [x] 02-23-PLAN.md — CLI last-active-admin authority and role-identity invariant

**Wave 22** *(gap closure; blocked on Wave 21 completion)*

- [x] 02-22-PLAN.md — Generated OAuth client and secret-free administrator recovery UI
- [x] 02-24-PLAN.md — Product graph ownership and published-child database immutability
- [x] 02-35-PLAN.md — Repository-scoped live-provider smoke and lossless API coverage reconciliation

**Wave 23** *(gap closure; blocked on Wave 22 completion)*

- [x] 02-25-PLAN.md — Complete active-to-candidate clone and atomic identity publication
- [x] 02-26-PLAN.md — Revision-scoped mapping reads and exact query-encoded branch resolution
- [x] 02-36-PLAN.md — Preview watchdog state/started-at index migration and query-plan proof

**Wave 24** *(gap closure; blocked on Wave 23 completion)*

- [x] 02-29-PLAN.md — Bounded durable preview worker-loss and hard-timeout recovery using PreviewJob.id
- [x] 02-31-PLAN.md — Canonical OpenAPI and generated-client contracts for revision mappings and exact branches

**Wave 25** *(gap closure; blocked on Wave 24 completion)*

- [x] 02-27-PLAN.md — Routed published-product editing and complete five-step mobile wizard

**Wave 26** *(gap closure; blocked on Wave 25 completion)*

- [x] 02-28-PLAN.md — Dependency-free repository, mapping, and exact-branch cursor accumulation
- [x] 02-32-PLAN.md — Exact unchanged-active-revision product reactivation

**Wave 27** *(gap closure; blocked on Wave 26 completion)*

- [x] 02-33-PLAN.md — Role-aware Workspace overview with zero non-admin administrator requests

**Wave 28** *(gap closure; blocked on Wave 27 completion)*

- [ ] 02-34-PLAN.md — Complete preview pagination and mapping-51 lifecycle gating

**Wave 29** *(gap closure traceability; blocked on Waves 21-28 completion)*

- [ ] 02-30-PLAN.md — Literal multi-source semantic traceability and deterministic coverage-audit contracts

**Wave 30** *(gap closure runtime gate; blocked on Wave 29 completion)*

- [ ] 02-37-PLAN.md — Full architecture, E2E, Compose, worker-loss, security, and unchanged-source gauntlet expansion

**Wave 31** *(gap closure final authority; blocked on every Plan 02-21 through 02-37)*

- [ ] 02-38-PLAN.md — Fresh critical-zero ASVS L1 review and independent `status: passed` verifier closeout

### Phase 3: Bitbucket Import Integration

**Goal**: Turn the Phase 2 read-only Bitbucket boundary into an import-grade integration with capability validation, durable source references, resilient reads, and actionable operational errors.
**Depends on**: Phase 2
**Requirements**: [BITB-02, BITB-05, BITB-06]
**UI hint**: yes
**Success Criteria** (what must be TRUE):

  1. System validates the capabilities required by configured read/import operations and reports the later write/PR capability profile without silently expanding OAuth scopes.
  2. Import-oriented reads use bounded retry, pagination, rate-limit, and provider-error handling on top of the Phase 2 OAuth/source boundary.
  3. System stores the exact source commit hash and file reference used by each import attempt.
  4. Admin receives actionable, sanitized connection, permission, rate-limit, missing-source, and import errors with safe retry guidance.
  5. Phase quality gate passes with integration tests, code review, and backend/worker/deploy smoke verification.

**Plans**: 4 plans

Plans:

- [ ] 03-01: Import-grade capability validation and resilient Bitbucket client
- [ ] 03-02: Durable source commit/file references and import baselines
- [ ] 03-03: Actionable admin errors, recovery, and retry behavior
- [ ] 03-04: Phase quality gate - integration tests, code review, and deploy/build verification

### Phase 4: Localization Parser Foundation

**Goal**: Convert supported localization files into stable canonical translation records and prove all four parser contracts with complete golden fixtures.
**Depends on**: Phase 3
**Requirements**: [FMT-01, FMT-02, FMT-03, FMT-04, FMT-06, FMT-07]
**UI hint**: no
**Success Criteria** (what must be TRUE):

  1. System parses Android XML strings into canonical records.
  2. System parses Qt `.ts` translations into canonical records.
  3. System parses JSON localization files into canonical records.
  4. System parses iOS `.strings` files into canonical records.
  5. Canonical records include product, repository, branch, file path, format, stable key identity, language, text, state, and locator metadata.
  6. Complete golden fixtures cover valid, empty, malformed, escaped, Unicode, and format-specific boundary cases for every supported parser.
  7. Phase quality gate passes with parser tests, code review, and backend deploy/build smoke verification.

**Plans**: 7 plans

Plans:

- [ ] 04-01: Canonical translation model and adapter interfaces
- [ ] 04-02: Android XML parser
- [ ] 04-03: Qt `.ts` parser
- [ ] 04-04: JSON parser
- [ ] 04-05: iOS `.strings` parser
- [ ] 04-06: Cross-format golden fixtures and canonical conformance
- [ ] 04-07: Phase quality gate - parser tests, code review, and deploy/build verification

### Phase 5: Import, Search, and Constraints

**Goal**: Import translations into searchable records while preserving review context and calculating max-length violations.
**Depends on**: Phase 4
**Requirements**: [FMT-08, SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, SRCH-07, SRCH-08, CONS-01, CONS-02, CONS-03, CONS-04, CONS-05]
**UI hint**: yes
**Success Criteria** (what must be TRUE):

  1. Celery import jobs can refresh Bitbucket translations without losing stable review context.
  2. Product managers can search/filter by product, language, key/text, approval state, and violation status.
  3. User can open a translation detail view with repository/file/branch context.
  4. Authorized user can create, edit, and remove max-length constraints.
  5. System recalculates and displays length violations after imports and edits.
  6. Phase quality gate passes with tests, code review, and deploy/build smoke verification.

**Plans**: 6 plans

Plans:

- [ ] 05-01: Import job orchestration and canonical upserts
- [ ] 05-02: Search/filter API and indexed queries
- [ ] 05-03: Translation detail API and frontend navigation
- [ ] 05-04: Max-length constraint model and violation calculation
- [ ] 05-05: Search/review list UX with pagination or virtualization
- [ ] 05-06: Phase quality gate - tests, code review, and deploy/build verification

### Phase 6: Review Workspace and Comments

**Goal**: Provide the core review workspace where authorized users edit, comment, and move translations through simple states.
**Depends on**: Phase 5
**Requirements**: [REVW-01, REVW-02, REVW-03, REVW-04, REVW-05, REVW-06, REVW-07, REVW-08, COMM-01, COMM-02, COMM-03, COMM-04, COMM-05, UI-02]
**UI hint**: yes
**Success Criteria** (what must be TRUE):

  1. Authorized user can edit translation text and see it as a pending unsent change.
  2. Authorized user can mark translations draft, approved, or rejected.
  3. System records review state-change history with actor and timestamp.
  4. Authorized user can add and view per-translation comments that persist across workflow actions.
  5. Viewer-only user cannot edit translations or change review state.
  6. Phase quality gate passes with tests, code review, and deploy/build smoke verification.

**Plans**: 6 plans

Plans:

- [ ] 06-01: Pending translation changes and edit workflow
- [ ] 06-02: Draft/approved/rejected state transitions and audit history
- [ ] 06-03: Translation comments model, API, and persistence
- [ ] 06-04: Permission-aware review workspace actions
- [ ] 06-05: Dense shadcn/ui review workspace polish
- [ ] 06-06: Phase quality gate - tests, code review, and deploy/build verification

### Phase 7: Format-Safe Write-Back

**Goal**: Make file write-back safe enough to trust before creating Bitbucket pull requests.
**Depends on**: Phase 6
**Requirements**: [FMT-05, PR-04]
**UI hint**: no
**Success Criteria** (what must be TRUE):

  1. System preserves file location metadata needed to write changed translations back to original files.
  2. Writer fixtures extend the Phase 4 parser corpus to verify format-preserving edits for Android XML, Qt `.ts`, JSON, and iOS `.strings`.
  3. System detects source branch or file changes since import before writing.
  4. Writer output avoids broad unrelated diffs for simple translation edits.
  5. Stale source state blocks write-back with an actionable error.
  6. Phase quality gate passes with writer tests, code review, and deploy/build smoke verification.

**Plans**: 5 plans

Plans:

- [ ] 07-01: File locator metadata and raw snapshot strategy
- [ ] 07-02: Writer adapters and golden fixtures
- [ ] 07-03: Stale branch/file detection
- [ ] 07-04: Diff review and write-back safety tests
- [ ] 07-05: Phase quality gate - writer tests, code review, and deploy/build verification

### Phase 8: Change Sets and Pull Requests

**Goal**: Submit reviewed translation changes through Bitbucket Cloud branches, commits, and pull requests.
**Depends on**: Phase 7
**Requirements**: [PR-01, PR-02, PR-03, PR-05, PR-06, PR-07, PR-08, PR-09, PR-10, PR-11, UI-04]
**UI hint**: yes
**Success Criteria** (what must be TRUE):

  1. Authorized user can select pending translation changes for submission.
  2. System groups changes according to product PR configuration and selected target branch rules.
  3. Celery job creates or updates a Bitbucket branch, writes files, creates a commit, and opens a pull request.
  4. User can see PR URL, id, branch, commit hash, included translations, status, and errors.
  5. Failed PR submission jobs can be retried without duplicate change sets.
  6. Phase quality gate passes with tests, code review, and deploy/build smoke verification.

**Plans**: 6 plans

Plans:

- [ ] 08-01: Change-set selection and grouping
- [ ] 08-02: Target branch selection and submission validation
- [ ] 08-03: Bitbucket branch and commit job
- [ ] 08-04: Pull request creation and audit records
- [ ] 08-05: Job status UI, errors, and idempotent retry
- [ ] 08-06: Phase quality gate - tests, code review, and deploy/build verification

### Phase 9: Verification and Hardening

**Goal**: Verify the whole v1 workflow and close security, audit, authorization, and operational gaps.
**Depends on**: Phase 8
**Requirements**: [PLAT-07, AUTH-05, AUTH-06]
**UI hint**: yes
**Success Criteria** (what must be TRUE):

  1. System records audit metadata for key mutations across configuration, review, comments, and PR submission.
  2. Backend enforces role-based authorization on all mutating APIs.
  3. Frontend hides or disables unauthorized actions consistently.
  4. End-to-end flow works from product setup through import, review, comment, approval, change set, and Bitbucket PR.
  5. Common permission, stale-source, parser, and Bitbucket failure cases are covered by tests or manual verification notes.
  6. Final quality gate confirms code review, tests, and deploy verification for the full v1 app.

**Plans**: 5 plans

Plans:

- [ ] 09-01: Audit metadata completion
- [ ] 09-02: Backend authorization audit and security tests
- [ ] 09-03: Frontend permission and UX hardening
- [ ] 09-04: End-to-end verification and release readiness
- [ ] 09-05: Final quality gate - code review, tests, and deploy verification

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Platform Foundation | 15/15 | Complete    | 2026-08-26 |
| 2. Admin Configuration | 34/38 | In Progress|  |
| 3. Bitbucket Import Integration | 0/4 | Not started | - |
| 4. Localization Parser Foundation | 0/7 | Not started | - |
| 5. Import, Search, and Constraints | 0/6 | Not started | - |
| 6. Review Workspace and Comments | 0/6 | Not started | - |
| 7. Format-Safe Write-Back | 0/5 | Not started | - |
| 8. Change Sets and Pull Requests | 0/6 | Not started | - |
| 9. Verification and Hardening | 0/5 | Not started | - |
