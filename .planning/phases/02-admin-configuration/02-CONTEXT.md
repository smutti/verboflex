# Phase 2: Admin Configuration - Context

**Gathered:** 2026-08-26
**Status:** Ready for specification and planning

<domain>
## Phase Boundary

Phase 2 delivers the administrative control plane for internal users and roles, products, reusable Bitbucket Cloud repositories, product-repository mappings, branch and pull-request behavior, and the corresponding shadcn-based admin experience.

The phase boundary is intentionally expanded from the current roadmap: Phase 2 also establishes a backend-only Bitbucket OAuth 2.0 connection, performs live repository discovery for configuration preview, and provides minimal read-only detection for Android XML, Qt `.ts`, JSON, and iOS `.strings`. The preview must show detected files, formats, languages, sample keys, and sample translations before an administrator can activate a product.

This phase does not implement canonical translation imports, durable import baselines, format-preserving write-back, translation review, comments, constraints, or pull-request creation. The Phase 2 SPEC must reconcile the expanded boundary with Phases 3 and 4 before implementation plans are written, so live-read and minimal-detection work is not duplicated downstream.

</domain>

<decisions>
## Implementation Decisions

### Internal user lifecycle
- **D-01:** User creation and administrative password reset generate a temporary password in the backend, reveal it exactly once to the administrator, and require the affected user to change it at first login.
- **D-02:** A user's corporate email is immutable after account creation. Correcting an erroneous email requires a new account. — **Reversibility:** costly — changing this later alters the stable login identifier contract and every administrative/audit flow that refers to it.
- **D-03:** Administrators may update only the user's display name, assigned roles, lifecycle state, and password authority through the dedicated reset operation; password plaintext is never stored or recoverable.
- **D-04:** Roles are additive, any combination of the four fixed roles is allowed, and every user must retain at least one role.
- **D-05:** An administrator cannot remove their own `admin` role. Role changes and lifecycle mutations must transactionally preserve at least one active administrator.
- **D-06:** Deactivation is reversible. Deactivation immediately revokes all authority for the user; reactivation generates a new one-time temporary password and again requires a password change.

### Products and reusable repositories
- **D-07:** A Bitbucket repository is a global resource identified uniquely by normalized `workspace + repository_slug`, with an optional descriptive name. It may be reused by multiple products. — **Reversibility:** one-way — changing to product-owned repository rows after launch requires a data migration and rewrites repository and mapping API identities.
- **D-08:** Product-repository mappings hold product-specific branch and localization configuration; reuse of the global repository never forces products to share those settings.
- **D-09:** Only the product has an active/inactive operational state. Mappings do not have independent draft/enabled/disabled states.
- **D-10:** Activating or publishing a product requires every mapping in the candidate configuration to pass validation and preview. Deactivating a product suspends all of its mappings without deleting configuration.
- **D-11:** Every product-repository mapping stores exactly one source branch, one or more allowed pull-request target branches, and one designated default target branch. Different products may use different branches of the same repository.

### Localization mapping and live preview
- **D-12:** One mapping model supports two explicit topologies: `direct`, where keys and translations use one repository side, and `separate`, where key and translation repository sides are linked explicitly. — **Reversibility:** one-way — splitting this into unrelated schemas later requires migration of mapping identities and published API payloads.
- **D-13:** Repository localization layout is discovered automatically. Administrators do not maintain globs, per-file lists, or language extraction templates in v1.
- **D-14:** Phase 2 pulls forward the Bitbucket read access and minimal format-detection work previously assigned to Phases 3 and 4. Minimal parsers are read-only preview adapters, not the later canonical import or format-preserving writer implementations.
- **D-15:** Preview displays detected files, formats, languages, sample keys, and sample translations. Ambiguous or invalid detection blocks activation; an administrator must explicitly confirm a successful preview.
- **D-16:** Repository scanning and parsing must respect the existing background-job boundary when work is not safely bounded for an HTTP request.

### Pull-request behavior and admin UX
- **D-17:** Pull-request grouping is fixed per repository and target branch. Compatible changes for all languages and files in that repository/target pair belong to one PR; a change set must never span repositories or target branches.
- **D-18:** Administrators configure an allowed target-branch list plus a default target. A future submitter may choose another target only from the allowed list.
- **D-19:** New product setup uses a guided wizard. After creation, configuration is organized into focused overview, repository, mapping, and preview sections; user administration remains a global admin section in the same shell.
- **D-20:** Edits to an active product create a candidate configuration revision. The currently active revision remains effective until the candidate passes validation and preview and an administrator publishes it atomically. — **Reversibility:** one-way — removing revisioned publication later requires collapsing active/candidate records and changing concurrency and API semantics.

### Bitbucket authentication
- **D-21:** VerboFlex authenticates to Bitbucket Cloud with OAuth 2.0 rather than repository/workspace access tokens, API tokens, or deprecated app passwords. — **Reversibility:** costly — changing the provider credential model affects callback APIs, encrypted token persistence, refresh/rotation, capability checks, and repository bindings.
- **D-22:** Bitbucket access and refresh credentials remain backend-only, encrypted at rest, excluded from API responses and logs, and independent from VerboFlex's internal user authentication. Microsoft Entra ID/OIDC remains deferred and is not part of this decision.
- **D-23:** The Phase 2 SPEC/research must define the least-privilege Bitbucket OAuth scope matrix for preview now and later write/PR capabilities; implementation must not request an undocumented superset by default.

