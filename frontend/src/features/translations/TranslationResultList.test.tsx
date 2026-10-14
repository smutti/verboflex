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
import { useState } from "react";
import { TranslationFilters } from "./TranslationFilters";
import type { TranslationSearchFilters } from "./useTranslationSearch";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWindowVirtualizer } from "@tanstack/react-virtual";

import {
  searchTranslationKeys,
  type TranslationKeySummary,
} from "../../api/client";
import { useTranslationSearch } from "./useTranslationSearch";
import {
  TranslationResultList,
  type TranslationResultListProps,
} from "./TranslationResultList";

vi.mock("@tanstack/react-virtual", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@tanstack/react-virtual")>();
  return {
    ...actual,
    useWindowVirtualizer: vi.fn(actual.useWindowVirtualizer),
  };
});
vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, searchTranslationKeys: vi.fn() };
});

const measuredHeights = new Map<string, number>();
const resizeObservers = new Set<TestResizeObserver>();
class TestResizeObserver {
  targets = new Set<Element>();
  constructor(readonly callback: ResizeObserverCallback) {
    resizeObservers.add(this);
  }
  observe = (element: Element) => {
    this.targets.add(element);
  };
  unobserve = (element: Element) => {
    this.targets.delete(element);
  };
  disconnect = () => {
    this.targets.clear();
    resizeObservers.delete(this);
  };
  notify(element: Element) {
    if (this.targets.has(element)) {
      this.callback(
        [
          {
            target: element,
            borderBoxSize: [
              { blockSize: height(element), inlineSize: window.innerWidth },
            ],
            contentBoxSize: [],
            devicePixelContentBoxSize: [],
            contentRect: element.getBoundingClientRect(),
          },
        ],
        this as unknown as ResizeObserver,
      );
    }
  }
}

function height(element: Element) {
  return (
    measuredHeights.get(
      element.getAttribute("data-translation-group-id") ?? "",
    ) ?? 288
  );
}
function group(
  index: number,
  changes: Partial<TranslationKeySummary> = {},
): TranslationKeySummary {
  return {
    translation_key_id: `key-${index}`,
    scope_id: "scope",
    product_id: "product",
    product_name: "Mobile",
    raw_key: `literal.[${index}]`,
    base_language: "en",
    rank: index,
    key_truncated: false,
    source_text: `Source ${index}`,
    source_truncated: false,
    slots: ["en", "fr", "it-IT"].map((language) => ({
      language,
      language_label: language,
      group_id: `${language}-${index}`,
      kind: "imported",
      editable: true,
      edit_field: language === "en" ? "source_text" : "translated_text",
      effective_text: `${language} value ${index}`,
      is_deleted: false,
      matches_filters: true,
      no_max_count: 1,
      over_limit_count: 0,
      within_limit_count: 0,
      pending_change: null,
      preview_kind: "scalar",
      provenance: null,
      read_only_reason: null,
      selector_kinds: ["scalar"],
      source_changed: false,
      states: ["draft"],
      text_truncated: false,
      value_count: 1,
      comment_count: 0,
    })),
    ...changes,
  };
}
const many = () => Array.from({ length: 100 }, (_, index) => group(index));

function BilingualControlsAndRows() {
  const [filters, setFilters] = useState<TranslationSearchFilters>({
    productId: null,
    language: null,
    visibleLanguages: ["en", "it-IT"],
    viewMode: "multilingual",
    state: null,
    violation: null,
    deleted: "active",
  });
  const item = group(0);
  return (
    <MemoryRouter>
      <TranslationFilters
        filters={filters}
        options={{
          products: [],
          languages: ["en", "fr", "it-IT"].map((code) => ({
            code,
            label: code,
          })),
        }}
        baseLanguage="en"
        onChange={setFilters}
        onClear={() => {}}
      />
      <TranslationResultList
        {...defaults()}
        items={[
          {
            ...item,
            slots: item.slots.filter((slot) =>
              filters.visibleLanguages
                ? filters.visibleLanguages.includes(slot.language)
                : true,
            ),
          },
        ]}
        viewMode={filters.viewMode}
        focusLanguage={filters.language}
      />
    </MemoryRouter>
  );
}

