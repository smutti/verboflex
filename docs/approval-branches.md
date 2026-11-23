# Approval commits and pull requests

An optional product workflow saves each approved translation to an existing working
branch in Bitbucket. Saving a draft still only saves it in VerboFlex. Approval
records an immutable snapshot and queues a separate commit. Later drafts or
approvals do not replace earlier queued snapshots.

In **Publish translations**, users see each approval, its queue status and the resulting
commit link. **Create pull request** is a separate, explicit action. It becomes
available after all queued commits finish. An open PR automatically includes later
commits on the same working branch. Merging remains a Bitbucket action.

The publication summary keeps the open PR link, the first blocked change and the
number of pending changes visible on every history page. New approvals join the
open PR once their commits reach Bitbucket. Editing and approving a translation
are separate from merging it. An approval tied to an older import requires
administrator review. The panel identifies the affected change and suppresses
retries that would reuse the same obsolete approval.

## Configuration

In **Product configuration → Approval branches**, an administrator selects a
published translation source, its **Working branch** and its **PR destination**,
then chooses **Enable approval commits**. Branch names are configurable for every
product; no repository name or branch name is built into the workflow. The import
branch is suggested as the PR destination, independently of the working branch.

The same database-only action is available through
`PUT /api/v1/products/{product_id}/branch-workflow`:

```json
{
  "mapping_id": "<active mapping UUID>",
  "work_branch": "feature/verboflex",
  "target_branch": "master"
}
```

Both branches must already exist. The working branch must differ from the PR
destination, but it can also be the import branch. To review translations before
merging them, import from the working branch and select the stable/release branch
as the PR destination. Reimporting matching approved values does not require
reconciliation or mark them as integrated: the **Awaiting target** badge remains
until a background check verifies the values on the PR destination. Coverage and
search exclude imports from repository/branch identities removed from the active
configuration; unchanged identities can retain their last successful baseline.
With a separate code/translation mapping, only the
translation repository is written. The code repository remains an import source.
Each translation source can have its own workflow. With multiple sources, configure
each before approving its changes; **Change sets** lets users select the repository
branch and its history. A repository working branch cannot be shared by two
workflows. Branch configuration with recorded jobs is immutable, preserving the
meaning of retained intents and history. After replacing an import source, an
administrator can re-enable its unused, inactive workflow on the new mapping in
the same product, with the same repository, working branch and PR destination.
The change is audited; workflows with any job or retained file state cannot be
reassigned. Publishing a new configuration revision with the
same repository/import-branch identity retains the existing workflow; newly approved
changes use the newly imported source. A removed source retains read-only history.
Existing change sets must be completed before enabling it. Existing approvals are
not sent retroactively; the workflow starts with the next approval. Products
without this configuration keep the existing reviewed change-set workflow.

## Execution and recovery

Approval and its outbox row commit in one database transaction. Celery dispatches
pending rows every ten seconds and serializes effects per working branch. The
dispatcher considers only the first unfinished job per workflow, so a blocked backlog
does not prevent other products from progressing. Explicit recovery is eligible for
the next dispatch immediately. Each commit includes a stable operation ID and
content manifest. Provider reads and
writes never run inside HTTP handlers. The API enforces current product roles;
workers recheck membership, product configuration, import identity and constraints
before sending. A reviewer can request the PR or retry a blocked operation.

The renderer preserves the original localization structure and accumulates
approved edits against their imported file baseline. It verifies that the working
branch still contains the last verified file bytes before appending a commit.
An external change to a managed file, a new import or a changed configuration can
block an operation for review; the worker never force-pushes or resets the branch.
Unrelated files are not included in the commit.

Shared MOKO translation catalogs can contain duplicate keys belonging to other
products. Editing a unique key preserves those unrelated occurrences byte for
byte, including comments, CDATA and whitespace. Selecting a duplicated resource
still fails, even with an exact imported locator. Canonical import rules remain
unchanged. Unsupported source structures are reported as preparation failures:
no commit has been sent, and **Check and retry** can prepare the same approval
again after the problem is resolved.

When the working branch already differs from the import at the first MOKO edit,
the worker can preserve that existing work and apply only the approved text.
Every selected key must remain unique and retain its expected text and structure;
changed targets are blocked. Subsequent approvals require the last verified
working-file digest and preserve the same branch baseline. External file changes
after the first recorded commit remain blocked. This initial alignment supports
edits to existing MOKO values; insertions and other formats require a matching
baseline.

The send intent is persisted before each network mutation. Duplicate deliveries
cannot create another commit. After an uncertain response, **Check and retry**
only reconciles that exact intent; it does not resend an unverified mutation.
An unresolved operation stops later commits and PR creation. The approval snapshot,
commit receipt and content-free audit events remain available for investigation.
Open PR state is refreshed in the background, normally once every 15 minutes.

The strings workspace shows **Pending** for a saved change awaiting approval.
After approval it shows **Approved**, plus **Awaiting <target branch>** when approval
commits are enabled. A commit on the working branch does not clear that indicator.
Celery checks the current approved version against the configured target branch,
normally once every 15 minutes. It compares every selected key, language and selector at
one immutable target commit; missing, ambiguous or different values remain awaiting
integration. This also supports manual merges, squash merges and a target branch
different from the import branch. Checking never creates a commit or a PR.

