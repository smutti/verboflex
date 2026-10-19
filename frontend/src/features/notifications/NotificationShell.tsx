import { t, useUiLanguage } from "@/i18n";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import {
  getUnreadNotificationCount,
  listRecentNotifications,
  markNotificationRead as generatedMarkNotificationRead,
  streamNotificationInvalidations,
  type NotificationInvalidationEventResponse,
  type NotificationItemResponse,
  type NotificationReadResponse,
} from "../../api/client";

const POLL_INTERVAL_MS = 30_000;
const ANNOUNCEMENT_DELAY_MS = 1_000;
const STREAM_RETRY_LIMIT = 5;

export type NotificationShellStatus = "error" | "loading" | "ready";

export interface NotificationShellValue {
  announcement: string;
  markRead: (notificationId: string) => Promise<boolean>;
  readErrorId: string | null;
  readingIds: ReadonlySet<string>;
  recent: readonly NotificationItemResponse[];
  refresh: () => Promise<void>;
  stale: boolean;
  status: NotificationShellStatus;
  unreadCount: number;
}

export interface NotificationShellProps extends PropsWithChildren {
  accessToken: string;
  principalId: string;
}

const NotificationShellContext = createContext<NotificationShellValue | null>(
  null,
);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) >= 0;
}

function isNotificationItem(value: unknown): value is NotificationItemResponse {
  if (!isRecord(value) || !isRecord(value.actor) || !isRecord(value.product)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    value.id.length > 0 &&
    typeof value.actor.user_id === "string" &&
    typeof value.actor.display_name === "string" &&
    (value.comment_status === "available" ||
      value.comment_status === "removed") &&
    typeof value.created_at === "string" &&
    typeof value.is_read === "boolean" &&
    typeof value.key_excerpt === "string" &&
    typeof value.language === "string" &&
    typeof value.originating_comment_id === "string" &&
    typeof value.product.id === "string" &&
    typeof value.product.name === "string" &&
    (value.read_at === undefined ||
      value.read_at === null ||
      typeof value.read_at === "string") &&
    typeof value.translation_group_id === "string"
  );
}

function isRecentProjection(value: unknown): value is {
  items: NotificationItemResponse[];
  next_cursor: string | null;
} {
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    value.items.length > 5 ||
    !(value.next_cursor === null || typeof value.next_cursor === "string") ||
    !value.items.every(isNotificationItem)
  ) {
    return false;
  }
  return new Set(value.items.map(({ id }) => id)).size === value.items.length;
}

function isInvalidation(
  value: unknown,
): value is NotificationInvalidationEventResponse {
  if (!isRecord(value)) {
    return false;
  }
  const keys = Object.keys(value).sort();
  return (
    keys.length === 2 &&
    keys[0] === "id" &&
    keys[1] === "kind" &&
    typeof value.id === "string" &&
    value.id.length > 0 &&
    value.kind === "notifications_changed"
  );
}

function isReadProjection(
  value: unknown,
  notificationId: string,
): value is NotificationReadResponse {
  return (
    isRecord(value) &&
    isNotificationItem(value.item) &&
    value.item.id === notificationId &&
    value.item.is_read &&
    isNonNegativeInteger(value.unread_count)
  );
}

export function NotificationShell({
  accessToken,
  children,
  principalId,
}: NotificationShellProps) {
  return (
    <NotificationShellController
      key={`${principalId}\u0000${accessToken}`}
      accessToken={accessToken}
      principalId={principalId}
    >
      {children}
    </NotificationShellController>
  );
}

