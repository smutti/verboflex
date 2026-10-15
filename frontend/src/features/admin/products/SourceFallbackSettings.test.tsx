import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import {
  getAdminSourceFallback,
  searchTranslationKeys,
  updateAdminSourceFallback,
} from "../../../api/client";
import { SourceFallbackSettings } from "./SourceFallbackSettings";

vi.mock("../../../api/client", () => ({
  getAdminSourceFallback: vi.fn(),
  searchTranslationKeys: vi.fn(),
  updateAdminSourceFallback: vi.fn(),
}));

const initial = {
  product_id: "product",
  version: 0,
  enabled: false,
  language: null,
  available_languages: ["it-IT"],
  source_texts: [],
};
function result(data: unknown) {
  return {
    data,
    response: new Response(),
    request: new Request("https://example.test"),
  } as never;
}
function open() {
  const view = render(
    <SourceFallbackSettings accessToken="token" productId="product" />,
  );
  expect(getAdminSourceFallback).not.toHaveBeenCalled();
  const details = view.container.querySelector("details")!;
  details.open = true;
  fireEvent(details, new Event("toggle"));
  return view;
}
beforeEach(() => {
  vi.mocked(getAdminSourceFallback).mockResolvedValue(result(initial));
  vi.mocked(searchTranslationKeys).mockResolvedValue(
    result({
      next_cursor: null,
      items: ["Operazione completata", "Open the message"].map(
        (source_text) => ({
          source_text,
          source_truncated: false,
          base_language: "it-IT",
          slots: [
            {
              language: "it-IT",
              provenance: { format: "qt_ts" },
              selector_kinds: ["scalar"],
            },
          ],
        }),
      ),
    }),
  );
  vi.mocked(updateAdminSourceFallback).mockImplementation(async (options) =>
    result({
      ...initial,
      ...options!.body,
      version: 1,
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it("loads only when opened and saves explicitly selected sources with the current version", async () => {
  open();
  const enable = await screen.findByRole("checkbox", {
    name: "Use confirmed source text for the base language",
  });
  expect(enable).not.toBeChecked();
  await userEvent.click(enable);
  await userEvent.click(
    await screen.findByRole("checkbox", { name: "Operazione completata" }),
  );
  expect(
    screen.getByRole("checkbox", { name: "Open the message" }),
  ).not.toBeChecked();
  await userEvent.click(
    screen.getByRole("button", { name: "Save source language settings" }),
  );
  expect(
    await screen.findByText("Source language settings saved."),
  ).toBeVisible();
  expect(updateAdminSourceFallback).toHaveBeenCalledWith(
    expect.objectContaining({
      auth: "token",
      path: { product_id: "product" },
      body: {
        expected_version: 0,
        enabled: true,
        language: "it-IT",
        source_texts: ["Operazione completata"],
      },
    }),
  );
  await userEvent.click(enable);
  await userEvent.click(
    screen.getByRole("button", { name: "Save source language settings" }),
  );
  await waitFor(() =>
    expect(updateAdminSourceFallback).toHaveBeenLastCalledWith(
      expect.objectContaining({
        body: {
          expected_version: 1,
          enabled: false,
          language: "it-IT",
          source_texts: ["Operazione completata"],
        },
      }),
    ),
  );
});

it("keeps the selection when an optimistic save fails and never reports success", async () => {
  vi.mocked(updateAdminSourceFallback).mockResolvedValue({
    error: { detail: "Conflict" },
  } as never);
  open();
  await userEvent.click(
    await screen.findByRole("checkbox", { name: "Operazione completata" }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Save source language settings" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Settings were not saved",
  );
  expect(
    screen.getByRole("checkbox", { name: "Operazione completata" }),
  ).toBeChecked();
  expect(screen.queryByText("Source language settings saved.")).toBeNull();
});

it("retries configuration errors and aborts an outstanding request when unmounted", async () => {
  vi.mocked(getAdminSourceFallback).mockResolvedValueOnce({
    error: {},
  } as never);
  const view = open();
  await userEvent.click(
    await screen.findByRole("button", { name: "Retry settings" }),
  );
  expect(
    await screen.findByRole("checkbox", {
      name: "Use confirmed source text for the base language",
    }),
  ).toBeVisible();
  const signal = vi.mocked(getAdminSourceFallback).mock.calls.at(-1)![0]!
    .signal;
  view.unmount();
  expect(signal!.aborted).toBe(true);
});

it("restores the saved selection and excludes truncated, foreign, and non-scalar candidates", async () => {
  vi.mocked(getAdminSourceFallback).mockResolvedValue(
    result({
      ...initial,
      enabled: true,
      language: "it-IT",
      version: 4,
      source_texts: ["Operazione completata"],
    }),
  );
  vi.mocked(searchTranslationKeys).mockResolvedValue(
    result({
      next_cursor: null,
      items: [
        {
          source_text: "Operazione completata",
          base_language: "it-IT",
          slots: [
            {
              language: "it-IT",
              provenance: { format: "qt_ts" },
              selector_kinds: ["scalar"],
            },
          ],
        },
        {
          source_text: "Truncated",
          source_truncated: true,
          base_language: "it-IT",
          slots: [],
        },
        { source_text: "Other locale", base_language: "en", slots: [] },
        {
          source_text: "Plural",
          base_language: "it-IT",
          slots: [
            {
              language: "it-IT",
              provenance: { format: "qt_ts" },
              selector_kinds: ["plural"],
            },
          ],
        },
      ],
    }),
  );
  open();
  expect(
    await screen.findByRole("checkbox", { name: "Operazione completata" }),
  ).toBeChecked();
  expect(screen.queryByRole("checkbox", { name: "Truncated" })).toBeNull();
  expect(screen.queryByRole("checkbox", { name: "Other locale" })).toBeNull();
  expect(screen.queryByRole("checkbox", { name: "Plural" })).toBeNull();
});
