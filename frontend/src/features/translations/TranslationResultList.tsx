import { useCallback, useEffect, useRef, useState } from "react";
import {
  useWindowVirtualizer,
  defaultRangeExtractor,
  type Range,
  type VirtualItem,
} from "@tanstack/react-virtual";
import { Link } from "react-router-dom";
import {
  MessageSquare,
  History,
  CheckCircle2,
  Info,
  ExternalLink,
  Pencil,
  TriangleAlert,
  PackageOpen,
  Clock3,
} from "lucide-react";

import type {
  TranslationKeySummary,
  TranslationLanguageSlot,
} from "../../api/client";
import { translationKeyIdentity } from "./useTranslationSearch";
import { productIdentity } from "../products/productIdentity";
import {
  Tooltip,
  TooltipProvider,
  TooltipContent,
  TooltipTrigger,
} from "../../components/ui/tooltip";
import { Alert, AlertTitle } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";

export type TranslationContextSection =
  "comments" | "history" | "source" | "review";
export interface TranslationContextSelection {
  groupId: string | null;
  language: string;
  section: TranslationContextSection;
  trigger: HTMLElement;
  item: TranslationKeySummary;
  slot: TranslationLanguageSlot;
}

export interface TranslationResultListProps {
  items: readonly TranslationKeySummary[];
  viewMode?: "multilingual" | "bilingual";
  focusLanguage?: string | null;
  showProductIdentity?: boolean;
  onOpenContext?: (selection: TranslationContextSelection) => void;
  onRefresh?: () => void;
  nextCursor: string | null;
  requestIdentity: string;
  loadingMore: boolean;
  loadMoreError: boolean;
  onLoadMore: () => Promise<void>;
  onRetryLoadMore: () => Promise<void>;
  initialMeasurements?: VirtualItem[];
  initialOffset?: number;
  detailsBasePath?: string;
  onOpenDetails?: (
    translationGroupId: string,
    measurements: VirtualItem[],
  ) => void;
  canEdit?: boolean;
  onEditTranslation?: (
    translationGroupId: string,
    trigger: HTMLElement,
  ) => void;
  onAddTranslation?: (
    item: TranslationKeySummary,
    language: string,
    trigger: HTMLElement,
  ) => void;
  activeEditorGroupId?: string | null;
  editor?: React.ReactNode;
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

const READ_ONLY_REASONS = {
  absent: "Not imported for this language",
  source_context:
    "Embedded source text is read-only; edit it in the repository.",
  deleted: "Deleted in source",
  keys_repository: "Keys-repository values are read-only in this workspace.",
  unsupported_format: "This source format cannot be edited here.",
  unsupported_shape: "This structured value cannot be edited here.",
  unavailable_provenance:
    "Source provenance is unavailable; refresh the import before editing.",
  mixed_edit_fields:
    "Members have conflicting source provenance and cannot be edited together.",
} as const;

export function TranslationResultList({
  items,
  nextCursor,
  requestIdentity,
  loadingMore,
  loadMoreError,
  onLoadMore,
  onRetryLoadMore,
  onOpenDetails,
  initialMeasurements,
  initialOffset,
  detailsBasePath = "/translations",
  canEdit = false,
  onEditTranslation,
  onAddTranslation,
  activeEditorGroupId,
  editor,
  viewMode = "multilingual",
  focusLanguage,
  showProductIdentity = false,
  onOpenContext,
  onRefresh,
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
  const loadedCopy = `${count} ${count === 1 ? "key" : "keys"} loaded`;
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
          ? `Loaded ${added} more ${added === 1 ? "key" : "keys"}`
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

  const getItemKey = useCallback(
    (index: number) => translationKeyIdentity(items[index]),
    [items],
  );
  const activeIndex = items.findIndex((item) =>
    item.slots.some((slot) => slot.group_id === activeEditorGroupId),
  );
  const rangeExtractor = useCallback(
    (range: Range) => {
      const visible = defaultRangeExtractor(range);
      return activeIndex < 0
        ? visible
        : [...new Set([...visible, activeIndex])].sort((a, b) => a - b);
    },
    [activeIndex],
  );
  const virtualizer = useWindowVirtualizer<HTMLElement>({
    count,
    estimateSize: (index) => 56 + items[index].slots.length * 76,
    overscan: 8,
    useFlushSync: false,
    getItemKey,
    rangeExtractor,
    scrollMargin,
    initialMeasurementsCache: initialMeasurements,
    initialOffset,
  });
  const measurementIdentity = JSON.stringify([
    requestIdentity,
    viewMode,
    focusLanguage,
  ]);
  const measuredIdentity = useRef(measurementIdentity);
  useEffect(() => {
    const measure = () => virtualizer.measure();
    if (measuredIdentity.current !== measurementIdentity) {
      measure();
      measuredIdentity.current = measurementIdentity;
    }
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [virtualizer, measurementIdentity]);
  const virtualRows = virtualizer.getVirtualItems();
  const lastRenderedIndex = virtualRows.at(-1)?.index;
  const scrolledGroup = useRef<string | null>(null);
  useEffect(() => {
    if (!activeEditorGroupId) {
      scrolledGroup.current = null;
      return;
    }
    if (
      scrollMargin === 0 ||
      activeIndex < 0 ||
      scrolledGroup.current === activeEditorGroupId
    )
      return;
    scrolledGroup.current = activeEditorGroupId;
    virtualizer.scrollToIndex(activeIndex, { align: "start" });
  }, [activeEditorGroupId, activeIndex, virtualizer, scrollMargin]);

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
    <TooltipProvider>
      <div className="min-w-0 space-y-(--space-md)">
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
            const identity = showProductIdentity
              ? productIdentity(item.product_id, item.product_name)
              : null;
            const slots =
              viewMode === "bilingual" && focusLanguage
                ? item.slots.filter(
                    (slot) =>
                      slot.language === item.base_language ||
                      slot.language === focusLanguage,
                  )
                : item.slots;
            return (
              <article
                key={virtualRow.key}
                ref={virtualizer.measureElement}
                data-index={virtualRow.index}
                data-translation-key-id={translationKeyIdentity(item)}
                data-translation-group-id={item.translation_key_id}
                role="listitem"
                aria-posinset={virtualRow.index + 1}
                aria-setsize={nextCursor === null ? count : -1}
                className="absolute top-0 left-0 grid w-full min-w-0 grid-cols-1 border-b-2 border-slate-200 bg-card text-body md:grid-cols-[minmax(12rem,16rem)_minmax(0,1fr)]"
                style={{
                  transform: `translateY(${virtualRow.start - scrollMargin}px)`,
                }}
              >
                <div
                  data-part="key"
                  className="min-w-0 border-b bg-slate-50 p-3 md:border-r md:border-b-0"
                >
                  <div
                    className={`space-y-3 ${showProductIdentity ? "md:sticky md:top-3" : ""}`}
                  >
                    {identity && (
                      <div
                        className="flex items-start gap-2 rounded-r-md border-l-4 px-2.5 py-2 text-sm font-semibold wrap-anywhere"
                        style={{
                          borderColor: identity.accent,
                          backgroundColor: identity.soft,
                          color: identity.ink,
                        }}
                      >
                        <PackageOpen
                          aria-hidden="true"
                          className="mt-0.5 size-4 shrink-0"
                        />
                        <span className="min-w-0" dir="auto">
                          <span className="sr-only">Product: </span>
                          {item.product_name}
                        </span>
                      </div>
                    )}
                    <code
                      title={item.raw_key}
                      dir="auto"
                      className="block font-mono text-body whitespace-pre-wrap wrap-anywhere"
                    >
                      {item.raw_key}
                      {item.key_truncated ? "…" : ""}
                    </code>
                    {!showProductIdentity && (
                      <p className="text-label text-muted-foreground wrap-anywhere">
                        {item.product_name}
                      </p>
                    )}
                  </div>
                </div>
                <div className="min-w-0 divide-y">
                  {slots.map((slot) => {
                    const active =
                      !!slot.group_id && slot.group_id === activeEditorGroupId;
                    const label = `${item.raw_key} (${slot.language})`;
                    const overLimitCount =
                      slot.effective_over_limit_count ?? slot.over_limit_count;
                    const overLimit = overLimitCount > 0;
                    const hasPendingChange = !!slot.pending_change;
                    const limitId = `length-${item.scope_id}-${item.translation_key_id}-${slot.language}`;
                    const reason = slot.read_only_reason
                      ? READ_ONLY_REASONS[slot.read_only_reason]
                      : null;
                    const state =
                      slot.pending_change?.state ??
                      (slot.states.length > 1 ? "mixed" : slot.states[0]);
                    const editable =
                      canEdit &&
                      slot.kind === "imported" &&
                      slot.editable &&
                      !slot.is_deleted &&
                      onEditTranslation;
                    const text =
                      slot.kind === "absent"
                        ? "Not imported for this language"
                        : slot.effective_text ||
                          (slot.language === item.base_language
                            ? "Empty source text"
                            : "Empty translation");
                    const actions = slot.group_id
                      ? [
                          {
                            section: "comments" as const,
                            label: `Comments for ${label}, ${slot.comment_count.toLocaleString()} comments`,
                            Icon: MessageSquare,
                          },
                          {
                            section: "history" as const,
                            label: `History for ${label}`,
                            Icon: History,
                          },
                          {
                            section: "review" as const,
                            label: `Review for ${label}: ${state ? STATE_LABELS[state] : "No saved proposal"}`,
                            Icon: CheckCircle2,
                          },
                          {
                            section: "source" as const,
                            label: `Source and length details for ${label}`,
                            Icon: Info,
                          },
                        ]
                      : slot.kind === "source_context"
                        ? [
                            {
                              section: "source" as const,
                              label: `Source details for ${label}`,
                              Icon: Info,
                            },
                          ]
                        : [];
                    const selectors = [
                      ...new Set(
                        slot.selector_kinds.flatMap((kind) =>
                          SELECTOR_LABELS[kind] ? [SELECTOR_LABELS[kind]] : [],
                        ),
                      ),
                    ];
                    return (
                      <div
                        key={slot.language}
                        data-language={slot.language}
                        data-group-id={slot.group_id ?? undefined}
                        className={`grid min-w-0 grid-cols-[minmax(5.5rem,7rem)_minmax(0,1fr)] xl:grid-cols-[minmax(6rem,8rem)_minmax(0,1fr)_auto] ${active ? "bg-blue-50/50 ring-2 ring-inset ring-blue-600" : ""}`}
                      >
                        <div
                          className={`min-w-0 p-3 text-label wrap-anywhere ${hasPendingChange ? "border-l-4 border-amber-400 bg-amber-50 dark:border-amber-500 dark:bg-amber-950/30" : "bg-slate-100"}`}
                        >
                          <span className="font-semibold">
                            {slot.language_label}
                          </span>
                          {slot.language_label !== slot.language && (
                            <span className="block text-muted-foreground">
                              {slot.language}
                            </span>
                          )}
                          {canEdit &&
                            onAddTranslation &&
                            slot.kind === "imported" &&
                            slot.selector_kinds.some(
                              (kind) =>
                                kind === "android_quantity" ||
                                kind === "qt_numerus",
                            ) && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="mt-2 px-0 text-blue-700"
                                onClick={(event) =>
                                  onAddTranslation(
                                    item,
                                    slot.language,
                                    event.currentTarget,
                                  )
                                }
                              >
                                Add forms
                              </Button>
                            )}
                          {slot.language === item.base_language && (
                            <span className="block text-muted-foreground">
                              Source
                            </span>
                          )}
                        </div>
                        <div className="min-w-0 p-2">
                          {active && editor ? (
                            <div data-part="editor" className="min-w-0 p-1">
                              {editor}
                            </div>
                          ) : slot.kind === "absent" &&
                            canEdit &&
                            onAddTranslation ? (
                            <Button
                              variant="outline"
                              className="w-full justify-start border-dashed border-blue-300 text-blue-700"
                              onClick={(event) =>
                                onAddTranslation(
                                  item,
                                  slot.language,
                                  event.currentTarget,
                                )
                              }
                            >
                              Add translation
                            </Button>
                          ) : editable ? (
                            <button
                              type="button"
                              data-translation-editor-trigger={slot.group_id}
                              aria-label={`Edit translation for ${label}`}
                              aria-expanded={false}
                              aria-describedby={overLimit ? limitId : undefined}
                              className={`group flex min-h-[44px] w-full min-w-0 cursor-text items-start gap-3 rounded-md border px-3 py-2 text-left transition-colors focus-visible:outline-2 ${overLimit ? "border-destructive bg-red-50 hover:bg-red-100 focus-visible:border-destructive focus-visible:outline-destructive dark:bg-red-950/30" : hasPendingChange ? "border-amber-400 bg-amber-50 hover:border-amber-600 hover:bg-amber-100 focus-visible:border-amber-700 focus-visible:outline-amber-700 dark:bg-amber-950/30 dark:hover:bg-amber-950/50" : "border-blue-200 bg-blue-50/60 hover:border-blue-500 hover:bg-blue-100/70 focus-visible:border-blue-600 focus-visible:outline-blue-600"}`}
                              onClick={(event) =>
                                onEditTranslation!(
                                  slot.group_id!,
                                  event.currentTarget,
                                )
                              }
                            >
                              <span
                                lang={slot.language}
                                dir="auto"
                                className={`block min-w-0 flex-1 line-clamp-3 whitespace-pre-wrap wrap-anywhere ${!slot.effective_text ? "font-medium text-blue-700" : "text-foreground"}`}
                              >
                                {text}
                                {slot.text_truncated ? "…" : ""}
                              </span>
                              <span
                                aria-hidden="true"
                                className="flex shrink-0 items-center gap-1 pt-0.5 text-label font-semibold text-blue-700"
                              >
                                <Pencil className="size-3.5" />
                                <span className="hidden sm:inline">Edit</span>
                              </span>
                            </button>
                          ) : (
                            <p
                              lang={slot.language}
                              dir="auto"
                              aria-describedby={overLimit ? limitId : undefined}
                              className={`min-h-[44px] rounded-md px-3 py-2 whitespace-pre-wrap wrap-anywhere ${overLimit ? "border border-destructive bg-red-50 text-foreground dark:bg-red-950/30" : hasPendingChange ? "border border-amber-400 bg-amber-50 text-foreground dark:bg-amber-950/30" : "bg-slate-50 text-muted-foreground"}`}
                            >
                              {text}
                              {slot.text_truncated ? "…" : ""}
                            </p>
                          )}
                          <div className="flex min-w-0 flex-wrap gap-x-3 gap-y-1 px-1 text-label text-muted-foreground">
                            {reason && slot.kind !== "absent" && (
                              <span>{reason}</span>
                            )}
                            {slot.pending_change && (
                              <span className="my-1 inline-flex items-center gap-1 rounded-md border border-amber-300 bg-amber-100 px-1.5 py-0.5 font-semibold text-amber-950 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-200">
                                <Clock3
                                  aria-hidden="true"
                                  className="size-3.5 shrink-0"
                                />
                                Pending{" "}
                                {STATE_LABELS[slot.pending_change.state]}
                              </span>
                            )}
                            {slot.pending_change?.reconciliation_required && (
                              <span>Needs reconciliation</span>
                            )}
                            {overLimit && !active && (
                              <span
                                id={limitId}
                                className="flex items-center gap-1 font-semibold text-destructive"
                              >
                                <TriangleAlert
                                  aria-hidden="true"
                                  className="size-4 shrink-0"
                                />
                                {overLimitCount} of {slot.value_count} over
                                limit
                              </span>
                            )}
                            {slot.source_changed && <span>Source changed</span>}
                            {selectors.length > 0 && (
                              <span>
                                {slot.value_count} values ·{" "}
                                {selectors.join(", ")}
                              </span>
                            )}
                            {!slot.matches_filters &&
                              slot.kind !== "absent" && (
                                <span>Context language</span>
                              )}
                          </div>
                        </div>
                        <div className="col-span-2 flex min-w-0 flex-wrap items-start justify-end px-1 xl:col-span-1">
                          {onOpenContext &&
                            actions.map(
                              ({ section, label: actionLabel, Icon }) => (
                                <Tooltip key={section}>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      type="button"
                                      className="min-h-[44px] min-w-[44px]"
                                      aria-label={actionLabel}
                                      onClick={(event) =>
                                        onOpenContext({
                                          groupId: slot.group_id,
                                          language: slot.language,
                                          section,
                                          trigger: event.currentTarget,
                                          item,
                                          slot,
                                        })
                                      }
                                    >
                                      <Icon
                                        aria-hidden="true"
                                        className="size-4"
                                      />
                                      {section === "comments" &&
                                        slot.comment_count > 0 && (
                                          <span className="text-xs">
                                            {slot.comment_count}
                                          </span>
                                        )}
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>{actionLabel}</TooltipContent>
                                </Tooltip>
                              ),
                            )}
                          {slot.group_id && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  asChild
                                  variant="ghost"
                                  size="icon"
                                  className="min-h-[44px] min-w-[44px]"
                                >
                                  <Link
                                    to={`${detailsBasePath}/${encodeURIComponent(slot.group_id)}`}
                                    aria-label={`Open details for ${label}`}
                                    data-translation-group-id={slot.group_id}
                                    onClick={() =>
                                      onOpenDetails?.(
                                        slot.group_id!,
                                        virtualizer.takeSnapshot(),
                                      )
                                    }
                                  >
                                    <ExternalLink
                                      aria-hidden="true"
                                      className="size-4"
                                    />
                                  </Link>
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>
                                Open details for {label}
                              </TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </article>
            );
          })}
        </div>
        {error && (
          <Alert ref={alertRef} tabIndex={-1}>
            <AlertTitle>More translations could not be loaded</AlertTitle>
            {onRefresh && (
              <Button variant="outline" onClick={onRefresh}>
                Refresh results
              </Button>
            )}
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
    </TooltipProvider>
  );
}
