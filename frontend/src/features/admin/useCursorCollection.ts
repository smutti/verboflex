import { useCallback, useEffect, useRef, useState } from "react";

type CursorSlice<TItem> = Readonly<{
  items: readonly TItem[];
  next_cursor: string | null;
}>;

export interface CursorCollectionOptions<TItem> {
  getItemId: (item: TItem) => string;
  loadPage: (
    cursor: string | null,
    signal: AbortSignal,
  ) => Promise<CursorSlice<TItem>>;
  queryKey: string;
}

export type CursorCollectionStatus = "error" | "loading" | "ready";

export interface CursorCollectionState<TItem> {
  appendItems: (items: readonly TItem[]) => void;
  isEmpty: boolean;
  isEnd: boolean;
  isPartial: boolean;
  items: readonly TItem[];
  loadMore: () => Promise<void>;
  loadMoreError: boolean;
  loadingMore: boolean;
  nextCursor: string | null;
  reload: () => Promise<void>;
  status: CursorCollectionStatus;
  upsertItems: (items: readonly TItem[]) => void;
}

interface InternalState<TItem> {
  items: readonly TItem[];
  loadMoreError: boolean;
  loadingMore: boolean;
  nextCursor: string | null;
  status: CursorCollectionStatus;
}

function mergeByStableIdentity<TItem>(
  current: readonly TItem[],
  incoming: readonly TItem[],
  getItemId: (item: TItem) => string,
) {
  const seen = new Set(current.map(getItemId));
  const merged = [...current];
  for (const item of incoming) {
    const identity = getItemId(item);
    if (!seen.has(identity)) {
      seen.add(identity);
      merged.push(item);
    }
  }
  return merged;
}

function upsertByStableIdentity<TItem>(
  current: readonly TItem[],
  incoming: readonly TItem[],
  getItemId: (item: TItem) => string,
) {
  const replacements = new Map(incoming.map((item) => [getItemId(item), item]));
  const seen = new Set(current.map(getItemId));
  return [
    ...current.map((item) => replacements.get(getItemId(item)) ?? item),
    ...incoming.filter((item) => {
      const identity = getItemId(item);
      if (seen.has(identity)) {
        return false;
      }
      seen.add(identity);
      return true;
    }),
  ];
}

export function useCursorCollection<TItem>({
  getItemId,
  loadPage,
  queryKey,
}: CursorCollectionOptions<TItem>): CursorCollectionState<TItem> {
  const generationRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const inFlightRef = useRef(false);
  const getItemIdRef = useRef(getItemId);
  const loadPageRef = useRef(loadPage);
  const [state, setState] = useState<InternalState<TItem>>({
    items: [],
    loadMoreError: false,
    loadingMore: false,
    nextCursor: null,
    status: "loading",
  });

  useEffect(() => {
    getItemIdRef.current = getItemId;
    loadPageRef.current = loadPage;
  }, [getItemId, loadPage]);

  const requestPage = useCallback(
    async (cursor: string | null, append: boolean, generation: number) => {
      if (inFlightRef.current || generationRef.current !== generation) {
        return;
      }

      const controller = new AbortController();
      controllerRef.current = controller;
      inFlightRef.current = true;
      setState((current) => ({
        ...(append
          ? current
          : {
              ...current,
              items: [],
              nextCursor: null,
              status: "loading" as const,
            }),
        loadMoreError: false,
        loadingMore: append,
      }));

      try {
        const page = await loadPageRef.current(cursor, controller.signal);
        if (controller.signal.aborted || generationRef.current !== generation) {
          return;
        }
        setState((current) => ({
          items: mergeByStableIdentity(
            append ? current.items : [],
            page.items,
            getItemIdRef.current,
          ),
          loadMoreError: false,
          loadingMore: false,
          nextCursor: page.next_cursor,
          status: "ready",
        }));
      } catch {
        if (controller.signal.aborted || generationRef.current !== generation) {
          return;
        }
        setState((current) => ({
          ...current,
          loadMoreError: append,
          loadingMore: false,
          status: append ? "ready" : "error",
        }));
      } finally {
        if (
          controllerRef.current === controller &&
          generationRef.current === generation
        ) {
          controllerRef.current = null;
          inFlightRef.current = false;
        }
      }
    },
    [],
  );

  useEffect(() => {
    const generation = ++generationRef.current;
    controllerRef.current?.abort();
    controllerRef.current = null;
    inFlightRef.current = false;
    queueMicrotask(() => {
      if (generationRef.current === generation) {
        void requestPage(null, false, generation);
      }
    });

    return () => {
      if (generationRef.current === generation) {
        generationRef.current += 1;
        controllerRef.current?.abort();
        controllerRef.current = null;
        inFlightRef.current = false;
      }
    };
  }, [queryKey, requestPage]);

  const loadMore = useCallback(async () => {
    if (
      state.status !== "ready" ||
      state.nextCursor === null ||
      state.loadingMore ||
      inFlightRef.current
    ) {
      return;
    }
    await requestPage(state.nextCursor, true, generationRef.current);
  }, [requestPage, state.loadingMore, state.nextCursor, state.status]);

  const reload = useCallback(async () => {
    const generation = ++generationRef.current;
    controllerRef.current?.abort();
    controllerRef.current = null;
    inFlightRef.current = false;
    await requestPage(null, false, generation);
  }, [requestPage]);

  const appendItems = useCallback((items: readonly TItem[]) => {
    setState((current) => ({
      ...current,
      items: mergeByStableIdentity(current.items, items, getItemIdRef.current),
    }));
  }, []);

  const upsertItems = useCallback((items: readonly TItem[]) => {
    setState((current) => ({
      ...current,
      items: upsertByStableIdentity(current.items, items, getItemIdRef.current),
    }));
  }, []);

  return {
    appendItems,
    isEmpty: state.status === "ready" && state.items.length === 0,
    isEnd: state.status === "ready" && state.nextCursor === null,
    isPartial: state.status === "ready" && state.nextCursor !== null,
    items: state.items,
    loadMore,
    loadMoreError: state.loadMoreError,
    loadingMore: state.loadingMore,
    nextCursor: state.nextCursor,
    reload,
    status: state.status,
    upsertItems,
  };
}
