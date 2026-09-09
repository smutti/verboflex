# Requirements: VerboFlex

**Defined:** 2026-05-04
**Reconciled:** 2026-08-26 after Phase 2 specification
**Core Value:** Product teams can quickly find, review, constrain, modify, comment on, and approve translations, then send approved changes back through the standard Bitbucket Cloud pull request workflow.

## v1 Requirements

### Platform Foundation

- [x] **PLAT-01**: The application is organized as separate frontend and backend applications.
- [x] **PLAT-02**: The frontend is implemented with React, Vite, TypeScript, and shadcn/ui project-owned components.
- [x] **PLAT-03**: The backend exposes a FastAPI HTTP API consumed by the frontend.
- [x] **PLAT-04**: The backend persists application data in PostgreSQL through SQLAlchemy models.
- [x] **PLAT-05**: The backend manages database schema changes through Alembic migrations.
- [x] **PLAT-06**: Long-running imports, parsing, commits, and pull request operations run through Celery workers using Redis.
- [ ] **PLAT-07**: The system records audit metadata for key mutations, including actor, timestamp, entity, and action.

### Authentication and Roles

- [x] **AUTH-01**: User can authenticate to the backend with an internal corporate-email/password account using OAuth2 bearer-token authentication; bootstrapped or reset credentials require a password change before normal application access.
- [x] **AUTH-02**: Admin can create, update, administratively reset passwords for, deactivate, and view internal users.
- [x] **AUTH-03**: Admin can assign multiple roles to the same user.
- [x] **AUTH-04**: System supports the roles admin, product manager/reviewer, translator, and viewer.
- [ ] **AUTH-05**: Backend enforces role-based authorization on admin configuration, translation editing, approval, commenting, and PR submission APIs.
- [ ] **AUTH-06**: Frontend hides or disables actions the authenticated user is not authorized to perform.

### Product and Repository Configuration

- [x] **PROD-01**: Admin can create and edit a product record with name, description, and active/inactive status.
- [x] **PROD-02**: Admin can configure one or more Bitbucket Cloud repositories for a product.
- [x] **PROD-03**: Admin can configure the source branch the platform reads from for each repository mapping.
- [x] **PROD-04**: Admin can configure allowed target branches for translation pull requests.
- [x] **PROD-05**: Admin can configure product-specific pull request grouping behavior.
- [x] **PROD-06**: Admin can configure whether translations live directly in the product repository or in a linked translation repository.
- [x] **PROD-07**: Admin can configure links between a repository containing translation keys and a separate Bitbucket project/repository containing translated values.
- [x] **PROD-08**: Admin can validate a repository mapping by previewing detected files, languages, sample keys, and sample translations before enabling imports.
- [x] **PROD-09**: Admin can configure the localization file format used by each mapping.

### Bitbucket Cloud Integration

- [x] **BITB-01**: Admin can connect, reconnect, revoke, and view bounded status for the single organization-wide Bitbucket Cloud OAuth 2.0 connection used for repository access.
- [x] **BITB-02**: System validates and reports Bitbucket Cloud capabilities required by configured read/import operations and the later write/pull-request profile without silently expanding OAuth scopes.
- [x] **BITB-03**: System can list configured repository branches from Bitbucket Cloud.
- [x] **BITB-04**: System can read configured localization files from the configured Bitbucket Cloud source branch.
- [x] **BITB-05**: System stores the source commit hash and file reference used for each import.
- [x] **BITB-06**: System reports Bitbucket connection, permission, and import errors in a way admins can act on.

### Localization Import and Formats

- [x] **FMT-01**: System can parse Android XML string resources into canonical translation records.
- [x] **FMT-02**: System can parse Qt `.ts` files into canonical translation records.
- [x] **FMT-03**: System can parse JSON localization files into canonical translation records.
- [x] **FMT-04**: System can parse iOS `.strings` files into canonical translation records.
- [ ] **FMT-05**: System preserves enough file location metadata to write edited translations back to their original files.
- [x] **FMT-06**: System validates parser behavior with golden fixtures for all supported v1 formats.
- [x] **FMT-07**: System imports translations into a canonical model that includes product, repository, branch, file path, format, key, language, source text when available, translated text, state, and locator metadata.
- [x] **FMT-08**: System can refresh imported translations from Bitbucket without losing review states, comments, constraints, or audit history attached to stable translation identities.

### Search and Review Navigation

- [x] **SRCH-01**: Product manager can search and filter translations by product.
- [x] **SRCH-02**: Product manager can search for a specific translation in a selected language.
- [x] **SRCH-03**: Product manager can search by translation key or text.
- [x] **SRCH-04**: Product manager can filter translations by approval state.
- [x] **SRCH-05**: Product manager can filter translations by maximum-length constraint violation status.
- [x] **SRCH-06**: User can open a translation detail view from search results.
- [x] **SRCH-07**: Translation detail view shows product, language, key, source text when available, translated text, state, file path, repository, branch, constraints, comments, and pending change status.
- [x] **SRCH-08**: Search results are paginated or virtualized so large translation sets remain usable.

### Constraints

