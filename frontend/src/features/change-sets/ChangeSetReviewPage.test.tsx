import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type {
  ChangeSetCandidate,
  ChangeSetCandidatesResponse,
  MappingDestination,
  SubmissionReviewResponse,
  SubmissionBatchResponse,
} from "../../api/client";
import { ChangeSetsPage } from "./ChangeSetsPage";
import { ChangeSetReviewPage } from "./ChangeSetReviewPage";
import { ChangeSetDetailPage } from "./ChangeSetDetailPage";
import { ChangeSetsLayout } from "./ChangeSetWorkspace";
import { useChangeSetWorkspace } from "./changeSetContext";

const api = vi.hoisted(() => ({
  getBranchWorkflow: vi.fn(),
  getChangeSetCandidates: vi.fn(),
  createSubmissionReview: vi.fn(),
  getSubmissionReview: vi.fn(),
  getSubmissionReviewFiles: vi.fn(),
  getSubmissionReviewValues: vi.fn(),
  createSubmissionBatch: vi.fn(),
  getSubmissionBatchByKey: vi.fn(),
  getChangeSet: vi.fn(),
  listChangeSets: vi.fn(),
}));
vi.mock("../../api/client", () => api);
Object.defineProperties(HTMLElement.prototype, {
  hasPointerCapture: { configurable: true, value: () => false },
  setPointerCapture: { configurable: true, value: () => undefined },
  releasePointerCapture: { configurable: true, value: () => undefined },
  scrollIntoView: { configurable: true, value: () => undefined },
});
const destination: MappingDestination = {
  mapping_id: "mapping",
  repository_id: "repo",
  workspace: "team",
  repository_slug: "mobile",
  allowed_targets: ["main", "release"],
  default_target: "main",
  chosen_target: "main",
};
function candidate(id: string): ChangeSetCandidate {
  return {
    proposal_id: id,
    version: 2,
    key: id,
    language: "it",
    state: "approved",
    value_count: 1,
    can_review: true,
    blocker: null,
    mapping_id: "mapping",
    published_excerpt: "Old",
    proposed_excerpt: "New",
  };
}
function page(
  items = [candidate("one"), candidate("two")],
): ChangeSetCandidatesResponse {
  return {
    product_id: "product",
    active_revision_id: "revision",
    can_request_review: true,
    max_selected_proposals: 100,
    destinations: [destination],
    next_after: null,
    items,
  };
}
function ready(): SubmissionReviewResponse {
  return {
    id: "review",
    product_id: "product",
    active_revision_id: "revision",
    state: "ready",
    attempt: 1,
    created_at: new Date().toISOString(),
    started_at: null,
    expires_at: new Date(Date.now() + 900000).toISOString(),
    error_code: null,
    manifest_digest: "f".repeat(64),
    destinations: [destination],
    groups: [
      {
        id: "group",
        repository_id: "repo",
        workspace: "team",
        repository_slug: "mobile",
        target_branch: "main",
        target_head: "a".repeat(40),
        source_branch: "verboflex/server-reservation",
        proposal_ids: ["one", "two"],
        value_count: 26,
        file_count: 26,
        sources: [
          {
            mapping_id: "mapping",
            repository_id: "keys-repo",
            repository_side: "keys",
            branch: "keys-main",
            commit_hash: "b".repeat(40),
          },
        ],
      },
    ],
    proposal_count: 2,
    value_count: 26,
    file_count: 26,
    next_values_after: 25,
    values: [
      {
        proposal_id: "one",
        proposal_version: 2,
        value_id: "value-first",
        key: "First value",
        language: "it",
        selector_kind: "plural",
        selector: "quantity=one",
        published_text: "Old <script>",
        proposed_text: "Nuovo",
        group_id: "group",
        file_path: "first.xml",
        character_count: 5,
        effective_maximum: 20,
      },
    ],
  };
}
function view(
  path = "/products/product/change-sets",
  principalId = "actor",
  accessToken = "token",
) {
  return (
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/products/:productId/change-sets"
          element={
            <ChangeSetsLayout
              accessToken={accessToken}
              principalId={principalId}
            />
          }
        >
          <Route
            index
            element={
              <>
                <ChangeSetsPage accessToken={accessToken} />
                <Link to="review">Return to prepared review</Link>
              </>
            }
          />
          <Route
            path="review"
            element={
              <>
                <ChangeSetReviewPage />
                <WorkspaceCache />
              </>
            }
          />
          <Route
            path="history"
            element={<ChangeSetsPage accessToken={accessToken} />}
          />
          <Route path=":changeSetId" element={<ChangeSetDetailPage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}
function WorkspaceCache() {
  const workspace = useChangeSetWorkspace();
  return (
    <output data-testid="workspace-cache">
      {JSON.stringify({
        selection: workspace.selection.length,
        destinations: workspace.destinations.length,
        review: !!workspace.review,
        intake: !!workspace.submissionIntake,
        candidates: !!workspace.candidateMemory,
      })}
    </output>
  );
}
beforeEach(() => {
  vi.resetAllMocks();
  api.getBranchWorkflow.mockResolvedValue({ data: { enabled: false } });
  api.getChangeSetCandidates.mockResolvedValue({ data: page() });
  api.createSubmissionReview.mockResolvedValue({ data: ready() });
  api.getSubmissionReview.mockResolvedValue({ data: ready() });
  api.getChangeSet.mockResolvedValue({
    response: new Response(null, { status: 404 }),
  });
  api.listChangeSets.mockResolvedValue({
    data: { items: [], next_cursor: null, page_size: 25 },
  });
  api.getSubmissionReviewFiles.mockResolvedValue({
    data: {
      items: [
        {
          index: 0,
          group_id: "group",
          path: "first.xml",
          before_sha256: "a".repeat(64),
          after_sha256: "b".repeat(64),
          changed_values: 1,
        },
      ],
      next_after: 25,
    },
  });
  api.getSubmissionReviewValues.mockResolvedValue({
    data: {
      items: [
        {
          ...ready().values[0],
          value_id: "last",
          key: "Last value",
          proposed_text: "Last proposed",
        },
      ],
      next_after: null,
    },
  });
});
afterEach(cleanup);
function denied(status: number) {
  return { response: new Response(null, { status }) };
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
async function expectRevoked() {
  expect(
    await screen.findByRole("heading", { name: "Review unavailable" }),
  ).toHaveFocus();
  expect(screen.queryByText("Nuovo")).not.toBeInTheDocument();
  expect(screen.queryByText("Old <script>")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("region", { name: "Included proposals" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", {
      name: /Create.*pull request|Check status|Load more/,
    }),
  ).not.toBeInTheDocument();
  expect(
    JSON.parse(screen.getByTestId("workspace-cache").textContent!),
  ).toEqual({
    selection: 0,
    destinations: 0,
    review: false,
    intake: false,
    candidates: false,
  });
}

it("recovers a missing detail through fresh authorized history and pending route reads", async () => {
  render(
    view("/products/product/change-sets/00000000-0000-0000-0000-000000000001"),
  );
  const user = userEvent.setup();
  await screen.findByText("Change set unavailable");
  await user.click(
    screen.getByRole("link", { name: "Back to submission history" }),
  );
  await screen.findByText("No submissions yet");
  await user.click(screen.getByRole("button", { name: "Pending changes" }));
  await user.click(
    await screen.findByRole("checkbox", { name: "Select one (it)" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Review selected changes (1)" }),
  );
  await screen.findByText("Review ready");
  expect(api.getChangeSetCandidates).toHaveBeenCalledTimes(1);
  expect(api.createSubmissionReview).toHaveBeenCalledTimes(1);
  expect(
    screen.getByRole("button", { name: "Create pull request" }),
  ).toBeEnabled();
});

it("restores review capability only after explicit return and fresh authorized candidates, ignoring old epoch successes", async () => {
  const oldValues = deferred<unknown>();
  const oldSubmission = deferred<unknown>();
  const freshCandidates = deferred<unknown>();
  const user = await reviewTwo();
  api.getSubmissionReviewValues.mockReturnValueOnce(oldValues.promise);
  api.createSubmissionBatch.mockReturnValueOnce(oldSubmission.promise);
  await user.click(
    screen.getByRole("button", { name: "Load more diff entries" }),
  );
  await user.click(screen.getByRole("button", { name: "Create pull request" }));
  const oldRequest = api.createSubmissionBatch.mock.lastCall![0];
  api.getSubmissionReview.mockResolvedValueOnce(denied(403));
  fireEvent(document, new Event("visibilitychange"));
  await expectRevoked();
  api.getChangeSetCandidates.mockReturnValueOnce(freshCandidates.promise);
  await user.click(screen.getByRole("link", { name: "Back to selection" }));
  await waitFor(() =>
    expect(api.getChangeSetCandidates).toHaveBeenCalledTimes(2),
  );
  await act(async () => {
    oldValues.resolve({
      data: {
        items: [{ ...ready().values[0], proposed_text: "OLD EPOCH SECRET" }],
        next_after: null,
      },
    });
    oldSubmission.resolve({ data: acceptedBatch(oldRequest.body.request_key) });
  });
  expect(oldRequest.signal.aborted).toBe(true);
  expect(screen.queryByText("OLD EPOCH SECRET")).not.toBeInTheDocument();
  expect(screen.queryByText("Nuovo")).not.toBeInTheDocument();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /Create.*pull request/ }),
  ).not.toBeInTheDocument();
  await act(async () =>
    freshCandidates.resolve({ data: page([candidate("fresh")]) }),
  );
  await user.click(
    await screen.findByRole("checkbox", { name: "Select fresh (it)" }),
  );
  api.createSubmissionReview.mockResolvedValueOnce({
    data: { ...ready(), id: "new-epoch-review" },
  });
  await user.click(
    screen.getByRole("button", { name: "Review selected changes (1)" }),
  );
  await screen.findByText("Review ready");
  expect(api.createSubmissionReview.mock.lastCall![0].body.proposals).toEqual([
    { proposal_id: "fresh", expected_version: 2 },
  ]);
  expect(
    screen.getByRole("button", { name: "Create pull request" }),
  ).toBeEnabled();
  expect(api.createSubmissionBatch).toHaveBeenCalledTimes(1);
});

it.each([401, 403, 404])(
  "keeps a fresh pending entry unavailable when its current read is denied %i",
  async (status) => {
    const user = await reviewTwo();
    api.getSubmissionReview.mockResolvedValueOnce(denied(403));
    fireEvent(document, new Event("visibilitychange"));
    await expectRevoked();
    api.getChangeSetCandidates.mockResolvedValueOnce(denied(status));
    await user.click(screen.getByRole("link", { name: "Back to selection" }));
    await screen.findByText("Change set unavailable");
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByText("Nuovo")).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("link", { name: "Return to prepared review" }),
    );
    expect(
      screen.queryByRole("region", { name: "Included proposals" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Create.*pull request/ }),
    ).not.toBeInTheDocument();
    expect(api.createSubmissionReview).toHaveBeenCalledTimes(1);
  },
);

