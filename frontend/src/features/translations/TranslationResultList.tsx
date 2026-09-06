import { useCallback, useEffect, useRef, useState } from "react";
import { useWindowVirtualizer } from "@tanstack/react-virtual";
import { Link } from "react-router-dom";

import type { TranslationGroupSummaryResponse } from "../../api/client";
import { Alert, AlertTitle } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";

interface TranslationResultListProps {
  items: readonly TranslationGroupSummaryResponse[];
  nextCursor: string | null;
  requestIdentity: string;
  loadingMore: boolean;
  loadMoreError: boolean;
  onLoadMore: () => Promise<void>;
  onRetryLoadMore: () => Promise<void>;
  onOpenDetails?: (translationGroupId: string) => void;
}

const STATE_LABELS = {
  draft: "Draft",
  approved: "Approved",
  rejected: "Rejected",
  mixed: "Mixed states",
} as const;
const SELECTOR_LABELS = {
  scalar: null,
  android_quantity: "Plural",
  android_array_item: "Array",
  qt_numerus: "Qt variant",
  qt_length_variant: "Qt variant",
  json_path: "JSON path",
} as const;

function rowPresentation(item: TranslationGroupSummaryResponse) {
  return {
    selectorLabels: [
      ...new Set(
        item.selector_kinds.flatMap((kind) =>
          SELECTOR_LABELS[kind] === null ? [] : [SELECTOR_LABELS[kind]],
        ),
      ),
    ],
    languageLabel:
      item.language_label && item.language_label !== item.language
        ? `${item.language_label} (${item.language})`
        : item.language,
    detailsLabel: `Open details for ${item.raw_key} (${item.language})`,
  };
}

