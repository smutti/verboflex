import "@testing-library/jest-dom/vitest";

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  listNotifications,
  listTranslationOptions,
  markNotificationRead,
  type NotificationItemResponse,
  type NotificationPageResponse,
  type NotificationReadResponse,
} from "../../api/client";
import { NotificationCenterPage } from "./NotificationCenterPage";

vi.mock("../../api/client", () => ({
  listNotifications: vi.fn(),
  listTranslationOptions: vi.fn(),
  markNotificationRead: vi.fn(),
}));

const listNotificationsMock = vi.mocked(listNotifications);
const listTranslationOptionsMock = vi.mocked(listTranslationOptions);
const markNotificationReadMock = vi.mocked(markNotificationRead);

function notification(
  id: string,
  overrides: Partial<NotificationItemResponse> = {},
): NotificationItemResponse {
  return {
    actor: { display_name: "Ada Reviewer", user_id: `actor-${id}` },
    comment_status: "available",
    created_at: "2026-09-10T12:00:00Z",
    id,
    is_read: false,
    key_excerpt: `checkout.title.${id}`,
    language: "it",
    originating_comment_id: `comment-${id}`,
    product: { id: "product-a", name: "Product A" },
    read_at: null,
    translation_group_id: `group-${id}`,
    ...overrides,
  };
}

function renderCenter() {
  return render(
    <MemoryRouter>
      <NotificationCenterPage
        accessToken="principal-token"
        principalId="principal-a"
      />
    </MemoryRouter>,
  );
}

