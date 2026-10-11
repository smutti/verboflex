import type { ChangeSetResponse } from "../../api/client";

const statuses: Record<ChangeSetResponse["status"], string> = {
  queued: "Queued",
  running: "Working",
  reconciling: "Checking submission outcome",
  blocked: "Needs review",
  failed: "Submission failed",
  succeeded: "Pull request opened",
  needs_attention: "Submission needs attention",
  resolved: "Submission resolved",
};
const stages: Record<ChangeSetResponse["stage"], string> = {
  branch: "Creating branch",
  commit: "Committing changes",
  pull_request: "Opening pull request",
  complete: "Complete",
};
export const pullRequestProblems: Record<
  string,
  { title: string; detail: string }
> = {
  pr_merge_conflicts: {
    title: "Merge conflicts",
    detail: "Resolve conflicts in the repository, then check status.",
  },
  pr_content_changed: {
    title: "PR changes need review",
    detail: "The current PR differs from the approved changes.",
  },
  pr_check_unavailable: {
    title: "PR check incomplete",
    detail: "Could not verify the PR. Check status again.",
  },
  pr_changed_during_check: {
    title: "PR changed during check",
    detail: "Check status again to verify the latest commits.",
  },
  pr_identity_changed: {
    title: "PR identity changed",
    detail: "The PR no longer matches this submission.",
  },
};

export function submissionStatus(record: ChangeSetResponse) {
  if (
    record.status === "needs_attention" &&
    record.error_code &&
    pullRequestProblems[record.error_code]
  )
    return pullRequestProblems[record.error_code].title;
  if (
    record.status === "succeeded" &&
    record.pr_tracking?.content_status === "verified"
  )
    return "Rebase verified";
  if (record.status === "running" && record.pr_id)
    return "Checking pull request";
  return record.status === "running"
    ? stages[record.stage]
    : statuses[record.status];
}
export function submissionActive(record: ChangeSetResponse) {
  return (
    record.status === "queued" ||
    record.status === "running" ||
    record.status === "reconciling"
  );
}
export function nextSubmissionPollDelay(elapsed: number) {
  if (!Number.isFinite(elapsed) || elapsed >= 90_000) return null;
  return Math.min(
    elapsed < 30_000 ? 2_000 : 5_000,
    90_000 - Math.max(0, elapsed),
  );
}
