import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useCursorCollection } from "./useCursorCollection";

interface Item {
  id: string;
  label: string;
}

function item(index: number): Item {
  return { id: `item-${index}`, label: `Item ${index}` };
}

describe("useCursorCollection", () => {
  it("lets an explicit reload supersede the queued initial request", async () => {
    const loadPage = vi.fn().mockResolvedValue({
      items: [item(1)],
      next_cursor: null,
    });
    const { result } = renderHook(() =>
      useCursorCollection({
        getItemId: (entry: Item) => entry.id,
        loadPage,
        queryKey: "reload-before-microtask",
      }),
    );

    await act(async () => result.current.reload());
    await waitFor(() => expect(result.current.items).toEqual([item(1)]));
    expect(loadPage).toHaveBeenCalledOnce();
  });

  it("drops an initial microtask whose generation was synchronously replaced", async () => {
    const queued: VoidFunction[] = [];
    const queue = vi
      .spyOn(globalThis, "queueMicrotask")
      .mockImplementation((callback) => queued.push(callback));
    const loadPage = vi
      .fn()
      .mockResolvedValue({ items: [item(1)], next_cursor: null });
    const { result, rerender } = renderHook(
      ({ queryKey }) =>
        useCursorCollection({
          getItemId: (entry: Item) => entry.id,
          loadPage,
          queryKey,
        }),
      { initialProps: { queryKey: "first-generation" } },
    );
    rerender({ queryKey: "second-generation" });
    await act(async () => {
      const callbacks = queued.splice(0);
      callbacks.forEach((callback) => callback());
      callbacks.at(-1)?.();
      await Promise.resolve();
    });
    expect(loadPage).toHaveBeenCalledOnce();
    expect(result.current.items).toEqual([item(1)]);
    queue.mockRestore();
  });

  it("appends opaque cursor pages in response order and deduplicates stable identities", async () => {
    const firstPage = Array.from({ length: 50 }, (_, index) => item(index + 1));
    const loadPage = vi
      .fn()
      .mockResolvedValueOnce({ items: firstPage, next_cursor: "opaque-page-2" })
      .mockResolvedValueOnce({
        items: [firstPage[49], item(51)],
        next_cursor: null,
      });

    const { result } = renderHook(() =>
      useCursorCollection({
        getItemId: (entry: Item) => entry.id,
        loadPage,
        queryKey: "repositories:all",
      }),
    );

    await waitFor(() => expect(result.current.items).toHaveLength(50));
    expect(result.current.isPartial).toBe(true);

    await act(async () => {
      await result.current.loadMore();
    });

    expect(loadPage).toHaveBeenNthCalledWith(1, null, expect.any(AbortSignal));
    expect(loadPage).toHaveBeenNthCalledWith(
      2,
      "opaque-page-2",
      expect.any(AbortSignal),
    );
    expect(loadPage).toHaveBeenCalledTimes(2);
    expect(result.current.items.map((entry) => entry.id)).toEqual(
      Array.from({ length: 51 }, (_, index) => `item-${index + 1}`),
    );
    expect(result.current.isPartial).toBe(false);
    expect(result.current.isEnd).toBe(true);
  });

  it("aborts and ignores stale pages when the complete query identity changes", async () => {
    let resolveOld:
      | ((page: { items: Item[]; next_cursor: string | null }) => void)
      | undefined;
    const oldPage = new Promise<{ items: Item[]; next_cursor: string | null }>(
      (resolve) => {
        resolveOld = resolve;
      },
    );
    const signals: AbortSignal[] = [];
    const loadPage = vi.fn((cursor: string | null, signal: AbortSignal) => {
      signals.push(signal);
      return cursor === null && signals.length === 1
        ? oldPage
        : Promise.resolve({ items: [item(200)], next_cursor: null });
    });

    const { result, rerender } = renderHook(
      ({ queryKey }) =>
        useCursorCollection({
          getItemId: (entry: Item) => entry.id,
          loadPage,
          queryKey,
        }),
      { initialProps: { queryKey: "product-1:revision-1:filter-a" } },
    );

    await waitFor(() => expect(loadPage).toHaveBeenCalledTimes(1));
    rerender({ queryKey: "product-2:revision-9:filter-b" });
    await waitFor(() => expect(result.current.items).toEqual([item(200)]));
    expect(signals[0]?.aborted).toBe(true);

    resolveOld?.({ items: [item(1)], next_cursor: "stale-cursor" });
    await act(async () => Promise.resolve());

    expect(result.current.items).toEqual([item(200)]);
    expect(result.current.nextCursor).toBeNull();
    expect(loadPage).toHaveBeenCalledTimes(2);
  });

  it("recovers initial and appended failures, replaces identities, and bounds duplicate actions", async () => {
    const loadPage = vi
      .fn()
      .mockRejectedValueOnce(new Error("initial diagnostics"))
      .mockResolvedValueOnce({ items: [item(1)], next_cursor: "page-2" })
      .mockRejectedValueOnce(new Error("page diagnostics"))
      .mockResolvedValueOnce({
        items: [{ id: "item-1", label: "Updated item 1" }, item(2)],
        next_cursor: null,
      });
    const { result } = renderHook(() =>
      useCursorCollection({
        getItemId: (entry: Item) => entry.id,
        loadPage,
        queryKey: "recoverable",
      }),
    );

    await waitFor(() => expect(result.current.status).toBe("error"));
    await act(async () => {
      await result.current.loadMore();
    });
    expect(loadPage).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.reload();
    });
    expect(result.current.items).toEqual([item(1)]);

    await act(async () => {
      await Promise.all([result.current.loadMore(), result.current.loadMore()]);
    });
    expect(loadPage).toHaveBeenCalledTimes(3);
    expect(result.current.loadMoreError).toBe(true);

    await act(async () => {
      await result.current.loadMore();
    });
    expect(result.current.items).toEqual([item(1), item(2)]);
    expect(result.current.isEnd).toBe(true);

    act(() => {
      result.current.appendItems([
        { id: "item-1", label: "Appended item 1" },
        item(3),
        { id: "item-3", label: "Duplicate item 3" },
      ]);
    });
    expect(result.current.items).toEqual([item(1), item(2), item(3)]);

    act(() => {
      result.current.upsertItems([
        { id: "item-1", label: "Upserted item 1" },
        item(4),
        { id: "item-4", label: "Latest item 4" },
      ]);
    });
    expect(result.current.items).toEqual([
      { id: "item-1", label: "Upserted item 1" },
      item(2),
      item(3),
      item(4),
    ]);
  });

  it("ignores a rejected request after its query authority is aborted", async () => {
    let rejectObsolete!: (reason: Error) => void;
    const obsolete = new Promise<{ items: Item[]; next_cursor: null }>(
      (_resolve, reject) => {
        rejectObsolete = reject;
      },
    );
    const loadPage = vi
      .fn()
      .mockReturnValueOnce(obsolete)
      .mockResolvedValueOnce({ items: [item(2)], next_cursor: null });
    const { result, rerender } = renderHook(
      ({ queryKey }) =>
        useCursorCollection({
          getItemId: (entry: Item) => entry.id,
          loadPage,
          queryKey,
        }),
      { initialProps: { queryKey: "obsolete" } },
    );
    await waitFor(() => expect(loadPage).toHaveBeenCalledOnce());

    rerender({ queryKey: "successor" });
    rejectObsolete(new Error("stale failure"));
    await waitFor(() => expect(result.current.items).toEqual([item(2)]));
    expect(result.current.status).toBe("ready");
  });
});
