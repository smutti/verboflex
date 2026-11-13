import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { BulkAuthoringApproval } from "./BulkAuthoringApproval";
import {
  approveAllAuthoringDrafts,
  getAuthoringApprovalPreview,
} from "../../api/client";
vi.mock("../../api/client", () => ({
  approveAllAuthoringDrafts: vi.fn(),
  getAuthoringApprovalPreview: vi.fn(),
}));
const preview = {
  count: 506,
  languages: { fr: 251, nl: 255 },
  fingerprint: "a".repeat(64),
  source_changed: 0,
  over_limit: false,
  latest: null,
};
const job = {
  id: "job",
  count: 506,
  state: "queued",
  error: null,
  branch_job_ids: [],
  created_at: "2026-01-01T00:00:00Z",
};
function setup() {
  return render(
    <BulkAuthoringApproval
      accessToken="token"
      productId="synthetic"
      revision={0}
      onCompleted={vi.fn()}
    />,
  );
}
beforeEach(() => {
  vi.mocked(getAuthoringApprovalPreview).mockResolvedValue({
    data: preview,
  } as never);
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
it("confirms all 506 server-selected drafts, then leaves processing on the server", async () => {
  const user = userEvent.setup();
  const view = setup();
  await user.click(
    await screen.findByRole("button", { name: "Approve all drafts" }),
  );
  const dialog = screen.getByRole("dialog");
  expect(dialog).toHaveTextContent("506 drafts selected");
  expect(dialog).toHaveTextContent("fr: 251");
  expect(dialog).toHaveTextContent("nl: 255");
  expect(approveAllAuthoringDrafts).not.toHaveBeenCalled();
  await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(approveAllAuthoringDrafts).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Approve all drafts" }));
  vi.mocked(approveAllAuthoringDrafts).mockResolvedValue({
    data: job,
  } as never);
  vi.mocked(getAuthoringApprovalPreview).mockResolvedValue({
    data: { ...preview, latest: job },
  } as never);
  await user.click(screen.getByRole("button", { name: "Confirm approval" }));
  await screen.findByText(
    "Approval is running on the server. You can leave this page.",
  );
  expect(approveAllAuthoringDrafts).toHaveBeenCalledTimes(1);
  expect(approveAllAuthoringDrafts).toHaveBeenCalledWith(
    expect.objectContaining({
      body: { fingerprint: preview.fingerprint },
      path: { product_id: "synthetic", request_id: expect.any(String) },
    }),
  );
  view.unmount();
  setup();
  expect(
    await screen.findByRole("button", { name: "Approving drafts…" }),
  ).toBeDisabled();
  expect(approveAllAuthoringDrafts).toHaveBeenCalledTimes(1);
});
it("blocks changed sources and reports a server failure without clearing drafts", async () => {
  vi.mocked(getAuthoringApprovalPreview).mockResolvedValue({
    data: {
      ...preview,
      source_changed: 3,
      latest: {
        ...job,
        state: "failed",
        error: "new_key (fr): Complete the translation before approving",
      },
    },
  } as never);
  const user = userEvent.setup();
  setup();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "All selected drafts are unchanged.",
  );
  await user.click(screen.getByRole("button", { name: "Approve all drafts" }));
  expect(
    screen.getByRole("button", { name: "Confirm approval" }),
  ).toBeDisabled();
  expect(screen.getByRole("dialog")).toHaveTextContent(
    "3 drafts have a changed source",
  );
  expect(approveAllAuthoringDrafts).not.toHaveBeenCalled();
});
it("reuses the operation identifier after an uncertain network response", async () => {
  const user = userEvent.setup();
  setup();
  await user.click(
    await screen.findByRole("button", { name: "Approve all drafts" }),
  );
  vi.mocked(approveAllAuthoringDrafts).mockRejectedValue(
    new Error("synthetic disconnect"),
  );
  await user.click(screen.getByRole("button", { name: "Confirm approval" }));
  await screen.findByRole("alert");
  await user.click(screen.getByRole("button", { name: "Confirm approval" }));
  await waitFor(() =>
    expect(approveAllAuthoringDrafts).toHaveBeenCalledTimes(2),
  );
  expect(vi.mocked(approveAllAuthoringDrafts).mock.calls[0][0]?.path).toEqual(
    vi.mocked(approveAllAuthoringDrafts).mock.calls[1][0]?.path,
  );
});
