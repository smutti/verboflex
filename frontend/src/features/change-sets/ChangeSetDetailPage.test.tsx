import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ChangeSetDetailPage } from "./ChangeSetDetailPage";
import { ChangeSetsLayout } from "./ChangeSetWorkspace";
import { ChangeSetsPage } from "./ChangeSetsPage";
import { submissionFixture } from "./submissionTestFixture";
const api = vi.hoisted(() => ({
  getChangeSet: vi.fn(),
  getSubmissionBatch: vi.fn(),
  getChangeSetItems: vi.fn(),
  getChangeSetFiles: vi.fn(),
  getChangeSetValues: vi.fn(),
  getChangeSetActivity: vi.fn(),
  retryChangeSet: vi.fn(),
  reconcileChangeSet: vi.fn(),
  finalizeChangeSet: vi.fn(),
  listChangeSets: vi.fn(),
  createSubmissionReview: vi.fn(),
  getChangeSetCandidates: vi.fn(),
}));
vi.mock("../../api/client", () => api);
const ok = (data: unknown) => ({ data, response: new Response() });
const empty = () => ok({ items: [], next_cursor: null, page_size: 25 });
function view(
  path = "/products/product/change-sets/group",
  token = "token",
  principal = "actor",
) {
  return (
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/products/:productId/change-sets"
          element={
            <ChangeSetsLayout accessToken={token} principalId={principal} />
          }
        >
          <Route index element={<ChangeSetsPage accessToken={token} />} />
          <Route
            path="history"
            element={<ChangeSetsPage accessToken={token} />}
          />
          <Route path=":changeSetId" element={<ChangeSetDetailPage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}
beforeEach(() => {
  vi.resetAllMocks();
  api.getChangeSet.mockResolvedValue(
    ok(submissionFixture({ status: "failed", can_retry: true })),
  );
  api.getSubmissionBatch.mockResolvedValue(ok({ groups: [] }));
  for (const call of [
    api.getChangeSetItems,
    api.getChangeSetFiles,
    api.getChangeSetValues,
    api.getChangeSetActivity,
    api.listChangeSets,
  ])
    call.mockResolvedValue(empty());
});
afterEach(cleanup);
it("shows the original submitting actor separately from the current reader", async () => {
  api.getChangeSet.mockResolvedValue(
    ok({
      ...submissionFixture({ status: "resolved" }),
      actor: { id: "original", display_name: "Original reviewer" },
    }),
  );
  render(view());
  expect(
    await screen.findByText("Submitted by Original reviewer"),
  ).toBeInTheDocument();
});
it("refreshes an active sibling after the focused group has already failed", async () => {
  const failed = submissionFixture({ status: "failed", can_retry: true });
  const running = submissionFixture({ id: "sibling", status: "running" });
  api.getSubmissionBatch
    .mockResolvedValueOnce(ok({ groups: [failed, running] }))
    .mockResolvedValue(
      ok({
        groups: [
          failed,
          {
            ...running,
            status: "succeeded",
            pr_id: 42,
            pr_url: "https://bitbucket.org/acme/mobile/pull-requests/42",
          },
        ],
      }),
    );
  render(view());
  await screen.findByText("0 of 2 pull requests opened");
  expect(
    await screen.findByRole(
      "link",
      { name: /Open pull request #42/ },
      { timeout: 3500 },
    ),
  ).toBeInTheDocument();
  expect(api.retryChangeSet).not.toHaveBeenCalled();
});
it("reloads frozen detail, retains successful sibling, and retries only failed group once", async () => {
  const old = submissionFixture({
    status: "failed",
    can_retry: true,
    stage: "pull_request",
    commit_hash: "b".repeat(40),
  });
  api.getChangeSet.mockResolvedValue(ok(old));
  api.getSubmissionBatch.mockResolvedValue(
    ok({
      groups: [
        old,
        submissionFixture({
          id: "success",
          status: "succeeded",
          pr_id: 41,
          pr_url: "https://bitbucket.org/acme/mobile/pull-requests/41",
        }),
      ],
    }),
  );
  let finish!: (value: ReturnType<typeof ok>) => void;
  api.retryChangeSet.mockImplementation(
    () =>
      new Promise((r) => {
        finish = r;
      }),
  );
  render(view());
  const user = userEvent.setup();
  expect(
    await screen.findByText("1 of 2 pull requests opened"),
  ).toBeInTheDocument();
  expect(screen.getByText(/Submitted commit:/)).toHaveTextContent(
    "b".repeat(40),
  );
  expect(
    screen.getByRole("link", { name: /Open pull request/ }),
  ).toHaveAttribute("rel", "noopener noreferrer");
  const button = screen.getByRole("button", { name: "Retry submission" });
  await user.dblClick(button);
  expect(api.retryChangeSet).toHaveBeenCalledTimes(1);
  expect(api.retryChangeSet.mock.calls[0][0]).toMatchObject({
    path: { product_id: "product", change_set_id: "group" },
    body: { expected_attempt: 1 },
  });
  finish(ok({ ...old, attempt: 2, status: "queued", can_retry: false }));
  await screen.findByRole("heading", { name: "Queued" });
  expect(
    screen.queryByRole("button", { name: "Retry submission" }),
  ).not.toBeInTheDocument();
});
it("unknown outcomes expose Check status only and never POST a retry", async () => {
  const group = submissionFixture({
    status: "reconciling",
    can_reconcile: true,
  });
  api.getChangeSet.mockResolvedValue(ok(group));
  api.reconcileChangeSet.mockResolvedValue(
    ok({ ...group, can_reconcile: false, attempt: 2 }),
  );
  render(view());
  await userEvent.click(
    await screen.findByRole("button", { name: "Check status" }),
  );
  expect(api.reconcileChangeSet).toHaveBeenCalledTimes(1);
  expect(api.retryChangeSet).not.toHaveBeenCalled();
  expect(
    screen.queryByRole("button", { name: "Retry submission" }),
  ).not.toBeInTheDocument();
});
it("renders malicious URLs as text and keeps frozen values separate from newer proposals", async () => {
  api.getChangeSet.mockResolvedValue(
    ok(
      submissionFixture({
        status: "succeeded",
        pr_id: 41,
        pr_url: "https://evil.test/41",
      }),
    ),
  );
  api.getChangeSetItems.mockResolvedValue(
    ok({
      items: [
        {
          proposal_id: "one",
          proposal_version: 2,
          key: "hello",
          language: "ar",
          value_count: 1,
          current_version: 3,
          newer_version_available: true,
        },
      ],
      next_cursor: null,
    }),
  );
  api.getChangeSetValues.mockResolvedValue(
    ok({
      items: [
        {
          proposal_id: "one",
          proposal_version: 2,
          value_id: "value",
          key: "hello",
          language: "ar",
          selector_kind: "scalar",
          selector: "default",
          published_text: "Published",
          proposed_text: "<script>مرحبا</script>\nsecond line",
          file_path: "res/ar.xml",
          basis_revision_number: 1,
          basis_digest: "f".repeat(64),
          source: null,
        },
      ],
      next_cursor: null,
    }),
  );
  render(view());
  expect(
    await screen.findByText(/Newer proposal available/),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: /Open pull request/ }),
  ).not.toBeInTheDocument();
  const text = await screen.findByText(/<script>مرحبا/);
  expect(text).toHaveAttribute("dir", "auto");
  expect(text).toHaveAttribute("lang", "ar");
  expect(document.querySelector("script")).toBeNull();
});
it("pages every frozen section with its own bounded cursor", async () => {
  for (const call of [
    api.getChangeSetItems,
    api.getChangeSetFiles,
    api.getChangeSetValues,
    api.getChangeSetActivity,
  ])
    call
      .mockResolvedValueOnce(ok({ items: [], next_cursor: "opaque" }))
      .mockResolvedValue(empty());
  render(view());
  for (const label of [
    "Load more proposals",
    "Load more files",
    "Load more diff entries",
    "Load more activity",
  ])
    await userEvent.click(await screen.findByRole("button", { name: label }));
  for (const call of [
    api.getChangeSetItems,
    api.getChangeSetFiles,
    api.getChangeSetValues,
    api.getChangeSetActivity,
  ])
    expect(call.mock.calls[1][0].query).toEqual({ cursor: "opaque" });
});
it("purges detail on lost read authority from a paged projection", async () => {
  api.getChangeSetFiles.mockResolvedValue({
    response: new Response(null, { status: 403 }),
  });
  render(view());
  expect(await screen.findByText("Change set unavailable")).toBeInTheDocument();
  expect(screen.queryByText(/Captured head/)).not.toBeInTheDocument();
});
it("drops a pending action result when the principal changes", async () => {
  let finish!: (value: ReturnType<typeof ok>) => void;
  api.retryChangeSet.mockImplementation(
    () =>
      new Promise((r) => {
        finish = r;
      }),
  );
  const mounted = render(view());
  await userEvent.click(
    await screen.findByRole("button", { name: "Retry submission" }),
  );
  api.getChangeSet.mockResolvedValue({
    response: new Response(null, { status: 404 }),
  });
  mounted.rerender(view(undefined, "other-token", "other"));
  await screen.findByText("Change set unavailable");
  finish(ok(submissionFixture({ status: "succeeded", pr_id: 41 })));
  await waitFor(() =>
    expect(screen.queryByText("Pull request opened")).not.toBeInTheDocument(),
  );
});
it("restores the exact second-page history invoker after detail unmount and return", async () => {
  api.listChangeSets.mockImplementation(
    ({ query }: { query: { cursor?: string } }) =>
      Promise.resolve(
        ok({
          items: [submissionFixture({ id: query.cursor ? "second" : "first" })],
          next_cursor: query.cursor ? null : "page-two",
        }),
      ),
  );
  render(view("/products/product/change-sets/history"));
  await userEvent.click(
    await screen.findByRole("button", { name: "Load more submissions" }),
  );
  const rows = screen.getAllByRole("link", { name: /View change set/ });
  api.getChangeSet.mockResolvedValue(
    ok(submissionFixture({ id: "second", status: "resolved" })),
  );
  await userEvent.click(rows[1]);
  await screen.findByRole("heading", { name: "Change set" });
  await userEvent.click(
    screen.getByRole("link", { name: "Back to submission history" }),
  );
  await waitFor(() =>
    expect(document.getElementById("history-second")).toHaveFocus(),
  );
  expect(
    within(screen.getByRole("list")).getAllByRole("listitem"),
  ).toHaveLength(2);
});

it("shows the verified rebased head separately from the original submitted commit", async () => {
  api.getChangeSet.mockResolvedValue(
    ok(
      submissionFixture({
        status: "succeeded",
        pr_state: "OPEN",
        commit_hash: "b".repeat(40),
        pr_tracking: {
          source_commit: "c".repeat(40),
          target_commit: "d".repeat(40),
          content_status: "verified",
          merge_status: "clean",
          checked_at: "2026-10-09T12:00:00Z",
        },
      }),
    ),
  );
  render(view());
  expect(
    await screen.findByRole("heading", { name: "Rebase verified" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/Current PR commit:/)).toHaveTextContent(
    "c".repeat(40),
  );
  expect(screen.getByText(/Submitted commit:/)).toHaveTextContent(
    "b".repeat(40),
  );
  expect(
    screen.getByText("Approved changes preserved. No Git conflicts."),
  ).toBeInTheDocument();
});

it("makes real merge conflicts visible and offers a read-only status check", async () => {
  api.getChangeSet.mockResolvedValue(
    ok(
      submissionFixture({
        status: "needs_attention",
        error_code: "pr_merge_conflicts",
        can_reconcile: true,
        pr_state: "OPEN",
        commit_hash: "b".repeat(40),
        pr_tracking: {
          source_commit: "b".repeat(40),
          target_commit: "d".repeat(40),
          content_status: "original",
          merge_status: "conflicts",
          checked_at: "2026-10-09T12:00:00Z",
        },
      }),
    ),
  );
  render(view());
  expect(
    await screen.findByRole("heading", { name: "Merge conflicts" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Resolve conflicts in the repository, then check status.",
  );
  expect(screen.getByRole("button", { name: "Check status" })).toBeEnabled();
  expect(screen.queryByText(/provider conflict/)).not.toBeInTheDocument();
});
