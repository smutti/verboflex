import { useEffect, useRef, useState } from "react";

import {
  listTranslationReviewActivity,
  type ReviewActivityPageResponse,
  type ReviewActivityResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Skeleton } from "../../components/ui/skeleton";

type LoadState =
  "collapsed" | "loading" | "ready" | "initial-error" | "earlier-error";

function validActivityPage(
  page: ReviewActivityPageResponse,
  groupId: string,
  language: string,
  retained: ReviewActivityResponse[],
  requestedCursor: string | null,
  seenCursors: Set<string>,
) {
  if (!page || !Array.isArray(page.items) || page.items.length > 20)
    return false;
  const ids = new Set(retained.map((item) => item.id));
  for (const item of page.items) {
    if (
      !item ||
      !item.id ||
      ids.has(item.id) ||
      item.translation_group_id !== groupId ||
      item.language !== language ||
      !Number.isSafeInteger(item.proposal_version) ||
      item.proposal_version < 1 ||
      !item.actor_id ||
      !item.created_at
    )
      return false;
    ids.add(item.id);
  }
  const next = page.next_cursor ?? null;
  if (
    next !== null &&
    (!next.trim() || next === requestedCursor || seenCursors.has(next))
  )
    return false;
  return true;
}

function ActivityValues({
  title,
  values,
}: {
  title: string;
  values: ReviewActivityResponse["after_values"];
}) {
  if (values === null) return null;
  return (
    <section aria-label={title} className="space-y-(--space-sm)">
      <h4 className="font-semibold">{title}</h4>
      {values.length === 0 ? (
        <p>No values</p>
      ) : (
        values.map((value) => (
          <div
            key={value.translation_value_id}
            className="space-y-(--space-xs)"
          >
            <p className="font-mono wrap-anywhere">
              {value.translation_value_id}
            </p>
            <p className="whitespace-pre-wrap wrap-anywhere" dir="auto">
              {value.text || "Empty translation"}
            </p>
          </div>
        ))
      )}
    </section>
  );
}

function ActivityItem({ item }: { item: ReviewActivityResponse }) {
  return (
    <li className="space-y-(--space-md) rounded-md border p-(--space-md)">
      <div className="flex min-w-0 flex-wrap items-center gap-(--space-sm)">
        <h3 className="font-semibold">
          {item.kind === "proposal_saved"
            ? "Proposal saved"
            : "Review state changed"}
        </h3>
        <Badge variant="outline">Version {item.proposal_version}</Badge>
      </div>
      <p className="wrap-anywhere">Actor: {item.actor_id}</p>
      <time dateTime={item.created_at}>{item.created_at}</time>
      {item.kind === "state_changed" && (
        <p>
          {item.from_state ?? "No prior state"} →{" "}
          {item.to_state ?? "No new state"}
        </p>
      )}
      <ActivityValues title="Before values" values={item.before_values} />
      <ActivityValues title="After values" values={item.after_values} />
      {item.reason !== null && (
        <div className="space-y-(--space-xs)">
          <h4 className="font-semibold">Reason</h4>
          <p className="whitespace-pre-wrap wrap-anywhere">{item.reason}</p>
        </div>
      )}
      {item.comment_id !== null && (
        <a
          className="wrap-anywhere underline"
          href={`#comment-${item.comment_id}`}
        >
          Comment {item.comment_id}
        </a>
      )}
    </li>
  );
}

export function ActivityHistory({
  accessToken,
  translationGroupId,
  language,
}: {
  accessToken: string;
  translationGroupId: string;
  language: string;
}) {
  const [state, setState] = useState<LoadState>("collapsed");
  const [items, setItems] = useState<ReviewActivityResponse[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const seenCursors = useRef(new Set<string>());
  const active = useRef<AbortController | null>(null);
  const generation = useRef(0);

  useEffect(
    () => () => {
      generation.current += 1;
      active.current?.abort();
    },
    [],
  );

  async function load(cursor: string | null, initial: boolean) {
    active.current?.abort();
    const controller = new AbortController();
    const requestGeneration = ++generation.current;
    active.current = controller;
    setState("loading");
    try {
      const result = await listTranslationReviewActivity({
        auth: accessToken,
        path: { translation_group_id: translationGroupId },
        query: { cursor },
        signal: controller.signal,
      });
      if (controller.signal.aborted || requestGeneration !== generation.current)
        return;
      const retained = initial ? [] : items;
      if (
        !result.data ||
        !validActivityPage(
          result.data,
          translationGroupId,
          language,
          retained,
          cursor,
          seenCursors.current,
        )
      )
        throw new Error("Invalid activity page");
      if (cursor) seenCursors.current.add(cursor);
      const next = result.data.next_cursor ?? null;
      if (next) seenCursors.current.add(next);
      setItems(
        initial ? result.data.items : [...retained, ...result.data.items],
      );
      setNextCursor(next);
      setState("ready");
    } catch {
      if (
        !controller.signal.aborted &&
        requestGeneration === generation.current
      )
        setState(initial ? "initial-error" : "earlier-error");
    } finally {
      if (requestGeneration === generation.current) active.current = null;
    }
  }

  if (state === "collapsed")
    return (
      <section aria-label="Activity history" className="space-y-(--space-md)">
        <h2 className="text-heading font-semibold">Activity history</h2>
        <Button
          type="button"
          variant="outline"
          onClick={() => void load(null, true)}
        >
          Show activity history
        </Button>
      </section>
    );

  return (
    <section aria-label="Activity history" className="space-y-(--space-md)">
      <h2 className="text-heading font-semibold">Activity history</h2>
      {state === "loading" && items.length === 0 && (
        <div role="status" className="space-y-(--space-sm)">
          <p>Loading activity history</p>
          {Array.from({ length: 3 }, (_, index) => (
            <Skeleton key={index} className="h-28 w-full" />
          ))}
        </div>
      )}
      {state === "initial-error" && (
        <Alert role="alert">
          <AlertTitle>Activity history could not be loaded</AlertTitle>
          <AlertDescription>
            <Button
              type="button"
              variant="outline"
              onClick={() => void load(null, true)}
            >
              Reload activity history
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {state !== "initial-error" &&
        items.length === 0 &&
        state !== "loading" && (
          <div className="space-y-(--space-xs)">
            <h3 className="font-semibold">No activity yet</h3>
          </div>
        )}
      {items.length > 0 && (
        <ol className="space-y-(--space-md)">
          {items.map((item) => (
            <ActivityItem key={item.id} item={item} />
          ))}
        </ol>
      )}
      {state === "earlier-error" && (
        <Alert role="alert">
          <AlertTitle>Earlier activity could not be loaded</AlertTitle>
          <AlertDescription>
            <Button
              type="button"
              variant="outline"
              onClick={() => void load(nextCursor, false)}
            >
              Retry earlier activity
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {nextCursor && state !== "earlier-error" && (
        <Button
          type="button"
          variant="outline"
          disabled={state === "loading"}
          onClick={() => void load(nextCursor, false)}
        >
          {state === "loading"
            ? "Loading earlier activity"
            : "Show earlier activity"}
        </Button>
      )}
    </section>
  );
}
