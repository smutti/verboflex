# Phase 3: Bitbucket Import Integration - Context

**Gathered:** 2026-09-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 turns the Phase 2 Bitbucket boundary into an import-grade integration for configured repository-and-branch sources. It validates access during each import, resolves mutable branches to immutable commits, persists the exact commit and file references used, distinguishes fast-forward movement from rewritten history, and gives administrators bounded operational status and manual recovery.

This phase also upgrades the single organizational OAuth connection so later phases can create source commits and open pull requests. Phase 3 must acquire and validate that capability, but it must not perform provider mutations. Canonical localization parsing remains Phase 4, searchable imported translation records remain Phase 5, format-safe write-back remains Phase 7, and branch/commit/pull-request execution remains Phase 8.

</domain>

<decisions>
## Implementation Decisions

### Source baseline and rewritten-branch reconciliation
- **D-01:** A configured `repository + branch` is a mutable selector, not a durable source identity. Every import execution resolves it again and persists the exact provider commit plus every file reference actually used.
- **D-02:** A normal fast-forward is accepted as the next baseline without administrator confirmation. A rebase, force-push, or other rewritten-history movement requires explicit administrator confirmation.
- **D-03:** Reconciliation is isolated to the mapping that uses the rewritten branch. Other mappings on the same product remain usable. For a multi-side `separate` mapping, the mapping is the consistency boundary and cannot become partially reconciled.
- **D-04:** Before reconciliation can be confirmed, VerboFlex must successfully read the proposed baseline and show the old and new commits together with localization files added, removed, or modified.
- **D-05:** Pending VerboFlex edits remain associated with their old baseline when history is rewritten. Pull-request submission is blocked until the new baseline is confirmed and the edits are reapplied or reconciled; conflicts must be explicit. — **Reversibility:** costly — changing this later alters stale-source and write-back contracts across Phases 6–8.

### Capability profile and provider authority
- **D-06:** An active global Bitbucket connection is sufficient to start an import. Repository, branch, and file access are checked during that execution rather than through a blocking per-repository preflight.
- **D-07:** Persist the latest capability result per mapping with its timestamp and source identity, but verify access again on every import. A previous success is never authorization for a later read.
- **D-08:** Supersede the Phase 2 read-only OAuth decision: the single organizational connection must request Bitbucket OAuth `pullrequest:write`, which also implies the repository read/write capability needed for source commits. — **Reversibility:** costly — this changes deployed OAuth-consumer configuration, granted-token validation, connection recovery, tests, and the provider security boundary.
- **D-09:** VerboFlex must enforce an application-owned provider-operation allowlist limited to reading sources, creating a branch, writing source commits, and opening a pull request. It must never expose merge, approve, decline, repository administration, or repository deletion operations, even though Bitbucket's coarse scope can authorize some of them.
- **D-10:** Phase 3 validates and reports the expanded connection capability but performs zero provider writes. The allowlisted mutation operations become executable only in Phase 8 after Phase 7 establishes safe write-back.

### Retry and last-success preservation
- **D-11:** There are no automatic retries. Timeout, rate-limit, provider-unavailable, authentication, permission, and missing-source failures all stop after one execution; an administrator explicitly chooses when to retry.
- **D-12:** If a refresh import fails, the last successful baseline remains active. The mapping is separately marked as potentially stale because its latest attempt failed.
- **D-13:** Manual retry reuses the same logical import record. Its current status and current error are replaced by the latest execution; retain a retry counter and latest execution timestamp rather than a separate visible attempt record. — **Reversibility:** costly — changing to immutable attempt history later requires a persistence migration and API/UI contract changes.
- **D-14:** A manual retry resolves the configured branch again and targets its current commit. If that resolution detects rewritten history, the mapping enters the reconciliation flow before the new baseline can become active.

### Operational diagnostics and admin presentation
- **D-15:** Administrator-facing failures contain only a general category and concise sanitized message. Provider bodies and detailed technical diagnostics remain in sanitized server logs.
- **D-16:** The UI shows the last successful baseline and the current state of the latest logical import only; it does not expose full import, failure, retry, or reconciliation history.
- **D-17:** Error messages contain no contextual action buttons or automatic navigation links. Administrators navigate to configuration themselves; the normal mapping import control remains the place for manual retry.
- **D-18:** A mapping using an older baseline after a failed refresh receives a status badge, and the product overview shows a concise count of affected mappings. There is no global administration banner.

### the agent's Discretion
- Exact model, table, route, job, event, and error-code names may follow established FastAPI, SQLAlchemy, Celery, generated-client, and shadcn patterns.
- Research and planning may choose the exact Bitbucket ancestry-check API and file-delta representation, provided branch names remain opaque, commits remain exact, reads stay bounded, and D-02 through D-04 hold.
- Exact concise error copy, badge labels, timestamps, and product-summary placement may follow the existing admin interface.
- Internal sanitized logs may retain enough correlation and provider status metadata for operations, provided no token, client secret, raw source body, or unsafe provider payload is recorded.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope and phase requirements
- `.planning/PROJECT.md` — project constraints, provider scope, background-job boundary, and accepted Phase 2 decisions.
- `.planning/REQUIREMENTS.md` — Phase 3 requirements BITB-02, BITB-05, and BITB-06.
- `.planning/ROADMAP.md` — Phase 3 goal and success criteria plus the downstream Phase 7 write-back and Phase 8 pull-request boundaries.
- `.planning/STATE.md` — current phase position, retained warnings, and cross-phase concerns.
- `.planning/phases/02-admin-configuration/02-CONTEXT.md` — global repository identity, revision-specific mappings, exact branches, preview, connection, and prior read-only decision that D-08 explicitly supersedes.
- `.planning/phases/02-admin-configuration/02-SECURITY.md` — verified provider trust boundaries and residual risks that the expanded OAuth authority must re-evaluate.

