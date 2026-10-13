import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TranslationScreenshots } from "./TranslationScreenshots";

const api = vi.hoisted(() => ({
  getTranslationCodeContext: vi.fn(),
  listTranslationScreenshots: vi.fn(),
  requestTranslationScreenshot: vi.fn(),
  getTranslationScreenshot: vi.fn(),
  getTranslationScreenshotImage: vi.fn(),
  cancelTranslationScreenshot: vi.fn(),
}));
vi.mock("../../api/client", () => api);

const job = {
  id: "capture-id",
  state: "succeeded",
  request: { preview_function: "demo.HomePreview" },
  created_at: "2026-01-01T12:00:00Z",
  expires_at: "2026-01-08T12:00:00Z",
  error_code: null,
};

describe("Compose screenshots", () => {
  afterEach(cleanup);
  beforeEach(() => {
    vi.clearAllMocks();
    api.getTranslationCodeContext.mockResolvedValue({
      data: {
        configured: true,
        occurrences: [
          {
            key: "title",
            path: "Screen.kt",
            line: 10,
            column: 2,
            function: "demo.Home",
            symbol: "Res.strings.title",
            kind: "reference",
          },
        ],
        previews: [
          {
            function: "demo.HomePreview",
            path: "Screen.kt",
            line: 20,
            keys: ["title"],
            annotation: "@Preview",
            evidence: "static_reference",
          },
        ],
        capture_functions: ["demo.HomePreview"],
      },
    });
    api.listTranslationScreenshots.mockResolvedValue({
      data: { items: [], next_cursor: null },
    });
    api.requestTranslationScreenshot.mockResolvedValue({ data: job });
    api.getTranslationScreenshotImage.mockResolvedValue({
      data: new Blob(["synthetic"], { type: "image/png" }),
    });
    URL.createObjectURL = vi.fn(() => "blob:synthetic-preview");
    URL.revokeObjectURL = vi.fn();
  });

  it("requests a fresh capture with a saved proposal and loads the image with authentication", async () => {
    const user = userEvent.setup();
    const view = render(
      <TranslationScreenshots
        accessToken="token"
        groupId="group"
        dirty={false}
        proposalVersion={4}
      />,
    );
    await user.click(
      await screen.findByRole("button", { name: "Generate screenshot" }),
    );
    const call = api.requestTranslationScreenshot.mock.calls[0][0];
    expect(call.auth).toBe("token");
    expect(call.body).toEqual({
      preview_function: "demo.HomePreview",
      theme: "light",
      proposal_version: 4,
    });
    expect(call.path.job_id).toMatch(/^[\da-f-]{36}$/);
    expect(
      await screen.findByAltText(
        "Compose screen preview with the selected translations",
      ),
    ).toHaveAttribute("src", "blob:synthetic-preview");
    expect(api.getTranslationScreenshotImage.mock.calls[0][0].auth).toBe(
      "token",
    );
    view.unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:synthetic-preview");
  });

  it("requires saving dirty text", async () => {
    render(
      <TranslationScreenshots accessToken="token" groupId="group" dirty />,
    );
    expect(
      await screen.findByRole("button", { name: "Generate screenshot" }),
    ).toBeDisabled();
    expect(api.requestTranslationScreenshot).not.toHaveBeenCalled();
  });

  it("reuses the request identity after a network failure", async () => {
    api.requestTranslationScreenshot.mockRejectedValueOnce(
      new Error("Network interrupted"),
    );
    const user = userEvent.setup();
    render(
      <TranslationScreenshots
        accessToken="token"
        groupId="group"
        dirty={false}
      />,
    );
    await user.click(
      await screen.findByRole("button", { name: "Generate screenshot" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Retry capture request" }),
    );
    await waitFor(() =>
      expect(api.requestTranslationScreenshot).toHaveBeenCalledTimes(2),
    );
    expect(api.requestTranslationScreenshot.mock.calls[1][0].path.job_id).toBe(
      api.requestTranslationScreenshot.mock.calls[0][0].path.job_id,
    );
  });

  it("restores a completed capture after navigation", async () => {
    api.listTranslationScreenshots.mockResolvedValue({
      data: { items: [job], next_cursor: null },
    });
    render(
      <TranslationScreenshots
        accessToken="token"
        groupId="group"
        dirty={false}
      />,
    );
    expect(
      await screen.findByAltText(
        "Compose screen preview with the selected translations",
      ),
    ).toBeVisible();
    expect(api.requestTranslationScreenshot).not.toHaveBeenCalled();
  });

  it("retries the completed image on reconnect without rendering again", async () => {
    api.listTranslationScreenshots.mockResolvedValue({
      data: { items: [job], next_cursor: null },
    });
    api.getTranslationScreenshotImage.mockRejectedValueOnce(
      new Error("Offline"),
    );
    const user = userEvent.setup();
    render(
      <TranslationScreenshots
        accessToken="token"
        groupId="group"
        dirty={false}
      />,
    );
    await user.click(await screen.findByRole("button", { name: "Reconnect" }));
    expect(
      await screen.findByAltText(
        "Compose screen preview with the selected translations",
      ),
    ).toBeVisible();
    expect(api.getTranslationScreenshotImage).toHaveBeenCalledTimes(2);
    expect(api.requestTranslationScreenshot).not.toHaveBeenCalled();
  });
});
