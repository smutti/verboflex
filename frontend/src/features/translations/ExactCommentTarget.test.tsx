import "@testing-library/jest-dom/vitest";

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getTranslationCommentAnchor,
  markNotificationReadByComment,
  type TranslationCommentResponse,
} from "../../api/client";
import { ExactCommentTarget } from "./ExactCommentTarget";

vi.mock("../../api/client", () => ({
  getTranslationCommentAnchor: vi.fn(),
  markNotificationReadByComment: vi.fn(),
}));

const anchorMock = vi.mocked(getTranslationCommentAnchor);
const markReadMock = vi.mocked(markNotificationReadByComment);
const groupId = "opaque-group";
const targetId = "opaque-comment";

function comment(
  id: string,
  minute: number,
  overrides: Partial<TranslationCommentResponse> = {},
): TranslationCommentResponse {
  return {
    id,
    translation_group_id: groupId,
    language: "it",
    status: "available",
    body: `Body ${id}`,
    mentions: [],
    author: { id: `author-${id}`, display_name: `Author ${id}` },
    current_version: 1,
    edited: false,
    created_at: `2026-09-10T12:${String(minute).padStart(2, "0")}:00Z`,
    updated_at: `2026-09-10T12:${String(minute).padStart(2, "0")}:00Z`,
    deleted_at: null,
    deleted_by: null,
    ...overrides,
  };
}

function mount(
  props: Partial<React.ComponentProps<typeof ExactCommentTarget>> = {},
) {
  return render(
    <MemoryRouter>
      <ExactCommentTarget
        accessToken="access-token"
        translationGroupId={groupId}
        language="it"
        commentId={targetId}
        {...props}
      />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  anchorMock.mockReset();
  markReadMock.mockReset();
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({ matches: false }),
  });
});

afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

