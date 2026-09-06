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
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWindowVirtualizer } from "@tanstack/react-virtual";

import {
  searchTranslations,
  type TranslationGroupSummaryResponse,
} from "../../api/client";
import { useTranslationSearch } from "./useTranslationSearch";
import { TranslationResultList } from "./TranslationResultList";

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
  return { ...actual, searchTranslations: vi.fn() };
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
          } as ResizeObserverEntry,
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
  changes: Partial<TranslationGroupSummaryResponse> = {},
): TranslationGroupSummaryResponse {
  return {
    id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    product_id: "00000000-0000-4000-8000-999999999999",
    product_name: "Mobile",
    raw_key: `literal.[${index}]`,
    language: "it-IT",
    language_label: "Italian",
    source_language: "en",
    source_text: `Source ${index}`,
    translated_text: `Translation ${index}`,
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
const many = () => Array.from({ length: 100 }, (_, index) => group(index));
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
function mount(props: ReturnType<typeof defaults>) {
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
    function () {
      return height(this);
    },
  );
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(
    function () {
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
  it("uses the exact approved adapter options and window scrollbar with opaque stable keys", async () => {
    const props = { ...defaults(), items: many(), nextCursor: "next" };
    mount(props);
    await screen.findByRole("listitem");
    const options = vi.mocked(useWindowVirtualizer).mock.calls.at(-1)![0];
    expect(options.count).toBe(100);
    expect(options.estimateSize(0)).toBe(288);
    expect(options.overscan).toBe(8);
    expect(options.useFlushSync).toBe(false);
    expect(options.getItemKey!(0)).toBe(props.items[0].id);
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
    expect(screen.getByText("100 translation groups loaded")).toBeVisible();
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
      measuredHeights.set(props.items[0].id, 620);
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
      items: [
        group(0, { translated_text: "OLD private row", is_deleted: true }),
      ],
    };
    const view = mount(props);
    const oldLink = await screen.findByRole("link");
    oldLink.focus();
    view.update({
      ...props,
      items: [
        group(8, {
          translated_text: "NEW row",
          state_summary: "approved",
          states: ["approved"],
        }),
      ],
      requestIdentity: "search-two",
    });
    expect(screen.queryByText("OLD private row")).not.toBeInTheDocument();
    expect(screen.queryByText("Deleted in source")).not.toBeInTheDocument();
    expect(screen.getByText("NEW row")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      `/translations/${group(8).id}`,
    );
    expect(screen.getByRole("link")).not.toBe(oldLink);
  });
});

describe("TranslationResultList six-part anatomy and safe content", () => {
  it.each([390, 768, 1440])(
    "preserves six sections in DOM order with two-line excerpts at %ipx",
    async (width) => {
      Object.defineProperty(window, "innerWidth", {
        configurable: true,
        value: width,
      });
      mount(defaults());
      const row = await screen.findByRole("listitem");
      expect(
        Array.from(row.children).map((child) =>
          child.getAttribute("data-part"),
        ),
      ).toEqual([
        "key",
        "language",
        "source",
        "translation",
        "status",
        "details",
      ]);
      expect(row).toHaveClass(
        "grid",
        "grid-cols-1",
        "md:grid-cols-[minmax(0,1fr)_minmax(0,0.5fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.8fr)_minmax(0,0.6fr)]",
      );
      expect(row).toHaveClass("gap-(--space-md)", "p-(--space-md)", "border-b");
      expect(row).not.toHaveClass("shadow", "shadow-sm");
      for (const label of ["Source text", "Translated text"]) {
        const excerpt = within(row).getByLabelText(label);
        expect(excerpt).toHaveClass(
          "line-clamp-2",
          "whitespace-pre-wrap",
          "wrap-anywhere",
        );
        expect(excerpt).not.toHaveAttribute("title");
        expect(excerpt).toHaveAttribute("dir", "auto");
      }
      expect(within(row).getByLabelText("Source text")).toHaveAttribute(
        "lang",
        "en",
      );
      expect(within(row).getByLabelText("Translated text")).toHaveAttribute(
        "lang",
        "it-IT",
      );
      expect(within(row).getAllByRole("link")).toHaveLength(1);
      expect(within(row).queryByRole("button")).not.toBeInTheDocument();
      const link = within(row).getByRole("link", {
        name: "Open details for literal.[0] (it-IT)",
      });
      expect(link).toHaveTextContent(/^Open details$/);
      expect(link).toHaveClass(
        "min-h-[44px]",
        "min-w-[44px]",
        "whitespace-normal",
      );
      expect(row.querySelector("[aria-expanded], details")).toBeNull();
    },
  );

  it.each([
    ["scalar", null],
    ["android_quantity", "Plural"],
    ["android_array_item", "Array"],
    ["qt_numerus", "Qt variant"],
    ["qt_length_variant", "Qt variant"],
    ["json_path", "JSON path"],
  ] as const)(
    "keeps %s metadata separate even with one value",
    async (kind, label) => {
      mount({
        ...defaults(),
        items: [
          group(0, { selector_kinds: [kind], raw_key: " raw.key[one] " }),
        ],
      });
      const row = await screen.findByRole("listitem");
      expect(row.querySelector("[data-part=key] code")?.textContent).toBe(
        " raw.key[one] ",
      );
      if (label === null) {
        expect(within(row).queryByText(/1 value/)).not.toBeInTheDocument();
      } else {
        expect(within(row).getByText("1 value")).toBeVisible();
        expect(within(row).getByText(label)).toHaveAttribute(
          "data-variant",
          "secondary",
        );
      }
    },
  );

  it.each([
    ["draft", "Draft"],
    ["approved", "Approved"],
    ["rejected", "Rejected"],
    ["mixed", "Mixed states"],
  ] as const)("renders honest %s review state", async (state, label) => {
    mount({ ...defaults(), items: [group(0, { state_summary: state })] });
    expect(await screen.findByText(label)).toBeVisible();
  });

  it("shows partial violations, mixed constraints and deleted last-known provenance without inventing totals", async () => {
    mount({
      ...defaults(),
      items: [
        group(0, {
          selector_kinds: ["qt_numerus", "qt_length_variant"],
          value_count: 3,
          over_limit_count: 1,
          within_limit_count: 1,
          no_max_count: 1,
          has_over_limit: true,
          state_summary: "mixed",
          is_deleted: true,
          provenance: {
            repository_name: "Mobile repo",
            branch: "main",
            path: "locales/old.json",
          },
        }),
      ],
    });
    const row = await screen.findByRole("listitem");
    expect(within(row).getByText("3 values")).toBeVisible();
    expect(within(row).getAllByText("Qt variant")).toHaveLength(1);
    expect(within(row).getByText("1 of 3 over limit")).toHaveClass(
      "text-warning",
    );
    expect(within(row).getByText("Deleted in source")).toBeVisible();
    expect(within(row).getByText("locales/old.json")).toBeVisible();
    expect(within(row).getByText("Mobile repo")).toBeVisible();
    expect(within(row).getByText("main")).toBeVisible();
    expect(within(row).queryByText(/^No max length$/)).not.toBeInTheDocument();
  });

  it("labels absent source, empty translation, unknown friendly locale and no limit explicitly", async () => {
    mount({
      ...defaults(),
      items: [
        group(0, {
          source_text: null,
          translated_text: "",
          language_label: "it-IT",
        }),
      ],
    });
    expect(await screen.findByText("No source text available")).toBeVisible();
    expect(screen.getByText("Empty translation")).toBeVisible();
    expect(screen.getByText("it-IT")).toBeVisible();
    expect(screen.getByText("No max length")).toBeVisible();
    expect(screen.getByText("1 translation group loaded")).toBeVisible();
  });

  it("keeps malicious markup, URLs, Unicode and long multiline values literal with no reveal or storage", async () => {
    const malicious =
      '<img src=x onerror="alert(1)"><script>bad()</script> https://attacker.test/?raw=secret';
    const unicode = `العربية שלום é 👩🏽‍💻\n${"very long text ".repeat(400)}`;
    const props = {
      ...defaults(),
      items: [
        group(0, {
          raw_key: malicious,
          translated_text: unicode,
          source_text: malicious,
          language: "ar",
        }),
      ],
    };
    const { container } = mount(props);
    const row = await screen.findByRole("listitem");
    expect(within(row).getByLabelText("Source text").textContent).toBe(
      malicious,
    );
    expect(within(row).getByLabelText("Translated text").textContent).toBe(
      unicode,
    );
    expect(
      container.querySelector("img,script,iframe,textarea,input,details"),
    ).toBeNull();
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      `/translations/${props.items[0].id}`,
    );
    expect(JSON.stringify(localStorage)).not.toContain("attacker");
    expect(JSON.stringify(sessionStorage)).not.toContain("attacker");
    expect(screen.getByRole("link").getAttribute("aria-label")).not.toContain(
      unicode,
    );
  });
});

describe("TranslationResultList cursor and keyboard loading", () => {
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
    expect(props.onOpenDetails).toHaveBeenCalledWith(props.items[0].id);
  });

  it("announces appends only, remains silent on scroll, and removes terminal loading controls", async () => {
    const props = {
      ...defaults(),
      items: many().slice(0, 50),
      nextCursor: "cursor-1",
    };
    const view = mount(props);
    expect(screen.getByRole("status")).toHaveTextContent(
      "50 translation groups loaded",
    );
    await scroll(500);
    expect(screen.getByRole("status")).toHaveTextContent(
      "50 translation groups loaded",
    );
    view.update({ ...props, items: many(), nextCursor: null });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loaded 50 more translation groups",
    );
    expect(screen.getByText("100 translation groups loaded")).toBeVisible();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it.each(["repeat", "empty"])(
    "retains valid rows and stops %s cursor loops until explicit retry",
    async (failure) => {
      const api = vi.mocked(searchTranslations);
      const response = (
        items: TranslationGroupSummaryResponse[],
        next_cursor: string | null,
      ) => ({
        data: { items, next_cursor },
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
