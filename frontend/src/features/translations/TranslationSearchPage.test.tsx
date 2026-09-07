import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  Link,
  Outlet,
  MemoryRouter,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  listTranslationOptions,
  searchTranslations,
  type CurrentUserResponse,
  type TranslationGroupSummaryResponse,
} from "../../api/client";
import { TranslationSearchPage } from "./TranslationSearchPage";
import { TranslationsWorkspace } from "./TranslationsWorkspace";
import { translationPreferenceKey } from "./translationPreferences";
import { translationSearchIdentity } from "./useTranslationSearch";

vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  listTranslationOptions: vi.fn(),
  searchTranslations: vi.fn(),
}));
const listProps = vi.hoisted(() => vi.fn());
vi.mock("./TranslationResultList", () => ({
  TranslationResultList: (props: {
    items: TranslationGroupSummaryResponse[];
    nextCursor: string | null;
    onLoadMore: () => void;
    onOpenDetails: (id: string) => void;
  }) => {
    listProps(props);
    return (
      <div role="list" aria-label="Translation results">
        {props.items.map((item) => (
          <Link
            key={item.id}
            to={`/translations/${item.id}`}
            data-translation-group-id={item.id}
            onClick={() => props.onOpenDetails(item.id)}
          >
            Open details {item.raw_key}
          </Link>
        ))}
        {props.nextCursor && (
          <button onClick={props.onLoadMore}>Load more translations</button>
        )}
      </div>
    );
  },
}));
const principal = {
  id: "principal-a",
  roles: ["viewer"],
  display_name: "Viewer",
  email: "viewer@example.test",
  must_change_password: false,
} as CurrentUserResponse;
const options = {
  products: [
    { id: "alpha", name: "Alpha" },
    { id: "beta", name: "Beta" },
  ],
  languages: [
    { code: "en", label: "English" },
    { code: "it", label: "Italian" },
  ],
};
function group(
  id: string,
  changes: Partial<TranslationGroupSummaryResponse> = {},
): TranslationGroupSummaryResponse {
  return {
    id,
    product_id: "alpha",
    product_name: "Alpha",
    raw_key: id,
    language: "it",
    language_label: "Italian",
    source_language: "en",
    source_text: "Source",
    translated_text: "Translated",
    selector_kinds: ["scalar"],
    provenance: null,
    value_count: 1,
    no_max_count: 1,
    over_limit_count: 0,
    within_limit_count: 0,
    has_no_max: true,
    has_over_limit: false,
    is_deleted: false,
    rank: 3,
    states: ["draft"],
    state_summary: "draft",
    ...changes,
  };
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { resolve, promise };
}
const flush = () =>
  act(async () => {
    for (let i = 0; i < 12; i++) await Promise.resolve();
  });
