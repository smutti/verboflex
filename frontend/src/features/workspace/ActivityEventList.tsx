import { statusLabel } from "@/i18n/statusLabels";
import { t, useUiLanguage, getUiLanguage } from "@/i18n";
import type { ReactNode } from "react";
import { Link, useInRouterContext } from "react-router-dom";
import type { DashboardFeed } from "../../api/client";

type DashboardEvent = DashboardFeed["items"][number];
const linkClass =
  "inline-block min-h-[44px] rounded-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [overflow-wrap:anywhere]";

export function Destination({
  to,
  children,
}: {
  to: string;
  children: ReactNode;
}) {
  useUiLanguage();
  const inRouter = useInRouterContext();
  return inRouter ? (
    <Link to={to} className={linkClass}>
      {children}
    </Link>
  ) : (
    <a href={to} className={linkClass}>
      {children}
    </a>
  );
}

function eventDestination(event: DashboardEvent): string {
  const product = `/products/${encodeURIComponent(event.product.id)}`;
  if (event.kind === "change_set_submitted")
    return `${product}/change-sets/${encodeURIComponent(event.change_set_id)}`;
  if (event.kind === "current_import_completed") return `${product}/strings`;
  const translation = `${product}/strings/${encodeURIComponent(event.translation_group_id)}`;
  return "comment_id" in event &&
    event.comment_status === "available" &&
    event.comment_id
    ? `${translation}?comment=${encodeURIComponent(event.comment_id)}`
    : translation;
}

function eventLabel(event: DashboardEvent): string {
  switch (event.kind) {
    case "proposal_saved":
      return t("Saved a proposal");
    case "state_changed":
      return t("Changed review state from {{v0}} to {{v1}}", {
        v0: statusLabel(event.from_state),
        v1: statusLabel(event.to_state),
      });
    case "comment_created":
      return t("Added a comment");
    case "comment_edited":
      return t("Edited a comment");
    case "comment_removed":
      return t("Removed a comment");
    case "change_set_submitted":
      return t("Submitted a change set");
    case "current_import_completed":
      return t("Current import completed");
  }
}

export function ActivityEventList({
  items,
}: {
  items: DashboardFeed["items"];
}) {
  useUiLanguage();
  return (
    <ul className="mt-4 divide-y">
      {items.map((event) => (
        <li
          key={event.event_id}
          className="grid min-w-0 gap-2 py-4 first:pt-0 [overflow-wrap:anywhere]"
        >
          <Destination to={eventDestination(event)}>
            <span className="block">{eventLabel(event)}</span>
            {"key_excerpt" in event ? (
              <span className="mt-1 block text-sm font-normal" dir="auto">
                {event.key_excerpt}
              </span>
            ) : null}
          </Destination>
          <div className="flex flex-wrap gap-x-2 text-sm">
            <span className="font-medium">{event.product.name}</span>
            {"language" in event ? (
              <span className="text-muted-foreground">{event.language}</span>
            ) : null}
          </div>
          <p className="text-xs text-muted-foreground">
            {event.actor ? `${event.actor.display_name} · ` : ""}
            <time dateTime={event.occurred_at}>
              {new Date(event.occurred_at).toLocaleString(getUiLanguage())}
            </time>
          </p>
          {event.kind === "change_set_submitted" ? (
            <p className="text-sm text-muted-foreground">
              {t("Current status: ")}
              {statusLabel(event.current_status)}
            </p>
          ) : null}
          {"comment_status" in event && event.comment_status === "removed" ? (
            <p className="text-sm text-muted-foreground">
              {t("Comment no longer available")}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
