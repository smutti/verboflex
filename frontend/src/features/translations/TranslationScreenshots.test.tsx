import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
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
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });
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

  it("restores waiting work, shows elapsed time, polls through rendering and displays the result", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T12:00:05Z"));
    api.listTranslationScreenshots.mockResolvedValue({
      data: { items: [{ ...job, state: "queued" }] },
    });
    api.getTranslationScreenshot
      .mockResolvedValueOnce({ data: { ...job, state: "rendering" } })
      .mockResolvedValue({ data: job });
    await act(async () => {
      render(
        <TranslationScreenshots
          accessToken="token"
          groupId="group"
          dirty={false}
        />,
      );
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Waiting to generate screenshot",
    );
    expect(screen.getByText("Elapsed: 0m 5s")).toBeVisible();
    expect(screen.getByText(/This can take several minutes/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Generating screenshot…" }),
    ).toBeDisabled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Generating screenshot",
    );
    expect(screen.getByText("Elapsed: 0m 7s")).toBeVisible();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(screen.getByRole("status")).toHaveTextContent("Screenshot ready");
    expect(screen.getByRole("img")).toBeVisible();
    expect(screen.queryByText(/Elapsed:/)).toBeNull();
    expect(api.requestTranslationScreenshot).not.toHaveBeenCalled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(api.getTranslationScreenshot).toHaveBeenCalledTimes(2);
  });

  it("clears a transient connection warning when polling recovers", async () => {
    vi.useFakeTimers();
    api.listTranslationScreenshots.mockResolvedValue({
      data: { items: [{ ...job, state: "rendering" }] },
    });
    api.getTranslationScreenshot
      .mockRejectedValueOnce(new Error("Offline"))
      .mockResolvedValue({ data: job });
    await act(async () => {
      render(
        <TranslationScreenshots
          accessToken="token"
          groupId="group"
          dirty={false}
        />,
      );
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Connection interrupted",
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent("Screenshot ready");
  });

  it("explains a failed render and allows a fresh request", async () => {
    api.listTranslationScreenshots.mockResolvedValue({
      data: {
        items: [{ ...job, state: "failed", error_code: "render_timeout" }],
      },
    });
    const user = userEvent.setup();
    render(
      <TranslationScreenshots
        accessToken="token"
        groupId="group"
        dirty={false}
      />,
    );
    expect(
      await screen.findByText(
        "The screenshot took too long to generate. Try again.",
      ),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Generate screenshot" }),
    );
    expect(await screen.findByRole("img")).toBeVisible();
    expect(
      api.requestTranslationScreenshot.mock.calls[0][0].path.job_id,
    ).not.toBe(job.id);
  });

  it("announces the request immediately while the server accepts it", async () => {
    let accept!: (value: unknown) => void;
    api.requestTranslationScreenshot.mockReturnValue(
      new Promise((resolve) => {
        accept = resolve;
      }),
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
    expect(screen.getByRole("status")).toHaveTextContent(
      "Requesting screenshot",
    );
    expect(screen.getByRole("button", { name: "Requesting…" })).toBeDisabled();
    await act(async () => {
      accept({ data: { ...job, state: "queued" } });
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Waiting to generate screenshot",
    );
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

  it("marks an older capture as stale after saving or editing without generating automatically", async () => {
    api.listTranslationScreenshots.mockResolvedValue({
      data: {
        items: [{ ...job, request: { ...job.request, proposal_version: 4 } }],
      },
    });
    const view = render(
      <TranslationScreenshots
        accessToken="token"
        groupId="group"
        dirty={false}
        proposalVersion={4}
      />,
    );
    expect(await screen.findByRole("img")).toBeVisible();
    expect(
      screen.queryByText(/This screenshot does not show your latest changes/),
    ).toBeNull();
    view.rerender(
      <TranslationScreenshots
        accessToken="token"
        groupId="group"
        dirty={false}
        proposalVersion={5}
      />,
    );
    expect(
      screen.getByText(/This screenshot does not show your latest changes/),
    ).toBeVisible();
    view.rerender(
      <TranslationScreenshots
        accessToken="token"
        groupId="group"
        dirty
        proposalVersion={4}
      />,
    );
    expect(
      screen.getByText(/This screenshot does not show your latest changes/),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Generate screenshot" }),
    ).toBeDisabled();
    expect(api.requestTranslationScreenshot).not.toHaveBeenCalled();
  });

  it("keeps generation explicit and preview configuration collapsed when no screenshot exists", async () => {
    render(
      <TranslationScreenshots
        accessToken="token"
        groupId="group"
        dirty={false}
      />,
    );
    expect(await screen.findByText("No screenshot available")).toBeVisible();
    expect(screen.getByLabelText("Screen preview")).not.toBeVisible();
    expect(
      screen.getByRole("button", { name: "Generate screenshot" }),
    ).toBeEnabled();
    await userEvent.click(screen.getByText("Screenshot options"));
    expect(screen.getByLabelText("Screen preview")).toBeVisible();
    expect(api.requestTranslationScreenshot).not.toHaveBeenCalled();
  });

  it("shows a compact unavailable state without offering generation for an unconfigured product", async () => {
    api.getTranslationCodeContext.mockResolvedValue({
      data: { configured: false },
    });
    render(
      <TranslationScreenshots
        accessToken="token"
        groupId="group"
        dirty={false}
      />,
    );
    expect(
      await screen.findByText(
        "Screenshots are not available for this translation.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Generate screenshot" }),
    ).toBeNull();
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
