import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Outlet, useLocation, useParams } from "react-router-dom";
import {
  createSubmissionReview,
  getChangeSetCandidates,
  type ChangeSetCandidate,
  type ChangeSetCandidatesResponse,
  type MappingDestination,
  type MappingTarget,
  type SubmissionReviewResponse,
} from "../../api/client";
import {
  ChangeSetContext,
  type SelectionEntry,
  type SubmissionIntake,
} from "./changeSetContext";
export function ChangeSetsLayout({
  accessToken,
  principalId,
}: {
  accessToken: string;
  principalId: string;
}) {
  const productId = useParams<"productId">().productId ?? "";
  return (
    <ChangeSetWorkspace
      key={`${principalId}:${accessToken}:${productId}`}
      principalId={principalId}
      accessToken={accessToken}
      productId={productId}
    >
      <Outlet />
    </ChangeSetWorkspace>
  );
}
type WorkspaceProps = {
  accessToken: string;
  principalId?: string;
  productId: string;
  children: ReactNode;
};

export function ChangeSetWorkspace(props: WorkspaceProps) {
  const entry = useLocation().key;
  const [epoch, setEpoch] = useState<{ id: number; revokedEntry?: string }>({
    id: 0,
  });
  if (epoch.revokedEntry !== undefined && epoch.revokedEntry !== entry) {
    // Explicit navigation starts empty. Only the new entry's authorized
    // candidates read can grant capabilities; old controllers stay aborted.
    setEpoch({ id: epoch.id + 1 });
  }
  const onReadRevoked = useCallback(() => {
    setEpoch((current) => ({ ...current, revokedEntry: entry }));
  }, [entry]);
  return (
    <WorkspaceState key={epoch.id} {...props} onReadRevoked={onReadRevoked} />
  );
}

