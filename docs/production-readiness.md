# Production readiness

Reviewed on 2026-10-04. The release target remains the internal-team v1 scope.
A green application workflow is the first checkpoint; it does not complete the
remaining release work below.

| Order | Work | Completion evidence |
| --- | --- | --- |
| 1 | Restore the full automated baseline and application CI | **Complete.** Commit `511435e9`: 3,188 backend, 998 frontend and 39 MCP tests, zero failures/skips; all contract, build and Docker checks passed in [GitHub run 37215420835](https://github.com/smutti/verboflex/actions/runs/37215420835). See [application checks](application-ci.md). |
| 2 | Complete Phase 8 audit and permissions | **Complete.** Transactional metadata audit, API/MCP policy inventory, current-authority checks and revoked-session UI teardown. Commit `382b8d9b`: 3,205 backend, 1,003 frontend and 39 MCP tests, zero failures/errors/skips; HTTP setup, comments, five PR paths and 17 fault groups passed in [GitHub run 37224425394](https://github.com/smutti/verboflex/actions/runs/37224425394). See [authorization and audit](authorization-and-audit.md). |
| 3 | Verify the production deployment | Chosen host/domain, HTTPS and OAuth URLs, protected secrets, versioned release images, migration rehearsal and rollback/restore on that environment. |
| 4 | Complete recovery and monitoring | Encrypted off-host backups, tested recovery from that copy, and delivered alerts for failed/stale backups, failed jobs and unhealthy services. See [backup and restore](backup-restore.md). |
| 5 | Validate the expected data volume | Representative load tests for browsing and filtering, bounded imports/reconciliation and summary updates, with measured latency and resource limits. Tens of millions of strings are not certified yet. |

## Current boundaries

- The CI provider is a controlled TLS fixture. It exercises repository effects
  without writing to real Bitbucket or GitHub repositories.
- Daily backups already perform a full temporary restore verification. They are
  currently local to the host; off-host storage and external alerts need a
  destination.
- GitHub public repositories support import, refresh and local review. Private
  GitHub repositories and GitHub write-back remain outside v1.
- Internal roles exist. Isolation between external customer organizations is a
  separate product requirement and has not been certified.
- GitHub currently refuses branch-protection configuration for this private
  repository on the current account plan. The aggregate **Application checks**
  job is available; making it a required merge check needs eligible plan support.
- Server and domain are not yet selected (confirmed on 2026-10-04). The backup
  destination and alert destination also remain to be defined.
- Historical Phase 4/5 closeout evidence remains open: complete live-provider,
  native assistive-technology, mention/notification focus and reconnect journeys.
  Passing the expanded Phase 8 smoke does not replace these source-bound checks.

## Database rollout

Migration `0037_mcp_maintenance_catalog` repairs maintenance after the MCP OAuth
schema additions. Migration `0038_audit_events` adds the content-free audit ledger.
Both were tested on disposable databases, including downgrade/re-upgrade and
rejection of unexpected foreign-key changes. This checkpoint did not migrate
the development database. Apply them with the matching application release after
the deployment backup and rehearsal. Audit recording begins with that release;
there is no historical backfill.
