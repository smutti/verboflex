# VerboFlex

## What This Is

VerboFlex is a web-based platform for reviewing, managing, modifying, and approving localized strings used across multiple software products. The platform provides product managers, translators, reviewers, and admins with a searchable portal over localization data stored in Bitbucket Cloud repositories, without requiring users to manually navigate repository structures.

Products may use different technologies and localization layouts, including mobile applications, Linux embedded systems, Qt projects, and other software platforms. Some products store translated strings directly inside the product repository, while others store translation keys in one repository and retrieve translations from another Bitbucket project configured by an admin.

## Core Value

Product teams can quickly find, review, constrain, modify, comment on, and approve translations, then send approved changes back through the standard Bitbucket Cloud pull request workflow.

## Requirements

### Validated

- [x] Admin can configure products, Bitbucket Cloud repositories, source branches to read from, and target branches for changes. — Phase 2
- [x] Admin can configure product-specific links between repositories when translation keys and translated values live in different Bitbucket projects. — Phase 2
- [x] Admin can configure project-specific pull request behavior for translation updates. — Phase 2
- [x] Platform supports internal corporate-email/password accounts and a role model with users able to hold multiple roles. — Phases 1–2
- [x] Initial roles include admin, product manager/reviewer, translator, and viewer. — Phases 1–2

### Active

- [ ] Platform can read and parse localized strings from Android XML string resources.
- [ ] Platform can read and parse localized strings from Qt `.ts` translation files.
- [ ] Platform can read and parse localized strings from JSON localization files.
- [ ] Platform can read and parse localized strings from iOS `.strings` files.
- [ ] Product managers can search and filter translations by product.
- [ ] Product managers can search for a specific translation in a selected language.
- [ ] Product managers can filter translations by approval state.
- [ ] Product managers can identify translations that violate configured constraints.
- [ ] Authorized users can define and manage a maximum character length constraint for each string.
- [ ] Authorized users can review a translation and mark it as draft, approved, or rejected.
- [ ] Authorized users can modify translation text directly in the platform.
- [ ] Authorized users can add comments to individual translations.
- [ ] When translation changes are submitted, the platform commits them back to the relevant Bitbucket Cloud repository.
- [ ] When translation changes are submitted, the platform opens a pull request against the configured or user-selected target branch according to the product's PR configuration.

### Out of Scope

- Figma integration - explicitly deferred to a later phase after the core Bitbucket-backed review workflow is working.
- Constraints beyond maximum character length - placeholder validation, forbidden characters, line counts, plural-form rules, and read-only key handling are deferred until the base constraint model is proven.
- Bitbucket Server/Data Center support - v1 targets Bitbucket Cloud only.
- Complex approval gates - v1 uses simple draft, approved, and rejected states rather than per-product approval rules or mandatory multi-role approvals.
- External identity provider integration - v1 uses a simple internal user and role setup.

## Context

The product exists to reduce friction for product managers and localization stakeholders who need to inspect and approve translations across many software products. Today, those strings live in Bitbucket repositories with different structures and technologies, making review slow and dependent on repository knowledge.

The platform must support heterogeneous source layouts. Some products will have complete translations stored directly in their product repository. Other products will store translation keys in the product repository while translations are retrieved from a separate Bitbucket project. Those cross-repository relationships are not assumed to be discoverable automatically; admins configure them in the UI.

Bitbucket Cloud remains the source of truth. VerboFlex should read strings from configured repositories and branches, allow authorized edits in the portal, then write changes back as commits and pull requests so teams can review and merge through their normal development workflow.

The initial review model is intentionally simple. Translations have draft, approved, and rejected states, and users can comment on individual translations. More advanced workflow controls can be added after the core search, review, edit, and PR loop is validated.

## Constraints

