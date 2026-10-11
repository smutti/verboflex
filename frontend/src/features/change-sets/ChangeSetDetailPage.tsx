import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getChangeSet,
  retryChangeSet,
  reconcileChangeSet,
  finalizeChangeSet,
  type ChangeSetResponse,
} from "../../api/client";
import { Alert, AlertTitle, AlertDescription } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { useChangeSetWorkspace } from "./changeSetContext";
import { useSubmissionPolling } from "./useSubmissionPolling";
import { submissionStatus, pullRequestProblems } from "./submissionStatus";
import { PullRequestLink, SourceProvenance } from "./SubmissionPresentation";
import { useSubmissionBatchPolling } from "./useSubmissionBatchPolling";
import { SubmissionPages } from "./SubmissionPages";

export function ChangeSetDetailPage() {
  const { accessToken, productId } = useChangeSetWorkspace();
  const id = useParams<"changeSetId">().changeSetId ?? "";
  return <DetailLoader key={`${accessToken}:${productId}:${id}`} id={id} />;
}
function Unavailable() {
  return (
    <Alert>
      <AlertTitle>Change set unavailable</AlertTitle>
      <AlertDescription>
        This change set is unavailable to your account.
      </AlertDescription>
    </Alert>
  );
}
function DetailLoader({ id }: { id: string }) {
  const { accessToken, productId, setReturnFocus, revokeRead } =
    useChangeSetWorkspace();
  const [record, setRecord] = useState<ChangeSetResponse>();
  const [error, setError] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    void getChangeSet({
      auth: accessToken,
      path: { product_id: productId, change_set_id: id },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if ([401, 403, 404].includes(result.response?.status ?? 0)) {
          setUnavailable(true);
          revokeRead();
          return;
        }
        if (!result.data || result.data.id !== id)
          throw new Error("Unavailable");
        setRecord(result.data);
        setError(false);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      });
    return () => controller.abort();
  }, [accessToken, productId, id, reload, revokeRead]);
  return (
    <div className="grid min-w-0 gap-(--space-lg)">
      <Link
        className="inline-flex min-h-[44px] items-center underline"
        to={`/products/${encodeURIComponent(productId)}/change-sets/history`}
        onClick={() => setReturnFocus(`history-${id}`)}
      >
        Back to submission history
      </Link>
      {unavailable ? (
        <Unavailable />
      ) : record ? (
        <LoadedDetail initial={record} />
      ) : error ? (
        <Alert>
          <AlertTitle>Change set could not be loaded</AlertTitle>
          <AlertDescription>
            <Button variant="outline" onClick={() => setReload((n) => n + 1)}>
              Retry loading change set
            </Button>
          </AlertDescription>
        </Alert>
      ) : (
        <p role="status">Loading change set…</p>
      )}
    </div>
  );
}
function LoadedDetail({ initial }: { initial: ChangeSetResponse }) {
  const { accessToken, productId, revokeRead } = useChangeSetWorkspace();
  const [unavailable, setUnavailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const controller = useRef<AbortController | undefined>(undefined);
  const [actionError, setActionError] = useState(false);
  const summary = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const lostAccess = useCallback(() => {
    setUnavailable(true);
    revokeRead();
  }, [revokeRead]);
  const polling = useSubmissionPolling(
    accessToken,
    productId,
    initial,
    lostAccess,
  );
  const record = polling.record;
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    return () => controller.current?.abort();
  }, []);
  const siblingPolling = useSubmissionBatchPolling(
    accessToken,
    productId,
    record,
    lostAccess,
  );
  const batch = siblingPolling.batch;
  async function action(kind: "retry" | "reconcile" | "finalize") {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setActionError(false);
    const abort = new AbortController();
    controller.current = abort;
    try {
      const call =
        kind === "retry"
          ? retryChangeSet
          : kind === "reconcile"
            ? reconcileChangeSet
            : finalizeChangeSet;
      const result = await call({
        auth: accessToken,
        path: { product_id: productId, change_set_id: record.id },
        body: { expected_attempt: record.attempt },
        signal: abort.signal,
      });
      if (abort.signal.aborted) return;
      if ([401, 403, 404].includes(result.response?.status ?? 0)) {
        lostAccess();
        return;
      }
      if (!result.data) throw new Error("Unavailable");
      polling.accept(result.data);
    } catch {
      if (!abort.signal.aborted) {
        setActionError(true);
        queueMicrotask(() => summary.current?.focus());
        polling.refresh();
      }
    } finally {
      if (!abort.signal.aborted) {
        busyRef.current = false;
        setBusy(false);
      }
    }
  }
  if (unavailable || polling.unavailable) return <Unavailable />;
  const siblings = batch?.groups.map((group) =>
    group.id === record.id ? record : group,
  ) ?? [record];
  const success = siblings.filter((group) => group.pr_id !== null).length;
  return (
    <section
      className="grid min-w-0 gap-(--space-xl)"
      aria-labelledby="change-set-detail-heading"
    >
      <h2
        ref={heading}
        tabIndex={-1}
        id="change-set-detail-heading"
        className="text-heading font-semibold"
      >
        Change set
      </h2>
      <p role="status" className="sr-only">
        {polling.announcement}
      </p>
      <section
        className="grid min-w-0 gap-(--space-md) rounded-lg border p-(--space-lg)"
        aria-label="Submission status"
      >
        <h3 className="text-heading font-semibold">
          {submissionStatus(record)}
        </h3>
        <p className="wrap-anywhere">
          {record.workspace}/{record.repository_slug} · Repository{" "}
          {record.repository_id}
        </p>
        <p>
          {record.proposal_count} proposals · {record.value_count} values ·{" "}
          {record.file_count} files · Attempt {record.attempt}
        </p>
        <p className="wrap-anywhere">
          Submitted by {record.actor?.display_name ?? "Unknown user"}
        </p>
        <p>
          Accepted {new Date(record.created_at).toLocaleString()}
          {record.finished_at
            ? ` · Finished ${new Date(record.finished_at).toLocaleString()}`
            : ""}
        </p>
        <p className="wrap-anywhere">
          Pull request source branch: {record.source_branch}
        </p>
        <p className="wrap-anywhere">
          Target branch: {record.target_branch} · Captured head{" "}
          {record.target_head}
        </p>
        {record.branch_commit && (
          <p className="wrap-anywhere">
            Verified branch commit: {record.branch_commit}
          </p>
        )}
        {record.commit_hash && (
          <p className="wrap-anywhere">
            Submitted commit: {record.commit_hash}
          </p>
        )}
        {record.pr_state && <p>Pull request state: {record.pr_state}</p>}
        {record.pr_tracking && (
          <div className="grid gap-1 rounded-md border p-3">
            {record.status === "succeeded" &&
              record.pr_tracking.content_status === "verified" && (
                <p className="font-semibold text-emerald-700 dark:text-emerald-400">
                  Approved changes preserved. No Git conflicts.
                </p>
              )}
            <p className="wrap-anywhere">
              Current PR commit: {record.pr_tracking.source_commit}
            </p>
            <p className="wrap-anywhere">
              Current base commit: {record.pr_tracking.target_commit}
            </p>
            <p className="text-muted-foreground">
              Checked {new Date(record.pr_tracking.checked_at).toLocaleString()}
            </p>
          </div>
        )}
        <PullRequestLink record={record} />
        {record.status === "reconciling" && (
          <p>
            {record.pr_id
              ? "Checking the current PR."
              : "Checking the submission outcome."}
          </p>
        )}
        {record.status === "blocked" && (
          <p>
            Review the current proposal and repository configuration before
            continuing.
          </p>
        )}
        {record.error_code &&
          (pullRequestProblems[record.error_code] ? (
            <Alert variant="destructive" className="border-destructive">
              <AlertTitle>
                {pullRequestProblems[record.error_code].title}
              </AlertTitle>
              <AlertDescription>
                {pullRequestProblems[record.error_code].detail}
              </AlertDescription>
            </Alert>
          ) : (
            <p className="wrap-anywhere">
              Reason: {record.error_code.replaceAll("_", " ")}
            </p>
          ))}
        {record.recovery_reason && (
          <p>{record.recovery_reason.replaceAll("_", " ")}</p>
        )}
        <div className="flex flex-wrap gap-(--space-sm)">
          {record.can_retry && (
            <Button disabled={busy} onClick={() => void action("retry")}>
              Retry submission
            </Button>
          )}
          {record.can_reconcile && (
            <Button disabled={busy} onClick={() => void action("reconcile")}>
              Check status
            </Button>
          )}
          {record.can_finalize && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => void action("finalize")}
            >
              Release changes for a new review
            </Button>
          )}
          {record.status === "blocked" && (
            <Button asChild variant="outline">
              <Link
                to={`/products/${encodeURIComponent(productId)}/change-sets`}
              >
                Review latest changes
              </Link>
            </Button>
          )}
        </div>
        {record.can_finalize && (
          <p>
            Releasing permits a fresh review. Any recorded branch or commit
            remains in Bitbucket.
          </p>
        )}
        {actionError && (
          <Alert ref={summary} tabIndex={-1} variant="destructive">
            <AlertTitle>Submission action could not be confirmed</AlertTitle>
            <AlertDescription>
              The recorded status is being refreshed. Check the latest attempt
              before another action.
            </AlertDescription>
          </Alert>
        )}
        {(polling.error || siblingPolling.error) && (
          <Alert>
            <AlertTitle>Status could not be refreshed</AlertTitle>
            <AlertDescription>
              The last known status is shown. Refresh to check for updates.
            </AlertDescription>
          </Alert>
        )}
        {(polling.paused || siblingPolling.paused) && (
          <p>Automatic updates paused. The job may still be running.</p>
        )}
        <p>
          Last status read:{" "}
          <time dateTime={polling.updatedAt}>
            {new Date(polling.updatedAt).toLocaleString()}
          </time>
        </p>
        <Button
          className="w-fit"
          variant="outline"
          onClick={() => {
            polling.refresh();
            siblingPolling.refresh();
          }}
        >
          Refresh status
        </Button>
      </section>
      {siblings.length > 1 && (
        <section
          aria-label="Related submissions"
          className="grid gap-(--space-md)"
        >
          <h3 className="text-heading font-semibold">
            {success} of {siblings.length} pull requests opened
          </h3>
          <p>Review each remaining change set for its next action.</p>
          <ul>
            {siblings.map((group) => (
              <li
                key={group.id}
                className="min-w-0 space-y-(--space-sm) border-b py-(--space-md) wrap-anywhere"
              >
                <Link
                  className="inline-flex min-h-[44px] items-center underline"
                  to={`/products/${encodeURIComponent(productId)}/change-sets/${encodeURIComponent(group.id)}`}
                >
                  {group.repository_slug} → {group.target_branch}:{" "}
                  {submissionStatus(group)}
                </Link>
                <PullRequestLink record={group} />
              </li>
            ))}
          </ul>
        </section>
      )}
      <section
        aria-label="Source provenance"
        className="grid min-w-0 gap-(--space-md)"
      >
        <h3 className="text-heading font-semibold">Source provenance</h3>
        {record.provenance_available ? (
          <SourceProvenance sources={record.sources ?? []} />
        ) : (
          <p>
            Source provenance unavailable. Recorded submission evidence remains
            readable.
          </p>
        )}
      </section>
      <SubmissionPages id={record.id} onUnavailable={lostAccess} />
    </section>
  );
}
