import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MemoryRouter,
  Outlet,
  Route,
  Routes,
  RouterProvider,
  createMemoryRouter,
} from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getTranslationCommentAnchor,
  getTranslationCodeContext,
  listTranslationScreenshots,
  getTranslationGroup,
  listTranslationComments,
  listTranslationReviewActivity,
  markNotificationReadByComment,
  putTranslationConstraint,
  saveTranslationProposal,
  transitionTranslationProposal,
  type TranslationGroupDetailResponse,
  type ReviewActivityResponse,
  type RoleName,
} from "../../api/client";
import { TranslationDetailPage } from "./TranslationDetailPage";
import { TranslationsWorkspace } from "./TranslationsWorkspace";
import { consumeSubmissionEntry } from "../change-sets/submissionEntry";
import { DirtyFormNavigationProvider } from "../../components/navigation/DirtyFormNavigationGuard";

vi.mock("../../api/client", () => ({
  getTranslationCodeContext: vi.fn(),
  listTranslationScreenshots: vi.fn(),
  getTranslationSuggestions: vi.fn().mockResolvedValue({ data: { items: [] } }),
  resolveTranslationSuggestion: vi.fn(),
  matchGlossaryTerms: vi
    .fn()
    .mockResolvedValue({ data: { items: [], truncated: false } }),
  getTranslationCommentAnchor: vi.fn(),
  getTranslationGroup: vi.fn(),
  putTranslationConstraint: vi.fn(),
  deleteTranslationConstraint: vi.fn(),
  saveTranslationProposal: vi.fn(),
  transitionTranslationProposal: vi.fn(),
  listTranslationReviewActivity: vi.fn(),
  markNotificationReadByComment: vi.fn(),
  listTranslationComments: vi.fn(),
  listTranslationCommentVersions: vi.fn(),
  updateTranslationComment: vi.fn(),
  deleteTranslationComment: vi.fn(),
  createTranslationComment: vi.fn(),
  searchMentionUsers: vi.fn(),
}));

