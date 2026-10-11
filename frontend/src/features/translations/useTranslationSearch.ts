import { useCallback, useEffect, useRef, useState } from "react";

import {
  searchTranslationKeys,
  type SearchTranslationKeysData,
  type TranslationKeySummary,
  type TranslationKeyPageResponse,
} from "../../api/client";
import type { TranslationSearchPreferences } from "./translationPreferences";

const TRANSLATION_PAGE_SIZE = 50 as const;
const SEARCH_DEBOUNCE_MS = 300;
const SNAPSHOT_VERSION = 2 as const;

type SearchQuery = NonNullable<SearchTranslationKeysData["query"]>;

export interface TranslationSearchFilters extends TranslationSearchPreferences {
  visibleLanguages?: string[] | null;
  viewMode?: "multilingual" | "bilingual";
  workStatus?: SearchQuery["work_status"];
  state: SearchQuery["state"];
  violation: SearchQuery["violation"];
  deleted: NonNullable<SearchQuery["deleted"]>;
}

export interface TranslationSearchSnapshot {
  version: typeof SNAPSHOT_VERSION;
  requestIdentity: string;
  query: string;
  filters: TranslationSearchFilters;
  pages: readonly TranslationKeyPageResponse[];
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
  items: readonly TranslationKeySummary[];
  pages: readonly TranslationKeyPageResponse[];
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
const WORK_STATUSES = new Set([
  "needs_translation",
  "needs_review",
  "source_changed",
]);

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
    visibleLanguages:
      Array.isArray(filters.visibleLanguages) &&
      filters.visibleLanguages.length &&
      new Set(filters.visibleLanguages).size <= 20
        ? [
            ...new Set(
              filters.visibleLanguages.filter(
                (code) => typeof code === "string" && code.length > 0,
              ),
            ),
          ].sort()
        : null,
    viewMode: filters.viewMode === "bilingual" ? "bilingual" : "multilingual",
    workStatus:
      typeof filters.workStatus === "string" &&
      WORK_STATUSES.has(filters.workStatus)
        ? filters.workStatus
        : null,
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
    representation: "translation-keys:2",
    viewMode: normalized.viewMode,
    visibleLanguages: normalized.visibleLanguages,
    query,
    productId: normalized.productId,
    language: normalized.language,
    state: normalized.state,
    violation: normalized.violation,
    deleted: normalized.deleted,
    ...(normalized.workStatus ? { workStatus: normalized.workStatus } : {}),
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
    ...(filters.visibleLanguages
      ? { visible_languages: filters.visibleLanguages }
      : {}),
    ...(filters.workStatus ? { work_status: filters.workStatus } : {}),
  };
}

export function translationKeyIdentity(item: TranslationKeySummary): string {
  return `${item.product_id}:${item.scope_id}:${item.translation_key_id}`;
}

function mergeGroups(
  current: readonly TranslationKeySummary[],
  incoming: readonly TranslationKeySummary[],
) {
  const seen = new Set(current.map(translationKeyIdentity));
  return [
    ...current,
    ...incoming.filter((item) => {
      const id = translationKeyIdentity(item);
      if (seen.has(id)) return false;
      seen.add(id);
      return true;
    }),
  ];
}

