import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  searchTranslations,
  type TranslationGroupSummaryResponse,
  type TranslationSearchPageResponse,
} from "../../api/client";
import {
  translationSearchIdentity,
  useTranslationSearch,
  type TranslationSearchFilters,
} from "./useTranslationSearch";

vi.mock("../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/client")>();
  return { ...original, searchTranslations: vi.fn() };
});

const searchTranslationsMock = vi.mocked(searchTranslations);

const defaultFilters: TranslationSearchFilters = {
  productId: null,
  language: null,
  state: null,
  violation: null,
  deleted: "active",
};

function group(index: number): TranslationGroupSummaryResponse {
  return {
    has_no_max: false,
    has_over_limit: false,
    id: `group-${index}`,
    is_deleted: false,
    language: "it-IT",
    language_label: "Italian",
    no_max_count: 0,
    over_limit_count: 0,
    product_id: "product-alpha",
    product_name: "Alpha",
    rank: index,
    raw_key: `key.${index}`,
    source_text: `Source ${index}`,
    source_language: "en",
    selector_kinds: ["scalar"],
    provenance: null,
    state_summary: "draft",
    states: ["draft"],
    translated_text: `Translation ${index}`,
    value_count: 1,
    within_limit_count: 1,
  };
}

function page(
  items: TranslationGroupSummaryResponse[],
  nextCursor: string | null,
): TranslationSearchPageResponse {
  return { items, next_cursor: nextCursor };
}

