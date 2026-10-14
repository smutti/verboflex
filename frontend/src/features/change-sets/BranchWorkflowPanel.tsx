import { useEffect, useState, type ReactNode } from "react";
import {
  createBranchPullRequest,
  getBranchWorkflow,
  retryBranchChange,
  type BranchWorkflowResponse,
} from "../../api/client";
import { Button } from "../../components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { useChangeSetWorkspace } from "./changeSetContext";

const states: Record<string, string> = {
  queued: "Waiting to save",
  running: "Saving to branch…",
  sending: "Checking Git result…",
  committed: "Saved to branch",
  open: "Pull request open",
  merged: "Merged",
  declined: "Pull request closed",
  blocked: "Needs attention",
};
const errors: Record<string, string> = {
  unsupported_shape:
    "The translation file contains a structure that cannot be edited safely. No commit was sent. Check the source file before retrying.",
  ambiguous_locator:
    "The translation key is duplicated or its location is ambiguous. No commit was sent. Check the source file before retrying.",
  file_changed: "The file changed in Git. Review the branch before continuing.",
  source_file_changed:
    "The approved string or its structure changed on the working branch. Refresh and review it before retrying.",
  import_changed:
    "The imported source changed. Refresh the product configuration before continuing.",
  authority_changed:
    "Repository access changed. An authorized reviewer can retry.",
  branch_advanced:
    "The branch changed while saving. Check the Git result before continuing.",
  no_changes: "The working branch has no new commits to publish.",
};

export function BranchWorkflowPanel({ children }: { children: ReactNode }) {
  const { accessToken, productId } = useChangeSetWorkspace();
  const [data, setData] = useState<BranchWorkflowResponse>();
  const [failure, setFailure] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [reload, setReload] = useState(0);
  const [before, setBefore] = useState<number>();
  const [workflowId, setWorkflowId] = useState<string>();
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const result = await getBranchWorkflow({
          auth: accessToken,
          path: { product_id: productId },
          query: { before, workflow_id: workflowId },
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (!result.data) {
          if ([401, 403, 404].includes(result.response?.status ?? 0))
            setData(undefined);
          throw new Error("unavailable");
        }
        setData(result.data);
        setFailure(false);
        if (result.data.enabled) timer = setTimeout(() => void load(), 5000);
      } catch {
        if (!controller.signal.aborted) setFailure(true);
      }
    }
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [accessToken, productId, reload, before, workflowId]);
  async function act(jobId?: string) {
    setBusy(true);
    setFailure(false);
    try {
      const result = jobId
        ? await retryBranchChange({
            auth: accessToken,
            path: { product_id: productId, job_id: jobId },
          })
        : await createBranchPullRequest({
            auth: accessToken,
            path: { product_id: productId },
            query: { workflow_id: data?.workflow_id ?? undefined },
          });
      if (!result.data) {
        if ([401, 403, 404].includes(result.response?.status ?? 0))
          setData(undefined);
        throw new Error("unavailable");
      }
      setData(result.data);
      setBefore(undefined);
      setConfirm(false);
      setReload((n) => n + 1);
    } catch {
      setFailure(true);
    } finally {
      setBusy(false);
    }
  }
  if (data && !data.enabled) return children;
  if (!data && !failure)
    return <p role="status">Loading repository workflow…</p>;
  const items = data?.items ?? [];
  return (
    <section
      className="grid min-w-0 gap-(--space-lg)"
      aria-label="Approved changes on branch"
    >
      {failure && (
        <Alert variant="destructive">
          <AlertTitle>Repository workflow unavailable</AlertTitle>
          <AlertDescription>
            The request could not be completed. Your saved changes are retained.
            <Button variant="outline" onClick={() => setReload((n) => n + 1)}>
              Reload status
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {data?.enabled && (
        <>
          <div>
            <h2 className="text-heading font-semibold">Approved changes</h2>
            {(data.workflows?.length ?? 0) > 1 && (
              <label className="my-3 grid gap-2">
                Repository branch
                <select
                  className="min-h-11 min-w-0 w-full rounded-md border bg-background px-3"
                  value={data.workflow_id ?? ""}
                  disabled={busy}
                  onChange={(event) => {
                    setWorkflowId(event.target.value);
                    setBefore(undefined);
                    setConfirm(false);
                    setData(undefined);
                  }}
                >
                  {data.workflows?.map((workflow) => (
                    <option key={workflow.id} value={workflow.id}>
                      {workflow.repository} · {workflow.work_branch} →{" "}
                      {workflow.target_branch}
                      {workflow.active ? "" : " (inactive)"}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <p className="text-muted-foreground">
              Each approval is saved as a commit in {data.repository} on{" "}
              <strong>{data.work_branch}</strong>.
            </p>
            <p className="text-muted-foreground">
              Open a pull request to <strong>{data.target_branch}</strong> when
              the changes are ready.
            </p>
          </div>
          {data.can_publish && (
            <div>
              {!confirm ? (
                <Button
                  disabled={!data.can_create_pr || busy || failure}
                  onClick={() => setConfirm(true)}
                >
                  Create pull request
                </Button>
              ) : (
                <div className="flex flex-wrap items-center gap-(--space-md)">
                  <p>
                    Create a PR from {data.work_branch} to {data.target_branch}?
                  </p>
                  <Button
                    disabled={busy || failure || !data.can_create_pr}
                    onClick={() => void act()}
                  >
                    {busy ? "Creating…" : "Confirm pull request"}
                  </Button>
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() => setConfirm(false)}
                  >
                    Cancel
                  </Button>
                </div>
              )}
            </div>
          )}
          {!items.length && (
            <p>
              No approvals saved yet. Approve a translation in Strings to save
              its first commit.
            </p>
          )}
          <ol className="grid gap-(--space-md)" aria-label="Branch history">
            {items.map((item) => (
              <li
                key={item.id}
                className="flex min-w-0 flex-wrap items-center gap-(--space-md) rounded-lg border bg-card p-(--space-md)"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-semibold wrap-anywhere">{item.label}</p>
                  <p
                    role={
                      ["queued", "running", "sending"].includes(item.state)
                        ? "status"
                        : undefined
                    }
                  >
                    {states[item.state]}
                  </p>
                  <time
                    className="text-sm text-muted-foreground"
                    dateTime={item.created_at}
                  >
                    {new Date(item.created_at).toLocaleString()}
                  </time>
                  {item.error_code && (
                    <p>
                      {errors[item.error_code] ??
                        "The Git result could not be verified. Check its status before continuing."}
                    </p>
                  )}
                </div>
                {item.commit_url && (
                  <a
                    className="text-primary underline"
                    href={item.commit_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Commit {item.commit_hash?.slice(0, 7)}
                  </a>
                )}
                {item.pr_url && (
                  <a
                    className="text-primary underline"
                    href={item.pr_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open pull request
                  </a>
                )}
                {item.can_retry && (
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() => void act(item.id)}
                  >
                    Check and retry
                  </Button>
                )}
              </li>
            ))}
          </ol>
          <div className="flex gap-(--space-md)">
            {before && (
              <Button variant="outline" onClick={() => setBefore(undefined)}>
                Latest changes
              </Button>
            )}
            {data.next_before && (
              <Button
                variant="outline"
                onClick={() => setBefore(data.next_before ?? undefined)}
              >
                Older changes
              </Button>
            )}
          </div>
        </>
      )}
    </section>
  );
}
