# API Coverage — Bitbucket Cloud OAuth 2.0 and REST

> Full coverage by default. Opt-outs are explicit, reasoned decisions. Phase 2 uses the OAuth consumer's exact read-only `repository` permission and does not claim an unverified provider revocation endpoint.

| capability | decision | reason |
|---|---|---|
| oauth-authorization-code-start | INTEGRATE | |
| oauth-authorization-code-exchange | INTEGRATE | |
| oauth-refresh-token-exchange-and-rotation | INTEGRATE | |
| oauth-effective-scope-inspection | INTEGRATE | |
| repository-metadata-by-workspace-and-slug | INTEGRATE | |
| branch-listing-with-provider-pagination | INTEGRATE | |
| branch-to-commit-resolution | INTEGRATE | |
| source-tree-directory-pagination | INTEGRATE | |
| raw-source-file-read-at-commit | INTEGRATE | |
| provider-next-url-validation | INTEGRATE | |
| oauth-provider-side-token-revocation | OPT-OUT | No official Bitbucket Cloud provider revocation endpoint was verified; Phase 2 guarantees immediate local generation invalidation only. |
| repository-listing-and-search | OPT-OUT | Phase 2 registers an explicit workspace and repository slug, then reads that repository's metadata; broad account/workspace discovery is outside the approved setup contract. |
| account-profile-and-email | OPT-OUT | Repository preview needs no account/email scope and must not expand the exact read-only consumer permission. |
| workspace-membership-and-permissions | OPT-OUT | Organization membership administration is outside Phase 2 and would require unrelated authority. |
| project-listing-and-metadata | OPT-OUT | Products use configured repositories directly; Bitbucket project discovery is not part of the approved mapping contract. |
| workspace-and-project-administration | OPT-OUT | Phase 2 is a read-only repository consumer and performs no provider administration. |
| tag-listing-and-other-ref-discovery | OPT-OUT | Configuration selects source and target branches only; tags and other refs are not accepted mapping inputs. |
| commit-history-listing-and-search | OPT-OUT | Phase 2 resolves the selected branch to one commit and does not browse commit history. |
| commit-diff-diffstat-and-patch-read | OPT-OUT | Preview reads source at one commit and does not compare commits or expose diffs. |
| commit-status-read-and-write | OPT-OUT | Build/status reporting is unrelated to configuration preview and would add provider capability without a Phase 2 requirement. |
| source-file-create-update-delete | OPT-OUT | Provider source writes are reserved for the later write-back workflow and require explicit reauthorization. |
| branch-create-update-delete | OPT-OUT | Phase 2 only lists branches; branch mutation belongs to later submission work and requires write authority. |
| tag-create-update-delete | OPT-OUT | Tag mutation is not part of the repository-backed translation workflow in this phase. |
| commit-create | OPT-OUT | Phase 2 performs read-only validation and cannot create provider commits. |
| pull-request-list-and-read | OPT-OUT | No pull-request resource is needed to configure or preview a product in Phase 2. |
| pull-request-create-and-update | OPT-OUT | Pull-request automation is assigned to the later submission phase and requires a new permission profile plus reauthorization. |
| pull-request-merge-decline-and-approve | OPT-OUT | Provider pull-request workflow actions are outside the Phase 2 read-only control plane. |
| pull-request-comments-tasks-and-activity | OPT-OUT | Translation review context remains application-owned and Phase 2 does not integrate provider PR collaboration APIs. |
| pull-request-diff-and-diffstat | OPT-OUT | Phase 2 has no provider pull request and performs no write-back diff review. |
| repository-webhook-list-and-read | OPT-OUT | Preview is explicitly requested and polling-based; Phase 2 does not consume provider webhooks. |
| repository-webhook-create-update-delete | OPT-OUT | Webhook administration is outside Phase 2 and would require administrative provider authority. |
| repository-settings-and-permissions-admin | OPT-OUT | The organizational connection is a least-privilege reader and never modifies repository settings or permissions. |
| branch-restrictions-and-merge-checks-admin | OPT-OUT | Phase 2 records allowed application target branches but does not administer provider branch policy. |
| deploy-keys-access-keys-and-ssh-keys-admin | OPT-OUT | OAuth is the locked credential model and no provider key administration is permitted. |
| pipelines-list-and-read | OPT-OUT | CI pipeline state is not required for repository configuration or localization preview. |
| pipelines-run-stop-and-manage | OPT-OUT | Phase 2 cannot trigger or administer provider pipelines. |
| deployments-and-environments | OPT-OUT | Deployment metadata is unrelated to the administrator localization configuration scope. |
| issues-list-and-read | OPT-OUT | Bitbucket issues are not a source of localization configuration or review context. |
| issues-create-update-delete-and-comments | OPT-OUT | Phase 2 performs no issue-tracker mutation and requests no issue authority. |
| downloads-list-and-read | OPT-OUT | Localization sources are read from the repository source API, not repository downloads. |
| downloads-upload-and-delete | OPT-OUT | Phase 2 performs no provider artifact mutation. |
| wiki-read-and-write | OPT-OUT | Repository wiki content is not part of localization discovery and no wiki authority is requested. |
| snippets-read-and-write | OPT-OUT | Snippets are not configurable localization repositories in Phase 2. |
| code-search | OPT-OUT | Discovery traverses the selected repository source tree under explicit budgets and does not use provider-wide search. |
