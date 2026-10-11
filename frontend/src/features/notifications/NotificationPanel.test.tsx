import "@testing-library/jest-dom/vitest";

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getTranslationCommentAnchor,
  markNotificationReadByComment,
} from "../../api/client";
import type { CommentAnchorWindowResponse } from "../../api/client";
import { ExactCommentTarget } from "../translations/ExactCommentTarget";
import { NotificationPanel } from "./NotificationPanel";

vi.mock("../../api/client", () => ({
  getTranslationCommentAnchor: vi.fn(),
  markNotificationReadByComment: vi.fn(),
}));

const item = vi.hoisted(() => ({
  id: "notification-1",
  actor: { user_id: "author-1", display_name: "Author" },
  comment_status: "available" as const,
  created_at: "2026-09-30T19:00:00Z",
  is_read: false,
  key_excerpt: "hello",
  language: "it",
  originating_comment_id: "comment-1",
  product: { id: "product-1", name: "Product" },
  read_at: null,
  translation_group_id: "group-1",
}));

vi.mock("./NotificationShell", () => ({
  useNotificationShell: () => ({
    announcement: "",
    unreadCount: 1,
    status: "ready",
    recent: [item],
    stale: false,
    readingIds: new Set(),
    readErrorId: null,
    markRead: vi.fn(),
    refresh: vi.fn(),
  }),
}));

const anchorResponse: {
  data: CommentAnchorWindowResponse;
  error: undefined;
} = {
  data: {
    target_id: "comment-1",
    items: [
      {
        id: "comment-1",
        translation_group_id: "group-1",
        language: "it",
        status: "available",
        body: "Exact target",
        mentions: [],
        author: { id: "author-1", display_name: "Author" },
        current_version: 1,
        edited: false,
        created_at: "2026-09-30T19:00:00Z",
        updated_at: "2026-09-30T19:00:00Z",
        deleted_at: null,
        deleted_by: null,
      },
    ],
  },
  error: undefined,
};

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
  Object.defineProperty(HTMLElement.prototype, "hasPointerCapture", {
    configurable: true,
    value: () => false,
  });
  Object.defineProperty(HTMLElement.prototype, "releasePointerCapture", {
    configurable: true,
    value: vi.fn(),
  });
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({ matches: true }),
  });
  vi.mocked(getTranslationCommentAnchor).mockResolvedValue(anchorResponse);
  vi.mocked(markNotificationReadByComment).mockResolvedValue({
    data: {
      item: { ...item, is_read: true },
      unread_count: 0,
    },
    error: undefined,
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mount() {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <NotificationPanel />
      <Routes>
        <Route path="/" element={<h1>Workspace</h1>} />
        <Route
          path="/translations/group-1"
          element={
            <ExactCommentTarget
              accessToken="token"
              translationGroupId="group-1"
              language="it"
              commentId="comment-1"
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("NotificationPanel focus ownership", () => {
  it.each(["keyboard", "pointer"])(
    "retains exact-comment focus after %s menu navigation",
    async (mode) => {
      const user = userEvent.setup();
      mount();
      const bell = screen.getByRole("button", {
        name: "Notifications, 1 unread notification",
      });
      if (mode === "keyboard") {
        bell.focus();
        await user.keyboard("{Enter}");
      } else await user.click(bell);
      const notification = screen.getByRole("menuitem", {
        name: /Author.*Unread/,
      });
      if (mode === "keyboard") {
        notification.focus();
        await user.keyboard("{Enter}");
      } else await user.click(notification);
      const target = await screen.findByTestId("exact-comment-comment-1");
      await waitFor(() =>
        expect(screen.queryByRole("menu")).not.toBeInTheDocument(),
      );
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 10));
      });
      expect(target).toHaveFocus();
      expect(markNotificationReadByComment).toHaveBeenCalledTimes(1);

      bell.focus();
      await user.keyboard("{Enter}{Escape}");
      await waitFor(() => expect(bell).toHaveFocus());
    },
  );

  it("restores the bell while the destination loads, then focuses the ready comment", async () => {
    let resolveAnchor!: (value: typeof anchorResponse) => void;
    vi.mocked(getTranslationCommentAnchor).mockReturnValueOnce(
      new Promise<typeof anchorResponse>((resolve) => {
        resolveAnchor = resolve;
      }),
    );
    const user = userEvent.setup();
    mount();
    const bell = screen.getByRole("button", {
      name: "Notifications, 1 unread notification",
    });
    bell.focus();
    await user.keyboard("{Enter}");
    screen.getByRole("menuitem", { name: /Author.*Unread/ }).focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(bell).toHaveFocus());
    expect(markNotificationReadByComment).not.toHaveBeenCalled();
    await act(async () => resolveAnchor(anchorResponse));
    await waitFor(() =>
      expect(screen.getByTestId("exact-comment-comment-1")).toHaveFocus(),
    );
    expect(markNotificationReadByComment).toHaveBeenCalledTimes(1);
  });

  it("returns focus to the bell when the menu is dismissed without navigation", async () => {
    const user = userEvent.setup();
    mount();
    const bell = screen.getByRole("button", {
      name: "Notifications, 1 unread notification",
    });
    bell.focus();
    await user.keyboard("{Enter}");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(bell).toHaveFocus());
    expect(getTranslationCommentAnchor).not.toHaveBeenCalled();
  });
});
