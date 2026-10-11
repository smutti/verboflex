import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createTranslationComment,
  deleteTranslationComment,
  listTranslationComments,
  listTranslationCommentVersions,
  searchMentionUsers,
  updateTranslationComment,
  type RoleName,
  type TranslationCommentResponse,
  type TranslationCommentVersionResponse,
} from "../../api/client";
import { Discussion } from "./Discussion";

vi.mock("../../api/client", () => ({
  createTranslationComment: vi.fn(),
  deleteTranslationComment: vi.fn(),
  listTranslationComments: vi.fn(),
  listTranslationCommentVersions: vi.fn(),
  searchMentionUsers: vi.fn(),
  updateTranslationComment: vi.fn(),
}));

function comment(
  index: number,
  overrides: Partial<TranslationCommentResponse> = {},
): TranslationCommentResponse {
  return {
    id: `comment-${index}`,
    translation_group_id: "group-1",
    language: "it",
    author: { id: "author-1", display_name: "Ari <script>" },
    body: `Comment ${index}\nمرحبا 中文`,
    current_version: 2,
    status: "available",
    edited: true,
    mentions: [],
    created_at: `2026-09-${String(index).padStart(2, "0")}T10:00:00Z`,
    updated_at: `2026-09-${String(index).padStart(2, "0")}T11:00:00Z`,
    deleted_at: null,
    deleted_by: null,
    ...overrides,
  };
}

function version(
  index: number,
  body = `Version ${index}`,
): TranslationCommentVersionResponse {
  return {
    version: index,
    status: "available",
    body,
    actor: { id: "author-1", display_name: "Ari" },
    mentions: [],
    created_at: `2026-08-${String(index).padStart(2, "0")}T10:00:00Z`,
  };
}

function mount(role: RoleName = "viewer", userId = "reader-1") {
  return render(
    <Discussion
      accessToken="token"
      translationGroupId="group-1"
      language="it"
      principal={{ id: userId, roles: [role] }}
    />,
  );
}

