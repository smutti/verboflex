# Phase 5: Review Workspace and Comments - Context

**Gathered:** 2026-09-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 turns the existing read-only translation search and detail experience into the core VerboFlex review workspace. Authorized users can create per-language pending translation proposals, move them through Draft, Approved, and Rejected states, discuss a specific key-and-language translation with persistent comments and structured mentions, and receive private in-app mention notifications that deep-link to the exact comment.

This phase does not serialize changes back into localization files, mutate Bitbucket branches, create commits, or open pull requests. Format-safe write-back remains Phase 6 and Bitbucket change-set/PR delivery remains Phase 7.

</domain>

<decisions>
## Implementation Decisions

### Translation editing and pending changes
- **D-01:** Support editing both inline from the translation workspace and in the full translation detail view. Inline editing is for quick changes; detail editing retains the complete language, review-state, constraint, source, and history context.
- **D-02:** Editing is an explicit session with `Save` and `Cancel`. Unsaved text remains browser-local and the application warns before route change, product/context change, or page exit would discard it; typing alone never persists a change.
- **D-03:** Keep the current published/imported value separate from its pending proposal. Saving creates or updates a pending Draft without changing the value currently presented as published/approved. — **Reversibility:** one-way — collapsing the two authorities later would require a persisted-data and API migration and would weaken Phase 6/7 write-back provenance.
- **D-04:** Detect concurrent edits and never overwrite silently. The first valid save succeeds; a later save based on stale state is rejected with an actionable comparison against the newer server value so the user can reconcile and retry.
- **D-05:** Each language is saved and reviewed independently. A key with pending edits in multiple languages exposes a separate pending indicator, conflict authority, and review state for every language.

### Roles, review states, and history
- **D-06:** Translators may edit translations and leave pending proposals in Draft. Product manager/reviewers may approve or reject and may approve their own edits. Administrators may perform every review operation. Viewer-only users remain read-only. The backend enforces the same authority regardless of which controls the frontend renders.
- **D-07:** A rejection reason is optional. When supplied, it is retained with the transition history; the absence of a reason must not block rejection.
- **D-08:** Editing an Approved translation does not demote the published value. The published value remains Approved while the new pending proposal starts in Draft and is shown as a distinct review subject.
- **D-09:** Show a complete audit history in an expandable panel. It includes value changes, state changes, actor, timestamp, and any accompanying comment or reason, while the collapsed workspace remains task-focused.
- **D-10:** Carry forward Phase 4's authoritative constraint gate: an over-limit proposal may remain Draft but cannot become Approved. Deleted source translations retain readable review context but cannot accept new edits or approval transitions.

### Comments and structured mentions
- **D-11:** A discussion belongs to one stable key-and-language translation group, not to all languages of a key and not to a transient file path. Structured selector values within that key-language group share its discussion context. — **Reversibility:** costly — changing comment scope later would require reassignment of persisted conversations and deep links.
- **D-12:** A comment author may edit their own comment. Every edit is versioned and visible as edited history. Only an administrator may delete a comment; the persistence strategy must retain enough audit continuity that existing conversations and notification links do not become ambiguous.
- **D-13:** Mentions are created by typing `@` and selecting an active user from immediate autocomplete results. Free text that merely resembles `@name` is not a mention; persistence stores immutable user identity separately from rendered display text.
- **D-14:** Editing a comment creates notifications only for newly added distinct mentions. Previously notified users are not notified again, and removing a mention does not retract an already delivered notification.
- **D-15:** Show the most recent comments in the normal detail view and allow older history to be expanded. Expanded comments preserve chronological conversation order and retain author, timestamp, edit status, and mention rendering.

