---
phase: 04-localization-import-search-and-constraints
plan: 13
subsystem: translation-search-api
tags: [fastapi, pydantic, sqlalchemy, postgresql, pg-trgm, keyset-pagination, hmac]
requires:
  - phase: 04-localization-import-search-and-constraints
    plans: [10, 11]
    provides: stable active localization scopes, canonical translation identities, constraint projections, and immutable provenance
provides:
  - externally gated reversible PostgreSQL B-tree and trigram search indexes without extension ownership
  - literal case-insensitive ranked group search across active authorized datasets with exact five-filter semantics
  - HMAC-authenticated 50-group keyset cursors bound to principal, filters, scope versions, and total order
  - ordinary authenticated options, search, and complete grouped-detail API operations for every internal role
affects: [openapi-generation, generated-client, translation-search-ui, translation-detail-ui, constraint-ui]
actuals:
  tokens: 24127
  tasks: 2
  commits: 6
tech-stack:
  added: []
  patterns:
    - assert externally managed PostgreSQL capabilities before project-owned migration DDL
    - bind opaque keyset cursors to principal scope, canonical filters, dataset versions, and last total-order tuple
    - resolve grouped detail in one active-dataset SQL statement to avoid mixed activation snapshots
key-files:
  created:
    - backend/alembic/versions/0017_translation_search_indexes.py
    - backend/src/verboflex/services/translation_search.py
    - backend/src/verboflex/schemas/translations.py
    - backend/src/verboflex/api/v1/routes/translations.py
    - backend/tests/integration/test_translation_search.py
    - backend/tests/api/test_translations.py
  modified:
    - backend/src/verboflex/api/v1/router.py
    - backend/tests/integration/test_migrations.py
key-decisions:
  - "Every authenticated internal role is authorized for every active product; one shared active-product predicate is used by options, search, cursor scope, and detail."
  - "A group UUID is the stable lowest current value UUID for one raw-key and language group; non-leading member UUIDs are never accepted as detail identifiers."
  - "Search cursors use canonical JSON plus HMAC-SHA256 and bind principal, normalized query, all filters, fixed page size, active scope executions/versions, and the complete last ordering tuple."
  - "pg_trgm remains infrastructure-owned: revision 0017 only asserts the extension, similarity function, and GIN/GiST operator classes before creating or dropping six named project indexes."
  - "Grouped detail is selected in one statement from an exact active product/scope snapshot and returns every value, selector, state, constraint projection, tombstone, and current locator."
patterns-established:
  - "Search total order: rank, Unicode-stable casefolded raw key, exact canonical language, then opaque group UUID."
  - "Non-enumeration: unknown/inactive product filters return empty pages; absent/inactive/non-group detail UUIDs share one fixed 404."
  - "Explicit absence: nullable source/translated text, empty display text, no-max status, no pending change, and empty comments remain distinct public states."