beforeEach(() => {
  vi.mocked(searchMentionUsers).mockResolvedValue({
    data: [],
    error: undefined,
  } as never);
  vi.mocked(listTranslationComments).mockResolvedValue({
    data: { items: [], older_cursor: null },
    error: undefined,
  } as never);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Discussion recent and older collection", () => {
  it("renders the newest five in chronological order and prepends a validated older page", async () => {
    const recent = [2, 3, 4, 5, 6].map((index) => comment(index));
    vi.mocked(listTranslationComments)
      .mockResolvedValueOnce({
        data: { items: recent, older_cursor: "older" },
        error: undefined,
      } as never)
      .mockResolvedValueOnce({
        data: { items: [comment(1)], older_cursor: null },
        error: undefined,
      } as never);
    mount();

    const list = await screen.findByRole("list", { name: "Comments" });
    expect(
      within(list)
        .getAllByRole("article")
        .map((item) => item.id),
    ).toEqual(recent.map((item) => `comment-${item.id}`));
    const earlierButton = screen.getByRole("button", {
      name: "Show earlier comments",
    });
    earlierButton.focus();
    await userEvent.click(earlierButton);
    await waitFor(() =>
      expect(
        within(list)
          .getAllByRole("article")
          .map((item) => item.id),
      ).toEqual([
        "comment-comment-1",
        ...recent.map((item) => `comment-${item.id}`),
      ]),
    );
    expect(listTranslationComments).toHaveBeenLastCalledWith(
      expect.objectContaining({
        auth: "token",
        path: { translation_group_id: "group-1" },
        query: { cursor: "older" },
        signal: expect.any(AbortSignal),
      }),
    );
    expect(document.activeElement).toBe(
      document.getElementById("comment-comment-1"),
    );
  });

  it("uses the stable comment id to order comments with equal timestamps", async () => {
    const createdAt = "2026-09-01T10:00:00Z";
    vi.mocked(listTranslationComments).mockResolvedValue({
      data: {
        items: [
          comment(1, { id: "comment-a", created_at: createdAt }),
          comment(2, { id: "comment-b", created_at: createdAt }),
        ],
        older_cursor: null,
      },
      error: undefined,
    } as never);
    mount();
    const list = await screen.findByRole("list", { name: "Comments" });
    expect(
      within(list)
        .getAllByRole("article")
        .map((item) => item.id),
    ).toEqual(["comment-comment-a", "comment-comment-b"]);
  });

  it("keeps the last complete discussion when an older page is corrupt and supports recovery", async () => {
    const retained = comment(2);
    vi.mocked(listTranslationComments)
      .mockResolvedValueOnce({
        data: { items: [retained], older_cursor: "older" },
        error: undefined,
      } as never)
      .mockResolvedValueOnce({
        data: {
          items: [comment(1, { translation_group_id: "foreign" })],
          older_cursor: "older",
        },
        error: undefined,
      } as never)
      .mockResolvedValueOnce({
        data: { items: [comment(1)], older_cursor: null },
        error: undefined,
      } as never);
    mount();
    expect(await screen.findByText(/Comment 2/)).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Show earlier comments" }),
    );
    expect(
      await screen.findByText("Earlier comments could not be loaded"),
    ).toBeVisible();
    expect(screen.getByText(/Comment 2/)).toBeVisible();
    expect(screen.queryByText(/Comment 1/)).toBeNull();
    await userEvent.click(
      screen.getByRole("button", { name: "Retry earlier comments" }),
    );
    expect(await screen.findByText(/Comment 1/)).toBeVisible();
  });

  it("uses exact loading, author-role empty, viewer empty, and initial recovery states", async () => {
    let resolve!: (value: unknown) => void;
    vi.mocked(listTranslationComments).mockReturnValueOnce(
      new Promise((done) => {
        resolve = done;
      }) as never,
    );
    const view = mount("translator", "author-1");
    expect(screen.getByText("Loading comments")).toBeVisible();
    resolve({ data: { items: [], older_cursor: null }, error: undefined });
    expect(await screen.findByText("No comments yet")).toBeVisible();
    view.unmount();

    vi.mocked(listTranslationComments)
      .mockRejectedValueOnce(new Error("private"))
      .mockResolvedValueOnce({
        data: { items: [], older_cursor: null },
        error: undefined,
      } as never);
    mount("viewer");
    expect(
      await screen.findByText("Comments could not be loaded"),
    ).toBeVisible();

    expect(document.body).not.toHaveTextContent("private");
    await userEvent.click(
      screen.getByRole("button", { name: "Reload comments" }),
    );
    expect(await screen.findByText("No comments yet")).toBeVisible();
  });
});