- **Repository provider**: Bitbucket Cloud only for v1 - keeps API integration focused and avoids self-hosted Bitbucket differences.
- **Application architecture**: Frontend and backend are separate applications - keeps the review UI independent from backend API/workers.
- **Frontend stack**: React + Vite + TypeScript - provides a focused SPA for dense review and admin workflows.
- **UI system**: shadcn/ui - frontend components should be installed as project-owned code and customized for the review/admin experience.
- **Backend stack**: Python + FastAPI - provides the API layer, OpenAPI surface, OAuth2 security model, and service boundary.
- **Background processing**: Celery + Redis - repository imports, parsing, commits, and pull request creation must not run inside HTTP requests.
- **Database and migrations**: PostgreSQL with SQLAlchemy and Alembic - Postgres remains the data store and Alembic owns schema changes.
- **Authentication**: OAuth2 bearer-token based authentication - authorization still uses internal users and multiple roles.
- **Phase quality gate**: Every phase must close with targeted tests, code review, and build/deploy smoke verification for the current app slice.
- **Localization formats**: Android XML strings, Qt `.ts`, JSON, and iOS `.strings` are the first supported formats - these cover the known product technologies.
- **Repository mapping**: Product, repository, branch, translation source, and PR behavior must be configurable per project - localization layouts vary across products.
- **Constraint model**: Maximum character length only for v1 - this directly supports UI and technical limits while keeping validation rules tractable.
- **Access model**: Internal users with multiple roles - sufficient for v1 without requiring external identity provider integration.
- **Workflow states**: Draft, approved, and rejected only - avoids complex approval policy design before usage patterns are known.
- **Deferred design context**: Figma integration comes later - the Bitbucket-backed localization workflow is the first priority.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Target Bitbucket Cloud for v1 | The repositories are hosted in Bitbucket, and focusing on Cloud avoids supporting multiple API surfaces immediately. | - Pending |
| Prioritize repository modeling and Bitbucket write-back automation | Products use different localization structures, and the core value depends on safely committing changes and opening PRs. | - Pending |
| Support Android XML, Qt `.ts`, JSON, and iOS `.strings` first | These formats match the known product technologies and localization file structures. | - Pending |
| Use admin-configured cross-repository mappings | Some products separate keys from translations, and the relationship should be explicit in the UI. | - Pending |
| Use internal email/password accounts with multiple roles | V1 avoids dependency on an external identity provider while retaining a provider-independent role model. Corporate email is the unique login identifier; the first admin is bootstrapped by CLI; password reset is admin-managed with a mandatory first-login password change. Microsoft Entra ID/OIDC remains a future integration. | Accepted 2026-08-24 |
| Use simple translation states for v1 | Draft, approved, and rejected states provide an actionable review loop without overdesigning workflow rules. | - Pending |
| Limit v1 constraints to maximum character length | This is the known immediate constraint and keeps the validation model small. | - Pending |
| Defer Figma integration | UI design context is valuable, but the core repository-backed review and PR workflow must work first. | - Pending |
| Separate frontend and backend applications | The frontend should remain independent from the Python backend API and worker stack. | - Pending |
| Use shadcn/ui for frontend UI | shadcn/ui provides accessible, composable component code that can be customized into the product's design system. | - Pending |
| Use Python FastAPI for the backend | FastAPI fits API-first development, OAuth2 support, OpenAPI docs, and service boundaries. | - Pending |
| Use Celery and Redis for background work | Bitbucket imports, parsing, commits, and PR creation are long-running and need retries/status tracking. | - Pending |
| Use PostgreSQL with SQLAlchemy and Alembic | PostgreSQL fits the relational model, while Alembic provides versioned schema migrations. | - Pending |
| Use OAuth2 for authentication | Matches the desired auth model while keeping roles and permissions enforced by the backend. | - Pending |
| Require per-phase quality gates | Each phase should add or update tests, complete code review, and verify build/deploy behavior before being marked complete. | - Pending |
| Publish immutable active product revisions | Admin edits remain isolated in candidate revisions and publication swaps the active revision atomically, so readers never observe partial configuration. | Accepted 2026-09-01 |
| Use one organizational Bitbucket client-credentials connection | VerboFlex uses encrypted, generation-bound, access-only credentials with exact repository read scope; Phase 2 performs no provider writes. | Accepted 2026-09-01 |
| Keep repository identity global and mappings revision-specific | Repositories are reusable global identities, while branches, layouts, translation targets, and PR grouping belong to the product revision; each mapping represents exactly one layout. | Accepted 2026-09-01 |
| Bind previews to immutable repository commits | Preview resolves a branch once, then parses bounded content from that immutable commit with fail-closed format handling. | Accepted 2026-09-01 |
| Let the router own dirty-form navigation transactions | Product and mapping navigation cannot discard unsaved changes until the authoritative route transition commits. | Accepted 2026-09-01 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? Move to Out of Scope with reason
2. Requirements validated? Move to Validated with phase reference
3. New requirements emerged? Add to Active
4. Decisions to log? Add to Key Decisions
5. "What This Is" still accurate? Update if drifted

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check - still the right priority?
3. Audit Out of Scope - reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-01 after Phase 2*
