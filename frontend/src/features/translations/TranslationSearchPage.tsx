import { useCallback, useEffect, useRef, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import {
  listTranslationOptions,
  type TranslationOptionsResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Skeleton } from "../../components/ui/skeleton";
import { TranslationFilters } from "./TranslationFilters";
import { translationFilterLabels } from "./translationFilterLabels";
import { TranslationResultList } from "./TranslationResultList";
import {
  loadTranslationPreferences,
  sanitizeTranslationPreferences,
  saveTranslationPreferences,
} from "./translationPreferences";
import {
  useTranslationSearch,
  type TranslationSearchFilters,
  type TranslationSearchSnapshot,
} from "./useTranslationSearch";
import type { TranslationsWorkspaceContext } from "./TranslationsWorkspace";

const DEFAULT_FILTERS: TranslationSearchFilters = {
  productId: null,
  language: null,
  state: null,
  violation: null,
  deleted: "active",
};
const EMPTY_OPTIONS: TranslationOptionsResponse = {
  products: [],
  languages: [],
};
type Seed = {
  query: string;
  filters: TranslationSearchFilters;
  snapshot?: TranslationSearchSnapshot | null;
  focusControl?: string;
};
type ReadyOptions = { options: TranslationOptionsResponse; seed: Seed };

function LoadingResults() {
  return (
    <div className="space-y-(--space-md)" role="status" aria-live="polite">
      <span>Loading translations</span>
      {Array.from({ length: 5 }, (_, index) => (
        <div
          key={index}
          data-translation-skeleton
          className="grid grid-cols-1 gap-(--space-md) border-b p-(--space-md) md:grid-cols-6"
          aria-hidden="true"
        >
          {Array.from({ length: 6 }, (_, column) => (
            <Skeleton key={column} className="h-12 w-full" />
          ))}
        </div>
      ))}
    </div>
  );
}

function SearchError({
  onRetry,
  alertRef,
}: {
  onRetry: () => void;
  alertRef?: React.Ref<HTMLDivElement>;
}) {
  return (
    <Alert ref={alertRef} tabIndex={-1}>
      <AlertTitle>Translations could not be loaded</AlertTitle>
      <AlertDescription className="space-y-(--space-md)">
        <p>
          Your filters are still available. Retry the search without leaving
          this page.
        </p>
        <Button
          type="button"
          variant="outline"
          className="min-h-[44px] min-w-[44px]"
          onClick={onRetry}
        >
          Retry search
        </Button>
      </AlertDescription>
    </Alert>
  );
}

function ResolvedSearch({
  ready,
  context,
  onRestart,
}: {
  ready: ReadyOptions;
  context: TranslationsWorkspaceContext;
  onRestart: (seed: Seed) => void;
}) {
  const { options, seed } = ready;
  const lockedProduct = context.lockedProduct;
  const search = useTranslationSearch({
    accessToken: context.accessToken,
    initialQuery: seed.query,
    initialFilters: seed.filters,
    initialSnapshot: seed.snapshot,
  });
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const resultRegion = useRef<HTMLElement>(null);
  const alertRef = useRef<HTMLDivElement>(null);
  const explicitAction = useRef(false);
  const previousIdentity = useRef(search.requestIdentity);
  const restorationDone = useRef(false);
  const { setSnapshot } = context;
  const { createSnapshot, query, filters, items, nextCursor, requestIdentity } =
    search;
  useEffect(() => {
    setSnapshot(createSnapshot(window.scrollY, null));
  }, [
    setSnapshot,
    createSnapshot,
    query,
    filters,
    items,
    nextCursor,
    requestIdentity,
  ]);

  useEffect(() => {
    if (lockedProduct) return;
    try {
      saveTranslationPreferences(
        localStorage,
        context.principal.id,
        options,
        search.filters,
      );
    } catch {
      /* Storage can be disabled; search stays usable in memory. */
    }
  }, [context.principal.id, lockedProduct, options, search.filters]);

  useEffect(() => {
    if (
      search.requestIdentity &&
      previousIdentity.current !== search.requestIdentity
    ) {
      previousIdentity.current = search.requestIdentity;
      resultHeading.current?.scrollIntoView({
        behavior: "instant",
        block: "start",
      });
    }
  }, [search.requestIdentity]);

  useEffect(() => {
    let active = true;
    if (search.initialError && explicitAction.current)
      queueMicrotask(() => {
        if (active) alertRef.current?.focus();
      });
    return () => {
      active = false;
    };
  }, [search.initialError]);

  useEffect(() => {
    if (seed.focusControl) {
      if (seed.focusControl === "query") {
        document
          .getElementById("translation-query")
          ?.focus({ preventScroll: true });
        return;
      }
      if (seed.focusControl === "clear") {
        document
          .querySelector<HTMLButtonElement>("[data-clear-translation-filters]")
          ?.focus({ preventScroll: true });
        return;
      }
      const control = Array.from(
        document.querySelectorAll<HTMLElement>('[role="combobox"]'),
      ).find((element) => element.id.endsWith(`-${seed.focusControl}`));
      control?.focus({ preventScroll: true });
    }
  }, [seed.focusControl]);

  useEffect(() => {
    const navigation = search.restoredNavigation;
    if (!navigation || restorationDone.current || search.isInitialLoading)
      return;
    window.scrollTo({ top: navigation.scrollAnchor, behavior: "instant" });
    const restoreFocus = () => {
      if (!navigation.focusedGroupId) {
        restorationDone.current = true;
        return true;
      }
      const link = Array.from(
        resultRegion.current?.querySelectorAll<HTMLAnchorElement>(
          "a[data-translation-group-id]",
        ) ?? [],
      ).find(
        (element) =>
          element.dataset.translationGroupId === navigation.focusedGroupId,
      );
      if (!link) return false;
      link.focus({ preventScroll: true });
      restorationDone.current = true;
      return true;
    };
    if (restoreFocus()) return;
    const observer = new MutationObserver(() => {
      if (restoreFocus()) observer.disconnect();
    });
    if (resultRegion.current)
      observer.observe(resultRegion.current, {
        childList: true,
        subtree: true,
      });
    return () => observer.disconnect();
  }, [search.restoredNavigation, search.isInitialLoading]);

  const clearAll = () => {
    context.setSnapshot(null);
    onRestart({
      query: "",
      filters: {
        ...DEFAULT_FILTERS,
        productId: lockedProduct?.id ?? null,
      },
      focusControl: "clear",
    });
  };
  const changeFilters = (filters: TranslationSearchFilters) => {
    explicitAction.current = true;
    const nextFilters = lockedProduct
      ? { ...filters, productId: lockedProduct.id }
      : filters;
    if (nextFilters.productId !== search.filters.productId) {
      onRestart({
        query: search.query,
        filters: nextFilters,
        focusControl: "productId",
      });
    } else search.setFilters(nextFilters);
  };
  const filtered =
    search.query !== "" ||
    (!lockedProduct && search.filters.productId !== null) ||
    search.filters.language !== null ||
    search.filters.state != null ||
    search.filters.violation != null ||
    search.filters.deleted !== "active";
  const criteria = [
    search.query && `Search: ${search.query}`,
    !lockedProduct &&
      search.filters.productId &&
      `Product: ${options.products.find((item) => item.id === search.filters.productId)?.name}`,
    search.filters.language && `Language: ${search.filters.language}`,
    search.filters.state &&
      `Approval state: ${translationFilterLabels.state[search.filters.state]}`,
    search.filters.violation &&
      `Length status: ${translationFilterLabels.violation[search.filters.violation]}`,
    search.filters.deleted !== "active" &&
      `Deleted status: ${translationFilterLabels.deleted[search.filters.deleted]}`,
  ]
    .filter(Boolean)
    .join("; ");

  return (
    <>
      <div className="space-y-(--space-sm) rounded-lg bg-secondary p-(--space-md)">
        <Label htmlFor="translation-query">Search keys and translations</Label>
        <Input
          id="translation-query"
          className="min-h-[44px]"
          placeholder="Enter a key or text"
          aria-describedby="translation-query-help"
          value={search.query}
          onChange={(event) => {
            explicitAction.current = true;
            if (event.target.value === "") search.clearQuery();
            else search.setQuery(event.target.value);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              explicitAction.current = true;
              search.submitQuery();
            }
          }}
        />
        <p
          id="translation-query-help"
          className="text-body text-muted-foreground"
        >
          Searches original keys, source text, and translated text.
        </p>
        <Button
          type="button"
          variant="outline"
          className="min-h-[44px]"
          onClick={() => {
            explicitAction.current = true;
            search.clearQuery();
          }}
        >
          Clear search
        </Button>
      </div>
      <TranslationFilters
        filters={search.filters}
        options={options}
        hideProduct={Boolean(lockedProduct)}
        onChange={changeFilters}
        onClear={clearAll}
      />
      <section
        ref={resultRegion}
        className="min-w-0 space-y-(--space-md)"
        aria-labelledby="translation-results-heading"
      >
        <h2
          ref={resultHeading}
          id="translation-results-heading"
          className="text-heading font-semibold"
        >
          Translation results
        </h2>
        {search.isInitialLoading ? (
          <LoadingResults />
        ) : search.initialError ? (
          <SearchError
            alertRef={alertRef}
            onRetry={() => {
              explicitAction.current = true;
              void search.retryInitial();
            }}
          />
        ) : search.items.length === 0 ? (
          <div role="status" className="space-y-(--space-sm)">
            <h3 className="text-heading font-semibold">
              {filtered
                ? "No translations match these filters"
                : "No translations available"}
            </h3>
            <p>
              {filtered
                ? "Change your search or clear the filters to see more translations."
                : "Complete an import for an active product, or choose another authorized product."}
            </p>
            {filtered && (
              <p className="wrap-anywhere">Active criteria: {criteria}</p>
            )}
          </div>
        ) : (
          <TranslationResultList
            items={search.items}
            nextCursor={search.nextCursor}
            requestIdentity={search.requestIdentity}
            loadingMore={search.loadingMore}
            loadMoreError={search.loadMoreError}
            onLoadMore={search.loadMore}
            onRetryLoadMore={search.retryLoadMore}
            initialOffset={search.restoredNavigation?.scrollAnchor}
            initialMeasurements={
              search.restoredNavigation &&
              !seed.snapshot?.invalidated &&
              seed.snapshot?.viewportWidth === window.innerWidth
                ? seed.snapshot.measurements
                : undefined
            }
            onOpenDetails={(id, measurements) =>
              context.setSnapshot({
                ...search.createSnapshot(window.scrollY, id),
                measurements,
                viewportWidth: window.innerWidth,
              })
            }
            detailsBasePath={context.detailsBasePath}
          />
        )}
      </section>
    </>
  );
}

