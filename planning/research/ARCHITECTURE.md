# Architecture Research

**Domain:** Bitbucket-backed localization review and approval portal
**Researched:** 2026-05-04
**Confidence:** MEDIUM-HIGH

## Standard Architecture

### System Overview

```text
React/Vite Frontend
  -> FastAPI Backend API
      -> OAuth2 bearer authentication and role checks
      -> Application services
          -> Product/repository config service
          -> Bitbucket integration service
          -> Localization import service
          -> Parser/writer registry
          -> Review/comment/constraint service
          -> Change-set and PR service
      -> PostgreSQL
      -> Redis
      -> Celery workers
          -> Bitbucket Cloud REST API
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Frontend app | Search, review, edit, comment, state changes, admin configuration. | React + Vite + TypeScript SPA consuming FastAPI endpoints. |
| UI component system | Shared accessible frontend primitives and product-specific component variants. | shadcn/ui generated code, Tailwind CSS, lucide icons. |
| Backend API | Auth, authorization, validation, business workflows, persistence. | FastAPI routers/services with Pydantic schemas. |
| Product config | Products, repositories, branches, formats, source/target branch rules, PR behavior. | Admin UI + FastAPI + Postgres tables. |
| Repository mapping | Direct repo mappings and cross-repo key-to-translation relationships. | Explicit mapping entities with validation previews. |
| Bitbucket client | Read files/directories, create branches, create commits, open PRs, fetch PR status. | Backend-only REST client with encrypted credentials. |
| Import scanner | Discover configured localization files on configured branches. | Celery task; idempotent import records. |
| Parser registry | Convert each format into canonical translation units. | Python format-specific adapters behind a shared interface. |
| Canonical translation store | Store searchable strings, translations, states, constraints, comments, file references. | PostgreSQL tables with indexed product/language/key/state/violation fields. |
| Review UI | Search, filter, inspect, edit, approve/reject, comment. | Dense table + detail panel optimized for repeated review work. |
| Change-set service | Group approved/pending edits into branch-scoped write batches. | Database transaction plus Celery dispatch. |
| Writer service | Apply changes back to original files safely. | Minimal edits or format-preserving serializer with golden tests. |
| PR service | Create Bitbucket branch/commit/PR per product config. | Celery task with audit records and retry handling. |

## Recommended Project Structure

```text
frontend/
  src/
    app/                    # App shell, routes, layout state
    api/                    # Typed FastAPI client and query keys
    components/
      admin/                # Product/repo/branch/mapping forms
      review/               # Translation table, filters, detail panel, state controls
      ui/                   # shadcn/ui generated primitives owned by the project
    features/
      auth/                 # Login/token handling
      products/             # Product and repository config screens
      translations/         # Search/review/edit/comment workflows
      jobs/                 # Import/PR job status views
    tests/                  # Frontend unit and component tests

backend/
  app/
    main.py                 # FastAPI application factory
    api/
      routes/               # FastAPI routers
      deps.py               # OAuth2, DB session, role dependencies
      schemas/              # Pydantic request/response models
    auth/                   # OAuth2 token issuing/verification and role checks
    db/
      models/               # SQLAlchemy models
      session.py            # Engine/session lifecycle
      migrations/           # Alembic versions
    services/
      bitbucket/            # REST client, auth, pagination, rate handling
      products/             # Product/repository config services
      localization/
        parsers/            # android_xml, qt_ts, json, ios_strings adapters
        writers/            # Format-specific write-back logic
        canonical/          # Canonical translation model and normalization
        constraints/        # Max length validator and future validator registry
      review/               # States, comments, audit events
      changesets/           # Change grouping, branch naming, PR submission
    workers/
      celery_app.py         # Celery configuration
      tasks/                # Import, refresh, write-back, PR tasks
  tests/
    fixtures/localization/  # Golden files per format and edge case
    integration/            # Bitbucket API mocks and workflow tests
