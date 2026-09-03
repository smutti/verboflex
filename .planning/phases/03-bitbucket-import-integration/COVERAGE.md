# API Coverage — Bitbucket Cloud OAuth 2.0 and REST

> Full coverage by default. Opt-outs are explicit, reasoned decisions. Phase 3 validates the expanded organizational capability contract and executes repository reads only. Rows marked for Phase 8 are integrated as validated, server-reported capability now, while their provider mutations remain disabled until Phase 8.

| capability | decision | reason |
|---|---|---|
| oauth-client-credentials-acquisition | INTEGRATE | Phase 3 exchanges the organizational client credentials and validates the expanded effective capability. |
| oauth-client-credentials-reacquisition | INTEGRATE | Reconnect and expiry recovery reacquire one generation under the existing singleton authority. |
| oauth-effective-scope-inspection | INTEGRATE | The backend validates `pullrequest:write` and projects only closed readiness fields, never raw scope text. |
| oauth-legacy-read-only-generation-detection | INTEGRATE | Existing `repository`-only generations are reported as requiring reauthorization. |
| oauth-authorization-code-callback-and-refresh-token-flows | OPT-OUT | The locked organizational integration uses server-to-server client credentials and grants no browser callback or refresh-token authority. |
| oauth-provider-side-token-revocation | OPT-OUT | No verified Bitbucket Cloud provider revocation operation is required; local generation invalidation remains authoritative. |
| repository-metadata-by-workspace-and-slug | INTEGRATE | Each import may validate its configured repository while resolving the source. |
| repository-listing-and-search | OPT-OUT | Administrators register exact workspace and repository slugs; broad provider repository discovery is outside the product workflow. |
| branch-listing-with-provider-pagination | INTEGRATE | Existing configuration discovery remains available under the expanded connection profile. |
| branch-to-commit-resolution | INTEGRATE | Every import execution resolves each exact configured branch to an immutable commit. |
| branch-create | INTEGRATE | Capability is acquired, allowlisted, validated, and reported in Phase 3; execution is deferred to Phase 8 and no Phase 3 provider write is permitted. |
| branch-update | OPT-OUT | The workflow creates a dedicated source branch in Phase 8 and does not rewrite an existing provider branch. |
| branch-delete | OPT-OUT | Branch deletion is outside the translation pull-request workflow. |
| tag-listing-and-other-ref-discovery | OPT-OUT | Configured localization sources and targets are branches; tags and other ref families are not accepted mapping inputs. |
| tag-create-update-delete | OPT-OUT | Tag mutation is unrelated to translation imports or pull-request submission. |
| commit-ancestry-comparison | INTEGRATE | Phase 3 classifies equal, fast-forward, and rewritten source movement using bounded commit-exact reads. |
| commit-history-listing-and-search | OPT-OUT | Only the bounded ancestry predicate is integrated; user-facing history browsing and arbitrary commit search are outside the workflow. |
| commit-diffstat-between-source-commits | INTEGRATE | Phase 3 reads the complete bounded localization-file delta required before rewrite confirmation. |
| commit-patch-and-raw-diff-read | OPT-OUT | Reconciliation needs file-level added/modified/removed metadata, not raw patch bodies or source text in public state. |
| source-tree-directory-pagination | INTEGRATE | Import discovery traverses the selected commit under the inherited page, entry, depth, candidate, and byte ceilings. |
| raw-source-file-read-at-commit | INTEGRATE | Worker reads are bound to the resolved immutable commit and source bytes remain backend-only. |
| source-file-create-update | INTEGRATE | Capability is acquired, allowlisted, validated, and reported in Phase 3; source commit execution is deferred to Phase 8 after Phase 7 write-back proof. |
| source-file-delete | OPT-OUT | Translation write-back does not authorize deleting provider files. |
| source-commit-create | INTEGRATE | Capability is acquired, allowlisted, validated, and reported in Phase 3; commit execution remains disabled until Phase 8. |
| source-file-reference-metadata | INTEGRATE | Exact repository side, branch, commit, relative path, size, and digest metadata are retained per import execution. |
| provider-next-url-validation | INTEGRATE | Every provider continuation remains server-side and must pass the existing HTTPS host and endpoint-family allowlist. |
| pull-request-create | INTEGRATE | `pullrequest:write` readiness is validated and reported now; the provider call is not implemented or executable until Phase 8. |
| pull-request-list-and-read | OPT-OUT | Import and change-set job status are application-owned; provider pull-request browsing is not required. |
| pull-request-update | OPT-OUT | Updating or superseding an open translation pull request is outside the current roadmap scope. |
| pull-request-merge | OPT-OUT | VerboFlex opens pull requests but never merges them. |
| pull-request-approve | OPT-OUT | Provider approval remains in Bitbucket and is never application authority. |
| pull-request-decline | OPT-OUT | Declining provider pull requests is outside the platform workflow. |
| pull-request-comments-tasks-and-activity | OPT-OUT | Translation comments remain application-owned and are not mirrored into provider collaboration resources. |
| pull-request-diff-and-diffstat | OPT-OUT | Phase 3 compares source commits directly; no provider pull request exists during import. |
| pull-request-participants-and-default-reviewers | OPT-OUT | Reviewer assignment and provider-side approval policy are outside the configured v1 PR behavior. |
| commit-status-read-and-write | OPT-OUT | Build and commit-status integration is unrelated to localization imports and pull-request creation. |
| workspace-membership-and-permissions | OPT-OUT | Organizational membership administration is outside VerboFlex's internal role model. |
| workspace-and-project-administration | OPT-OUT | The connection must never administer Bitbucket workspaces or projects. |
| project-listing-and-metadata | OPT-OUT | Products reference exact repositories directly and do not discover Bitbucket projects. |
| account-profile-and-email | OPT-OUT | Provider account identity is not used for VerboFlex authentication or authorization. |
| repository-settings-and-permissions-admin | OPT-OUT | Repository settings and permission mutation are explicitly outside the application-owned operation allowlist. |
| repository-delete | OPT-OUT | Repository deletion is never part of the localization workflow. |
| branch-restrictions-and-merge-checks-admin | OPT-OUT | VerboFlex consumes configured branches and does not administer provider policy. |
| deploy-keys-access-keys-and-ssh-keys-admin | OPT-OUT | OAuth client credentials are the sole provider credential model; key administration is forbidden. |
| repository-webhook-list-and-read | OPT-OUT | Imports are explicitly manual and observed through application polling, not provider webhooks. |
| repository-webhook-create-update-delete | OPT-OUT | Scheduled or event-driven imports are outside Phase 3 and webhook administration is not authorized. |
| pipelines-list-and-read | OPT-OUT | Pipeline state is unrelated to source import capability. |
| pipelines-run-stop-and-manage | OPT-OUT | VerboFlex never controls provider CI pipelines. |
| deployments-and-environments | OPT-OUT | Provider deployment metadata is outside localization source management. |
| issues-list-and-read | OPT-OUT | Bitbucket issues are not a localization source or review record. |
| issues-create-update-delete-and-comments | OPT-OUT | Issue tracker mutation is unrelated to the approved product workflow. |
| downloads-list-and-read | OPT-OUT | Localization sources are read from commit-bound repository source endpoints. |
| downloads-upload-and-delete | OPT-OUT | Provider download artifacts are outside the workflow and never mutated. |
| wiki-read-and-write | OPT-OUT | Repository wiki content is not a localization source. |
| snippets-read-and-write | OPT-OUT | Snippets are not configurable localization repositories. |
| code-search | OPT-OUT | Import traversal is repository-, branch-, commit-, and budget-bound and does not use provider-wide search. |

