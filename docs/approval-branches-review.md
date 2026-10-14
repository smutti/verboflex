# Approval branch workflow review — 2026-10-14

Scope: approval intake, immutable snapshots, Celery dispatch, provider send/recovery,
explicit PR requests, product configuration and browser actions. Reviewed the
workflow introduced in `6925407` and applied the corrections below.

| Finding | Correction and regression evidence |
| --- | --- |
| A new-translation request could be approved again while already approved. | Reject an unchanged state, as for existing translations. Repeated and concurrent approval requests produce one queued operation. |
| A fresh product configuration permanently invalidated the workflow's mapping UUID. | Resolve the current mapping by its stable repository/import-branch identity. Real preview, publication and import tests verify subsequent commits retain their existing workflow. |
| Explicit recovery of an uncertain send waited for the ten-minute stale-worker timeout. | Ownerless recovery is eligible for the next dispatch; an uncertain PR response is reconciled without another POST. An active sending worker cannot be reset by the retry endpoint. |
| A blocked backlog could occupy all dispatcher slots and starve other products. | Dispatch only the first unfinished operation per workflow. A 110-job blocked backlog no longer prevents another product from committing. |
| Long supported repository paths could exceed PostgreSQL's primary-key index limit after the remote commit. | Index a fixed-length generated path digest and compare the full path before using a row. Tests cover a long path and migration of existing committed file state. |
| Translation details still offered the legacy submission entry point for approval-commit products. | Explain approval commits and use their history; omit the legacy submission action. |

The generalized configuration is available in **Product configuration → Approval
branches** for published Bitbucket sources. Each source can select a working branch
and PR destination. Multiple sources have independent queues/history; the API
requires an explicit workflow selection for their PR requests. Configuring branches
does not create commits or PRs, and previously approved drafts are not sent
retroactively.

## Verification

- 151 backend tests covering branch workflows, HTTP permissions, authoring,
  existing review/submission flows, Bitbucket adapters, mutation inventory,
  architecture boundaries and database maintenance passed.
- Two additional migration tests passed: complete upgrade/downgrade/upgrade and
  preservation of existing workflow/file history followed by another approval.
- 279 frontend tests passed, including product configuration, branch selection,
  explicit confirmation, translation details and legacy change sets.
- The built-stack browser smoke passed with PostgreSQL, Redis, Celery, scheduler,
  built frontend and a synthetic TLS Bitbucket service. Configuring the workflow
  through the browser produced three distinct approval commits on
  `feature/verboflex`, rejected a duplicate approval, observed zero PRs before the
  user action and exactly one PR to `master` after confirmation. Responsive
  checks passed at 320 pixels and 200% zoom.
- Ruff, mypy, frontend lint/build, generated API/MCP contracts and website checks
  passed.

No production translation changes or pull requests were created during verification.
Production configuration was inspected read-only: Babel uses `feature/verboflex`
and targets `master`.

## Operational boundaries

Provider effects run only in Celery. An uncertain send that cannot be proven from
remote evidence remains blocked; it is never automatically resent. Imported
authority changes and external edits to managed files still require resolution
before later work proceeds. Both configured branches must exist, a repository
working branch belongs to one workflow, and branch names remain bound to their
retained history. GitHub writes are outside this Bitbucket workflow.
