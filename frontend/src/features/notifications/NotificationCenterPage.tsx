import { Bell, CircleAlert } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  listNotifications,
  listTranslationOptions,
  markNotificationRead,
  type NotificationItemResponse,
  type NotificationPageResponse,
  type NotificationReadResponse,
  type TranslationProductOptionResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Label } from "../../components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { Skeleton } from "../../components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "../../components/ui/tabs";

const PAGE_SIZE = 25;
type NotificationView = "all" | "unread";
type LoadStatus = "error" | "loading" | "ready";

function notificationHref(item: NotificationItemResponse) {
  return `/translations/${encodeURIComponent(item.translation_group_id)}?comment=${encodeURIComponent(item.originating_comment_id)}`;
}

function validPage(
  page: NotificationPageResponse,
  view: NotificationView,
  productId: string | null,
  current: readonly NotificationItemResponse[],
  seenCursors: ReadonlySet<string>,
  requestedCursor: string | null,
) {
  if (page.items.length > PAGE_SIZE) return false;
  if (
    page.next_cursor !== null &&
    (page.next_cursor.length === 0 ||
      page.next_cursor === requestedCursor ||
      seenCursors.has(page.next_cursor))
  )
    return false;
  if (page.next_cursor !== null && page.items.length === 0) return false;

  const existingIds = new Set(current.map(({ id }) => id));
  const pageIds = new Set<string>();
  for (const item of page.items) {
    if (
      item.id.length === 0 ||
      pageIds.has(item.id) ||
      existingIds.has(item.id) ||
      (productId !== null && item.product.id !== productId) ||
      (view === "unread" && item.is_read)
    )
      return false;
    pageIds.add(item.id);
  }
  return true;
}

function validReadProjection(
  projection: NotificationReadResponse,
  notificationId: string,
) {
  return (
    projection.item.id === notificationId &&
    projection.item.is_read &&
    Number.isInteger(projection.unread_count) &&
    projection.unread_count >= 0
  );
}

function LoadingRows() {
  return (
    <div role="status" aria-live="polite" className="grid gap-3">
      <span>Loading notifications</span>
      {Array.from({ length: 5 }, (_, index) => (
        <Skeleton key={index} className="h-28 w-full rounded-lg" />
      ))}
    </div>
  );
}

function EmptyState({ view }: { view: NotificationView }) {
  return (
    <section className="grid justify-items-center gap-3 py-12 text-center">
      <Bell aria-hidden="true" className="size-10 text-muted-foreground" />
      <h2 className="text-heading-2 font-semibold">
        {view === "unread" ? "You're all caught up" : "No notifications yet"}
      </h2>
    </section>
  );
}

