# Project Research Summary

**Project:** VerboFlex
**Domain:** Bitbucket-backed localization review and approval portal
**Researched:** 2026-05-04
**Confidence:** MEDIUM-HIGH

## Executive Summary

VerboFlex is closest to a focused translation management and review portal, but with a narrower and more repository-centered goal than broad platforms like Crowdin, Lokalise, Phrase, or Weblate. The critical product bet is not machine translation or full localization-suite breadth; it is making Bitbucket Cloud localization data searchable, reviewable, constrained, editable, commentable, and safely returned as pull requests.

The recommended architecture is a separated frontend/backend system: React + Vite + TypeScript for the review/admin UI, shadcn/ui as the project-owned component system, and Python + FastAPI for the backend API. PostgreSQL remains the primary database, Alembic owns schema migrations, Redis backs Celery, and Celery workers handle long-running imports, parser jobs, commits, and pull request creation. Bitbucket remains the file source of truth, while the app imports configured localization files into a canonical translation model for fast search, review states, comments, constraints, and audit history.

The biggest technical risk is file write-back. Android XML, Qt `.ts`, JSON, and iOS `.strings` all carry format-specific semantics, escaping, metadata, comments, or ordering concerns. Parser/writer support must be built with golden fixtures before PR automation is trusted.

## Key Findings

### Recommended Stack

Use a split stack: React 19 + Vite 8 + TypeScript 6 + shadcn/ui 4.6 for the frontend, and Python 3.14 + FastAPI 0.136 + Celery 5.6 + Redis + PostgreSQL 18 + SQLAlchemy 2 + Alembic 1.18 for the backend. Authentication should use OAuth2 bearer tokens through FastAPI's security model, with internal users and roles stored in PostgreSQL unless a future external OAuth2/OIDC provider is introduced.

**Core technologies:**
- React 19 + Vite 8 + TypeScript 6: dense frontend review/admin UI separated from the backend API.
- shadcn/ui 4.6 + Tailwind CSS 4: accessible, composable UI primitives installed as project-owned component code.
- FastAPI 0.136: API layer, OpenAPI docs, OAuth2 security dependencies, Pydantic validation.
- Celery 5.6 + Redis: background imports, parsing, Bitbucket write-back, PR creation, retries, and status tracking.
- PostgreSQL 18 + SQLAlchemy 2 + Alembic 1.18: durable relational model with versioned migrations.
- Python parser/writer adapters: format-specific handling for Android XML, Qt `.ts`, JSON, and iOS `.strings`.

### Expected Features

**Must have (table stakes):**
- Product/repository/branch configuration.
- Cross-repository key-to-translation mapping.
- Android XML, Qt `.ts`, JSON, and iOS `.strings` parser/writer support.
- Search by product, language, key/text, approval state, and max-length violations.
- Translation detail view with source text, translated text, state, constraints, comments, and file context.
- Edit, draft/approve/reject, and comment actions with role checks.
- Max length constraint model and violation calculation.
- Internal users with multiple roles.
- Bitbucket branch, commit, and PR creation.
- PR/change-set audit trail.

**Should have (competitive):**
- Mapping validation preview during admin setup.
- File/change preview before PR creation.
- Import and PR job status dashboard.
- Product-specific PR grouping behavior.

**Defer (v2+):**
- Figma screen context.
- Placeholder/plural/forbidden-character/line-count validators.
- External identity provider integration.
- Per-product approval gates.
- Machine translation, translation memory, glossary, and terminology management.
- Bitbucket Server/Data Center support.

### Architecture Approach

Build around a canonical translation model and parser/writer adapters. The React frontend searches local canonical records through FastAPI endpoints, not Bitbucket trees. Bitbucket integration runs only in the Python backend and Celery workers, handling repository reads, branch creation, commit creation, PR creation, and status capture. All write-back starts from a change set that groups edits according to product PR configuration.

**Major components:**
1. Product config - products, repositories, branches, formats, mappings, PR behavior.
2. FastAPI backend - OAuth2 auth, role checks, validation, services, persistence.
3. Celery workers - imports, refreshes, parser jobs, Bitbucket commits, PR creation, retries.
4. Bitbucket client - read files, create branches, create commits, open PRs.
5. Localization parser/writer registry - Android XML, Qt TS, JSON, iOS strings adapters.
6. Canonical translation store - searchable units, constraints, comments, states, audit trail.
7. Review UI - product/language/state/violation filters, detail editing, comments.
8. Change-set and PR service - grouped write-back and PR status.

