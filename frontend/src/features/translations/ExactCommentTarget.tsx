import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  getTranslationCommentAnchor,
  markNotificationReadByComment,
  type CommentAnchorWindowResponse,
  type MentionResponse,
  type TranslationCommentResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Skeleton } from "../../components/ui/skeleton";

const ANCHOR_WINDOW_LIMIT = 11;
const HIGHLIGHT_DURATION_MS = 4_000;
const OPAQUE_ID = /^[A-Za-z0-9][A-Za-z0-9._~-]{0,199}$/;

type ExactCommentStatus = "loading" | "ready" | "unavailable";

export interface ExactCommentTargetProps {
  accessToken: string;
  translationGroupId: string;
  language: string;
  commentId: string;
  onFocused?: (commentId: string) => void;
  onNotificationStateChanged?: () => void | Promise<void>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isValidDate(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    Number.isFinite(Date.parse(value))
  );
}

function validMention(
  body: string,
  mention: unknown,
): mention is MentionResponse {
  if (!isRecord(mention)) return false;
  return (
    typeof mention.user_id === "string" &&
    mention.user_id.length > 0 &&
    typeof mention.display_text === "string" &&
    mention.display_text.length > 0 &&
    Number.isSafeInteger(mention.start_utf16) &&
    Number.isSafeInteger(mention.end_utf16) &&
    Number(mention.start_utf16) >= 0 &&
    Number(mention.end_utf16) > Number(mention.start_utf16) &&
    Number(mention.end_utf16) <= body.length &&
    body.slice(Number(mention.start_utf16), Number(mention.end_utf16)) ===
      mention.display_text
  );
}

function validComment(
  value: unknown,
  translationGroupId: string,
  language: string,
): value is TranslationCommentResponse {
  if (
    !isRecord(value) ||
    !isRecord(value.author) ||
    typeof value.id !== "string" ||
    !OPAQUE_ID.test(value.id) ||
    value.translation_group_id !== translationGroupId ||
    value.language !== language ||
    typeof value.author.id !== "string" ||
    value.author.id.length === 0 ||
    typeof value.author.display_name !== "string" ||
    value.author.display_name.length === 0 ||
    !Number.isSafeInteger(value.current_version) ||
    Number(value.current_version) < 1 ||
    typeof value.edited !== "boolean" ||
    !isValidDate(value.created_at) ||
    !isValidDate(value.updated_at) ||
    !Array.isArray(value.mentions)
  ) {
    return false;
  }
  if (value.status === "removed") {
    return (
      value.body === null &&
      value.mentions.length === 0 &&
      isValidDate(value.deleted_at) &&
      typeof value.deleted_by === "string" &&
      value.deleted_by.length > 0
    );
  }
  if (
    value.status !== "available" ||
    typeof value.body !== "string" ||
    value.deleted_at !== null ||
    value.deleted_by !== null
  ) {
    return false;
  }
  const mentions = [...value.mentions].sort(
    (left, right) => Number(left.start_utf16) - Number(right.start_utf16),
  );
  return mentions.every(
    (mention, index) =>
      validMention(value.body as string, mention) &&
      (index === 0 ||
        Number(mentions[index - 1].end_utf16) <= mention.start_utf16),
  );
}

function compareCommentOrder(
  left: TranslationCommentResponse,
  right: TranslationCommentResponse,
) {
  const timestamp = left.created_at.localeCompare(right.created_at);
  return timestamp === 0 ? left.id.localeCompare(right.id) : timestamp;
}

function validWindow(
  value: unknown,
  translationGroupId: string,
  language: string,
  commentId: string,
): value is CommentAnchorWindowResponse {
  if (
    !isRecord(value) ||
    value.target_id !== commentId ||
    !Array.isArray(value.items) ||
    value.items.length < 1 ||
    value.items.length > ANCHOR_WINDOW_LIMIT
  ) {
    return false;
  }
  const ids = new Set<string>();
  let targetCount = 0;
  for (const [index, item] of value.items.entries()) {
    if (
      !validComment(item, translationGroupId, language) ||
      ids.has(item.id) ||
      (index > 0 &&
        compareCommentOrder(
          value.items[index - 1] as TranslationCommentResponse,
          item,
        ) >= 0)
    ) {
      return false;
    }
    ids.add(item.id);
    if (item.id === commentId) targetCount += 1;
  }
  return targetCount === 1;
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "long",
  }).format(new Date(value));
}

function UnavailableComment() {
  return (
    <Alert role="alert">
      <AlertTitle>Comment not available</AlertTitle>
      <AlertDescription className="space-y-(--space-sm)">
        <p>
          This comment may have been removed or is outside your authorized
          products. Return to your notifications and choose another item.
        </p>
        <Link
          to="/notifications"
          className="inline-flex min-h-[44px] items-center underline"
        >
          Back to notifications
        </Link>
      </AlertDescription>
    </Alert>
  );
}