```

### Structure Rationale

- **`frontend/` and `backend/`:** Keeps deployment, dependencies, tests, and ownership separated as requested.
- **`frontend/src/components/ui/`:** Houses shadcn/ui generated code so the project owns and can adapt the component layer.
- **`backend/app/services/localization/`:** Keeps format parsing/writing separate from product workflows.
- **`backend/app/services/bitbucket/`:** Isolates API scopes, token handling, pagination, branch, commit, and PR behavior.
- **`backend/app/services/changesets/`:** Makes write-back an explicit workflow rather than a side effect of editing a translation.
- **`backend/app/workers/`:** Keeps long-running Bitbucket imports and PR creation out of request handlers.
- **`backend/tests/fixtures/localization/`:** Format preservation must be proven with real before/after files.

## Architectural Patterns

### Pattern 1: Canonical Translation Unit

**What:** Parse every file format into a shared internal representation.
**When to use:** Always. Search, review state, comments, constraints, and PR workflows should not depend on raw file structure.
**Trade-offs:** Requires adapters per format, but prevents UI and workflow duplication.

```python
from typing import Literal
from pydantic import BaseModel

class TranslationUnit(BaseModel):
    product_id: str
    repository_id: str
    branch: str
    file_path: str
    format: Literal["android_xml", "qt_ts", "json", "ios_strings"]
    key: str
    source_text: str | None = None
    language: str
    translated_text: str
    state: Literal["draft", "approved", "rejected"]
    locator: dict[str, str | int]
```

### Pattern 2: Parser/Writer Adapter Registry

**What:** Each supported format implements `parse`, `validate`, and `apply_changes`.
**When to use:** Required for format-specific escaping, metadata, comments, and plural/variant structures.
**Trade-offs:** More upfront code, but avoids fragile shared parser logic.

```python
from typing import Protocol

class LocalizationAdapter(Protocol):
    def parse(self, raw_file: RawLocalizationFile) -> ParsedLocalizationFile: ...
    def apply_changes(
        self,
        raw_file: RawLocalizationFile,
        changes: list[TranslationChange],
    ) -> RawLocalizationFile: ...
```

### Pattern 3: Branch-Scoped Change Sets

**What:** User edits accumulate in the app. Submission creates a change set grouped by repository and target branch according to project config.
**When to use:** Any write-back to Bitbucket.
**Trade-offs:** Requires Celery job/status UI, but avoids partial writes and supports retries.

### Pattern 4: Explicit Mapping Configuration

**What:** Admins configure where keys live, where translations live, which branches to read, which target branch to use, and how PRs are grouped.
**When to use:** All product setup.
**Trade-offs:** More admin work, but safer than guessing cross-repo relationships.

### Pattern 5: OAuth2 at the API Boundary

**What:** The frontend receives/stores OAuth2 bearer tokens and every API mutation is authorized by FastAPI dependencies.
**When to use:** All authenticated API calls.
**Trade-offs:** Requires careful token storage/refresh handling, but keeps authorization server-side and framework-native.

### Pattern 6: Project-Owned UI Components

**What:** Use shadcn/ui as a component code generator and design-system seed, not as a black-box library.
**When to use:** All core frontend surfaces: admin forms, review tables, filters, dialogs, sheets, comments, state badges, toasts, and job status views.
**Trade-offs:** The team owns updates and customizations, but gains direct control over accessibility, styling, and domain-specific behavior.

## Data Flow

### Import Flow

```text
Admin configures product/repo/branch/format in frontend
  -> FastAPI stores validated config
  -> Celery import task reads Bitbucket source tree/file contents
  -> Adapter parses raw files
  -> Canonical translation units are upserted in Postgres
  -> Constraints are evaluated
  -> Search indexes/derived fields are refreshed
```

### Review Flow

```text
Reviewer filters by product/language/state/violations in React UI
  -> FastAPI returns paginated canonical translations
  -> Reviewer opens translation detail
  -> Edit/comment/state mutation calls FastAPI
  -> FastAPI checks OAuth2 token and roles
  -> App stores audit event and pending change
  -> Constraint status recalculates immediately
```

### Submit Flow

```text
User submits selected changes
  -> FastAPI creates change set and enqueues Celery job
  -> Job verifies source branch/head is still valid
  -> Bitbucket branch is created if needed
  -> Writer applies changes to raw files
  -> Bitbucket source endpoint creates commit on branch
  -> Pull request is opened against target branch
  -> PR id/url/status stored on change set
  -> Frontend polls job/change-set status
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-20 products | React SPA, FastAPI API, Postgres, Redis, one Celery worker is enough. |
| 20-200 products | Add dedicated Celery queues for imports and PR jobs, import scheduling, pagination, and per-project rate limiting. |
| 200+ products | Consider dedicated worker pools, incremental imports using commit hashes, and search service only if Postgres indexing is insufficient. |

### Scaling Priorities

