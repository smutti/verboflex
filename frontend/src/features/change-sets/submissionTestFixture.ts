import type { ChangeSetResponse } from "../../api/client";
export function submissionFixture(
  overrides: Partial<ChangeSetResponse> = {},
): ChangeSetResponse {
  return {
    id: "group",
    batch_id: "batch",
    status: "queued",
    stage: "branch",
    attempt: 1,
    repository_id: "repo",
    workspace: "acme",
    repository_slug: "mobile",
    target_branch: "main",
    target_head: "a".repeat(40),
    source_branch: "verboflex/change-set-group",
    proposal_count: 1,
    value_count: 1,
    file_count: 1,
    error_code: null,
    can_retry: false,
    can_reconcile: false,
    pr_id: null,
    pr_url: null,
    pr_state: null,
    created_at: new Date().toISOString(),
    attempt_started_at: new Date().toISOString(),
    ...overrides,
  };
}