export function detailFixture(): TranslationGroupDetailResponse {
  return {
    id: "opaque-group",
    product_id: "product",
    product_name: "Mobile",
    raw_key: "menu.<script>bad()</script>",
    language: "it",
    language_label: "Italian",
    base_language: "en",
    base_maximum: 5,
    explicit_maximum: null,
    constraint_version: null,
    states: ["draft"],
    state_summary: "draft",
    is_deleted: false,
    pending_change: null,
    comment_count: 0,
    mutation_eligible: true,
    review_eligible: true,
    values: [
      {
        id: "value-1",
        selector_version: 1,
        selector_digest: "a".repeat(64),
        selector_kind: "scalar",
        selector_fields: [],
        source_text: "Save",
        translated_text: "<img src=x onerror=bad()>👨‍👩‍👧‍👦\nمرحبا",
        display_text: "👨‍👩‍👧‍👦",
        structure: [],
        grapheme_count: 6,
        constraint: {
          actual: 6,
          maximum: 5,
          source: "base_default",
          status: "over_limit",
          overage: 1,
        },
        review_state: "draft",
        is_deleted: false,
        deleted_at: null,
        provenance: {
          repository_id: "repo",
          repository_name: "Mobile repo",
          repository_side: "direct",
          branch: "main",
          path: "locales/it.json",
          format: "json",
          commit_hash: "a".repeat(40),
          execution_id: "execution",
          line: 7,
          column: 2,
        },
        history: [
          {
            revision_number: 1,
            revision_digest: "d".repeat(64),
            review_state: "approved",
            is_deleted: false,
            created_at: "2026-09-01T00:00:00Z",
            commit_hash: "b".repeat(40),
            execution_id: "old-execution",
          },
        ],
        history_has_more: false,
      },
    ],
  };
}
function mount(role: RoleName = "viewer", id = "opaque-group", search = "") {
  return render(
    <MemoryRouter initialEntries={[`/translations/${id}${search}`]}>
      <Routes>
        <Route
          path="/translations"
          element={
            <TranslationsWorkspace
              accessToken="token"
              principal={{
                id: "person",
                email: "person@example.com",
                display_name: "Person",
                roles: [role],
                must_change_password: false,
              }}
            />
          }
        >
          <Route
            path=":translationGroupId"
            element={<TranslationDetailPage />}
          />
          <Route index element={<h1>Search restored</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}
function mountProduct(id = "opaque-group") {
  return render(
    <MemoryRouter initialEntries={[`/products/product/strings/${id}`]}>
      <Routes>
        <Route
          path="/products/:productId"
          element={
            <TranslationsWorkspace
              accessToken="token"
              principal={{
                id: "person",
                email: "person@example.com",
                display_name: "Person",
                roles: ["viewer"],
                must_change_password: false,
              }}
              lockedProduct={{ id: "product", name: "Mobile" }}
              detailsBasePath="/products/product/strings"
              searchPath="/products/product/strings"
            />
          }
        >
          <Route
            path="strings/:translationGroupId"
            element={<TranslationDetailPage />}
          />
          <Route path="strings" element={<h2>Product search restored</h2>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}
beforeEach(() => {
  vi.mocked(getTranslationCodeContext)
    .mockReset()
    .mockResolvedValue({
      data: {
        configured: false,
        occurrences: [],
        previews: [],
        capture_functions: [],
      },
    } as never);
  vi.mocked(listTranslationScreenshots)
    .mockReset()
    .mockResolvedValue({ data: { items: [], next_cursor: null } } as never);
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({ matches: false }),
  });
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  vi.mocked(getTranslationGroup).mockResolvedValue({
    data: detailFixture(),
    error: undefined,
  });
  vi.mocked(listTranslationComments).mockResolvedValue({
    data: { items: [], older_cursor: null },
    error: undefined,
  } as never);
  vi.mocked(getTranslationCommentAnchor).mockReset();
  vi.mocked(markNotificationReadByComment).mockReset();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Translation detail — SRCH-06 SRCH-07 CONS-03, populated/long-text/partial", () => {
  it("offers lazy screenshots on a direct translation URL", async () => {
    const user = userEvent.setup();
    mountProduct();
    const summary = await screen.findByText("Screenshots and code references", {
      exact: true,
    });
    expect(getTranslationCodeContext).not.toHaveBeenCalled();
    await user.click(summary);
    expect(
      await screen.findByText(
        "No application code repository is configured for this translation.",
      ),
    ).toBeVisible();
    expect(getTranslationCodeContext).toHaveBeenCalledWith(
      expect.objectContaining({
        auth: "token",
        path: { group_id: "opaque-group" },
      }),
    );
  });
  it("loads a direct exact-comment URL without walking ordinary discussion pages", async () => {
    const target = {
      id: "opaque-comment",
      translation_group_id: "opaque-group",
      language: "it",
      status: "available" as const,
      body: "Please review this exact comment",
      mentions: [],
      author: { id: "author-id", display_name: "Ada Reviewer" },
      current_version: 1,
      edited: false,
      created_at: "2026-09-10T12:00:00Z",
      updated_at: "2026-09-10T12:00:00Z",
      deleted_at: null,
      deleted_by: null,
    };
    vi.mocked(getTranslationCommentAnchor).mockResolvedValue({
      data: { target_id: target.id, items: [target] },
      error: undefined,
    });
    vi.mocked(markNotificationReadByComment).mockResolvedValue({
      data: {
        item: {
          actor: { display_name: "Ada Reviewer", user_id: "author-id" },
          comment_status: "available",
          created_at: target.created_at,
          id: "notification-id",
          is_read: true,
          key_excerpt: "checkout.title",
          language: "it",
          originating_comment_id: target.id,
          product: { id: "product", name: "Mobile" },
          read_at: "2026-09-10T12:01:00Z",
          translation_group_id: "opaque-group",
        },
        unread_count: 0,
      },
      error: undefined,
    });

    mount("viewer", "opaque-group", "?comment=opaque-comment");

    const exact = await screen.findByText("Please review this exact comment");
    await waitFor(() => expect(exact.closest("article")).toHaveFocus());
    expect(getTranslationCommentAnchor).toHaveBeenCalledWith(
      expect.objectContaining({
        path: { translation_group_id: "opaque-group" },
        query: { comment: "opaque-comment" },
      }),
    );
    expect(listTranslationComments).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(markNotificationReadByComment).toHaveBeenCalledTimes(1),
    );
  });
  it("places one stable key-language Discussion between translation content and activity history", async () => {
    mount("viewer");
    const discussion = await screen.findByRole("region", {
      name: "Discussion",
    });
    const translation = screen.getByRole("region", {
      name: "Translation content",
    });
    const activity = screen.getByRole("region", { name: "Activity history" });
    expect(
      translation.compareDocumentPosition(discussion) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      discussion.compareDocumentPosition(activity) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(listTranslationComments).toHaveBeenCalledWith(
      expect.objectContaining({
        auth: "token",
        path: { translation_group_id: "opaque-group" },
      }),
    );
  });
  it("shows role-specific constraint actions and replaces authoritative status while invalidating search pages", async () => {
    const data = detailFixture();
    const fresh = detailFixture();
    fresh.explicit_maximum = 9;
    fresh.constraint_version = 1;
    fresh.values[0].constraint = {
      actual: 6,
      maximum: 9,
      source: "language_override",
      status: "within_limit",
      overage: 0,
    };
    vi.mocked(getTranslationGroup)
      .mockResolvedValueOnce({ data, error: undefined })
      .mockResolvedValue({ data: fresh, error: undefined });
    vi.mocked(putTranslationConstraint).mockResolvedValue({
      data: {
        translation_group_id: data.id,
        language: data.language,
        base_language: "en",
        explicit_maximum: 9,
        version: 1,
        total_count: 1,
        violating_count: 0,
        values: [
          {
            id: "value-1",
            language: "it",
            constraint: fresh.values[0].constraint,
            approval_eligible: true,
            submission_eligible: true,
          },
        ],
      },
      error: undefined,
    });
    const snapshot = {
      query: "retain me",
      pages: [{ items: [], next_cursor: null }],
      scrollAnchor: 123,
      focusedGroupId: data.id,
    };
    const setSnapshot = vi.fn();
    render(
      <MemoryRouter initialEntries={["/translations/opaque-group"]}>
        <Routes>
          <Route
            path="/translations"
            element={
              <Outlet
                context={{
                  accessToken: "token",
                  principal: { id: "person", roles: ["admin"] },
                  snapshot,
                  setSnapshot,
                }}
              />
            }
          >
            <Route
              path=":translationGroupId"
              element={<TranslationDetailPage />}
            />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    const trigger = await screen.findByRole("button", {
      name: "Add language override",
    });
    await userEvent.click(trigger);
    fireEvent.change(screen.getByRole("spinbutton"), {
      target: { value: "9" },
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Save max length" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(
      screen.getByRole("button", { name: "Edit max length" }),
    ).toHaveFocus();
    expect(setSnapshot).toHaveBeenCalledWith({
      ...snapshot,
      pages: [],
      invalidated: true,
    });
    expect(screen.getAllByText("Within limit").length).toBeGreaterThan(0);
    expect(screen.getByTestId("target-value-1")).toHaveTextContent("<img");
  });
  it.each<RoleName>([
    "admin",
    "product_manager_reviewer",
    "translator",
    "viewer",
  ])(
    "reads inert complete content and read-only review context for %s",
    async (role) => {
      mount(role);
      const title = await screen.findByRole("heading", {
        name: "Translation details",
        level: 1,
      });
      expect(title).toHaveFocus();
      expect(screen.getByText("menu.<script>bad()</script>")).toBeVisible();
      expect(screen.getByTestId("target-value-1")).toHaveTextContent(
        "<img src=x onerror=bad()>",
      );
      expect(screen.getByTestId("target-value-1")).toHaveAttribute(
        "lang",
        "it",
      );
      expect(screen.getByTestId("target-value-1")).toHaveAttribute(
        "dir",
        "auto",
      );
      expect(document.querySelector("img, script")).toBeNull();
      expect(screen.getByText("Pending change: None")).toBeVisible();
      expect(screen.getByText("Comments: No comments yet")).toBeVisible();
      expect(screen.getByText("Actual: 6 · Maximum: 5")).toBeVisible();
      expect(screen.getAllByText("Over limit by 1").length).toBeGreaterThan(0);
      expect(screen.getByText("Revision 1")).toBeVisible();
      expect(screen.getByText("old-execution")).toBeVisible();
      expect(
        screen.queryByRole("textbox", { name: /Proposed translation/ }),
      ).toBeNull();
      if (role === "viewer") {
        expect(
          screen.queryByRole("textbox", { name: "Add a comment" }),
        ).toBeNull();
        expect(
          screen.queryByRole("button", {
            name: /approve|submit|comment|edit translation/i,
          }),
        ).toBeNull();
      } else {
        expect(
          screen.getByRole("textbox", { name: "Add a comment" }),
        ).toBeVisible();
        expect(
          screen.getByRole("button", { name: "Post comment" }),
        ).toBeDisabled();
        expect(
          screen.getByRole("button", { name: "Edit translation" }),
        ).toBeVisible();
        expect(
          screen.queryByRole("button", { name: /approve|submit/i }),
        ).toBeNull();
      }
      expect(getTranslationGroup).toHaveBeenCalledWith(
        expect.objectContaining({
          auth: "token",
          path: { translation_group_id: "opaque-group" },
          signal: expect.any(AbortSignal),
        }),
      );
    },
  );
  it("keeps scalar, plural, array, numerus, length variants and typed JSON paths individually addressable", async () => {
    const data = detailFixture();
    const kinds = [
      "scalar",
      "android_quantity",
      "android_array_item",
      "qt_numerus",
      "qt_length_variant",
      "json_path",
    ] as const;
    data.values = kinds.map((kind, i) => ({
      ...data.values[0],
      id: `value-${i}`,
      selector_kind: kind,
      selector_fields:
        kind === "scalar"
          ? []
          : [
              {
                name: ["", "quantity", "index", "form", "variant", "segments"][
                  i
                ],
                value: i === 5 ? ["menu", "a.b"] : i,
              },
            ],
      history: [],
    }));
    vi.mocked(getTranslationGroup).mockResolvedValue({
      data,
      error: undefined,
    });
    mount();
    await screen.findByRole("heading", { name: "Translation details" });
    for (let i = 0; i < 6; i++)
      expect(document.getElementById(`value-value-${i}`)).not.toBeNull();
    expect(
      screen.getByRole("heading", { name: "Default value" }),
    ).toBeVisible();
    expect(screen.getByText("Quantity")).toBeVisible();
    expect(screen.getByText("Array position")).toBeVisible();
    expect(screen.getByText('["menu","a.b"]')).toBeVisible();
  });
  it("renders deleted values, empty content, no maximum and missing optional provenance explicitly", async () => {
    const data = detailFixture();
    data.is_deleted = true;
    data.values[0] = {
      ...data.values[0],
      source_text: null,
      translated_text: "",
      display_text: "",
      grapheme_count: 0,
      constraint: {
        actual: 0,
        maximum: null,
        source: "none",
        status: "no_max",
        overage: null,
      },
      provenance: null,
      history: [],
      is_deleted: true,
      deleted_at: "2026-09-01T00:00:00Z",
    };
    vi.mocked(getTranslationGroup).mockResolvedValue({
      data,
      error: undefined,
    });
    mount();
    expect(await screen.findByText("Empty translation")).toBeVisible();
    expect(screen.getByText("No source text available")).toBeVisible();
    expect(screen.getAllByText("Deleted in source").length).toBeGreaterThan(0);
    expect(screen.getAllByText("No max length").length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Some source or history metadata is unavailable/),
    ).toBeVisible();
    expect(screen.getByText("Pending change: None")).toBeVisible();
  });
  it.each([403, 404])(
    "uses identical bounded unavailable copy for %s",
    async (status) => {
      vi.mocked(getTranslationGroup).mockResolvedValue({
        data: undefined,
        error: { detail: "Translation unavailable" },
        response: new Response(null, { status }),
      });
      mount();
      expect(
        await screen.findByText("Translation not available"),
      ).toBeVisible();
      expect(screen.queryByText(/menu\./)).toBeNull();
    },
  );
  it.each([
    "count",
    "comment-count",
    "states",
    "version-pair",
    "negative-maximum",
    "duplicate-value",
  ])(
    "blocks inconsistent %s authority without leaking the record",
    async (defect) => {
      const data = detailFixture();
      if (defect === "count") data.values[0].constraint.actual = 3;
      if (defect === "comment-count") data.comment_count = -1;
      if (defect === "states") data.states = [];
      if (defect === "version-pair") data.constraint_version = 1;
      if (defect === "negative-maximum") {
        data.explicit_maximum = -1;
        data.constraint_version = 2;
      }
      if (defect === "duplicate-value") data.values.push(data.values[0]);
      vi.mocked(getTranslationGroup).mockResolvedValue({
        data,
        error: undefined,
      });
      mount("admin");
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Translation details unavailable",
      );
      expect(screen.queryByText(data.raw_key)).toBeNull();
    },
  );
  it("shows a compact source location with optional technical details and no unavailable coordinates", async () => {
    const data = detailFixture();
    data.values[0].provenance!.line = null;
    data.values[0].provenance!.column = null;
    vi.mocked(getTranslationGroup).mockResolvedValue({
      data,
      error: undefined,
    });
    mount();
    const source = within(
      await screen.findByRole("region", { name: "Source context" }),
    );
    expect(source.getByText("Mobile repo")).toBeVisible();
    expect(source.getByText("main")).toBeVisible();
    expect(source.getByText("locales/it.json")).toBeVisible();
    expect(source.queryByText("value-1")).toBeNull();
    expect(source.queryByText("execution")).toBeNull();
    expect(source.queryByText(/unavailable/)).toBeNull();
    expect(
      source.getByRole("button", { name: "Copy full commit" }),
    ).not.toBeVisible();
    await userEvent.click(source.getByText("Technical details"));
    expect(
      source.getByRole("button", { name: "Copy full commit" }),
    ).toBeVisible();
  });
  it("announces clipboard failure without exposing the rejected error", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByText("Translation content");
    await user.click(
      within(screen.getByRole("region", { name: "Source context" })).getByText(
        "Technical details",
      ),
    );
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(
      new Error("private clipboard error"),
    );
    await user.click(
      within(screen.getByRole("region", { name: "Source context" })).getByRole(
        "button",
        { name: "Copy full commit" },
      ),
    );
    expect(await screen.findByText("Commit could not be copied")).toBeVisible();
    expect(document.body).not.toHaveTextContent("private clipboard error");
  });
  it("opens a versioned removal confirmation from the detail action", async () => {
    const data = detailFixture();
    data.explicit_maximum = 5;
    data.constraint_version = 2;
    vi.mocked(getTranslationGroup).mockResolvedValue({
      data,
      error: undefined,
    });
    mount("admin");
    await userEvent.click(
      await screen.findByRole("button", { name: "Remove language override" }),
    );
    expect(screen.getByRole("alertdialog")).toHaveTextContent("Remove");
    expect(screen.getByRole("alertdialog")).toHaveTextContent("inherit");
  });
  it("loads with skeletons, silently aborts abandoned requests and supports retry/back", async () => {
    vi.mocked(getTranslationGroup).mockRejectedValueOnce(
      new Error("private error"),
    );
    mount();
    expect(screen.getByText("Loading translation details")).toBeVisible();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Translation details",
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Retry details" }),
    );
    await screen.findByText("Translation content");
    await userEvent.click(
      screen.getByRole("link", { name: "Back to translations" }),
    );
    expect(await screen.findByText("Search restored")).toBeVisible();
    expect(
      vi.mocked(getTranslationGroup).mock.calls[0][0].signal?.aborted,
    ).toBe(true);
  });
  it("returns from details to the focused product search", async () => {
    mountProduct();

    await screen.findByText("Translation content");
    const back = screen.getByRole("link", {
      name: "Back to Mobile strings",
    });
    expect(back).toHaveAttribute("href", "/products/product/strings");
    await userEvent.click(back);
    expect(await screen.findByText("Product search restored")).toBeVisible();
  });
  it("focuses only the current explicit retry failure while retaining the route heading", async () => {
    vi.mocked(getTranslationGroup)
      .mockRejectedValueOnce(new Error("private"))
      .mockRejectedValueOnce(new Error("private"));
    mount();
    const firstAlert = await screen.findByRole("alert");
    expect(firstAlert).not.toHaveFocus();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Translation details",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Retry details" }),
    );
    await waitFor(() => expect(screen.getByRole("alert")).toHaveFocus());
  });
  it("copies only a user-requested complete commit and announces bounded success", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByText("Translation content");
    await user.click(
      within(screen.getByRole("region", { name: "Source context" })).getByText(
        "Technical details",
      ),
    );
    const copy = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    await user.click(
      within(screen.getByRole("region", { name: "Source context" })).getByRole(
        "button",
        { name: "Copy full commit" },
      ),
    );
    expect(copy).toHaveBeenCalledWith("a".repeat(40));
    expect(await screen.findByText("Full commit copied")).toBeVisible();
    expect(
      within(screen.getByRole("region", { name: "Review context" })).getByText(
        "Draft",
      ),
    ).toBeVisible();
  });
  it("ignores late detail success after navigation", async () => {
    let resolve!: (
      value: Awaited<ReturnType<typeof getTranslationGroup<false>>>,
    ) => void;
    vi.mocked(getTranslationGroup).mockReturnValue(
      new Promise<Awaited<ReturnType<typeof getTranslationGroup<false>>>>(
        (r) => {
          resolve = r;
        },
      ),
    );
    const view = mount();
    view.unmount();
    await act(async () => resolve({ data: detailFixture(), error: undefined }));
    expect(screen.queryByText("Translation content")).toBeNull();
  });
});

