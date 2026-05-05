<!-- GSD:project-start source:PROJECT.md -->
## Project

**VerboFlex**

VerboFlex is a web-based platform for reviewing, managing, modifying, and approving localized strings used across multiple software products. The platform provides product managers, translators, reviewers, and admins with a searchable portal over localization data stored in Bitbucket Cloud repositories, without requiring users to manually navigate repository structures.

Products may use different technologies and localization layouts, including mobile applications, Linux embedded systems, Qt projects, and other software platforms. Some products store translated strings directly inside the product repository, while others store translation keys in one repository and retrieve translations from another Bitbucket project configured by an admin.

**Core Value:** Product teams can quickly find, review, constrain, modify, comment on, and approve translations, then send approved changes back through the standard Bitbucket Cloud pull request workflow.

### Constraints

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
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.14.x | Backend runtime | Current stable Python line; strong ecosystem for API services, background workers, XML/JSON parsing, and integration code. |
| FastAPI | 0.136.1 | Backend API | First-class OpenAPI support, dependency injection, OAuth2 security utilities, Pydantic validation, and clean separation from the frontend. |
| Celery | 5.6.3 | Background task queue | Standard Python worker model for repository imports, parser jobs, Bitbucket commits, PR creation, retries, and status tracking. |
| Redis | 7.x server / redis-py 7.4.0 | Celery broker/result backend and lightweight job coordination | Celery officially supports Redis as a broker/backend; fits import and PR job queues. |
| PostgreSQL | 18.x | Primary database | Durable relational model for products, repositories, branches, users, roles, strings, review states, comments, constraints, imports, and PR jobs. |
| SQLAlchemy | 2.0.49 | Database ORM/query layer | Mature Python ORM with strong PostgreSQL support and Alembic integration. |
| Alembic | 1.18.4 | Database migrations | Standard migration tool for SQLAlchemy metadata and versioned schema changes. |
| OAuth2 + Bearer/JWT | FastAPI security utilities | Authentication model | Matches the user's stack preference and FastAPI's documented security model; supports role checks on API endpoints. |
| React | 19.2.5 | Frontend UI | Current React runtime for dense review screens and controlled editing workflows. |
| Vite | 8.0.10 | Frontend build/dev tooling | Cleanly separates SPA/frontend delivery from the Python API while supporting React + TypeScript. |
| TypeScript | 6.0.3 | Frontend language | Strong types for API clients, translation table state, forms, and review workflows. |
| shadcn/ui CLI | 4.6.0 | Frontend component distribution/design system seed | Provides accessible, composable component code installed into the project rather than hidden behind a package abstraction. |
| Tailwind CSS | 4.2.4 | Styling foundation for shadcn/ui | Required by current shadcn/ui Vite setup and keeps styling close to component code. |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pydantic | 2.13.3 | API schemas and validation | Validate request/response payloads, parser output, admin mappings, and Bitbucket API responses. |
| psycopg | 3.3.4 | PostgreSQL driver | Use with SQLAlchemy for PostgreSQL connectivity. |
| python-jose or PyJWT | TBD during auth planning | JWT signing/verification | Use for OAuth2 bearer access tokens if not delegated to an external OAuth2/OIDC provider. |
| passlib/argon2/bcrypt | TBD during auth planning | Password hashing | Needed if v1 keeps internal username/password users while exposing OAuth2 token endpoints. |
| defusedxml + lxml/ElementTree | TBD during parser planning | XML parsing | Use safe XML parsing for Android XML and Qt `.ts`; choose serializer strategy based on fixture preservation tests. |
| json module / jsonpath tooling | Standard/TBD | JSON localization parsing | Use standard JSON first; add path-aware editing library if preserving formatting requires it. |
| polib/custom parser | TBD | iOS `.strings` support if useful | Evaluate during parser planning; `.strings` may require a custom format-preserving parser. |
| TanStack React Table | 8.21.3 | Search/review grids | Dense translation tables with filtering, sorting, pagination, and column controls. |
| TanStack Query | 5.100.9 | Frontend server-state cache | API polling, filters, comments, job status, optimistic updates. |
| lucide-react | 1.14.0 | UI icons | Lightweight icon set for review actions, states, comments, filters, and admin tools. |
| class-variance-authority | 0.7.1 | Component variants | Common shadcn/ui pattern for variants such as button size/state/tone. |
| clsx | 2.1.1 | Conditional classes | Utility for composing class names in project-owned UI components. |
| tailwind-merge | 3.5.0 | Tailwind class conflict resolution | Keeps component overrides predictable. |
| Playwright | 1.59.1 | E2E testing | Verify search, editing, approval, and PR submission flows. |
| pytest | TBD during scaffold | Backend tests | Parser, serializer, auth, Bitbucket integration, and service tests. |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| Docker Compose | Local Postgres, Redis, backend, worker, frontend | Keep local setup reproducible. |
| Alembic CLI | Database migrations | Store schema evolution in versioned migration scripts. |
| Celery worker/beat | Background processing | Use worker for imports/PRs; add beat only if scheduled imports are needed. |
| Bitbucket API mocks | Integration tests | Mock Bitbucket Cloud for file read, branch, commit, and PR flows. |
| Playwright traces | Review UI debugging | Capture search/edit/approve regressions. |
## Installation
# Backend
# Frontend
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| React + Vite SPA | Next.js App Router | Use Next.js only if server-side rendering or a unified JS full-stack architecture becomes a requirement. |
| shadcn/ui | MUI/Ant Design/Chakra UI | Use a packaged UI library only if the team wants less component ownership and accepts heavier design/API constraints. |
| FastAPI | Django + DRF | Use Django if built-in admin, ORM, and batteries-included auth outweigh API-first flexibility. |
| Celery + Redis | RQ/Arq | Use simpler queues only if job orchestration remains small and retries/status are basic. |
| SQLAlchemy + Alembic | Django ORM migrations | Use Django ORM only if choosing Django as the backend framework. |
| PostgreSQL | MySQL/MariaDB | Use only if infrastructure mandates it; Postgres fits relational + JSON indexing needs better. |
| Bitbucket REST source endpoints | Local git clone worker | Use local clones if API commit endpoint cannot preserve file structure/encoding well enough or if PR creation needs complex multi-commit history. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Regex-only localization parsers | XML, `.strings`, JSON escaping, comments, plural forms, and formatting will break. | Format-aware parsers plus serializer tests. |
| Re-serializing entire files blindly | Can reorder keys, drop comments, change whitespace, or corrupt platform-specific escapes. | Minimal edit application where possible; golden-file tests for every format. |
| Running Bitbucket imports inside API request handlers | Imports and PR creation are slow, retry-prone operations. | Celery tasks with Redis broker/result backend. |
| Storing Bitbucket tokens in plaintext | Source write permissions are high impact. | Encrypt secrets at rest; audit usage; use least-privilege scopes. |
| Putting review comments only into PR comments | Product managers need comments attached to translations before and after PRs exist. | Store app-level translation comments; optionally mirror summary into PR description. |
| Frontend-only authorization | API calls can bypass UI checks. | Enforce OAuth2 authentication and role checks in FastAPI dependencies. |
| Treating shadcn/ui as an immutable third-party library | shadcn/ui intentionally gives you component source code. | Own and adapt the generated components in the frontend design system. |
## Stack Patterns by Variant
- Implement OAuth2 password/token endpoints in FastAPI with bearer JWT access tokens.
- Store users and roles in Postgres.
- Enforce permissions through FastAPI dependencies on every mutating endpoint.
- Initialize shadcn/ui for Vite and install only the components needed by each phase.
- Keep generated components in `frontend/src/components/ui` or a dedicated frontend UI package if a JS monorepo layout is introduced.
- Prefer shadcn primitives for buttons, inputs, dialogs, sheets, tables, forms, tabs, tooltips, badges, dropdowns, sidebars, and toasts.
- Keep the OAuth2 boundary but move authentication to an external OIDC provider.
- Preserve internal role mapping in Postgres.
- Keep canonical translation records in Postgres, but store raw file snapshots and apply path-specific text edits back to the original file.
- Add golden-file parser/serializer fixtures before supporting each file format in production.
- Run imports, refreshes, commits, and PR creation through Celery workers.
- Keep search backed by indexed Postgres fields first; add OpenSearch only if Postgres search becomes insufficient.
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Python 3.14.x | FastAPI 0.136.x, Celery 5.6.x, SQLAlchemy 2.0.x | Verify all parser dependencies support Python 3.14 during scaffold; pin to Python 3.13 if a critical package lags. |
| FastAPI 0.136.x | Pydantic 2.x | FastAPI's current validation model is Pydantic v2 based. |
| Celery 5.6.x | Redis broker/backend | Celery supports Redis as broker/backend; configure visibility timeout and retry behavior explicitly. |
| SQLAlchemy 2.0.x | Alembic 1.18.x, psycopg 3.x | Standard Postgres ORM/migration pairing. |
| React 19.x | Vite 8.x, TypeScript 6.x, shadcn 4.6.x | SPA frontend consumes FastAPI OpenAPI endpoints and uses shadcn/ui project-owned components. |
| shadcn/ui 4.6.x | Tailwind CSS 4.x, lucide-react | Current docs support Vite and Tailwind CSS v4 setup. |
## Sources
- [FastAPI security docs](https://fastapi.tiangolo.com/tutorial/security/) - OAuth2 and dependency-based security model.
- [FastAPI OAuth2 with JWT docs](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) - OAuth2 bearer token pattern.
- [Celery Redis docs](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html) - Redis broker/backend configuration.
- [Celery first steps](https://docs.celeryq.dev/en/stable/getting-started/first-steps-with-celery.html) - worker/task model.
- [Alembic docs](https://alembic.sqlalchemy.org/en/latest/) - SQLAlchemy migrations.
- [SQLAlchemy PostgreSQL dialect docs](https://docs.sqlalchemy.org/21/dialects/postgresql.html) - PostgreSQL support.
- [Python documentation by version](https://www.python.org/doc/versions/) - current Python release line.
- [Vite getting started](https://vite.dev/guide/) - React TypeScript SPA tooling and templates.
- [React docs](https://react.dev/) - current React documentation.
- [shadcn/ui GitHub repository](https://github.com/shadcn-ui/ui) - project description, license, latest release.
- [shadcn/ui introduction](https://ui.shadcn.com/docs) - open-code component distribution model.
- [shadcn/ui Vite installation](https://ui.shadcn.com/docs/installation/vite) - Vite setup and CLI commands.
- [TanStack Query docs](https://tanstack.com/query/latest/docs/framework/react/overview) - frontend server-state management.
- [Bitbucket Cloud REST API intro](https://developer.atlassian.com/cloud/bitbucket/rest/intro/) - auth methods, scopes, OAuth behavior, API token notes.
- [Bitbucket Cloud source API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-source/) - file browse and commit endpoint behavior.
- [Bitbucket Cloud refs API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-refs/) - branch creation.
- [Bitbucket Cloud pull request API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pullrequests/) - PR creation and comments.
- [PostgreSQL current docs](https://www.postgresql.org/docs/current/) - current supported PostgreSQL version.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