export function TranslationResultList({
  items,
  nextCursor,
  requestIdentity,
  loadingMore,
  loadMoreError,
  onLoadMore,
  onRetryLoadMore,
  onOpenDetails,
}: TranslationResultListProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const alertRef = useRef<HTMLDivElement>(null);
  const userRequestedIdentity = useRef<string | null>(null);
  const [scrollMargin, setScrollMargin] = useState(0);
  const attempted = useRef<{ identity: string; cursor: string } | null>(null);
  const pending = useRef<{ identity: string } | null>(null);
  const [callbackErrorIdentity, setCallbackErrorIdentity] = useState<
    string | null
  >(null);
  const error = loadMoreError || callbackErrorIdentity === requestIdentity;
  const count = items.length;
  const loadedCopy = `${count} translation ${count === 1 ? "group" : "groups"} loaded`;
  const [announcement, setAnnouncement] = useState({
    identity: requestIdentity,
    count,
    text: loadedCopy,
  });
  if (
    announcement.identity !== requestIdentity ||
    announcement.count !== count
  ) {
    const added = count - announcement.count;
    setAnnouncement({
      identity: requestIdentity,
      count,
      text:
        announcement.identity === requestIdentity && added > 0
          ? `Loaded ${added} more translation ${added === 1 ? "group" : "groups"}`
          : loadedCopy,
    });
  }

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    let active = true;
    const updateMargin = () => {
      if (active)
        setScrollMargin(list.getBoundingClientRect().top + window.scrollY);
    };
    const observer = new ResizeObserver(updateMargin);
    observer.observe(list);
    if (list.parentElement) observer.observe(list.parentElement);
    observer.observe(document.body);
    window.addEventListener("resize", updateMargin);
    queueMicrotask(updateMargin);
    return () => {
      active = false;
      observer.disconnect();
      window.removeEventListener("resize", updateMargin);
    };
  }, []);

  const getItemKey = useCallback((index: number) => items[index].id, [items]);
  const virtualizer = useWindowVirtualizer<HTMLElement>({
    count,
    estimateSize: () => 288,
    overscan: 8,
    useFlushSync: false,
    getItemKey,
    scrollMargin,
  });
  const virtualRows = virtualizer.getVirtualItems();
  const lastRenderedIndex = virtualRows.at(-1)?.index;

  const requestMore = useCallback(
    async (retry = false) => {
      if (
        !nextCursor ||
        loadingMore ||
        pending.current?.identity === requestIdentity ||
        (!retry && error)
      )
        return;
      if (
        !retry &&
        attempted.current?.identity === requestIdentity &&
        attempted.current.cursor === nextCursor
      )
        return;
      attempted.current = { identity: requestIdentity, cursor: nextCursor };
      const request = { identity: requestIdentity };
      pending.current = request;
      setCallbackErrorIdentity(null);
      try {
        await (retry ? onRetryLoadMore() : onLoadMore());
      } catch {
        if (pending.current === request)
          setCallbackErrorIdentity(requestIdentity);
      } finally {
        if (pending.current === request) pending.current = null;
      }
    },
    [
      nextCursor,
      loadingMore,
      error,
      requestIdentity,
      onLoadMore,
      onRetryLoadMore,
    ],
  );

  useEffect(() => {
    let active = true;
    if (
      count > 0 &&
      lastRenderedIndex !== undefined &&
      lastRenderedIndex >= count - 1
    ) {
      queueMicrotask(() => {
        if (active) void requestMore();
      });
    }
    return () => {
      active = false;
    };
  }, [count, lastRenderedIndex, requestMore]);

  useEffect(() => {
    let active = true;
    if (error && userRequestedIdentity.current === requestIdentity) {
      queueMicrotask(() => {
        if (active) alertRef.current?.focus();
      });
    }
    return () => {
      active = false;
    };
  }, [error, requestIdentity]);

  return (
    <div className="min-w-0 space-y-(--space-md)">
      <p className="text-label font-semibold">{loadedCopy}</p>
      <p role="status" aria-live="polite" className="sr-only">
        {announcement.text}
      </p>
      <div
        ref={listRef}
        role="list"
        aria-label="Translation results"
        className="relative min-w-0 border-t bg-secondary"
        style={{ height: virtualizer.getTotalSize() }}
      >
        {virtualRows.map((virtualRow) => {
          const item = items[virtualRow.index];
          const { selectorLabels, languageLabel, detailsLabel } =
            rowPresentation(item);
          return (
            <article
              key={virtualRow.key}
              ref={virtualizer.measureElement}
              data-index={virtualRow.index}
              data-translation-group-id={item.id}
              role="listitem"
              aria-posinset={virtualRow.index + 1}
              aria-setsize={nextCursor === null ? count : -1}
              className="absolute top-0 left-0 grid w-full min-w-0 grid-cols-1 gap-(--space-md) border-b p-(--space-md) text-body md:grid-cols-[minmax(0,1fr)_minmax(0,0.5fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.8fr)_minmax(0,0.6fr)]"
              style={{
                transform: `translateY(${virtualRow.start - scrollMargin}px)`,
              }}
            >
              <div data-part="key" className="min-w-0 space-y-(--space-sm)">
                <code
                  className="block font-mono text-body font-regular whitespace-pre-wrap wrap-anywhere"
                  dir="auto"
                >
                  {item.raw_key}
                </code>
                {selectorLabels.length > 0 && (
                  <div className="flex flex-wrap items-center gap-(--space-xs)">
                    <span className="text-label font-semibold">
                      {item.value_count}{" "}
                      {item.value_count === 1 ? "value" : "values"}
                    </span>
                    {selectorLabels.map((label) => (
                      <Badge
                        key={label}
                        variant="secondary"
                        className="text-label font-semibold"
                      >
                        {label}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
              <div data-part="language" className="min-w-0">
                <Badge
                  variant="outline"
                  className="max-w-full text-label font-semibold whitespace-normal wrap-anywhere"
                >
                  {languageLabel}
                </Badge>
              </div>
              <div data-part="source" className="min-w-0">
                <p
                  aria-label="Source text"
                  lang={item.source_language ?? undefined}
                  dir="auto"
                  className="line-clamp-2 text-body whitespace-pre-wrap wrap-anywhere"
                >
                  {item.source_text ?? "No source text available"}
                </p>
              </div>
              <div data-part="translation" className="min-w-0">
                <p
                  aria-label="Translated text"
                  lang={item.language}
                  dir="auto"
                  className="line-clamp-2 text-body whitespace-pre-wrap wrap-anywhere"
                >
                  {item.translated_text || "Empty translation"}
                </p>
              </div>
              <div data-part="status" className="min-w-0 space-y-(--space-sm)">
                <Badge
                  variant="secondary"
                  className="text-label font-semibold whitespace-normal"
                >
                  {STATE_LABELS[item.state_summary]}
                </Badge>
                {item.over_limit_count > 0 ? (
                  <p className="text-label font-semibold text-warning">
                    {item.over_limit_count} of {item.value_count} over limit
                  </p>
                ) : item.no_max_count === item.value_count ? (
                  <p className="text-label font-semibold">No max length</p>
                ) : item.within_limit_count === item.value_count ? (
                  <p className="text-label font-semibold">Within limit</p>
                ) : (
                  <div className="text-label font-semibold">
                    <p>
                      {item.within_limit_count} of {item.value_count} within
                      limit
                    </p>
                    <p>
                      {item.no_max_count} of {item.value_count} with no max
                      length
                    </p>
                  </div>
                )}
                {item.is_deleted && (
                  <>
                    <Badge
                      variant="outline"
                      className="text-label font-semibold whitespace-normal"
                    >
                      Deleted in source
                    </Badge>
                    {item.provenance && (
                      <div
                        aria-label="Last-known source"
                        className="space-y-(--space-xs) text-label wrap-anywhere"
                      >
                        <p>{item.provenance.repository_name}</p>
                        <p className="font-mono">{item.provenance.branch}</p>
                        <p className="font-mono">{item.provenance.path}</p>
                      </div>
                    )}
                  </>
                )}
              </div>
              <div data-part="details" className="min-w-0">
                <Button
                  asChild
                  variant="link"
                  className="h-auto min-h-[44px] min-w-[44px] max-w-full px-0 text-body whitespace-normal"
                >
                  <Link
                    to={`/translations/${encodeURIComponent(item.id)}`}
                    aria-label={detailsLabel}
                    data-translation-group-id={item.id}
                    onClick={() => onOpenDetails?.(item.id)}
                  >
                    Open details
                  </Link>
                </Button>
              </div>
            </article>
          );
        })}
      </div>
      {error && (
        <Alert ref={alertRef} tabIndex={-1}>
          <AlertTitle>More translations could not be loaded</AlertTitle>
        </Alert>
      )}
      {nextCursor !== null && (
        <Button
          variant="outline"
          className="h-auto min-h-[44px] min-w-[44px] text-body whitespace-normal"
          disabled={loadingMore}
          aria-busy={loadingMore}
          onClick={() => {
            userRequestedIdentity.current = requestIdentity;
            void requestMore(error);
          }}
        >
          {error ? "Retry loading more" : "Load more translations"}
        </Button>
      )}
    </div>
  );
}
