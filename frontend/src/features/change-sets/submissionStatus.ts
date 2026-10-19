import { t } from "@/i18n";
import type { ChangeSetResponse } from "../../api/client";

const statuses: Record<ChangeSetResponse["status"], string> = {
  get queued() {
    return t("Queued");
  },
  get running() {
    return t("Working");
  },
  get reconciling() {
    return t("Checking submission outcome");
  },
  get blocked() {
    return t("Needs review");
  },
  get failed() {
    return t("Submission failed");
  },
  get succeeded() {
    return t("Pull request opened");
  },
  get needs_attention() {
    return t("Submission needs attention");
  },
  get resolved() {
    return t("Submission resolved");
  },
};
const stages: Record<ChangeSetResponse["stage"], string> = {
  get branch() {
    return t("Creating branch");
  },
  get commit() {
    return t("Committing changes");
  },
  get pull_request() {
    return t("Opening pull request");
  },
  get complete() {
    return t("Complete");
  },
};
export const pullRequestProblems: Record<
  string,
  { title: string; detail: string }
> = {
  pr_merge_conflicts: {
    get title() {
      return t("Merge conflicts");
    },
    get detail() {
      return t("Resolve conflicts in the repository, then check status.");
    },
  },
  pr_content_changed: {
    get title() {
      return t("PR changes need review");
    },
    get detail() {
      return t("The current PR differs from the approved changes.");
    },
  },
  pr_check_unavailable: {
    get title() {
      return t("PR check incomplete");
    },
    get detail() {
      return t("Could not verify the PR. Check status again.");
    },
  },
  pr_changed_during_check: {
    get title() {
      return t("PR changed during check");
    },
    get detail() {
      return t("Check status again to verify the latest commits.");
    },
  },
  pr_identity_changed: {
    get title() {
      return t("PR identity changed");
    },
    get detail() {
      return t("The PR no longer matches this submission.");
    },
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
    return t("Rebase verified");
  if (record.status === "running" && record.pr_id)
    return t("Checking pull request");
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
