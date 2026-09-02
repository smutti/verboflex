# Phase 3: Bitbucket Import Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-02
**Phase:** 3-Bitbucket Import Integration
**Areas discussed:** Source baseline and rewritten-branch reconciliation, capability profile and blocking behavior, retry and last-success preservation, operational diagnostics and history

---

## Source Baseline and Rewritten-Branch Reconciliation

### Branch movement

| Option | Description | Selected |
|--------|-------------|----------|
| New baseline for every commit | Create a new immutable baseline automatically for every changed commit. | |
| Fast-forward automatic, rewrite confirmed | Accept descendant commits automatically; require administrator confirmation for rebase/force-push. | ✓ |
| Confirm every update | Require administrator approval for every branch movement. | |

**User's choice:** Fast-forward automatic; rewritten history requires confirmation.
**Notes:** The branch is mutable and must be refreshed rather than treated as the durable identity.

### Pending VerboFlex changes

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve and reconcile | Keep pending changes on the old baseline, block PR submission, then reapply or reconcile them. | ✓ |
| Block baseline update | Keep the old baseline until changes are submitted or discarded. | |
| Invalidate changes | Mark changes based on the old baseline obsolete. | |

**User's choice:** Preserve and reconcile.
**Notes:** Conflicts after rebase must be explicit.

### Reconciliation scope

| Option | Description | Selected |
|--------|-------------|----------|
| Mapping-level | Only the mapping consuming the rewritten branch enters reconciliation. | ✓ |
| Independent side | Permit each side of a separate mapping to reconcile independently. | |
| Product-wide | Put every mapping for the product into reconciliation. | |

**User's choice:** “Se un ramo viene ribasato il solo mapping per quel ramo deve essere messo in riconciliazione.”
**Notes:** Other mappings remain usable; a multi-side mapping remains the consistency boundary.

### Confirmation evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Source comparison | Show old/new commits plus added, removed, and modified localization files. | ✓ |
| Commit only | Show only branch and old/new commit hashes. | |
| Full configuration preview | Repeat the entire product configuration preview. | |

**User's choice:** Source comparison.
**Notes:** Confirmation becomes available only after the proposed baseline can be read successfully.

---

## Capability Profile and Blocking Behavior

### Import start gate

| Option | Description | Selected |
|--------|-------------|----------|
| Read readiness preflight | Require repository, branch, and file access before starting. | |
| Read plus write/PR readiness | Require all current and future capabilities before starting. | |
| Global connection only | Start with an active global connection; verify concrete source access during execution. | ✓ |

**User's choice:** Global connection only.
**Notes:** A failure for one repository does not invalidate the global connection.

### Capability-result retention

| Option | Description | Selected |
|--------|-------------|----------|
| Latest per mapping, always reverify | Persist the latest result but check real access during every import. | ✓ |
| Cache until configuration changes | Reuse capability results until connection or mapping configuration changes. | |
| Attempt only | Keep capability results only inside one import attempt. | |

**User's choice:** Latest result per mapping, always reverify.
**Notes:** A previous result is informational, never later authorization.

### OAuth authority

| Option | Description | Selected |
|--------|-------------|----------|
| Keep read-only | Report future write/PR capability without granting it. | |
| Defer write scope | Add write/PR capability only in Phase 8. | |
| Upgrade current connection | Give the single current OAuth connection the capability needed for commits and PRs. | ✓ |

**User's choice:** “Modifichiamo la connessione attuale in modo da far sì che abbia tutte le capability per aprire anche PR.”
**Notes:** This explicitly supersedes the Phase 2 read-only decision.

### Application privilege boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal allowlist | Request `pullrequest:write`, but expose only branch creation, source commits, and PR creation. | ✓ |
| Full PR lifecycle | Also expose approve, decline, and merge. | |
| Two connections | Split read-only import authority from write/PR authority. | |

**User's choice:** Minimal application allowlist.
**Notes:** Repository administration and deletion remain forbidden. Phase 3 obtains and validates authority but performs no provider mutations.

---

## Retry and Last-Success Preservation

### Automatic retry

| Option | Description | Selected |
|--------|-------------|----------|
| Transient only | Automatically retry timeout, rate-limit, and temporary provider failures. | |
| None | Stop after one execution and require an administrator to retry manually. | ✓ |
| All failures | Retry authentication, permission, and missing-source failures too. | |

**User's choice:** No automatic retry.
**Notes:** This includes timeout and rate-limit failures.

### Failed refresh behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve last baseline | Keep the last successful baseline active and flag possible staleness. | ✓ |
| Disable mapping | Invalidate the prior baseline after any refresh failure. | |
| Depend on error | Preserve or invalidate based on failure category. | |

**User's choice:** Preserve the last successful baseline.
**Notes:** The latest failure is shown separately.

### Manual retry record

| Option | Description | Selected |
|--------|-------------|----------|
| Linked immutable attempt | Create a new child record for each retry. | |
| Reuse logical record | Replace current status/error and retain a retry count plus latest timestamp. | ✓ |
| Independent attempt | Create an unrelated new record. | |

**User's choice:** Reuse the failed import record.
**Notes:** The interface does not retain earlier failure details.

### Retry source target

| Option | Description | Selected |
|--------|-------------|----------|
| Current branch commit | Resolve the branch again and use its current commit. | ✓ |
| Failed commit | Retry the exact commit targeted by the failed execution. | |
| Administrator choice | Select old or current commit for each retry. | |

**User's choice:** Current branch commit.
**Notes:** A rewritten history detected during retry enters mapping reconciliation.

---

## Operational Diagnostics and History

### Error detail

| Option | Description | Selected |
|--------|-------------|----------|
| Concise actionable message | Show a sanitized category and guided recovery. | |
| General concise message | Show only a general category and short message; keep technical detail in server logs. | ✓ |
| Provider detail | Show the original Bitbucket body and message. | |

**User's choice:** General concise message.
**Notes:** Server logs must remain sanitized.

### Visible history

| Option | Description | Selected |
|--------|-------------|----------|
| Last success and current attempt | Show one active baseline and one current logical attempt. | ✓ |
| All successful baselines | Expose the complete successful-baseline history. | |
| Complete history | Expose successes, failures, retries, and reconciliation events. | |

**User's choice:** Last success and current attempt.
**Notes:** No full operational timeline in the UI.

### Error actions

| Option | Description | Selected |
|--------|-------------|----------|
| Context-specific action | Link to reconnect, edit mapping, reconcile, or retry. | |
| Always retry | Put the same Retry action on every error. | |
| No direct action | Show status only; normal navigation and mapping controls remain separate. | ✓ |

**User's choice:** No direct action.
**Notes:** Manual retry remains available through the normal mapping import control, not the error message.

### Stale-baseline visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Mapping and product summary | Badge the affected mapping and show a count on its product overview. | ✓ |
| Mapping detail only | Show the warning only after opening the mapping. | |
| Global banner | Warn throughout the administration area. | |

**User's choice:** Mapping and product summary.
**Notes:** Unrelated products and mappings receive no global warning.

---

## the agent's Discretion

- Exact persistence, API, job, error-code, badge, and route names.
- Exact Bitbucket ancestry-check mechanism and source-delta representation.
- Exact concise error copy and sanitized correlation fields.
- Exact layout of the mapping badge and product-level count within existing admin patterns.

## Deferred Ideas

- Canonical parsers and translation identity remain Phase 4.
- Searchable imported translations remain Phase 5.
- Review and pending-change workflows remain Phase 6.
- Format-safe write-back and stale-file conflict handling remain Phase 7.
- Executing Bitbucket branch creation, source commits, and pull-request creation remains Phase 8.

