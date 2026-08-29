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
});