### Critical Pitfalls

1. **Losing file semantics during write-back** - prevent with format-specific adapters and golden fixtures.
2. **Guessing repository mappings** - prevent with explicit admin configuration and validation previews.
3. **Writing from stale branch state** - store import commit/file hashes and verify before PR creation.
4. **Under-scoped Bitbucket tokens** - validate read/write/PR capabilities during setup.
5. **Comments detached from translation history** - store comments in the app against canonical translations.
6. **Repository-shaped UX** - search and review by product/language/state/violation, with file paths only as context.

## Implications for Roadmap

Based on fine-grained project settings, suggested phase structure:

### Phase 1: Application Foundation and Data Model
**Rationale:** All later work depends on users, products, repositories, branches, and canonical translation entities.
**Delivers:** Monorepo/workspace layout with separated `frontend/` and `backend/`, React/Vite shell, shadcn/ui initialization, FastAPI app, OAuth2 auth foundation, SQLAlchemy models, Alembic migrations, Postgres/Redis Docker setup, roles, base schema.
**Addresses:** Internal roles, product/repo config base.
**Avoids:** Undefined authorization and ad hoc config blobs.

### Phase 2: Product and Repository Mapping UI
**Rationale:** The project has non-standard direct and cross-repo localization structures.
**Delivers:** Product setup, Bitbucket workspace/repo config, source branch config, target branch config, cross-repo key/translation mapping, validation preview.
**Addresses:** Admin-configured repository links.
**Avoids:** Incorrect inferred mappings.

### Phase 3: Bitbucket Cloud Read Integration
**Rationale:** Imports require reliable Bitbucket auth, file browsing, branch reads, and permission checks.
**Delivers:** Credential storage, capability checks, repository tree/file reads, branch metadata, Celery import job skeleton.
**Uses:** FastAPI, Celery, Redis, Bitbucket REST API.
**Avoids:** Late discovery of token/scope failures.

### Phase 4: Localization Parser Foundation
**Rationale:** Search/review requires canonical translation records across four file formats.
**Delivers:** Android XML, Qt `.ts`, JSON, and iOS `.strings` parsers; canonical model; golden parse fixtures.
**Addresses:** Multi-format support.
**Avoids:** UI coupled to repository file formats.

### Phase 5: Import, Search, and Constraint Indexing
**Rationale:** Product managers need fast search without navigating Bitbucket.
**Delivers:** Celery import jobs, canonical upserts, FastAPI search endpoints, frontend filters for product/language/key/text/state/violations, max length validator.
**Addresses:** Search and constraint visibility.
**Avoids:** API-backed search and rate-limit pressure.

### Phase 6: Translation Review Workspace
**Rationale:** The core value depends on reviewing, editing, state changes, and comments.
**Delivers:** Dense shadcn/ui-based React review table, detail panel, edit flow, draft/approved/rejected state controls, per-translation comments, audit events, FastAPI role enforcement.
**Addresses:** Review portal workflow.
**Avoids:** Detached PR-only comments.

### Phase 7: Format-Safe Write-Back
**Rationale:** PR automation is unsafe until file edits preserve platform semantics.
**Delivers:** Writer adapters, minimal edit strategy where possible, golden before/after fixtures, stale source detection.
**Addresses:** Safe file modifications for all v1 formats.
**Avoids:** Large noisy diffs and corrupted localization files.

### Phase 8: Change Sets and Bitbucket PR Creation
**Rationale:** Final v1 value requires commits and pull requests through standard development workflow.
**Delivers:** Change-set grouping by product PR config, Celery write-back tasks, branch creation, commit creation, PR creation, PR audit/status UI, retry handling.
**Addresses:** End-to-end Bitbucket write-back.
**Avoids:** Partial writes and target-branch commits.

### Phase 9: Verification, Hardening, and Admin UX Polish
**Rationale:** The full loop needs reliable behavior before expansion.
**Delivers:** E2E tests, parser fixture expansion, permission edge cases, job dashboard basics, error handling, audit review.
**Addresses:** Operational confidence.
**Avoids:** "Looks done but isn't" failures.

### Phase Ordering Rationale