1. **First bottleneck:** Bitbucket API throughput and repository scanning. Fix with explicit configured paths, cached commit heads, and incremental imports.
2. **Second bottleneck:** Review table filtering at high string counts. Fix with indexed Postgres queries and stable pagination before adding a separate search engine.
3. **Third bottleneck:** Celery queue contention between imports and PR creation. Fix with separate queues and worker concurrency limits.

## Anti-Patterns

### Anti-Pattern 1: UI Reads Directly From Bitbucket

**What people do:** Query Bitbucket every time a reviewer searches.
**Why it is wrong:** Slow, rate-limited, inconsistent, and cannot store comments/states reliably.
**Do this instead:** Import into canonical tables and keep Bitbucket as source of file truth.

### Anti-Pattern 2: One Serializer for Every Format

**What people do:** Parse to generic data and stringify everything back.
**Why it is wrong:** Android XML, Qt TS, JSON, and `.strings` have different escaping, comments, and metadata.
**Do this instead:** Use per-format adapters with fixtures and minimal edits.

### Anti-Pattern 3: Edits Immediately Commit

**What people do:** Commit each field edit as soon as it is saved.
**Why it is wrong:** Creates noisy history, partial updates, and review confusion.
**Do this instead:** Store edits as pending changes and submit grouped change sets.

### Anti-Pattern 4: Running Long Jobs In FastAPI Requests

**What people do:** Import repositories or create PRs inside a synchronous HTTP request.
**Why it is wrong:** Timeouts, duplicate submissions, poor retry behavior, and opaque failures.
**Do this instead:** Enqueue Celery tasks and expose job/change-set status through the API.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Bitbucket Cloud | REST API from FastAPI/Celery backend | Needs repository read/write and pull request write permissions. |
| Figma | Deferred API integration | Add after core review and PR workflow is stable. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| React frontend -> FastAPI | HTTP JSON API, OAuth2 bearer token | Frontend never talks to Bitbucket directly. |
| shadcn/ui components -> app features | Local imports from `frontend/src/components/ui` | Generated components are project-owned and can be adapted. |
| FastAPI -> Postgres | SQLAlchemy sessions | Alembic owns schema migrations. |
| FastAPI -> Celery | Redis broker | Mutations create jobs for imports/write-back. |
| Parser adapters -> canonical store | Typed service calls and Pydantic models | Parser output must be normalized and validated before upsert. |
| Celery jobs -> Bitbucket client | Backend-only REST calls | Secrets never leave backend/worker runtime. |

## Sources

- [FastAPI security docs](https://fastapi.tiangolo.com/tutorial/security/) - OAuth2 and bearer-token security model.
- [FastAPI OAuth2 with JWT docs](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) - OAuth2 token flow pattern.
- [Celery Redis docs](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html) - Redis as broker/backend.
- [Alembic docs](https://alembic.sqlalchemy.org/en/latest/) - SQLAlchemy migration tooling.
- [SQLAlchemy PostgreSQL dialect docs](https://docs.sqlalchemy.org/21/dialects/postgresql.html) - PostgreSQL support.
- [Vite getting started](https://vite.dev/guide/) - React TypeScript SPA tooling.
- [shadcn/ui introduction](https://ui.shadcn.com/docs) - open-code component model.
- [shadcn/ui Vite installation](https://ui.shadcn.com/docs/installation/vite) - Vite setup and component add workflow.
- [shadcn/ui monorepo docs](https://ui.shadcn.com/docs/monorepo) - optional shared UI package layout.
- [Bitbucket Cloud REST API intro](https://developer.atlassian.com/cloud/bitbucket/rest/intro/) - auth, tokens, scopes, OAuth request model.
- [Bitbucket Cloud source API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-source/) - source browse and commit behavior.
- [Bitbucket Cloud refs API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-refs/) - branch creation.
- [Bitbucket Cloud pull request API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pullrequests/) - pull request creation, comments, tasks, status endpoints.
- [Android string resources](https://developer.android.com/guide/topics/resources/string-resource) - Android XML string, array, plural resource shape and escaping requirements.
- [Qt TS file format](https://doc.qt.io/qt-6/linguist-ts-file-format.html) - TS schema, contexts, messages, translations, variants.
- [Apple String Resources](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/LoadingResources/Strings/Strings.html) - `.strings` key/value format, comments, uniqueness, encoding.
- [RFC 8259 JSON](https://www.rfc-editor.org/rfc/rfc8259.html) - JSON object/value/string rules and interoperability notes.

---
*Architecture research for: VerboFlex*
*Researched: 2026-05-04*
