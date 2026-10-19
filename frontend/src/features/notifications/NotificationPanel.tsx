import { t, useUiLanguage, getUiLanguage } from "@/i18n";
import { Bell, CircleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useInRouterContext } from "react-router-dom";

import type { NotificationItemResponse } from "../../api/client";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../../components/ui/dropdown-menu";
import { Skeleton } from "../../components/ui/skeleton";
import { useNotificationShell } from "./NotificationShell";

function notificationBellLabel(unreadCount: number): string {
  if (unreadCount === 0) {
    return t("Notifications, no unread notifications");
  }
  if (unreadCount === 1) {
    return t("Notifications, 1 unread notification");
  }
  return t("Notifications, {{v0}} unread notifications", { v0: unreadCount });
}

function notificationHref(item: NotificationItemResponse): string {
  return `/translations/${encodeURIComponent(item.translation_group_id)}?comment=${encodeURIComponent(item.originating_comment_id)}`;
}

function NotificationSummary({ item }: { item: NotificationItemResponse }) {
  useUiLanguage();
  const {
    actor: { display_name: actorDisplayName },
    comment_status: commentStatus,
    created_at: createdAt,
    is_read: isRead,
    key_excerpt: keyExcerpt,
    language,
    product: { name: productName },
  } = item;

  return (
    <div className="grid min-w-0 gap-1 text-left">
      <div className="flex min-w-0 items-center justify-between gap-2">
        <span
          className="min-w-0 truncate font-semibold"
          title={actorDisplayName}
        >
          {actorDisplayName}
        </span>
        <span className="shrink-0 text-xs text-muted-foreground">
          {isRead ? t("Read") : t("Unread")}
        </span>
      </div>
      <span className="truncate text-sm" title={productName}>
        {productName}
      </span>
      <span
        className="line-clamp-2 break-words text-sm text-muted-foreground [overflow-wrap:anywhere]"
        dir="auto"
        title={keyExcerpt}
      >
        {keyExcerpt}
      </span>
      <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
        <span>{language}</span>
        <time dateTime={createdAt}>
          {new Date(createdAt).toLocaleString(getUiLanguage())}
        </time>
      </span>
      {commentStatus === "removed" ? (
        <span className="text-sm font-medium text-muted-foreground">
          {t("Comment no longer available")}
        </span>
      ) : null}
    </div>
  );
}

function NotificationRow({ item }: { item: NotificationItemResponse }) {
  useUiLanguage();
  const { markRead, readErrorId, readingIds } = useNotificationShell();
  const [successAnnouncement, setSuccessAnnouncement] = useState("");
  const alertRef = useRef<HTMLDivElement>(null);
  const isReading = readingIds.has(item.id);
  const failed = readErrorId === item.id;
  const isWithinRouter = useInRouterContext();

  useEffect(() => {
    if (failed) {
      alertRef.current?.focus();
    }
  }, [failed]);

  async function readItem() {
    const succeeded = await markRead(item.id);
    if (succeeded) {
      setSuccessAnnouncement("Notification marked as read");
    }
  }

  const content = <NotificationSummary item={item} />;

  return (
    <article
      className="grid min-w-0 gap-1 rounded-md border bg-background p-1"
      aria-label={t("Notification from {{v0}}", {
        v0: item.actor.display_name,
      })}
    >
      {item.comment_status === "available" ? (
        <DropdownMenuItem
          asChild
          className="h-auto min-h-[44px] items-start p-2"
        >
          {isWithinRouter ? (
            <Link to={notificationHref(item)}>{content}</Link>
          ) : (
            <a href={notificationHref(item)}>{content}</a>
          )}
        </DropdownMenuItem>
      ) : (
        <div className="min-h-[44px] p-2">{content}</div>
      )}
      {!item.is_read ? (
        <DropdownMenuItem
          disabled={isReading}
          aria-busy={isReading}
          onSelect={(event) => {
            event.preventDefault();
            void readItem();
          }}
          className="min-h-[44px] justify-center"
        >
          {isReading ? t("Marking as read") : t("Mark as read")}
        </DropdownMenuItem>
      ) : null}
      {failed ? (
        <div
          ref={alertRef}
          role="alert"
          tabIndex={-1}
          className="grid gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="flex items-center gap-2 font-semibold text-destructive">
            <CircleAlert aria-hidden="true" />
            {t("Notification was not marked as read")}
          </span>
          <Button
            type="button"
            variant="outline"
            onClick={() => void readItem()}
          >
            {t("Retry marking as read")}
          </Button>
        </div>
      ) : null}
      <span className="sr-only" aria-live="polite">
        {successAnnouncement}
      </span>
    </article>
  );
}

