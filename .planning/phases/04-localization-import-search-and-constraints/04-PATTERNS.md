# Phase 04: Localization Import, Search, and Constraints - Pattern Map

**Mapped:** 2026-09-04
**Target groups classified:** 31
**Live analog coverage:** 29 / 31 target groups
**Source changes made:** None

This map treats the approved 04-CONTEXT.md and 04-UI-SPEC.md as authoritative. In particular, canonical import is deliberately separate from preview detection, the search result is a semantic flat list rather than a table, and parser diagnostics extend the existing Published Mapping Imports surface rather than creating a new screen.

## File Classification

| New/Modified File or Module | Role | Data Flow | Closest Live Analog | Match Quality |
|---|---|---|---|---|
| backend/src/verboflex/localization/importing/core.py | utility / domain contract | file-I/O, transform | backend/src/verboflex/localization/preview/core.py | role-flow match |
| backend/src/verboflex/localization/importing/registry.py | service / registry | batch, transform | backend/src/verboflex/localization/preview/registry.py | exact structural match |
| backend/src/verboflex/localization/importing/android_xml.py | parser utility | file-I/O, transform | backend/src/verboflex/localization/preview/android_xml.py | exact format, narrower semantics |
| backend/src/verboflex/localization/importing/qt_ts.py | parser utility | file-I/O, transform | backend/src/verboflex/localization/preview/qt_ts.py | exact format, narrower semantics |
| backend/src/verboflex/localization/importing/json.py | parser utility | file-I/O, transform | backend/src/verboflex/localization/preview/json.py | exact format, narrower semantics |
| backend/src/verboflex/localization/importing/ios_strings.py | parser utility | file-I/O, transform | backend/src/verboflex/localization/preview/ios_strings.py | near-exact parser match |
| backend/src/verboflex/localization/importing/__init__.py | package export | transform | backend/src/verboflex/localization/preview/__init__.py | exact |
| backend/src/verboflex/models/translation.py | model | CRUD, batch | backend/src/verboflex/models/import_job.py; backend/src/verboflex/models/product_mapping.py | role match |
| backend/src/verboflex/models/translation_constraint.py | model | CRUD | backend/src/verboflex/models/product_mapping.py | role match |
| backend/src/verboflex/models/{__init__,product_mapping,import_job}.py | model / metadata | CRUD, batch | the same files' existing ownership and currentness contracts | exact extension seam |
| backend/alembic/versions/0015_*.py (next revision; final name chosen by plan) | migration | batch | backend/alembic/versions/0012_import_jobs.py | role-flow match |
| backend/src/verboflex/services/translation_imports.py | service | batch, file-I/O | backend/src/verboflex/services/import_jobs.py | strong role-flow match |
| backend/src/verboflex/services/translation_search.py | service | request-response | backend/src/verboflex/services/products.py; import_jobs.py cursor codec | role match; ranking is new |
| backend/src/verboflex/services/translation_constraints.py | service | CRUD, transform | backend/src/verboflex/services/products.py | strong role match |
| backend/src/verboflex/services/{import_jobs,preview_jobs,products}.py and worker/import_tasks.py | service / worker | batch, event-driven | existing finalizer, confirmation, clone, and UUID-only worker paths | exact extension seams |
| backend/src/verboflex/schemas/translations.py | config / schema | request-response | backend/src/verboflex/schemas/imports.py; schemas/previews.py | exact structural match |
| backend/src/verboflex/schemas/{imports,previews}.py and api/v1/routes/{admin_previews,admin_mappings}.py | schema / controller | request-response | the same files' current closed projections | exact extension seams |
| backend/src/verboflex/api/v1/routes/translations.py and api/v1/router.py | controller / route | request-response | backend/src/verboflex/api/v1/routes/admin_products.py; routes/users.py | strong role-flow match |
| backend/tests/fixtures/localization/** and tests/unit/localization/importing/test_*.py | fixture / test | file-I/O, transform | backend/tests/unit/localization/preview/test_*.py | exact format test match |
| backend/tests/unit/localization/test_grapheme_count.py | test | transform | no production or test analog | no analog |
| backend/tests/integration/test_translation_{import_activation,search,constraints}.py, tests/api/test_translation*.py, and test_migrations.py | integration / API / migration test | batch, CRUD, request-response | test_import_jobs.py; test_admin_mappings.py; test_migrations.py | strong role-flow match |
| backend/tests/api/test_openapi_contract.py, frontend/openapi.json, frontend/src/api/client/**, and frontend API contract tests | generated contract | request-response | existing OpenAPI export/generation/contract pipeline | exact |
| frontend/package.json and package-lock.json | config | build | current exact-pinned dependency policy | exact extension seam |
| frontend/src/features/translations/useTranslationSearch.ts | hook | request-response | frontend/src/features/admin/useCursorCollection.ts; useImportPolling.ts | strong role-flow match |
| frontend/src/features/translations/translationPreferences.ts | utility / store | event-driven, transform | none; production code currently does not persist preferences | no analog |
| frontend/src/features/translations/{TranslationsWorkspace,TranslationSearchPage,TranslationDetailPage,TranslationFilters}.tsx | component / route | request-response | WorkspaceOverviewPage.tsx; ProductPreviewPage.tsx | role match |
| frontend/src/features/translations/TranslationResultList.tsx | component | request-response, virtualized rendering | PublishedMappingImports.tsx for bounded row content only | partial; virtualization is new |
| frontend/src/features/translations/MaximumLengthDialog.tsx | component / dialog | CRUD, request-response | RewrittenBaselineDialog.tsx; UserDialog.tsx | strong role-flow match |
| frontend/src/{App,router}.tsx and components/layout/AppShell.tsx | route / shell | request-response | current authenticated and admin route trees/navigation | exact extension seam |
| frontend/src/features/admin/imports/PublishedMappingImports.tsx and features/admin/previews/ProductPreviewPage.tsx | component | request-response, event-driven | the same files | exact extension seams |
| frontend/src/features/translations/*.test.tsx, router/AppShell/admin tests, and frontend/e2e/translations.spec.ts | test | request-response, event-driven | useCursorCollection.test.ts; ProductPreviewPage.test.tsx; PublishedMappingImports.test.tsx; admin-configuration.spec.ts | strong role-flow match |

## Pattern Assignments

### Canonical localization import package

**Targets:** backend/src/verboflex/localization/importing/{core,registry,android_xml,qt_ts,json,ios_strings,__init__}.py

Use the preview package for input safety, deterministic ordering, and format grammar, but not for its partial-output semantics. Preview samples are explicitly noncanonical and capped. The new import contract must return all canonical scalar/structured values for the confirmed layout or a closed mapping-level failure.

| Target | Primary Analog | Concrete Pattern to Copy | Required Canonical Delta |
|---|---|---|---|
| core.py | localization/preview/core.py:45-100, 247-305, 433-484 | immutable frozen/slots records; canonical JSON with sorted keys and compact separators; deterministic UUID/digest; validate untrusted output before persistence | model raw key bytes/text separately from typed selector; carry language, selector, source locator, markup status, and closed issue category; do not cap canonical records |
| registry.py | localization/preview/registry.py:20-55 | tupleize inputs once, reject overlapping claims/IDs, return stable sorted results | dispatch only the already-confirmed format/layout and require exactly one complete parser result |
| android_xml.py | localization/preview/android_xml.py:47-88, 147-215 | strict UTF/BOM declaration checks, defused XML with DTD/entities/external access disabled, sorted files, byte budgets, duplicate rejection | add Android plurals, arrays, and markup preservation; unsupported or ambiguous constructs fail the complete mapping |
| qt_ts.py | localization/preview/qt_ts.py:45-62, 104-150, 191-244 | strict decode, defused XML, exact TS root/version, deterministic context traversal, duplicate rejection | add context-aware IDs, numerus/variants, status handling, and markup preservation according to the research contract |
| json.py | localization/preview/json.py:34-70, 73-115, 157-188 | strict decode, duplicate-aware object_pairs_hook, non-finite constant rejection, sorted/bounded file traversal | recursively accept string leaves only; retain a typed JSON-path selector while preserving the raw key identity |
| ios_strings.py | localization/preview/ios_strings.py:21-53, 63-210, 249-335 | BOM-qualified decoding, single-pass lexer, source spans, comments/escapes/surrogate validation, exact duplicate detection | emit the complete canonical set and retain spans/lexical metadata needed for later minimal edits |

The preview core pattern to preserve is an immutable boundary:

    @dataclass(frozen=True, slots=True)
    class PreviewSample:
        ...

    @dataclass(frozen=True, slots=True)
    class PreviewLayoutCandidate:
        ...

The canonical package should use its own names and version. Do not import PreviewSample or treat preview keys/samples as authoritative translation data.

**Tests to copy:**

- backend/tests/unit/localization/preview/test_android_xml.py:43-89 asserts deterministic immutable output; 141-171 covers DTDs, duplicates, and unsupported structures; 205-230 tests exact byte boundaries; 281-292 fuzzes arbitrary bytes without leaking exceptions.
- Corresponding Qt/JSON/iOS preview tests use parameterized encodings, malicious grammar, duplicate keys, peer-file atomicity, deterministic ordering, budget boundaries, and Hypothesis arbitrary-byte inputs. Create golden canonical fixtures with explicit expected records rather than regenerating expected values through production code.
- Add one conformance suite that feeds every adapter through the same contract: stable order, stable identity, exact selector typing, closed failures, no partial dataset, and no raw-source/provider secret in diagnostics.

### Translation domain models and Alembic migration

**Targets:** models/translation.py, models/translation_constraint.py, models/import_job.py, models/product_mapping.py, models/__init__.py, and the next Alembic revision.

**Primary analogs:**

- models/product_mapping.py:25-66 for named check constraints, natural uniqueness, and consistency checks; 68-111 for UUID/timestamp/current authority fields; 113-126 for cascade/ordered relationships.
- models/import_job.py:27-144 for owned composite foreign keys and current execution pointers; 147-270 for immutable execution/source-reference history and deterministic position constraints.
- models/__init__.py:1-42 for the complete metadata import/export list. New tables must be imported here before Alembic/test metadata is evaluated.
- alembic/versions/0012_import_jobs.py:1-17 for revision metadata; 82-317 for tables, named checks, composite/deferrable ownership foreign keys, indexes, and insert guards; 320-354 for symmetric downgrade.

Model the identities as separate database concepts:

- group identity: repository + configured branch + raw key;
- value identity: group + language + typed selector;
- locator: file path/span/position, mutable without changing identity;
- lifecycle: active/deleted tombstone and external-source revision/current dataset ownership;
- constraint: group-level default maximum plus optional per-target-language override, actor, timestamp, and optimistic version.

Do not collapse raw keys into normalized display keys and do not use mutable file paths in unique identity. A move updates locators; a rename tombstones the old group and inserts a new one.

The migration should follow the live explicit style, not autogenerated anonymous constraints:

    revision: str = "0012_import_jobs"
    down_revision: str | None = "0011_active_revision_revalidations"

    def upgrade() -> None:
        ...

    def downgrade() -> None:
        ...

Choose the actual next revision ID/name during planning, with down_revision set to 0014_import_source_reference_insert_guard. Add indexes for the exact search/filter/order plan, including pg_trgm only if the dependency checkpoint is accepted.

**Migration tests:** extend backend/tests/integration/test_migrations.py. Lines 232-258 show the required shape: upgrade to head, prove malformed writes roll back atomically, then assert Base.metadata contains every table. Lines 579-652 show revision-by-revision upgrade and named constraint/index inspection. Also exercise downgrade/upgrade round-trip and forged cross-product/cross-execution ownership.

### Atomic import activation and worker integration

**Targets:** services/translation_imports.py, services/import_jobs.py, models/import_job.py, worker/import_tasks.py, and translation import integration tests.

**Primary analog:** services/import_jobs.py.

- Lines 575-671 lock connection generation, published revision, mapping, and ordered repository sides.
- Lines 1286-1390 validate the complete reference set and derive a canonical digest from all currentness inputs.
- Lines 1570-1745 finalize inside one database transaction: re-lock durable authority, fail closed, retain the old baseline on failure, and only then move the current/baseline projection.
- Lines 2060-2102 confirm a rewrite and move its baseline under the same transaction.
- Lines 2215-2302 isolate provider processing from durable finalization.

Preserve the transaction shape used by preview confirmation (services/preview_jobs.py:825-898):

    with session.begin():
        row = session.execute(
            select(PreviewJob).where(PreviewJob.id == job_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise PreviewJobNotFound("preview job unavailable")
        if _current_failure_code(session, row, for_update=True) is not None:
            raise PreviewJobConflict("preview identity conflict")
        ...
        session.flush()

For Phase 4, parsing and staging may happen before finalization, but activation of the complete direct dataset or the complete keys+translations pair must occur in the same final transaction that advances the successful baseline. A parser failure records bounded closed issues and leaves the last successful active dataset/baseline untouched. Rewrite confirmation must invoke the same canonical activation path; otherwise the baseline pointer and searchable dataset can diverge.

Keep worker transport UUID-only. worker/import_tasks.py:85-111 is the exact pattern: enqueue an import UUID, configure the Celery task with late acknowledgement/worker-loss rejection/time limits/JSON serialization, reconstruct dependencies in the worker, and let the worker own and close its adapter. Do not serialize source bytes, parsed records, credentials, or SQLAlchemy objects through Celery.

**Integration tests to copy:**

- test_import_jobs.py:1051-1090 proves a same-commit refresh retains the baseline pointer.
- test_import_jobs.py:1093-1145 proves failed refresh/retry keeps the previous complete baseline.
- test_import_jobs.py:1551-1650 proves separate keys and translations activate as one ordered baseline.
- test_import_jobs.py:2917-3010 proves rewrite confirmation moves durable authority atomically.
- Add Phase 4 assertions that the active translation dataset follows the same pointer in each case, including one-side parser failure and malformed/unsupported source.

### Base-language confirmation seam

**Targets:** models/product_mapping.py, services/preview_jobs.py, services/products.py, schemas/previews.py, routes/admin_previews.py, and ProductPreviewPage.tsx.

The current confirmation request is a closed compare contract (schemas/previews.py:41-48):

    class AdminPreviewConfirmationRequest(BaseModel):
        model_config = ConfigDict(extra="forbid")

        preview_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
        layout_candidate_id: UUID
        layout_candidate_version: Literal[1]

Add base_language to the candidate and active-revalidation confirmation request/response identities. Validate it against the selected candidate's detected languages on the server, store it on the mapping, include it in idempotent equality/currentness checks, and clone it with the mapping in services/products.py:184-251. Do not trust the UI Select as authority.

The current service already locks and revalidates the full confirmation before assignment (services/preview_jobs.py:825-898), while is_current_preview_confirmation at 1016-1070 and _mapping_has_complete_confirmation/_confirmed_layout_matches at 1208-1287 recompute currentness. Extend all of those together; updating only the Pydantic payload would create stale confirmations.

The route pattern is routes/admin_previews.py:281-313:

    confirmation = confirm_preview_job(
        session,
        job_id=job_id,
        preview_digest=payload.preview_digest,
        layout_candidate_id=payload.layout_candidate_id,
        layout_candidate_version=payload.layout_candidate_version,
        actor_id=principal.user_id,
    )

ProductPreviewPage.test.tsx:1212-1254 verifies that publication remains disabled until backend confirmation succeeds and asserts the exact generated-client request body. Extend that assertion with base_language. Add cases for one detected language (deterministic default), multiple languages (required explicit selection), a stale/foreign language, duplicate submits, and rejected confirmation. Lines 1792-1851 are the existing duplicate/stale bounded-error pattern.

### Search, detail, and maximum-length services

**Targets:** services/translation_search.py, services/translation_constraints.py, schemas/translations.py, routes/translations.py, and api/v1/router.py.

Use services/products.py:47-82 for immutable record/page/cursor types, 393-444 for bounded canonical cursor decoding, and 447-496 for limit+1 keyset pagination. The stronger cursor authority test is test_import_jobs.py:3420-3505: cursors are opaque, at most 2048 characters, preserve server order, and are rejected when reused with another product/filter or malformed encoding.

The translation cursor must bind:

- active canonical dataset/version;
- product, selected languages, workflow states, violation state, deleted state, and normalized query;
- complete server ordering, including exact/prefix/partial rank and deterministic final identity tie-breakers;
- fixed page size 50.

There is no live analog for literal-safe wildcard search or pg_trgm ranking. Implement the RESEARCH.md SQL plan directly: exact before prefix before partial, escape user percent/underscore/backslash as literals, and add deterministic tie-breakers. Do not let the client re-sort appended pages.

Use schemas/imports.py and schemas/previews.py throughout for closed contracts: ConfigDict(extra="forbid"), Annotated Field bounds, Literal state/error vocabularies, bounded lists, and nullable fields only where absence is a real state. Parser issues exposed on an import row must use a closed category, bounded safe message, location metadata, and at most five displayed issues.

Use routes/admin_products.py:166-199 for list endpoint structure: bounded Query parameters, typed service records projected into response models, invalid cursor mapped to a bounded 422, and no raw database/provider exception text. Register the new router exactly as api/v1/router.py:5-30 imports/includes existing modules.

All authenticated roles can read translation search/detail/constraint values. Compose the mutating dependency from auth/principal.py:127-143 and the existing role contract:

    ConstraintPrincipal = Annotated[
        Principal,
        Depends(
            require_roles(
                RoleName.ADMIN,
                RoleName.PRODUCT_MANAGER_REVIEWER,
            )
        ),
    ]

backend/tests/auth/test_roles.py:23-35 proves that require_roles accepts either configured role and returns the exact generic 403 for a viewer. Add route-level tests proving translator/viewer read access, admin/product_manager_reviewer mutation access, and translator/viewer mutation denial.

Maximum-length writes follow services/products.py:98-151 and 254-319: begin a transaction, lock the authoritative row, compare expected_version, write/flush, map IntegrityError to a closed conflict, and return a fresh server projection. The backend recomputes violations using grapheme clusters; the frontend count is display guidance only. Null removal restores inherited/default behavior.

### Generated API client contract

**Targets:** frontend/openapi.json, frontend/src/api/client/**, frontend API contract tests, backend test_openapi_contract.py, package scripts.

Do not hand-edit generated client files or add a handwritten fetch wrapper. The existing workflow is:

1. backend/scripts/export_openapi.py writes deterministic app.openapi() JSON;
2. frontend/package.json api:schema exports the schema;
3. api:generate runs openapi-ts.config.ts;
4. api:check regenerates and fails on a git diff;
5. frontend/src/api/config.ts keeps the generated fetch client on the relative API base with credentials included.

backend/tests/api/test_openapi_contract.py:368-380 owns the exact path/operation/status/security inventory. Extend EXPECTED_OPERATIONS for every translation read/mutation and import projection change. Mirror frontend/src/api/admin-client-contract.test.ts:692-763 by asserting bearer auth, URL/path/query encoding, method/body, and that tokens never enter URL or body; mirror 799-844 for exact generated types and forbidden sensitive properties.

### Translation search hook and preference storage

**Targets:** useTranslationSearch.ts and translationPreferences.ts.

Use useCursorCollection.ts:79-231 as the hook skeleton:

- generation, AbortController, and in-flight refs are authority;
- the queryKey contains the complete query identity;
- changing identity aborts and ignores the old success or failure;
- append in response order and deduplicate only by stable group identity;
- bound duplicate load-more actions;
- preserve already-visible rows when an appended page fails;
- expose distinct initial-error and load-more-error states.

The tests are especially reusable. useCursorCollection.test.ts:63-100 verifies 50-row first-page append and stable-ID deduplication. Lines 102-140 prove that changing the full query identity aborts and ignores stale pages. Lines 142-205 cover initial recovery, load-more retry, duplicate actions, append, and upsert. Lines 207-233 prove obsolete failures cannot replace successor state.

Phase 4 adds a 200 ms query debounce, fixed 50-group pages, explicit Load more, and stricter cursor-chain validation already demonstrated in PublishedMappingImports.tsx:482-568 (reject empty/repeated cursors and impossible page shapes). Clear the visible list immediately when any filter/query identity changes. Never re-sort a completed server page in the browser.

There is no production persistence analog. translationPreferences.ts must be a small, isolated, fail-closed module with tests for corrupt/unavailable storage. Key preferences by the authenticated principal ID and persist only selected product ID and selected language IDs. Do not persist query text, translation/source content, constraint values, tokens, or user role data.

### Translation routes, flat list, and shell navigation

**Targets:** TranslationsWorkspace.tsx, TranslationSearchPage.tsx, TranslationDetailPage.tsx, TranslationFilters.tsx, TranslationResultList.tsx, App.tsx, router.tsx, and AppShell.tsx.

Use router.tsx:90-150 for authenticated session routing and 152-223 for nested route composition. Add /translations and /translations/:translationGroupId as ordinary authenticated routes, not admin routes. Preserve the admin guard unchanged. App.tsx currently renders the ordinary workspace directly, so refactor the ordinary branch into route elements instead of nesting translation URLs under /admin.

Use AppShell.tsx:54-70 for destination/match definitions and 168-203 for the shared desktop/mobile navigation source. Add Translations immediately after Workspace for every authenticated role. AppShell.test.tsx:452-520 checks desktop aria-current and mobile Sheet focus restoration; lines 523-549 assert exact destination order and must become Workspace, Translations, then the existing administration links.

Use WorkspaceOverviewPage.tsx:67-137 for generated-client requests with generation checks and 248-313 for restrained bordered content hierarchy. TranslationResultList is not a table: follow the UI-SPEC semantic list/article contract, preserving backend order. PublishedMappingImports row rendering may be copied only for bounded metadata/badge/overflow treatment, not its table semantics.

There is no live @tanstack/react-virtual/useWindowVirtualizer implementation. After the required human dependency checkpoint, use the approved UI contract verbatim: useWindowVirtualizer, estimateSize 288, overscan 8, useFlushSync false, and manual Load more. Add exact version pins in both package.json and package-lock.json; do not use a range. If the checkpoint rejects the dependency, planning must revisit the approved UI contract rather than silently substituting a different virtualizer.

The detail route must be deep-linkable and preserve the search workspace's server-authoritative query state when navigating back. Tests should use semantic roles/list items rather than DOM position generated by the virtualizer.

### Maximum-length dialog

**Target:** frontend/src/features/translations/MaximumLengthDialog.tsx

Use UserDialog.tsx:43-161 for controlled fields, validation, generated-client submit, and focus-on-error. Use the stronger pending authority from RewrittenBaselineDialog.tsx:248-260 and 380-489: pair React state with a synchronous request ref, attach an AbortController/generation, validate response identity, show only bounded errors, and announce success only after the backend commits.

For the required non-dismissable pending state, copy the AlertDialog behavior at RewrittenBaselineDialog.tsx:492-500 and 623-640:

- disable Save/Remove/Cancel while the request ref is active;
- set aria-busy on the active action;
- prevent Escape and outside-pointer dismissal while pending;
- keep duplicate Enter/click submissions from starting a second request;
- restore focus to the originating list action after close;
- on 409/version mismatch, retain the user's value, announce a bounded conflict, and require refresh/retry.

The removal confirmation can follow UsersPage.tsx:628-675 for a focused Alert, disabled paired actions, and aria-busy. Do not optimistically change the row's displayed limit or violation count.

### Existing admin surfaces

**Targets:** PublishedMappingImports.tsx and ProductPreviewPage.tsx, plus their tests.

For parser failure, extend the existing row-owned error projection in PublishedMappingImports.tsx:266-303 and both render paths: desktop table at 850-946 and mobile articles at 948-1016. Preserve bounded opaque path/branch rendering from 192-224 and current baseline visibility from 226-263. Show at most five safe issues and retain the active successful baseline when the newest attempt fails.

PublishedMappingImports.test.tsx:345-405 is the state/action matrix; add parser failure state/category and issue assertions there. Lines 500-530 prove a failed refresh still displays the successful baseline. Lines 682-755 prove old/unmounted mutations cannot toast, replace current rows, or steal focus.

For base language, extend ProductPreviewPage.tsx around candidate selection/details at 268-374 and confirmation at 431-466/546-603. Source Select options only from the selected candidate's detected languages. One option is deterministic; multiple options require an explicit choice. Send the selected language as part of the confirmation identity and render backend confirmation as authority.

## Shared Patterns

### Durable authority and atomicity

**Sources:** services/import_jobs.py:575-671, 1570-1745, 2060-2102; services/preview_jobs.py:825-974.

Apply to canonical activation, rewrite confirmation, base-language confirmation, and constraint mutation. Lock owner pointers before children, re-read exact version/generation/digest identity, persist related rows, flush, and advance the visible pointer inside one transaction. On any parsing/currentness/constraint error, leave the prior successful projection intact.

### Closed validation and bounded errors

**Sources:** schemas/imports.py, schemas/previews.py:23-48 and 65-145; routes/admin_previews.py:172-207.

All input models forbid extras and bound strings/lists/numbers. Convert service errors to stable 401/403/404/409/422/503 details. Never render or return source bytes, credentials, exception repr, provider payloads, SQL, or parser tracebacks.

### Authorization

**Sources:** auth/principal.py:106-143; routes/users.py:22-51; tests/auth/test_roles.py:23-35.

Every translation route requires a database-resolved bearer principal. Reads accept all authenticated roles. Constraint mutations use the explicit admin-or-product_manager_reviewer dependency. UI visibility is convenience only; the API is authoritative.

### Pagination and stale work

**Sources:** services/products.py:393-496; services/import_jobs.py:368-434, 838-940; useCursorCollection.ts:79-231; useImportPolling.ts:56-203.

Bind opaque cursors to complete filters/order/authority, use limit+1, and reject malformed/replayed contexts. On the frontend, use generation + abort + exact response identity; stale successes and stale failures are both no-ops.

### Generated network boundary

**Sources:** backend/scripts/export_openapi.py; frontend/openapi-ts.config.ts; package.json api:* scripts; api/config.ts.

Backend schemas/routes are the source of truth. Regenerate schema/client, then compile/test. Feature components import generated SDK functions/types and pass the in-memory bearer token only through auth configuration.

### Accessible async UI

**Sources:** AppShell.tsx; RewrittenBaselineDialog.tsx; PublishedMappingImports.tsx.

Use semantic headings/list/articles, visible labels, aria-current, focused role=alert, aria-live for async completion, 44px controls, bounded horizontal overflow for opaque values, pending duplicate guards, and deterministic trigger-focus restoration.

## No Close Analog Found

| Target / Concern | Role | Data Flow | Planner Guidance |
|---|---|---|---|
| Canonical translation group/value/tombstone schema | model / domain | batch, CRUD | Reuse SQLAlchemy ownership/check conventions only. Derive exact identities and lifecycle from CONTEXT.md/RESEARCH.md; preview samples are not an analog. |
| Grapheme-cluster counting and violation recomputation | utility / service | transform | No regex/grapheme implementation exists. Use the researched regex dependency only after its human checkpoint, centralize one backend function, and add Unicode golden/property tests. |
| Exact > prefix > partial translation ranking with literal wildcard escaping and pg_trgm | service / migration | request-response | No repository query implements this. Follow RESEARCH.md SQL/index plan and test percent, underscore, backslash, Unicode, ties, cursor continuation, and explain/index behavior. |
| useWindowVirtualizer result list | component | virtualized rendering | No package or live component exists. Follow the approved UI-SPEC constants after the dependency checkpoint; do not imitate the existing HTML table. |
| Principal-scoped local preference persistence | utility / store | event-driven | No production storage wrapper exists. Build a narrow fail-closed module and prove it cannot store tokens/query/content. |

## Test Pattern Matrix

| New Behavior | Closest Test Analog | Required Reuse |
|---|---|---|
| Four canonical parsers | tests/unit/localization/preview/test_*.py | golden outputs, encoding matrix, malicious inputs, duplicate/ambiguity, byte boundaries, peer atomicity, Hypothesis no-crash |
| Atomic dataset activation | tests/integration/test_import_jobs.py:1051-1145, 1551-1650, 2917-3010 | old dataset retention, paired-side activation, rewrite parity, exact pointers |
| Translation cursor/search | test_import_jobs.py:3420-3505; useCursorCollection.test.ts:63-140 | opaque bounded cursor, full filter binding, server order, stale page abort/ignore |
| Constraint authorization/versioning | tests/auth/test_roles.py:23-35; admin product service/API tests | either allowed role, viewer/translator denial, expected_version conflict, null removal |
| Schema/client drift | backend/tests/api/test_openapi_contract.py:368-380; frontend/src/api/admin-client-contract.test.ts:692-844 | exact operations/security/status, generated URL/body/type and secret-exclusion assertions |
| Base language confirmation | ProductPreviewPage.test.tsx:1212-1254, 1792-1851 | backend-success authority, exact request identity, duplicate submit, bounded rejected response |
| Parser errors in import row | PublishedMappingImports.test.tsx:345-405, 500-530, 682-755 | desktop/mobile state, prior baseline retained, stale/unmounted work ignored, focus preserved |
| Ordinary translations routing/nav | router.test.tsx:268-367; AppShell.test.tsx:452-558 | all authenticated roles, no admin routing, deep links, aria-current, exact nav order, mobile focus |
| Maximum-length dialog | RewrittenBaselineDialog.test.tsx and UsersPage dialog tests | synchronous duplicate guard, no pending dismissal, 409 retention, abort/unmount, focus restoration |
| Virtualized flat list | no analog | test semantic list content/order, overscan behavior without DOM-index assumptions, manual load-more, reduced viewport/mobile |
| End-to-end workflow | frontend/e2e/admin-configuration.spec.ts:1679-1955, 3785-4020 | generated-route fakes, desktop/mobile access, keyboard focus, import refresh/error behavior, secret-free UI |

## Metadata

**Analog search scope:** backend/src, backend/alembic/versions, backend/tests, frontend/src, frontend/e2e, frontend package/OpenAPI configuration.

**Unique paths scanned:** 242 across the application/test scope; 182 source/config paths and 80 detected test specifications (categories overlap because frontend tests live under frontend/src).

**Strong analog clusters used:** preview parsers, SQLAlchemy/Alembic ownership, import finalization/Celery, versioned list/mutation services, FastAPI/Pydantic/auth, generated OpenAPI client, abortable cursor hooks, accessible dialogs/routes/admin rows.

**Pattern extraction date:** 2026-09-04
