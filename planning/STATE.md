# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-04)

**Core value:** Product teams can quickly find, review, constrain, modify, comment on, and approve translations, then send approved changes back through the standard Bitbucket Cloud pull request workflow.
**Current focus:** Phase 1: Platform Foundation

## Current Position

Phase: 1 of 9 (Platform Foundation)
Plan: 0 of 5 in current phase
Status: Phase 1 UI-SPEC approved; ready to plan
Last activity: 2026-05-05 - Phase 1 UI design contract approved

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: N/A
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Platform Foundation | 0/5 | 0.0h | N/A |

**Recent Trend:**
- Last 5 plans: none
- Trend: N/A

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- V1 targets Bitbucket Cloud only.
- Frontend and backend are separate applications.
- Frontend uses React, Vite, TypeScript, and shadcn/ui.
- Backend uses Python, FastAPI, OAuth2, PostgreSQL, SQLAlchemy, and Alembic.
- Background work uses Celery and Redis.
- V1 supports Android XML, Qt `.ts`, JSON, and iOS `.strings`.
- V1 uses simple draft/approved/rejected review states and per-translation comments.
- Every phase closes with tests, code review, and deploy/build smoke verification.
- Figma, extra validators, external identity, and complex approval gates are deferred.

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 1 must decide OAuth2 detail: internal password flow with JWT vs future external OAuth2/OIDC provider boundary.
- Phase 3 must decide Bitbucket Cloud credential type and least-privilege scope model.
- Phase 4 must clarify JSON shape conventions and Qt `.ts` edit scope.
- Phase 8 must define exact allowed product-specific PR grouping options.

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

Last session: 2026-05-05 14:11 CEST
Stopped at: Phase 1 UI-SPEC approved; next step is Phase 1 planning
Resume file: .planning/phases/01-platform-foundation/01-UI-SPEC.md