it("fresh authorized read-only candidates after revocation do not regain submission capability", async () => {
  const user = await reviewTwo();
  api.getSubmissionReview.mockResolvedValueOnce(denied(403));
  fireEvent(document, new Event("visibilitychange"));
  await expectRevoked();
  api.getChangeSetCandidates.mockResolvedValueOnce({
    data: { ...page(), can_request_review: false },
  });
  await user.click(screen.getByRole("link", { name: "Back to selection" }));
  await screen.findByText("Submission access is read-only");
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /Review selected changes/ }),
  ).not.toBeInTheDocument();
});

it("does not let an old candidate response authorize a new entry before its own read finishes", async () => {
  const oldCandidates = deferred<unknown>();
  const freshCandidates = deferred<unknown>();
  const user = await reviewTwo();
  api.getChangeSetCandidates.mockReturnValueOnce(oldCandidates.promise);
  await user.click(screen.getByRole("link", { name: "Back to selection" }));
  await waitFor(() =>
    expect(api.getChangeSetCandidates).toHaveBeenCalledTimes(2),
  );
  const oldRequest = api.getChangeSetCandidates.mock.lastCall![0];
  await user.click(
    screen.getByRole("link", { name: "Return to prepared review" }),
  );
  await screen.findByText("Review ready");
  api.getSubmissionReview.mockResolvedValueOnce(denied(403));
  fireEvent(document, new Event("visibilitychange"));
  await expectRevoked();
  api.getChangeSetCandidates.mockReturnValueOnce(freshCandidates.promise);
  await user.click(screen.getByRole("link", { name: "Back to selection" }));
  await waitFor(() =>
    expect(api.getChangeSetCandidates).toHaveBeenCalledTimes(3),
  );
  await act(async () =>
    oldCandidates.resolve({ data: page([candidate("OLD SECRET")]) }),
  );
  expect(oldRequest.signal.aborted).toBe(true);
  expect(screen.queryByText("OLD SECRET")).not.toBeInTheDocument();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  await act(async () => freshCandidates.resolve(denied(403)));
  await screen.findByText("Change set unavailable");
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(api.createSubmissionReview).toHaveBeenCalledTimes(1);
});