function PanelBody() {
  useUiLanguage();
  const { recent, refresh, stale, status } = useNotificationShell();

  if (status === "loading") {
    return (
      <div
        role="status"
        aria-label={t("Loading notifications")}
        className="grid gap-2 p-2"
      >
        {Array.from({ length: 5 }, (_, index) => (
          <Skeleton
            key={index}
            data-testid="notification-skeleton"
            className="h-20 w-full rounded-md"
          />
        ))}
      </div>
    );
  }

  if (status === "error" && recent.length === 0) {
    return (
      <div role="alert" className="grid gap-2 p-2">
        <p className="font-semibold text-destructive">
          {t("Notifications could not be loaded")}
        </p>
        <Button type="button" variant="outline" onClick={() => void refresh()}>
          {t("Refresh notifications")}
        </Button>
      </div>
    );
  }

  if (recent.length === 0) {
    return (
      <div className="grid gap-1 p-4 text-center">
        <p className="font-semibold">{t("No notifications yet")}</p>
      </div>
    );
  }

  return (
    <div className="grid gap-2 p-1">
      {stale ? (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-2 p-1 text-sm"
        >
          <span className="font-medium text-amber-800">
            {t("May be out of date")}
          </span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void refresh()}
          >
            {t("Refresh notifications")}
          </Button>
        </div>
      ) : null}
      {recent.slice(0, 5).map((item) => (
        <NotificationRow key={item.id} item={item} />
      ))}
    </div>
  );
}

export function NotificationPanel() {
  useUiLanguage();
  const { announcement, unreadCount } = useNotificationShell();
  const [open, setOpen] = useState(false);
  const visualCount = unreadCount > 99 ? "99+" : String(unreadCount);
  const isWithinRouter = useInRouterContext();

  return (
    <>
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="relative min-h-[44px] min-w-[44px]"
            aria-label={notificationBellLabel(unreadCount)}
          >
            <Bell aria-hidden="true" />
            {unreadCount > 0 ? (
              <Badge
                data-testid="notification-count-badge"
                aria-hidden="true"
                className="absolute -top-1 -right-1 min-w-5 justify-center rounded-full px-1 text-[0.65rem]"
              >
                {visualCount}
              </Badge>
            ) : null}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          inert={!open}
          align="end"
          aria-labelledby="notification-panel-title"
          className="w-[24rem] max-w-[calc(100vw-2rem)] overflow-x-hidden"
          onCloseAutoFocus={(event) => {
            // Navigation can focus its destination before the menu finishes closing.
            if (document.activeElement !== document.body) {
              event.preventDefault();
            }
          }}
        >
          <DropdownMenuLabel
            id="notification-panel-title"
            className="text-base font-semibold"
          >
            {t("Notifications")}
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <PanelBody />
          <DropdownMenuSeparator />
          <DropdownMenuItem
            asChild
            className="min-h-[44px] justify-center font-medium"
          >
            {isWithinRouter ? (
              <Link to="/notifications">{t("View all notifications")}</Link>
            ) : (
              <a href="/notifications">{t("View all notifications")}</a>
            )}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {t(announcement)}
      </span>
    </>
  );
}