describe("ExactCommentTarget", () => {
  it.each([
    ["first", [comment(targetId, 1), comment("newer", 2)]],
    [
      "middle",
      [comment("older", 0), comment(targetId, 1), comment("newer", 2)],
    ],
    ["last", [comment("older", 0), comment(targetId, 1)]],
  ])(
    "renders and focuses a valid %s target from one bounded request",
    async (_position, items) => {
      anchorMock.mockResolvedValue({
        data: { target_id: targetId, items },
        error: undefined,
      });
      const onFocused = vi.fn();

      mount({ onFocused });

      const target = await screen.findByTestId(`exact-comment-${targetId}`);
      await waitFor(() => expect(target).toHaveFocus());
      expect(target).toHaveClass("ring-2");
      expect(target.scrollIntoView).toHaveBeenCalledWith({
        behavior: "smooth",
        block: "center",
      });
      expect(onFocused).toHaveBeenCalledTimes(1);
      expect(anchorMock).toHaveBeenCalledTimes(1);
      expect(anchorMock).toHaveBeenCalledWith(
        expect.objectContaining({
          auth: "access-token",
          path: { translation_group_id: groupId },
          query: { comment: targetId },
        }),
      );
    },
  );

  it("treats an authorized tombstone as the exact focusable target", async () => {
    anchorMock.mockResolvedValue({
      data: {
        target_id: targetId,
        items: [
          comment(targetId, 1, {
            status: "removed",
            body: null,
            mentions: [],
            deleted_at: "2026-09-10T13:00:00Z",
            deleted_by: "admin-id",
          }),
        ],
      },
      error: undefined,
    });

    mount();

    expect(
      await screen.findByText("Comment removed by an administrator"),
    ).toBeVisible();
    expect(screen.getByTestId(`exact-comment-${targetId}`)).toHaveFocus();
  });

  it.each([
    ["wrong anchor", { target_id: "other", items: [comment(targetId, 1)] }],
    ["missing target", { target_id: targetId, items: [comment("other", 1)] }],
    [
      "duplicate target",
      {
        target_id: targetId,
        items: [comment(targetId, 1), comment(targetId, 2)],
      },
    ],
    [
      "mixed group",
      {
        target_id: targetId,
        items: [
          comment(targetId, 1),
          comment("foreign", 2, { translation_group_id: "foreign-group" }),
        ],
      },
    ],
    [
      "mixed language",
      {
        target_id: targetId,
        items: [
          comment(targetId, 1),
          comment("foreign", 2, { language: "fr" }),
        ],
      },
    ],
    [
      "non chronological",
      {
        target_id: targetId,
        items: [comment(targetId, 2), comment("older", 1)],
      },
    ],
    [
      "over bound",
      {
        target_id: targetId,
        items: Array.from({ length: 12 }, (_, index) =>
          comment(index === 5 ? targetId : `comment-${index}`, index),
        ),
      },
    ],
    ["empty", { target_id: targetId, items: [] }],
  ])("rejects a %s response before rendering or focus", async (_case, data) => {
    anchorMock.mockResolvedValue({ data, error: undefined });
    const onFocused = vi.fn();

    mount({ onFocused });

    expect(await screen.findByText("Comment not available")).toBeVisible();
    expect(screen.queryByText(`Body ${targetId}`)).not.toBeInTheDocument();
    expect(onFocused).not.toHaveBeenCalled();
  });

  it("uses identical unavailable copy for malformed input and load failure", async () => {
    const first = mount({ commentId: "bad comment" });
    expect(await screen.findByText("Comment not available")).toBeVisible();
    expect(anchorMock).not.toHaveBeenCalled();
    expect(
      screen.getByRole("link", { name: "Back to notifications" }),
    ).toHaveAttribute("href", "/notifications");
    expect(screen.queryByText(/bad comment/i)).not.toBeInTheDocument();
    first.unmount();

    anchorMock.mockRejectedValue(new Error("private provider detail"));
    mount();
    expect(await screen.findByText("Comment not available")).toBeVisible();
    expect(screen.queryByText(/provider|private/i)).not.toBeInTheDocument();
  });

  it("clears only the static highlight after four seconds while focus remains", async () => {
    vi.useFakeTimers();
    anchorMock.mockResolvedValue({
      data: { target_id: targetId, items: [comment(targetId, 1)] },
      error: undefined,
    });

    mount();
    await act(async () => Promise.resolve());
    await act(async () => Promise.resolve());
    const target = screen.getByTestId(`exact-comment-${targetId}`);
    expect(target).toHaveFocus();
    expect(target).toHaveClass("ring-2");

    act(() => vi.advanceTimersByTime(4_000));

    expect(target).not.toHaveClass("ring-2");
    expect(target).toHaveFocus();
  });

  it("scrolls instantly when reduced motion is preferred", async () => {
    vi.mocked(window.matchMedia).mockReturnValue({
      matches: true,
    } as MediaQueryList);
    anchorMock.mockResolvedValue({
      data: { target_id: targetId, items: [comment(targetId, 1)] },
      error: undefined,
    });

    mount();

    const target = await screen.findByTestId(`exact-comment-${targetId}`);
    await waitFor(() => expect(target).toHaveFocus());
    expect(target.scrollIntoView).toHaveBeenCalledWith({
      behavior: "auto",
      block: "center",
    });
  });

  it("marks the principal-owned notification read exactly once and only after focus", async () => {
    anchorMock.mockResolvedValue({
      data: { target_id: targetId, items: [comment(targetId, 1)] },
      error: undefined,
    });
    markReadMock.mockImplementation(async () => {
      expect(document.activeElement).toHaveAttribute(
        "data-testid",
        `exact-comment-${targetId}`,
      );
      return {
        data: {
          item: {
            actor: { display_name: "Ada", user_id: "actor-id" },
            comment_status: "available",
            created_at: "2026-09-10T12:00:00Z",
            id: "notification-id",
            is_read: true,
            key_excerpt: "checkout.title",
            language: "it",
            originating_comment_id: targetId,
            product: { id: "product-id", name: "Product" },
            read_at: "2026-09-10T12:01:00Z",
            translation_group_id: groupId,
          },
          unread_count: 0,
        },
        error: undefined,
      };
    });
    const onNotificationStateChanged = vi.fn();

    mount({ onNotificationStateChanged });

    await waitFor(() => expect(markReadMock).toHaveBeenCalledTimes(1));
    expect(markReadMock).toHaveBeenCalledWith(
      expect.objectContaining({
        auth: "access-token",
        path: { comment_id: targetId },
      }),
    );
    expect(onNotificationStateChanged).toHaveBeenCalledTimes(1);
  });

  it("never marks read when the mounted target cannot receive focus", async () => {
    const focus = vi
      .spyOn(HTMLElement.prototype, "focus")
      .mockImplementation(() => undefined);
    anchorMock.mockResolvedValue({
      data: { target_id: targetId, items: [comment(targetId, 1)] },
      error: undefined,
    });

    mount();

    expect(await screen.findByText("Comment not available")).toBeVisible();
    expect(markReadMock).not.toHaveBeenCalled();
    focus.mockRestore();
  });

  it("keeps the focused comment visible when its read transition fails", async () => {
    anchorMock.mockResolvedValue({
      data: { target_id: targetId, items: [comment(targetId, 1)] },
      error: undefined,
    });
    markReadMock.mockRejectedValue(new Error("private read failure"));

    mount();

    expect(await screen.findByText(`Body ${targetId}`)).toBeVisible();
    expect(
      await screen.findByText("Notification status could not be updated"),
    ).toBeVisible();
    expect(screen.queryByText(/private read failure/i)).not.toBeInTheDocument();
  });
});