function NotificationShellController({
  accessToken,
  children,
}: NotificationShellProps) {
  useUiLanguage();
  const [status, setStatus] = useState<NotificationShellStatus>("loading");
  const [unreadCount, setUnreadCount] = useState(0);
  const [recent, setRecent] = useState<readonly NotificationItemResponse[]>([]);
  const [stale, setStale] = useState(false);
  const [disconnected, setDisconnected] = useState(false);
  const [visible, setVisible] = useState(
    () => document.visibilityState !== "hidden",
  );
  const [announcementCount, setAnnouncementCount] = useState(0);
  const announcement =
    announcementCount === 0
      ? ""
      : announcementCount === 1
        ? t("1 new notification")
        : t("{{v0}} new notifications", { v0: announcementCount });
  const [readingIds, setReadingIds] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const [readErrorId, setReadErrorId] = useState<string | null>(null);

  const shellGeneration = useRef(0);
  const requestGeneration = useRef(0);
  const activeReconcile = useRef<AbortController | null>(null);
  const activeReads = useRef(new Map<string, AbortController>());
  const activeStream = useRef<AsyncGenerator<unknown, unknown, unknown> | null>(
    null,
  );
  const hasCompleteProjection = useRef(false);
  const unreadCountRef = useRef(0);
  const pendingAnnouncementCount = useRef(0);
  const announcementTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const queueAnnouncement = useCallback((count: number) => {
    if (count <= 0) {
      return;
    }
    pendingAnnouncementCount.current += count;
    if (announcementTimer.current !== null) {
      return;
    }
    announcementTimer.current = setTimeout(() => {
      const total = pendingAnnouncementCount.current;
      pendingAnnouncementCount.current = 0;
      announcementTimer.current = null;
      setAnnouncementCount(total);
    }, ANNOUNCEMENT_DELAY_MS);
  }, []);

  const reconcile = useCallback(
    async (announceChanges = true) => {
      const expectedShellGeneration = shellGeneration.current;
      const expectedRequestGeneration = ++requestGeneration.current;
      activeReconcile.current?.abort();
      const controller = new AbortController();
      activeReconcile.current = controller;

      try {
        const [countResult, recentResult] = await Promise.all([
          getUnreadNotificationCount({
            auth: accessToken,
            signal: controller.signal,
          }),
          listRecentNotifications({
            auth: accessToken,
            signal: controller.signal,
          }),
        ]);
        if (
          controller.signal.aborted ||
          shellGeneration.current !== expectedShellGeneration ||
          requestGeneration.current !== expectedRequestGeneration
        ) {
          return;
        }
        const count = countResult.data?.unread_count;
        const recentProjection = recentResult.data;
        if (
          !isNonNegativeInteger(count) ||
          !isRecentProjection(recentProjection)
        ) {
          setStatus("error");
          setStale(hasCompleteProjection.current);
          return;
        }

        const previousCount = unreadCountRef.current;
        unreadCountRef.current = count;
        setUnreadCount(count);
        setRecent(recentProjection.items);
        setStatus("ready");
        setStale(false);
        hasCompleteProjection.current = true;
        if (announceChanges && count > previousCount) {
          queueAnnouncement(count - previousCount);
        }
      } catch {
        if (
          !controller.signal.aborted &&
          shellGeneration.current === expectedShellGeneration &&
          requestGeneration.current === expectedRequestGeneration
        ) {
          setStatus("error");
          setStale(hasCompleteProjection.current);
        }
      } finally {
        if (activeReconcile.current === controller) {
          activeReconcile.current = null;
        }
      }
    },
    [accessToken, queueAnnouncement],
  );

  const markRead = useCallback(
    async (notificationId: string) => {
      if (activeReads.current.has(notificationId)) {
        return false;
      }
      const expectedShellGeneration = shellGeneration.current;
      const controller = new AbortController();
      activeReads.current.set(notificationId, controller);
      setReadErrorId(null);
      setReadingIds(new Set(activeReads.current.keys()));
      try {
        const result = await generatedMarkNotificationRead({
          auth: accessToken,
          path: { notification_id: notificationId },
          signal: controller.signal,
        });
        const projection = result.data;
        if (
          controller.signal.aborted ||
          shellGeneration.current !== expectedShellGeneration
        ) {
          return false;
        }
        if (!isReadProjection(projection, notificationId)) {
          setReadErrorId(notificationId);
          return false;
        }
        unreadCountRef.current = projection.unread_count;
        setUnreadCount(projection.unread_count);
        setRecent((items) =>
          items.map((item) =>
            item.id === notificationId ? projection.item : item,
          ),
        );
        setReadErrorId(null);
        return true;
      } catch {
        if (
          !controller.signal.aborted &&
          shellGeneration.current === expectedShellGeneration
        ) {
          setReadErrorId(notificationId);
        }
        return false;
      } finally {
        if (activeReads.current.get(notificationId) === controller) {
          activeReads.current.delete(notificationId);
          if (
            !controller.signal.aborted &&
            shellGeneration.current === expectedShellGeneration
          ) {
            setReadingIds(new Set(activeReads.current.keys()));
          }
        }
      }
    },
    [accessToken],
  );

  useEffect(() => {
    const generation = ++shellGeneration.current;
    const streamController = new AbortController();
    const reads = activeReads.current;
    let iterator: AsyncGenerator<unknown, unknown, unknown> | null = null;

    const initialReconcileTimer = window.setTimeout(() => {
      if (shellGeneration.current === generation) {
        void reconcile(false);
      }
    }, 0);
    void (async () => {
      try {
        const result = await streamNotificationInvalidations({
          auth: accessToken,
          signal: streamController.signal,
          sseMaxRetryAttempts: STREAM_RETRY_LIMIT,
          sseMaxRetryDelay: POLL_INTERVAL_MS,
          onSseError: () => {
            if (
              !streamController.signal.aborted &&
              shellGeneration.current === generation
            ) {
              setDisconnected(true);
            }
          },
        });
        iterator = result.stream as AsyncGenerator<unknown, unknown, unknown>;
        activeStream.current = iterator;
        for await (const event of iterator) {
          if (
            streamController.signal.aborted ||
            shellGeneration.current !== generation
          ) {
            break;
          }
          if (!isInvalidation(event)) {
            continue;
          }
          setDisconnected(false);
          await reconcile(true);
        }
      } catch {
        // Transport diagnostics are intentionally private. Durable HTTP state remains visible.
      } finally {
        if (
          !streamController.signal.aborted &&
          shellGeneration.current === generation
        ) {
          setDisconnected(true);
        }
        if (activeStream.current === iterator) {
          activeStream.current = null;
        }
      }
    })();

    const handleOnline = () => {
      if (shellGeneration.current === generation) {
        void reconcile(true);
      }
    };
    const handleVisibilityChange = () => {
      const isVisible = document.visibilityState !== "hidden";
      setVisible(isVisible);
      if (isVisible && shellGeneration.current === generation) {
        void reconcile(true);
      }
    };
    window.addEventListener("online", handleOnline);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      shellGeneration.current += 1;
      window.clearTimeout(initialReconcileTimer);
      streamController.abort();
      void iterator?.return?.(undefined);
      activeReconcile.current?.abort();
      activeReconcile.current = null;
      for (const controller of reads.values()) {
        controller.abort();
      }
      reads.clear();
      if (announcementTimer.current !== null) {
        clearTimeout(announcementTimer.current);
        announcementTimer.current = null;
      }
      pendingAnnouncementCount.current = 0;
      window.removeEventListener("online", handleOnline);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [accessToken, reconcile]);

  useEffect(() => {
    if (!disconnected || !visible) {
      return;
    }
    const interval = window.setInterval(() => {
      void reconcile(true);
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [disconnected, reconcile, visible]);

  const value = useMemo<NotificationShellValue>(
    () => ({
      announcement,
      markRead,
      readErrorId,
      readingIds,
      recent,
      refresh: () => reconcile(false),
      stale,
      status,
      unreadCount,
    }),
    [
      announcement,
      markRead,
      readErrorId,
      readingIds,
      recent,
      reconcile,
      stale,
      status,
      unreadCount,
    ],
  );

  return (
    <NotificationShellContext.Provider value={value}>
      {children}
    </NotificationShellContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useNotificationShell(): NotificationShellValue {
  const value = useContext(NotificationShellContext);
  if (value === null) {
    throw new Error(
      "useNotificationShell must be used within NotificationShell",
    );
  }
  return value;
}

// Exact-comment routes also render in isolated component tests and product-scoped
// workspaces. They refresh the shell when one exists without creating a second
// notification owner.
// eslint-disable-next-line react-refresh/only-export-components
export function useOptionalNotificationShell(): NotificationShellValue | null {
  return useContext(NotificationShellContext);
}