requirements-completed: [SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, SRCH-07, SRCH-08]
coverage:
  - id: D1
    description: "Every authenticated role receives server-ordered active product/language options and searches all authorized active datasets without enumerating inactive or unknown products."
    requirement: SRCH-01
    verification:
      - kind: integration
        ref: backend/tests/api/test_translations.py#test_all_authenticated_roles_can_read_and_anonymous_callers_cannot
        status: pass
      - kind: integration
        ref: backend/tests/api/test_translations.py#test_options_are_server_ordered_and_exclude_inactive_datasets
        status: pass
    human_judgment: false
  - id: D2
    description: "Normalized literal key/source/translated-text search ranks exact, prefix, and partial groups deterministically without fuzzy matching or wildcard injection."
    requirement: SRCH-02
    verification:
      - kind: integration
        ref: backend/tests/integration/test_translation_search.py#test_search_groups_values_ranks_matches_and_preserves_mixed_state
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_translation_search.py#test_literal_wildcards_unicode_exact_filters_and_deleted_modes
        status: pass
    human_judgment: false
  - id: D3
    description: "Exact product, language, deleted, workflow-state, and constraint filters preserve complete matching groups and never silently widen invalid scope."
    requirement: SRCH-03
    verification:
      - kind: integration
        ref: backend/tests/integration/test_translation_search.py#test_state_and_constraint_filters_match_any_member_without_pruning_group
        status: pass
    human_judgment: false
  - id: D4
    description: "Mixed workflow states are explicit at group level while every member retains its individual draft, approved, or rejected state."
    requirement: SRCH-04
    verification:
      - kind: integration
        ref: backend/tests/api/test_translations.py#test_detail_projects_every_selector_constraint_provenance_and_absence
        status: pass
    human_judgment: false
  - id: D5
    description: "Server-owned group counts and per-value actual/maximum/source/status/overage projections distinguish over-limit, within-limit, and no-max values."
    requirement: SRCH-05
    verification:
      - kind: integration
        ref: backend/tests/integration/test_translation_search.py#test_search_groups_values_ranks_matches_and_preserves_mixed_state
        status: pass
      - kind: integration
        ref: backend/tests/api/test_translations.py#test_detail_projects_every_selector_constraint_provenance_and_absence
        status: pass
    human_judgment: false
  - id: D6
    description: "Search groups by raw key and language while detail preserves every stable value UUID, typed selector, safe structure object, and exact text absence."
    requirement: SRCH-06
    verification:
      - kind: integration
        ref: backend/tests/api/test_translations.py#test_detail_projects_every_selector_constraint_provenance_and_absence
        status: pass
      - kind: integration
        ref: backend/tests/api/test_translations.py#test_detail_never_accepts_a_non_group_member_uuid
        status: pass
    human_judgment: false
  - id: D7
    description: "Complete detail includes deleted state, repository/branch/path/side/format/commit/execution provenance, fixed pending-change absence, and empty comments without leaking inaccessible identities."
    requirement: SRCH-07
    verification:
      - kind: integration
        ref: backend/tests/api/test_translations.py#test_deleted_detail_remains_reachable_and_inaccessible_ids_do_not_enumerate
        status: pass
    human_judgment: false
  - id: D8
    description: "Opaque 50-group keysets use limit-plus-one, a complete stable tie tuple, canonical HMAC validation, and principal/filter/dataset replay rejection."
    requirement: SRCH-08
    verification:
      - kind: integration
        ref: backend/tests/integration/test_translation_search.py#test_keyset_cursor_is_bounded_tamper_proof_scope_bound_and_stale_safe
        status: pass
      - kind: integration
        ref: backend/tests/integration/test_translation_search.py#test_partial_search_plan_can_reach_project_owned_trigram_index
        status: pass
    human_judgment: false
duration: 1h 28min
completed: 2026-09-05
status: complete
---

# Phase 04 Plan 13: Translation Search and Grouped Detail API Summary

**PostgreSQL-backed literal translation search now returns stable authorized key-language groups through signed dataset-bound pagination and complete non-enumerating detail APIs.**

## Performance

- **Duration:** 1 hour 28 minutes, including the external `pg_trgm` precondition checkpoint
- **Started:** 2026-09-05T12:37:38Z
- **Completed:** 2026-09-05T14:05:47Z
- **Tasks:** 2
- **Files changed:** 8 implementation/test files, plus GSD tracking artifacts

## Accomplishments

- Added a reversible migration that fails before index DDL unless the externally managed `pg_trgm` capability is usable, and that creates/drops only six named project-owned indexes.
- Added bounded exact/prefix/partial literal search over raw keys, source text, and translated display text, grouped by raw key and language with any-member state/constraint/deleted semantics.
- Added canonical HMAC keyset cursors that bind the current principal, every normalized filter, the exact 50-row page size, active scope execution/version authority, and the last rank/key/language/UUID tuple.
- Added ordinary authenticated `listTranslationOptions`, `searchTranslations`, and `getTranslationGroup` operations with closed schemas, fixed errors, complete selector/constraint/provenance projections, and indistinguishable inaccessible IDs.

