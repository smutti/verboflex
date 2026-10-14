# Approval commits and pull requests

An optional product workflow saves each approved translation to an existing working
branch in Bitbucket. Saving a draft still only saves it in VerboFlex. Approval
records an immutable snapshot and queues a separate commit. Later drafts or
approvals do not replace earlier queued snapshots.

In **Change sets**, users see each approval, its queue status and the resulting
commit link. **Create pull request** is a separate, explicit action. It becomes
available after all queued commits finish. An open PR automatically includes later
commits on the same working branch. Merging remains a Bitbucket action.

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

Both branches must already exist. The working branch must differ from the import
branch and the PR destination. With a separate code/translation mapping, only the
translation repository is written. The code repository remains an import source.
Each translation source can have its own workflow. With multiple sources, configure
each before approving its changes; **Change sets** lets users select the repository
branch and its history. A repository working branch cannot be shared by two
workflows. Branch configuration is immutable once enabled, preserving the meaning
of retained intents and history. Publishing a new configuration revision with the
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

The send intent is persisted before each network mutation. Duplicate deliveries
cannot create another commit. After an uncertain response, **Check and retry**
only reconciles that exact intent; it does not resend an unverified mutation.
An unresolved operation stops later commits and PR creation. The approval snapshot,
commit receipt and content-free audit events remain available for investigation.
Open PR state is refreshed in the background, normally once per minute.

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
unit and integration tests:

```sh
BRANCH_WORKFLOW_SMOKE_ONLY=1 PHASE8_HTTP_SETUP=1 \
  PHASE7_EVIDENCE_DIR=/tmp/verboflex-approval-branches bash tools/phase7_smoke.sh
```

The same scenario also runs at the end of the complete application smoke.