function Detail() {
  const navigate = useNavigate();
  return (
    <>
      <h1>Details</h1>
      <button onClick={() => navigate(-1)}>Back</button>
    </>
  );
}
function tree(
  user = principal,
  token = "token",
  initialEntry = "/translations",
  lockedProduct?: { id: string; name: string },
) {
  return (
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route
          path={lockedProduct ? "/products/:productId" : "/translations"}
          element={
            <TranslationsWorkspace
              principal={user}
              accessToken={token}
              lockedProduct={lockedProduct}
            />
          }
        >
          <Route
            index={!lockedProduct}
            path={lockedProduct ? "strings" : undefined}
            element={<TranslationSearchPage />}
          />
          <Route path=":id" element={<Detail />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}
async function mount() {
  const result = render(tree());
  await flush();
  return result;
}
async function choose(label: string, name: string) {
  const user = userEvent.setup();
  await user.click(screen.getByRole("combobox", { name: label }));
  await user.click(screen.getByRole("option", { name }));
  await flush();
}
function preference(productId: string | null, language: string | null) {
  localStorage.setItem(
    translationPreferenceKey(principal.id),
    JSON.stringify({ version: 1, productId, language }),
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  Object.defineProperties(HTMLElement.prototype, {
    hasPointerCapture: { configurable: true, value: () => false },
    setPointerCapture: { configurable: true, value: () => {} },
    releasePointerCapture: { configurable: true, value: () => {} },
    scrollIntoView: { configurable: true, value: vi.fn() },
  });
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  vi.mocked(listTranslationOptions).mockImplementation(
    async () => ({ data: options }) as never,
  );
  vi.mocked(searchTranslations).mockImplementation(
    async () => ({ data: { items: [], next_cursor: null } }) as never,
  );
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("TranslationSearchPage", () => {
  it("locks product-scoped search and retains the product when filters are cleared", async () => {
    render(
      tree(principal, "token", "/products/alpha/strings", {
        id: "alpha",
        name: "Alpha",
      }),
    );
    await flush();

    expect(screen.queryByRole("combobox", { name: "Product" })).toBeNull();
    expect(screen.getByText("Searching only in Alpha")).toBeVisible();
    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({ product_id: "alpha" });

    await choose("Language", "Italian (it)");
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    await flush();

    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({ product_id: "alpha", language: null });
  });

  it("automatically applies a valid product filter from the imported-strings URL", async () => {
    preference("beta", null);

    render(tree(principal, "token", "/translations?product_id=alpha"));
    await flush();

    expect(screen.getByRole("combobox", { name: "Product" })).toHaveTextContent(
      "Alpha",
    );
    expect(vi.mocked(listTranslationOptions)).toHaveBeenCalledWith(
      expect.objectContaining({ query: { product_id: "alpha" } }),
    );
    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({ product_id: "alpha" });
  });

  it("clears pending options criteria and aborts the superseded option request", async () => {
    const pending = deferred<never>();
    vi.mocked(listTranslationOptions).mockReturnValueOnce(pending.promise);
    render(tree());
    await flush();
    const signal = vi.mocked(listTranslationOptions).mock.calls[0][0]?.signal;
    fireEvent.change(screen.getByLabelText("Search keys and translations"), {
      target: { value: "discard this" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    await flush();
    expect(signal?.aborted).toBe(true);
    expect(screen.getByLabelText("Search keys and translations")).toHaveValue(
      "",
    );
    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({ q: "", product_id: null, language: null });
    await act(async () =>
      pending.resolve({ data: { products: [], languages: [] } } as never),
    );
    expect(screen.getByRole("combobox", { name: "Product" })).toHaveTextContent(
      "All products",
    );
  });
  it.each([null, "later"])(
    "restores navigation before deferred result focus is available (%s)",
    async (focusedGroupId) => {
      const filters = {
        productId: null,
        language: null,
        state: null,
        violation: null,
        deleted: "active" as const,
      };
      vi.mocked(searchTranslations).mockResolvedValue({
        data: { items: [group("later")], next_cursor: null },
      } as never);
      render(
        <MemoryRouter initialEntries={["/translations"]}>
          <Routes>
            <Route
              element={
                <Outlet
                  context={{
                    principal,
                    accessToken: "token",
                    setSnapshot: vi.fn(),
                    snapshot: {
                      version: 1,
                      query: "",
                      filters,
                      pages: [{ items: [group("first")], next_cursor: "next" }],
                      requestIdentity: translationSearchIdentity("", filters),
                      scrollAnchor: 480,
                      focusedGroupId,
                    },
                  }}
                />
              }
            >
              <Route path="translations" element={<TranslationSearchPage />} />
            </Route>
          </Routes>
        </MemoryRouter>,
      );
      await flush();
      expect(window.scrollTo).toHaveBeenCalledWith({
        top: 480,
        behavior: "instant",
      });
      expect(searchTranslations).not.toHaveBeenCalled();
      fireEvent.click(
        screen.getByRole("button", { name: "Load more translations" }),
      );
      await flush();
      const later = screen.getByRole("link", { name: "Open details later" });
      if (focusedGroupId) expect(later).toHaveFocus();
      else expect(later).not.toHaveFocus();
    },
  );
  it("retains query input across pending and failed options retries and focuses only explicit failure", async () => {
    const pending = deferred<never>();
    vi.mocked(listTranslationOptions)
      .mockReturnValueOnce(pending.promise)
      .mockResolvedValueOnce({ error: {} } as never);
    render(tree());
    fireEvent.change(screen.getByLabelText("Search keys and translations"), {
      target: { value: "literal pending query" },
    });
    await act(async () => pending.resolve({ error: {} } as never));
    await flush();
    expect(screen.getByLabelText("Search keys and translations")).toHaveValue(
      "literal pending query",
    );
    expect(screen.getByRole("alert")).not.toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Retry search" }));
    await flush();
    expect(screen.getByRole("alert")).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Retry search" }));
    await flush();
    expect(screen.getByLabelText("Search keys and translations")).toHaveFocus();
    expect(vi.mocked(searchTranslations).mock.lastCall?.[0]?.query?.q).toBe(
      "literal pending query",
    );
  });

  it("focuses a current explicit search retry failure", async () => {
    vi.mocked(searchTranslations).mockResolvedValue({ error: {} } as never);
    await mount();
    expect(screen.getByRole("alert")).not.toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Retry search" }));
    await flush();
    expect(screen.getByRole("alert")).toHaveFocus();
  });
  it("waits for live options before searching and exposes the exact query contract", async () => {
    const pending = deferred<never>();
    vi.mocked(listTranslationOptions).mockReturnValueOnce(pending.promise);
    render(tree());
    await flush();
    expect(searchTranslations).not.toHaveBeenCalled();
    expect(screen.getByRole("combobox", { name: "Product" })).toBeDisabled();
    expect(screen.getByLabelText("Search keys and translations")).toHaveValue(
      "",
    );
    await act(async () => pending.resolve({ data: options } as never));
    await flush();
    expect(
      screen.getByLabelText("Search keys and translations"),
    ).toHaveAttribute("placeholder", "Enter a key or text");
    expect(
      screen.getByText(
        "Searches original keys, source text, and translated text.",
      ),
    ).toBeVisible();
    expect(searchTranslations).toHaveBeenCalledOnce();
    expect(vi.mocked(searchTranslations).mock.calls[0][0]).toMatchObject({
      auth: "token",
      query: {
        q: "",
        product_id: null,
        language: null,
        state: null,
        violation: null,
        deleted: "active",
        page_size: 50,
      },
    });
  });
  it("debounces only free text for exactly 300 ms and preserves literal query", async () => {
    vi.useFakeTimers();
    await mount();
    fireEvent.change(screen.getByLabelText("Search keys and translations"), {
      target: { value: "MiXeD %_[key]" },
    });
    await act(async () => vi.advanceTimersByTime(299));
    expect(searchTranslations).toHaveBeenCalledOnce();
    await act(async () => vi.advanceTimersByTime(1));
    expect(searchTranslations).toHaveBeenCalledTimes(2);
    expect(vi.mocked(searchTranslations).mock.lastCall?.[0]?.query?.q).toBe(
      "MiXeD %_[key]",
    );
  });
  it("Enter and explicit query clear dispatch immediately without duplicate debounce", async () => {
    vi.useFakeTimers();
    await mount();
    const input = screen.getByLabelText("Search keys and translations");
    fireEvent.change(input, { target: { value: "Pending" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await flush();
    expect(searchTranslations).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
    await flush();
    expect(vi.mocked(searchTranslations).mock.lastCall?.[0]?.query?.q).toBe("");
    await act(async () => vi.advanceTimersByTime(400));
    expect(searchTranslations).toHaveBeenCalledTimes(3);
  });
  it("deleting the last query character dispatches immediately", async () => {
    vi.useFakeTimers();
    await mount();
    const input = screen.getByLabelText("Search keys and translations");
    fireEvent.change(input, { target: { value: "text" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await flush();
    fireEvent.change(input, { target: { value: "" } });
    await flush();
    expect(vi.mocked(searchTranslations).mock.lastCall?.[0]?.query?.q).toBe("");
    expect(searchTranslations).toHaveBeenCalledTimes(3);
  });
  it("applies explicit filters immediately and keeps focus on the changed control", async () => {
    await mount();
    await choose("Approval state", "Approved");
    expect(vi.mocked(searchTranslations).mock.lastCall?.[0]?.query?.state).toBe(
      "approved",
    );
    expect(
      screen.getByRole("combobox", { name: "Approval state" }),
    ).toHaveFocus();
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });
  it("uses principal preferences only after global and product language authorization", async () => {
    preference("alpha", "it");
    const scoped = deferred<never>();
    vi.mocked(listTranslationOptions)
      .mockResolvedValueOnce({ data: options } as never)
      .mockReturnValueOnce(scoped.promise);
    render(tree());
    await flush();
    expect(searchTranslations).not.toHaveBeenCalled();
    expect(vi.mocked(listTranslationOptions).mock.lastCall?.[0]?.query).toEqual(
      { product_id: "alpha" },
    );
    await act(async () =>
      scoped.resolve({
        data: { ...options, languages: [{ code: "en", label: "English" }] },
      } as never),
    );
    await flush();
    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({ product_id: "alpha", language: null });
  });
  it.each([
    "{bad",
    JSON.stringify({ version: 1, productId: "foreign", language: "xx" }),
  ])(
    "safely discards malformed or inaccessible preferences: %s",
    async (stored) => {
      localStorage.setItem(translationPreferenceKey(principal.id), stored);
      await mount();
      expect(
        vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
      ).toMatchObject({ product_id: null, language: null });
    },
  );
  it("revalidates language before issuing a changed-product search", async () => {
    preference(null, "it");
    await mount();
    vi.mocked(listTranslationOptions).mockImplementation(
      async ({ query } = {}) =>
        ({
          data:
            query?.product_id === "beta"
              ? { ...options, languages: [{ code: "en", label: "English" }] }
              : options,
        }) as never,
    );
    await choose("Product", "Beta");
    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({ product_id: "beta", language: null });
    expect(
      vi
        .mocked(searchTranslations)
        .mock.calls.some(
          ([call]) =>
            call?.query?.product_id === "beta" &&
            call?.query?.language === "it",
        ),
    ).toBe(false);
    expect(
      screen.getByRole("combobox", { name: "Language" }),
    ).toHaveTextContent("All languages");
  });
  it("clears query and all filters in one immediate request and persists only preferences", async () => {
    preference("alpha", "it");
    await mount();
    await choose("Deleted status", "Active and deleted");
    fireEvent.change(screen.getByLabelText("Search keys and translations"), {
      target: { value: "secret original content" },
    });
    const count = vi.mocked(searchTranslations).mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    await flush();
    expect(searchTranslations).toHaveBeenCalledTimes(count + 1);
    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({
      q: "",
      product_id: null,
      language: null,
      state: null,
      violation: null,
      deleted: "active",
    });
    expect(
      JSON.parse(localStorage.getItem(translationPreferenceKey(principal.id))!),
    ).toEqual({ version: 1, productId: null, language: null });
    expect(sessionStorage.length).toBe(0);
  });
  it("shows five loading skeleton rows and safe recoverable search failure", async () => {
    const pending = deferred<never>();
    vi.mocked(searchTranslations).mockReturnValueOnce(pending.promise);
    await mount();
    expect(screen.getByText("Loading translations")).toBeVisible();
    expect(
      document.querySelectorAll("[data-translation-skeleton]"),
    ).toHaveLength(5);
    await act(async () =>
      pending.resolve({ error: { message: "private provider body" } } as never),
    );
    await flush();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Translations could not be loaded",
    );
    expect(document.body).not.toHaveTextContent("private provider body");
    fireEvent.click(screen.getByRole("button", { name: "Retry search" }));
    await flush();
    expect(
      screen.getByRole("heading", { name: "No translations available" }),
    ).toBeVisible();
  });
  it("provides options-error retry without mounting an unauthorized query", async () => {
    vi.mocked(listTranslationOptions).mockResolvedValueOnce({
      error: {},
    } as never);
    await mount();
    expect(searchTranslations).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Retry search" }));
    await flush();
    expect(searchTranslations).toHaveBeenCalledOnce();
  });
  it("names active criteria when no result matches", async () => {
    await mount();
    fireEvent.change(screen.getByLabelText("Search keys and translations"), {
      target: { value: "unmatched <script>" },
    });
    fireEvent.keyDown(screen.getByLabelText("Search keys and translations"), {
      key: "Enter",
    });
    await flush();
    expect(
      screen.getByRole("heading", {
        name: "No translations match these filters",
      }),
    ).toBeVisible();
    expect(screen.getByText(/Active criteria:/)).toHaveTextContent(
      "unmatched <script>",
    );
    expect(document.querySelector("script")).toBeNull();
  });
  it("discards superseded search responses and composes one list with all loaded groups", async () => {
    const stale = deferred<never>();
    vi.mocked(searchTranslations).mockReturnValueOnce(stale.promise);
    await mount();
    const signal = vi.mocked(searchTranslations).mock.calls[0][0]?.signal;
    vi.mocked(searchTranslations).mockResolvedValueOnce({
      data: { items: [group("new")], next_cursor: "more" },
    } as never);
    fireEvent.change(screen.getByLabelText("Search keys and translations"), {
      target: { value: "new" },
    });
    expect(signal?.aborted).toBe(true);
    fireEvent.keyDown(screen.getByLabelText("Search keys and translations"), {
      key: "Enter",
    });
    await flush();
    await act(async () =>
      stale.resolve({
        data: { items: [group("old")], next_cursor: null },
      } as never),
    );
    await flush();
    expect(screen.queryByRole("link", { name: "Open details old" })).toBeNull();
    vi.mocked(searchTranslations).mockResolvedValueOnce({
      data: { items: [group("second")], next_cursor: null },
    } as never);
    fireEvent.click(
      screen.getByRole("button", { name: "Load more translations" }),
    );
    await flush();
    expect(screen.getAllByRole("list")).toHaveLength(1);
    expect(
      listProps.mock.lastCall?.[0].items.map(
        (item: TranslationGroupSummaryResponse) => item.id,
      ),
    ).toEqual(["new", "second"]);
  });
  it("restores loaded pages, query, scroll and invoking focus on Back before preferences", async () => {
    vi.mocked(searchTranslations).mockResolvedValue({
      data: { items: [group("memory")], next_cursor: null },
    } as never);
    await mount();
    fireEvent.change(screen.getByLabelText("Search keys and translations"), {
      target: { value: "memory query" },
    });
    fireEvent.keyDown(screen.getByLabelText("Search keys and translations"), {
      key: "Enter",
    });
    await flush();
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 480,
    });
    fireEvent.click(screen.getByRole("link", { name: "Open details memory" }));
    await flush();
    preference("beta", "en");
    const count = vi.mocked(searchTranslations).mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    await flush();
    expect(screen.getByLabelText("Search keys and translations")).toHaveValue(
      "memory query",
    );
    expect(screen.getByRole("combobox", { name: "Product" })).toHaveTextContent(
      "All products",
    );
    expect(searchTranslations).toHaveBeenCalledTimes(count);
    expect(window.scrollTo).toHaveBeenCalledWith({
      top: 480,
      behavior: "instant",
    });
    expect(
      screen.getByRole("link", { name: "Open details memory" }),
    ).toHaveFocus();
  });
  it.each(["new query", ""])(
    "preserves edited query %j while Back navigation reauthorizes saved results",
    async (nextQuery) => {
      vi.mocked(searchTranslations).mockResolvedValue({
        data: { items: [group("memory")], next_cursor: null },
      } as never);
      await mount();
      fireEvent.change(screen.getByLabelText("Search keys and translations"), {
        target: { value: "memory query" },
      });
      fireEvent.keyDown(screen.getByLabelText("Search keys and translations"), {
        key: "Enter",
      });
      await flush();
      fireEvent.click(
        screen.getByRole("link", { name: "Open details memory" }),
      );
      await flush();

      const pending = deferred<never>();
      vi.mocked(listTranslationOptions).mockReturnValueOnce(pending.promise);
      const count = vi.mocked(searchTranslations).mock.calls.length;
      fireEvent.click(screen.getByRole("button", { name: "Back" }));
      await flush();
      fireEvent.change(screen.getByLabelText("Search keys and translations"), {
        target: { value: nextQuery },
      });
      expect(searchTranslations).toHaveBeenCalledTimes(count);
      vi.mocked(searchTranslations).mockResolvedValueOnce({
        data: { items: [group("fresh")], next_cursor: null },
      } as never);
      await act(async () => pending.resolve({ data: options } as never));
      await flush();

      expect(screen.getByLabelText("Search keys and translations")).toHaveValue(
        nextQuery,
      );
      expect(searchTranslations).toHaveBeenCalledTimes(count + 1);
      expect(vi.mocked(searchTranslations).mock.lastCall?.[0]?.query?.q).toBe(
        nextQuery,
      );
      expect(
        screen.queryByRole("link", { name: "Open details memory" }),
      ).toBeNull();
      expect(
        screen.getByRole("link", { name: "Open details fresh" }),
      ).toBeVisible();
    },
  );
  it("drops search memory and cancels pending work when principal changes", async () => {
    const pending = deferred<never>();
    vi.mocked(searchTranslations).mockReturnValueOnce(pending.promise);
    const view = await mount();
    const signal = vi.mocked(searchTranslations).mock.calls[0][0]?.signal;
    fireEvent.change(screen.getByLabelText("Search keys and translations"), {
      target: { value: "private query" },
    });
    view.rerender(tree({ ...principal, id: "principal-b" }, "new-token"));
    await flush();
    await act(async () =>
      pending.resolve({
        data: { items: [group("private")], next_cursor: null },
      } as never),
    );
    await flush();
    expect(signal?.aborted).toBe(true);
    expect(screen.getByLabelText("Search keys and translations")).toHaveValue(
      "",
    );
    expect(screen.queryByText("Open details private")).toBeNull();
  });

  it("preserves literal query through token rotation while reauthorizing options and results", async () => {
    const view = await mount();
    fireEvent.change(screen.getByLabelText("Search keys and translations"), {
      target: { value: "remember across refresh" },
    });
    fireEvent.keyDown(screen.getByLabelText("Search keys and translations"), {
      key: "Enter",
    });
    await flush();
    view.rerender(tree(principal, "rotated-token"));
    await flush();
    expect(screen.getByLabelText("Search keys and translations")).toHaveValue(
      "remember across refresh",
    );
    expect(vi.mocked(searchTranslations).mock.lastCall?.[0]).toMatchObject({
      auth: "rotated-token",
      query: { q: "remember across refresh" },
    });
  });

  it("keeps search usable when browser preference storage is blocked", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("Denied", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("Denied", "SecurityError");
    });
    await mount();
    expect(searchTranslations).toHaveBeenCalledOnce();
    expect(screen.getByLabelText("Search keys and translations")).toHaveValue(
      "",
    );
  });
});