function scalarMissing(assertionId: string, detail: string): never {
  throw new Error(`PHASE5_SCALAR_MISSING[${assertionId}]: ${detail}`);
}

function proposalProjection(
  data: TranslationGroupDetailResponse,
  text: string,
) {
  const value = data.values[0];
  return {
    translation_group_id: data.id,
    language: data.language,
    version: 1,
    state: "draft",
    reconciliation_required: false,
    published: [
      {
        translation_value_id: value.id,
        selector_version: value.selector_version,
        selector_digest: value.selector_digest,
        revision_number: 1,
        revision_digest: "d".repeat(64),
        text: value.translated_text,
        review_state: value.review_state,
      },
    ],
    pending: [
      {
        translation_value_id: value.id,
        selector_version: value.selector_version,
        selector_digest: value.selector_digest,
        basis_revision_number: 1,
        basis_digest: "d".repeat(64),
        text,
        grapheme_count: [...text].length,
        maximum: null,
        is_over_limit: false,
        approval_eligible: true,
        submission_eligible: true,
      },
    ],
    updated_by: "person",
    updated_at: "2026-09-10T00:00:00Z",
    activity: {
      kind: "proposal_saved",
      proposal_version: 1,
      actor_id: "person",
      created_at: "2026-09-10T00:00:00Z",
      id: "activity",
      translation_group_id: data.id,
      language: data.language,
      from_state: null,
      to_state: null,
      before_values: null,
      after_values: null,
      reason: null,
      comment_id: null,
    },
  };
}

