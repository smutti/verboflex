import { CheckCircle2, Clock3, GitBranch } from "lucide-react";

type ProposalStatus = {
  state: "draft" | "approved" | "rejected";
  target_branch?: string | null;
  target_integrated?: boolean;
};

export function TranslationStatusBadge({
  proposal,
}: {
  proposal: ProposalStatus;
}) {
  if (proposal.state === "approved" && proposal.target_integrated) return null;
  const approved = proposal.state === "approved";
  const Icon = approved ? CheckCircle2 : Clock3;
  return (
    <span
      className="inline-flex max-w-full flex-wrap items-center gap-2"
      aria-label="Translation status"
    >
      <span
        className={`my-1 inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-label font-semibold ${approved ? "border-blue-300 bg-blue-50 text-blue-900 dark:border-blue-700 dark:bg-blue-950/50 dark:text-blue-200" : "border-amber-300 bg-amber-100 text-amber-950 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-200"}`}
        title={
          proposal.state === "rejected"
            ? "Rejected; changes need review before approval."
            : undefined
        }
      >
        <Icon aria-hidden="true" className="size-3.5 shrink-0" />
        {approved ? "Approved" : "Pending"}
      </span>
      {approved && proposal.target_branch && (
        <span
          className="inline-flex min-w-0 items-center gap-1 rounded-md border px-1.5 py-0.5 text-label text-muted-foreground"
          title={`The approved text has not yet been verified on ${proposal.target_branch}.`}
        >
          <GitBranch aria-hidden="true" className="size-3.5 shrink-0" />
          <span className="wrap-anywhere">
            Awaiting {proposal.target_branch}
          </span>
        </span>
      )}
    </span>
  );
}
