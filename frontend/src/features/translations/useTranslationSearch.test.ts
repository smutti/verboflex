import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  searchTranslationKeys,
  type TranslationKeySummary,
  type TranslationKeyPageResponse,
} from "../../api/client";
import {
  translationSearchIdentity,
  useTranslationSearch,
  type TranslationSearchFilters,
} from "./useTranslationSearch";

vi.mock("../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/client")>();
  return { ...original, searchTranslationKeys: vi.fn() };
});

const searchTranslationKeysMock = vi.mocked(searchTranslationKeys);

const defaultFilters: TranslationSearchFilters = {
  visibleLanguages: null,
  viewMode: "multilingual",
  workStatus: null,
  productId: null,
  language: null,
  state: null,
  violation: null,
  deleted: "active",
};

function group(index: number): TranslationKeySummary {
  return {
    translation_key_id: `group-${index}`,
    scope_id: "scope-alpha",
    product_id: "product-alpha",
    product_name: "Alpha",
    rank: index,
    raw_key: `key.${index}`,
    base_language: "en",
    key_truncated: false,
    source_text: `Source ${index}`,
    source_truncated: false,
    slots: ["en", "it-IT"].map((language) => ({
      language,
      language_label: language,
      group_id: `${language}-${index}`,
      kind: "imported",
      editable: true,
      edit_field: language === "en" ? "source_text" : "translated_text",
      effective_text: `Translation ${index}`,
      is_deleted: false,
      matches_filters: language !== "en",
      no_max_count: 0,
      over_limit_count: 0,
      within_limit_count: 1,
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
  };
}

function page(
  items: TranslationKeySummary[],
  nextCursor: string | null,
): TranslationKeyPageResponse {
  return {
    items,
    next_cursor: nextCursor,
    visible_languages: ["en", "it-IT"],
    available_languages: [
      { code: "en", label: "English" },
      { code: "it-IT", label: "Italian" },
    ],
    available_languages_truncated: false,
    default_selection_capped: false,
    language_selection_limit: 20,
  };
}

function ok(data: TranslationKeyPageResponse) {
  return {
    data,
    error: undefined,
    request: new Request("http://localhost/api/v1/translations"),
    response: new Response(null, { status: 200 }),
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

async function settleInitial() {
  await act(async () => {
    for (let flush = 0; flush < 5; flush += 1) {
      await Promise.resolve();
    }
  });
}

describe("useTranslationSearch", () => {
  it.each([true, false])(
    "validates deleted-only embedded source history (consistent deletion %s)",
    async (deletedSource) => {
      const item = group(1);
      item.source_text = "Retained embedded source";
      item.slots = item.slots.map((slot) => ({
        ...slot,
        editable: false,
        edit_field: null,
        is_deleted: true,
        matches_filters: true,
        read_only_reason: "deleted",
      }));
      item.slots[0] = {
        ...item.slots[0],
        kind: "source_context",
        preview_kind: "context",
        group_id: null,
        read_only_reason: "source_context",
        is_deleted: deletedSource,
        effective_text: item.source_text,
        value_count: 0,
        states: [],
        selector_kinds: [],
        within_limit_count: 0,
      };
      searchTranslationKeysMock.mockResolvedValue(ok(page([item], null)));
      const { result } = renderHook(() =>
        useTranslationSearch({
          accessToken: "token",
          initialFilters: { ...defaultFilters, deleted: "deleted" },
        }),
      );
      await settleInitial();
      expect(result.current.status).toBe(deletedSource ? "ready" : "error");
      if (deletedSource) {
        expect(result.current.items[0].slots[0]).toMatchObject({
          kind: "source_context",
          is_deleted: true,
          effective_text: "Retained embedded source",
          editable: false,
        });
      }
    },
  );
  it("requests server work queues and discards stale continuation when refreshing", async () => {
    searchTranslationKeysMock.mockResolvedValue(ok(page([group(1)], "next")));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "token",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    const identities = new Set([result.current.requestIdentity]);
    for (const workStatus of [
      "needs_translation",
      "needs_review",
      "source_changed",
    ] as const) {
      act(() => result.current.setFilters({ ...defaultFilters, workStatus }));
      await settleInitial();
      expect(searchTranslationKeysMock.mock.lastCall?.[0]?.query).toMatchObject(
        {
          work_status: workStatus,
          cursor: null,
        },
      );
      identities.add(result.current.requestIdentity);
    }
    expect(identities.size).toBe(4);
    act(() => result.current.refresh());
    await settleInitial();
    expect(
      searchTranslationKeysMock.mock.lastCall?.[0]?.query?.cursor,
    ).toBeNull();
  });
  it.each([
    ["malformed cursor", [page([group(1)], 42 as never)]],
    [
      "nonterminal after terminal",
      [page([group(1)], null), page([group(2)], null)],
    ],
  ])(
    "rejects %s snapshots and fetches fresh authority",
    async (_name, pages) => {
      searchTranslationKeysMock.mockResolvedValue(ok(page([group(9)], null)));
      const { result } = renderHook(() =>
        useTranslationSearch({
          accessToken: "token",
          initialFilters: defaultFilters,
          initialSnapshot: {
            version: 2,
            query: "",
            filters: defaultFilters,
            pages,
            requestIdentity: translationSearchIdentity("", defaultFilters),
            scrollAnchor: 30,
            focusedGroupId: null,
          },
        }),
      );
      await settleInitial();
      expect(searchTranslationKeysMock).toHaveBeenCalledOnce();
      expect(result.current.items).toEqual([group(9)]);
      expect(result.current.restoredNavigation).toBeNull();
    },
  );

  it("restores a nonterminal snapshot and advances each distinct server cursor once", async () => {
    searchTranslationKeysMock
      .mockResolvedValueOnce(ok(page([group(2)], "next-2")))
      .mockResolvedValueOnce(ok(page([group(3)], null)));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "token",
        initialFilters: defaultFilters,
        initialSnapshot: {
          version: 2,
          query: "",
          filters: defaultFilters,
          pages: [page([group(1)], "next-1")],
          requestIdentity: translationSearchIdentity("", defaultFilters),
          scrollAnchor: 30,
          focusedGroupId: null,
        },
      }),
    );
    await settleInitial();
    expect(searchTranslationKeysMock).not.toHaveBeenCalled();
    await act(async () => result.current.loadMore());
    expect(result.current.nextCursor).toBe("next-2");
    await act(async () => result.current.loadMore());
    expect(
      searchTranslationKeysMock.mock.calls.map(
        ([request]) => request?.query?.cursor,
      ),
    ).toEqual(["next-1", "next-2"]);
    expect(result.current.items).toEqual([group(1), group(2), group(3)]);
  });

  it("reauthorizes token rotation during debounce and ignores identical query assignments", async () => {
    searchTranslationKeysMock.mockResolvedValue(ok(page([], null)));
    const { result, rerender } = renderHook(
      ({ token }) =>
        useTranslationSearch({
          accessToken: token,
          initialFilters: defaultFilters,
        }),
      { initialProps: { token: "old" } },
    );
    await settleInitial();
    act(() => {
      result.current.setQuery("pending");
      result.current.setQuery("pending");
    });
    rerender({ token: "new" });
    await settleInitial();
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(2);
    expect(searchTranslationKeysMock.mock.lastCall?.[0]).toMatchObject({
      auth: "new",
      query: { q: "pending" },
    });
    act(() => vi.advanceTimersByTime(300));
    await settleInitial();
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(2);
  });

  it("applies a filter during debounce without a duplicate delayed search", async () => {
    searchTranslationKeysMock.mockResolvedValue(ok(page([], null)));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "token",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    act(() => result.current.setQuery("pending"));
    act(() =>
      result.current.setFilters({ ...defaultFilters, language: "it-IT" }),
    );
    await settleInitial();
    expect(searchTranslationKeysMock.mock.lastCall?.[0]?.query).toMatchObject({
      q: "pending",
      language: "it-IT",
    });
    act(() => vi.advanceTimersByTime(300));
    await settleInitial();
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(2);
  });

  beforeEach(() => {
    vi.useFakeTimers();
    searchTranslationKeysMock.mockReset();
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("binds the complete canonical identity and fixed 50-group first page", async () => {
    const approved: TranslationKeySummary = {
      ...group(1),
      slots: group(1).slots.map((slot) => ({ ...slot, states: ["approved"] })),
    };
    searchTranslationKeysMock.mockResolvedValue(ok(page([approved], null)));
    const filters: TranslationSearchFilters = {
      productId: "product-alpha",
      language: "it-IT",
      state: "approved",
      violation: "within_limit",
      deleted: "all",
    };
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: filters,
        initialQuery: "  literal Query  ",
      }),
    );

    await settleInitial();
    expect(result.current.items).toEqual([approved]);

    expect(searchTranslationKeysMock).toHaveBeenCalledOnce();
    expect(searchTranslationKeysMock).toHaveBeenCalledWith({
      auth: "memory-only-bearer",
      query: {
        cursor: null,
        deleted: "all",
        language: "it-IT",
        page_size: 50,
        product_id: "product-alpha",
        q: "  literal Query  ",
        state: "approved",
        violation: "within_limit",
      },
      signal: expect.any(AbortSignal),
    });
    expect(result.current.requestIdentity).toBe(
      translationSearchIdentity("  literal Query  ", filters),
    );
  });

  it("invalidates mutated pages while preserving query filters and return navigation", async () => {
    searchTranslationKeysMock.mockResolvedValue(ok(page([group(1)], null)));
    const initialSnapshot = {
      version: 2 as const,
      requestIdentity: translationSearchIdentity("settings", defaultFilters),
      query: "settings",
      filters: defaultFilters,
      pages: [],
      scrollAnchor: 864,
      focusedGroupId: "group-1",
      invalidated: true,
    };
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "token",
        initialQuery: "settings",
        initialFilters: defaultFilters,
        initialSnapshot,
      }),
    );
    await settleInitial();
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(1);
    expect(result.current.query).toBe("settings");
    expect(result.current.restoredNavigation).toEqual({
      scrollAnchor: 864,
      focusedGroupId: "group-1",
    });
    expect(result.current.items).toEqual([group(1)]);
  });

  it("coalesces typing for 300ms while Enter and clear run once immediately", async () => {
    searchTranslationKeysMock.mockResolvedValue(ok(page([], null)));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    expect(searchTranslationKeysMock).toHaveBeenCalledOnce();

    act(() => {
      result.current.setQuery("fir");
      result.current.setQuery("first");
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(299);
    });
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(2);
    expect(searchTranslationKeysMock.mock.calls[1]?.[0]?.query?.q).toBe(
      "first",
    );

    act(() => {
      result.current.setQuery("run on Enter");
      result.current.submitQuery();
    });
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(3);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(3);

    act(() => {
      result.current.setQuery("will be cleared");
      result.current.clearQuery();
    });
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(4);
    expect(searchTranslationKeysMock.mock.calls[3]?.[0]?.query?.q).toBe("");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(4);
  });

  it("applies filters immediately, aborts the old generation, and ignores stale success", async () => {
    const obsolete = deferred<ReturnType<typeof ok>>();
    searchTranslationKeysMock
      .mockReturnValueOnce(obsolete.promise as never)
      .mockResolvedValueOnce(ok(page([group(2)], null)));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    expect(searchTranslationKeysMock).toHaveBeenCalledOnce();
    const obsoleteSignal = searchTranslationKeysMock.mock.calls[0]?.[0]?.signal;

    act(() => {
      result.current.setFilters({
        ...defaultFilters,
        productId: "product-alpha",
      });
    });
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(2);
    expect(obsoleteSignal?.aborted).toBe(true);
    await settleInitial();
    expect(result.current.items).toEqual([group(2)]);

    obsolete.resolve(ok(page([group(1)], "obsolete-cursor")));
    await act(async () => Promise.resolve());
    expect(result.current.items).toEqual([group(2)]);
    expect(result.current.nextCursor).toBeNull();
    expect(result.current.initialError).toBe(false);
  });

  it("makes stale failures no-ops after a newer generation succeeds", async () => {
    const obsolete = deferred<ReturnType<typeof ok>>();
    searchTranslationKeysMock
      .mockReturnValueOnce(obsolete.promise as never)
      .mockResolvedValueOnce(ok(page([group(3)], null)));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    act(() => result.current.setQuery("new"));
    act(() => result.current.submitQuery());
    await settleInitial();
    expect(result.current.items).toEqual([group(3)]);

    obsolete.reject(new Error("private stale diagnostics"));
    await act(async () => Promise.resolve());
    expect(result.current.items).toEqual([group(3)]);
    expect(result.current.initialError).toBe(false);
    expect(result.current.loadMoreError).toBe(false);
  });

  it("aborts on typing before debounce and never revives a reverted generation", async () => {
    const obsolete = deferred<ReturnType<typeof ok>>();
    searchTranslationKeysMock
      .mockReturnValueOnce(obsolete.promise as never)
      .mockResolvedValueOnce(ok(page([group(2)], null)));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    const signal = searchTranslationKeysMock.mock.calls[0]?.[0]?.signal;
    act(() => result.current.setQuery("changed"));
    expect(signal?.aborted).toBe(true);
    act(() => result.current.setQuery(""));
    obsolete.resolve(ok(page([group(1)], "obsolete-cursor")));
    await settleInitial();
    expect(result.current.items).toEqual([]);
    await act(async () => vi.advanceTimersByTimeAsync(300));
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(2);
    expect(result.current.items).toEqual([group(2)]);
  });

  it.each([
    ["foreign product", { ...group(2), product_id: "other-product" }],
    [
      "foreign language",
      {
        ...group(2),
        slots: group(2).slots.map((slot) => ({ ...slot, language: "fr-FR" })),
      },
    ],
    [
      "foreign deletion",
      {
        ...group(2),
        slots: group(2).slots.map((slot) => ({ ...slot, is_deleted: true })),
      },
    ],
    [
      "foreign state",
      {
        ...group(2),
        slots: group(2).slots.map((slot) => ({
          ...slot,
          states: ["approved"],
        })),
      },
    ],
    [
      "foreign length status",
      {
        ...group(2),
        slots: group(2).slots.map((slot) => ({
          ...slot,
          within_limit_count: 0,
        })),
      },
    ],
  ])("rejects %s continuation rows without appending", async (_label, item) => {
    searchTranslationKeysMock
      .mockResolvedValueOnce(ok(page([group(1)], "cursor-2")))
      .mockResolvedValueOnce(ok(page([item as TranslationKeySummary], null)));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: {
          ...defaultFilters,
          productId: "product-alpha",
          language: "it-IT",
          state: "draft",
          violation: "within_limit",
        },
      }),
    );
    await settleInitial();
    await act(async () => result.current.loadMore());
    expect(result.current.items).toEqual([group(1)]);
    expect(result.current.loadMoreError).toBe(true);
  });

  it("rejects nonterminal continuation pages that make no identity progress", async () => {
    searchTranslationKeysMock
      .mockResolvedValueOnce(ok(page([group(1)], "cursor-2")))
      .mockResolvedValueOnce(ok(page([group(1)], "cursor-3")));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    await act(async () => result.current.loadMore());
    expect(result.current.items).toEqual([group(1)]);
    expect(result.current.nextCursor).toBe("cursor-2");
    expect(result.current.loadMoreError).toBe(true);
  });

  it("retains successful rows across load-more failure and retries without duplicates", async () => {
    const firstPage = Array.from({ length: 50 }, (_, index) =>
      group(index + 1),
    );
    const continuation = deferred<ReturnType<typeof ok>>();
    searchTranslationKeysMock
      .mockResolvedValueOnce(ok(page(firstPage, "cursor-2")))
      .mockReturnValueOnce(continuation.promise as never)
      .mockRejectedValueOnce(new Error("bounded failure"))
      .mockResolvedValueOnce(ok(page([group(51)], null)));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    expect(result.current.items).toHaveLength(50);

    act(() => {
      void result.current.loadMore();
      void result.current.loadMore();
    });
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(2);
    continuation.reject(new Error("first continuation failure"));
    await act(async () => Promise.resolve());
    expect(result.current.items).toHaveLength(50);
    expect(result.current.loadMoreError).toBe(true);
    expect(result.current.canRetryLoadMore).toBe(true);

    await act(async () => result.current.retryLoadMore());
    expect(result.current.items).toHaveLength(50);
    expect(result.current.loadMoreError).toBe(true);

    await act(async () => result.current.retryLoadMore());
    expect(
      result.current.items.map(({ translation_key_id }) => translation_key_id),
    ).toEqual(Array.from({ length: 51 }, (_, index) => `group-${index + 1}`));
    expect(searchTranslationKeysMock.mock.calls[3]?.[0]?.query?.cursor).toBe(
      "cursor-2",
    );
    expect(result.current.isEnd).toBe(true);
    expect(result.current.loadMoreError).toBe(false);
  });

  it.each([
    ["empty cursor", page([group(51)], "")],
    ["repeated cursor", page([group(51)], "cursor-2")],
    ["empty non-terminal page", page([], "cursor-3")],
    [
      "over-bound page",
      page(
        Array.from({ length: 51 }, (_, index) => group(index + 51)),
        null,
      ),
    ],
  ])(
    "rejects an impossible %s continuation without replacing rows",
    async (_case, badPage) => {
      const firstPage = Array.from({ length: 50 }, (_, index) =>
        group(index + 1),
      );
      searchTranslationKeysMock
        .mockResolvedValueOnce(ok(page(firstPage, "cursor-2")))
        .mockResolvedValueOnce(ok(badPage));
      const { result } = renderHook(() =>
        useTranslationSearch({
          accessToken: "memory-only-bearer",
          initialFilters: defaultFilters,
        }),
      );
      await settleInitial();
      expect(result.current.items).toHaveLength(50);

      await act(async () => result.current.loadMore());

      expect(result.current.items).toEqual(firstPage);
      expect(result.current.nextCursor).toBe("cursor-2");
      expect(result.current.loadMoreError).toBe(true);
    },
  );

  it("does not request after the terminal cursor or while a continuation is active", async () => {
    const continuation = deferred<ReturnType<typeof ok>>();
    searchTranslationKeysMock
      .mockResolvedValueOnce(ok(page([group(1)], "cursor-2")))
      .mockReturnValueOnce(continuation.promise as never);
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    expect(result.current.items).toEqual([group(1)]);

    act(() => {
      void result.current.loadMore();
      void result.current.loadMore();
    });
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(2);
    continuation.resolve(ok(page([group(2)], null)));
    await act(async () => Promise.resolve());
    await act(async () => result.current.loadMore());
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(2);
  });

  it("restores query, filters, loaded pages, scroll anchor, and focused group only in memory", async () => {
    searchTranslationKeysMock.mockResolvedValue(
      ok(page([group(1), group(2)], null)),
    );
    const first = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: { ...defaultFilters, language: "it-IT" },
        initialQuery: "settings",
      }),
    );
    await settleInitial();
    expect(first.result.current.items).toHaveLength(2);
    const snapshot = first.result.current.createSnapshot(864, "group-2");
    first.unmount();
    searchTranslationKeysMock.mockClear();

    const restored = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: snapshot.filters,
        initialQuery: snapshot.query,
        initialSnapshot: snapshot,
      }),
    );
    await settleInitial();

    expect(searchTranslationKeysMock).not.toHaveBeenCalled();
    expect(restored.result.current.query).toBe("settings");
    expect(restored.result.current.filters).toEqual({
      ...defaultFilters,
      language: "it-IT",
    });
    expect(restored.result.current.items).toEqual([group(1), group(2)]);
    expect(restored.result.current.restoredNavigation).toEqual({
      scrollAnchor: 864,
      focusedGroupId: "group-2",
    });
    expect(localStorage).toHaveLength(0);
    expect(sessionStorage).toHaveLength(0);
  });

  it("bounds duplicate initial retries and separates initial from appended loading", async () => {
    const retry = deferred<ReturnType<typeof ok>>();
    searchTranslationKeysMock
      .mockRejectedValueOnce(new Error("private detail"))
      .mockReturnValueOnce(retry.promise as never);
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "token",
        initialFilters: defaultFilters,
      }),
    );
    expect(result.current.isInitialLoading).toBe(true);
    await settleInitial();
    expect(result.current.canRetryInitial).toBe(true);
    act(() => {
      void result.current.retryInitial();
      void result.current.retryInitial();
    });
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(2);
    expect(result.current.isInitialLoading).toBe(true);
    expect(result.current.loadingMore).toBe(false);
    retry.resolve(ok(page([group(1)], null)));
    await settleInitial();
    expect(result.current.initialError).toBe(false);
    act(() => {
      result.current.submitQuery();
      result.current.setFilters({ ...defaultFilters });
    });
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(2);
  });

  it.each(["success", "failure"])(
    "ignores stale continuation %s after filters change",
    async (outcome) => {
      const obsolete = deferred<ReturnType<typeof ok>>();
      searchTranslationKeysMock
        .mockResolvedValueOnce(ok(page([group(1)], "old-cursor")))
        .mockReturnValueOnce(obsolete.promise as never)
        .mockResolvedValueOnce(ok(page([group(3)], null)));
      const { result } = renderHook(() =>
        useTranslationSearch({
          accessToken: "token",
          initialFilters: defaultFilters,
        }),
      );
      await settleInitial();
      act(() => {
        void result.current.loadMore();
      });
      expect(result.current.loadingMore).toBe(true);
      expect(result.current.items).toEqual([group(1)]);
      act(() =>
        result.current.setFilters({ ...defaultFilters, language: "it-IT" }),
      );
      await settleInitial();
      if (outcome === "success")
        obsolete.resolve(ok(page([group(2)], "foreign-cursor")));
      else obsolete.reject(new Error("private stale error"));
      await settleInitial();
      expect(result.current.items).toEqual([group(3)]);
      expect(result.current.nextCursor).toBeNull();
      expect(result.current.loadMoreError).toBe(false);
    },
  );

  it("rejects mismatched snapshots and cancels work on unmount", async () => {
    searchTranslationKeysMock.mockResolvedValueOnce(ok(page([group(1)], null)));
    const first = renderHook(() =>
      useTranslationSearch({
        accessToken: "token",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    const snapshot = first.result.current.createSnapshot(10, "group-1");
    first.unmount();
    const pending = deferred<ReturnType<typeof ok>>();
    searchTranslationKeysMock.mockReturnValueOnce(pending.promise as never);
    const next = renderHook(() =>
      useTranslationSearch({
        accessToken: "token",
        initialFilters: defaultFilters,
        initialSnapshot: { ...snapshot, query: "foreign query" },
      }),
    );
    await settleInitial();
    expect(next.result.current.items).toEqual([]);
    expect(next.result.current.restoredNavigation).toBeNull();
    expect(searchTranslationKeysMock).toHaveBeenCalledTimes(2);
    const signal = searchTranslationKeysMock.mock.calls[1]?.[0]?.signal;
    next.unmount();
    expect(signal?.aborted).toBe(true);
    pending.resolve(ok(page([group(2)], null)));
    await settleInitial();
  });
});

it.each(["duplicate", "wrong-selection", "borrowed-group"])(
  "rejects %s language slots",
  async (kind) => {
    const data = page([group(1)], null);
    if (kind === "duplicate") data.items[0].slots[1] = data.items[0].slots[0];
    if (kind === "wrong-selection") data.visible_languages = ["fr"];
    if (kind === "borrowed-group")
      data.items[0].slots[1].group_id = data.items[0].slots[0].group_id;
    searchTranslationKeysMock.mockReset();
    searchTranslationKeysMock.mockResolvedValue(ok(data));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "token",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    expect(result.current.initialError).toBe(true);
    expect(result.current.items).toEqual([]);
  },
);

it("accepts visible source context when the matching focus locale is intentionally hidden", async () => {
  searchTranslationKeysMock.mockReset();
  const data = page([group(1)], null);
  data.visible_languages = ["en"];
  data.items[0].slots = data.items[0].slots.slice(0, 1);
  searchTranslationKeysMock.mockResolvedValue(ok(data));
  const { result } = renderHook(() =>
    useTranslationSearch({
      accessToken: "token",
      initialFilters: {
        ...defaultFilters,
        language: "it-IT",
        visibleLanguages: ["en"],
      },
    }),
  );
  await settleInitial();
  expect(result.current.initialError).toBe(false);
  expect(result.current.items).toHaveLength(1);
});

it("accepts a current key with a repository-deleted language row omitted", async () => {
  searchTranslationKeysMock.mockReset();
  const data = page([group(1)], null);
  data.items[0].slots.pop();
  searchTranslationKeysMock.mockResolvedValue(ok(data));
  const { result } = renderHook(() =>
    useTranslationSearch({
      accessToken: "token",
      initialFilters: defaultFilters,
    }),
  );
  await settleInitial();
  expect(result.current.initialError).toBe(false);
  expect(result.current.items[0].slots).toHaveLength(1);
});

it("keeps repository-specific language subsets across global result pages", async () => {
  searchTranslationKeysMock.mockReset();
  const first = group(1);
  first.slots = first.slots.slice(0, 1);
  const second = {
    ...group(2),
    product_id: "product-beta",
    scope_id: "scope-beta",
  };
  second.slots = second.slots.slice(1);
  searchTranslationKeysMock
    .mockResolvedValueOnce(ok(page([first], "next")))
    .mockResolvedValueOnce(ok(page([second], null)));
  const { result } = renderHook(() =>
    useTranslationSearch({
      accessToken: "token",
      initialFilters: defaultFilters,
    }),
  );
  await settleInitial();
  await act(async () => {
    await result.current.loadMore();
  });
  expect(result.current.initialError).toBe(false);
  expect(result.current.loadMoreError).toBe(false);
  expect(
    result.current.items.map((item) => item.slots.map((slot) => slot.language)),
  ).toEqual([["en"], ["it-IT"]]);
});