export function ExactCommentTarget({
  accessToken,
  translationGroupId,
  language,
  commentId,
  onFocused,
  onNotificationStateChanged,
}: ExactCommentTargetProps) {
  const validAuthority =
    OPAQUE_ID.test(translationGroupId) && OPAQUE_ID.test(commentId);
  const [status, setStatus] = useState<ExactCommentStatus>(() =>
    validAuthority ? "loading" : "unavailable",
  );
  const [items, setItems] = useState<TranslationCommentResponse[]>([]);
  const [highlighted, setHighlighted] = useState(true);
  const [readFailed, setReadFailed] = useState(false);
  const target = useRef<HTMLElement>(null);
  const focusReported = useRef(false);
  const readStarted = useRef(false);
  const readRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!validAuthority) {
      return;
    }
    const controller = new AbortController();
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      setStatus("loading");
      setItems([]);
      setHighlighted(true);
      setReadFailed(false);
      focusReported.current = false;
      readStarted.current = false;
      void (async () => {
        try {
          const result = await getTranslationCommentAnchor({
            auth: accessToken,
            path: { translation_group_id: translationGroupId },
            query: { comment: commentId },
            signal: controller.signal,
          });
          if (controller.signal.aborted) return;
          if (
            !result.data ||
            !validWindow(result.data, translationGroupId, language, commentId)
          ) {
            throw new Error("Invalid comment anchor window");
          }
          setItems(result.data.items);
          setStatus("ready");
        } catch {
          if (!controller.signal.aborted) setStatus("unavailable");
        }
      })();
    });
    return () => {
      controller.abort();
      readRequest.current?.abort();
    };
  }, [accessToken, commentId, language, translationGroupId, validAuthority]);

  useLayoutEffect(() => {
    if (status !== "ready" || focusReported.current) return;
    const element = target.current;
    if (!element) {
      setStatus("unavailable");
      return;
    }
    try {
      element.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "auto"
          : "smooth",
        block: "center",
      });
      element.focus({ preventScroll: true });
      if (document.activeElement !== element) {
        throw new Error("Comment target did not receive focus");
      }
      focusReported.current = true;
      onFocused?.(commentId);
    } catch {
      setStatus("unavailable");
    }
  }, [commentId, onFocused, status]);

  useEffect(() => {
    if (status !== "ready" || !focusReported.current || readStarted.current)
      return;
    readStarted.current = true;
    const controller = new AbortController();
    readRequest.current = controller;
    void (async () => {
      try {
        const result = await markNotificationReadByComment({
          auth: accessToken,
          path: { comment_id: commentId },
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        const projection = result.data;
        if (
          !projection ||
          !projection.item ||
          !projection.item.is_read ||
          projection.item.originating_comment_id !== commentId ||
          projection.item.translation_group_id !== translationGroupId ||
          projection.item.language !== language ||
          typeof projection.item.id !== "string" ||
          projection.item.id.length === 0 ||
          !Number.isSafeInteger(projection.unread_count) ||
          projection.unread_count < 0
        ) {
          throw new Error("Invalid notification read projection");
        }
        await onNotificationStateChanged?.();
      } catch {
        if (!controller.signal.aborted) setReadFailed(true);
      } finally {
        if (readRequest.current === controller) readRequest.current = null;
      }
    })();
    return () => controller.abort();
  }, [
    accessToken,
    commentId,
    language,
    onNotificationStateChanged,
    status,
    translationGroupId,
  ]);

  useEffect(() => {
    if (status !== "ready" || !focusReported.current) return;
    const timer = window.setTimeout(
      () => setHighlighted(false),
      HIGHLIGHT_DURATION_MS,
    );
    return () => window.clearTimeout(timer);
  }, [status]);

  if (!validAuthority || status === "unavailable")
    return <UnavailableComment />;
  if (status === "loading") {
    return (
      <section aria-label="Exact comment" className="space-y-(--space-sm)">
        <h2 className="text-heading font-semibold">Discussion</h2>
        <div role="status" className="space-y-(--space-sm)">
          <p>Loading comment context</p>
          <Skeleton className="h-28 w-full" />
        </div>
      </section>
    );
  }

  return (
    <section
      aria-label="Discussion"
      className="min-w-0 space-y-(--space-md) rounded-lg border bg-secondary p-(--space-lg)"
    >
      <h2 className="text-heading font-semibold">Discussion</h2>
      {readFailed && (
        <Alert role="alert">
          <AlertTitle>Notification status could not be updated</AlertTitle>
          <AlertDescription>
            The comment is open, but its notification may still appear unread.
            You can try again from Notifications.
          </AlertDescription>
        </Alert>
      )}
      <div role="list" aria-label="Comments" className="space-y-(--space-md)">
        {items.map((item, index) => {
          const isTarget = item.id === commentId;
          return (
            <article
              key={item.id}
              ref={isTarget ? target : undefined}
              role="listitem"
              tabIndex={isTarget ? -1 : undefined}
              data-testid={isTarget ? `exact-comment-${item.id}` : undefined}
              className={`min-w-0 space-y-(--space-sm) rounded-md border-t p-(--space-md) first:border-t-0 ${
                isTarget && highlighted
                  ? "bg-accent/10 ring-2 ring-accent ring-offset-2"
                  : ""
              }`}
            >
              {item.status === "removed" ? (
                <>
                  <h3 className="font-semibold">Comment {index + 1}</h3>
                  <p>Comment removed by an administrator</p>
                  {item.deleted_at && (
                    <time dateTime={item.deleted_at}>
                      {formatTimestamp(item.deleted_at)}
                    </time>
                  )}
                </>
              ) : (
                <>
                  <div className="flex min-w-0 flex-wrap items-center gap-(--space-sm)">
                    <h3 className="font-semibold wrap-anywhere">
                      {item.author.display_name}
                    </h3>
                    {item.edited && <Badge variant="outline">Edited</Badge>}
                  </div>
                  <time dateTime={item.created_at}>
                    {formatTimestamp(item.created_at)}
                  </time>
                  <p className="whitespace-pre-wrap wrap-anywhere" dir="auto">
                    {item.body}
                  </p>
                </>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
