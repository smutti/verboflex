import "@testing-library/jest-dom/vitest";

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getUnreadNotificationCount,
  listRecentNotifications,
  streamNotificationInvalidations,
  type NotificationInvalidationEventResponse,
  type NotificationItemResponse,
} from "../../api/client";
import { NotificationShell, useNotificationShell } from "./NotificationShell";

vi.mock("../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/client")>();
  return {
    ...original,
    getUnreadNotificationCount: vi.fn(),
    listRecentNotifications: vi.fn(),
    streamNotificationInvalidations: vi.fn(),
  };
});

const countMock = vi.mocked(getUnreadNotificationCount);
const recentMock = vi.mocked(listRecentNotifications);
const streamMock = vi.mocked(streamNotificationInvalidations);

function notification(id: string, isRead = false): NotificationItemResponse {
  return {
    id,
    actor: { user_id: `actor-${id}`, display_name: `Actor ${id}` },
    comment_status: "available",
    created_at: "2026-09-10T10:00:00Z",
    is_read: isRead,
    key_excerpt: `key.${id}`,
    language: "it",
    originating_comment_id: `comment-${id}`,
    product: { id: `product-${id}`, name: `Product ${id}` },
    read_at: isRead ? "2026-09-10T10:01:00Z" : null,
    translation_group_id: `group-${id}`,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function controlledStream() {
  const queued: Array<NotificationInvalidationEventResponse | unknown> = [];
  const waiting: Array<(value: IteratorResult<unknown>) => void> = [];
  let closed = false;
  const stream = {
    [Symbol.asyncIterator]() {
      return this;
    },
    next: vi.fn(() => {
      if (queued.length > 0) {
        return Promise.resolve({ done: false, value: queued.shift() });
      }
      if (closed) {
        return Promise.resolve({ done: true, value: undefined });
      }
      return new Promise((resolve) => waiting.push(resolve));
    }),
    return: vi.fn(async () => {
      closed = true;
      while (waiting.length > 0) {
        waiting.shift()?.({ done: true, value: undefined });
      }
      return { done: true, value: undefined };
    }),
    throw: vi.fn(async (error?: unknown) => {
      throw error;
    }),
  } as unknown as AsyncGenerator<unknown, void, unknown>;
  return {
    stream,
    emit(value: unknown) {
      const resolve = waiting.shift();
      if (resolve) {
        resolve({ done: false, value });
      } else {
        queued.push(value);
      }
    },
    close() {
      closed = true;
      while (waiting.length > 0) {
        waiting.shift()?.({ done: true, value: undefined });
      }
    },
  };
}

function Probe() {
  const notifications = useNotificationShell();
  return (
    <>
      <output data-testid="status">{notifications.status}</output>
      <output data-testid="count">{notifications.unreadCount}</output>
      <output data-testid="recent">
        {notifications.recent.map(({ id }) => id).join(",")}
      </output>
      <output data-testid="stale">{String(notifications.stale)}</output>
      <div aria-live="polite">{notifications.announcement}</div>
      <label>
        Active editor
        <input defaultValue="kept text" />
      </label>
    </>
  );
}

function renderShell(accessToken = "token-a", principalId = "principal-a") {
  return render(
    <NotificationShell accessToken={accessToken} principalId={principalId}>
      <Probe />
    </NotificationShell>,
  );
}

async function flushAsync() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "visible",
  });
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    value: true,
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("NotificationShell", () => {
  it("owns one generated authenticated stream and hydrates only from durable HTTP projections", async () => {
    const live = controlledStream();
    countMock.mockResolvedValue({
      data: { unread_count: 1 },
      error: undefined,
    });
    recentMock.mockResolvedValue({
      data: { items: [notification("newest")], next_cursor: null },
      error: undefined,
    });
    streamMock.mockResolvedValue({ stream: live.stream } as never);

    renderShell();

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("ready"),
    );
    expect(screen.getByTestId("count")).toHaveTextContent("1");
    expect(screen.getByTestId("recent")).toHaveTextContent("newest");
    expect(streamMock).toHaveBeenCalledOnce();
    expect(streamMock).toHaveBeenCalledWith(
      expect.objectContaining({
        auth: "token-a",
        signal: expect.any(AbortSignal),
        sseMaxRetryAttempts: 5,
      }),
    );
    expect(countMock).toHaveBeenCalledWith(
      expect.objectContaining({
        auth: "token-a",
        signal: expect.any(AbortSignal),
      }),
    );
    expect(recentMock).toHaveBeenCalledWith(
      expect.objectContaining({
        auth: "token-a",
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("ignores malformed invalidations and coalesces exact new-count announcements without moving focus", async () => {
    const live = controlledStream();
    countMock
      .mockResolvedValueOnce({ data: { unread_count: 0 }, error: undefined })
      .mockResolvedValueOnce({ data: { unread_count: 1 }, error: undefined })
      .mockResolvedValueOnce({ data: { unread_count: 3 }, error: undefined });
    recentMock
      .mockResolvedValueOnce({
        data: { items: [], next_cursor: null },
        error: undefined,
      })
      .mockResolvedValueOnce({
        data: { items: [notification("one")], next_cursor: null },
        error: undefined,
      })
      .mockResolvedValueOnce({
        data: {
          items: [
            notification("three"),
            notification("two"),
            notification("one"),
          ],
          next_cursor: null,
        },
        error: undefined,
      });
    streamMock.mockResolvedValue({ stream: live.stream } as never);
    renderShell();
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("ready"),
    );
    const editor = screen.getByRole("textbox", { name: "Active editor" });
    editor.focus();

    live.emit({ id: "bad", kind: "notification_with_content", body: "secret" });
    await flushAsync();
    expect(countMock).toHaveBeenCalledOnce();

    live.emit({ id: "event-1", kind: "notifications_changed" });
    await flushAsync();
    live.emit({ id: "event-2", kind: "notifications_changed" });
    await flushAsync();
    await act(async () => vi.advanceTimersByTimeAsync(1_000));

    expect(screen.getByText("3 new notifications")).toBeVisible();
    expect(editor).toHaveFocus();
    expect(editor).toHaveValue("kept text");
  });

  it("polls every 30 seconds only while visible and refetches on visible wake and online recovery", async () => {
    let onSseError: ((error: unknown) => void) | undefined;
    const live = controlledStream();
    streamMock.mockImplementation(async (options) => {
      onSseError = options?.onSseError;
      return { stream: live.stream } as never;
    });
    countMock.mockResolvedValue({
      data: { unread_count: 0 },
      error: undefined,
    });
    recentMock.mockResolvedValue({
      data: { items: [], next_cursor: null },
      error: undefined,
    });
    renderShell();
    await waitFor(() => expect(countMock).toHaveBeenCalledOnce());

    act(() => onSseError?.(new Error("transport detail must stay hidden")));
    await act(async () => vi.advanceTimersByTimeAsync(30_000));
    expect(countMock).toHaveBeenCalledTimes(2);

    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    expect(countMock).toHaveBeenCalledTimes(2);

    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    await flushAsync();
    expect(countMock).toHaveBeenCalledTimes(3);

    act(() => window.dispatchEvent(new Event("online")));
    await flushAsync();
    expect(countMock).toHaveBeenCalledTimes(4);
    expect(screen.queryByText(/transport detail/i)).not.toBeInTheDocument();
  });

  it("fences late prior-principal responses and aborts every owned resource on token change and unmount", async () => {
    const firstCount = deferred<{
      data: { unread_count: number };
      error: undefined;
    }>();
    const firstRecent = deferred<{
      data: { items: NotificationItemResponse[]; next_cursor: null };
      error: undefined;
    }>();
    const firstLive = controlledStream();
    const secondLive = controlledStream();
    const streamSignals: AbortSignal[] = [];
    streamMock.mockImplementation(async (options) => {
      streamSignals.push(options?.signal as AbortSignal);
      return {
        stream:
          streamSignals.length === 1 ? firstLive.stream : secondLive.stream,
      } as never;
    });
    countMock
      .mockReturnValueOnce(firstCount.promise as never)
      .mockResolvedValueOnce({ data: { unread_count: 2 }, error: undefined });
    recentMock
      .mockReturnValueOnce(firstRecent.promise as never)
      .mockResolvedValueOnce({
        data: { items: [notification("current")], next_cursor: null },
        error: undefined,
      });

    const view = renderShell("token-old", "principal-old");
    await waitFor(() => expect(streamMock).toHaveBeenCalledOnce());
    view.rerender(
      <NotificationShell accessToken="token-new" principalId="principal-new">
        <Probe />
      </NotificationShell>,
    );
    await waitFor(() => expect(streamMock).toHaveBeenCalledTimes(2));
    expect(streamSignals[0].aborted).toBe(true);
    await waitFor(() =>
      expect(screen.getByTestId("recent")).toHaveTextContent("current"),
    );

    await act(async () => {
      firstCount.resolve({ data: { unread_count: 99 }, error: undefined });
      firstRecent.resolve({
        data: { items: [notification("private-old")], next_cursor: null },
        error: undefined,
      });
    });
    expect(screen.getByTestId("count")).toHaveTextContent("2");
    expect(screen.getByTestId("recent")).not.toHaveTextContent("private-old");

    view.unmount();
    expect(streamSignals[1].aborted).toBe(true);
  });

  it("retains the last complete list as stale when authoritative refresh fails", async () => {
    const live = controlledStream();
    countMock
      .mockResolvedValueOnce({ data: { unread_count: 1 }, error: undefined })
      .mockResolvedValueOnce({
        data: undefined,
        error: { detail: "unavailable" } as never,
      });
    recentMock
      .mockResolvedValueOnce({
        data: { items: [notification("retained")], next_cursor: null },
        error: undefined,
      })
      .mockResolvedValueOnce({
        data: undefined,
        error: { detail: "unavailable" } as never,
      });
    streamMock.mockResolvedValue({ stream: live.stream } as never);
    renderShell();
    await waitFor(() =>
      expect(screen.getByTestId("recent")).toHaveTextContent("retained"),
    );

    live.emit({ id: "event-1", kind: "notifications_changed" });
    await flushAsync();

    expect(screen.getByTestId("status")).toHaveTextContent("error");
    expect(screen.getByTestId("stale")).toHaveTextContent("true");
    expect(screen.getByTestId("recent")).toHaveTextContent("retained");
    expect(screen.getByTestId("count")).toHaveTextContent("1");
  });
});
