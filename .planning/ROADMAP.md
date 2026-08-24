# Roadmap: VerboFlex

## Overview

VerboFlex v1 builds the repository-backed localization workflow from the foundation upward: first the separated frontend/backend platform and data model, then admin configuration, Bitbucket read integration, parser/import support, search and review workflows, safe write-back, pull request automation, and final hardening. The roadmap keeps Bitbucket Cloud as the source of truth while giving product managers a dense shadcn/ui-based portal for finding, reviewing, commenting on, approving, and submitting translation changes. Every phase closes with a quality gate covering targeted tests, code review, and deploy/build smoke verification for the current app slice.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Platform Foundation** - Establish separated frontend/backend apps, OAuth2 base, Postgres/Alembic schema, Redis/Celery, and shadcn/ui.
- [ ] **Phase 2: Admin Configuration** - Build internal user, role, product, repository, branch, mapping, and PR behavior configuration.
- [ ] **Phase 3: Bitbucket Read Integration** - Connect to Bitbucket Cloud, validate permissions, list branches, read configured files, and record import baselines.
- [ ] **Phase 4: Localization Parser Foundation** - Parse Android XML, Qt `.ts`, JSON, and iOS `.strings` into canonical translation records.
- [ ] **Phase 5: Import, Search, and Constraints** - Import translations, preserve review context, expose search/filter APIs, and calculate max-length violations.
- [ ] **Phase 6: Review Workspace and Comments** - Deliver the task-focused translation review UI with editing, state changes, comments, and pending-change visibility.
- [ ] **Phase 7: Format-Safe Write-Back** - Prove file-location metadata, golden fixtures, stale-source detection, and safe writer behavior before PR automation.
- [ ] **Phase 8: Change Sets and Pull Requests** - Submit grouped changes through Celery jobs that create Bitbucket branches, commits, and pull requests.
- [ ] **Phase 9: Verification and Hardening** - Audit role enforcement, mutation audit metadata, UI permissions, error handling, and end-to-end readiness.

## Per-Phase Quality Gate

Every phase must complete these checks before it can be marked complete:

1. **Tests added or updated:** Unit, integration, parser fixture, API, frontend, or E2E tests appropriate to the phase scope.
2. **Code review completed:** Review changed backend, frontend, worker, migration, and test code for correctness, security, maintainability, and missing coverage.
3. **Deploy/build verification completed:** Verify the current app slice builds and starts in the closest available deployment-like path, such as Docker Compose, local production build, or staging deployment.
4. **Smoke check documented:** Record the commands/results or manual smoke checks used to verify the phase.
5. **Blocking findings resolved:** Fix critical review, test, security, or deploy failures before moving to the next phase.

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

**Plans**: 10/15 plans executed

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
- [ ] 01-11-PLAN.md — Exact Phase 1 theme tokens and drift test
- [ ] 01-12-PLAN.md — Login/change-password routing and forms through TDD
- [ ] 01-13-PLAN.md — Neutral dashboard, service status, responsive shell, and E2E
- [ ] 01-14-PLAN.md — Fail-closed gauntlet/smoke plus fresh-context code and ASVS L1 review gate
- [ ] 01-15-PLAN.md — Final immutable-source gauntlet, evidence, and independent-verifier handoff

### Phase 2: Admin Configuration

**Goal**: Let admins configure users, roles, products, Bitbucket repositories, branches, localization layouts, and PR behavior.
**Depends on**: Phase 1
**Requirements**: [AUTH-02, AUTH-03, PROD-01, PROD-02, PROD-03, PROD-04, PROD-05, PROD-06, PROD-07, PROD-08, PROD-09, UI-03]
**UI hint**: yes
**Success Criteria** (what must be TRUE):

  1. Admin can manage internal users and assign multiple roles.
  2. Admin can create products and configure one or more Bitbucket Cloud repositories.
  3. Admin can configure source branches, allowed target branches, localization formats, and PR grouping behavior.
  4. Admin can define direct-repository and cross-repository key/translation mappings.
  5. Admin sees validation feedback and mapping previews before enabling imports.
  6. Phase quality gate passes with tests, code review, and deploy/build smoke verification.

**Plans**: 6 plans

Plans:

- [ ] 02-01: User and role administration
- [ ] 02-02: Product and repository configuration model/API
- [ ] 02-03: Branch, format, and PR behavior configuration
- [ ] 02-04: Cross-repository mapping configuration and validation preview
- [ ] 02-05: shadcn-based admin UX and validation states
- [ ] 02-06: Phase quality gate - tests, code review, and deploy/build verification

### Phase 3: Bitbucket Read Integration

**Goal**: Read configured Bitbucket Cloud repository data safely and expose actionable setup/import errors.
**Depends on**: Phase 2
**Requirements**: [BITB-01, BITB-02, BITB-03, BITB-04, BITB-05, BITB-06]
**UI hint**: yes
**Success Criteria** (what must be TRUE):

  1. Admin can store Bitbucket Cloud credentials or tokens for configured repositories.
  2. System validates read, write, branch, and pull request capabilities during setup.
  3. System can list configured repository branches.
  4. System can read configured localization files from the selected source branch.
  5. System stores source commit/file references and surfaces actionable connection or permission failures.
  6. Phase quality gate passes with tests, code review, and deploy/build smoke verification.

**Plans**: 5 plans

Plans:

- [ ] 03-01: Bitbucket credential storage and secure backend client
- [ ] 03-02: Permission and capability validation
- [ ] 03-03: Branch listing and file read APIs
- [ ] 03-04: Import baseline records and admin-facing errors
- [ ] 03-05: Phase quality gate - tests, code review, and deploy/build verification

### Phase 4: Localization Parser Foundation

**Goal**: Convert supported localization files into canonical translation records.
**Depends on**: Phase 3
**Requirements**: [FMT-01, FMT-02, FMT-03, FMT-04, FMT-07]
**UI hint**: no
**Success Criteria** (what must be TRUE):

  1. System parses Android XML strings into canonical records.
  2. System parses Qt `.ts` translations into canonical records.
  3. System parses JSON localization files into canonical records.
  4. System parses iOS `.strings` files into canonical records.
  5. Canonical records include product, repository, branch, file path, format, key, language, text, state, and locator metadata.
  6. Phase quality gate passes with parser tests, code review, and backend deploy/build smoke verification.

**Plans**: 6 plans

Plans:

- [ ] 04-01: Canonical translation model and adapter interfaces
- [ ] 04-02: Android XML parser
- [ ] 04-03: Qt `.ts` parser
- [ ] 04-04: JSON parser
- [ ] 04-05: iOS `.strings` parser
- [ ] 04-06: Phase quality gate - parser tests, code review, and deploy/build verification

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
**Requirements**: [FMT-05, FMT-06, PR-04]
**UI hint**: no
**Success Criteria** (what must be TRUE):

  1. System preserves file location metadata needed to write changed translations back to original files.
  2. Golden fixtures verify parse/write behavior for Android XML, Qt `.ts`, JSON, and iOS `.strings`.
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
| 1. Platform Foundation | 10/15 | In Progress|  |
| 2. Admin Configuration | 0/6 | Not started | - |
| 3. Bitbucket Read Integration | 0/5 | Not started | - |
| 4. Localization Parser Foundation | 0/6 | Not started | - |
| 5. Import, Search, and Constraints | 0/6 | Not started | - |
| 6. Review Workspace and Comments | 0/6 | Not started | - |
| 7. Format-Safe Write-Back | 0/5 | Not started | - |
| 8. Change Sets and Pull Requests | 0/6 | Not started | - |
| 9. Verification and Hardening | 0/5 | Not started | - |
