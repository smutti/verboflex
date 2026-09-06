import { useCallback, useEffect, useRef, useState } from "react";

import {
  searchTranslations,
  type SearchTranslationsData,
  type TranslationGroupSummaryResponse,
  type TranslationSearchPageResponse,
} from "../../api/client";
import type { TranslationSearchPreferences } from "./translationPreferences";

const TRANSLATION_PAGE_SIZE = 50 as const;
const SEARCH_DEBOUNCE_MS = 300;
const SNAPSHOT_VERSION = 1 as const;

type SearchQuery = NonNullable<SearchTranslationsData["query"]>;

export interface TranslationSearchFilters extends TranslationSearchPreferences {
  state: SearchQuery["state"];
  violation: SearchQuery["violation"];
  deleted: NonNullable<SearchQuery["deleted"]>;
}

export interface TranslationSearchSnapshot {
  version: typeof SNAPSHOT_VERSION;
  requestIdentity: string;
  query: string;
  filters: TranslationSearchFilters;
  pages: readonly TranslationSearchPageResponse[];
  scrollAnchor: number;
  focusedGroupId: string | null;
  invalidated?: boolean;
  measurements?: import("@tanstack/react-virtual").VirtualItem[];
  viewportWidth?: number;
}

export interface UseTranslationSearchOptions {
  accessToken: string;
  initialFilters: TranslationSearchFilters;
  initialQuery?: string;
  initialSnapshot?: TranslationSearchSnapshot | null;
}

type SearchStatus = "error" | "loading" | "ready";
type RequestKind = "initial" | "more";

interface SearchState {
  items: readonly TranslationGroupSummaryResponse[];
  pages: readonly TranslationSearchPageResponse[];
  nextCursor: string | null;
  requestIdentity: string;
  status: SearchStatus;
  loadingMore: boolean;
  loadMoreError: boolean;
}

interface ActiveRequest {
  controller: AbortController;
  cursor: string | null;
  generation: number;
  identity: string;
  kind: RequestKind;
}

interface RestoredState {
  filters: TranslationSearchFilters;
  navigation: {
    scrollAnchor: number;
    focusedGroupId: string | null;
  } | null;
  query: string;
  search: SearchState | null;
  cursors: Set<string>;
}

