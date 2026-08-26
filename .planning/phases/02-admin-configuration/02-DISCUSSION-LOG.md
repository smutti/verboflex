# Phase 2: Admin Configuration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-26
**Phase:** 2-Admin Configuration
**Areas discussed:** Internal users and roles, products and repositories, mappings and preview, PR behavior and admin UX, Bitbucket authentication

---

## Internal users and roles

### Initial credentials

| Option | Description | Selected |
|--------|-------------|----------|
| System-generated password | Reveal once and require change at first login | ✓ |
| Admin-chosen password | Administrator enters a temporary password | |
| Inactive account | Activate through a separate password operation | |

### Editable identity

| Option | Description | Selected |
|--------|-------------|----------|
| Email and display name | Email change revokes sessions | |
| Display name only | Email remains immutable | ✓ |
| Email before first login | Email becomes immutable after initial password change | |

### Role safety

| Option | Description | Selected |
|--------|-------------|----------|
| Additive roles with strong protection | At least one role; no self-removal of admin; preserve an active admin | ✓ |
| Additive roles with minimal protection | Self-change allowed when another active admin exists | |
| Viewer exclusive | Viewer cannot combine with other roles | |

### Deactivation

| Option | Description | Selected |
|--------|-------------|----------|
| Reversible with new credentials | Revoke sessions and generate a new temporary password on reactivation | ✓ |
| Reversible with old password | Preserve the previous password | |
| Permanent | Keep history but never reactivate | |

**User's choice:** Generated one-time credentials; immutable email; additive protected roles; reversible deactivation with fresh credentials.
**Notes:** Phase 1 session revocation and forced-password-change behavior remain authoritative.

---

## Products and repositories

### Repository reuse

| Option | Description | Selected |
|--------|-------------|----------|
| Global reusable repository | Link one repository to multiple products through independent mappings | ✓ |
| Product-owned repository | Duplicate configuration when shared | |
| Reusable with shared mapping | All products share branch, format, and path settings | |

### Operational state

| Option | Description | Selected |
|--------|-------------|----------|
| Product and mapping states | Product plus draft/enabled/disabled mappings | |
| Product state only | Active product makes all validated mappings operational | ✓ |
| Mapping state only | Derive product state from enabled mappings | |

### Repository identity

| Option | Description | Selected |
|--------|-------------|----------|
| Workspace plus slug | Canonical unique pair with optional descriptive name | ✓ |
| Full URL | Parse workspace and slug from a URL | |
| Workspace, slug, and URL | Require and cross-check all fields | |

### Branch ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Product-repository mapping | One source branch and multiple allowed targets per mapping | ✓ |
| Global repository | Share branches across every product | |
| Multiple source branches | Import from several sources in one mapping | |

**User's choice:** Reusable global repository, product-only activation, workspace/slug identity, and mapping-specific branches.
**Notes:** The user explicitly added that branch information must be tracked.

---

## Mappings and preview

### Direct and cross-repository topology

| Option | Description | Selected |
|--------|-------------|----------|
| Unified model with two modes | Direct or explicitly linked separate repositories | ✓ |
| Separate models and APIs | Independent direct and cross-repository resource types | |
| Always two-sided | Configure key and translation sides even when identical | |

### File and language discovery

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable patterns | Admin supplies format, glob, and language extraction rule | |
| Fully automatic discovery | Detect files, formats, and languages from repository contents | ✓ |
| Manual file list | Admin enumerates every file and language | |

### Phase placement of live preview

| Option | Description | Selected |
|--------|-------------|----------|
| Progressive across Phases 2–4 | Contract in Phase 2, reads in Phase 3, parsing in Phase 4 | |
| Pull live access and minimal parsers into Phase 2 | Expand Phase 2 and reconcile later boundaries | ✓ |
| Non-blocking preview | Permit activation before live validation | |

### Ambiguous detection

| Option | Description | Selected |
|--------|-------------|----------|
| Mandatory admin confirmation | Show samples; ambiguity blocks activation | ✓ |
| Highest-confidence candidate | Choose automatically and warn | |
| First valid candidate | Accept the first recognized structure | |

**User's choice:** Unified topology, fully automatic detection, live preview pulled into Phase 2, and fail-closed administrator confirmation.
**Notes:** This materially expands Phase 2 and requires roadmap reconciliation before implementation planning.

---

## Pull-request behavior and admin UX

### PR grouping

| Option | Description | Selected |
|--------|-------------|----------|
| Repository, language, or file strategies | Product chooses among three strategies | |
| Repository and target branch | One PR for all compatible changes in the pair | ✓ |
| Language only | One PR per repository, target, and language | |

### Target branch selection

| Option | Description | Selected |
|--------|-------------|----------|
| Allowed list with default | Submitter may select another allowed branch | ✓ |
| One fixed target | No submit-time choice | |
| Allowed list without default | Always require explicit selection | |

### Admin interface

| Option | Description | Selected |
|--------|-------------|----------|
| Setup wizard and detail sections | Guided creation followed by focused configuration sections | ✓ |
| Separate CRUD pages | Independent resource-management pages only | |
| One large form | Edit all product configuration together | |

### Editing an active product

| Option | Description | Selected |
|--------|-------------|----------|
| Candidate revision | Keep active revision until validated candidate is published atomically | ✓ |
| Immediate deactivation | Disable product on every edit | |
| Immediate mutation | Apply edits before validation finishes | |

**User's choice:** Group by repository/target, allowed targets with default, wizard plus detail sections, and candidate configuration revisions.
**Notes:** Publishing is an explicit atomic action after preview confirmation.

---

## Bitbucket authentication

| Option | Description | Selected |
|--------|-------------|----------|
| Repository access token | Static least-privilege token per repository | |
| Workspace access token | Static reusable workspace credential | |
| OAuth 2.0 | Authorization-code connection with access/refresh lifecycle | ✓ |

**User's choice:** OAuth 2.0.
**Notes:** This choice was added after the live Bitbucket work moved from Phase 3 into Phase 2. Exact scopes and encrypted token lifecycle remain specification/research prerequisites.

---

## the agent's Discretion

- Exact API names, pagination, sorting, UI copy, and confidence thresholds within the fail-closed preview rule.

## Deferred Ideas

- Microsoft Entra ID/OIDC for VerboFlex login remains deferred.
- Canonical imports, format-preserving writes, and pull-request execution remain later-phase work.