it("switches from source and Italian to all language siblings through the toolbar", async () => {
  render(<BilingualControlsAndRows />);
  await userEvent.click(screen.getByRole("button", { name: "Bilingual" }));
  expect(await screen.findByText("it-IT value 0")).toBeVisible();
  expect(screen.getByText("en value 0")).toBeVisible();
  expect(screen.queryByText("fr value 0")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Multilingual" }));
  expect(await screen.findByText("fr value 0")).toBeVisible();
  expect(screen.getByText("it-IT value 0")).toBeVisible();
  expect(screen.getByText("en value 0")).toBeVisible();
});
const defaults = () => ({
  items: [group(0)],
  nextCursor: null as string | null,
  requestIdentity: "search-one",
  loadingMore: false,
  loadMoreError: false,
  onLoadMore: vi.fn(async () => {}),
  onRetryLoadMore: vi.fn(async () => {}),
  onOpenDetails: vi.fn(),
});
function mount(props: TranslationResultListProps) {
  const result = render(
    <MemoryRouter>
      <TranslationResultList {...props} />
    </MemoryRouter>,
  );
  return {
    ...result,
    update: (next: typeof props) =>
      result.rerender(
        <MemoryRouter>
          <TranslationResultList {...next} />
        </MemoryRouter>,
      ),
  };
}
async function scroll(top: number) {
  await act(async () => {
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: top,
    });
    fireEvent.scroll(window);
  });
}

it("shows pending, approval and target status, then removes all change highlighting", async () => {
  const item = group(0);
  const pending = {
    state: "draft" as const,
    version: 1,
    value_count: 1,
    reconciliation_required: false,
  };
  item.slots[0].pending_change = pending;
  const props = {
    ...defaults(),
    items: [item],
    canEdit: true,
    onEditTranslation: vi.fn(),
  };
  const view = mount(props);
  expect(await screen.findByText("Pending", { exact: true })).toBeVisible();
  expect(screen.queryByText("Pending Draft")).toBeNull();
  const update = (state: "approved" | "draft", integrated = false) => {
    const next = {
      ...item,
      slots: item.slots.map((slot, index) =>
        index
          ? slot
          : {
              ...slot,
              pending_change: {
                ...pending,
                state,
                target_branch: "release/translations",
                target_integrated: integrated,
              },
            },
      ),
    };
    view.update({ ...props, items: [next] });
  };
  update("approved");
  expect(await screen.findByText("Approved", { exact: true })).toBeVisible();
  expect(screen.getByText("Awaiting release/translations")).toBeVisible();
  expect(screen.queryByText("Pending", { exact: true })).toBeNull();
  update("approved", true);
  await waitFor(() =>
    expect(screen.queryByLabelText("Translation status")).toBeNull(),
  );
  const row = view.container.querySelector('[data-group-id="en-0"]')!;
  expect(row.innerHTML).not.toContain("border-l-4");
  expect(screen.getByText("en value 0")).toBeVisible();
  update("draft");
  expect(await screen.findByText("Pending", { exact: true })).toBeVisible();
  expect(screen.queryByText("Awaiting release/translations")).toBeNull();
});