### Personal notifications and exact-comment navigation
- **D-16:** A notification becomes read automatically only after its exact linked comment has been opened successfully. Users can also mark individual notifications as read manually; opening the notification list alone does not mark them read.
- **D-17:** Update the unread count in real time when the connection is available and use periodic automatic refresh as the recovery fallback. The server remains authoritative after reconnect, tab wake, or missed live events.
- **D-18:** Add a notification bell to the authenticated application shell. It opens a compact panel of recent notifications with a link to a dedicated full notification center.
- **D-19:** The notification center provides `All` and `Unread` views plus a product filter. Exact pagination, empty-state copy, and bounded retention presentation are implementation details, but access remains scoped to the signed-in user.
- **D-20:** A mention notification uses a stable URL reference to the originating translation and comment. Following it opens surrounding conversation context, scrolls to the exact comment, moves accessible focus to it, and applies a temporary visual highlight.
- **D-21:** Notification creation is exactly once per distinct newly mentioned user other than the author. No user may read, mark, count, subscribe to, or otherwise infer another user's notifications.

### the agent's Discretion
- Choose the SQLAlchemy table names, revision-token or ETag representation, optimistic concurrency payload, API route shapes, and transaction boundaries, while preserving the separate published/pending authorities and fail-closed conflict behavior.
- Choose whether live notification delivery uses SSE, WebSocket, or an equivalent authenticated transport, and choose the periodic fallback interval and reconnect strategy.
- Choose the exact inline editor and detail-panel composition, recent-comment count, animation duration, focus treatment, and notification empty/loading/error copy within the existing shadcn/ui design system and accessibility patterns.
- Choose the administrative comment-deletion persistence mechanism. It must preserve audit continuity, prevent broken or misleading deep links, and never expose deleted text to users who no longer have authority to view it.
- Treat `admin`, `product_manager_reviewer`, and `translator` as authorized comment authors and viewers; treat `viewer` as comment-readable but unable to add, edit, delete, or mention. This residual permission assumption may be tightened during planning if the existing authorization model requires a narrower product-scoped rule.
- Simple explicit state transitions are sufficient for v1; no multi-step approval quorum, assignment queue, mandatory rejection reason, or comment-thread resolution workflow is implied.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope and Phase 5 requirements
- `.planning/PROJECT.md` — project architecture, provider boundary, authentication model, roles, workflow states, and quality gate.
- `.planning/REQUIREMENTS.md` — authoritative REVW-01..08, COMM-01..06, NOTF-01..05, and UI-02 contracts.
- `.planning/ROADMAP.md` — Phase 5 goal, boundary, success criteria, and relationship to Phases 4, 6, and 7.
- `.planning/STATE.md` — current project position and the still-open Phase 4 human UAT status.

### Carried-forward product and UI decisions
- `.planning/phases/01-platform-foundation/01-CONTEXT.md` — provider-independent roles, backend-enforced authorization, OAuth2 bearer identity, and role-aware shell boundary.
- `.planning/phases/04-localization-import-search-and-constraints/04-CONTEXT.md` — stable key/language identity, deletion behavior, import-driven Draft resets, approved synchronization, search grouping, and constraint approval gate.
- `.planning/phases/04-localization-import-search-and-constraints/04-UI-SPEC.md` — canonical translation workspace/detail information architecture, shadcn/ui patterns, accessibility, virtualized search, safe untrusted-text rendering, and existing read-only review seams.