describe("Phase 5 scalar proposal tracer RED", () => {
  it("renders published and pending scalar authorities separately", async () => {
    const data = detailFixture();
    const pendingText = "Bozza مرحبا 中文";
    vi.mocked(getTranslationGroup).mockResolvedValue({
      data,
      error: undefined,
    });
    vi.mocked(saveTranslationProposal).mockResolvedValue({
      data: proposalProjection(data, pendingText),
      error: undefined,
    } as never);

    mount("translator");
    await screen.findByRole("heading", { name: "Translation details" });
    const edit = await screen
      .findByRole("button", { name: "Edit translation" })
      .catch(() => null);
    if (!edit)
      scalarMissing(
        "edit-control",
        "authorized scalar detail has no explicit proposal editor",
      );
    await userEvent.click(edit);
    const textbox = screen.getByRole("textbox", {
      name: "Proposed translation",
    });
    await userEvent.clear(textbox);
    await userEvent.type(textbox, pendingText);
    await userEvent.click(
      screen.getByRole("button", { name: "Save translation" }),
    );
    const published = screen.queryByRole("region", {
      name: "Published translation",
    });
    const pending = screen.queryByRole("region", { name: "Pending proposal" });
    if (!published || !pending)
      scalarMissing(
        "published-pending-separation",
        "detail does not expose separately labelled published and pending authorities",
      );
    expect(
      within(published).getByText(/<img src=x onerror=bad\(\)>/),
    ).toBeVisible();
    expect(within(pending).getByText(pendingText)).toBeVisible();
    expect(within(pending).getByText("Draft")).toBeVisible();
  });

  it("keeps text browser-local until Save and discards it on Cancel", async () => {
    const data = detailFixture();
    const unicode = "𐐷 e\u0301 — مرحبا — 中文";
    vi.mocked(saveTranslationProposal)
      .mockRejectedValueOnce(new Error("private transport failure"))
      .mockResolvedValue({
        data: proposalProjection(data, unicode),
        error: undefined,
      } as never);
    mount("translator");
    await screen.findByText("Translation content");

    const edit = screen.queryByRole("button", { name: "Edit translation" });
    if (!edit)
      scalarMissing(
        "edit-control",
        "authorized scalar detail has no explicit proposal editor",
      );
    await userEvent.click(edit);
    const textbox = screen.getByRole("textbox", {
      name: "Proposed translation",
    });
    await userEvent.clear(textbox);
    await userEvent.type(textbox, "browser-only");
    expect(saveTranslationProposal).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Stop editing translation" }),
    );
    expect(
      screen.getByRole("alertdialog", { name: "Leave without saving?" }),
    ).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Discard changes" }),
    );
    expect(saveTranslationProposal).not.toHaveBeenCalled();
    expect(screen.getByTestId("target-value-1")).toHaveTextContent(
      "<img src=x",
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Edit translation" }),
    );
    const reopened = screen.getByRole("textbox", {
      name: "Proposed translation",
    });
    expect(reopened).not.toHaveValue("browser-only");
    await userEvent.clear(reopened);
    await userEvent.type(reopened, unicode);
    expect(saveTranslationProposal).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Save translation" }),
    );
    expect(
      await screen.findByText(
        "Your changes are still in this editor. Review them and save again.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("textbox", { name: "Proposed translation" }),
    ).toHaveValue(unicode);
    expect(document.body).not.toHaveTextContent("private transport failure");
    await userEvent.click(
      screen.getByRole("button", { name: "Save translation" }),
    );
    await waitFor(() =>
      expect(saveTranslationProposal).toHaveBeenCalledTimes(2),
    );
    expect(saveTranslationProposal).toHaveBeenLastCalledWith(
      expect.objectContaining({
        auth: "token",
        path: { translation_group_id: data.id },
        body: {
          expected_version: 0,
          values: [
            {
              translation_value_id: "value-1",
              selector_version: 1,
              selector_digest: "a".repeat(64),
              basis_revision_number: 1,
              basis_digest: "d".repeat(64),
              proposed_text: unicode,
            },
          ],
        },
      }),
    );
    expect(screen.getByTestId("target-value-1")).toHaveTextContent(
      "<img src=x",
    );
    expect(
      screen.getByRole("region", { name: "Pending proposal" }),
    ).toHaveTextContent(unicode);
  });

  it("hides proposal controls from a viewer", async () => {
    mount("viewer");
    await screen.findByText("Translation content");
    if (!screen.queryByRole("region", { name: "Published translation" }))
      scalarMissing(
        "viewer-published-authority",
        "viewer detail lacks the explicit published-authority projection",
      );
    expect(
      screen.queryByRole("button", { name: "Edit translation" }),
    ).toBeNull();
    expect(
      screen.queryByRole("textbox", { name: "Proposed translation" }),
    ).toBeNull();
    expect(saveTranslationProposal).not.toHaveBeenCalled();
  });
});

