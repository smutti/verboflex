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
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getTranslationGroup,
  putTranslationConstraint,
  type TranslationGroupDetailResponse,
  type RoleName,
} from "../../api/client";
import { TranslationDetailPage } from "./TranslationDetailPage";
import { TranslationsWorkspace } from "./TranslationsWorkspace";

vi.mock("../../api/client", () => ({
  getTranslationGroup: vi.fn(),
  putTranslationConstraint: vi.fn(),
  deleteTranslationConstraint: vi.fn(),
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
    comments: [],
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
function mount(role: RoleName = "viewer", id = "opaque-group") {
  return render(
    <MemoryRouter initialEntries={[`/translations/${id}`]}>
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
beforeEach(() =>
  vi
    .mocked(getTranslationGroup)
    .mockResolvedValue({ data: detailFixture(), error: undefined }),
);
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Translation detail — SRCH-06 SRCH-07 CONS-03, populated/long-text/partial", () => {
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
      expect(screen.getAllByText("Over limit by 1").length).toBeGreaterThan(0);
      expect(screen.getByText("Revision 1")).toBeVisible();
      expect(screen.getByText("old-execution")).toBeVisible();
      expect(screen.queryByRole("textbox")).toBeNull();
      expect(
        screen.queryByRole("button", {
          name: /approve|submit|comment|edit translation/i,
        }),
      ).toBeNull();
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
    expect(screen.getByText("Default value")).toBeVisible();
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
  it("blocks inconsistent mandatory authority without leaking the record", async () => {
    const data = detailFixture();
    data.values[0].constraint.actual = 3;
    vi.mocked(getTranslationGroup).mockResolvedValue({
      data,
      error: undefined,
    });
    mount("admin");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Translation details unavailable",
    );
    expect(screen.queryByText(data.raw_key)).toBeNull();
  });
  it("loads with skeletons, silently aborts abandoned requests and supports retry/back", async () => {
    vi.mocked(getTranslationGroup).mockRejectedValueOnce(
      new Error("private error"),
    );
    mount();
    expect(screen.getByText("Loading translation details")).toBeVisible();
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
  it("copies only a user-requested complete commit and announces bounded success", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByText("Translation content");
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