- [x] **CONS-01**: Authorized user can define a maximum character length constraint for a translation key.
- [x] **CONS-02**: Authorized user can edit or remove a maximum character length constraint.
- [x] **CONS-03**: System calculates whether each translated value violates its configured maximum character length.
- [x] **CONS-04**: System recalculates maximum-length violations after import and after translation edits.
- [x] **CONS-05**: Translation detail view shows configured max length, actual length, and violation status.

### Translation Review Workflow

- [ ] **REVW-01**: Authorized user can edit translation text in the platform.
- [ ] **REVW-02**: System stores edited translations as pending changes before Bitbucket write-back.
- [ ] **REVW-03**: Authorized user can mark a translation as draft.
- [ ] **REVW-04**: Authorized user can mark a translation as approved.
- [ ] **REVW-05**: Authorized user can mark a translation as rejected.
- [ ] **REVW-06**: System records state-change history with actor and timestamp.
- [ ] **REVW-07**: System prevents viewer-only users from editing translations or changing review state.
- [ ] **REVW-08**: User can see whether a translation has pending unsent changes.

### Translation Comments

- [ ] **COMM-01**: Authorized user can add a comment to an individual translation.
- [ ] **COMM-02**: Authorized user can view comments attached to an individual translation.
- [ ] **COMM-03**: System stores comment author and timestamp.
- [ ] **COMM-04**: Translation search results show whether a translation has comments.
- [ ] **COMM-05**: Comments remain available after imports, edits, review state changes, and PR submission.
- [ ] **COMM-06**: Comment authors can mention active users through a structured `@` autocomplete that stores immutable user identity rather than display text alone.

### In-App Notifications

- [ ] **NOTF-01**: Creating a comment produces exactly one notification for every distinct mentioned user other than the comment author.
- [ ] **NOTF-02**: Each authenticated user can view only their own notifications and distinguish unread notifications from read notifications.
- [ ] **NOTF-03**: A user can mark each of their notifications as read without changing another user's notification state.
- [ ] **NOTF-04**: A mention notification links directly to the originating translation comment and the UI scrolls to, focuses, and visually highlights that exact comment.
- [ ] **NOTF-05**: The authenticated application shell shows a notification bell with the user's unread count and provides access to a dedicated notification center.

### Change Sets and Pull Requests

- [ ] **PR-01**: Authorized user can select pending translation changes for submission.
- [ ] **PR-02**: System groups selected translation changes according to the product's configured pull request behavior.
- [ ] **PR-03**: User can choose an allowed target branch when submitting changes if the project configuration permits target branch selection.
- [ ] **PR-04**: System checks whether the source branch or file changed since the relevant import before writing changes.
- [ ] **PR-05**: System creates or updates a Bitbucket Cloud source branch for the submitted change set.
- [ ] **PR-06**: System writes modified localization files back to the correct Bitbucket Cloud repository.
- [ ] **PR-07**: System creates a Bitbucket Cloud commit that includes the submitted translation changes.
- [ ] **PR-08**: System opens a Bitbucket Cloud pull request against the selected or configured target branch.
- [ ] **PR-09**: System stores pull request URL, id, source branch, target branch, commit hash, included translations, and submission status.
- [ ] **PR-10**: User can view PR creation status and errors from the platform.
- [ ] **PR-11**: System supports retrying failed PR submission jobs without creating duplicate change sets.

### User Interface

- [x] **UI-01**: Frontend uses shadcn/ui primitives for core controls such as buttons, inputs, selects, dialogs, sheets, badges, tooltips, tabs, tables, sidebars, and toasts.
- [ ] **UI-02**: Review workspace presents filters, results, translation detail, comments, state controls, and constraint status in a dense task-focused layout.
- [x] **UI-03**: Admin configuration screens provide clear validation feedback for repository, branch, mapping, and credential setup.
- [ ] **UI-04**: Frontend shows background job status for imports and PR submissions without blocking the user interface.

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Design Context

- **FIG-01**: User can link translation keys to Figma screens or frames.
- **FIG-02**: User can view Figma design context while reviewing a translation.
- **FIG-03**: System can help validate whether a translation fits its associated design context.

### Advanced Constraints

- **VAL-01**: System can validate required placeholders.
- **VAL-02**: System can validate forbidden characters.
- **VAL-03**: System can validate line count constraints.
- **VAL-04**: System can validate plural-form rules.
- **VAL-05**: Admin can mark keys as read-only.

### Advanced Workflow

- **WF-01**: Admin can configure per-product approval gates.
- **WF-02**: Admin can require role-specific approval before PR submission.
- **WF-03**: User can perform bulk approval or rejection operations.
- **WF-04**: System can update or supersede an existing open translation PR.

### Enterprise Integration

- **ENT-01**: System can integrate with an external OAuth2/OIDC identity provider.
- **ENT-02**: System can support Bitbucket Server/Data Center.
- **ENT-03**: System can synchronize groups or roles from an external identity system.

### Localization Suite Features