function SearchOptions({
  context,
  requestedProductId,
}: {
  context: TranslationsWorkspaceContext;
  requestedProductId: string | null;
}) {
  const [pendingQuery, setPendingQuery] = useState(
    context.snapshot?.query ?? "",
  );
  const queryRef = useRef(pendingQuery);
  const retryAction = useRef(false);
  const optionsAlert = useRef<HTMLDivElement>(null);
  const [seed, setSeed] = useState<Seed | null>(() => {
    if (requestedProductId !== null) {
      return {
        query: "",
        filters: { ...DEFAULT_FILTERS, productId: requestedProductId },
        snapshot: null,
      };
    }
    return context.snapshot
      ? {
          query: context.snapshot.query,
          filters: context.snapshot.filters,
          snapshot: context.snapshot,
        }
      : null;
  });
  const [request, setRequest] = useState(0);
  const [load, setLoad] = useState<{
    request: number;
    ready?: ReadyOptions;
    failed?: boolean;
  }>({ request: 0 });
  const ready = load.request === request ? load.ready : undefined;
  const failed = load.request === request && load.failed;
  useEffect(() => {
    if (!failed || !retryAction.current) return;
    let active = true;
    queueMicrotask(() => {
      if (active) optionsAlert.current?.focus();
    });
    return () => {
      active = false;
    };
  }, [failed]);
  const principalId = context.principal.id;
  const accessToken = context.accessToken;
  const lockedProduct = context.lockedProduct;
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const global = await listTranslationOptions({
          auth: accessToken,
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (!global.data) throw new Error("Options unavailable");
        let choices = global.data;
        let preferences;
        if (seed)
          preferences = sanitizeTranslationPreferences(seed.filters, choices);
        else {
          try {
            preferences = loadTranslationPreferences(
              localStorage,
              principalId,
              choices,
            );
          } catch {
            preferences = { productId: null, language: null };
          }
        }
        if (lockedProduct) {
          const authorized = choices.products.some(
            (product) => product.id === lockedProduct.id,
          );
          if (!authorized) throw new Error("Product unavailable");
          preferences = { ...preferences, productId: lockedProduct.id };
        }
        if (preferences.productId !== null) {
          const scoped = await listTranslationOptions({
            auth: accessToken,
            query: { product_id: preferences.productId },
            signal: controller.signal,
          });
          if (controller.signal.aborted) return;
          if (!scoped.data) throw new Error("Options unavailable");
          choices = scoped.data;
          preferences = sanitizeTranslationPreferences(preferences, choices);
        }
        const filters = {
          ...DEFAULT_FILTERS,
          ...seed?.filters,
          ...preferences,
        };
        const snapshot = seed?.snapshot;
        const validSnapshot =
          snapshot &&
          snapshot.query === queryRef.current &&
          snapshot.filters.productId === filters.productId &&
          snapshot.filters.language === filters.language;
        setLoad({
          request,
          ready: {
            options: choices,
            seed: {
              query: queryRef.current,
              filters,
              snapshot: validSnapshot ? snapshot : null,
              focusControl: retryAction.current ? "query" : seed?.focusControl,
            },
          },
        });
      } catch {
        if (!controller.signal.aborted) setLoad({ request, failed: true });
      }
    })();
    return () => controller.abort();
  }, [accessToken, lockedProduct, principalId, request, seed]);
  const restart = useCallback((next: Seed) => {
    retryAction.current = false;
    queryRef.current = next.query;
    setPendingQuery(next.query);
    setSeed(next);
    setRequest((value) => value + 1);
  }, []);
  return (
    <div className="grid min-w-0 gap-(--space-xl)">
      <header className="space-y-(--space-sm)">
        {lockedProduct ? (
          <h2 className="text-display font-semibold">Strings</h2>
        ) : (
          <h1 className="text-display font-semibold">Translations</h1>
        )}
        <p className="text-muted-foreground">
          {lockedProduct
            ? `Searching only in ${lockedProduct.name}`
            : "Find imported localization keys, text, review state, and length constraints across your authorized products."}
        </p>
      </header>
      {ready ? (
        <ResolvedSearch
          key={request}
          ready={ready}
          context={context}
          onRestart={restart}
        />
      ) : (
        <>
          <div
            className="space-y-(--space-sm) rounded-lg bg-secondary p-(--space-md)"
            aria-busy={!failed}
          >
            <Label htmlFor="translation-query">
              Search keys and translations
            </Label>
            <Input
              id="translation-query"
              className="min-h-[44px]"
              placeholder="Enter a key or text"
              aria-describedby="translation-query-help"
              value={pendingQuery}
              onChange={(event) => {
                queryRef.current = event.target.value;
                setPendingQuery(event.target.value);
              }}
            />
            <p
              id="translation-query-help"
              className="text-body text-muted-foreground"
            >
              Searches original keys, source text, and translated text.
            </p>
          </div>
          <TranslationFilters
            filters={
              seed?.filters ?? {
                ...DEFAULT_FILTERS,
                productId: lockedProduct?.id ?? null,
              }
            }
            options={load.ready?.options ?? EMPTY_OPTIONS}
            disabled
            hideProduct={Boolean(lockedProduct)}
            onChange={() => {}}
            onClear={() =>
              restart({
                query: "",
                filters: {
                  ...DEFAULT_FILTERS,
                  productId: lockedProduct?.id ?? null,
                },
              })
            }
          />
          {failed ? (
            <SearchError
              alertRef={optionsAlert}
              onRetry={() => {
                retryAction.current = true;
                setRequest((value) => value + 1);
              }}
            />
          ) : (
            <LoadingResults />
          )}
        </>
      )}
    </div>
  );
}

export function TranslationSearchPage() {
  const context = useOutletContext<TranslationsWorkspaceContext>();
  const [searchParams] = useSearchParams();
  const requestedProductId =
    context.lockedProduct?.id ??
    (searchParams.get("product_id")?.trim() || null) ??
    null;
  return (
    <SearchOptions
      key={`${context.accessToken}:${requestedProductId ?? ""}`}
      context={context}
      requestedProductId={requestedProductId}
    />
  );
}