### Existing implementation seams
- `backend/src/verboflex/models/translation.py` — canonical localization scopes, values, closed ReviewState vocabulary, history, provenance, and constraints to extend.
- `backend/src/verboflex/api/v1/routes/translations.py` — current authenticated search/detail projection, including placeholder pending-change and comment fields.
- `backend/src/verboflex/schemas/translations.py` — generated-client source contracts for translation search and detail.
- `backend/src/verboflex/models/user.py` — stable internal user identity and active-user authority for mentions.
- `backend/src/verboflex/models/role.py` — canonical `admin`, `product_manager_reviewer`, `translator`, and `viewer` roles.
- `backend/src/verboflex/auth/principal.py` — server-side principal and role dependency patterns required on every mutation and notification route.
- `backend/src/verboflex/api/v1/routes/users.py` — existing current-user route; active-user mention search must extend authenticated user discovery without exposing administrative data.
- `frontend/src/features/translations/TranslationsWorkspace.tsx` — existing feature-level route state that preserves translation search context across detail navigation.
- `frontend/src/features/translations/TranslationSearchPage.tsx` — current dense, filtered, cursor-backed result surface to extend with inline editing and pending/comment indicators.
- `frontend/src/features/translations/TranslationDetailPage.tsx` — current read-only review placeholders, constraint actions, history, and stable detail route to turn into the review workspace.
- `frontend/src/components/layout/AppShell.tsx` — authenticated header and navigation integration point for the notification bell and unread badge.
- `frontend/src/router.tsx` — authenticated route integration point for the notification center and exact-comment deep links.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- The canonical translation model already has stable key/language identities, individual structured values, ReviewState, value revisions, imported history, and constraint projections. Phase 5 should extend these authorities rather than create a second translation domain.
- `TranslationsWorkspace`, the cursor-backed search page, and `TranslationDetailPage` already preserve filter/search context across child routes and expose safe, URL-backed server identifiers.
- `AppShell` already has responsive desktop/mobile navigation, an authenticated user menu, shadcn dropdown primitives, and a compact header action area suitable for a notification bell.
- The internal `User`/`Role` models and principal dependencies provide immutable mention identities and backend-enforced authorization foundations.

### Established Patterns
- FastAPI owns public request/response contracts and generates the TypeScript client; frontend code must not hand-author a parallel API client.
- Imported repository content is untrusted and rendered as text with language/direction attributes. Comment content and display names require the same safe rendering boundary.
- Server-calculated review, constraint, and authorization state is authoritative; hiding a frontend control is never sufficient enforcement.
- Stable translation identity excludes mutable file paths, so comments, pending proposals, history, and deep links survive safe imports and file moves.
- User-facing asynchronous state uses bounded loading, empty, stale, and recoverable error presentations rather than silent retries or full-page refreshes.

### Integration Points
- Extend the translation model and Alembic schema with pending proposals, review transitions, comments/revisions/mentions, and per-user notifications.
- Add authenticated translation mutation, comment, mention-user search, notification list/read, and unread-count APIs under the existing v1 router, then regenerate OpenAPI and the frontend client.
- Extend the existing search/detail routes rather than introduce a separate review product area; preserve product focus, filters, virtual scrolling, and stable URL authority.
- Add notification UI to `AppShell` and a protected notification-center route; exact-comment links should resolve through the translation detail route and an opaque comment identifier.

</code_context>

<specifics>
## Specific Ideas

- Inline editing should feel fast for routine changes, while the detail page remains the complete review surface for constraints, history, and comments.
- The UI must visibly distinguish “currently published and Approved” from “new pending Draft” instead of making an approved value appear silently replaced.
- A stale editor should see the value they attempted to save beside the newer server value and be invited to reconcile, never discover later that another user's work was overwritten.
- Notification navigation should land inside the surrounding conversation, not isolate the comment in a modal or separate page.
- Phase 4's remaining defects stay in its human UAT backlog while Phase 5 planning proceeds. A defect that blocks Phase 5 implementation must be repaired and tracked as Phase 4 UAT/debug work rather than silently reclassified as a Phase 5 feature.

</specifics>

<deferred>
## Deferred Ideas

- Format-safe serialization of approved pending changes is Phase 6.
- Change-set selection, Bitbucket branch/commit mutation, pull-request creation, and PR synchronization are Phase 7.
- The unresolved Phase 4 human test findings remain open in `.planning/phases/04-localization-import-search-and-constraints/04-UAT.md`; this Phase 5 context does not close or waive them.

</deferred>

---

*Phase: 5-Review Workspace and Comments*
*Context gathered: 2026-09-09*
