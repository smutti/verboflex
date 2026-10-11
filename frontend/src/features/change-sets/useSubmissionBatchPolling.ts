import { useEffect, useRef, useState } from "react";
import {
  getSubmissionBatch,
  type SubmissionBatchResponse,
  type ChangeSetResponse,
} from "../../api/client";
import { submissionActive, nextSubmissionPollDelay } from "./submissionStatus";

export function useSubmissionBatchPolling(
  accessToken: string,
  productId: string,
  record: ChangeSetResponse,
  onUnavailable: () => void,
) {
  const [batch, setBatch] = useState<SubmissionBatchResponse>();
  const latest = useRef<SubmissionBatchResponse | undefined>(undefined);
  const [error, setError] = useState(false);
  const [paused, setPaused] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    function delay() {
      const active = (latest.current?.groups ?? []).filter(submissionActive);
      const delays = active
        .map((group) =>
          nextSubmissionPollDelay(
            Date.now() -
              Date.parse(group.attempt_started_at ?? group.created_at),
          ),
        )
        .filter((value): value is number => value !== null);
      return delays.length ? Math.min(...delays) : null;
    }
    async function read() {
      if (stopped || document.hidden) return;
      controller?.abort();
      const abort = new AbortController();
      controller = abort;
      try {
        const result = await getSubmissionBatch({
          auth: accessToken,
          path: { product_id: productId, batch_id: record.batch_id },
          signal: abort.signal,
        });
        if (stopped || abort.signal.aborted) return;
        if ([401, 403, 404].includes(result.response?.status ?? 0)) {
          onUnavailable();
          return;
        }
        if (!result.data) throw new Error("Unavailable");
        const previous = latest.current;
        const next = {
          ...result.data,
          groups: result.data.groups.map((group) => {
            const old = previous?.groups.find((item) => item.id === group.id);
            if (
              old &&
              (group.attempt < old.attempt ||
                (old.attempt === group.attempt &&
                  ((old.pr_id !== null && group.pr_id === null) ||
                    (old.status === "resolved" &&
                      group.status !== "resolved") ||
                    (["succeeded", "resolved"].includes(old.status) &&
                      !["succeeded", "resolved"].includes(group.status)))))
            )
              return old;
            return group;
          }),
        };
        latest.current = next;
        setBatch(next);
        setError(false);
        const wait = delay();
        setPaused(wait === null && next.groups.some(submissionActive));
        if (wait !== null) timer = setTimeout(() => void read(), wait);
      } catch {
        if (!stopped && !abort.signal.aborted) {
          setError(true);
          setPaused(true);
        }
      }
    }
    function visibility() {
      clearTimeout(timer);
      controller?.abort();
      if (!document.hidden && delay() !== null) void read();
    }
    void read();
    document.addEventListener("visibilitychange", visibility);
    return () => {
      stopped = true;
      clearTimeout(timer);
      controller?.abort();
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [
    accessToken,
    productId,
    record.batch_id,
    record.attempt,
    record.status,
    onUnavailable,
    refresh,
  ]);
  return { batch, error, paused, refresh: () => setRefresh((n) => n + 1) };
}