const STATES = new Set(["draft", "approved", "rejected"]);
const VIOLATIONS = new Set(["over_limit", "within_limit", "no_max"]);
const DELETED = new Set(["active", "deleted", "all"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function normalizeFilters(filters: TranslationSearchFilters) {
  const state = filters.state;
  const violation = filters.violation;
  const deleted = filters.deleted;
  return {
    productId: nullableString(filters.productId),
    language: nullableString(filters.language),
    state:
      typeof state === "string" && STATES.has(state) ? state : (null as null),
    violation:
      typeof violation === "string" && VIOLATIONS.has(violation)
        ? violation
        : (null as null),
    deleted:
      typeof deleted === "string" && DELETED.has(deleted)
        ? deleted
        : ("active" as const),
  } as TranslationSearchFilters;
}

export function translationSearchIdentity(
  query: string,
  filters: TranslationSearchFilters,
): string {
  const normalized = normalizeFilters(filters);
  return JSON.stringify({
    query,
    productId: normalized.productId,
    language: normalized.language,
    state: normalized.state,
    violation: normalized.violation,
    deleted: normalized.deleted,
    pageSize: TRANSLATION_PAGE_SIZE,
  });
}

function requestQuery(
  query: string,
  filters: TranslationSearchFilters,
  cursor: string | null,
): SearchQuery {
  return {
    q: query,
    product_id: filters.productId,
    language: filters.language,
    state: filters.state,
    violation: filters.violation,
    deleted: filters.deleted,
    page_size: TRANSLATION_PAGE_SIZE,
    cursor,
  };
}

function mergeGroups(
  current: readonly TranslationGroupSummaryResponse[],
  incoming: readonly TranslationGroupSummaryResponse[],
) {
  const seen = new Set(current.map(({ id }) => id));
  const merged = [...current];
  for (const item of incoming) {
    if (!seen.has(item.id)) {
      seen.add(item.id);
      merged.push(item);
    }
  }
  return merged;
}

function validPage(
  page: unknown,
  seenCursors: ReadonlySet<string>,
  filters: TranslationSearchFilters,
  current: readonly TranslationGroupSummaryResponse[] = [],
): page is TranslationSearchPageResponse {
  if (
    !isRecord(page) ||
    !Array.isArray(page.items) ||
    page.items.length > TRANSLATION_PAGE_SIZE ||
    !page.items.every(
      (item) =>
        isRecord(item) &&
        typeof item.id === "string" &&
        item.id.length > 0 &&
        (filters.productId === null || item.product_id === filters.productId) &&
        (filters.language === null || item.language === filters.language) &&
        (filters.deleted === "all" ||
          item.is_deleted === (filters.deleted === "deleted")) &&
        (filters.state == null ||
          (Array.isArray(item.states) &&
            item.states.includes(filters.state))) &&
        (filters.violation == null ||
          (filters.violation === "over_limit" &&
            Number(item.over_limit_count) > 0) ||
          (filters.violation === "within_limit" &&
            Number(item.within_limit_count) > 0) ||
          (filters.violation === "no_max" && Number(item.no_max_count) > 0)),
    )
  ) {
    return false;
  }
  const nextCursor = page.next_cursor ?? null;
  if (nextCursor !== null && typeof nextCursor !== "string") {
    return false;
  }
  if (nextCursor === "") {
    return false;
  }
  if (nextCursor !== null && page.items.length === 0) {
    return false;
  }
  const currentIds = new Set(current.map(({ id }) => id));
  if (
    nextCursor !== null &&
    page.items.every((item) => currentIds.has(item.id))
  ) {
    return false;
  }
  return nextCursor === null || !seenCursors.has(nextCursor);
}

function restoreSnapshot(
  initialSnapshot: TranslationSearchSnapshot | null | undefined,
  initialQuery: string,
  initialFilters: TranslationSearchFilters,
): RestoredState {
  const fallback: RestoredState = {
    filters: normalizeFilters(initialFilters),
    navigation: null,
    query: initialQuery,
    search: null,
    cursors: new Set(),
  };
  if (
    !isRecord(initialSnapshot) ||
    initialSnapshot.version !== SNAPSHOT_VERSION ||
    typeof initialSnapshot.query !== "string" ||
    !isRecord(initialSnapshot.filters) ||
    !Array.isArray(initialSnapshot.pages) ||
    !Number.isFinite(initialSnapshot.scrollAnchor) ||
    initialSnapshot.scrollAnchor < 0 ||
    (initialSnapshot.focusedGroupId !== null &&
      typeof initialSnapshot.focusedGroupId !== "string")
  ) {
    return fallback;
  }

  const filters = normalizeFilters(
    initialSnapshot.filters as unknown as TranslationSearchFilters,
  );
  const identity = translationSearchIdentity(initialSnapshot.query, filters);
  if (
    initialSnapshot.invalidated === true &&
    initialSnapshot.requestIdentity === identity
  ) {
    return {
      ...fallback,
      filters,
      query: initialSnapshot.query,
      navigation: {
        scrollAnchor: initialSnapshot.scrollAnchor,
        focusedGroupId: initialSnapshot.focusedGroupId,
      },
    };
  }
  const cursors = new Set<string>();
  let items: readonly TranslationGroupSummaryResponse[] = [];
  for (const [index, page] of initialSnapshot.pages.entries()) {
    if (!validPage(page, cursors, filters, items)) {
      return fallback;
    }
    const nextCursor = page.next_cursor ?? null;
    if (index < initialSnapshot.pages.length - 1 && nextCursor === null) {
      return fallback;
    }
    if (nextCursor !== null) {
      cursors.add(nextCursor);
    }
    items = mergeGroups(items, page.items);
  }
  if (
    initialSnapshot.pages.length === 0 ||
    initialSnapshot.requestIdentity !== identity
  ) {
    return fallback;
  }

  const finalPage = initialSnapshot.pages.at(-1);
  return {
    filters,
    navigation: {
      scrollAnchor: initialSnapshot.scrollAnchor,
      focusedGroupId: initialSnapshot.focusedGroupId,
    },
    query: initialSnapshot.query,
    search: {
      items,
      pages: initialSnapshot.pages,
      nextCursor: finalPage?.next_cursor ?? null,
      requestIdentity: identity,
      status: "ready",
      loadingMore: false,
      loadMoreError: false,
    },
    cursors,
  };
}

export function useTranslationSearch({
  accessToken,
  initialFilters,
  initialQuery = "",
  initialSnapshot,
}: UseTranslationSearchOptions) {
  const [restored] = useState(() =>
    restoreSnapshot(initialSnapshot, initialQuery, initialFilters),
  );
  const initialIdentity = translationSearchIdentity(
    restored.query,
    restored.filters,
  );
  const initialSearch: SearchState = restored.search ?? {
    items: [],
    pages: [],
    nextCursor: null,
    requestIdentity: initialIdentity,
    status: "loading",
    loadingMore: false,
    loadMoreError: false,
  };

  const [query, setQueryState] = useState(restored.query);
  const [filters, setFiltersState] = useState(restored.filters);
  const [search, setSearchState] = useState<SearchState>(initialSearch);
  const accessTokenRef = useRef(accessToken);
  const queryRef = useRef(restored.query);
  const filtersRef = useRef(restored.filters);
  const searchRef = useRef(initialSearch);
  const cursorsRef = useRef(restored.cursors);
  const generationRef = useRef(0);
  const activeRequestRef = useRef<ActiveRequest | null>(null);
  const debounceRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  const updateSearch = useCallback((next: SearchState) => {
    searchRef.current = next;
    setSearchState(next);
  }, []);

  const requestIsCurrent = useCallback((request: ActiveRequest) => {
    return (
      mountedRef.current &&
      !request.controller.signal.aborted &&
      activeRequestRef.current === request &&
      generationRef.current === request.generation &&
      translationSearchIdentity(queryRef.current, filtersRef.current) ===
        request.identity
    );
  }, []);

  const startInitial = useCallback(
    (
      nextQuery: string,
      nextFilters: TranslationSearchFilters,
      force = false,
    ) => {
      const normalizedFilters = normalizeFilters(nextFilters);
      const identity = translationSearchIdentity(nextQuery, normalizedFilters);
      const currentRequest = activeRequestRef.current;
      if (
        !force &&
        ((currentRequest?.kind === "initial" &&
          currentRequest.identity === identity) ||
          (searchRef.current.status === "ready" &&
            searchRef.current.requestIdentity === identity))
      ) {
        return;
      }

      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
      generationRef.current += 1;
      activeRequestRef.current?.controller.abort();
      const controller = new AbortController();
      const request: ActiveRequest = {
        controller,
        cursor: null,
        generation: generationRef.current,
        identity,
        kind: "initial",
      };
      activeRequestRef.current = request;
      cursorsRef.current = new Set();
      updateSearch({
        items: [],
        pages: [],
        nextCursor: null,
        requestIdentity: identity,
        status: "loading",
        loadingMore: false,
        loadMoreError: false,
      });

      const pending = searchTranslations({
        auth: accessTokenRef.current,
        query: requestQuery(nextQuery, normalizedFilters, null),
        signal: controller.signal,
      });
      void (async () => {
        try {
          const result = await pending;
          if (!requestIsCurrent(request)) {
            return;
          }
          if (
            result.data === undefined ||
            !validPage(result.data, new Set(), normalizedFilters)
          ) {
            throw new Error("Translation search unavailable");
          }
          const nextCursor = result.data.next_cursor ?? null;
          if (nextCursor !== null) {
            cursorsRef.current.add(nextCursor);
          }
          updateSearch({
            items: mergeGroups([], result.data.items),
            pages: [result.data],
            nextCursor,
            requestIdentity: identity,
            status: "ready",
            loadingMore: false,
            loadMoreError: false,
          });
        } catch {
          if (requestIsCurrent(request)) {
            updateSearch({
              items: [],
              pages: [],
              nextCursor: null,
              requestIdentity: identity,
              status: "error",
              loadingMore: false,
              loadMoreError: false,
            });
          }
        } finally {
          if (activeRequestRef.current === request) {
            activeRequestRef.current = null;
          }
        }
      })();
    },
    [requestIsCurrent, updateSearch],
  );

  const requestMore = useCallback(
    async (retry = false) => {
      const current = searchRef.current;
      const cursor = current.nextCursor;
      if (
        current.status !== "ready" ||
        cursor === null ||
        activeRequestRef.current !== null ||
        (!retry && current.loadMoreError)
      ) {
        return;
      }

      const identity = translationSearchIdentity(
        queryRef.current,
        filtersRef.current,
      );
      // Ready state with a cursor comes only from a validated page/snapshot.
      // Criteria changes synchronously clear its cursor or enter loading;
      // response authority is rechecked after the await below.
      const controller = new AbortController();
      const request: ActiveRequest = {
        controller,
        cursor,
        generation: generationRef.current,
        identity,
        kind: "more",
      };
      activeRequestRef.current = request;
      updateSearch({
        ...current,
        loadingMore: true,
        loadMoreError: false,
      });

      try {
        const result = await searchTranslations({
          auth: accessTokenRef.current,
          query: requestQuery(queryRef.current, filtersRef.current, cursor),
          signal: controller.signal,
        });
        if (
          !requestIsCurrent(request) ||
          searchRef.current.requestIdentity !== identity ||
          searchRef.current.nextCursor !== cursor
        ) {
          return;
        }
        if (
          result.data === undefined ||
          !validPage(
            result.data,
            cursorsRef.current,
            filtersRef.current,
            searchRef.current.items,
          )
        ) {
          throw new Error("Invalid translation continuation");
        }
        const nextCursor = result.data.next_cursor ?? null;
        if (nextCursor !== null) {
          cursorsRef.current.add(nextCursor);
        }
        const latest = searchRef.current;
        updateSearch({
          ...latest,
          items: mergeGroups(latest.items, result.data.items),
          pages: [...latest.pages, result.data],
          nextCursor,
          loadingMore: false,
          loadMoreError: false,
        });
      } catch {
        if (requestIsCurrent(request)) {
          updateSearch({
            ...searchRef.current,
            loadingMore: false,
            loadMoreError: true,
          });
        }
      } finally {
        if (activeRequestRef.current === request) {
          activeRequestRef.current = null;
        }
      }
    },
    [requestIsCurrent, updateSearch],
  );

  useEffect(() => {
    mountedRef.current = true;
    if (restored.search === null) {
      const generation = generationRef.current;
      queueMicrotask(() => {
        if (mountedRef.current && generationRef.current === generation) {
          startInitial(queryRef.current, filtersRef.current);
        }
      });
    }
    return () => {
      mountedRef.current = false;
      generationRef.current += 1;
      activeRequestRef.current?.controller.abort();
      activeRequestRef.current = null;
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
    };
  }, [restored.search, startInitial]);

  useEffect(() => {
    if (accessTokenRef.current === accessToken) {
      return;
    }
    accessTokenRef.current = accessToken;
    startInitial(queryRef.current, filtersRef.current, true);
  }, [accessToken, startInitial]);

  const setQuery = useCallback(
    (nextQuery: string) => {
      if (nextQuery === queryRef.current) {
        return;
      }
      generationRef.current += 1;
      activeRequestRef.current?.controller.abort();
      activeRequestRef.current = null;
      cursorsRef.current = new Set();
      updateSearch({
        ...searchRef.current,
        nextCursor: null,
        requestIdentity: "",
        loadingMore: false,
        loadMoreError: false,
      });
      queryRef.current = nextQuery;
      setQueryState(nextQuery);
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current);
      }
      debounceRef.current = window.setTimeout(() => {
        debounceRef.current = null;
        startInitial(nextQuery, filtersRef.current);
      }, SEARCH_DEBOUNCE_MS);
    },
    [startInitial, updateSearch],
  );

  const submitQuery = useCallback(() => {
    if (debounceRef.current !== null) {
      window.clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    startInitial(queryRef.current, filtersRef.current);
  }, [startInitial]);

  const clearQuery = useCallback(() => {
    queryRef.current = "";
    setQueryState("");
    if (debounceRef.current !== null) {
      window.clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    startInitial("", filtersRef.current);
  }, [startInitial]);

  const setFilters = useCallback(
    (nextFilters: TranslationSearchFilters) => {
      const normalized = normalizeFilters(nextFilters);
      filtersRef.current = normalized;
      setFiltersState(normalized);
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
      startInitial(queryRef.current, normalized);
    },
    [startInitial],
  );

  const retryInitial = useCallback(async () => {
    if (searchRef.current.status === "error") {
      startInitial(queryRef.current, filtersRef.current, true);
    }
  }, [startInitial]);

  const retryLoadMore = useCallback(async () => {
    if (searchRef.current.loadMoreError) {
      await requestMore(true);
    }
  }, [requestMore]);

  const createSnapshot = useCallback(
    (scrollAnchor: number, focusedGroupId: string | null) => ({
      version: SNAPSHOT_VERSION,
      requestIdentity: searchRef.current.requestIdentity,
      query: queryRef.current,
      filters: { ...filtersRef.current },
      pages: searchRef.current.pages.map((page) => ({
        items: [...page.items],
        next_cursor: page.next_cursor ?? null,
      })),
      scrollAnchor: Math.max(
        0,
        Number.isFinite(scrollAnchor) ? scrollAnchor : 0,
      ),
      focusedGroupId,
    }),
    [],
  );

  return {
    query,
    filters,
    items: search.items,
    nextCursor: search.nextCursor,
    requestIdentity: search.requestIdentity,
    status: search.status,
    isInitialLoading: search.status === "loading",
    initialError: search.status === "error",
    loadingMore: search.loadingMore,
    loadMoreError: search.loadMoreError,
    canRetryInitial: search.status === "error",
    canRetryLoadMore:
      search.status === "ready" &&
      search.loadMoreError &&
      search.nextCursor !== null,
    isEnd: search.status === "ready" && search.nextCursor === null,
    restoredNavigation: restored.navigation,
    setQuery,
    submitQuery,
    clearQuery,
    setFilters,
    loadMore: requestMore,
    retryInitial,
    retryLoadMore,
    createSnapshot,
  };
}