describe("NotificationCenterPage", () => {
  beforeEach(() => {
    Object.defineProperties(HTMLElement.prototype, {
      hasPointerCapture: { configurable: true, value: () => false },
      releasePointerCapture: { configurable: true, value: () => undefined },
      setPointerCapture: { configurable: true, value: () => undefined },
      scrollIntoView: { configurable: true, value: () => undefined },
    });
    listNotificationsMock.mockReset();
    listTranslationOptionsMock.mockReset();
    markNotificationReadMock.mockReset();
    listTranslationOptionsMock.mockResolvedValue({
      data: {
        products: [
          { id: "product-a", name: "Product A" },
          { id: "product-b", name: "Product B" },
        ],
        languages: [],
      },
      error: undefined,
    });
  });

  afterEach(cleanup);

  it("loads a principal-owned 25-item all page in server order", async () => {
    const items = Array.from({ length: 25 }, (_, index) =>
      notification(`notification-${index + 1}`),
    );
    listNotificationsMock.mockResolvedValue({
      data: { items, next_cursor: "page-2" },
      error: undefined,
    });

    renderCenter();

    expect(screen.getByText("Loading notifications")).toBeVisible();
    expect(
      await screen.findByRole("heading", { name: "Notifications" }),
    ).toBeVisible();
    expect(await screen.findAllByRole("article")).toHaveLength(25);
    expect(screen.getAllByRole("article")[0]).toHaveTextContent(
      "checkout.title.notification-1",
    );
    expect(listNotificationsMock).toHaveBeenCalledWith({
      auth: "principal-token",
      query: { cursor: null, product_id: null, view: "all" },
      signal: expect.any(AbortSignal),
    });
    expect(
      screen.getByRole("button", { name: "Load more notifications" }),
    ).toBeVisible();
  });

  it("keeps filters usable after an initial failure and retries in place", async () => {
    listNotificationsMock
      .mockRejectedValueOnce(new Error("private diagnostic"))
      .mockResolvedValueOnce({
        data: { items: [], next_cursor: null },
        error: undefined,
      });
    const user = userEvent.setup();

    renderCenter();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Notifications could not be loaded");
    expect(screen.getByRole("tab", { name: "All" })).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Product" })).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Reload notifications" }),
    );
    expect(await screen.findByText("No notifications yet")).toBeVisible();
    expect(screen.queryByText("private diagnostic")).not.toBeInTheDocument();
  });

  it("preserves valid rows when a duplicate or non-progressing page arrives", async () => {
    const firstPage = Array.from({ length: 25 }, (_, index) =>
      notification(`notification-${index + 1}`),
    );
    listNotificationsMock
      .mockResolvedValueOnce({
        data: { items: firstPage, next_cursor: "page-2" },
        error: undefined,
      })
      .mockResolvedValueOnce({
        data: {
          items: [notification("notification-25")],
          next_cursor: "page-2",
        },
        error: undefined,
      });
    const user = userEvent.setup();

    renderCenter();
    expect(await screen.findAllByRole("article")).toHaveLength(25);
    await user.click(
      screen.getByRole("button", { name: "Load more notifications" }),
    );

    expect(
      await screen.findByText("More notifications could not be loaded"),
    ).toBeVisible();
    expect(screen.getAllByRole("article")).toHaveLength(25);
    expect(
      screen.getByRole("button", { name: "Retry loading more" }),
    ).toBeVisible();
  });

  it("appends the twenty-sixth equal-time item without reordering", async () => {
    const firstPage = Array.from({ length: 25 }, (_, index) =>
      notification(`notification-${index + 1}`),
    );
    listNotificationsMock
      .mockResolvedValueOnce({
        data: { items: firstPage, next_cursor: "page-2" },
        error: undefined,
      })
      .mockResolvedValueOnce({
        data: { items: [notification("notification-26")], next_cursor: null },
        error: undefined,
      });
    const user = userEvent.setup();

    renderCenter();
    expect(await screen.findAllByRole("article")).toHaveLength(25);
    await user.click(
      screen.getByRole("button", { name: "Load more notifications" }),
    );

    expect(await screen.findAllByRole("article")).toHaveLength(26);
    expect(screen.getAllByRole("article")[25]).toHaveTextContent(
      "checkout.title.notification-26",
    );
    expect(listNotificationsMock).toHaveBeenLastCalledWith({
      auth: "principal-token",
      query: { cursor: "page-2", product_id: null, view: "all" },
      signal: expect.any(AbortSignal),
    });
  });

  it("reloads exact unread and authorized-product filters", async () => {
    listNotificationsMock.mockResolvedValue({
      data: { items: [], next_cursor: null },
      error: undefined,
    });
    const user = userEvent.setup();

    renderCenter();
    expect(await screen.findByText("No notifications yet")).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "Unread" }));
    expect(await screen.findByText("You're all caught up")).toBeVisible();
    await user.click(screen.getByRole("combobox", { name: "Product" }));
    await user.click(await screen.findByRole("option", { name: "Product B" }));

    await waitFor(() =>
      expect(listNotificationsMock).toHaveBeenLastCalledWith({
        auth: "principal-token",
        query: { cursor: null, product_id: "product-b", view: "unread" },
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("discards a late page from a superseded filter generation", async () => {
    type Success = {
      data: NotificationPageResponse;
      request: Request;
      response: Response;
    };
    let resolveAll!: (value: Success) => void;
    listNotificationsMock
      .mockReturnValueOnce(
        new Promise<Success>((resolve) => {
          resolveAll = resolve;
        }),
      )
      .mockResolvedValueOnce({
        data: { items: [notification("unread-fresh")], next_cursor: null },
        error: undefined,
      });
    const user = userEvent.setup();

    renderCenter();
    await user.click(screen.getByRole("tab", { name: "Unread" }));
    expect(await screen.findByRole("article")).toHaveTextContent(
      "checkout.title.unread-fresh",
    );
    await act(async () => {
      resolveAll({
        data: { items: [notification("late-all")], next_cursor: null },
        request: new Request("http://localhost/api/v1/notifications"),
        response: new Response(null, { status: 200 }),
      });
    });

    expect(
      screen.queryByText("checkout.title.late-all"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("checkout.title.unread-fresh")).toBeVisible();
  });

  it("marks one item read only after a fresh successful response", async () => {
    const unread = notification("notification-1");
    let resolveRead!: (value: {
      data: NotificationReadResponse;
      request: Request;
      response: Response;
    }) => void;
    markNotificationReadMock.mockReturnValue(
      new Promise<{
        data: NotificationReadResponse;
        request: Request;
        response: Response;
      }>((resolve) => {
        resolveRead = resolve;
      }),
    );
    listNotificationsMock.mockResolvedValue({
      data: { items: [unread], next_cursor: null },
      error: undefined,
    });
    const user = userEvent.setup();

    renderCenter();
    const readButton = await screen.findByRole("button", {
      name: "Mark as read",
    });
    await user.click(readButton);
    expect(readButton).toHaveTextContent("Marking as read");

    await act(async () => {
      resolveRead({
        data: {
          item: {
            ...unread,
            is_read: true,
            read_at: "2026-09-10T12:01:00Z",
          },
          unread_count: 0,
        },
        request: new Request(
          "http://localhost/api/v1/notifications/notification-1/read",
        ),
        response: new Response(null, { status: 200 }),
      });
    });

    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Mark as read" }),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Notification marked as read",
    );
  });

  it("renders removed targets without a link or deleted comment body", async () => {
    listNotificationsMock.mockResolvedValue({
      data: {
        items: [
          notification("removed", {
            comment_status: "removed",
            key_excerpt: "retained.safe.key",
          }),
        ],
        next_cursor: null,
      },
      error: undefined,
    });

    renderCenter();

    const row = await screen.findByRole("article");
    expect(row).toHaveTextContent("Comment not available");
    expect(row).not.toHaveTextContent("deleted body");
    expect(row.querySelector("a")).toBeNull();
  });
});
