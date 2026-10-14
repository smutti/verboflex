import "@testing-library/jest-dom/vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { BranchWorkflowPanel } from "./BranchWorkflowPanel";
const api = vi.hoisted(() => ({
  getBranchWorkflow: vi.fn(),
  createBranchPullRequest: vi.fn(),
  retryBranchChange: vi.fn(),
}));
vi.mock("../../api/client", () => api);
vi.mock("./changeSetContext", () => ({
  useChangeSetWorkspace: () => ({ accessToken: "token", productId: "product" }),
}));
const workflow = {
  enabled: true,
  repository: "translations",
  work_branch: "feature/translations",
  target_branch: "main",
  can_publish: true,
  can_create_pr: true,
  items: [
    {
      id: "first",
      label: "hello (it)",
      state: "committed",
      created_at: "2026-10-14T08:00:00Z",
      commit_hash: "abcdef0123456789",
      commit_url: "https://bitbucket.org/team/repo/commits/abcdef0123456789",
    },
  ],
  next_before: null,
};
beforeEach(() => {
  vi.resetAllMocks();
  api.getBranchWorkflow.mockResolvedValue({ data: workflow });
});
afterEach(cleanup);
it("shows each saved commit and opens a PR only on explicit confirmation", async () => {
  api.createBranchPullRequest.mockResolvedValue({
    data: { ...workflow, can_create_pr: false },
  });
  render(
    <BranchWorkflowPanel>
      <p>Legacy submissions</p>
    </BranchWorkflowPanel>,
  );
  expect(await screen.findByText("Saved to branch")).toBeVisible();
  expect(screen.getByRole("link", { name: "Commit abcdef0" })).toHaveAttribute(
    "href",
    workflow.items[0].commit_url,
  );
  expect(screen.queryByText("Legacy submissions")).not.toBeInTheDocument();
  expect(api.createBranchPullRequest).not.toHaveBeenCalled();
  await userEvent.click(
    screen.getByRole("button", { name: "Create pull request" }),
  );
  expect(api.createBranchPullRequest).not.toHaveBeenCalled();
  await userEvent.click(
    screen.getByRole("button", { name: "Confirm pull request" }),
  );
  await waitFor(() =>
    expect(api.createBranchPullRequest).toHaveBeenCalledTimes(1),
  );
});
it("shows queued approvals and prevents creating a PR before commits finish", async () => {
  api.getBranchWorkflow.mockResolvedValue({
    data: {
      ...workflow,
      can_create_pr: false,
      items: [
        {
          ...workflow.items[0],
          state: "queued",
          commit_hash: null,
          commit_url: null,
        },
      ],
    },
  });
  render(<BranchWorkflowPanel>Legacy</BranchWorkflowPanel>);
  expect(await screen.findByText("Waiting to save")).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Create pull request" }),
  ).toBeDisabled();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});
it("keeps the legacy workflow when branch commits are not configured", async () => {
  api.getBranchWorkflow.mockResolvedValue({ data: { enabled: false } });
  render(<BranchWorkflowPanel>Legacy submissions</BranchWorkflowPanel>);
  expect(await screen.findByText("Legacy submissions")).toBeVisible();
});
it("keeps workflow data out of an unauthorized response", async () => {
  api.getBranchWorkflow.mockResolvedValue({
    response: new Response(null, { status: 403 }),
  });
  render(<BranchWorkflowPanel>Legacy submissions</BranchWorkflowPanel>);
  expect(
    await screen.findByText("Repository workflow unavailable"),
  ).toBeVisible();
  expect(screen.queryByText("hello (it)")).not.toBeInTheDocument();
  expect(screen.queryByText("Legacy submissions")).not.toBeInTheDocument();
});
