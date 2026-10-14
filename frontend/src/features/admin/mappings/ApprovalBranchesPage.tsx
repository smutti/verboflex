import { useEffect, useState, type FormEvent } from "react";
import {
  configureBranchWorkflow,
  getBranchWorkflow,
  type BranchWorkflowResponse,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";

export function ApprovalBranchesPage({
  accessToken,
  productId,
}: {
  accessToken: string;
  productId: string;
}) {
  const [data, setData] = useState<BranchWorkflowResponse>();
  const [mappingId, setMappingId] = useState("");
  const [workBranch, setWorkBranch] = useState("");
  const [targetBranch, setTargetBranch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    void getBranchWorkflow({
      auth: accessToken,
      path: { product_id: productId },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.data) {
          if ([401, 403, 404].includes(result.response?.status ?? 0))
            setData(undefined);
          throw new Error("unavailable");
        }
        setData(result.data);
        setError("");
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError("Approval branches could not be loaded.");
      });
    return () => controller.abort();
  }, [accessToken, productId, reload]);
  const available = (data?.available_mappings ?? []).filter(
    (m) => !m.workflow_id,
  );
  const selected = available.find((m) => m.mapping_id === mappingId);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected || busy) return;
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const result = await configureBranchWorkflow({
        auth: accessToken,
        path: { product_id: productId },
        body: {
          mapping_id: selected.mapping_id,
          work_branch: workBranch.trim(),
          target_branch: targetBranch.trim(),
        },
      });
      if (!result.data) {
        if ([401, 403, 404].includes(result.response?.status ?? 0))
          setData(undefined);
        const detail =
          result.error && "detail" in result.error
            ? result.error.detail
            : undefined;
        setError(
          typeof detail === "string"
            ? detail
            : "The branches could not be saved. Check the configuration and try again.",
        );
        return;
      }
      setData(result.data);
      setMappingId("");
      setWorkBranch("");
      setTargetBranch("");
      setSaved(true);
    } catch {
      setError(
        "The branches could not be saved. Your entries are retained; you can retry.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="grid min-w-0 gap-6"
      aria-labelledby="approval-branches-title"
    >
      <div>
        <h1 id="approval-branches-title" className="text-display font-semibold">
          Approval branches
        </h1>
        <p className="text-muted-foreground">
          Save a draft in VerboFlex, approve it to create a commit, then open a
          pull request when ready.
        </p>
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Configuration unavailable</AlertTitle>
          <AlertDescription>
            {error}
            <Button variant="outline" onClick={() => setReload((n) => n + 1)}>
              Reload configuration
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {!data && !error && <p role="status">Loading approval branches…</p>}
      {saved && (
        <p role="status">
          Approval commits enabled. The next approval will be saved on the
          working branch.
        </p>
      )}
      {(data?.workflows ?? []).map((w) => (
        <div
          key={w.id}
          className="min-w-0 rounded-lg border bg-card p-4 wrap-anywhere"
        >
          <h2 className="font-semibold">{w.repository}</h2>
          <dl className="mt-2 grid gap-2 sm:grid-cols-2">
            <div>
              <dt className="text-sm text-muted-foreground">
                Working branch · approval commits
              </dt>
              <dd className="font-mono">{w.work_branch}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">
                PR destination · on request
              </dt>
              <dd className="font-mono">{w.target_branch}</dd>
            </div>
          </dl>
          {!w.active && (
            <p className="mt-2">
              This translation source is no longer active. Its history is
              retained.
            </p>
          )}
        </div>
      ))}
      {data && available.length > 0 && (
        <form
          onSubmit={(event) => void submit(event)}
          className="grid min-w-0 gap-4 rounded-lg border bg-card p-4"
        >
          <h2 className="text-heading font-semibold">
            Enable approval commits
          </h2>
          <p className="text-sm text-muted-foreground">
            Choose existing branches. Each approval creates a separate commit on
            the working branch. A pull request is opened only from Change sets
            when you request it.
          </p>
          <fieldset disabled={busy} className="grid min-w-0 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="approval-source">Translation source</Label>
              <select
                id="approval-source"
                value={mappingId}
                onChange={(e) => {
                  setMappingId(e.target.value);
                  setSaved(false);
                  const m = available.find(
                    (item) => item.mapping_id === e.target.value,
                  );
                  setTargetBranch(m?.source_branch ?? "");
                }}
                required
                className="min-h-11 min-w-0 w-full rounded-md border bg-background px-3"
              >
                <option value="">Select a translation source</option>
                {available.map((m) => (
                  <option key={m.mapping_id} value={m.mapping_id}>
                    {m.repository} · import from {m.source_branch}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="approval-work-branch">Working branch</Label>
                <Input
                  id="approval-work-branch"
                  value={workBranch}
                  onChange={(e) => setWorkBranch(e.target.value)}
                  placeholder="feature/translations"
                  required
                  maxLength={255}
                  autoComplete="off"
                />
                <p className="text-sm text-muted-foreground">
                  Approved changes are committed here.
                </p>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="approval-target-branch">PR destination</Label>
                <Input
                  id="approval-target-branch"
                  value={targetBranch}
                  onChange={(e) => setTargetBranch(e.target.value)}
                  placeholder="main"
                  required
                  maxLength={255}
                  autoComplete="off"
                />
                <p className="text-sm text-muted-foreground">
                  The pull request will propose merging into this branch.
                </p>
              </div>
            </div>
            <p className="text-sm text-muted-foreground">
              Finish existing change sets first. Once enabled, configure every
              translation source before approving its changes. Existing
              approvals are not committed retroactively.
            </p>
            <Button
              type="submit"
              className="w-fit"
              disabled={
                !selected || !workBranch.trim() || !targetBranch.trim() || busy
              }
            >
              {busy ? "Saving…" : "Enable approval commits"}
            </Button>
          </fieldset>
        </form>
      )}
      {data && !(data.available_mappings ?? []).length && (
        <p>
          Publish a Bitbucket translation source to configure approval commits.
        </p>
      )}
    </section>
  );
}