describe("Discussion lifecycle authority", () => {
  it.each<RoleName>([
    "admin",
    "product_manager_reviewer",
    "translator",
    "viewer",
  ])(
    "allows %s to view live edit history without granting unrelated mutations",
    async (role) => {
      vi.mocked(listTranslationComments).mockResolvedValue({
        data: { items: [comment(1)], older_cursor: null },
        error: undefined,
      } as never);
      vi.mocked(listTranslationCommentVersions).mockResolvedValue({
        data: { items: [version(1), version(2)], next_cursor: null },
        error: undefined,
      } as never);
      mount(role);
      await userEvent.click(
        await screen.findByRole("button", { name: "View edit history" }),
      );
      const history = await screen.findByRole("region", {
        name: "Edit history for comment 1",
      });
      expect(
        within(history)
          .getAllByRole("listitem")
          .map((item) => item.textContent),
      ).toEqual([
        expect.stringContaining("Version 1"),
        expect.stringContaining("Version 2"),
      ]);
      expect(screen.queryByRole("button", { name: "Edit comment" })).toBeNull();
      expect(
        Boolean(screen.queryByRole("button", { name: "Delete comment" })),
      ).toBe(role === "admin");
    },
  );

  it("edits only the current author's comment non-optimistically and preserves local text on conflict", async () => {
    const live = comment(1);
    vi.mocked(listTranslationComments).mockResolvedValue({
      data: { items: [live], older_cursor: null },
      error: undefined,
    } as never);
    vi.mocked(updateTranslationComment).mockResolvedValue({
      data: undefined,
      error: {
        detail: "Comment version conflict",
        attempted_body: "My local edit",
        attempted_version: 2,
        latest: comment(1, { body: "Newer server body", current_version: 3 }),
      },
      response: new Response(null, { status: 409 }),
    } as never);
    mount("translator", "author-1");
    await userEvent.click(
      await screen.findByRole("button", { name: "Edit comment" }),
    );
    const editor = screen.getByRole("textbox", { name: "Edit comment text" });
    await userEvent.clear(editor);
    await userEvent.type(editor, "My local edit");
    expect(screen.getByText(/Comment 1/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Save comment" }));
    expect(
      await screen.findByText("Comment changed in another session"),
    ).toBeVisible();
    expect(editor).toHaveValue("My local edit");
    expect(screen.getByText("Newer server body")).toBeVisible();
    expect(updateTranslationComment).toHaveBeenCalledWith(
      expect.objectContaining({
        body: { body: "My local edit", expected_version: 2, mentions: [] },
      }),
    );
  });

  it("replaces an edited comment only after server success and restores trigger focus", async () => {
    const live = comment(1);
    const saved = comment(1, { body: "Saved text", current_version: 3 });
    let resolve!: (value: unknown) => void;
    vi.mocked(listTranslationComments).mockResolvedValue({
      data: { items: [live], older_cursor: null },
      error: undefined,
    } as never);
    vi.mocked(updateTranslationComment).mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }) as never,
    );
    mount("translator", "author-1");
    await userEvent.click(
      await screen.findByRole("button", { name: "Edit comment" }),
    );
    const editor = screen.getByRole("textbox", { name: "Edit comment text" });
    await userEvent.clear(editor);
    await userEvent.type(editor, "Saved text");
    await userEvent.click(screen.getByRole("button", { name: "Save comment" }));
    expect(screen.getByText(/Comment 1/)).toBeVisible();
    resolve({ data: saved, error: undefined });
    expect(
      await screen.findByText("Saved text", { selector: "p" }),
    ).toBeVisible();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Edit comment" }),
      ).toHaveFocus(),
    );
  });

  it("lets only an administrator confirm deletion and replaces success with the server tombstone", async () => {
    const live = comment(1);
    const removed = comment(1, {
      body: null,
      status: "removed",
      mentions: [],
      current_version: 3,
      edited: true,
      deleted_at: "2026-09-09T12:00:00Z",
      deleted_by: "admin-1",
    });
    vi.mocked(listTranslationComments).mockResolvedValue({
      data: { items: [live], older_cursor: null },
      error: undefined,
    } as never);
    vi.mocked(deleteTranslationComment).mockResolvedValue({
      data: removed,
      error: undefined,
    } as never);
    mount("admin", "admin-1");
    await userEvent.click(
      await screen.findByRole("button", { name: "Delete comment" }),
    );
    const dialog = screen.getByRole("alertdialog", {
      name: "Delete this comment?",
    });
    expect(dialog).toHaveTextContent(
      "The comment text will no longer be visible. Its audit record and existing notification links will remain.",
    );
    expect(
      within(dialog).getByRole("button", { name: "Keep comment" }),
    ).toBeVisible();
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Delete comment" }),
    );
    const tombstone = await screen.findByText(
      "Comment removed by an administrator",
    );
    expect(tombstone.closest("article")).toHaveAttribute(
      "id",
      "comment-comment-1",
    );
    expect(document.body).not.toHaveTextContent("مرحبا 中文");
    expect(
      screen.queryByRole("button", { name: "View edit history" }),
    ).toBeNull();
  });

  it("never reveals deleted bodies or version history to non-admin readers", async () => {
    vi.mocked(listTranslationComments).mockResolvedValue({
      data: {
        items: [
          comment(1, {
            body: null,
            status: "removed",
            mentions: [],
            deleted_at: "2026-09-09T12:00:00Z",
          }),
        ],
        older_cursor: null,
      },
      error: undefined,
    } as never);
    mount("product_manager_reviewer");
    expect(
      await screen.findByText("Comment removed by an administrator"),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "View edit history" }),
    ).toBeNull();
    expect(listTranslationCommentVersions).not.toHaveBeenCalled();
    expect(document.body).not.toHaveTextContent("مرحبا 中文");
  });

  it("posts structured comments non-optimistically, preserves failures, and focuses server success", async () => {
    const created = comment(9, {
      id: "created-comment",
      author: { id: "author-1", display_name: "Ari" },
      body: "Please check",
      current_version: 1,
      edited: false,
      created_at: "2026-09-09T10:00:00Z",
      updated_at: "2026-09-09T10:00:00Z",
    });
    vi.mocked(createTranslationComment)
      .mockRejectedValueOnce(new Error("private"))
      .mockResolvedValueOnce({ data: created, error: undefined } as never);
    mount("translator", "author-1");
    const composer = await screen.findByRole("textbox", {
      name: "Add a comment",
    });
    await userEvent.type(composer, "Please check");
    await userEvent.click(screen.getByRole("button", { name: "Post comment" }));
    expect(await screen.findByText("Comment was not posted")).toBeVisible();
    expect(composer).toHaveValue("Please check");
    await userEvent.click(screen.getByRole("button", { name: "Post comment" }));
    const article = await screen.findByRole("article");
    expect(article).toHaveAttribute("id", "comment-created-comment");
    await waitFor(() => expect(article).toHaveFocus());
    expect(composer).toHaveValue("");
    expect(createTranslationComment).toHaveBeenLastCalledWith(
      expect.objectContaining({
        body: { body: "Please check", mentions: [] },
      }),
    );
  });
});