beforeEach(() => {
  measuredHeights.clear();
  resizeObservers.clear();
  vi.stubGlobal("ResizeObserver", TestResizeObserver);
  Object.defineProperty(window, "innerHeight", {
    configurable: true,
    value: 800,
  });
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: 1440,
  });
  Object.defineProperty(window, "scrollY", { configurable: true, value: 0 });
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockImplementation(
    function (this: HTMLElement) {
      return height(this);
    },
  );
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(
    function (this: HTMLElement) {
      return {
        x: 0,
        y: 400 - window.scrollY,
        top: 400 - window.scrollY,
        left: 0,
        bottom: 400 - window.scrollY + height(this),
        right: window.innerWidth,
        width: window.innerWidth,
        height: height(this),
        toJSON: () => ({}),
      };
    },
  );
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TranslationResultList window virtualization", () => {
  it("pins the selected editor outside the visible range and respects read-only source capabilities", async () => {
    const props = {
      ...defaults(),
      items: many(),
      canEdit: true,
      onEditTranslation: vi.fn(),
      activeEditorGroupId: "fr-0",
      editor: (
        <textarea aria-label="Selected draft" defaultValue="Preserved text" />
      ),
    };
    const view = mount(props);
    await screen.findByRole("textbox", { name: "Selected draft" });
    await scroll(16000);
    expect(screen.getByRole("textbox", { name: "Selected draft" })).toHaveValue(
      "Preserved text",
    );
    expect(screen.getAllByRole("listitem").length).toBeLessThan(25);
    view.update({
      ...props,
      items: [
        group(0, {
          slots: group(0).slots.map((slot) => ({ ...slot, editable: false })),
        }),
      ],
    });
    expect(
      screen.queryByRole("button", { name: /Edit translation/ }),
    ).not.toBeInTheDocument();
  });
  it("uses the exact approved adapter options and window scrollbar with opaque stable keys", async () => {
    const props = { ...defaults(), items: many(), nextCursor: "next" };
    mount(props);
    await screen.findAllByRole("listitem");
    const options = vi.mocked(useWindowVirtualizer).mock.calls.at(-1)![0];
    expect(options.count).toBe(100);
    expect(options.estimateSize(0)).toBe(284);
    expect(options.overscan).toBe(8);
    expect(options.useFlushSync).toBe(false);
    expect(options.getItemKey!(0)).toBe("product:scope:key-0");
    expect(options.scrollMargin).toBe(400);
    const instance = vi.mocked(useWindowVirtualizer).mock.results.at(-1)!.value;
    expect(instance.scrollElement).toBe(window);
    const list = screen.getByRole("list", { name: "Translation results" });
    expect(list).not.toHaveClass(
      "overflow-auto",
      "overflow-y-auto",
      "overflow-scroll",
    );
    expect(list.style.overflow).toBe("");
    expect(screen.getByRole("status")).toHaveTextContent("100 keys loaded");
    expect(props.onLoadMore).not.toHaveBeenCalled();
  });

  it("keeps DOM bounded, server order and unknown/final positions across window scroll", async () => {
    const props = {
      ...defaults(),
      items: many().reverse(),
      nextCursor: "next",
    };
    const view = mount(props);
    await waitFor(() =>
      expect(screen.getAllByRole("listitem").length).toBeGreaterThan(1),
    );
    expect(screen.getAllByRole("listitem").length).toBeLessThanOrEqual(20);
    expect(screen.getAllByRole("listitem")[0]).toHaveAttribute(
      "aria-posinset",
      "1",
    );
    expect(screen.getAllByRole("listitem")[0]).toHaveTextContent(
      "literal.[99]",
    );
    await scroll(400 + 50 * 288);
    const rows = screen.getAllByRole("listitem");
    expect(rows.length).toBeLessThanOrEqual(20);
    const positions = rows.map((row) =>
      Number(row.getAttribute("aria-posinset")),
    );
    expect(positions[0]).toBeGreaterThan(1);
    expect(positions).toEqual([...positions].sort((a, b) => a - b));
    for (const row of rows) {
      expect(row).toHaveAttribute("aria-setsize", "-1");
      expect(row).toHaveTextContent(
        props.items[Number(row.getAttribute("aria-posinset")) - 1].raw_key,
      );
    }
    view.update({ ...props, nextCursor: null });
    for (const row of screen.getAllByRole("listitem"))
      expect(row).toHaveAttribute("aria-setsize", "100");
  });

  it("measures every dynamic row and disconnects removed row observations", async () => {
    const props = { ...defaults(), items: many() };
    const { unmount } = mount(props);
    const rows = await screen.findAllByRole("listitem");
    expect(rows[1].style.transform).toContain("288px");
    const observers = [...resizeObservers];
    expect(
      rows.every((row) =>
        observers.some((observer) => observer.targets.has(row)),
      ),
    ).toBe(true);
    await act(async () => {
      measuredHeights.set(props.items[0].translation_key_id, 620);
      for (const observer of resizeObservers) observer.notify(rows[0]);
    });
    expect(screen.getAllByRole("listitem")[1].style.transform).toContain(
      "620px",
    );
    expect(rows[0].style.height).toBe("");
    unmount();
    expect(observers.every((observer) => observer.targets.size === 0)).toBe(
      true,
    );
  });

  it("does not reuse text, status, link identity or focus across a replacement generation", async () => {
    const props = {
      ...defaults(),
      items: [group(0, { raw_key: "OLD private row" })],
    };
    const view = mount(props);
    const oldLink = await screen
      .findAllByRole("link")
      .then((links) => links[0]);
    oldLink.focus();
    view.update({
      ...props,
      items: [
        group(8, {
          raw_key: "NEW row",
        }),
      ],
      requestIdentity: "search-two",
    });
    expect(screen.queryByText("OLD private row")).not.toBeInTheDocument();
    expect(screen.queryByText("Deleted in source")).not.toBeInTheDocument();
    expect(screen.getByText("NEW row")).toBeInTheDocument();
    expect(screen.getAllByRole("link")[0]).toHaveAttribute(
      "href",
      `/translations/${group(8).slots[0].group_id}`,
    );
    expect(screen.getAllByRole("link")[0]).not.toBe(oldLink);
  });
});

