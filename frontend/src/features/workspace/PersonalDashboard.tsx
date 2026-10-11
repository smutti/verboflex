import { useCallback, useEffect, useRef, useState } from "react";
import {
  getPersonalDashboard,
  type CurrentUserResponse,
  type DashboardFeed,
  type DashboardResponse,
  type NotificationItemResponse,
} from "../../api/client";
import { ActivityEventList, Destination } from "./ActivityEventList";
import { Button } from "../../components/ui/button";
import { useNotificationShell } from "../notifications/NotificationShell";

function DashboardNotification({ item }: { item: NotificationItemResponse }) {
  const { markRead, readErrorId, readingIds } = useNotificationShell();
  const failure = useRef<HTMLDivElement>(null);
  const failed = readErrorId === item.id;
  useEffect(() => {
    if (failed) failure.current?.focus();
  }, [failed]);
  const summary = (
    <>
      <span className="block font-medium">
        {item.actor.display_name} mentioned you
      </span>
      <span className="mt-1 block text-sm font-normal" dir="auto">
        {item.key_excerpt}
      </span>
    </>
  );
  return (
    <li className="grid min-w-0 gap-2 py-4 first:pt-0 [overflow-wrap:anywhere]">
      {item.comment_status === "available" ? (
        <Destination
          to={`/translations/${encodeURIComponent(item.translation_group_id)}?comment=${encodeURIComponent(item.originating_comment_id)}`}
        >
          {summary}
        </Destination>
      ) : (
        <div>
          {summary}
          <p className="mt-2 text-sm text-muted-foreground">
            Comment no longer available
          </p>
        </div>
      )}
      <div className="flex flex-wrap gap-x-2 text-sm">
        <span className="font-medium">{item.product.name}</span>
        <span className="text-muted-foreground">{item.language}</span>
      </div>
      <p className="text-xs text-muted-foreground">
        <time dateTime={item.created_at}>
          {new Date(item.created_at).toLocaleString()}
        </time>{" "}
        · <span>{item.is_read ? "Read" : "Unread"}</span>
      </p>
      {!item.is_read && !failed ? (
        <Button
          type="button"
          variant="outline"
          className="min-h-[44px] w-fit"
          disabled={readingIds.has(item.id)}
          aria-busy={readingIds.has(item.id)}
          onClick={() => void markRead(item.id)}
        >
          {readingIds.has(item.id) ? "Marking as read" : "Mark as read"}
        </Button>
      ) : null}
      {failed ? (
        <div
          ref={failure}
          role="alert"
          tabIndex={-1}
          className="grid gap-2 rounded-md border border-destructive/40 p-3 text-sm focus-visible:ring-2 focus-visible:ring-ring"
        >
          <p>Notification was not marked as read</p>
          <Button
            type="button"
            variant="outline"
            className="h-auto min-h-[44px] whitespace-normal"
            disabled={readingIds.has(item.id)}
            onClick={() => void markRead(item.id)}
          >
            Retry marking as read
          </Button>
        </div>
      ) : null}
    </li>
  );
}

function DashboardNotifications() {
  const { status, recent, stale, unreadCount, refresh } =
    useNotificationShell();
  return (
    <section
      aria-labelledby="dashboard-notifications"
      className="min-w-0 rounded-lg border bg-card p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="dashboard-notifications" className="text-heading font-semibold">
          Notifications
        </h2>
        {status === "ready" || recent.length > 0 ? (
          <span className="rounded-full bg-primary/10 px-2 py-1 text-xs font-semibold text-primary">
            {unreadCount} unread
          </span>
        ) : null}
      </div>
      <Button
        variant="ghost"
        className="my-2 min-h-[44px] px-0"
        disabled={status === "loading"}
        onClick={() => void refresh()}
      >
        Refresh notifications
      </Button>
      {status === "loading" ? (
        <p role="status" className="py-6 text-sm text-muted-foreground">
          Loading notifications
        </p>
      ) : (
        <>
          {status === "error" && recent.length === 0 ? (
            <p role="alert" className="py-6 text-sm">
              Notifications could not be loaded
            </p>
          ) : (
            <>
              {stale ? (
                <p role="status" className="mb-3 text-sm text-muted-foreground">
                  May be out of date
                </p>
              ) : null}
              {recent.length ? (
                <ul className="divide-y">
                  {recent.slice(0, 5).map((item) => (
                    <DashboardNotification key={item.id} item={item} />
                  ))}
                </ul>
              ) : (
                <div className="grid gap-2 py-6 text-sm">
                  <p className="font-medium">No notifications yet</p>
                </div>
              )}
            </>
          )}
        </>
      )}
      <div className="mt-3 border-t pt-4 text-sm">
        <Destination to="/notifications">View all notifications</Destination>
      </div>
    </section>
  );
}

