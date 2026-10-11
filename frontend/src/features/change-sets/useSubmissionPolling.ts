import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getChangeSet, type ChangeSetResponse } from "../../api/client";
import {
  nextSubmissionPollDelay,
  submissionActive,
  submissionStatus,
} from "./submissionStatus";

export function useSubmissionPolling(
  accessToken: string,
  productId: string,
  initial: ChangeSetResponse,
  onUnavailable?: () => void,
) {
  const scope = JSON.stringify([accessToken, productId, initial.id]);
  const [memory, setMemory] = useState({
    scope,
    record: initial,
    updatedAt: new Date().toISOString(),
    error: false,
    unavailable: false,
    paused: false,
    announcement: "",
  });
  const current = useMemo(
    () =>
      memory.scope === scope
        ? memory
        : {
            scope,
            record: initial,
            updatedAt: new Date().toISOString(),
            error: false,
            unavailable: false,
            paused: false,
            announcement: "",
          },
    [memory, scope, initial],
  );
  const record = current.record;
  const ref = useRef(current);
  const generation = useRef(0);
  const controller = useRef<AbortController | undefined>(undefined);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    ref.current = current;
  }, [current]);
  useEffect(
    () => () => {
      generation.current++;
      controller.current?.abort();
    },
    [scope],
  );
  const accept = useCallback(
    (next: ChangeSetResponse) => {
      const old = ref.current;
      if (next.id !== initial.id || next.attempt < old.record.attempt) return;
      if (
        next.attempt === old.record.attempt &&
        ((!submissionActive(old.record) && submissionActive(next)) ||
          (old.record.status === "resolved" && next.status !== "resolved") ||
          (["succeeded", "resolved"].includes(old.record.status) &&
            !["succeeded", "resolved"].includes(next.status)))
      )
        return;
      const value = {
        scope,
        record: next,
        updatedAt: new Date().toISOString(),
        error: false,
        unavailable: false,
        paused: false,
        announcement:
          submissionStatus(next) !== submissionStatus(old.record)
            ? submissionStatus(next)
            : old.announcement,
      };
      ref.current = value;
      setMemory(value);
    },
    [initial.id, scope],
  );
  useEffect(() => {
    const requests = generation;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const request = async () => {
      if (stopped || document.hidden) return;
      const expected = ++generation.current;
      controller.current?.abort();
      const abort = new AbortController();
      controller.current = abort;
      try {
        const result = await getChangeSet({
          auth: accessToken,
          path: { product_id: productId, change_set_id: initial.id },
          signal: abort.signal,
        });
        if (stopped || abort.signal.aborted || expected !== generation.current)
          return;
        if ([401, 403, 404].includes(result.response?.status ?? 0)) {
          setMemory({ ...ref.current, unavailable: true, paused: true });
          onUnavailable?.();
          return;
        }
        if (!result.data) throw new Error("Unavailable");
        accept(result.data);
        schedule();
      } catch {
        if (
          !stopped &&
          !abort.signal.aborted &&
          expected === generation.current
        )
          setMemory({ ...ref.current, error: true, paused: true });
      }
    };
    function schedule() {
      clearTimeout(timer);
      const latest = ref.current.record;
      if (!submissionActive(latest)) return;
      const elapsed =
        Date.now() - Date.parse(latest.attempt_started_at ?? latest.created_at);
      const delay = nextSubmissionPollDelay(elapsed);
      if (delay === null) {
        setMemory({ ...ref.current, paused: true });
        return;
      }
      if (!document.hidden) timer = setTimeout(() => void request(), delay);
    }
    function visibility() {
      clearTimeout(timer);
      generation.current++;
      controller.current?.abort();
      const latest = ref.current.record;
      const elapsed =
        Date.now() - Date.parse(latest.attempt_started_at ?? latest.created_at);
      if (
        !document.hidden &&
        submissionActive(latest) &&
        nextSubmissionPollDelay(elapsed) !== null
      )
        void request();
    }
    if (refresh) void request();
    else schedule();
    document.addEventListener("visibilitychange", visibility);
    return () => {
      stopped = true;
      clearTimeout(timer);
      requests.current++;
      controller.current?.abort();
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [
    accessToken,
    productId,
    initial.id,
    scope,
    refresh,
    accept,
    record.attempt,
    onUnavailable,
  ]);
  return {
    ...current,
    accept,
    refresh: () => setRefresh((value) => value + 1),
  };
}