describe("Phase 5 complete review controls", () => {
  it("routes approved branch changes to history without offering legacy submission", async () => {
    const data = detailFixture();
    const fresh = proposalProjection(data, "Approved commit");
    data.approval_commits_enabled = true;
    data.pending_change = {
      version: 7,
      state: "approved",
      reconciliation_required: false,
      updated_by: fresh.updated_by,
      updated_at: fresh.updated_at,
      values: fresh.pending,
    };
    vi.mocked(getTranslationGroup).mockResolvedValue({
      data,
      error: undefined,
    });
    mount("admin");
    expect(
      await screen.findByText(/Each approval queues a separate commit/),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Review for submission" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "View change-set history" }),
    ).toHaveAttribute("href", "/products/product/change-sets/history");
  });
  it.each(["viewer", "translator"] as const)(
    "keeps submission controls hidden for %s with an Approved proposal",
    async (role) => {
      const data = detailFixture();
      const fresh = proposalProjection(data, "Saved approved");
      data.pending_change = {
        version: 7,
        state: "approved",
        reconciliation_required: false,
        updated_by: fresh.updated_by,
        updated_at: fresh.updated_at,
        values: fresh.pending,
      };
      vi.mocked(getTranslationGroup).mockResolvedValue({
        data,
        error: undefined,
      });
      mount(role);
      await screen.findByRole("region", { name: "Review context" });
      expect(
        screen.queryByRole("button", { name: "Review for submission" }),
      ).toBeNull();
      expect(
        screen.getByRole("link", { name: "View change-set history" }),
      ).toHaveAttribute("href", "/products/product/change-sets/history");
    },
  );

  it("offers submission review only for the saved complete Approved version", async () => {
    const data = detailFixture();
    const fresh = proposalProjection(data, "Saved approved");
    data.pending_change = {
      version: 7,
      state: "approved",
      reconciliation_required: false,
      updated_by: fresh.updated_by,
      updated_at: fresh.updated_at,
      values: fresh.pending,
    };
    vi.mocked(getTranslationGroup).mockResolvedValue({
      data,
      error: undefined,
    });
    mount("admin");
    const entry = await screen.findByRole("button", {
      name: "Review for submission",
    });
    await userEvent.click(entry);
    await waitFor(() =>
      expect(
        consumeSubmissionEntry({
          principalId: "person",
          accessToken: "token",
          productId: "product",
        }),
      ).toMatchObject({
        translationGroupId: "opaque-group",
        expectedVersion: 7,
      }),
    );
  });

  it("seeds only after dirty-editor discard and navigates through the global guard once", async () => {
    const data = detailFixture();
    const fresh = proposalProjection(data, "Saved approved");
    data.pending_change = {
      version: 7,
      state: "approved",
      reconciliation_required: false,
      updated_by: fresh.updated_by,
      updated_at: fresh.updated_at,
      values: fresh.pending,
    };
    vi.mocked(getTranslationGroup).mockResolvedValue({
      data,
      error: undefined,
    });
    const router = createMemoryRouter(
      [
        {
          element: (
            <DirtyFormNavigationProvider>
              <Outlet />
            </DirtyFormNavigationProvider>
          ),
          children: [
            {
              path: "/translations",
              element: (
                <TranslationsWorkspace
                  accessToken="token"
                  principal={{
                    id: "person",
                    email: "person@example.com",
                    display_name: "Person",
                    roles: ["admin"],
                    must_change_password: false,
                  }}
                />
              ),
              children: [
                {
                  path: ":translationGroupId",
                  element: <TranslationDetailPage />,
                },
              ],
            },
            {
              path: "/products/product/change-sets",
              element: <h1>Submission selection</h1>,
            },
          ],
        },
      ],
      { initialEntries: ["/translations/opaque-group"] },
    );
    render(<RouterProvider router={router} />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Edit translation" }),
    );
    const input = screen.getByRole("textbox", { name: "Proposed translation" });
    await userEvent.clear(input);
    await userEvent.type(input, "Unsaved text");
    expect(
      screen.getByRole("button", { name: "Return to Draft" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Reject translation" }),
    ).toBeDisabled();
    const entry = screen.getByRole("button", { name: "Review for submission" });
    await userEvent.click(entry);
    expect(await screen.findByRole("alertdialog")).toBeVisible();
    expect(
      consumeSubmissionEntry({
        principalId: "person",
        accessToken: "token",
        productId: "product",
      }),
    ).toBeUndefined();
    await userEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(input).toHaveValue("Unsaved text");
    expect(entry).toHaveFocus();
    await userEvent.click(entry);
    await userEvent.click(
      await screen.findByRole("button", { name: "Discard changes" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Submission selection" }),
    ).toBeVisible();
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(
      consumeSubmissionEntry({
        principalId: "person",
        accessToken: "token",
        productId: "product",
      }),
    ).toMatchObject({
      translationGroupId: "opaque-group",
      expectedVersion: 7,
    });
  });

  it.each([1, 2])(
    "honors refreshed detail eligibility at proposal version %i after a constraint change",
    async (version) => {
      const data = { ...detailFixture(), review_eligible: false };
      const fresh = proposalProjection(data, "Ciao");
      const refreshed: TranslationGroupDetailResponse = {
        ...data,
        explicit_maximum: 2,
        constraint_version: 1,
        pending_change: {
          version,
          state: "draft",
          reconciliation_required: false,
          updated_by: fresh.updated_by,
          updated_at: fresh.updated_at,
          values: fresh.pending.map((value) => ({
            ...value,
            maximum: 2,
            is_over_limit: true,
            approval_eligible: false,
            submission_eligible: false,
          })),
        },
        values: data.values.map((value) => ({
          ...value,
          constraint: {
            actual: 6,
            maximum: 2,
            source: "language_override",
            status: "over_limit",
            overage: 4,
          },
        })),
      };
      vi.mocked(getTranslationGroup)
        .mockResolvedValueOnce({ data, error: undefined })
        .mockResolvedValueOnce({ data: refreshed, error: undefined });
      vi.mocked(saveTranslationProposal).mockResolvedValue({
        data: fresh,
        error: undefined,
      } as never);
      vi.mocked(putTranslationConstraint).mockResolvedValue({
        data: { translation_group_id: data.id, language: data.language },
        error: undefined,
      } as never);
      mount("admin");
      await userEvent.click(
        await screen.findByRole("button", { name: "Edit translation" }),
      );
      const input = screen.getByRole("textbox", {
        name: "Proposed translation",
      });
      await userEvent.clear(input);
      await userEvent.type(input, "Ciao");
      await userEvent.click(
        screen.getByRole("button", { name: "Save translation" }),
      );
      expect(
        await screen.findByRole("button", { name: "Approve translation" }),
      ).toBeEnabled();
      await userEvent.click(
        screen.getByRole("button", { name: "Add language override" }),
      );
      const maximum = screen.getByRole("spinbutton", {
        name: "Maximum characters",
      });
      await userEvent.clear(maximum);
      await userEvent.type(maximum, "2");
      await userEvent.click(
        screen.getByRole("button", { name: "Save max length" }),
      );
      await waitFor(() =>
        expect(
          screen.queryByRole("button", { name: "Approve translation" }),
        ).not.toBeInTheDocument(),
      );
      expect(getTranslationGroup).toHaveBeenCalledTimes(2);
      expect(transitionTranslationProposal).not.toHaveBeenCalled();
    },
  );

  it.each(["admin", "product_manager_reviewer"] as const)(
    "lets %s review a first saved proposal without reloading the detail",
    async (role) => {
      const data = { ...detailFixture(), review_eligible: false };
      const fresh = proposalProjection(data, "Ciao");
      vi.mocked(getTranslationGroup).mockResolvedValue({
        data,
        error: undefined,
      });
      vi.mocked(saveTranslationProposal).mockResolvedValue({
        data: fresh,
        error: undefined,
      } as never);
      vi.mocked(transitionTranslationProposal).mockResolvedValue({
        data: { ...fresh, state: "approved", version: 2 },
        error: undefined,
      } as never);
      mount(role);
      await userEvent.click(
        await screen.findByRole("button", { name: "Edit translation" }),
      );
      const input = screen.getByRole("textbox", {
        name: "Proposed translation",
      });
      await userEvent.clear(input);
      await userEvent.type(input, "Ciao");
      await userEvent.click(
        screen.getByRole("button", { name: "Save translation" }),
      );
      const approve = await screen.findByRole("button", {
        name: "Approve translation",
      });
      expect(approve).toBeEnabled();
      await userEvent.click(approve);
      expect(transitionTranslationProposal).toHaveBeenCalledWith(
        expect.objectContaining({
          body: { expected_version: 1, target_state: "approved", reason: null },
        }),
      );
      expect(
        await screen.findByRole("button", { name: "Return to Draft" }),
      ).toBeEnabled();
      expect(getTranslationGroup).toHaveBeenCalledTimes(1);
    },
  );

  it.each(["translator", "server-denied", "reconciliation"] as const)(
    "preserves %s restrictions after a first proposal save",
    async (restriction) => {
      const data = { ...detailFixture(), review_eligible: false };
      const fresh = proposalProjection(data, "Ciao");
      if (restriction === "server-denied")
        fresh.pending[0].approval_eligible = false;
      if (restriction === "reconciliation")
        fresh.reconciliation_required = true;
      vi.mocked(getTranslationGroup).mockResolvedValue({
        data,
        error: undefined,
      });
      vi.mocked(saveTranslationProposal).mockResolvedValue({
        data: fresh,
        error: undefined,
      } as never);
      mount(restriction === "translator" ? "translator" : "admin");
      await userEvent.click(
        await screen.findByRole("button", { name: "Edit translation" }),
      );
      const input = screen.getByRole("textbox", {
        name: "Proposed translation",
      });
      await userEvent.clear(input);
      await userEvent.type(input, "Ciao");
      await userEvent.click(
        screen.getByRole("button", { name: "Save translation" }),
      );
      expect(
        await screen.findByRole("region", { name: "Pending proposal" }),
      ).toHaveTextContent("Ciao");
      expect(
        screen.queryByRole("button", { name: "Approve translation" }),
      ).not.toBeInTheDocument();
      expect(transitionTranslationProposal).not.toHaveBeenCalled();
    },
  );

  it("keeps Approved published authority beside Draft pending and performs optional-reason review transitions", async () => {
    const user = userEvent.setup();
    const data = detailFixture();
    data.values[0].review_state = "approved";
    data.states = ["approved"];
    data.state_summary = "approved";
    data.pending_change = {
      version: 4,
      state: "draft",
      reconciliation_required: false,
      updated_by: "translator",
      updated_at: "2026-09-10T00:00:00Z",
      values: [
        {
          translation_value_id: data.values[0].id,
          selector_version: 1,
          selector_digest: data.values[0].selector_digest,
          basis_revision_number: 1,
          basis_digest: "d".repeat(64),
          text: "Pending draft",
          grapheme_count: 3,
          maximum: 5,
          is_over_limit: false,
          approval_eligible: true,
          submission_eligible: true,
        },
      ],
    };
    const approved = proposalProjection(data, "Pending draft");
    approved.version = 5;
    approved.state = "approved";
    vi.mocked(getTranslationGroup).mockResolvedValue({
      data,
      error: undefined,
    });
    vi.mocked(transitionTranslationProposal).mockResolvedValue({
      data: approved,
      error: undefined,
    } as never);
    mount("product_manager_reviewer");
    const published = await screen.findByRole("region", {
      name: "Published translation",
    });
    const pending = screen.getByRole("region", { name: "Pending proposal" });
    expect(within(published).getAllByText("Approved")[0]).toBeVisible();
    expect(within(pending).getByText("Draft")).toBeVisible();
    expect(within(pending).getByText("Pending draft")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Reject translation" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Reject this translation?" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Reject translation" }),
    );
    expect(transitionTranslationProposal).toHaveBeenCalledWith(
      expect.objectContaining({
        auth: "token",
        path: { translation_group_id: data.id },
        body: { expected_version: 4, target_state: "rejected", reason: null },
      }),
    );
  });

  it("shows an approval block instead of hiding review authority for over-limit proposals", async () => {
    const data = detailFixture();
    data.pending_change = {
      version: 2,
      state: "draft",
      reconciliation_required: false,
      updated_by: "translator",
      updated_at: "2026-09-10T00:00:00Z",
      values: [
        {
          translation_value_id: data.values[0].id,
          selector_version: 1,
          selector_digest: data.values[0].selector_digest,
          basis_revision_number: 1,
          basis_digest: "d".repeat(64),
          text: "too long",
          grapheme_count: 8,
          maximum: 5,
          is_over_limit: true,
          approval_eligible: false,
          submission_eligible: false,
        },
      ],
    };
    vi.mocked(getTranslationGroup).mockResolvedValue({
      data,
      error: undefined,
    });
    mount("admin");
    expect(await screen.findByText("Approval blocked")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Approve translation" }),
    ).toBeDisabled();
  });
});

function activityFixture(index: number): ReviewActivityResponse {
  return {
    id: `activity-${index}`,
    translation_group_id: "opaque-group",
    language: "it",
    kind: index % 2 ? "state_changed" : "proposal_saved",
    proposal_version: 30 - index,
    actor_id: `actor-${index}`,
    created_at: `2026-09-${String(30 - index).padStart(2, "0")}T10:00:00Z`,
    from_state: index % 2 ? "draft" : null,
    to_state: index % 2 ? "approved" : null,
    before_values: [
      {
        translation_value_id: "value-1",
        selector_version: 1,
        selector_digest: "a".repeat(64),
        basis_revision_number: 1,
        basis_digest: "d".repeat(64),
        text: `before ${index}`,
      },
    ],
    after_values: [
      {
        translation_value_id: "value-1",
        selector_version: 1,
        selector_digest: "a".repeat(64),
        basis_revision_number: 1,
        basis_digest: "d".repeat(64),
        text: `after ${index}\nمرحبا 中文`,
      },
    ],
    reason: index % 2 ? `Complete reason ${index}` : null,
    comment_id: index === 0 ? "comment-1" : null,
  };
}

describe("Phase 5 complete activity history", () => {
  it("stays collapsed, loads the newest 20, and reaches the 21st item exactly once", async () => {
    const user = userEvent.setup();
    vi.mocked(listTranslationReviewActivity)
      .mockResolvedValueOnce({
        data: {
          items: Array.from({ length: 20 }, (_, index) =>
            activityFixture(index),
          ),
          next_cursor: "older-20",
        },
        error: undefined,
      } as never)
      .mockResolvedValueOnce({
        data: { items: [activityFixture(20)], next_cursor: null },
        error: undefined,
      } as never);
    mount();
    await screen.findByText("Translation content");
    expect(listTranslationReviewActivity).not.toHaveBeenCalled();
    await user.click(
      screen.getByRole("button", { name: "Show activity history" }),
    );
    expect(await screen.findByText("after 0 مرحبا 中文")).toBeVisible();
    expect(screen.queryByText("after 20 مرحبا 中文")).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Show earlier activity" }),
    );
    expect(await screen.findByText("after 20 مرحبا 中文")).toBeVisible();
    expect(listTranslationReviewActivity).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        path: { translation_group_id: "opaque-group" },
        query: { cursor: "older-20" },
      }),
    );
    expect(
      screen.queryByRole("button", { name: "Show earlier activity" }),
    ).toBeNull();
  });

  it("renders exact empty and initial failure recovery states without replacing detail", async () => {
    const user = userEvent.setup();
    vi.mocked(listTranslationReviewActivity)
      .mockRejectedValueOnce(new Error("private"))
      .mockResolvedValueOnce({
        data: { items: [], next_cursor: null },
        error: undefined,
      } as never);
    mount();
    await user.click(
      await screen.findByRole("button", { name: "Show activity history" }),
    );
    expect(
      await screen.findByText("Activity history could not be loaded"),
    ).toBeVisible();

    expect(screen.getByText("Translation content")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Reload activity history" }),
    );
    expect(await screen.findByText("No activity yet")).toBeVisible();
  });

  it("retains valid pages and fails closed on duplicate IDs, mixed scope, or repeated cursors", async () => {
    const user = userEvent.setup();
    const first = activityFixture(0);
    const corrupt = {
      ...activityFixture(1),
      id: first.id,
      translation_group_id: "another-group",
    };
    vi.mocked(listTranslationReviewActivity)
      .mockResolvedValueOnce({
        data: { items: [first], next_cursor: "same" },
        error: undefined,
      } as never)
      .mockResolvedValueOnce({
        data: { items: [corrupt], next_cursor: "same" },
        error: undefined,
      } as never)
      .mockResolvedValueOnce({
        data: { items: [activityFixture(1)], next_cursor: null },
        error: undefined,
      } as never);
    mount();
    await user.click(
      await screen.findByRole("button", { name: "Show activity history" }),
    );
    expect(await screen.findByText("after 0 مرحبا 中文")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Show earlier activity" }),
    );
    expect(
      await screen.findByText("Earlier activity could not be loaded"),
    ).toBeVisible();
    expect(screen.getByText("after 0 مرحبا 中文")).toBeVisible();
    expect(screen.queryByText("after 1 مرحبا 中文")).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Retry earlier activity" }),
    );
    expect(await screen.findByText("after 1 مرحبا 中文")).toBeVisible();
  });
});
