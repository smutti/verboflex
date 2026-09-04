# Phase 4: Localization Import, Search, and Constraints - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 converts localization content from published Bitbucket mappings into stable canonical translation records. It extends the existing strict preview detectors into complete import parsers for Android XML, Qt `.ts`, JSON, and iOS `.strings`; activates each mapping's canonical dataset atomically through Celery; preserves review context across safe refreshes; and exposes searchable translation groups, detail information, deletion visibility, and maximum-character constraints.

This phase does not let users edit translation text, manage comments, change review state, write localization files, or execute Bitbucket branches, commits, and pull requests. It may persist the identities and provenance needed for those later phases, but no provider mutation becomes executable here.

</domain>

<decisions>
## Implementation Decisions

### Format-specific structures and canonical presentation
- **D-01:** Import both scalar and structured localization values in v1: ordinary strings, Android and Qt plural/variant forms, Android arrays, and nested JSON string leaves. iOS support remains the configured `.strings` format; adding a separate `.stringsdict` format is not implied.
- **D-02:** Preserve every structured value as an individually addressable canonical value, while search results and detail presentation group those values by original key and language.
- **D-03:** Keep the repository key byte-for-byte as the logical key. Store plural quantity, array index, Qt variant, JSON path segment, or equivalent format detail as typed structured selectors rather than synthesizing dotted or bracketed key names. — **Reversibility:** costly — flattening selectors into keys later would change stable identities, search contracts, refresh matching, and eventual writer locators.
- **D-04:** Supported inline markup or other format structure must never be silently discarded. The parser must represent it without losing meaning or fail the mapping import atomically.
- **D-05:** A malformed, ambiguous, or unsupported file fails the complete mapping import. No partial dataset becomes visible; the last successful dataset remains active and the user receives a bounded list of actionable parser errors.
- **D-06:** A `separate` mapping remains one atomic boundary across its Keys and Translations sides, carrying forward the Phase 3 consistency rule.

### Stable identity, deletion, and refresh behavior
- **D-07:** A logical key is identified within its repository and configured branch; file path and in-file position are mutable locators, not identity. A canonical translated value additionally uses its language and structured selector so sibling variants cannot collide. The mapping/repository-side ownership already established by prior phases must prevent cross-mapping collisions. — **Reversibility:** one-way — changing this after persisted imports would require an identity migration and could detach review state, comments, constraints, and write-back provenance.
- **D-08:** Moving the same key between files preserves identity. Renaming a key is never inferred: the old identity becomes deleted and the new key becomes a new identity.
- **D-09:** Deleted keys are soft-deleted. They are excluded from normal results but remain searchable through a dedicated deleted filter with their review state, comments, constraints, and source provenance intact.
- **D-10:** If Bitbucket changes the translated value for an existing identity outside a VerboFlex-tracked change, import accepts the new value, retains comments and constraints, preserves the previous state in history, and moves the current translation to `Draft`.
- **D-11:** If an imported value exactly matches a future VerboFlex-tracked change merged through its pull request, it is not an external modification: the pending change can become synchronized and the translation remains `Approved`. A divergent merged value follows D-10 and returns to `Draft`.
- **D-12:** If the source text for a logical key changes, every associated target-language translation returns to `Draft`; existing translated text, comments, and constraints remain available for re-review.
- **D-13:** Phase 4 must leave a durable correlation seam for later change-set and PR phases to prove whether an imported value is the exact result of a VerboFlex submission. It must not guess origin from equal text alone or execute any provider write.

### Search and result loading
- **D-14:** The search page initially restores the user's last selected authorized product and provides an explicit `All products` option. A stale or unauthorized remembered selection must be discarded safely.
- **D-15:** Use one search field over original key, source text, and translated text. Matching is case-insensitive; exact matches rank before prefixes, prefixes before partial matches; fuzzy or typo-tolerant matching is excluded from v1.
- **D-16:** Initially restore the user's last selected available language and provide an explicit `All languages` option. Results remain grouped by key and language as defined by D-02.
- **D-17:** Use virtualized infinite scrolling backed by server-owned cursors and a deterministic stable order. Changing any search/filter dimension invalidates the loaded cursor chain; stale responses must not contaminate the new result set.
- **D-18:** The in-scope filters are product, language, approval state, maximum-length violation status, and deleted status. Normal results exclude deleted identities.

### Maximum-character constraints
- **D-19:** A key may have a maximum-character limit for each language. The base language supplies a dynamically inherited default; a target-language override remains independent when the base value changes. — **Reversibility:** costly — inheritance semantics affect stored overrides, violation recomputation, API payloads, and future approval gates.
- **D-20:** Count user-perceived Unicode characters (extended grapheme clusters), not code points or encoded bytes. A composed character or combined emoji counts once. Non-visible format markup is not counted as display text.
- **D-21:** Admin and Product manager/reviewer roles may create, edit, and remove maximum-character constraints. Translator and Viewer roles may read limits and violation status but may not mutate them.
- **D-22:** A violating translation may be retained and saved as `Draft`, but it cannot become `Approved` or be submitted for write-back while the violation remains. Phase 4 calculates and exposes this authoritative state; later workflow phases enforce it at their mutation boundaries.
- **D-23:** Recalculate effective limits and violation state after import, after a base-language limit changes, after an override changes or is removed, and through the later translation-edit boundary.