### the agent's Discretion
- Exact API resource names, pagination defaults, list sorting, validation copy, and wizard micro-interactions may follow established FastAPI, generated-client, and shadcn patterns.
- Exact automatic-detection confidence thresholds may be chosen during specification, provided ambiguity fails closed and requires explicit administrator confirmation.
- Exact temporary-password length and generation mechanism may reuse or strengthen the existing password-policy boundary without weakening Phase 1 guarantees.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope and requirements
- `.planning/PROJECT.md` — product constraints, internal access model, Bitbucket-only v1 scope, background-job boundary, and phase quality gate.
- `.planning/REQUIREMENTS.md` — AUTH-02, AUTH-03, PROD-01 through PROD-09, and UI-03; the Phase 2 SPEC must record the agreed boundary shift for Bitbucket read and minimal detection.
- `.planning/ROADMAP.md` — current Phase 2–4 boundaries and success criteria that require reconciliation before planning.
- `.planning/STATE.md` — active project decisions, security debt, and downstream blockers.
- `.planning/phases/01-platform-foundation/01-CONTEXT.md` — locked internal authentication, provider independence, session revocation, generated-client, and application-shell decisions.

### Architecture and risk research
- `.planning/research/ARCHITECTURE.md` — repository mapping, backend-only Bitbucket boundary, canonical translation model, and data-flow guidance.
- `.planning/research/PITFALLS.md` — mapping preview, capability validation, stale baselines, and format-preservation risks.
- `.planning/research/STACK.md` — FastAPI, PostgreSQL, Celery/Redis, React/Vite, generated OpenAPI client, and supported format stack.

### Existing authentication and UI implementation
- `backend/src/verboflex/models/user.py` — provider-independent user identity, lifecycle fields, token version, and role relationship.
- `backend/src/verboflex/models/role.py` — fixed role names and many-to-many mapping.
- `backend/src/verboflex/models/auth_session.py` — refresh-session authority that administrative mutations must revoke.
- `backend/src/verboflex/cli.py` — existing first-admin, reset, and deactivation authority behavior to reuse rather than fork.
- `backend/src/verboflex/auth/principal.py` — server-authoritative principal and role reconciliation.
- `backend/src/verboflex/api/v1/routes/users.py` — current `/users/me` integration point for new admin user APIs.
- `backend/src/verboflex/api/v1/router.py` — versioned API router integration point.
- `frontend/src/router.tsx` — authenticated route containment.
- `frontend/src/components/layout/AppShell.tsx` — responsive navigation and global admin-shell integration point.
- `frontend/src/features/auth/session.tsx` — memory-only browser authority and generated-client session pattern.

### Official Bitbucket Cloud references
- `https://developer.atlassian.com/cloud/bitbucket/rest/` — current REST authentication methods, OAuth 2.0 behavior, scopes, and app-password deprecation.
- `https://developer.atlassian.com/cloud/bitbucket/bitbucket-cloud-rest-api-scopes/` — authoritative endpoint scope model.
- `https://support.atlassian.com/bitbucket-cloud/docs/access-tokens/` — resource access-token alternative considered and rejected for this phase.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `User` and `Role` already provide normalized internal identities, active state, token-version revocation, fixed roles, and the required many-to-many relationship.
- Existing CLI administrative reset/deactivation behavior already applies atomic password replacement and session revocation and should be extracted behind reusable service authority rather than duplicated in HTTP routes.
- `Principal` keeps backend database roles authoritative; admin dependencies can build on this boundary.
- The generated OpenAPI client and memory-only session provider are ready for new typed admin endpoints without hand-written transport code.
- `AppShell` already has responsive desktop/sidebar and mobile/Sheet navigation seams for the admin module.

### Established Patterns
- API contracts are defined in FastAPI, exported to canonical OpenAPI, and consumed through generated TypeScript.
- Sensitive authority mutations fail closed, revoke affected sessions atomically, and return sanitized errors.
- PostgreSQL/Alembic own durable schema evolution; SQLAlchemy models use UUID identities and explicit constraints.
- Slow or retry-prone repository and parsing work belongs in Celery through Redis, not in HTTP handlers.
- Frontend route visibility is not authorization; every admin mutation requires a backend role check.

### Integration Points
- Extend the v1 router with admin user, product, repository, mapping, preview-job, and Bitbucket OAuth callback/status resources.
- Add new SQLAlchemy models through `models/__init__.py` and a reversible Alembic migration after RED migration tests.
- Regenerate the frontend client after each stable API contract slice and extend `AppShell` navigation and authenticated routes.
- Keep the Bitbucket OAuth callback and refresh-token authority backend-only; the SPA receives bounded connection status, never provider credentials.

</code_context>

<specifics>
## Specific Ideas

- Product activation and publication are explicit admin actions, not side effects of saving a form.
- The setup wizard culminates in live automatic discovery and a human-confirmed preview.
- A repository is entered as workspace plus repository slug; branch selection and live validation are mapping-specific.
- The active product revision remains usable while a replacement configuration is prepared and validated.

</specifics>

<deferred>
## Deferred Ideas

- Microsoft Entra ID/OIDC for VerboFlex user authentication remains a future identity-provider integration.
- Full canonical import, durable source baselines, stable translation identity, and complete parser fixtures remain downstream work after the minimal read-only preview adapters.
- Format-preserving writes, change-set execution, commits, and pull-request creation remain in the later write-back and PR phases.

</deferred>

---

*Phase: 2-Admin Configuration*
*Context gathered: 2026-08-26*