function NotificationRow({
  item,
  onMarkRead,
  readError,
  reading,
}: {
  item: NotificationItemResponse;
  onMarkRead: (id: string) => void;
  readError: boolean;
  reading: boolean;
}) {
  const alertRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (readError) alertRef.current?.focus();
  }, [readError]);

  const {
    actor: { display_name: actorName },
    comment_status: commentStatus,
    created_at: createdAt,
    is_read: isRead,
    key_excerpt: keyExcerpt,
    language,
    product: { name: productName },
  } = item;

  return (
    <article
      className={`grid min-w-0 gap-3 border-b p-4 ${isRead ? "bg-background" : "bg-accent/5 font-semibold"}`}
      aria-label={`Notification from ${actorName}`}
    >
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <p className="break-words [overflow-wrap:anywhere]">
            <span>{actorName}</span> mentioned you in{" "}
            <span dir="auto">{keyExcerpt}</span>
          </p>
          <p className="flex flex-wrap gap-x-3 gap-y-1 text-sm font-normal text-muted-foreground">
            <span className="break-words [overflow-wrap:anywhere]">
              {productName}
            </span>
            <span>{language}</span>
            <time dateTime={createdAt}>
              {new Date(createdAt).toLocaleString()}
            </time>
          </p>
        </div>
        <Badge variant="outline">{isRead ? "Read" : "Unread"}</Badge>
      </div>

      <div className="flex min-w-0 flex-wrap gap-2">
        {commentStatus === "available" ? (
          <Button
            asChild
            type="button"
            variant="outline"
            className="h-auto min-h-[44px] whitespace-normal"
          >
            <Link to={notificationHref(item)}>Open comment</Link>
          </Button>
        ) : (
          <p className="flex min-h-[44px] items-center text-sm font-medium text-muted-foreground">
            Comment not available
          </p>
        )}
        {!isRead ? (
          <Button
            type="button"
            variant="outline"
            className="h-auto min-h-[44px] whitespace-normal"
            disabled={reading}
            aria-busy={reading}
            onClick={() => onMarkRead(item.id)}
          >
            {reading ? "Marking as read" : "Mark as read"}
          </Button>
        ) : null}
      </div>

      {readError ? (
        <Alert ref={alertRef} tabIndex={-1} variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>Notification was not marked as read</AlertTitle>
          <AlertDescription>
            <Button
              type="button"
              variant="outline"
              onClick={() => onMarkRead(item.id)}
            >
              Retry marking as read
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
    </article>
  );
}

export function NotificationCenterPage({
  accessToken,
  principalId,
}: {
  accessToken: string;
  principalId: string;
}) {
  const productLabelId = useId();
  const [view, setView] = useState<NotificationView>("all");
  const [productId, setProductId] = useState<string | null>(null);
  const [products, setProducts] = useState<
    readonly TranslationProductOptionResponse[]
  >([]);
  const [items, setItems] = useState<readonly NotificationItemResponse[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [status, setStatus] = useState<LoadStatus>("loading");
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState(false);
  const [readingIds, setReadingIds] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const [readErrorId, setReadErrorId] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const requestGeneration = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);
  const activeReads = useRef(new Map<string, AbortController>());
  const seenCursors = useRef(new Set<string>());
  const loadMoreAlertRef = useRef<HTMLDivElement>(null);

  const load = useCallback(
    async (cursor: string | null) => {
      const isMore = cursor !== null;
      const generation = ++requestGeneration.current;
      activeRequest.current?.abort();
      const controller = new AbortController();
      activeRequest.current = controller;
      if (isMore) {
        setLoadingMore(true);
        setLoadMoreError(false);
      } else {
        setStatus("loading");
      }
      try {
        const result = await listNotifications({
          auth: accessToken,
          query: { cursor, product_id: productId, view },
          signal: controller.signal,
        });
        if (
          controller.signal.aborted ||
          generation !== requestGeneration.current ||
          !result.data
        )
          return;
        const currentItems = isMore ? items : [];
        if (
          !validPage(
            result.data,
            view,
            productId,
            currentItems,
            seenCursors.current,
            cursor,
          )
        )
          throw new Error("Invalid notification page");
        if (cursor !== null) seenCursors.current.add(cursor);
        setItems(isMore ? [...items, ...result.data.items] : result.data.items);
        setNextCursor(result.data.next_cursor);
        setStatus("ready");
        setLoadMoreError(false);
      } catch {
        if (
          controller.signal.aborted ||
          generation !== requestGeneration.current
        )
          return;
        if (isMore) setLoadMoreError(true);
        else setStatus("error");
      } finally {
        if (
          !controller.signal.aborted &&
          generation === requestGeneration.current
        ) {
          setLoadingMore(false);
          if (activeRequest.current === controller)
            activeRequest.current = null;
        }
      }
    },
    [accessToken, items, productId, view],
  );

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    void listTranslationOptions({
      auth: accessToken,
      signal: controller.signal,
    })
      .then((result) => {
        if (active && result.data) setProducts(result.data.products);
      })
      .catch(() => undefined);
    return () => {
      active = false;
      controller.abort();
    };
  }, [accessToken, principalId]);

  useEffect(() => {
    seenCursors.current = new Set();
    const timer = window.setTimeout(() => void load(null), 0);
    return () => {
      window.clearTimeout(timer);
      activeRequest.current?.abort();
    };
    // `items` intentionally does not restart the active filter request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, principalId, productId, view]);

  useEffect(
    () => () => {
      requestGeneration.current += 1;
      activeRequest.current?.abort();
      for (const controller of activeReads.current.values()) controller.abort();
      activeReads.current.clear();
    },
    [accessToken, principalId],
  );

  useEffect(() => {
    if (loadMoreError) loadMoreAlertRef.current?.focus();
  }, [loadMoreError]);

  const markRead = useCallback(
    async (notificationId: string) => {
      if (activeReads.current.has(notificationId)) return;
      const controller = new AbortController();
      const expectedPrincipal = principalId;
      activeReads.current.set(notificationId, controller);
      setReadingIds(new Set(activeReads.current.keys()));
      setReadErrorId(null);
      try {
        const result = await markNotificationRead({
          auth: accessToken,
          path: { notification_id: notificationId },
          signal: controller.signal,
        });
        if (
          controller.signal.aborted ||
          expectedPrincipal !== principalId ||
          !result.data ||
          !validReadProjection(result.data, notificationId)
        )
          throw new Error("Invalid read projection");
        const freshItem = result.data.item;
        setItems((current) =>
          view === "unread"
            ? current.filter(({ id }) => id !== notificationId)
            : current.map((item) =>
                item.id === notificationId ? freshItem : item,
              ),
        );
        setAnnouncement("Notification marked as read");
      } catch {
        if (!controller.signal.aborted && expectedPrincipal === principalId)
          setReadErrorId(notificationId);
      } finally {
        if (activeReads.current.get(notificationId) === controller) {
          activeReads.current.delete(notificationId);
          if (!controller.signal.aborted && expectedPrincipal === principalId)
            setReadingIds(new Set(activeReads.current.keys()));
        }
      }
    },
    [accessToken, principalId, view],
  );

  return (
    <main className="mx-auto grid w-full min-w-0 max-w-6xl gap-8">
      <header className="grid min-w-0 gap-2">
        <h1 className="text-heading-1 font-semibold">Notifications</h1>
      </header>

      <section className="grid min-w-0 gap-4" aria-label="Notification filters">
        <Tabs
          value={view}
          onValueChange={(value) =>
            setView(value === "unread" ? "unread" : "all")
          }
        >
          <TabsList aria-label="Notification view" className="min-h-[44px]">
            <TabsTrigger value="all" className="min-h-[44px]">
              All
            </TabsTrigger>
            <TabsTrigger value="unread" className="min-h-[44px]">
              Unread
            </TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="grid min-w-0 gap-2 sm:max-w-md">
          <Label id={productLabelId}>Product</Label>
          <Select
            value={productId ?? "all"}
            onValueChange={(value) =>
              setProductId(value === "all" ? null : value)
            }
          >
            <SelectTrigger
              aria-labelledby={productLabelId}
              className="h-auto min-h-[44px] w-full min-w-0 whitespace-normal"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all" className="min-h-[44px]">
                All products
              </SelectItem>
              {products.map((product) => (
                <SelectItem
                  key={product.id}
                  value={product.id}
                  className="min-h-[44px] whitespace-normal break-words"
                >
                  {product.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </section>

      {status === "loading" ? <LoadingRows /> : null}
      {status === "error" ? (
        <Alert variant="destructive">
          <AlertTitle>Notifications could not be loaded</AlertTitle>
          <AlertDescription className="grid gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => void load(null)}
            >
              Reload notifications
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
      {status === "ready" && items.length === 0 ? (
        <EmptyState view={view} />
      ) : null}
      {status === "ready" && items.length > 0 ? (
        <section
          aria-label="Notifications"
          className="min-w-0 overflow-x-hidden rounded-lg border bg-background"
        >
          {items.map((item) => (
            <NotificationRow
              key={item.id}
              item={item}
              onMarkRead={(id) => void markRead(id)}
              readError={readErrorId === item.id}
              reading={readingIds.has(item.id)}
            />
          ))}
        </section>
      ) : null}

      {status === "ready" && loadMoreError ? (
        <Alert ref={loadMoreAlertRef} tabIndex={-1} variant="destructive">
          <AlertTitle>More notifications could not be loaded</AlertTitle>
          <AlertDescription>
            <Button
              type="button"
              variant="outline"
              onClick={() => nextCursor && void load(nextCursor)}
            >
              Retry loading more
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
      {status === "ready" && !loadMoreError && nextCursor !== null ? (
        <Button
          type="button"
          variant="outline"
          className="h-auto min-h-[44px] justify-self-start whitespace-normal"
          disabled={loadingMore}
          aria-busy={loadingMore}
          onClick={() => void load(nextCursor)}
        >
          {loadingMore
            ? "Loading more notifications"
            : "Load more notifications"}
        </Button>
      ) : null}
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </main>
  );
}