function WorkspaceState({
  accessToken,
  principalId = "",
  productId,
  children,
  onReadRevoked,
}: WorkspaceProps & { onReadRevoked: () => void }) {
  const [candidateMemory, setCandidateMemory] =
    useState<import("./changeSetContext").CandidateMemory>();
  const [returnFocus, setReturnFocus] = useState<string>();
  const [historyMemory, setHistoryMemory] =
    useState<import("./changeSetContext").HistoryMemory>();
  const [selection, setSelection] = useState<SelectionEntry[]>([]);
  const [destinations, setDestinations] = useState<MappingDestination[]>([]);
  const [targets, setTargets] = useState<MappingTarget[]>([]);
  const [readController] = useState(() => new AbortController());
  const [readUnavailable, setReadUnavailable] = useState(false);
  const [submissionIntake, setSubmissionIntakeState] =
    useState<SubmissionIntake>();
  const setSubmissionIntake = useCallback(
    (value: SubmissionIntake) => {
      if (!readController.signal.aborted) setSubmissionIntakeState(value);
    },
    [readController],
  );
  const [canRequest, setCanRequest] = useState(false);
  const [limit, setLimit] = useState(100);
  const [reviewState, setReviewState] = useState<{
    token: string;
    review?: SubmissionReviewResponse;
  }>({ token: accessToken });
  const review =
    reviewState.token === accessToken ? reviewState.review : undefined;
  const setReview = useCallback(
    (value: SubmissionReviewResponse | undefined) =>
      setReviewState({ token: accessToken, review: value }),
    [accessToken],
  );
  const [requestState, setRequestState] = useState({
    token: accessToken,
    busy: false,
  });
  const busy = requestState.token === accessToken && requestState.busy;
  const setBusy = useCallback(
    (value: boolean) => setRequestState({ token: accessToken, busy: value }),
    [accessToken],
  );
  const [error, setError] = useState<string>();
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const revision = useRef<string | undefined>(undefined);
  const selectedRef = useRef(selection);
  useEffect(() => {
    selectedRef.current = selection;
  }, [selection]);
  const invalidate = useCallback(() => {
    generation.current++;
    controller.current?.abort();
    setReview(undefined);
    setBusy(false);
    setError(undefined);
  }, [setBusy, setReview]);
  useEffect(
    () => () => {
      generation.current++;
      controller.current?.abort();
    },
    [accessToken],
  );
  const observe = useCallback(
    (page: ChangeSetCandidatesResponse) => {
      if (readController.signal.aborted) return;
      setCanRequest(page.can_request_review);
      setLimit(Math.min(100, page.max_selected_proposals ?? 100));
      setDestinations((current) => [
        ...current.filter(
          (old) =>
            !(page.destinations ?? []).some(
              (next) => next.mapping_id === old.mapping_id,
            ),
        ),
        ...(page.destinations ?? []),
      ]);
      const changed =
        revision.current !== undefined &&
        revision.current !== page.active_revision_id;
      revision.current = page.active_revision_id;
      const stale = selectedRef.current.some((entry) =>
        page.items.some(
          (next) =>
            next.proposal_id === entry.candidate.proposal_id &&
            (!next.can_review || next.version !== entry.candidate.version),
        ),
      );
      if (changed || stale || !page.can_request_review) invalidate();
      setSelection((current) =>
        current.map((entry) => {
          const next = page.items.find(
            (item) => item.proposal_id === entry.candidate.proposal_id,
          );
          return {
            ...entry,
            needsReview:
              entry.needsReview ||
              changed ||
              !page.can_request_review ||
              (!!next &&
                (!next.can_review || next.version !== entry.candidate.version)),
          };
        }),
      );
    },
    [invalidate, readController],
  );
  function select(rows: ChangeSetCandidate[]) {
    if (readController.signal.aborted) return;
    const additions = rows.filter(
      (row) =>
        row.can_review &&
        !selection.some(
          (entry) => entry.candidate.proposal_id === row.proposal_id,
        ),
    );
    if (selection.length + additions.length > limit) {
      setError(
        `Select at most ${limit} proposals. Remove selected changes before adding this set.`,
      );
      return;
    }
    invalidate();
    setSelection((current) => [
      ...current,
      ...additions.map((candidate) => ({ candidate, needsReview: false })),
    ]);
  }
  function remove(id: string) {
    invalidate();
    setSelection((current) =>
      current.filter((entry) => entry.candidate.proposal_id !== id),
    );
  }
  async function requestReview(chosen = targets) {
    if (
      readController.signal.aborted ||
      !canRequest ||
      !selection.length ||
      selection.some((entry) => entry.needsReview)
    )
      return;
    invalidate();
    const expected = generation.current;
    const request = new AbortController();
    controller.current = request;
    setBusy(true);
    setTargets(chosen);
    try {
      const {
        data,
        error: responseError,
        response,
      } = await createSubmissionReview({
        auth: accessToken,
        path: { product_id: productId },
        body: {
          proposals: selection.map((entry) => ({
            proposal_id: entry.candidate.proposal_id,
            expected_version: entry.candidate.version,
          })),
          targets: chosen.filter((target) =>
            selection.some(
              (entry) => entry.candidate.mapping_id === target.mapping_id,
            ),
          ),
        },
        signal: request.signal,
      });
      if (request.signal.aborted || generation.current !== expected) return;
      if ([401, 403, 404].includes(response?.status ?? 0)) {
        revokeSubmission();
        // Preparing a review requires more authority than reading candidates.
        // Check the read boundary before retaining the previous selection.
        const read = await getChangeSetCandidates({
          auth: accessToken,
          path: { product_id: productId },
          query: { state: "approved" },
          signal: request.signal,
        });
        if (request.signal.aborted || generation.current !== expected) return;
        if ([401, 403, 404].includes(read.response?.status ?? 0)) {
          revokeRead();
          return;
        }
        if (!read.data || read.data.product_id !== productId)
          throw new Error("Unavailable");
        setError("Submission access is read-only");
        return;
      }
      if (!data) {
        setError(
          typeof responseError?.detail === "string"
            ? responseError.detail
            : "Review could not be prepared. Refresh and review the selected changes.",
        );
        return;
      }
      setReview(data);
    } catch {
      if (!request.signal.aborted && generation.current === expected)
        setError(
          "Review could not be prepared. Refresh and review the selected changes.",
        );
    } finally {
      if (!request.signal.aborted && generation.current === expected)
        setBusy(false);
    }
  }
  const updateReview = useCallback(
    (next: SubmissionReviewResponse) =>
      setReviewState((current) =>
        !readController.signal.aborted &&
        current.token === accessToken &&
        current.review?.id === next.id &&
        (current.review.state === "queued" ||
          current.review.state === "running" ||
          (next.state !== "queued" && next.state !== "running"))
          ? { token: accessToken, review: next }
          : current,
      ),
    [accessToken, readController],
  );
  const revokeSubmission = useCallback(() => setCanRequest(false), []);
  const revokeRead = useCallback(() => {
    // Abort all review consumers synchronously, before React unmounts them.
    readController.abort();
    onReadRevoked();
    setReadUnavailable(true);
    invalidate();
    selectedRef.current = [];
    revision.current = undefined;
    setSelection([]);
    setDestinations([]);
    setTargets([]);
    setCandidateMemory(undefined);
    setHistoryMemory(undefined);
    setReturnFocus(undefined);
    setSubmissionIntakeState(undefined);
    setCanRequest(false);
  }, [invalidate, readController, onReadRevoked]);
  return (
    <ChangeSetContext.Provider
      value={{
        principalId,
        accessToken,
        productId,
        selection,
        destinations,
        targets,
        canRequest,
        limit,
        review,
        busy,
        error,
        observe,
        select,
        remove,
        requestReview,
        setReview: updateReview,
        submissionIntake,
        setSubmissionIntake,
        candidateMemory,
        setCandidateMemory,
        returnFocus,
        setReturnFocus,
        historyMemory,
        setHistoryMemory,
        readSignal: readController.signal,
        readUnavailable,
        revokeRead,
        revokeSubmission,
      }}
    >
      <div className="min-w-0 [&_button:not([role=checkbox])]:min-h-[44px] [&_button]:whitespace-normal">
        {children}
      </div>
    </ChangeSetContext.Provider>
  );
}