it.each([401, 403, 404])(
  "purges selection when target review request %i is followed by denied candidate read",
  async (status) => {
    const user = await reviewTwo();
    api.createSubmissionReview.mockResolvedValueOnce(denied(status));
    api.getChangeSetCandidates.mockResolvedValueOnce(denied(403));
    await user.click(screen.getByRole("combobox", { name: /Target branch/ }));
    await user.click(screen.getByRole("option", { name: "release" }));
    await expectRevoked();
  },
);

it("suspends review creation after role-only denial while preserving authorized selection", async () => {
  const user = await reviewTwo();
  api.createSubmissionReview.mockResolvedValueOnce(denied(403));
  api.getChangeSetCandidates.mockResolvedValueOnce({
    data: { ...page(), can_request_review: false },
  });
  await user.click(screen.getByRole("combobox", { name: /Target branch/ }));
  await user.click(screen.getByRole("option", { name: "release" }));
  await screen.findByText("Submission access is read-only");
  expect(
    screen.getByRole("region", { name: "Included proposals" }),
  ).toHaveTextContent("one (it)");
  expect(
    screen.queryByRole("button", { name: "Check selected changes again" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("combobox", { name: /Target branch/ }),
  ).not.toBeInTheDocument();
});

it("aborts a request-key lookup on lost read and rejects its concurrent late receipt", async () => {
  const lookup = deferred<unknown>();
  const files = deferred<unknown>();
  api.createSubmissionBatch.mockRejectedValueOnce(new Error("lost"));
  api.getSubmissionBatchByKey.mockReturnValueOnce(lookup.promise);
  const user = await reviewTwo();
  await user.click(screen.getByRole("button", { name: "Create pull request" }));
  await waitFor(() =>
    expect(api.getSubmissionBatchByKey).toHaveBeenCalledTimes(1),
  );
  api.getSubmissionReviewFiles.mockReturnValueOnce(files.promise);
  await user.click(screen.getByRole("button", { name: "Load more files" }));
  const lookupRequest = api.getSubmissionBatchByKey.mock.lastCall![0];
  await act(async () => {
    files.resolve(denied(404));
    lookup.resolve({ data: acceptedBatch(lookupRequest.path.request_key) });
  });
  await expectRevoked();
  expect(lookupRequest.signal.aborted).toBe(true);
  expect(api.createSubmissionBatch).toHaveBeenCalledTimes(1);
});

it("keeps uncertain recovery identity on transient lookup failure and later recovers without another POST", async () => {
  api.createSubmissionBatch.mockRejectedValueOnce(new Error("lost"));
  api.getSubmissionBatchByKey.mockResolvedValueOnce(denied(503));
  const user = await reviewTwo();
  await user.click(screen.getByRole("button", { name: "Create pull request" }));
  await screen.findByRole("heading", { name: "Checking submission outcome" });
  expect(screen.getByText("Nuovo")).toBeVisible();
  const key = api.createSubmissionBatch.mock.lastCall![0].body.request_key;
  api.getSubmissionBatchByKey.mockResolvedValueOnce({
    data: acceptedBatch(key),
  });
  await user.click(screen.getByRole("button", { name: "Check status" }));
  await screen.findByRole("heading", { name: "Submission queued" });
  expect(api.getSubmissionBatchByKey.mock.lastCall![0].path.request_key).toBe(
    key,
  );
  expect(api.createSubmissionBatch).toHaveBeenCalledTimes(1);
});

it.each([401, 403, 404])(
  "purges ready review on visibility refresh denied with %i",
  async (status) => {
    await reviewTwo();
    api.getSubmissionReview.mockResolvedValueOnce(denied(status));
    fireEvent(document, new Event("visibilitychange"));
    await expectRevoked();
  },
);

it.each([401, 403, 404])(
  "purges queued review on polling denied with %i",
  async (status) => {
    api.createSubmissionReview.mockResolvedValueOnce({
      data: { ...ready(), state: "queued" },
    });
    api.getSubmissionReview.mockResolvedValueOnce(denied(status));
    render(view());
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("checkbox", { name: "Select one (it)" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Review selected changes (1)" }),
    );
    await expectRevoked();
  },
);

it.each([401, 403, 404])(
  "purges initial review files denied with %i",
  async (status) => {
    const read = deferred<ReturnType<typeof denied>>();
    api.getSubmissionReviewFiles.mockReturnValueOnce(read.promise);
    await reviewTwo();
    await act(async () => read.resolve(denied(status)));
    await expectRevoked();
  },
);

it.each([401, 403, 404])(
  "purges loaded files and text when file pagination is denied with %i",
  async (status) => {
    const user = await reviewTwo();
    await screen.findByRole("heading", { name: "first.xml" });
    api.getSubmissionReviewFiles.mockResolvedValueOnce(denied(status));
    await user.click(screen.getByRole("button", { name: "Load more files" }));
    await expectRevoked();
    expect(
      screen.queryByRole("heading", { name: "first.xml" }),
    ).not.toBeInTheDocument();
  },
);

it.each([401, 403, 404])(
  "purges loaded values when diff pagination is denied with %i",
  async (status) => {
    const user = await reviewTwo();
    api.getSubmissionReviewValues.mockResolvedValueOnce(denied(status));
    await user.click(
      screen.getByRole("button", { name: "Load more diff entries" }),
    );
    await expectRevoked();
  },
);

it.each([401, 403])(
  "purges review on request-key recovery denied with %i",
  async (status) => {
    api.createSubmissionBatch.mockRejectedValue(new Error("lost"));
    api.getSubmissionBatchByKey.mockResolvedValueOnce(denied(status));
    const user = await reviewTwo();
    await user.click(
      screen.getByRole("button", { name: "Create pull request" }),
    );
    await expectRevoked();
    expect(api.createSubmissionBatch).toHaveBeenCalledTimes(1);
  },
);

it.each([401, 403, 404])(
  "purges an ambiguous missing request key when review read is denied with %i",
  async (status) => {
    api.createSubmissionBatch.mockRejectedValue(new Error("lost"));
    api.getSubmissionBatchByKey.mockResolvedValueOnce(denied(404));
    api.getSubmissionReview.mockResolvedValueOnce(denied(status));
    const user = await reviewTwo();
    await user.click(
      screen.getByRole("button", { name: "Create pull request" }),
    );
    await expectRevoked();
    expect(api.createSubmissionBatch).toHaveBeenCalledTimes(1);
  },
);

it.each([401, 403, 404])(
  "verifies read authority after submission denial %i and clears inaccessible content",
  async (status) => {
    api.createSubmissionBatch.mockResolvedValueOnce(denied(status));
    api.getSubmissionReview.mockResolvedValueOnce(denied(403));
    const user = await reviewTwo();
    await user.click(
      screen.getByRole("button", { name: "Create pull request" }),
    );
    await expectRevoked();
  },
);

it("retains authorized read-only content after submission-role loss", async () => {
  api.createSubmissionBatch.mockResolvedValueOnce(denied(403));
  const user = await reviewTwo();
  await user.click(screen.getByRole("button", { name: "Create pull request" }));
  await screen.findByText("Submission access is read-only");
  expect(api.getSubmissionReview).toHaveBeenCalledTimes(1);
  expect(screen.getByText("Nuovo")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: /Create.*pull request/ }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("combobox", { name: /Target branch/ }),
  ).not.toBeInTheDocument();
});

it.each(["poll", "files", "values"])(
  "retains authorized review content after a transient %s error",
  async (boundary) => {
    const user = await reviewTwo();
    if (boundary === "poll") {
      api.getSubmissionReview.mockResolvedValueOnce(denied(503));
      fireEvent(document, new Event("visibilitychange"));
    } else if (boundary === "files") {
      api.getSubmissionReviewFiles.mockRejectedValueOnce(new Error("offline"));
      await user.click(screen.getByRole("button", { name: "Load more files" }));
    } else {
      api.getSubmissionReviewValues.mockResolvedValueOnce(denied(503));
      await user.click(
        screen.getByRole("button", { name: "Load more diff entries" }),
      );
    }
    await screen.findByRole("alert");
    expect(screen.getByText("Nuovo")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Create pull request" }),
    ).toBeEnabled();
  },
);

it("aborts all pending review reads and acceptance after revocation, fencing late successful responses", async () => {
  const files = deferred<unknown>();
  const values = deferred<unknown>();
  const submission = deferred<unknown>();
  const poll = deferred<unknown>();
  const user = await reviewTwo();
  api.getSubmissionReviewFiles.mockReturnValueOnce(files.promise);
  api.getSubmissionReviewValues.mockReturnValueOnce(values.promise);
  api.createSubmissionBatch.mockReturnValueOnce(submission.promise);
  api.getSubmissionReview.mockReturnValueOnce(poll.promise);
  await user.click(screen.getByRole("button", { name: "Load more files" }));
  await user.click(
    screen.getByRole("button", { name: "Load more diff entries" }),
  );
  await user.click(screen.getByRole("button", { name: "Create pull request" }));
  fireEvent(document, new Event("visibilitychange"));
  const fileRequest = api.getSubmissionReviewFiles.mock.lastCall![0];
  const valueRequest = api.getSubmissionReviewValues.mock.lastCall![0];
  const submitRequest = api.createSubmissionBatch.mock.lastCall![0];
  const pollRequest = api.getSubmissionReview.mock.lastCall![0];
  // Resolve denied and successful requests together, before an effect cleanup can fence them.
  await act(async () => {
    files.resolve(denied(403));
    values.resolve({
      data: {
        items: [{ ...ready().values[0], proposed_text: "LATE SECRET" }],
        next_after: null,
      },
    });
    submission.resolve({ data: acceptedBatch(submitRequest.body.request_key) });
    poll.resolve({ data: ready() });
  });
  await expectRevoked();
  for (const request of [fileRequest, valueRequest, submitRequest, pollRequest])
    expect(request.signal.aborted).toBe(true);
  expect(screen.queryByText("LATE SECRET")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Submission queued" }),
  ).not.toBeInTheDocument();
});

async function reviewTwo() {
  render(view());
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("checkbox", { name: "Select one (it)" }),
  );
  await user.click(screen.getByRole("checkbox", { name: "Select two (it)" }));
  await user.click(
    screen.getByRole("button", { name: "Review selected changes (2)" }),
  );
  await screen.findByText("Review ready");
  return user;
}

it("retains both complete aggregates in selection", async () => {
  render(view());
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("checkbox", { name: "Select one (it)" }),
  );
  await user.click(screen.getByRole("checkbox", { name: "Select two (it)" }));
  expect(
    screen.getByRole("button", { name: "Review selected changes (2)" }),
  ).toBeEnabled();
  expect(
    screen.getByRole("checkbox", { name: "Select loaded eligible changes" }),
  ).toBeChecked();
});
it("shows server counts/provenance and retrieves every paged file and diff entry", async () => {
  const user = await reviewTwo();
  expect(api.createSubmissionReview.mock.calls[0][0].body).toEqual({
    proposals: [
      { proposal_id: "one", expected_version: 2 },
      { proposal_id: "two", expected_version: 2 },
    ],
    targets: [],
  });
  expect(
    screen.getByRole("heading", { name: "Review change set" }),
  ).toBeVisible();
  const totals = screen.getByLabelText("Review totals");
  expect(totals).toHaveTextContent("2 changes");
  expect(totals).toHaveTextContent("26 translations");
  expect(totals).toHaveTextContent("26 files");
  expect(totals).toHaveTextContent("1 pull request");
  await user.click(screen.getByText("Technical details", { exact: true }));
  expect(screen.getByText("Imported source · keys")).toBeVisible();
  expect(screen.getByText("verboflex/server-reservation")).toBeVisible();
  expect(screen.getByText("Old <script>")).toBeVisible();
  await screen.findByRole("heading", { name: "first.xml" });
  api.getSubmissionReviewFiles.mockResolvedValueOnce({
    data: {
      items: [
        {
          index: 25,
          group_id: "group",
          path: "last.xml",
          before_sha256: "a".repeat(64),
          after_sha256: "b".repeat(64),
          changed_values: 1,
        },
      ],
      next_after: null,
    },
  });
  await user.click(screen.getByRole("button", { name: "Load more files" }));
  await screen.findByRole("heading", { name: "last.xml" });
  expect(api.getSubmissionReviewFiles.mock.lastCall?.[0].query).toEqual({
    after: 25,
  });
  await user.click(
    screen.getByRole("button", { name: "Load more diff entries" }),
  );
  await screen.findByText("Last proposed");
  expect(api.getSubmissionReviewValues.mock.lastCall?.[0].query).toEqual({
    after: 25,
  });
  expect(
    screen.queryByRole("button", { name: "Load more diff entries" }),
  ).not.toBeInTheDocument();
  expect(api.createSubmissionBatch).not.toHaveBeenCalled();
});
it("target change immediately invalidates ready and requests only that mapping target", async () => {
  const user = await reviewTwo();
  let finish: ((value: { data: SubmissionReviewResponse }) => void) | undefined;
  api.createSubmissionReview.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  await user.click(
    screen.getByRole("combobox", { name: /Target branch for team\/mobile/ }),
  );
  await user.click(screen.getByRole("option", { name: "release" }));
  expect(screen.queryByText("Review ready")).not.toBeInTheDocument();
  expect(screen.getByText("Checking selected changes…")).toBeVisible();
  expect(api.createSubmissionReview.mock.lastCall?.[0].body.targets).toEqual([
    { mapping_id: "mapping", target_branch: "release" },
  ]);
  finish?.({
    data: {
      ...ready(),
      id: "review-new",
      groups: [{ ...ready().groups![0], target_branch: "release" }],
    },
  });
  await screen.findByText("Review ready");
  await waitFor(() =>
    expect(
      screen.getByRole("combobox", { name: /Target branch for team\/mobile/ }),
    ).toHaveFocus(),
  );
});
it("single permitted destination is read-only and multiple groups use server plural counts", async () => {
  const response = ready();
  response.destinations = [{ ...destination, allowed_targets: ["main"] }];
  response.groups = [
    ...response.groups!,
    {
      ...response.groups![0],
      id: "group2",
      repository_id: "repo2",
      repository_slug: "desktop",
    },
  ];
  api.createSubmissionReview.mockResolvedValue({ data: response });
  await reviewTwo();
  expect(
    screen.getByRole("heading", { name: "Review change sets" }),
  ).toBeVisible();
  expect(screen.getByText("2 pull requests")).toBeVisible();
  expect(
    within(
      screen.getByRole("region", { name: "Permitted destinations" }),
    ).getByText("main", { exact: true }),
  ).toBeVisible();
  expect(
    screen.queryByRole("combobox", { name: /Target branch/ }),
  ).not.toBeInTheDocument();
});
it("direct review reload has no inferred selection and offers return action", () => {
  render(view("/products/product/change-sets/review"));
  expect(
    screen.getByRole("heading", { name: "No changes selected" }),
  ).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Back to selection" }),
  ).toHaveAttribute("href", "/products/product/change-sets");
  expect(api.createSubmissionReview).not.toHaveBeenCalled();
});
it("preserves selection outside filtered rows and sends Approved/default query filters", async () => {
  render(view());
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("checkbox", { name: "Select one (it)" }),
  );
  expect(api.getChangeSetCandidates.mock.calls[0][0].query.state).toBe(
    "approved",
  );
  api.getChangeSetCandidates.mockResolvedValue({
    data: page([candidate("two")]),
  });
  await user.type(
    screen.getByRole("textbox", { name: "Search changes" }),
    "two",
  );
  await user.type(screen.getByRole("textbox", { name: "Language" }), "it");
  await user.click(screen.getByRole("button", { name: "Apply filters" }));
  await screen.findByText("1 selected · 1 outside current filters");
  expect(api.getChangeSetCandidates.mock.lastCall?.[0].query).toMatchObject({
    state: "approved",
    query: "two",
    language: "it",
  });
  expect(
    screen.getByRole("button", { name: "Review selected changes (1)" }),
  ).toBeEnabled();
});
it("keeps stale or blocked selected versions until explicitly removed", async () => {
  render(view());
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("checkbox", { name: "Select one (it)" }),
  );
  api.getChangeSetCandidates.mockResolvedValue({
    data: page([
      {
        ...candidate("one"),
        version: 3,
        can_review: false,
        blocker: "stale_basis",
      },
    ]),
  });
  await user.click(screen.getByRole("button", { name: "Apply filters" }));
  await screen.findByText(
    /Needs review: remove and select the current version/,
  );
  expect(
    screen.getByRole("button", { name: "Review selected changes (1)" }),
  ).toBeDisabled();
  expect(
    within(screen.getByRole("region", { name: "Selected changes" })).getByText(
      /version 2/,
    ),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Remove one (it)" }));
  expect(
    screen.getByRole("button", { name: "Review selected changes (0)" }),
  ).toBeDisabled();
});
it("select-loaded refuses an over-limit set without silently dropping rows", async () => {
  api.getChangeSetCandidates.mockResolvedValue({
    data: { ...page(), max_selected_proposals: 1 },
  });
  render(view());
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("checkbox", {
      name: "Select loaded eligible changes",
    }),
  );
  expect(
    screen.getByText(/Select at most 1 proposals\. Remove selected changes/),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Review selected changes (0)" }),
  ).toBeDisabled();
});
it("read-only roles see candidates without selection or review actions", async () => {
  api.getChangeSetCandidates.mockResolvedValue({
    data: { ...page(), can_request_review: false },
  });
  render(view());
  await screen.findByText("Submission access is read-only");
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /Review selected changes/ }),
  ).not.toBeInTheDocument();
});
it("principal change discards the prior in-memory selection", async () => {
  const mounted = render(view());
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("checkbox", { name: "Select one (it)" }),
  );
  mounted.rerender(view("/products/product/change-sets", "different-actor"));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Review selected changes (0)" }),
    ).toBeDisabled(),
  );
});