## Task Commits

The two TDD tasks and final cleanup were committed atomically:

1. **Task 1 RED: failing migration and search matrix** - `dae76cc`
2. **Task 1 GREEN: external capability indexes and bounded search service** - `ba80b2a`
3. **Task 2 RED: failing authenticated API and detail contracts** - `d7f264a`
4. **Task 2 GREEN: closed options/search/detail routes and schemas** - `e164e96`
5. **Task 2 correctness fix: complete constraint summary counts** - `674324d`
6. **REFACTOR: shared mixed-state summary projection** - `591db87`

**Plan metadata:** committed in the final documentation commit.

## Files Created/Modified

- `backend/alembic/versions/0017_translation_search_indexes.py` - Asserts the external trigram capability and owns only search indexes with symmetric downgrade.
- `backend/src/verboflex/services/translation_search.py` - Centralizes active-product authority, literal ranked search, cursor validation, bounded options, and single-statement grouped detail.
- `backend/src/verboflex/schemas/translations.py` - Defines closed, bounded filter, options, page, group, value, constraint, provenance, and error models.
- `backend/src/verboflex/api/v1/routes/translations.py` - Publishes the three ordinary authenticated operations with fixed error mapping.
- `backend/src/verboflex/api/v1/router.py` - Registers the translation router.
- `backend/tests/integration/test_migrations.py` - Covers extension ownership, absent/unusable capability failure, and upgrade/downgrade/re-upgrade symmetry.
- `backend/tests/integration/test_translation_search.py` - Covers rank/order/ties, Unicode/literal wildcards, group filters, deleted modes, trigram plans, and cursor replay/staleness.
- `backend/tests/api/test_translations.py` - Covers all roles, options, closed inputs, projections, explicit absence, deleted detail, and non-enumeration.

## Decisions Made

- Authorization is deliberately the single current rule from D-14: all authenticated roles see all active products. No product-grant table or role-specific search branch was invented.
- Group IDs reuse the stable lowest member UUID under a key-language identity. This remains opaque and stable because canonical imports preserve member identities as tombstones; non-leading member IDs return the same 404 as unknown IDs.
- Cursor payloads are not merely encoded: canonical payload bytes are HMAC-authenticated with the application signing secret and rejected on noncanonical base64, tampering, changed principal/filter/page size, or any active dataset-version change.
- Search uses current materialized constraint projections and returns aggregate over-limit/within-limit/no-max counts; it never recalculates or accepts client-owned constraint status.
- Detail performs one active-dataset SQL statement, so an activation transaction cannot produce mixed group identity, values, and locator provenance within one response.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test fixture authority] Seeded published mappings and source references through valid lifecycle order**
- **Found during:** Task 1 GREEN integration verification
- **Issue:** The new fixtures initially attempted to add a mapping beneath an already published revision and a source reference beneath a terminal execution, correctly triggering existing immutability guards.
- **Fix:** Seeded the mapping before publication and inserted the source reference while the execution was running, then transitioned to the successful active baseline.
- **Files modified:** `backend/tests/integration/test_translation_search.py`, `backend/tests/api/test_translations.py`
- **Verification:** Both focused search/API suites pass against real PostgreSQL.
- **Committed in:** `ba80b2a`, `d7f264a`

**2. [Rule 2 - Missing critical projection] Added complete group constraint counts**
- **Found during:** Task 2 final contract review
- **Issue:** Boolean over-limit/no-max flags could not support the required mixed-group `{violating} of {total}` presentation without client inference.
- **Fix:** Added authoritative over-limit, within-limit, and no-max member counts to the service and closed API schema.
- **Files modified:** `backend/src/verboflex/services/translation_search.py`, `backend/src/verboflex/schemas/translations.py`, `backend/src/verboflex/api/v1/routes/translations.py`, focused tests
- **Verification:** All 12 focused search and API tests pass.
- **Committed in:** `674324d`