describe("compact multilingual key blocks", () => {
  it("renders one key and all exact locale siblings, including across scopes", async () => {
    mount({
      ...defaults(),
      items: [
        group(0),
        group(1, { raw_key: "literal.[0]", scope_id: "other" }),
      ],
    });
    const rows = await screen.findAllByRole("listitem");
    expect(rows).toHaveLength(2);
    for (const row of rows) {
      expect(row.querySelectorAll("code")).toHaveLength(1);
      expect(row.querySelectorAll("[data-language]")).toHaveLength(3);
    }
  });
  it("activates value cells by keyboard and targets context icons by locale", async () => {
    const onEditTranslation = vi.fn(),
      onOpenContext = vi.fn();
    mount({ ...defaults(), canEdit: true, onEditTranslation, onOpenContext });
    const cell = await screen.findByRole("button", {
      name: "Edit translation for literal.[0] (fr)",
    });
    cell.focus();
    await userEvent.keyboard("{Enter}");
    expect(onEditTranslation).toHaveBeenCalledWith("fr-0", cell);
    await userEvent.click(
      screen.getByRole("button", {
        name: "Comments for literal.[0] (it-IT), 0 comments",
      }),
    );
    expect(onOpenContext).toHaveBeenCalledWith(
      expect.objectContaining({
        groupId: "it-IT-0",
        language: "it-IT",
        section: "comments",
        trigger: expect.any(HTMLElement),
      }),
    );
  });
  it("never borrows a target identity for absent or embedded source slots", async () => {
    const item = group(0);
    item.slots[0] = {
      ...item.slots[0],
      group_id: null,
      kind: "source_context",
      editable: false,
      read_only_reason: "source_context",
    };
    item.slots[1] = {
      ...item.slots[1],
      group_id: null,
      kind: "absent",
      editable: false,
      effective_text: null,
      read_only_reason: "absent",
    };
    mount({
      ...defaults(),
      items: [item],
      canEdit: true,
      onEditTranslation: vi.fn(),
      onOpenContext: vi.fn(),
    });
    expect(
      await screen.findByText("Not imported for this language"),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /Edit translation.*\(en\)/ }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: /Comments.*\(en\)/ }),
    ).toBeNull();
    expect(screen.getByText(/Embedded source text/)).toBeVisible();
  });
  it.each(["Operazione completata", "Open the message", "<b>Open</b>"])(
    "shows Qt source %s without treating it as an Italian translation",
    async (source) => {
      const item = group(0, { base_language: "it-IT", source_text: source });
      item.slots = [
        {
          ...item.slots[2],
          effective_text: "",
          edit_field: "translated_text",
          provenance: {
            repository_side: "direct",
            format: "qt_ts",
            repository_name: "Example",
            branch: "work",
            path: "it.ts",
            path_truncated: false,
          },
        },
      ];
      const edit = vi.fn();
      const { container } = mount({
        ...defaults(),
        items: [item],
        canEdit: true,
        onEditTranslation: edit,
      });
      expect(
        await screen.findByText("Source text", { exact: true }),
      ).toBeVisible();
      expect(screen.getByText(source, { exact: true })).toBeVisible();
      expect(screen.queryByText("Empty source text")).toBeNull();
      expect(screen.queryByText("Source", { exact: true })).toBeNull();
      expect(container.querySelector('[data-part="source-text"] b')).toBeNull();
      const button = screen.getByRole("button", {
        name: /Edit translation.*it-IT/,
      });
      expect(button).toHaveTextContent("Empty translation");
      expect(button).not.toHaveTextContent(source);
      await userEvent.click(button);
      expect(edit).toHaveBeenCalledWith("it-IT-0", button);
    },
  );
  it("keeps siblings visible and pins the active editor beyond the visible range", async () => {
    mount({
      ...defaults(),
      items: many(),
      activeEditorGroupId: "fr-0",
      editor: <textarea aria-label="Draft" />,
    });
    await screen.findByRole("textbox");
    await scroll(15000);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem").length).toBeLessThan(24);
    expect(screen.getByText("it-IT value 0")).toBeVisible();
  });
  it("wraps literal long values without interpreting markup", async () => {
    const item = group(0);
    item.slots[1].effective_text =
      "<script>bad()</script>" + "verylong".repeat(200);
    const { container } = mount({ ...defaults(), items: [item] });
    await screen.findByRole("listitem");
    expect(container.querySelector("script,iframe,img")).toBeNull();
    expect(screen.getByText(/<script>/)).toHaveClass("wrap-anywhere");
    expect(screen.getAllByRole("link")).toHaveLength(3);
  });
});