function ok(data: TranslationSearchPageResponse) {
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
  beforeEach(() => {
    vi.useFakeTimers();
    searchTranslationsMock.mockReset();
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("binds the complete canonical identity and fixed 50-group first page", async () => {
    const approved: TranslationGroupSummaryResponse = {
      ...group(1),
      state_summary: "approved",
      states: ["approved"],
    };
    searchTranslationsMock.mockResolvedValue(ok(page([approved], null)));
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

    expect(searchTranslationsMock).toHaveBeenCalledOnce();
    expect(searchTranslationsMock).toHaveBeenCalledWith({
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

  it("coalesces typing for 300ms while Enter and clear run once immediately", async () => {
    searchTranslationsMock.mockResolvedValue(ok(page([], null)));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    expect(searchTranslationsMock).toHaveBeenCalledOnce();

    act(() => {
      result.current.setQuery("fir");
      result.current.setQuery("first");
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(299);
    });
    expect(searchTranslationsMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(searchTranslationsMock).toHaveBeenCalledTimes(2);
    expect(searchTranslationsMock.mock.calls[1]?.[0]?.query?.q).toBe("first");

    act(() => {
      result.current.setQuery("run on Enter");
      result.current.submitQuery();
    });
    expect(searchTranslationsMock).toHaveBeenCalledTimes(3);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });
    expect(searchTranslationsMock).toHaveBeenCalledTimes(3);

    act(() => {
      result.current.setQuery("will be cleared");
      result.current.clearQuery();
    });
    expect(searchTranslationsMock).toHaveBeenCalledTimes(4);
    expect(searchTranslationsMock.mock.calls[3]?.[0]?.query?.q).toBe("");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });
    expect(searchTranslationsMock).toHaveBeenCalledTimes(4);
  });

  it("applies filters immediately, aborts the old generation, and ignores stale success", async () => {
    const obsolete = deferred<ReturnType<typeof ok>>();
    searchTranslationsMock
      .mockReturnValueOnce(obsolete.promise as never)
      .mockResolvedValueOnce(ok(page([group(2)], null)));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    expect(searchTranslationsMock).toHaveBeenCalledOnce();
    const obsoleteSignal = searchTranslationsMock.mock.calls[0]?.[0]?.signal;

    act(() => {
      result.current.setFilters({
        ...defaultFilters,
        productId: "product-alpha",
      });
    });
    expect(searchTranslationsMock).toHaveBeenCalledTimes(2);
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
    searchTranslationsMock
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
    searchTranslationsMock
      .mockReturnValueOnce(obsolete.promise as never)
      .mockResolvedValueOnce(ok(page([group(2)], null)));
    const { result } = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: defaultFilters,
      }),
    );
    await settleInitial();
    const signal = searchTranslationsMock.mock.calls[0]?.[0]?.signal;
    act(() => result.current.setQuery("changed"));
    expect(signal?.aborted).toBe(true);
    act(() => result.current.setQuery(""));
    obsolete.resolve(ok(page([group(1)], "obsolete-cursor")));
    await settleInitial();
    expect(result.current.items).toEqual([]);
    await act(async () => vi.advanceTimersByTimeAsync(300));
    expect(searchTranslationsMock).toHaveBeenCalledTimes(2);
    expect(result.current.items).toEqual([group(2)]);
  });

  it.each([
    ["foreign product", { ...group(2), product_id: "other-product" }],
    ["foreign language", { ...group(2), language: "fr-FR" }],
    ["foreign deletion", { ...group(2), is_deleted: true }],
    ["foreign state", { ...group(2), states: ["approved"] }],
    ["foreign length status", { ...group(2), within_limit_count: 0 }],
  ])("rejects %s continuation rows without appending", async (_label, item) => {
    searchTranslationsMock
      .mockResolvedValueOnce(ok(page([group(1)], "cursor-2")))
      .mockResolvedValueOnce(
        ok(page([item as TranslationGroupSummaryResponse], null)),
      );
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
    searchTranslationsMock
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
    searchTranslationsMock
      .mockResolvedValueOnce(ok(page(firstPage, "cursor-2")))
      .mockReturnValueOnce(continuation.promise as never)
      .mockRejectedValueOnce(new Error("bounded failure"))
      .mockResolvedValueOnce(ok(page([group(50), group(51), group(51)], null)));
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
    expect(searchTranslationsMock).toHaveBeenCalledTimes(2);
    continuation.reject(new Error("first continuation failure"));
    await act(async () => Promise.resolve());
    expect(result.current.items).toHaveLength(50);
    expect(result.current.loadMoreError).toBe(true);
    expect(result.current.canRetryLoadMore).toBe(true);

    await act(async () => result.current.retryLoadMore());
    expect(result.current.items).toHaveLength(50);
    expect(result.current.loadMoreError).toBe(true);

    await act(async () => result.current.retryLoadMore());
    expect(result.current.items.map(({ id }) => id)).toEqual(
      Array.from({ length: 51 }, (_, index) => `group-${index + 1}`),
    );
    expect(searchTranslationsMock.mock.calls[3]?.[0]?.query?.cursor).toBe(
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
      searchTranslationsMock
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
    searchTranslationsMock
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
    expect(searchTranslationsMock).toHaveBeenCalledTimes(2);
    continuation.resolve(ok(page([group(2)], null)));
    await act(async () => Promise.resolve());
    await act(async () => result.current.loadMore());
    expect(searchTranslationsMock).toHaveBeenCalledTimes(2);
  });

  it("restores query, filters, loaded pages, scroll anchor, and focused group only in memory", async () => {
    searchTranslationsMock.mockResolvedValue(
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
    searchTranslationsMock.mockClear();

    const restored = renderHook(() =>
      useTranslationSearch({
        accessToken: "memory-only-bearer",
        initialFilters: defaultFilters,
        initialSnapshot: snapshot,
      }),
    );
    await settleInitial();

    expect(searchTranslationsMock).not.toHaveBeenCalled();
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
    searchTranslationsMock
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
    expect(searchTranslationsMock).toHaveBeenCalledTimes(2);
    expect(result.current.isInitialLoading).toBe(true);
    expect(result.current.loadingMore).toBe(false);
    retry.resolve(ok(page([group(1)], null)));
    await settleInitial();
    expect(result.current.initialError).toBe(false);
    act(() => {
      result.current.submitQuery();
      result.current.setFilters({ ...defaultFilters });
    });
    expect(searchTranslationsMock).toHaveBeenCalledTimes(2);
  });

  it.each(["success", "failure"])(
    "ignores stale continuation %s after filters change",
    async (outcome) => {
      const obsolete = deferred<ReturnType<typeof ok>>();
      searchTranslationsMock
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
    searchTranslationsMock.mockResolvedValueOnce(ok(page([group(1)], null)));
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
    searchTranslationsMock.mockReturnValueOnce(pending.promise as never);
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
    expect(searchTranslationsMock).toHaveBeenCalledTimes(2);
    const signal = searchTranslationsMock.mock.calls[1]?.[0]?.signal;
    next.unmount();
    expect(signal?.aborted).toBe(true);
    pending.resolve(ok(page([group(2)], null)));
    await settleInitial();
  });
});