- Configure products before imports; imports before search; parser foundation before review; writer safety before PR creation.
- Comments and review states belong in the app's canonical model, not Bitbucket PR metadata.
- Bitbucket permission checks should land before users invest time reviewing translations that cannot be submitted.
- Celery/Redis should be introduced before Bitbucket imports and PR creation, not retrofitted after long-running endpoints exist.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** OAuth2 implementation detail: internal password flow with JWT vs external OAuth2/OIDC provider integration.
- **Phase 3:** Bitbucket Cloud auth mode, token type, least-privilege setup, and Celery retry/idempotency model.
- **Phase 4:** Format edge cases for Android XML arrays/plurals, Qt numerus, iOS `.strings` escaping/comments, and JSON duplicate keys.
- **Phase 7:** Minimal edit/write-back strategy per format.
- **Phase 8:** Product-specific PR grouping and stale branch handling.

Phases with standard patterns:
- **Phase 1:** React/Vite/shadcn frontend, FastAPI backend, Postgres/Alembic, Redis/Celery setup.
- **Phase 5:** Server-side search and indexed filters.
- **Phase 6:** Review UI, comments, and state transitions.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | User selected backend stack explicitly; versions were verified. OAuth2 flow details still need Phase 1 clarification. |
| Features | HIGH | User requirements align with common localization-platform table stakes. |
| Architecture | MEDIUM-HIGH | Canonical model plus adapters is a standard fit; write-back details need fixtures. |
| Pitfalls | HIGH | Main risks are well-defined: file preservation, mapping, stale branches, permissions, and comments/audit. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Bitbucket auth model:** Decide API token vs OAuth vs workspace/project/repository access token during Phase 3 planning.
- **Application OAuth2 model:** Decide whether v1 issues OAuth2 bearer JWTs for internal users or integrates with an external OAuth2/OIDC provider while preserving internal roles.
- **Exact JSON conventions:** Determine whether supported product JSON files are flat, nested, array-based, or mixed.
- **Qt TS editing scope:** Decide whether v1 edits all TS translations or only simple non-numerus translations.
- **PR grouping options:** Define allowed per-project PR behaviors before Phase 8.
- **Constraint ownership:** Define who can set max length and whether constraints are per key, per product, per language, or per file occurrence.

## Sources

### Primary (HIGH confidence)
- [FastAPI security docs](https://fastapi.tiangolo.com/tutorial/security/) - OAuth2 and bearer-token security model.
- [FastAPI OAuth2 with JWT docs](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) - OAuth2 token flow pattern.
- [Celery Redis docs](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html) - Redis as broker/backend.
- [Alembic docs](https://alembic.sqlalchemy.org/en/latest/) - SQLAlchemy migrations.
- [SQLAlchemy PostgreSQL dialect docs](https://docs.sqlalchemy.org/21/dialects/postgresql.html) - PostgreSQL support.
- [Vite getting started](https://vite.dev/guide/) - React TypeScript SPA tooling.
- [shadcn/ui GitHub repository](https://github.com/shadcn-ui/ui) - project, license, latest release.
- [shadcn/ui introduction](https://ui.shadcn.com/docs) - open-code component distribution model.
- [shadcn/ui Vite installation](https://ui.shadcn.com/docs/installation/vite) - Vite setup and CLI workflow.
- [Bitbucket Cloud REST API intro](https://developer.atlassian.com/cloud/bitbucket/rest/intro/) - auth, tokens, scopes.
- [Bitbucket Cloud source API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-source/) - file read and commit behavior.
- [Bitbucket Cloud refs API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-refs/) - branch creation.
- [Bitbucket Cloud pull request API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pullrequests/) - PR creation and comments.
- [Android string resources](https://developer.android.com/guide/topics/resources/string-resource) - Android string XML shape and escaping.
- [Qt TS file format](https://doc.qt.io/qt-6/linguist-ts-file-format.html) - Qt Linguist schema.
- [Apple String Resources](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/LoadingResources/Strings/Strings.html) - iOS `.strings` structure.
- [RFC 8259 JSON](https://www.rfc-editor.org/rfc/rfc8259.html) - JSON standard.

### Secondary (MEDIUM confidence)
- [Crowdin platform overview](https://crowdin.com/) - localization platform feature landscape.
- [Lokalise Bitbucket integration](https://lokalise.com/product/apps/code-repositories/bitbucket/) - Bitbucket sync workflow.
- [Weblate features](https://weblate.org/en/features/) - comments, review, context, formats.
- [Phrase Strings overview](https://phrase.com/platform/strings/) - key-based software localization and workflow features.

---
*Research completed: 2026-05-04*
*Ready for roadmap: yes*