describe("TranslationResultList cursor and keyboard loading", () => {
  it("does not resubmit an already attempted unchanged cursor after completion", async () => {
    const p = { ...defaults(), items: many(), nextCursor: "same-cursor" };
    mount(p);
    await userEvent.click(
      screen.getByRole("button", { name: "Load more translations" }),
    );
    expect(p.onLoadMore).toHaveBeenCalledOnce();
    await userEvent.click(
      screen.getByRole("button", { name: "Load more translations" }),
    );
    expect(p.onLoadMore).toHaveBeenCalledOnce();
  });
  it("focuses an explicit loading error while superseded callbacks cannot contaminate a new search", async () => {
    const props = {
      ...defaults(),
      items: many(),
      nextCursor: "next",
      onLoadMore: vi.fn(async () => {
        throw new Error("private upstream failure");
      }),
    };
    const view = mount(props);
    await userEvent.click(
      screen.getByRole("button", { name: "Load more translations" }),
    );
    await waitFor(() => expect(screen.getByRole("alert")).toHaveFocus());
    expect(
      screen.queryByText("private upstream failure"),
    ).not.toBeInTheDocument();
    view.update({
      ...props,
      requestIdentity: "another search",
      onLoadMore: vi.fn(async () => {}),
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("allows a new generation to load before an old callback settles and ignores its late rejection", async () => {
    let rejectOld!: (reason: Error) => void;
    const props = {
      ...defaults(),
      nextCursor: "next",
      onLoadMore: vi.fn(
        () =>
          new Promise<void>((_resolve, reject) => {
            rejectOld = reject;
          }),
      ),
    };
    const view = mount(props);
    await waitFor(() => expect(props.onLoadMore).toHaveBeenCalledTimes(1));
    const newLoad = vi.fn(async () => {});
    view.update({
      ...props,
      requestIdentity: "another search",
      onLoadMore: newLoad,
    });
    await waitFor(() => expect(newLoad).toHaveBeenCalledTimes(1));
    await act(async () => {
      rejectOld(new Error("old failure"));
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("triggers the final rendered index once, and respects request identity and busy state", async () => {
    const props = { ...defaults(), items: many(), nextCursor: "cursor-1" };
    const view = mount(props);
    await scroll(400 + 90 * 288);
    await waitFor(() => expect(props.onLoadMore).toHaveBeenCalledTimes(1));
    await scroll(400 + 91 * 288);
    view.update({ ...props, loadingMore: true });
    view.update({ ...props });
    expect(props.onLoadMore).toHaveBeenCalledTimes(1);
    view.update({ ...props, requestIdentity: "new search", loadingMore: true });
    expect(props.onLoadMore).toHaveBeenCalledTimes(1);
    view.update({ ...props, requestIdentity: "new search" });
    await waitFor(() => expect(props.onLoadMore).toHaveBeenCalledTimes(2));
  });

  it("loads by Enter outside overscan, blocks concurrent activation and records detail identity", async () => {
    const user = userEvent.setup();
    let finish!: () => void;
    const props = {
      ...defaults(),
      items: many(),
      nextCursor: "cursor-1",
      onLoadMore: vi.fn(
        () =>
          new Promise<void>((resolve) => {
            finish = resolve;
          }),
      ),
    };
    mount(props);
    const button = screen.getByRole("button", {
      name: "Load more translations",
    });
    button.focus();
    await user.keyboard("{Enter}{Enter}");
    expect(props.onLoadMore).toHaveBeenCalledTimes(1);
    await act(async () => {
      finish();
    });
    const link = screen.getAllByRole("link")[0];
    link.focus();
    await user.keyboard("{Enter}");
    expect(props.onOpenDetails).toHaveBeenCalledWith(
      props.items[0].slots[0].group_id,
      expect.any(Array),
    );
  });

  it("announces appends only, remains silent on scroll, and removes terminal loading controls", async () => {
    const props = {
      ...defaults(),
      items: many().slice(0, 50),
      nextCursor: "cursor-1",
    };
    const view = mount(props);
    expect(screen.getByRole("status")).toHaveTextContent("50 keys loaded");
    await scroll(500);
    expect(screen.getByRole("status")).toHaveTextContent("50 keys loaded");
    view.update({ ...props, items: many(), nextCursor: null });
    expect(screen.getByRole("status")).toHaveTextContent("Loaded 50 more keys");
    expect(screen.getByRole("status")).toHaveClass("sr-only");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it.each(["repeat", "empty"])(
    "retains valid rows and stops %s cursor loops until explicit retry",
    async (failure) => {
      const api = vi.mocked(searchTranslationKeys);
      const response = (
        items: TranslationKeySummary[],
        next_cursor: string | null,
      ) => ({
        data: {
          items,
          next_cursor,
          visible_languages: ["en", "fr", "it-IT"],
          available_languages: [],
          available_languages_truncated: false,
          default_selection_capped: false,
        },
        error: undefined,
        request: new Request("http://localhost/api/v1/translations"),
        response: new Response(null, { status: 200 }),
      });
      api.mockResolvedValueOnce(response([group(0)], "cursor-1"));
      api.mockResolvedValueOnce(
        response(
          failure === "repeat" ? [group(1)] : [],
          failure === "repeat" ? "cursor-1" : "cursor-2",
        ),
      );
      api.mockResolvedValueOnce(response([group(1)], null));
      function Harness() {
        const state = useTranslationSearch({
          accessToken: "test-bearer",
          initialFilters: {
            productId: null,
            language: null,
            state: null,
            violation: null,
            deleted: "active",
          },
        });
        return (
          <TranslationResultList
            {...state}
            onLoadMore={state.loadMore}
            onRetryLoadMore={state.retryLoadMore}
          />
        );
      }
      render(
        <MemoryRouter>
          <Harness />
        </MemoryRouter>,
      );
      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent("More translations could not be loaded");
      expect(screen.getAllByRole("listitem")).toHaveLength(1);
      expect(screen.queryByText("literal.[1]")).not.toBeInTheDocument();
      await scroll(450);
      expect(api).toHaveBeenCalledTimes(2);
      await userEvent.click(
        screen.getByRole("button", { name: "Retry loading more" }),
      );
      await waitFor(() =>
        expect(screen.getAllByRole("listitem")).toHaveLength(2),
      );
      expect(api).toHaveBeenCalledTimes(3);
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    },
  );
});

it.each([true, false])(
  "shows effective length violations before focus (editable=%s)",
  async (editable) => {
    const item = group(0);
    item.slots[1].effective_over_limit_count = 1;
    item.slots[1].over_limit_count = 0;
    item.slots[2].effective_over_limit_count = 0;
    item.slots[2].over_limit_count = 1;
    mount({
      ...defaults(),
      items: [item],
      canEdit: editable,
      onEditTranslation: vi.fn(),
    });
    const text = editable
      ? await screen.findByRole("button", {
          name: "Edit translation for literal.[0] (fr)",
        })
      : await screen.findByText("fr value 0");
    expect(text).not.toHaveFocus();
    expect(text).toHaveClass("border-destructive", "bg-red-50");
    expect(text).toHaveAccessibleDescription("1 of 1 over limit");
    expect(screen.getByText("1 of 1 over limit")).toHaveClass(
      "text-destructive",
    );
    const corrected = editable
      ? screen.getByRole("button", {
          name: "Edit translation for literal.[0] (it-IT)",
        })
      : screen.getByText("it-IT value 0");
    expect(corrected).not.toHaveClass("border-destructive");
  },
);