---

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 2).
**Impact on plan:** Both fixes enforce existing database authority and complete the planned mixed constraint projection; no product scope or new dependency was added.

## TDD Gate Compliance

- RED commit `dae76cc` failed because revision 0017 and the translation search service did not exist; the migration capability/index and broad search behavior matrix failed at the intended seams.
- GREEN commit `ba80b2a` followed RED and passed the prescribed migration and search integration commands.
- RED commit `d7f264a` failed with 404 for the absent `/translations/options` route.
- GREEN commit `e164e96` followed RED and passed all six API contract tests.
- REFACTOR commit `591db87` centralized state-summary logic and retained all 12 focused search/API passes, Ruff formatting/lint, and strict typing.

## Automated Checks

- Prescribed migration gate: `7 passed, 14 deselected`.
- Search integration gate: `6 passed`.
- Translation API gate: `6 passed`.
- Complete backend integration regression: `334 passed`.
- Split localization unit regressions: `171 passed` importing, `181 passed` preview, and `85 passed` remaining unit/service tests.
- Remaining API/auth/core/CLI/architecture regression group: `428 passed, 2 downstream OpenAPI tests deselected`; five unrelated legacy/environment failures are recorded below.
- Project Ruff lint and full strict source mypy: passed.
- Focused Ruff format check across all Plan 04-13 files: passed.
- Static migration scan: no `CREATE EXTENSION`, `ALTER EXTENSION`, or `DROP EXTENSION` statement.
- Live FastAPI schema smoke: all three stable operation IDs are registered.
- Dependency integrity: `uv run --project backend pip check` passed.

## Issues Encountered

- Execution initially paused at the plan's blocking infrastructure precondition. The user enabled and verified `pg_trgm` 1.6, both trigram operator classes, and `similarity()` in the local application database; the isolated local test template was then enabled as authorized infrastructure setup. Alembic never manages the extension.
- The exact OpenAPI operation-set and checked-in export assertions now intentionally detect the three new operations. Plan 04-15 owns freezing that final inventory and regenerating the client after the remaining dependent backend plans.
- The already-recorded one-shot pytest basename collision prevents monolithic collection; running importing and preview directories separately covered the complete unit corpus.
- The broad regression still has three obsolete Phase-2 “translations must not exist” assertions and two worker smoke checks requiring Redis/Celery at `127.0.0.1:56379`; these pre-existing items were already recorded in `deferred-items.md`.
- Package-wide format check reports only existing drift in migrations 0011 and 0012; all touched files are formatted.

## Authentication Gates

None. The initial pause was an external database-capability precondition, not an authentication failure.

## User Setup Required

`pg_trgm` must be installed and usable by infrastructure in every development, CI, staging, and production database before revision 0017 runs. The local application and isolated test databases are verified; Alembic deliberately fails closed and never creates, alters, or drops the extension.

## Known Stubs

None. `pending_change: null` and `comments: []` are the explicitly required v1 read-only absence contract, not placeholders.

## Threat Flags

None beyond the plan's declared search-query, cursor, authorization, and detail-projection boundaries. Literal escaping, HMAC cursor binding, centralized active-product scope, fixed errors, bounded pages/options/detail, and non-enumerating lookups cover T-04-38 through T-04-41.

## Next Phase Readiness

- Plan 04-15 can freeze the three read operations in the exact OpenAPI inventory and regenerate the frontend client once its remaining backend dependencies complete.
- Plans 04-16 through 04-18 and 04-23 can consume stable options, group pages, aggregate counts, and complete detail projections without handwritten fetch contracts.
- Constraint mutation plans can reuse the same opaque group identity and server-owned per-value projection without changing search cursor authority.

## Self-Check: PASSED

All eight implementation/test artifacts, the summary, and all six ordered RED/GREEN/fix/refactor commits were verified on disk before state advancement.

---
*Phase: 04-localization-import-search-and-constraints*
*Completed: 2026-09-05*
