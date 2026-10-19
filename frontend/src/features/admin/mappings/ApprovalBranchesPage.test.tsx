import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApprovalBranchesPage } from "./ApprovalBranchesPage";

const api = vi.hoisted(() => ({
  getBranchWorkflow: vi.fn(),
  configureBranchWorkflow: vi.fn(),
}));
vi.mock("../../../api/client", () => api);
const initial = {
  enabled: false,
  workflows: [],
  available_mappings: [
    {
      mapping_id: "source",
      repository: "synthetic-repository",
      source_branch: "release/base",
      workflow_id: null,
    },
  ],
};
beforeEach(() => {
  vi.resetAllMocks();
  api.getBranchWorkflow.mockResolvedValue({ data: initial });
});
afterEach(cleanup);

it.each(["team/approved", "release/base"])("configures working branch %s separately from the PR destination", async (workBranch) => {
  const user = userEvent.setup();
  api.configureBranchWorkflow.mockResolvedValue({
    data: {
      ...initial,
      enabled: true,
      available_mappings: [
        { ...initial.available_mappings[0], workflow_id: "workflow" },
      ],
      workflows: [
        {
          id: "workflow",
          repository: "synthetic-repository",
          work_branch: workBranch,
          target_branch: "release/next",
          active: true,
        },
      ],
    },
  });
  render(<ApprovalBranchesPage accessToken="token" productId="product" />);
  await user.selectOptions(
    await screen.findByLabelText("Translation source"),
    "source",
  );
  expect(screen.getByLabelText("PR destination")).toHaveValue("release/base");
  await user.type(screen.getByLabelText("Working branch"), workBranch);
  await user.clear(screen.getByLabelText("PR destination"));
  await user.type(screen.getByLabelText("PR destination"), "release/next");
  expect(api.configureBranchWorkflow).not.toHaveBeenCalled();
  await user.click(
    screen.getByRole("button", { name: "Enable approval commits" }),
  );
  await waitFor(() =>
    expect(api.configureBranchWorkflow).toHaveBeenCalledOnce(),
  );
  expect(api.configureBranchWorkflow).toHaveBeenCalledWith({
    auth: "token",
    path: { product_id: "product" },
    body: {
      mapping_id: "source",
      work_branch: workBranch,
      target_branch: "release/next",
    },
  });
  expect(await screen.findByText(workBranch)).toBeVisible();
  expect(screen.getByText("release/next")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Create pull request" }),
  ).not.toBeInTheDocument();
});

it("retains branch entries when saving fails", async () => {
  api.configureBranchWorkflow.mockResolvedValue({
    response: new Response(null, { status: 409 }),
    error: { detail: "This working branch is already configured" },
  });
  const user = userEvent.setup();
  render(<ApprovalBranchesPage accessToken="token" productId="product" />);
  await user.selectOptions(
    await screen.findByLabelText("Translation source"),
    "source",
  );
  await user.type(screen.getByLabelText("Working branch"), "team/approved");
  await user.click(
    screen.getByRole("button", { name: "Enable approval commits" }),
  );
  expect(
    await screen.findByText("This working branch is already configured"),
  ).toBeVisible();
  expect(screen.getByLabelText("Working branch")).toHaveValue("team/approved");
});
