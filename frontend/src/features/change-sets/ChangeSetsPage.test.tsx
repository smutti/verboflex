import "@testing-library/jest-dom/vitest";
import { StrictMode } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ChangeSetsLayout } from "./ChangeSetWorkspace";
import { ChangeSetsPage } from "./ChangeSetsPage";
import { setSubmissionEntry } from "./submissionEntry";
const api = vi.hoisted(() => ({
  getChangeSetCandidates: vi.fn(),
  createSubmissionReview: vi.fn(),
  listChangeSets: vi.fn(),
}));
vi.mock("../../api/client", () => api);
function view(
  path = "/products/product/change-sets",
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
        </Route>
      </Routes>
    </MemoryRouter>
  );
}
const candidate = {
  proposal_id: "proposal",
  version: 2,
  key: "hello",
  language: "it",
  state: "approved",
  value_count: 2,
  can_review: true,
  blocker: null,
  mapping_id: "mapping",
  published_excerpt: "Old",
  proposed_excerpt: "New",
};
beforeEach(() => {
  vi.resetAllMocks();
  api.getChangeSetCandidates.mockResolvedValue({
    data: {
      product_id: "product",
      active_revision_id: "revision",
      can_request_review: true,
      max_selected_proposals: 100,
      items: [candidate],
      next_after: null,
      destinations: [],
    },
  });
  api.listChangeSets.mockResolvedValue({
    data: { items: [], next_cursor: null },
    response: new Response(),
  });
});
afterEach(cleanup);
it("removes protected candidates and selection after read access is revoked", async () => {
  render(<StrictMode>{view()}</StrictMode>);
  await userEvent.click(
    await screen.findByRole("checkbox", { name: "Select hello (it)" }),
  );
  api.getChangeSetCandidates.mockResolvedValue({
    response: new Response(null, { status: 403 }),
  });
  await userEvent.click(screen.getByRole("button", { name: "Apply filters" }));
  expect(await screen.findByText("Change set unavailable")).toBeInTheDocument();
  expect(screen.queryByText("New")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("region", { name: "Selected changes" }),
  ).not.toBeInTheDocument();
});
it("seeds only the exact saved complete version through the server's group filter", async () => {
  setSubmissionEntry({
    principalId: "actor",
    accessToken: "token",
    productId: "product",
    translationGroupId: "translation",
    expectedVersion: 2,
  });
  render(view());
  expect(
    await screen.findByRole("button", { name: "Review selected changes (1)" }),
  ).toBeEnabled();
  expect(
    api.getChangeSetCandidates.mock.calls[0][0].query.translation_group_id,
  ).toBe("translation");
  expect(api.createSubmissionReview).not.toHaveBeenCalled();
});
it("keeps a stale saved entry visibly blocked instead of choosing the new version", async () => {
  setSubmissionEntry({
    principalId: "actor",
    accessToken: "token",
    productId: "product",
    translationGroupId: "translation",
    expectedVersion: 1,
  });
  render(view());
  expect(
    await screen.findByText("Selected changes need review"),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Review selected changes (0)" }),
  ).toBeDisabled();
});
it("does not transfer a saved entry to another principal", async () => {
  setSubmissionEntry({
    principalId: "actor",
    accessToken: "token",
    productId: "product",
    translationGroupId: "translation",
    expectedVersion: 2,
  });
  render(view(undefined, "other-token", "other"));
  expect(
    await screen.findByRole("checkbox", { name: "Select hello (it)" }),
  ).not.toBeChecked();
  expect(
    api.getChangeSetCandidates.mock.calls[0][0].query.translation_group_id,
  ).toBeUndefined();
});
it("shows a reloadable read-only empty history without write controls", async () => {
  render(view("/products/product/change-sets/history"));
  expect(await screen.findByText("No submissions yet")).toBeInTheDocument();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(api.createSubmissionReview).not.toHaveBeenCalled();
  await userEvent.click(
    screen.getByRole("button", { name: "Pending changes" }),
  );
  expect(
    await screen.findByRole("checkbox", { name: "Select hello (it)" }),
  ).toBeInTheDocument();
});
