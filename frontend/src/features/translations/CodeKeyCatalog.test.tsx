import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { CodeKeyCatalog } from "./CodeKeyCatalog";

const api = vi.hoisted(() => ({
  listCodeKeys: vi.fn(),
  listProductCodeSources: vi.fn(),
}));
vi.mock("../../api/client", () => api);
afterEach(cleanup);
beforeEach(() => vi.resetAllMocks());

it("loads the full catalog only on request, including keys without any translation", async () => {
  api.listProductCodeSources.mockResolvedValue({
    data: {
      items: [
        {
          scope_id: "scope",
          mapping_id: "mapping",
          key_count: 2,
          missing_count: 1,
        },
      ],
      next_cursor: null,
    },
  });
  api.listCodeKeys
    .mockResolvedValueOnce({
      data: {
        items: [
          { key: "missing", missing_translation: true, missing_base: true },
        ],
        next_cursor: "missing",
        orphan_count: 3,
      },
    })
    .mockResolvedValueOnce({
      data: {
        items: [
          { key: "title", missing_translation: false, missing_base: false },
        ],
        next_cursor: null,
        orphan_count: 3,
      },
    });
  const user = userEvent.setup();
  render(<CodeKeyCatalog accessToken="token" productId="product" />);
  expect(api.listCodeKeys).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Code keys" }));
  expect(await screen.findByText("missing")).toBeVisible();
  expect(screen.getByText("No imported translation")).toBeVisible();
  expect(
    screen.getByText("3 translation keys are outside this code catalog."),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "More keys" }));
  expect(await screen.findByText("title")).toBeVisible();
  expect(api.listCodeKeys.mock.calls[1][0]).toMatchObject({
    auth: "token",
    path: { scope_id: "scope" },
    query: { after: "missing" },
  });
  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: "More keys" }),
    ).not.toBeInTheDocument(),
  );
});

it("shows a recoverable error when catalog access is denied", async () => {
  api.listProductCodeSources.mockResolvedValue({
    error: { detail: "unavailable" },
  });
  render(<CodeKeyCatalog accessToken="token" productId="product" />);
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: "Code keys" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Close and reopen to retry",
  );
  expect(api.listCodeKeys).not.toHaveBeenCalled();
});