function validPage(
  page: unknown,
  seenCursors: ReadonlySet<string>,
  filters: TranslationSearchFilters,
  current: readonly TranslationKeySummary[] = [],
  previousLanguages?: readonly string[],
): page is TranslationKeyPageResponse {
  if (
    !isRecord(page) ||
    !Array.isArray(page.items) ||
    page.items.length > TRANSLATION_PAGE_SIZE ||
    !Array.isArray(page.visible_languages) ||
    page.visible_languages.length > 20 ||
    !page.visible_languages.every(
      (code) => typeof code === "string" && code.length > 0,
    ) ||
    new Set(page.visible_languages).size !== page.visible_languages.length ||
    !Array.isArray(page.available_languages) ||
    page.available_languages.length > 500 ||
    !page.available_languages.every(
      (option) =>
        isRecord(option) &&
        typeof option.code === "string" &&
        typeof option.label === "string",
    ) ||
    typeof page.default_selection_capped !== "boolean" ||
    typeof page.available_languages_truncated !== "boolean"
  )
    return false;
  const languages = page.visible_languages as string[];
  const expected = filters.visibleLanguages ?? previousLanguages;
  if (
    expected &&
    (expected.length !== languages.length ||
      !expected.every((code) => languages.includes(code)))
  )
    return false;
  const identities = new Set(current.map(translationKeyIdentity));
  const groups = new Set(
    current.flatMap((key) =>
      key.slots.flatMap((slot) => (slot.group_id ? [slot.group_id] : [])),
    ),
  );
  for (const raw of page.items) {
    if (
      !isRecord(raw) ||
      ![
        raw.product_id,
        raw.scope_id,
        raw.translation_key_id,
        raw.raw_key,
      ].every((value) => typeof value === "string" && value.length > 0) ||
      (filters.productId !== null && raw.product_id !== filters.productId) ||
      !Array.isArray(raw.slots) ||
      raw.slots.length > languages.length
    )
      return false;
    const item = raw as unknown as TranslationKeySummary;
    const identity = translationKeyIdentity(item);
    if (identities.has(identity)) return false;
    identities.add(identity);
    const slots = new Set<string>();
    for (const slot of item.slots) {
      if (
        !slot ||
        !languages.includes(slot.language) ||
        slots.has(slot.language) ||
        !["imported", "source_context", "absent"].includes(slot.kind) ||
        typeof slot.editable !== "boolean" ||
        typeof slot.matches_filters !== "boolean" ||
        (slot.effective_text !== null &&
          typeof slot.effective_text !== "string") ||
        !Array.isArray(slot.states) ||
        !Array.isArray(slot.selector_kinds) ||
        ![
          slot.value_count,
          slot.comment_count,
          slot.over_limit_count,
          slot.within_limit_count,
          slot.no_max_count,
        ].every((n) => Number.isSafeInteger(n) && n >= 0)
      )
        return false;
      slots.add(slot.language);
      if (slot.kind === "imported") {
        if (!slot.group_id || groups.has(slot.group_id)) return false;
        groups.add(slot.group_id);
        if (
          slot.editable &&
          (slot.is_deleted ||
            !["source_text", "translated_text"].includes(slot.edit_field ?? ""))
        )
          return false;
      } else if (slot.group_id !== null || slot.editable) return false;
    }
    // A matching language can be outside the selected slots. Validate only
    // asserted matches; do not infer key membership from visible siblings.
    if (
      item.slots.some(
        (slot) =>
          slot.matches_filters &&
          ((filters.language !== null && slot.language !== filters.language) ||
            (filters.deleted !== "all" &&
              slot.is_deleted !== (filters.deleted === "deleted")) ||
            (filters.state != null && !slot.states.includes(filters.state)) ||
            (filters.violation != null &&
              !(filters.violation === "over_limit"
                ? slot.over_limit_count > 0
                : filters.violation === "within_limit"
                  ? slot.within_limit_count > 0
                  : slot.no_max_count > 0))),
      )
    )
      return false;
  }
  const nextCursor = page.next_cursor;
  return (
    nextCursor === null ||
    (typeof nextCursor === "string" &&
      nextCursor.length > 0 &&
      page.items.length > 0 &&
      !seenCursors.has(nextCursor))
  );
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
  if (identity !== translationSearchIdentity(initialQuery, initialFilters))
    return fallback;
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
  let items: readonly TranslationKeySummary[] = [];
  for (const [index, page] of initialSnapshot.pages.entries()) {
    if (
      !validPage(
        page,
        cursors,
        filters,
        items,
        initialSnapshot.pages[0]?.visible_languages,
      )
    ) {
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

      const pending = searchTranslationKeys({
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
        const result = await searchTranslationKeys({
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
            searchRef.current.pages[0]?.visible_languages,
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

  const refresh = useCallback(() => {
    startInitial(queryRef.current, filtersRef.current, true);
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
        ...page,
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
    visibleLanguages: search.pages[0]?.visible_languages ?? [],
    availableLanguages: search.pages[0]?.available_languages ?? [],
    languageSelectionLimit: search.pages[0]?.language_selection_limit ?? 20,
    defaultSelectionCapped: search.pages[0]?.default_selection_capped ?? false,
    availableLanguagesTruncated:
      search.pages[0]?.available_languages_truncated ?? false,
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
    refresh,
    retryLoadMore,
    createSnapshot,
  };
}