function ActivityFeed({
  title,
  id,
  feed,
  personal,
}: {
  title: string;
  id: string;
  feed: DashboardFeed;
  personal: boolean;
}) {
  return (
    <section
      aria-labelledby={id}
      className="min-w-0 rounded-lg border bg-card p-5"
    >
      <h2 id={id} className="text-heading font-semibold">
        {title}
      </h2>
      {feed.items.length ? (
        <ActivityEventList items={feed.items.slice(0, 3)} />
      ) : (
        <div className="grid gap-2 py-8 text-sm">
          <p className="font-medium">
            {personal ? "No recent activity yet" : "No project updates yet"}
          </p>
        </div>
      )}
      <div className="mt-3 grid gap-2 border-t pt-4 text-sm">
        <Destination to={personal ? "/my-activity" : "/project-updates"}>
          {personal ? "View all my activity" : "View all project updates"}
        </Destination>
      </div>
    </section>
  );
}

type ActivityState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; data: DashboardResponse };
function ActivityController({ accessToken }: { accessToken: string }) {
  const [state, setState] = useState<ActivityState>({ status: "loading" });
  const generation = useRef(0);
  const request = useRef<AbortController | null>(null);
  const load = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const current = ++generation.current;
    setState({ status: "loading" });
    try {
      const response = await getPersonalDashboard({
        auth: accessToken,
        signal: controller.signal,
      });
      if (controller.signal.aborted || current !== generation.current) return;
      if (!response.data) throw new Error("Activity unavailable");
      setState({ status: "ready", data: response.data });
    } catch {
      if (!controller.signal.aborted && current === generation.current)
        setState({ status: "error" });
    }
  }, [accessToken]);
  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) void load();
    });
    return () => {
      active = false;
      generation.current += 1;
      request.current?.abort();
    };
  }, [load]);

  return (
    <div className="grid min-w-0 gap-4">
      <div className="flex justify-end">
        <Button
          variant="outline"
          className="min-h-[44px]"
          onClick={() => void load()}
          disabled={state.status === "loading"}
        >
          Refresh activity
        </Button>
      </div>
      <div className="grid min-w-0 items-start gap-4 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,2fr)]">
        <DashboardNotifications />
        <div className="min-w-0">
          {state.status === "loading" ? (
            <p
              role="status"
              className="rounded-lg border p-6 text-muted-foreground"
            >
              Loading activity
            </p>
          ) : state.status === "error" ? (
            <div
              role="alert"
              className="grid gap-3 rounded-lg border border-destructive/40 p-5"
            >
              <p>Activity could not be loaded. Please try again.</p>
              <Button
                variant="outline"
                className="w-fit"
                onClick={() => void load()}
              >
                Retry activity
              </Button>
            </div>
          ) : (
            <div className="grid min-w-0 items-start gap-4 lg:grid-cols-2">
              <ActivityFeed
                id="my-activity"
                title="My recent activity"
                feed={state.data.my_activity}
                personal
              />
              <ActivityFeed
                id="project-updates"
                title="Project updates"
                feed={state.data.project_updates}
                personal={false}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function PersonalDashboard({
  accessToken,
  principal,
}: {
  accessToken: string;
  principal: CurrentUserResponse;
}) {
  const authorityKey = JSON.stringify([
    principal.id,
    accessToken,
    [...principal.roles].sort(),
  ]);
  return <ActivityController key={authorityKey} accessToken={accessToken} />;
}