describe("discussion draft state contract", () => {
  it("reports composition, failure, submission and explicit discard without losing the body", async () => {
    const onDraftStateChange = vi.fn();
    vi.mocked(createTranslationComment).mockRejectedValue(new Error("offline"));
    const view = render(
      <Discussion
        accessToken="token"
        translationGroupId="group-1"
        language="it"
        principal={{ id: "author-1", roles: ["translator"] }}
        onDraftStateChange={onDraftStateChange}
      />,
    );
    await userEvent.type(
      await screen.findByRole("textbox", { name: "Add a comment" }),
      "Unsent text",
    );
    expect(onDraftStateChange).toHaveBeenLastCalledWith({
      dirty: true,
      submitting: false,
    });
    await userEvent.click(screen.getByRole("button", { name: "Post comment" }));
    expect(await screen.findByText("Comment was not posted")).toBeVisible();
    expect(onDraftStateChange).toHaveBeenCalledWith({
      dirty: true,
      submitting: true,
    });
    expect(onDraftStateChange).toHaveBeenLastCalledWith({
      dirty: true,
      submitting: false,
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Discard comment draft" }),
    );
    expect(screen.getByRole("textbox", { name: "Add a comment" })).toHaveValue(
      "",
    );
    expect(onDraftStateChange).toHaveBeenLastCalledWith({
      dirty: false,
      submitting: false,
    });
    view.unmount();
    expect(onDraftStateChange).toHaveBeenLastCalledWith({
      dirty: false,
      submitting: false,
    });
  });
  it("tracks changed existing comments and resets private state on identity replacement", async () => {
    vi.mocked(listTranslationComments).mockResolvedValue({
      data: { items: [comment(1)], older_cursor: null },
    } as never);
    const onDraftStateChange = vi.fn();
    const props = {
      accessToken: "token",
      translationGroupId: "group-1",
      language: "it",
      principal: { id: "author-1", roles: ["translator" as const] },
      onDraftStateChange,
    };
    const view = render(<Discussion {...props} />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Edit comment" }),
    );
    expect(onDraftStateChange).toHaveBeenLastCalledWith({
      dirty: false,
      submitting: false,
    });
    await userEvent.type(
      screen.getByRole("textbox", { name: "Edit comment text" }),
      " changed",
    );
    expect(onDraftStateChange).toHaveBeenLastCalledWith({
      dirty: true,
      submitting: false,
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Stop editing comment" }),
    );
    expect(onDraftStateChange).toHaveBeenLastCalledWith({
      dirty: false,
      submitting: false,
    });
    await userEvent.type(
      screen.getByRole("textbox", { name: "Add a comment" }),
      "Private draft",
    );
    view.rerender(
      <Discussion
        {...props}
        principal={{ id: "second-user", roles: ["translator"] }}
      />,
    );
    expect(screen.getByRole("textbox", { name: "Add a comment" })).toHaveValue(
      "",
    );
    expect(onDraftStateChange).toHaveBeenLastCalledWith({
      dirty: false,
      submitting: false,
    });
  });
});
