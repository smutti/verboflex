import { useEffect, useState } from "react";
import {
  getSubmissionReview,
  type SubmissionReviewResponse,
} from "../../api/client";

export function useReviewPolling(
  accessToken: string,
  productId: string,
  review: SubmissionReviewResponse | undefined,
  update: (value: SubmissionReviewResponse) => void,
  onUnavailable: () => void,
  readSignal: AbortSignal,
) {
  const [refresh, setRefresh] = useState(0);
  const [feedback, setFeedback] = useState<{
    id: string;
    error: boolean;
    paused: boolean;
  }>();
  const id = review?.id;
  const attempt = review?.attempt;
  const createdAt = review?.created_at;
  const state = review?.state;
  useEffect(() => {
    if (!id || !createdAt) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    async function read() {
      if (stopped || document.hidden || readSignal.aborted) return;
      controller?.abort();
      const request = new AbortController();
      controller = request;
      const signal = AbortSignal.any([request.signal, readSignal]);
      try {
        const { data, response } = await getSubmissionReview({
          auth: accessToken,
          path: { product_id: productId, review_id: id! },
          signal,
        });
        if (stopped || signal.aborted) return;
        if ([401, 403, 404].includes(response?.status ?? 0)) {
          onUnavailable();
          return;
        }
        if (!data || data.id !== id || data.attempt !== attempt)
          throw new Error("unavailable");
        update(data);
        const elapsed = Date.now() - Date.parse(createdAt!);
        const pending = data.state === "queued" || data.state === "running";
        const paused =
          pending && (!Number.isFinite(elapsed) || elapsed >= 90_000);
        setFeedback({ id: data.id, error: false, paused });
        if (pending && !paused)
          timer = setTimeout(
            () => void read(),
            Math.min(elapsed < 30_000 ? 2000 : 5000, 90_000 - elapsed),
          );
      } catch {
        if (!stopped && !signal.aborted)
          setFeedback({ id: id!, error: true, paused: true });
      }
    }
    function visibility() {
      clearTimeout(timer);
      controller?.abort();
      if (!document.hidden) void read();
    }
    if (state === "queued" || state === "running" || refresh) void read();
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
    id,
    attempt,
    createdAt,
    state,
    update,
    refresh,
    onUnavailable,
    readSignal,
  ]);
  return {
    paused: !!feedback && feedback.id === id && feedback.paused,
    error: !!feedback && feedback.id === id && feedback.error,
    refresh: () => setRefresh((current) => current + 1),
  };
}
