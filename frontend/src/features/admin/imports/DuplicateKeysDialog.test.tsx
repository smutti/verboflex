import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { getAdminPreviewDuplicates } from "../../../api/client";
import { DuplicateKeysDialog } from "./DuplicateKeysDialog";

vi.mock("../../../api/client", async (original) => ({
  ...(await original<typeof import("../../../api/client")>()),
  getAdminPreviewDuplicates: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it("opens read-only duplicate diagnostics with source authority and escaped keys", async () => {
  vi.mocked(getAdminPreviewDuplicates).mockResolvedValue({
    data: {
      report_id: "report",
      execution: 2,
      complete: true,
      issue_codes: [],
      group_count: 1,
      repeated_occurrences: 2,
      sources: [
        {
          repository_id: "repo",
          repository_side: "direct",
          source_branch: "source/main",
          commit_hash: "a".repeat(40),
        },
      ],
      items: [
        {
          id: "group",
          repository_side: "direct",
          language: "default",
          key_preview: "<b>duplicate</b>",
          key_length: 16,
          occurrence_count: 3,
          occurrences: [
            { path: "moko/base/strings.xml", resource_position: 7 },
          ],
          next_occurrence_cursor: null,
        },
      ],
      next_cursor: null,
    },
    request: new Request("http://localhost/test"),
    response: new Response(),
  });
  render(<DuplicateKeysDialog accessToken="token" previewJobId="job" />);
  expect(getAdminPreviewDuplicates).not.toHaveBeenCalled();
  await userEvent.click(
    screen.getByRole("button", { name: "View duplicate keys" }),
  );
  expect(
    await screen.findByText("1 duplicate groups · 2 repeated occurrences"),
  ).toBeVisible();
  expect(screen.getByText("<b>duplicate</b>").tagName).not.toBe("B");
  expect(screen.getByText(/Resource position 7/)).toBeVisible();
  expect(screen.getByText(/source\/main/)).toBeVisible();
  expect(screen.getByText(/continue to import/)).toBeVisible();
  expect(screen.getByText(/stay quarantined/)).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Close diagnostics" }),
  );
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
});

it("shows an honest load failure and retry", async () => {
  vi.mocked(getAdminPreviewDuplicates).mockRejectedValue(new Error("failure"));
  render(<DuplicateKeysDialog accessToken="token" previewJobId="job" />);
  await userEvent.click(
    screen.getByRole("button", { name: "View duplicate keys" }),
  );
  expect(
    await screen.findByRole("button", { name: "Retry diagnostics" }),
  ).toBeVisible();
  expect(screen.queryByText(/0 duplicate groups/)).not.toBeInTheDocument();
});
