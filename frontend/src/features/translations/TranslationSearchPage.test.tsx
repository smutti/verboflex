import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  Link,
  createMemoryRouter,
  RouterProvider,
  Outlet,
  MemoryRouter,
  Route,
  Routes,
  useNavigate,
  useOutletContext,
} from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  listTranslationOptions,
  listTranslationComments,
  createTranslationComment,
  listTranslationReviewActivity,
  searchMentionUsers,
  getTranslationGroup,
  saveTranslationProposal,
  type TranslationGroupDetailResponse,
  type TranslationKeySummary,
  type TranslationKeyPageResponse,
  type CurrentUserResponse,
  type TranslationGroupSummaryResponse,
} from "../../api/client";
import { DirtyFormNavigationProvider } from "../../components/navigation/DirtyFormNavigationGuard";
import type { TranslationContextSelection } from "./TranslationResultList";
import { TranslationSearchPage } from "./TranslationSearchPage";
import { TranslationsWorkspace } from "./TranslationsWorkspace";
import type { TranslationsWorkspaceContext } from "./TranslationsWorkspace";
import { translationPreferenceKey } from "./translationPreferences";
import { translationSearchIdentity } from "./useTranslationSearch";

const searchTranslations = vi.hoisted(() => vi.fn());
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  listAuthoringRequests: vi
    .fn()
    .mockResolvedValue({ data: { items: [], next_after: null } }),
  listTranslationOptions: vi.fn(),
  listTranslationComments: vi.fn(),
  createTranslationComment: vi.fn(),
  listTranslationReviewActivity: vi.fn(),
  searchMentionUsers: vi.fn(),
  searchTranslationKeys: async (request: unknown) => {
    const response = await searchTranslations(request);
    // Legacy group fixtures emulate the key endpoint's complete selected slots.
    const query = (
      request as { query: { visible_languages?: string[]; language?: string } }
    ).query;
    if (
      response?.data?.items.length &&
      !("slots" in response.data.items[0]) &&
      (query.language || query.visible_languages)
    ) {
      const page = keyPage(response.data);
      const visible = query.visible_languages ?? ["en", "it"];
      page.visible_languages = visible;
      page.items = page.items.map((item) => ({
        ...item,
        slots: visible.map((language) => {
          const slot = item.slots.find(
            (candidate) => candidate.language === language,
          );
          if (slot)
            return {
              ...slot,
              matches_filters: !query.language || query.language === language,
            };
          return {
            ...item.slots[0],
            language,
            language_label: language,
            group_id: null,
            editable: false,
            edit_field: null,
            kind:
              language === item.base_language
                ? ("source_context" as const)
                : ("absent" as const),
            preview_kind:
              language === item.base_language
                ? ("context" as const)
                : ("absent" as const),
            effective_text:
              language === item.base_language ? item.source_text : null,
            matches_filters: false,
            value_count: 0,
            selector_kinds: [],
            states: [],
            read_only_reason:
              language === item.base_language
                ? ("source_context" as const)
                : ("absent" as const),
            no_max_count: 0,
            over_limit_count: 0,
            within_limit_count: 0,
            pending_change: null,
          };
        }),
      }));
      return { ...response, data: page };
    }
    return response?.data
      ? { ...response, data: keyPage(response.data) }
      : response;
  },
  getTranslationGroup: vi.fn(),
  saveTranslationProposal: vi.fn(),
}));
const listProps = vi.hoisted(() => vi.fn());
vi.mock("./TranslationResultList", () => ({
  TranslationResultList: (props: {
    items: TranslationKeySummary[];
    nextCursor: string | null;
    onLoadMore: () => void;
    onOpenDetails: (id: string) => void;
    detailsBasePath: string;
    onEditTranslation: (id: string, trigger: HTMLElement) => void;
    editor: React.ReactNode;
    onOpenContext: (selection: TranslationContextSelection) => void;
  }) => {
    listProps(props);
    const groups = props.items.flatMap((item) =>
      item.slots
        .filter((slot) => slot.group_id)
        .map((slot) => ({ ...item, id: slot.group_id! })),
    );
    return (
      <div role="list" aria-label="Translation results">
        {groups.map((item) => (
          <Link
            key={item.id}
            to={`${props.detailsBasePath}/${item.id}`}
            data-translation-group-id={item.id}
            onClick={() => props.onOpenDetails(item.id)}
          >
            Open details {item.raw_key}
          </Link>
        ))}
        {props.nextCursor && (
          <button onClick={props.onLoadMore}>Load more translations</button>
        )}
        {groups.map((item) => (
          <button
            key={`edit-${item.id}`}
            data-translation-editor-trigger={item.id}
            onClick={(event) =>
              props.onEditTranslation(item.id, event.currentTarget)
            }
          >
            Edit {item.id}
          </button>
        ))}
        {props.items.flatMap((item) =>
          item.slots
            .filter((slot) => slot.group_id)
            .map((slot) => (
              <button
                key={`context-${slot.group_id}`}
                onClick={(event) =>
                  props.onOpenContext({
                    groupId: slot.group_id,
                    language: slot.language,
                    section: "comments",
                    trigger: event.currentTarget,
                    item,
                    slot,
                  })
                }
              >
                Comments {slot.group_id}
              </button>
            )),
        )}
        {props.editor}
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
    comment_count: 0,
    pending_change: null,
    ...changes,
  };
}
function keyPage(data: {
  items: TranslationGroupSummaryResponse[] | TranslationKeySummary[];
  next_cursor?: string | null;
}): TranslationKeyPageResponse {
  const items = data.items.map((item) =>
    "slots" in item
      ? item
      : {
          translation_key_id: item.id,
          scope_id: "scope",
          product_id: item.product_id,
          product_name: item.product_name,
          raw_key: item.raw_key,
          base_language: item.source_language ?? "en",
          rank: item.rank,
          key_truncated: false,
          source_text: item.source_text,
          source_truncated: false,
          slots: [
            {
              language: item.language,
              language_label: item.language_label,
              group_id: item.id,
              kind: "imported" as const,
              editable: !item.is_deleted,
              edit_field: "translated_text" as const,
              effective_text: item.translated_text,
              is_deleted: item.is_deleted,
              matches_filters: true,
              no_max_count: item.no_max_count,
              over_limit_count: item.over_limit_count,
              within_limit_count: item.within_limit_count,
              pending_change: item.pending_change ?? null,
              preview_kind: "scalar" as const,
              provenance: null,
              read_only_reason: null,
              selector_kinds: item.selector_kinds,
              source_changed: false,
              states: item.states,
              text_truncated: false,
              value_count: item.value_count,
              comment_count: item.comment_count,
            },
          ],
        },
  );
  return {
    items,
    next_cursor: data.next_cursor ?? null,
    visible_languages: items[0]?.slots.map((slot) => slot.language) ?? ["it"],
    available_languages: options.languages,
    available_languages_truncated: false,
    default_selection_capped: false,
  };
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { resolve, promise };
}
function editable(id: string): TranslationGroupDetailResponse {
  return {
    id,
    product_id: "alpha",
    product_name: "Alpha",
    raw_key: id,
    language: "it",
    language_label: "Italian",
    base_language: "en",
    base_maximum: null,
    explicit_maximum: null,
    constraint_version: null,
    is_deleted: false,
    mutation_eligible: true,
    review_eligible: true,
    comment_count: 0,
    states: ["draft"],
    state_summary: "draft",
    pending_change: null,
    values: [
      {
        id,
        source_text: "Source",
        translated_text: "Old",
        display_text: "Old",
        structure: [],
        selector_kind: "scalar",
        selector_version: 1,
        selector_digest: "a".repeat(64),
        selector_fields: null,
        is_deleted: false,
        deleted_at: null,
        review_state: "draft",
        grapheme_count: 3,
        constraint: {
          actual: 3,
          maximum: null,
          source: "none",
          status: "no_max",
          overage: null,
        },
        provenance: {
          repository_id: "repo",
          repository_name: "Repo",
          repository_side: "translations",
          branch: "main",
          path: "it.json",
          format: "json",
          commit_hash: "a".repeat(40),
          execution_id: "execution",
          line: null,
          column: null,
        },
        history_has_more: false,
        history: [
          {
            revision_number: 1,
            revision_digest: "b".repeat(64),
            review_state: "draft",
            is_deleted: false,
            created_at: "2026-10-01T00:00:00Z",
            commit_hash: "a".repeat(40),
            execution_id: "execution",
          },
        ],
      },
    ],
  };
}
const flush = () =>
  act(async () => {
    for (let i = 0; i < 12; i++) await Promise.resolve();
  });
function Detail() {
  const navigate = useNavigate();
  const context = useOutletContext<TranslationsWorkspaceContext>();
  return (
    <>
      <h1>Details</h1>
      <button onClick={() => navigate(-1)}>Back</button>
      <Link to={context.searchPath}>Back to search</Link>
      <Link to={`${context.searchPath}?language=it`}>Fresh Italian search</Link>
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
              detailsBasePath={
                lockedProduct
                  ? `/products/${lockedProduct.id}/strings`
                  : "/translations"
              }
              searchPath={
                lockedProduct
                  ? `/products/${lockedProduct.id}/strings`
                  : "/translations"
              }
            />
          }
        >
          <Route
            index={!lockedProduct}
            path={lockedProduct ? "strings" : undefined}
            element={<TranslationSearchPage />}
          />
          <Route
            path={lockedProduct ? "strings/:id" : ":id"}
            element={<Detail />}
          />
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
  await user.click(screen.getByRole("button", { name: /^Filter/ }));
  const names: Record<string, string> = {
    Language: "Matching language",
    "Approval state": "Imported approval state",
    "Length status": "Imported length status",
  };
  await user.click(
    screen.getByRole("combobox", { name: names[label] ?? label }),
  );
  await user.click(screen.getByRole("option", { name }));
  await user.click(screen.getByRole("button", { name: "Apply filters" }));
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
  vi.mocked(listTranslationComments).mockResolvedValue({
    data: { items: [], older_cursor: null },
  } as never);
  vi.mocked(listTranslationReviewActivity).mockResolvedValue({
    data: { items: [], older_cursor: null },
  } as never);
  vi.mocked(searchMentionUsers).mockResolvedValue({ data: [] } as never);
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
  it.each(["URL", "restored preferences", "default reset"])(
    "keeps the bilingual focus visible outside server defaults from %s",
    async (entry) => {
      const item = keyPage({ items: [group("focused", { language: "it" })] })
        .items[0];
      const source = {
        ...item.slots[0],
        group_id: "source",
        language: "en",
        matches_filters: false,
      };
      searchTranslations.mockImplementation(async (request) => ({
        data: keyPage({
          items: [
            {
              ...item,
              slots: request.query.visible_languages
                ? [source, ...item.slots]
                : [source],
            },
          ],
        }),
      }));
      if (entry === "restored preferences") {
        localStorage.setItem(
          translationPreferenceKey(principal.id, "alpha"),
          JSON.stringify({
            version: 2,
            productId: "alpha",
            language: "it",
            viewMode: "bilingual",
            visibleLanguages: ["en"],
          }),
        );
      }
      render(
        tree(
          principal,
          "token",
          "/products/alpha/strings" +
            (entry === "restored preferences" ? "" : "?language=it"),
          {
            id: "alpha",
            name: "Alpha",
          },
        ),
      );
      await flush();
      if (entry === "default reset") {
        await userEvent.click(
          screen.getByRole("button", { name: /^Languages/ }),
        );
        await userEvent.click(
          screen.getByRole("button", { name: "Use default languages" }),
        );
        await flush();
      }
      expect(searchTranslations.mock.lastCall?.[0].query).toMatchObject({
        language: "it",
        visible_languages: ["en", "it"],
      });
      expect(
        screen.getAllByRole("link", { name: "Open details focused" }),
      ).toHaveLength(2);
    },
  );
  it("applies draft AND conditions once through the key API and cancels without a request", async () => {
    const user = userEvent.setup();
    vi.mocked(searchTranslations).mockResolvedValue({
      data: {
        items: [
          group("matched-key", {
            states: ["approved"],
            state_summary: "approved",
            over_limit_count: 1,
            has_over_limit: true,
          }),
        ],
        next_cursor: null,
      },
    } as never);
    await mount();
    const count = vi.mocked(searchTranslations).mock.calls.length;
    await user.click(screen.getByRole("button", { name: /^Filter/ }));
    await user.click(
      screen.getByRole("combobox", { name: "Imported approval state" }),
    );
    await user.click(screen.getByRole("option", { name: "Approved" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(searchTranslations).toHaveBeenCalledTimes(count);
    await user.click(screen.getByRole("button", { name: /^Filter/ }));
    await user.click(
      screen.getByRole("combobox", { name: "Imported approval state" }),
    );
    await user.click(screen.getByRole("option", { name: "Approved" }));
    await user.click(
      screen.getByRole("combobox", { name: "Imported length status" }),
    );
    await user.click(screen.getByRole("option", { name: "Over limit" }));
    await user.click(screen.getByRole("button", { name: "Apply filters" }));
    await flush();
    expect(searchTranslations).toHaveBeenCalledTimes(count + 1);
    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({
      state: "approved",
      violation: "over_limit",
      page_size: 50,
    });
    expect(
      screen.getByRole("link", { name: "Open details matched-key" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Remove Imported state: Approved" }),
    );
    await flush();
    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({ state: null, violation: "over_limit" });
  });
  it("saves in place and preserves dirty filter cancellation", async () => {
    const first = Array.from({ length: 50 }, (_, i) => group(`entry-${i}`));
    let pageAttempts = 0;
    vi.mocked(searchTranslations).mockImplementation(async (request) => {
      if (request?.query?.cursor && ++pageAttempts === 1)
        throw new Error("Next page unavailable");
      return {
        data: request?.query?.cursor
          ? { items: [group("entry-50")], next_cursor: null }
          : { items: first, next_cursor: "page-two" },
      } as never;
    });
    vi.mocked(getTranslationGroup).mockImplementation(
      async (request) =>
        ({ data: editable(request.path.translation_group_id) }) as never,
    );
    vi.mocked(saveTranslationProposal).mockImplementation(
      async (request) =>
        ({
          data: {
            translation_group_id: request.path.translation_group_id,
            language: "it",
            version: 1,
            state: "draft",
            reconciliation_required: false,
            updated_at: "2026-10-01T01:00:00Z",
            updated_by: principal.id,
            activity: null,
            published: request.body.values.map((v) => ({
              ...v,
              text: "Old",
              review_state: "draft",
              revision_number: 1,
              revision_digest: "b".repeat(64),
            })),
            pending: request.body.values.map((v) => ({
              ...v,
              text: v.proposed_text,
              grapheme_count: v.proposed_text.length,
              maximum: null,
              is_over_limit: false,
              approval_eligible: true,
              submission_eligible: true,
            })),
          },
        }) as never,
    );
    render(tree({ ...principal, roles: ["translator"] }));
    await flush();
    await userEvent.click(
      screen.getByRole("button", { name: "Edit entry-49" }),
    );
    await flush();
    await userEvent.clear(
      screen.getByRole("textbox", { name: "Proposed translation" }),
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Proposed translation" }),
      "Fresh text",
    );
    await userEvent.click(screen.getByRole("button", { name: /^Filter/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Needs translation" }),
    );
    expect(await screen.findByRole("alertdialog")).toHaveTextContent(
      "Leave without saving?",
    );
    await userEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(
      screen.getByRole("textbox", { name: "Proposed translation" }),
    ).toHaveValue("Fresh text");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("button", { name: "Save and next" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await flush();
    expect(saveTranslationProposal).toHaveBeenCalledTimes(1);
    expect(getTranslationGroup).toHaveBeenLastCalledWith(
      expect.objectContaining({ path: { translation_group_id: "entry-49" } }),
    );
    expect(
      screen.queryByRole("button", { name: "Retry next translation" }),
    ).toBeNull();
    const beforeBack = searchTranslations.mock.calls.length;
    await userEvent.click(
      screen.getByRole("link", { name: "Open details entry-49" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    await flush();
    expect(searchTranslations).toHaveBeenCalledTimes(beforeBack + 1);
    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query?.cursor,
    ).toBeNull();
  });
  it("validates the requested language against product-scoped options even when absent from the global list", async () => {
    vi.mocked(listTranslationOptions).mockImplementation(
      async (request) =>
        ({
          data: request?.query?.product_id
            ? options
            : { ...options, languages: [] },
        }) as never,
    );
    render(
      tree(principal, "token", "/products/alpha/strings?language=it", {
        id: "alpha",
        name: "Alpha",
      }),
    );
    await flush();
    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({ product_id: "alpha", language: "it" });
  });
  it("applies a language deep link on direct navigation and reload without changing the locked product", async () => {
    preference("beta", "en");
    for (let attempt = 0; attempt < 2; attempt++) {
      const view = render(
        tree(
          principal,
          "token",
          "/products/alpha/strings?product_id=beta&language=it",
          { id: "alpha", name: "Alpha" },
        ),
      );
      await flush();
      expect(
        screen.getByRole("button", { name: "Remove Matching language: it" }),
      ).toBeVisible();
      expect(
        vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
      ).toMatchObject({ product_id: "alpha", language: "it" });
      view.unmount();
    }
  });

  it.each(["not-a-language", "vi", "%3Cscript%3E"])(
    "sanitizes unavailable or invalid language %s through scoped options",
    async (language) => {
      render(
        tree(
          principal,
          "token",
          `/products/alpha/strings?language=${language}`,
          { id: "alpha", name: "Alpha" },
        ),
      );
      await flush();
      expect(
        vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
      ).toMatchObject({ product_id: "alpha", language: null });
    },
  );
  it("locks product-scoped search and retains the product when filters are cleared", async () => {
    render(
      tree(
        { ...principal, roles: ["translator"] },
        "token",
        "/products/alpha/strings",
        {
          id: "alpha",
          name: "Alpha",
        },
      ),
    );
    await flush();

    expect(screen.queryByRole("combobox", { name: "Product" })).toBeNull();
    expect(screen.queryByText("Searching only in Alpha")).toBeNull();
    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({ product_id: "alpha" });

    await choose("Language", "Italian (it)");
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    await flush();

    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({ product_id: "alpha", language: null });
    expect(screen.getAllByRole("button", { name: "New key" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Glossary" })).toHaveLength(1);
  });

  it("automatically applies a valid product filter from the imported-strings URL", async () => {
    preference("beta", null);

    render(tree(principal, "token", "/translations?product_id=alpha"));
    await flush();

    expect(
      screen.getByRole("button", { name: "Remove Product: Alpha" }),
    ).toBeVisible();
    expect(vi.mocked(listTranslationOptions)).toHaveBeenCalledWith(
      expect.objectContaining({ query: { product_id: "alpha" } }),
    );
    expect(
      vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
    ).toMatchObject({ product_id: "alpha" });
  });

  it.each(["product", "language"])(
    "does not restore an unrelated %s snapshot over an explicit URL",
    async (mismatch) => {
      const filters = {
        productId: mismatch === "product" ? "beta" : "alpha",
        language: mismatch === "product" ? null : "en",
        state: "approved" as const,
        violation: null,
        deleted: "active" as const,
      };
      render(
        <MemoryRouter
          initialEntries={["/translations?product_id=alpha&language=it"]}
        >
          <Routes>
            <Route
              element={
                <Outlet
                  context={{
                    principal,
                    accessToken: "token",
                    setSnapshot: vi.fn(),
                    detailsBasePath: "/translations",
                    searchPath: "/translations",
                    snapshot: {
                      version: 2,
                      query: "",
                      filters,
                      pages: [
                        {
                          items: [
                            group("foreign", {
                              product_id: "beta",
                              states: ["approved"],
                              state_summary: "approved",
                            }),
                          ],
                          next_cursor: null,
                        },
                      ],
                      requestIdentity: translationSearchIdentity("", filters),
                      scrollAnchor: 480,
                      focusedGroupId: "foreign",
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
      expect(
        screen.getByRole("button", { name: "Remove Product: Alpha" }),
      ).toBeVisible();
      expect(
        vi.mocked(searchTranslations).mock.lastCall?.[0]?.query,
      ).toMatchObject({
        product_id: "alpha",
        language: "it",
        state: null,
        q: "",
      });
      expect(
        screen.queryByRole("link", { name: "Open details foreign" }),
      ).not.toBeInTheDocument();
      expect(window.scrollTo).not.toHaveBeenCalledWith({
        top: 480,
        behavior: "instant",
      });
    },
  );

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
    expect(
      screen.queryByRole("button", { name: /^Remove Product:/ }),
    ).toBeNull();
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
                      version: 2,
                      query: "",
                      filters,
                      pages: [
                        keyPage({
                          items: [group("first")],
                          next_cursor: "next",
                        }),
                      ],
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
    expect(screen.getByRole("button", { name: /^Filter/ })).toBeDisabled();
    expect(screen.getByLabelText("Search keys and translations")).toHaveValue(
      "",
    );
    await act(async () => pending.resolve({ data: options } as never));
    await flush();
    expect(
      screen.getByLabelText("Search keys and translations"),
    ).toHaveAttribute("placeholder", "Enter a key or text");
    expect(
      screen.getByTitle(
        "Search original keys, source text, and translated text",
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
    expect(screen.getByRole("button", { name: /^Filter/ })).toHaveFocus();
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
      screen.queryByRole("button", { name: /^Remove Matching language:/ }),
    ).toBeNull();
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
    ).toEqual({
      version: 2,
      productId: null,
      language: null,
      viewMode: "multilingual",
      visibleLanguages: null,
    });
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
        (item: TranslationKeySummary) => item.translation_key_id,
      ),
    ).toEqual(["new", "second"]);
  });
  it.each(["global", "global-filter", "product", "filtered-url"])(
    "restores loaded pages, query, scroll and invoking focus on Back before preferences (%s)",
    async (scope) => {
      vi.mocked(searchTranslations).mockResolvedValue({
        data: { items: [group("memory")], next_cursor: null },
      } as never);
      const lockedProduct =
        scope === "product" ? { id: "alpha", name: "Alpha" } : undefined;
      render(
        tree(
          principal,
          "token",
          scope === "product"
            ? "/products/alpha/strings"
            : scope === "filtered-url"
              ? "/translations?product_id=alpha"
              : "/translations",
          lockedProduct,
        ),
      );
      await flush();
      if (scope === "global-filter") await choose("Product", "Alpha");
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
      fireEvent.click(
        screen.getByRole("link", { name: "Open details memory" }),
      );
      await flush();
      preference("beta", "en");
      const count = vi.mocked(searchTranslations).mock.calls.length;
      if (scope === "product") {
        const back = screen.getByRole("link", { name: "Back to search" });
        back.focus();
        await userEvent.keyboard("{Enter}");
      } else fireEvent.click(screen.getByRole("button", { name: "Back" }));
      await flush();
      expect(screen.getByLabelText("Search keys and translations")).toHaveValue(
        "memory query",
      );
      if (scope === "product")
        expect(
          screen.queryByRole("combobox", { name: "Product" }),
        ).not.toBeInTheDocument();
      else if (scope !== "global")
        expect(
          screen.getByRole("button", { name: "Remove Product: Alpha" }),
        ).toBeVisible();
      else
        expect(
          screen.queryByRole("button", { name: /^Remove Product:/ }),
        ).toBeNull();
      expect(searchTranslations).toHaveBeenCalledTimes(count);
      expect(window.scrollTo).toHaveBeenCalledWith({
        top: 480,
        behavior: "instant",
      });
      expect(
        screen.getByRole("link", { name: "Open details memory" }),
      ).toHaveFocus();
    },
  );
  it.each(["change", "clear", "fresh-link"])(
    "restores a %s to the deep-linked language with query, pages, scroll and focus on browser Back",
    async (action) => {
      vi.mocked(searchTranslations).mockImplementation(
        async (request) =>
          ({
            data: {
              items: [
                group("memory", { language: request?.query?.language ?? "it" }),
              ],
              next_cursor: null,
            },
          }) as never,
      );
      render(
        tree(principal, "token", "/products/alpha/strings?language=it", {
          id: "alpha",
          name: "Alpha",
        }),
      );
      await flush();
      if (action !== "clear") await choose("Language", "English (en)");
      else {
        fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
        await flush();
      }
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
      const count = vi.mocked(searchTranslations).mock.calls.length;
      fireEvent.click(
        screen.getByRole("link", { name: "Open details memory" }),
      );
      await flush();
      if (action === "fresh-link") {
        fireEvent.click(
          screen.getByRole("link", { name: "Fresh Italian search" }),
        );
        await flush();
        expect(
          screen.getByRole("button", { name: "Remove Matching language: it" }),
        ).toBeVisible();
        expect(
          screen.getByLabelText("Search keys and translations"),
        ).toHaveValue("");
        expect(searchTranslations).toHaveBeenCalledTimes(count + 1);
        return;
      }
      fireEvent.click(screen.getByRole("button", { name: "Back" }));
      await flush();
      if (action === "change")
        expect(
          screen.getByRole("button", { name: "Remove Matching language: en" }),
        ).toBeVisible();
      else
        expect(
          screen.queryByRole("button", { name: /^Remove Matching language:/ }),
        ).toBeNull();
      expect(screen.getByLabelText("Search keys and translations")).toHaveValue(
        "memory query",
      );
      expect(searchTranslations).toHaveBeenCalledTimes(count);
      expect(window.scrollTo).toHaveBeenCalledWith({
        top: 480,
        behavior: "instant",
      });
      expect(
        screen.getByRole("link", { name: "Open details memory" }),
      ).toHaveFocus();
    },
  );
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

describe("exact locale cell editing", () => {
  function multilingual() {
    const item = keyPage({ items: [group("french", { language: "fr" })] })
      .items[0];
    item.slots.push({
      ...item.slots[0],
      language: "it",
      group_id: "italian",
      effective_text: "Ciao",
    });
    return item;
  }
  it("cancels without writes, guards a locale switch, and opens only the requested full group", async () => {
    searchTranslations.mockResolvedValue({
      data: keyPage({ items: [multilingual()] }),
    });
    vi.mocked(getTranslationGroup).mockImplementation(
      async (request) =>
        ({
          data: {
            ...editable(request.path.translation_group_id),
            language:
              request.path.translation_group_id === "french" ? "fr" : "it",
          },
        }) as never,
    );
    render(tree({ ...principal, roles: ["translator"] }));
    await flush();
    const trigger = screen.getByRole("button", { name: "Edit french" });
    await userEvent.click(trigger);
    await flush();
    const field = screen.getByRole("textbox", { name: "Proposed translation" });
    await userEvent.type(field, " unsaved French");
    await userEvent.click(screen.getByRole("button", { name: "Edit italian" }));
    await userEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(field).toHaveValue("Old unsaved French");
    expect(getTranslationGroup).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(saveTranslationProposal).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("textbox", { name: "Proposed translation" }),
    ).toBeNull();
    expect(trigger).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "Edit italian" }));
    await flush();
    expect(getTranslationGroup).toHaveBeenLastCalledWith(
      expect.objectContaining({ path: { translation_group_id: "italian" } }),
    );
    expect(
      screen.getByRole("textbox", { name: "Proposed translation" }),
    ).toHaveValue("Old");
  });
  it("closes a saved inline editor, shows the saved language and restores it on reopen", async () => {
    const item = multilingual();
    const saved = new Map<
      string,
      NonNullable<TranslationGroupDetailResponse["pending_change"]>
    >();
    // A successful save may remove the key from the current filtered results.
    searchTranslations.mockImplementation(async () => ({
      data: keyPage({ items: saved.size ? [] : [item] }),
    }));
    vi.mocked(getTranslationGroup).mockImplementation(
      async (request) =>
        ({
          data: {
            ...editable(request.path.translation_group_id),
            language:
              request.path.translation_group_id === "french" ? "fr" : "it",
            pending_change:
              saved.get(request.path.translation_group_id) ?? null,
          },
        }) as never,
    );
    vi.mocked(saveTranslationProposal).mockImplementation(async (request) => {
      const id = request.path.translation_group_id;
      const pending = request.body.values.map((value) => ({
        ...value,
        text: value.proposed_text,
        grapheme_count: value.proposed_text.length,
        maximum: null,
        is_over_limit: false,
        approval_eligible: true,
        submission_eligible: true,
      }));
      saved.set(id, {
        version: 1,
        state: "draft",
        reconciliation_required: false,
        updated_at: "2026-10-01T00:00:00Z",
        updated_by: principal.id,
        values: pending,
      });
      return {
        data: {
          ...saved.get(id),
          translation_group_id: id,
          language: id === "french" ? "fr" : "it",
          pending,
          published: request.body.values.map((value) => ({
            ...value,
            text: "Old",
            review_state: "draft",
            revision_number: 1,
            revision_digest: "b".repeat(64),
          })),
          activity: null,
        },
      } as never;
    });
    render(tree({ ...principal, roles: ["translator"] }));
    await flush();
    for (const [id, text] of [
      ["french", "Bonjour"],
      ["italian", "Ciao"],
    ]) {
      await userEvent.click(screen.getByRole("button", { name: `Edit ${id}` }));
      await flush();
      const field = screen.getByRole("textbox", {
        name: "Proposed translation",
      });
      await userEvent.clear(field);
      await userEvent.type(field, text);
      await userEvent.click(screen.getByRole("button", { name: "Save" }));
      await flush();
      expect(
        screen.queryByRole("textbox", { name: "Proposed translation" }),
      ).toBeNull();
      expect(screen.getByText("Translation saved as Draft.")).toBeVisible();
      expect(screen.getByRole("button", { name: `Edit ${id}` })).toHaveFocus();
      const displayed = listProps.mock.lastCall?.[0]
        .items as TranslationKeySummary[];
      expect(
        displayed
          .flatMap((key) => key.slots)
          .find((slot) => slot.group_id === id)?.effective_text,
      ).toBe(text);
    }
    expect(
      vi
        .mocked(saveTranslationProposal)
        .mock.calls.map(([request]) => [
          request.path.translation_group_id,
          request.body.values.map((value) => value.proposed_text),
        ]),
    ).toEqual([
      ["french", ["Bonjour"]],
      ["italian", ["Ciao"]],
    ]);
    expect(saved.get("french")?.values[0].text).toBe("Bonjour");
    expect(item.slots[0].effective_text).toBe("Translated");
    expect(item.slots[1].effective_text).toBe("Ciao");
    await userEvent.click(screen.getByRole("button", { name: "Edit italian" }));
    await flush();
    const field = screen.getByRole("textbox", { name: "Proposed translation" });
    expect(field).toHaveValue("Ciao");
    vi.mocked(saveTranslationProposal).mockResolvedValue({
      error: {},
    } as never);
    await userEvent.type(field, " again");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await flush();
    expect(field).toHaveValue("Ciao again");
    expect(screen.getByText("Translation was not saved")).toBeVisible();
    expect(
      vi.mocked(saveTranslationProposal).mock.lastCall?.[0].body
        .expected_version,
    ).toBe(1);
  });
  it("disables the previous locale while the next editor detail is loading", async () => {
    searchTranslations.mockResolvedValue({
      data: keyPage({ items: [multilingual()] }),
    });
    const pending = deferred<never>();
    vi.mocked(getTranslationGroup)
      .mockResolvedValueOnce({
        data: { ...editable("french"), language: "fr" },
      } as never)
      .mockReturnValueOnce(pending.promise);
    render(tree({ ...principal, roles: ["translator"] }));
    await flush();
    await userEvent.click(screen.getByRole("button", { name: "Edit french" }));
    await flush();
    const previous = screen.getByRole("textbox", {
      name: "Proposed translation",
    });
    await userEvent.click(screen.getByRole("button", { name: "Edit italian" }));
    expect(previous).toBeDisabled();
    await userEvent.type(previous, "must not become a French draft");
    expect(previous).toHaveValue("Old");
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    await act(async () =>
      pending.resolve({
        data: { ...editable("italian"), language: "it" },
      } as never),
    );
    await flush();
    expect(
      screen.getByRole("textbox", { name: "Proposed translation" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("textbox", { name: "Proposed translation" }),
    ).toHaveAttribute("lang", "it");
    expect(saveTranslationProposal).not.toHaveBeenCalled();
  });
  it.each(["foreign-language", "foreign-product", "keys-side", "viewer"])(
    "rejects %s authority before draft creation",
    async (reason) => {
      const item = multilingual();
      searchTranslations.mockResolvedValue({
        data: keyPage({ items: [item] }),
      });
      const detail = editable("french");
      detail.language = reason === "foreign-language" ? "it" : "fr";
      if (reason === "foreign-product") detail.product_id = "foreign";
      if (reason === "keys-side")
        detail.values[0].provenance!.repository_side = "keys";
      vi.mocked(getTranslationGroup).mockResolvedValue({
        data: detail,
      } as never);
      render(
        tree({
          ...principal,
          roles: [reason === "viewer" ? "viewer" : "translator"],
        }),
      );
      await flush();
      await userEvent.click(
        screen.getByRole("button", { name: "Edit french" }),
      );
      await flush();
      expect(
        screen.queryByRole("textbox", { name: "Proposed translation" }),
      ).toBeNull();
      expect(saveTranslationProposal).not.toHaveBeenCalled();
      if (reason === "viewer")
        expect(getTranslationGroup).not.toHaveBeenCalled();
    },
  );
});

describe("on-demand exact-language discussion", () => {
  function externalDetail(version: number, source = "New imported source") {
    const detail = editable("italian");
    detail.values[0].source_text = source;
    detail.values[0].history[0].revision_number = 2;
    detail.values[0].history[0].revision_digest = "c".repeat(64);
    if (version)
      detail.pending_change = {
        version,
        state: "draft",
        reconciliation_required: false,
        updated_at: "2026-10-01T02:00:00Z",
        updated_by: "another-actor",
        values: [
          {
            translation_value_id: "italian",
            selector_version: 1,
            selector_digest: "a".repeat(64),
            basis_revision_number: 2,
            basis_digest: "c".repeat(64),
            text: "External proposal",
            grapheme_count: 17,
            maximum: null,
            is_over_limit: false,
            approval_eligible: true,
            submission_eligible: true,
          },
        ],
      };
    return detail;
  }
  it.each([
    [false, false, 2],
    [true, false, 2],
    [false, true, 2],
    [true, true, 2],
    [false, false, 0],
    [true, false, 0],
    [false, true, 0],
    [true, true, 0],
  ])(
    "refreshes active editor context without rebasing (dirty %s, reopen %s, external version %s)",
    async (dirty, reopen, version) => {
      setup();
      vi.mocked(getTranslationGroup).mockResolvedValue({
        data: editable("italian"),
      } as never);
      vi.mocked(saveTranslationProposal).mockResolvedValue({
        error: {},
      } as never);
      render(tree({ ...principal, roles: ["product_manager_reviewer"] }));
      await flush();
      await userEvent.click(
        screen.getByRole("button", { name: "Edit italian" }),
      );
      await flush();
      const field = screen.getByRole("textbox", {
        name: "Proposed translation",
      });
      if (dirty) await userEvent.type(field, " local");
      if (reopen) {
        await userEvent.click(
          screen.getByRole("button", { name: "Comments italian" }),
        );
        await flush();
        await userEvent.click(
          screen.getByRole("button", { name: "Close translation context" }),
        );
      }
      vi.mocked(getTranslationGroup).mockResolvedValue({
        data: externalDetail(version),
      } as never);
      await userEvent.click(
        screen.getByRole("button", { name: "Comments italian" }),
      );
      await flush();
      if (version)
        expect(screen.getByText("Pending: draft · Version 2")).toBeVisible();
      if (dirty && version)
        expect(
          screen.getByRole("button", { name: "Approve translation" }),
        ).toBeDisabled();
      await userEvent.click(
        screen.getByRole("tab", { name: "Source changes" }),
      );
      expect(screen.getByText("New imported source")).toBeVisible();
      expect(field).toHaveValue(dirty ? "Old local" : "Old");
      await userEvent.click(
        screen.getByRole("button", { name: "Close translation context" }),
      );
      if (!dirty) await userEvent.type(field, " local");
      await userEvent.click(screen.getByRole("button", { name: "Save" }));
      expect(
        vi.mocked(saveTranslationProposal).mock.lastCall?.[0].body,
      ).toMatchObject({
        expected_version: 0,
        values: [
          {
            translation_value_id: "italian",
            proposed_text: "Old local",
            basis_revision_number: 1,
            basis_digest: "b".repeat(64),
          },
        ],
      });
    },
  );
  it("ignores a context response started before a newer local save", async () => {
    setup();
    const delayed = deferred<never>();
    vi.mocked(getTranslationGroup)
      .mockResolvedValueOnce({ data: editable("italian") } as never)
      .mockReturnValueOnce(delayed.promise)
      .mockResolvedValue({ data: externalDetail(3, "Saved source") } as never);
    vi.mocked(saveTranslationProposal).mockImplementation(
      async (request) =>
        ({
          data: {
            translation_group_id: "italian",
            language: "it",
            version: 3,
            state: "draft",
            reconciliation_required: false,
            updated_at: "2026-10-01T03:00:00Z",
            updated_by: principal.id,
            pending: request.body.values.map((value) => ({
              ...value,
              text: value.proposed_text,
              grapheme_count: value.proposed_text.length,
              maximum: null,
              is_over_limit: false,
              approval_eligible: true,
              submission_eligible: true,
            })),
            published: request.body.values.map((value) => ({
              ...value,
              text: "Old",
              review_state: "draft",
              revision_number: 1,
              revision_digest: "b".repeat(64),
            })),
            activity: null,
          },
        }) as never,
    );
    render(tree({ ...principal, roles: ["translator"] }));
    await flush();
    await userEvent.click(screen.getByRole("button", { name: "Edit italian" }));
    await flush();
    await userEvent.type(
      screen.getByRole("textbox", { name: "Proposed translation" }),
      " local",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Comments italian" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await flush();
    expect(screen.getByText("Pending: draft · Version 3")).toBeVisible();
    await act(async () =>
      delayed.resolve({ data: externalDetail(2, "Stale source") } as never),
    );
    await flush();
    expect(screen.getByText("Pending: draft · Version 3")).toBeVisible();
    expect(screen.queryByText("Pending: draft · Version 2")).toBeNull();
    await userEvent.click(screen.getByRole("tab", { name: "Source changes" }));
    expect(screen.getByText("Saved source")).toBeVisible();
    expect(screen.queryByText("Stale source")).toBeNull();
  });
  function setup() {
    const item = keyPage({ items: [group("french", { language: "fr" })] })
      .items[0];
    item.slots.push({ ...item.slots[0], language: "it", group_id: "italian" });
    searchTranslations.mockResolvedValue({ data: keyPage({ items: [item] }) });
    vi.mocked(getTranslationGroup).mockImplementation(
      async (request) =>
        ({
          data: {
            ...editable(request.path.translation_group_id),
            language:
              request.path.translation_group_id === "french" ? "fr" : "it",
          },
        }) as never,
    );
  }
  it("preserves an unsent French comment across tabs/close and guards Italian Keep/Discard", async () => {
    setup();
    render(tree({ ...principal, roles: ["translator"] }));
    await flush();
    expect(screen.queryByRole("dialog")).toBeNull();
    const french = screen.getByRole("button", { name: "Comments french" });
    await userEvent.click(french);
    const comment = await screen.findByRole("textbox", {
      name: "Add a comment",
    });
    await userEvent.type(comment, "Texte français @Ari");
    await userEvent.click(screen.getByRole("tab", { name: "History" }));
    await userEvent.click(screen.getByRole("tab", { name: "Comments" }));
    expect(comment).toHaveValue("Texte français @Ari");
    await userEvent.click(
      screen.getByRole("button", { name: "Close translation context" }),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(french).toHaveFocus();
    const requestsBeforeReopen =
      vi.mocked(getTranslationGroup).mock.calls.length;
    await userEvent.click(french);
    await flush();
    expect(vi.mocked(getTranslationGroup).mock.calls.length).toBeGreaterThan(
      requestsBeforeReopen,
    );
    expect(screen.getByRole("textbox", { name: "Add a comment" })).toBe(
      comment,
    );
    expect(comment).toHaveValue("Texte français @Ari");
    await userEvent.click(
      screen.getByRole("button", { name: "Comments italian" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(comment).toHaveValue("Texte français @Ari");
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "Translation context · fr",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Comments italian" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Discard changes" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("dialog")).toHaveTextContent(
        "Translation context · it",
      ),
    );
    expect(
      await screen.findByRole("textbox", { name: "Add a comment" }),
    ).toHaveValue("");
    expect(createTranslationComment).not.toHaveBeenCalled();
    expect(listTranslationComments).toHaveBeenLastCalledWith(
      expect.objectContaining({ path: { translation_group_id: "italian" } }),
    );
  });
  it("accepts or cancels mixed dirty replacement atomically", async () => {
    setup();
    render(tree({ ...principal, roles: ["translator"] }));
    await flush();
    await userEvent.click(screen.getByRole("button", { name: "Edit french" }));
    await flush();
    const translation = screen.getByRole("textbox", {
      name: "Proposed translation",
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Comments french" }),
    );
    const comment = await screen.findByRole("textbox", {
      name: "Add a comment",
    });
    await userEvent.type(comment, "Private discussion");
    await userEvent.type(translation, " Private translation");
    await userEvent.click(
      screen.getByRole("button", { name: "Comments italian" }),
    );
    expect(screen.getAllByRole("alertdialog")).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(translation).toHaveValue("Old Private translation");
    expect(comment).toHaveValue("Private discussion");
    await userEvent.click(
      screen.getByRole("button", { name: "Comments italian" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Discard changes" }),
    );
    expect(
      screen.queryByRole("textbox", { name: "Proposed translation" }),
    ).toBeNull();
    expect(
      await screen.findByRole("textbox", { name: "Add a comment" }),
    ).toHaveValue("");
    expect(saveTranslationProposal).not.toHaveBeenCalled();
    expect(createTranslationComment).not.toHaveBeenCalled();
  });
  it("blocks context replacement during submission and retains a failed comment", async () => {
    setup();
    const pending = deferred<never>();
    vi.mocked(createTranslationComment).mockReturnValue(pending.promise);
    render(tree({ ...principal, roles: ["translator"] }));
    await flush();
    await userEvent.click(
      screen.getByRole("button", { name: "Comments french" }),
    );
    await userEvent.type(
      await screen.findByRole("textbox", { name: "Add a comment" }),
      "In flight",
    );
    await userEvent.click(screen.getByRole("button", { name: "Post comment" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Comments italian" }),
    );
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "Translation context · fr",
    );
    await act(async () =>
      pending.resolve({
        error: {},
        response: new Response(null, { status: 503 }),
      } as never),
    );
    expect(screen.getByRole("textbox", { name: "Add a comment" })).toHaveValue(
      "In flight",
    );
  });
  it("registers the real composer with route navigation protection", async () => {
    setup();
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
                  principal={{ ...principal, roles: ["translator"] }}
                />
              ),
              children: [{ index: true, element: <TranslationSearchPage /> }],
            },
            { path: "/elsewhere", element: <h1>Elsewhere</h1> },
          ],
        },
      ],
      { initialEntries: ["/translations"] },
    );
    render(<RouterProvider router={router} />);
    await flush();
    await userEvent.click(
      screen.getByRole("button", { name: "Comments french" }),
    );
    await userEvent.type(
      await screen.findByRole("textbox", { name: "Add a comment" }),
      "Route protected",
    );
    await act(async () => {
      void router.navigate("/elsewhere");
    });
    await userEvent.click(
      await screen.findByRole("button", { name: "Keep editing" }),
    );
    expect(screen.getByRole("textbox", { name: "Add a comment" })).toHaveValue(
      "Route protected",
    );
    await act(async () => {
      void router.navigate("/elsewhere");
    });
    await userEvent.click(
      await screen.findByRole("button", { name: "Discard changes" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Elsewhere" }),
    ).toBeVisible();
  });
  it.each(["token", "roles"])(
    "retires a pending translation replacement when %s authority changes",
    async (kind) => {
      setup();
      const user = { ...principal, roles: ["translator" as const] };
      const view = render(tree(user));
      await flush();
      await userEvent.click(
        screen.getByRole("button", { name: "Edit french" }),
      );
      await flush();
      await userEvent.type(
        screen.getByRole("textbox", { name: "Proposed translation" }),
        " unsaved",
      );
      await userEvent.click(
        screen.getByRole("button", { name: "Edit italian" }),
      );
      expect(screen.getByRole("alertdialog")).toBeVisible();
      view.rerender(
        tree(
          kind === "roles" ? { ...user, roles: ["viewer"] } : user,
          kind === "token" ? "rotated" : "token",
        ),
      );
      await flush();
      expect(screen.queryByRole("alertdialog")).toBeNull();
      expect(
        screen.queryByRole("textbox", { name: "Proposed translation" }),
      ).toBeNull();
      expect(saveTranslationProposal).not.toHaveBeenCalled();
    },
  );
  it.each(["principal", "token", "roles"])(
    "drops private editor/discussion authority when %s changes",
    async (kind) => {
      setup();
      const user = { ...principal, roles: ["translator" as const] };
      const view = render(tree(user));
      await flush();
      await userEvent.click(
        screen.getByRole("button", { name: "Edit french" }),
      );
      await flush();
      await userEvent.click(
        screen.getByRole("button", { name: "Comments french" }),
      );
      await userEvent.type(
        await screen.findByRole("textbox", { name: "Add a comment" }),
        "Private old identity",
      );
      await userEvent.type(
        screen.getByRole("textbox", { name: "Proposed translation" }),
        " unsaved",
      );
      view.rerender(
        tree(
          kind === "principal"
            ? { ...user, id: "other" }
            : kind === "roles"
              ? { ...user, roles: ["viewer"] }
              : user,
          kind === "token" ? "rotated" : "token",
        ),
      );
      await flush();
      expect(
        screen.queryByRole("textbox", { name: "Proposed translation" }),
      ).toBeNull();
      if (kind !== "roles") expect(screen.queryByRole("dialog")).toBeNull();
      expect(screen.queryByDisplayValue("Private old identity")).toBeNull();
      expect(saveTranslationProposal).not.toHaveBeenCalled();
    },
  );
});