Once all approved values are verified on the target, the workspace removes the
badges and change highlighting. History and the approved snapshot remain available.
A later edit starts a new pending version; an older approval's check cannot clear
it. Re-importing the matching text does not raise a false reconciliation warning.
A verified removal or reversal on the target restores the awaiting indicator.
Transient provider failures retain the last verified observation and retry on a
later check. Visible first-page results refresh every 30 seconds while awaiting
integration, except while an editor is open; longer result lists update on reload.

When a product has more than one workflow, an explicit PR request must include
`workflow_id` in `POST /products/{product_id}/branch-workflow/pull-request`.
The history endpoint accepts the same query parameter. The API rejects an ambiguous
PR request instead of choosing a destination. Neither configuration, approval nor
background polling opens a PR. The translation detail explains approval commits
and links to their history instead of offering the legacy submission action.

## Verification

`test_branch_workflow.py` covers both imported edits and new translations,
consecutive approvals, concurrent duplicate approvals and deliveries, worker crashes,
commit and PR timeouts, external changes, permission revocation, long paths,
multiple translation sources, equivalent configuration publication and explicit PR
creation. The API tests exercise configuration, product
visibility, publication roles, duplicate requests and the legacy submission boundary.

The built-stack browser test uses only synthetic repositories and the TLS Bitbucket
fixture. It configures branches through the browser and verifies actual worker
dispatch, separate commits on `feature/verboflex`, duplicate approval rejection,
zero PRs until the explicit browser action, then exactly one PR to `master`, and
the interface at 320 pixels and 200% zoom. Other branch names are covered by the
unit and integration tests.

The smoke also imports Kotlin/Java keys with a separate shared MOKO catalog,
approves a unique base-language key twice, and checks two sequential commits,
exact preservation of unrelated duplicate resources and zero PRs. Synthetic
writer tests additionally reject ambiguous targets, stale locators and
unsupported content following a duplicate.
The shared catalog smoke also starts from an existing branch with different
unrelated entries, preserves those differences across approvals, and verifies
that a later external file edit blocks the next approval without another commit.

```sh
BRANCH_WORKFLOW_SMOKE_ONLY=1 PHASE8_HTTP_SETUP=1 \
  PHASE7_EVIDENCE_DIR=/tmp/verboflex-approval-branches bash tools/phase7_smoke.sh
```

The same scenario also runs at the end of the complete application smoke.

Reapproving text that is already present on the working branch does not create
an empty commit. The worker first verifies the complete rendered files against
the immutable branch head, then records that existing commit and releases the
serial queue. Later drafts remain unpublished. External file changes still block
the operation, and uncertain sends still require read-only reconciliation.

Background PR and target-content observations run no more than once every 15 minutes
per job. A provider rate-limit response delays that observation for one hour,
preserving the last verified result. New approvals and explicit PR requests still
enter the worker queue immediately. This prevents observation traffic from
continually exhausting the shared provider budget needed by imports.

## Approve all new-entry drafts

Reviewers can select **Approve all drafts** beside **New entries** in the strings
workspace. The confirmation shows the server-side project total and counts by
language, including entries beyond the first page. This action covers draft new
keys/translations, not rejected entries or existing-value proposals. Saved texts
and the configured base language are preserved. The maximum is 5,000 drafts.

The preview binds the exact draft versions and current sources. Confirmation
creates a durable operation; Celery performs the same validation as single-entry
approval, rechecks reviewer authority, and atomically approves the selection with
one immutable commit job per mapped source. If any draft changed or fails
validation, all approvals roll back and the interface identifies the problem.
Correct it and confirm a fresh preview to retry. No pull request is opened.
Products without approval branches retain local approvals for the existing
change-set workflow. Delivery failures remain visible in **Approval commits**.

The operation continues after navigating away. Reloading discovers its status
from the server. Duplicate confirmations reuse their operation ID; simultaneous
operations for one product are rejected. A database row lock prevents concurrent
workers from processing the same selection. A worker crash rolls back approvals
and leaves the queued request available to the durable ten-second dispatcher.
HTTP only previews and records requests; repository work stays in Celery.

API: `GET /api/v1/products/{product_id}/authoring/approval-preview` and
`PUT /api/v1/products/{product_id}/authoring/approvals/{request_id}` with
`{ "fingerprint": "<preview fingerprint>" }`. The latter returns 202 with durable
status. Preview and confirmation both require current product review permission.


## Catalog refresh after commits

A verified working-branch commit records a durable catalog-refresh receipt in the
same database transaction. The Celery dispatcher coalesces pending commits for a
workflow into one normal import, after queued branch writes finish. This applies
only when the configured translation import source is already the working branch;
it never changes a source branch or the project's base language. Existing historical
commits are not automatically backfilled when the feature is deployed.

The normal import permission, connection and source-confirmation checks still apply.
A broker failure is retried from the recorded execution without another commit.
A failed import leaves saved entries visible and offers **Update catalog**.
Successful imports consume only additions that exactly match repository values;
unmatched drafts retain their text and normal source-change checks. Source changes
may require reopening and saving those drafts before another approval.

**New entries** identifies the last bulk approval as historical and reports actual
branch delivery and catalog-refresh state. A completed batch is not presented as
new work still queued. **Change sets** reports catalog progress for individual jobs.
Refresh never approves drafts or opens a pull request. The strings workspace refreshes
small visible result sets while approved additions await import, without replacing
an open editor. Saved changes also refresh the current search immediately.
