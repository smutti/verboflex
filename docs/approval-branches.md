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

An administrator enables the workflow with
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
One active mapping per product can use this workflow, and a repository working
branch cannot be shared by two products. Configuration is immutable once enabled.
Existing change sets must be completed before enabling it. Existing approvals are
not sent retroactively; the workflow starts with the next approval. Products
without this configuration keep the existing reviewed change-set workflow.

## Execution and recovery

Approval and its outbox row commit in one database transaction. Celery dispatches
pending rows every ten seconds and serializes effects per working branch. Each
commit includes a stable operation ID and content manifest. Provider reads and
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

## Verification

`test_branch_workflow.py` covers both imported edits and new translations,
consecutive approvals, queued snapshots, timeouts, external changes, permission
revocation and explicit PR creation. The API tests exercise configuration, product
visibility, publication roles, duplicate requests and the legacy submission boundary.

The built-stack browser test uses only synthetic repositories and the TLS Bitbucket
fixture. It verifies actual worker dispatch, multiple commits on one branch, no PR
before an explicit browser action, and the interface at 320 pixels and 200% zoom:

```sh
BRANCH_WORKFLOW_SMOKE_ONLY=1 PHASE8_HTTP_SETUP=1 \
  PHASE7_EVIDENCE_DIR=/tmp/verboflex-approval-branches bash tools/phase7_smoke.sh
```

The same scenario also runs at the end of the complete application smoke.
