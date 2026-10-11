import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  createSubmissionBatch,
  getSubmissionBatchByKey,
  getSubmissionReview,
  type SubmissionBatchResponse,
  type SubmissionReviewResponse,
} from "../../api/client";
import { Button } from "../../components/ui/button";
import {
  useChangeSetWorkspace,
  type SubmissionIntake,
} from "./changeSetContext";

export function SubmissionConfirmation({
  review,
}: {
  review: SubmissionReviewResponse;
}) {
  const {
    accessToken,
    productId,
    canRequest,
    selection,
    busy,
    submissionIntake,
    setSubmissionIntake,
    readSignal,
    revokeRead,
    revokeSubmission,
  } = useChangeSetWorkspace();
  const current =
    submissionIntake?.reviewId === review.id &&
    submissionIntake.attempt === review.attempt &&
    submissionIntake.digest === review.manifest_digest
      ? submissionIntake
      : undefined;
  const [inFlight, setInFlight] = useState(false);
  const [focusResult, setFocusResult] = useState(false);
  const [, setExpiryTime] = useState(Date.now);
  const heading = useRef<HTMLHeadingElement>(null);
  const lock = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  useEffect(
    () => () => {
      generation.current++;
      controller.current?.abort();
    },
    [accessToken, productId, review.id, review.attempt, review.manifest_digest],
  );
  useEffect(() => {
    if (focusResult && current?.state === "accepted") heading.current?.focus();
  }, [focusResult, current?.state]);
  useEffect(() => {
    const remaining = Date.parse(review.expires_at) - Date.now();
    if (!Number.isFinite(remaining) || remaining <= 0) return;
    const timer = setTimeout(() => setExpiryTime(Date.now()), remaining);
    return () => clearTimeout(timer);
  }, [review.expires_at]);

  function validBatch(
    batch: SubmissionBatchResponse,
    intent: SubmissionIntake,
  ) {
    const expected = new Set((review.groups ?? []).map((group) => group.id));
    return (
      batch.product_id === productId &&
      batch.review_id === review.id &&
      batch.request_key === intent.requestKey &&
      batch.groups.length === expected.size &&
      batch.groups.every((group) => expected.delete(group.id)) &&
      expected.size === 0
    );
  }

  async function submitOrRecover(recover: boolean) {
    if (lock.current || readSignal.aborted) return;
    if (!recover && (current || !canSubmit())) return;
    if (recover && !current) return;
    const intent: SubmissionIntake = current ?? {
      reviewId: review.id,
      attempt: review.attempt,
      digest: review.manifest_digest!,
      requestKey: crypto.randomUUID(),
      state: "pending",
    };
    lock.current = true;
    setInFlight(true);
    setSubmissionIntake(intent);
    const request = new AbortController();
    controller.current = request;
    const signal = AbortSignal.any([request.signal, readSignal]);
    const expected = generation.current;
    let lookedUp = false;
    let submissionDenied = false;
    const live = () => !signal.aborted && generation.current === expected;
    const accept = (batch: SubmissionBatchResponse | undefined) => {
      if (!live() || !batch || !validBatch(batch, intent)) return false;
      setSubmissionIntake({ ...intent, state: "accepted", batch });
      setFocusResult(true);
      return true;
    };
    async function verifyRead() {
      const { data, response } = await getSubmissionReview({
        auth: accessToken,
        path: { product_id: productId, review_id: review.id },
        signal,
      });
      if (!live()) return false;
      if ([401, 403, 404].includes(response?.status ?? 0)) {
        revokeRead();
        return false;
      }
      if (!data || data.id !== review.id || data.product_id !== productId)
        throw new Error("Unavailable");
      return true;
    }
    async function lookup() {
      lookedUp = true;
      const { data, response } = await getSubmissionBatchByKey({
        auth: accessToken,
        path: { product_id: productId, request_key: intent.requestKey },
        signal,
      });
      if (!live()) return;
      if ([401, 403].includes(response?.status ?? 0)) {
        revokeRead();
        return;
      }
      // A missing key is also a normal uncertain-send result. Verify the
      // review read boundary before preserving that same recovery identity.
      if (response?.status === 404 && !(await verifyRead())) return;
      if (!accept(data) && live())
        setSubmissionIntake({ ...intent, state: "uncertain" });
    }
    try {
      if (recover) await lookup();
      else {
        const { data, response } = await createSubmissionBatch({
          auth: accessToken,
          path: { product_id: productId },
          body: {
            review_id: intent.reviewId,
            expected_review_attempt: intent.attempt,
            expected_content_digest: intent.digest,
            request_key: intent.requestKey,
          },
          signal,
        });
        if (!live()) return;
        if ([401, 403, 404].includes(response?.status ?? 0)) {
          submissionDenied = true;
          revokeSubmission();
          setSubmissionIntake({ ...intent, state: "rejected" });
          await verifyRead();
          return;
        }
        if (accept(data)) return;
        if (response && [400, 409, 422].includes(response.status)) {
          setSubmissionIntake({ ...intent, state: "rejected" });
        } else await lookup();
      }
    } catch {
      if (live() && !submissionDenied) {
        if (!recover && !lookedUp) {
          try {
            await lookup();
          } catch {
            if (live()) setSubmissionIntake({ ...intent, state: "uncertain" });
          }
        } else setSubmissionIntake({ ...intent, state: "uncertain" });
      }
    } finally {
      if (live()) {
        lock.current = false;
        setInFlight(false);
      }
    }
  }
  function canSubmit() {
    return (
      canRequest &&
      !busy &&
      review.state === "ready" &&
      !!review.manifest_digest &&
      !!review.groups?.length &&
      !review.error_code &&
      !selection.some((entry) => entry.needsReview) &&
      !!review.expires_at &&
      Date.parse(review.expires_at) > Date.now()
    );
  }
  const groups =
    current?.batch?.groups ??
    (review.state === "accepted" ? (review.groups ?? []) : []);
  if (current?.state === "accepted" || review.state === "accepted")
    return (
      <section
        aria-labelledby="submission-result"
        className="grid min-w-0 gap-(--space-md)"
      >
        <h3
          id="submission-result"
          ref={heading}
          tabIndex={-1}
          className="font-semibold"
        >
          Submission queued
        </h3>
        <p>
          You can leave this page. Track each pull request through its change
          set.
        </p>
        <ul className="grid gap-(--space-sm)">
          {groups.map((group) => (
            <li key={group.id} className="wrap-anywhere">
              <Link
                className="text-primary underline"
                to={`/products/${encodeURIComponent(productId)}/change-sets/${encodeURIComponent(group.id)}`}
              >
                View change set: {group.workspace}/{group.repository_slug} →{" "}
                {group.target_branch}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    );
  if (!canRequest) return <p>Submission access is read-only</p>;
  if (current?.state === "rejected")
    return (
      <section className="grid gap-(--space-sm)" role="alert">
        <h3 className="font-semibold">Selected changes need review</h3>
        <p>
          Submission was not accepted. Return to selection and review the latest
          changes before submitting.
        </p>
      </section>
    );
  if (current && !inFlight)
    return (
      <section className="grid gap-(--space-md)">
        <h3 className="font-semibold">Checking submission outcome</h3>
        <p>
          The submission response could not be confirmed. Check the existing
          request before attempting another submission.
        </p>
        <Button
          className="w-fit"
          variant="outline"
          onClick={() => void submitOrRecover(true)}
        >
          Check status
        </Button>
      </section>
    );
  const count = review.groups?.length ?? 0;
  return (
    <section
      aria-label="Create pull request"
      className="flex min-w-0 flex-wrap items-center justify-between gap-4 rounded-lg border bg-card p-4"
    >
      <p className="min-w-0 text-sm text-muted-foreground">
        Approved changes only. No automatic merge.
      </p>
      <Button
        className="w-fit max-w-full min-h-[44px] h-auto whitespace-normal"
        disabled={inFlight || !canSubmit()}
        onClick={() => void submitOrRecover(false)}
      >
        {inFlight
          ? "Submitting changes…"
          : count === 1
            ? "Create pull request"
            : `Create ${count} pull requests`}
      </Button>
      {!inFlight && !canSubmit() && (
        <p>Review the complete current selection before submitting.</p>
      )}
    </section>
  );
}