it("token renewal rejects a late create response without leaving the review busy", async () => {
  let finish: ((value: { data: SubmissionReviewResponse }) => void) | undefined;
  api.createSubmissionReview.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const mounted = render(view());
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("checkbox", { name: "Select one (it)" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Review selected changes (1)" }),
  );
  await screen.findByText("Checking selected changes…");
  mounted.rerender(
    view("/products/product/change-sets", "actor", "renewed-token"),
  );
  finish?.({ data: ready() });
  expect(
    await screen.findByRole("heading", { name: "No changes selected" }),
  ).toBeInTheDocument();
  expect(screen.queryByText("Review ready")).not.toBeInTheDocument();
});

it("token renewal clears protected selection and previous ready authority", async () => {
  const mounted = render(view());
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("checkbox", { name: "Select one (it)" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Review selected changes (1)" }),
  );
  await screen.findByText("Review ready");
  mounted.rerender(
    view("/products/product/change-sets", "actor", "renewed-token"),
  );
  expect(
    await screen.findByRole("heading", { name: "No changes selected" }),
  ).toBeInTheDocument();
  expect(screen.queryByText("Review ready")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("region", { name: "Included proposals" }),
  ).not.toBeInTheDocument();
});

it("creates a batch only after explicit confirmation of the exact review", async () => {
  api.createSubmissionBatch.mockImplementation(
    () => new Promise(() => undefined),
  );
  render(view());
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("checkbox", { name: "Select one (it)" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Review selected changes (1)" }),
  );
  await screen.findByText("Review ready");
  expect(api.createSubmissionBatch).not.toHaveBeenCalled();
  const button = screen.getByRole("button", {
    name: "Create pull request",
  });
  await user.dblClick(button);
  expect(api.createSubmissionBatch).toHaveBeenCalledTimes(1);
  expect(api.createSubmissionBatch).toHaveBeenCalledWith(
    expect.objectContaining({
      body: {
        review_id: "review",
        expected_review_attempt: 1,
        expected_content_digest: "f".repeat(64),
        request_key: expect.stringMatching(
          /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/,
        ),
      },
    }),
  );
  expect(
    screen.getByRole("button", { name: "Submitting changes…" }),
  ).toBeDisabled();
});

function acceptedBatch(requestKey: string): SubmissionBatchResponse {
  return {
    id: "batch",
    product_id: "product",
    review_id: "review",
    request_key: requestKey,
    created_at: new Date().toISOString(),
    groups: [
      {
        id: "group",
        batch_id: "batch",
        status: "queued",
        stage: "branch",
        attempt: 1,
        repository_id: "repo",
        workspace: "team",
        repository_slug: "mobile",
        target_branch: "main",
        target_head: "a".repeat(40),
        source_branch: "verboflex/server-reservation",
        proposal_count: 2,
        value_count: 26,
        file_count: 26,
        error_code: null,
        can_retry: false,
        can_reconcile: false,
        pr_id: null,
        pr_url: null,
        pr_state: null,
        created_at: new Date().toISOString(),
      },
    ],
  };
}

it("shows queued durable links and focuses acceptance without claiming a PR opened", async () => {
  api.createSubmissionBatch.mockImplementation(({ body }) =>
    Promise.resolve({
      data: acceptedBatch(body.request_key),
      response: new Response(null, { status: 202 }),
    }),
  );
  const user = await reviewTwo();
  await user.click(screen.getByRole("button", { name: "Create pull request" }));
  const result = await screen.findByRole("heading", {
    name: "Submission queued",
  });
  expect(result).toHaveFocus();
  expect(
    screen.getByRole("link", { name: "View change set: team/mobile → main" }),
  ).toHaveAttribute("href", "/products/product/change-sets/group");
  expect(
    screen.queryByRole("button", { name: /Create.*pull request/ }),
  ).not.toBeInTheDocument();
  expect(screen.queryByText("Pull request opened")).not.toBeInTheDocument();
  expect(api.createSubmissionBatch).toHaveBeenCalledTimes(1);
});

it("recovers a lost acceptance response by the original request key without another POST", async () => {
  api.createSubmissionBatch.mockRejectedValue(new Error("connection lost"));
  api.getSubmissionBatchByKey.mockImplementation(({ path }) =>
    Promise.resolve({ data: acceptedBatch(path.request_key) }),
  );
  const user = await reviewTwo();
  await user.click(screen.getByRole("button", { name: "Create pull request" }));
  await screen.findByRole("heading", { name: "Submission queued" });
  expect(api.getSubmissionBatchByKey.mock.lastCall?.[0].path.request_key).toBe(
    api.createSubmissionBatch.mock.lastCall?.[0].body.request_key,
  );
  expect(api.createSubmissionBatch).toHaveBeenCalledTimes(1);
});

it("retains an uncertain request key across route remounts and checks only that request", async () => {
  api.createSubmissionBatch.mockResolvedValue({
    response: new Response(null, { status: 503 }),
  });
  api.getSubmissionBatchByKey.mockResolvedValue({
    response: new Response(null, { status: 404 }),
  });
  const user = await reviewTwo();
  await user.click(screen.getByRole("button", { name: "Create pull request" }));
  await screen.findByRole("heading", { name: "Checking submission outcome" });
  const key = api.createSubmissionBatch.mock.lastCall?.[0].body.request_key;
  await user.click(screen.getByRole("link", { name: "Back to selection" }));
  await user.click(
    screen.getByRole("link", { name: "Return to prepared review" }),
  );
  expect(
    screen.queryByRole("button", { name: /Create.*pull request/ }),
  ).not.toBeInTheDocument();
  api.getSubmissionBatchByKey.mockImplementation(({ path }) =>
    Promise.resolve({ data: acceptedBatch(path.request_key) }),
  );
  await user.click(screen.getByRole("button", { name: "Check status" }));
  await screen.findByRole("heading", { name: "Submission queued" });
  expect(api.getSubmissionBatchByKey.mock.lastCall?.[0].path.request_key).toBe(
    key,
  );
  expect(api.createSubmissionBatch).toHaveBeenCalledTimes(1);
});

it("keeps an intake conflict blocked until the user prepares a fresh review", async () => {
  api.createSubmissionBatch.mockResolvedValue({
    response: new Response(null, { status: 409 }),
  });
  const user = await reviewTwo();
  await user.click(screen.getByRole("button", { name: "Create pull request" }));
  await screen.findByRole("heading", { name: "Selected changes need review" });
  expect(
    screen.queryByRole("button", { name: /Create.*pull request/ }),
  ).not.toBeInTheDocument();
  expect(api.getSubmissionBatchByKey).not.toHaveBeenCalled();
});

it("a token transition discards a late intake result and old submit readiness", async () => {
  let finish: ((value: { data: SubmissionBatchResponse }) => void) | undefined;
  api.createSubmissionBatch.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const mounted = render(view());
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("checkbox", { name: "Select one (it)" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Review selected changes (1)" }),
  );
  await user.click(
    await screen.findByRole("button", {
      name: "Create pull request",
    }),
  );
  const key = api.createSubmissionBatch.mock.lastCall?.[0].body.request_key;
  mounted.rerender(
    view("/products/product/change-sets", "actor", "renewed-token"),
  );
  finish?.({ data: acceptedBatch(key) });
  await screen.findByRole("heading", { name: "No changes selected" });
  expect(
    screen.queryByRole("heading", { name: "Submission queued" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /Create.*pull request/ }),
  ).not.toBeInTheDocument();
});

it("uses plural explicit copy for two groups and never submits on target selection", async () => {
  api.createSubmissionReview.mockResolvedValue({
    data: {
      ...ready(),
      groups: [
        ready().groups![0],
        { ...ready().groups![0], id: "group-two", target_branch: "release" },
      ],
    },
  });
  await reviewTwo();
  expect(
    screen.getByRole("button", { name: "Create 2 pull requests" }),
  ).toBeEnabled();
  expect(
    screen.getByText("Approved changes only. No automatic merge."),
  ).toBeVisible();
  expect(api.createSubmissionBatch).not.toHaveBeenCalled();
});

it("blocks final action without a complete current review digest", async () => {
  api.createSubmissionReview.mockResolvedValue({
    data: { ...ready(), manifest_digest: null },
  });
  await reviewTwo();
  expect(
    screen.getByRole("button", { name: "Create pull request" }),
  ).toBeDisabled();
  expect(api.createSubmissionBatch).not.toHaveBeenCalled();
});

it("changing the target abandons old readiness and ignores its late intake response", async () => {
  let finish: ((value: { data: SubmissionBatchResponse }) => void) | undefined;
  api.createSubmissionBatch.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  api.createSubmissionBatch.mockImplementation(
    () => new Promise(() => undefined),
  );
  const user = await reviewTwo();
  await user.click(screen.getByRole("button", { name: "Create pull request" }));
  const firstKey =
    api.createSubmissionBatch.mock.lastCall?.[0].body.request_key;
  api.createSubmissionReview.mockResolvedValue({
    data: {
      ...ready(),
      id: "review-new",
      destinations: [{ ...destination, chosen_target: "release" }],
    },
  });
  await user.click(
    screen.getByRole("combobox", {
      name: "Target branch for team/mobile (mapping)",
    }),
  );
  await user.click(screen.getByRole("option", { name: "release" }));
  await screen.findByRole("button", {
    name: "Create pull request",
  });
  finish?.({ data: acceptedBatch(firstKey) });
  expect(
    screen.queryByRole("heading", { name: "Submission queued" }),
  ).not.toBeInTheDocument();
  expect(api.createSubmissionBatch).toHaveBeenCalledTimes(1);
  await user.click(screen.getByRole("button", { name: "Create pull request" }));
  expect(api.createSubmissionBatch).toHaveBeenCalledTimes(2);
  expect(
    api.createSubmissionBatch.mock.lastCall?.[0].body.request_key,
  ).not.toBe(firstKey);
  expect(api.createSubmissionBatch.mock.lastCall?.[0].body.review_id).toBe(
    "review-new",
  );
});

it("accepted review state only displays durable links and cannot submit again", async () => {
  api.createSubmissionReview.mockResolvedValue({
    data: { ...ready(), state: "accepted", batch_id: "batch" },
  });
  render(view());
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("checkbox", { name: "Select one (it)" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Review selected changes (1)" }),
  );
  await screen.findByRole("heading", { name: "Submission queued" });
  expect(screen.queryByText("Review not prepared")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /Create.*pull request/ }),
  ).not.toBeInTheDocument();
  expect(api.createSubmissionBatch).not.toHaveBeenCalled();
});