- **L10N-01**: System can provide translation memory suggestions.
- **L10N-02**: System can provide machine translation suggestions.
- **L10N-03**: System can manage glossaries or terminology rules.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Figma integration in v1 | Deferred until the core Bitbucket-backed review and PR workflow is working. |
| Constraints beyond maximum character length in v1 | The initial constraint model should stay small and proven before adding placeholder/plural/line rules. |
| Bitbucket Server/Data Center support in v1 | V1 targets Bitbucket Cloud only to avoid multiple API surfaces. |
| External identity provider integration in v1 | V1 uses internal users with OAuth2 bearer-token authentication; external OIDC can be added later. |
| Complex approval gates in v1 | The selected workflow uses simple draft, approved, and rejected states. |
| Machine translation, translation memory, and glossary management in v1 | These belong to broader localization-suite scope, not the initial repository-backed review portal. |
| Direct commits to protected target branches | V1 should route changes through pull requests. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLAT-01 | Phase 1 | Complete |
| PLAT-02 | Phase 1 | Complete |
| PLAT-03 | Phase 1 | Complete |
| PLAT-04 | Phase 1 | Complete |
| PLAT-05 | Phase 1 | Complete |
| PLAT-06 | Phase 1 | Complete |
| PLAT-07 | Phase 8 | Pending |
| AUTH-01 | Phase 1 | Complete |
| AUTH-02 | Phase 2 | Complete |
| AUTH-03 | Phase 2 | Complete |
| AUTH-04 | Phase 1 | Complete |
| AUTH-05 | Phase 8 | Pending |
| AUTH-06 | Phase 8 | Pending |
| PROD-01 | Phase 2 | Complete |
| PROD-02 | Phase 2 | Complete |
| PROD-03 | Phase 2 | Complete |
| PROD-04 | Phase 2 | Complete |
| PROD-05 | Phase 2 | Complete |
| PROD-06 | Phase 2 | Complete |
| PROD-07 | Phase 2 | Complete |
| PROD-08 | Phase 2 | Complete |
| PROD-09 | Phase 2 | Complete |
| BITB-01 | Phase 2 | Complete |
| BITB-02 | Phase 3 | Complete |
| BITB-03 | Phase 2 | Complete |
| BITB-04 | Phase 2 | Complete |
| BITB-05 | Phase 3 | Complete |
| BITB-06 | Phase 3 | Complete |
| FMT-01 | Phase 4 | Complete |
| FMT-02 | Phase 4 | Complete |
| FMT-03 | Phase 4 | Complete |
| FMT-04 | Phase 4 | Complete |
| FMT-05 | Phase 6 | Pending |
| FMT-06 | Phase 4 | Complete |
| FMT-07 | Phase 4 | Complete |
| FMT-08 | Phase 4 | Complete |
| SRCH-01 | Phase 4 | Complete |
| SRCH-02 | Phase 4 | Complete |
| SRCH-03 | Phase 4 | Complete |
| SRCH-04 | Phase 4 | Complete |
| SRCH-05 | Phase 4 | Complete |
| SRCH-06 | Phase 4 | Complete |
| SRCH-07 | Phase 4 | Complete |
| SRCH-08 | Phase 4 | Complete |
| CONS-01 | Phase 4 | Complete |
| CONS-02 | Phase 4 | Complete |
| CONS-03 | Phase 4 | Complete |
| CONS-04 | Phase 4 | Complete |
| CONS-05 | Phase 4 | Complete |
| REVW-01 | Phase 5 | Pending |
| REVW-02 | Phase 5 | Pending |
| REVW-03 | Phase 5 | Pending |
| REVW-04 | Phase 5 | Pending |
| REVW-05 | Phase 5 | Pending |
| REVW-06 | Phase 5 | Pending |
| REVW-07 | Phase 5 | Pending |
| REVW-08 | Phase 5 | Pending |
| COMM-01 | Phase 5 | Pending |
| COMM-02 | Phase 5 | Pending |
| COMM-03 | Phase 5 | Pending |
| COMM-04 | Phase 5 | Pending |
| COMM-05 | Phase 5 | Pending |
| COMM-06 | Phase 5 | Pending |
| NOTF-01 | Phase 5 | Pending |
| NOTF-02 | Phase 5 | Pending |
| NOTF-03 | Phase 5 | Pending |
| NOTF-04 | Phase 5 | Pending |
| NOTF-05 | Phase 5 | Pending |
| PR-01 | Phase 7 | Pending |
| PR-02 | Phase 7 | Pending |
| PR-03 | Phase 7 | Pending |
| PR-04 | Phase 6 | Pending |
| PR-05 | Phase 7 | Pending |
| PR-06 | Phase 7 | Pending |
| PR-07 | Phase 7 | Pending |
| PR-08 | Phase 7 | Pending |
| PR-09 | Phase 7 | Pending |
| PR-10 | Phase 7 | Pending |
| PR-11 | Phase 7 | Pending |
| UI-01 | Phase 1 | Complete |
| UI-02 | Phase 5 | Pending |
| UI-03 | Phase 2 | Complete |
| UI-04 | Phase 7 | Pending |

**Coverage:**

- v1 requirements: 83 total
- Mapped to phases: 83
- Unmapped: 0

---
*Requirements defined: 2026-05-04*
*Last updated: 2026-09-08 after adding Phase 5 mentions and in-app notifications*
