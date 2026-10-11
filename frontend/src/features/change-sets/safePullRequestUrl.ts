import type { ChangeSetResponse } from "../../api/client";

export function safePullRequestUrl(
  record: Pick<
    ChangeSetResponse,
    "pr_url" | "pr_id" | "workspace" | "repository_slug"
  >,
): string | null {
  const { pr_url, pr_id, workspace, repository_slug } = record;
  if (!pr_url || !pr_id || !Number.isSafeInteger(pr_id) || pr_id < 1)
    return null;
  // Exact canonical spelling prevents URL parser normalization from accepting
  // dot segments, alternate escapes, whitespace or ambiguous repository paths.
  if (
    ![workspace, repository_slug].every((part) => /^[A-Za-z0-9_-]+$/.test(part))
  )
    return null;
  const expected = `https://bitbucket.org/${encodeURIComponent(workspace)}/${encodeURIComponent(repository_slug)}/pull-requests/${pr_id}`;
  return pr_url === expected ? pr_url : null;
}
