import "@testing-library/jest-dom/vitest";

import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  listProjectUpdates,
  listMyActivity,
  type CurrentUserResponse,
  type ProjectUpdatesPage as Updates,
} from "../../api/client";
import { ProjectUpdatesPage } from "./ProjectUpdatesPage";

vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  listProjectUpdates: vi.fn(),
  listMyActivity: vi.fn(),
}));
const list = vi.mocked(listProjectUpdates);
const principal: CurrentUserResponse = {
  id: "me",
  email: "me@example.test",
  display_name: "Mira",
  roles: ["viewer"],
  must_change_password: false,
};
function page(
  start: number,
  count: number,
  cursor: string | null = null,
): Updates {
  return {
    items: Array.from({ length: count }, (_, n) => ({
      kind: "current_import_completed" as const,
      event_id: `import:${start + n}`,
      occurred_at: "2026-10-03T12:00:00Z",
      product: { id: `p${start + n}`, name: `Product ${start + n}` },
      actor: null,
    })),
    next_cursor: cursor,
  };
}
function view(token = "token") {
  return (
    <MemoryRouter>
      <ProjectUpdatesPage accessToken={token} principal={principal} />
    </MemoryRouter>
  );
}
beforeEach(() => list.mockReset());
afterEach(cleanup);

it("loads older updates, retains them on failure, and retries the same cursor", async () => {
  list
    .mockResolvedValueOnce({ data: page(0, 20, "next"), error: undefined })
    .mockRejectedValueOnce(new Error("private data"))
    .mockResolvedValueOnce({ data: page(20, 2), error: undefined });
  render(view());
  await screen.findByText("Product 0");
  expect(
    within(screen.getByRole("list")).getAllByRole("listitem"),
  ).toHaveLength(20);
  await userEvent.click(screen.getByRole("button", { name: "Load more" }));
  expect(await screen.findByRole("alert")).not.toHaveTextContent(
    "private data",
  );
  expect(screen.getByText("Product 0")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  await screen.findByText("Product 21");
  expect(
    within(screen.getByRole("list")).getAllByRole("listitem"),
  ).toHaveLength(22);
  expect(list.mock.calls[2][0]?.query).toEqual({ cursor: "next" });
  expect(screen.queryByRole("button", { name: "Load more" })).toBeNull();
  expect(screen.getByRole("link", { name: "Back to Home" })).toHaveAttribute(
    "href",
    "/",
  );
});

it("refreshes from the first page and handles empty results", async () => {
  list
    .mockResolvedValueOnce({ data: page(0, 1), error: undefined })
    .mockResolvedValueOnce({ data: page(0, 0), error: undefined });
  render(view());
  await screen.findByText("Product 0");
  await userEvent.click(screen.getByRole("button", { name: "Refresh" }));
  expect(await screen.findByText("No project updates yet")).toBeVisible();
  expect(screen.queryByText("Product 0")).toBeNull();
  expect(list.mock.calls[1][0]?.query).toEqual({});
});

it("clears prior authority and ignores a late response after token changes", async () => {
  let finish!: (value: { data: Updates; error: undefined }) => void;
  list
    .mockImplementationOnce(
      () =>
        new Promise<{ data: Updates; error: undefined }>((resolve) => {
          finish = resolve;
        }),
    )
    .mockResolvedValueOnce({ data: page(50, 1), error: undefined });
  const { rerender } = render(view());
  await waitFor(() => expect(list).toHaveBeenCalledOnce());
  const signal = list.mock.calls[0][0]?.signal;
  rerender(view("new-token"));
  await screen.findByText("Product 50");
  await act(async () => finish({ data: page(0, 1), error: undefined }));
  expect(signal?.aborted).toBe(true);
  expect(screen.queryByText("Product 0")).toBeNull();
});

it("retries initial loading failures", async () => {
  list
    .mockResolvedValueOnce({
      data: undefined,
      error: { detail: "private failure" },
    })
    .mockResolvedValueOnce({ data: page(0, 1), error: undefined });
  render(view());
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Activity could not be loaded.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("Product 0")).toBeVisible();
});

it("pages personal activity through the personal endpoint and clears it when the feed changes", async () => {
  const personal = vi.mocked(listMyActivity);
  personal.mockReset();
  personal
    .mockResolvedValueOnce({
      data: page(0, 20, "older-mine"),
      error: undefined,
    })
    .mockRejectedValueOnce(new Error("unavailable"))
    .mockResolvedValueOnce({ data: page(20, 1), error: undefined });
  const { rerender } = render(
    <MemoryRouter>
      <ProjectUpdatesPage accessToken="token" principal={principal} personal />
    </MemoryRouter>,
  );
  expect(
    await screen.findByRole("heading", { name: "My activity" }),
  ).toBeVisible();
  await screen.findByText("Product 0");
  await userEvent.click(screen.getByRole("button", { name: "Load more" }));
  await screen.findByRole("alert");
  expect(screen.getByText("Product 0")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  await screen.findByText("Product 20");
  expect(personal.mock.calls[2][0]?.query).toEqual({ cursor: "older-mine" });
  expect(list).not.toHaveBeenCalled();
  list.mockResolvedValueOnce({ data: page(99, 1), error: undefined });
  rerender(view());
  await screen.findByText("Product 99");
  expect(screen.queryByText("Product 0")).toBeNull();
});