### Existing Bitbucket and job implementation
- `backend/src/verboflex/integrations/bitbucket/client.py` — generation-bound read adapter, exact scope validation, safe provider failure kinds, redirect rejection, and bounded commit/file reads.
- `backend/src/verboflex/integrations/bitbucket/urls.py` — server-owned Bitbucket origins and opaque repository path validation.
- `backend/src/verboflex/services/bitbucket_oauth.py` — organizational client-credentials acquisition, encrypted connection generation, and current read-lease authority.
- `backend/src/verboflex/services/repository_discovery.py` — exact branch resolution, bounded traversal, and commit-bound source snapshots.
- `backend/src/verboflex/services/preview_jobs.py` — current asynchronous identity, currentness, timeout, confirmation, and active-revalidation patterns.
- `backend/src/verboflex/models/preview_job.py` — durable generation, revision, mapping, commit, digest, status, and watchdog fields reusable for import execution.
- `backend/src/verboflex/worker/preview_tasks.py` — Celery execution boundary and durable job transition pattern.
- `backend/src/verboflex/api/v1/routes/admin_bitbucket.py` — current global connection lifecycle and bounded public status.
- `frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx` — existing connection-state and manual-operation UI patterns.

### Official Bitbucket Cloud references
- `https://developer.atlassian.com/cloud/bitbucket/bitbucket-cloud-rest-api-scopes/` — OAuth scope implications; `pullrequest:write` is the selected coarse provider permission.
- `https://developer.atlassian.com/cloud/bitbucket/rest/api-group-source/` — source commit endpoint and required repository-write capability.
- `https://developer.atlassian.com/cloud/bitbucket/rest/api-group-refs/` — branch operations and required repository-write capability.
- `https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pullrequests/` — pull-request creation endpoint and required OAuth scope.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BitbucketHttpAdapter` already owns a pooled, no-redirect, generation-bound provider client and projects unsafe provider failures into bounded categories.
- `RepositorySourceSnapshot` and repository discovery already resolve exact branches to immutable commits and enforce page, entry, depth, candidate-file, per-file-byte, and total-byte ceilings.
- Preview jobs already persist mapping/revision/generation/commit identities, bounded errors, timestamps, terminal states, and watchdog ownership suitable as patterns for import state.
- Active-revalidation confirmation already demonstrates sidecar state that does not mutate the published product graph.
- The Bitbucket admin page already provides accessible loading, failure, connection, reconnection, and revocation states.

### Established Patterns
- Provider authorization and currentness are enforced server-side; UI status never grants authority.
- Slow provider work is represented durably and dispatched through Celery rather than running inside HTTP requests.
- Branch names remain exact opaque values, while every source read is bound to a validated immutable commit.
- API contracts originate in FastAPI/OpenAPI and flow to a generated TypeScript client.
- Provider bodies, credentials, raw source bytes, and sensitive headers do not cross into public schemas, browser state, or evidence.

### Integration Points
- Extend the OAuth service and Bitbucket adapter from exact read-only scope to the D-08 capability while preserving generation rotation, encryption, and safe logging.
- Add import baseline and logical-attempt persistence through SQLAlchemy/Alembic, keyed to the existing product revision and mapping ownership graph.
- Reuse repository discovery for fresh branch resolution and bounded file snapshots; add ancestry and file-delta capabilities without weakening URL/path checks.
- Add Celery import execution and manual retry transitions alongside the existing preview task/watchdog boundary.
- Extend admin mapping/product projections with last baseline, latest attempt, reconciliation state, mapping badge, and product-level stale count.
- Regenerate the frontend client after the new FastAPI contract stabilizes; do not introduce hand-written transports.

</code_context>

<specifics>
## Specific Ideas

- The branch is expected to move and may be rebased; the durable identity is always the resolved commit used by a specific import, never the branch name alone.
- “Automatic fast-forward” describes accepting a newly detected descendant commit during an import; it does not introduce scheduled polling or automatic retry.
- A rewritten branch affects only the mapping that consumes it, not every mapping or the whole product.
- The application deliberately obtains a coarse Bitbucket write/PR permission early but narrows actual behavior through its own operation allowlist.
- Administrators prefer a compact operational surface: one valid baseline, one current attempt, concise errors, local badges, and no global alerting.

</specifics>

<deferred>
## Deferred Ideas

- Full format parsers and stable canonical translation identity remain Phase 4.
- Persisting imported translations for search and constraint evaluation remains Phase 5.
- Editing, review states, comments, and pending-change management remain Phase 6.
- Format-preserving source updates, raw snapshots, and stale-file conflict handling remain Phase 7.
- Executing branch creation, commits, and pull-request creation remains Phase 8. Phase 3 only prepares and validates the required OAuth authority and durable baseline identity.

</deferred>

---

*Phase: 3-Bitbucket Import Integration*
*Context gathered: 2026-09-02*