### the agent's Discretion
- Choose the exact SQLAlchemy tables, parser adapter interfaces, typed selector schema, UUID strategy, indexes, cursor encoding, virtual-list library, overscan/page size, and deterministic search tie-breakers, provided all decisions above remain observable and testable.
- Choose whether the last product/language selection is stored as a non-sensitive browser preference or a server-side user preference; authorization and current availability must always be revalidated server-side.
- Choose the precise configuration/storage point for the base language. Residual assumption: each mapping must resolve exactly one explicit or deterministic base language; missing or ambiguous base-language authority fails closed rather than silently choosing a locale.
- Choose concise bounded parser and search error copy consistent with the existing generated-client and shadcn patterns.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope and current phase
- `.planning/PROJECT.md` — project constraints, supported formats, background-job boundary, role model, and deferred capabilities.
- `.planning/REQUIREMENTS.md` — Phase 4 requirements FMT-01..04, FMT-06..08, SRCH-01..08, and CONS-01..05.
- `.planning/ROADMAP.md` — merged Phase 4 goal, success criteria, parser checkpoint, and boundaries with Phases 5–7.
- `.planning/STATE.md` — current position, accepted cross-phase decisions, and retained concerns.

### Prior phase decisions and parser contract
- `.planning/phases/02-admin-configuration/02-CONTEXT.md` — one-layout mappings, direct/separate topology, published revisions, automatic discovery, and atomic preview expectations.
- `.planning/phases/02-admin-configuration/02-RESEARCH.md` — A-02 encoding/shape matrices, strict preview grammars, and format structures deliberately deferred from preview to canonical parsing/write-back.
- `.planning/phases/03-bitbucket-import-integration/03-CONTEXT.md` — immutable commit baselines, mapping-local reconciliation, last-success preservation, manual retry behavior, and provider-write prohibition.

### Existing implementation seams
- `backend/src/verboflex/localization/preview/core.py` — deterministic locale/layout utilities and bounded preview candidate contracts; useful building blocks but not canonical records.
- `backend/src/verboflex/localization/preview/registry.py` — current four-format fail-closed detector registry.
- `backend/src/verboflex/localization/preview/android_xml.py` — strict Android preview grammar and hardened XML boundary.
- `backend/src/verboflex/localization/preview/qt_ts.py` — strict Qt preview grammar and locale extraction.
- `backend/src/verboflex/localization/preview/json.py` — duplicate-aware JSON preview shapes.
- `backend/src/verboflex/localization/preview/ios_strings.py` — bounded `.strings` lexer, escapes, and encoding behavior.
- `backend/src/verboflex/services/import_jobs.py` — logical import, immutable execution, active-baseline, rewrite-proposal, and atomic transition authority.
- `backend/src/verboflex/models/import_job.py` — durable mapping-level import and source-reference identities.
- `backend/src/verboflex/worker/import_tasks.py` — UUID-only Celery import execution and watchdog boundary.
- `backend/src/verboflex/schemas/imports.py` — existing bounded public import, baseline, capability, and reconciliation contracts.
- `frontend/src/features/workspace/WorkspaceOverviewPage.tsx` — authenticated workspace and role-aware generated-client consumption pattern.
- `frontend/src/router.tsx` — route integration and authenticated application shell.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- The four preview adapters already implement hardened decoding, deterministic locale/path detection, duplicate rejection, bounded parsing, and format-specific fixtures. Canonical parsers should share proven primitives where semantics match, without treating bounded preview samples as canonical data.
- `ImportJob`, immutable import executions, source references, movement classification, rewrite proposals, and the production Celery task already provide the mapping-level execution and last-success boundary that canonical activation can extend.
- Generated FastAPI/OpenAPI clients, authenticated routing, shadcn primitives, polling generation guards, and role-aware workspace patterns are available for search/detail UI integration.

### Established Patterns
- Provider source reads resolve opaque configured branches to immutable commits and never expose credentials or raw provider failures to the browser.
- Slow provider and parsing work is durable and Celery-owned; Redis carries identifiers rather than source content.
- FastAPI owns the canonical HTTP contract and the TypeScript client is generated, never hand-written.
- Published configuration and active import baselines change atomically; failed candidate work does not replace usable state.
- Browser request generations and server cursor bounds prevent stale asynchronous responses from becoming current UI authority.

### Integration Points
- Extend the existing production import processor after immutable source acquisition to parse, stage, validate, and atomically activate canonical translations for the exact mapping execution.
- Add canonical translation, structured selector, deletion/tombstone, effective constraint, and refresh-history persistence through SQLAlchemy and Alembic.
- Add authenticated search/detail/constraint routes to the v1 FastAPI router, regenerate OpenAPI and the TypeScript client, then integrate a translation workspace route into the existing application shell.
- Preserve future seams for review/comment state, pending changes, format-safe locators, and PR-origin correlation without implementing those later-phase operations here.

</code_context>

<specifics>
## Specific Ideas

- A renamed repository key is visibly modeled as one deleted key plus one newly added key; VerboFlex never guesses that the two are a rename.
- Deleted translations stay out of everyday search but remain deliberately discoverable through a filter.
- A VerboFlex PR that later appears unchanged on the source branch should read as synchronized and remain `Approved`, while an externally altered value returns to `Draft`.
- Infinite scrolling must remain virtualized and cursor-backed so large localization sets do not accumulate an unbounded DOM or rely on offset stability.
- “Characters” means what a user perceives on screen. Byte limits are encoding-dependent: for example, common kanji typically occupy three bytes in UTF-8 but two bytes in UTF-16.

</specifics>

<deferred>
## Deferred Ideas

- Add and delete localization keys from VerboFlex in a later phase; direct key rename remains excluded. Phase 4 only imports key additions/deletions observed in Bitbucket.
- Add a dedicated later phase for `max_bytes` constraints with an explicit encoding per mapping or file. This is separate from Phase 4's maximum-character contract.
- Editing translations, comments, state mutations, format-safe write-back, commits, and pull requests remain assigned to Phases 5–7.

</deferred>

---

*Phase: 4-Localization Import, Search, and Constraints*
*Context gathered: 2026-09-04*
