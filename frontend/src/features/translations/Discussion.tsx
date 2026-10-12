import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  createTranslationComment,
  deleteTranslationComment,
  listTranslationComments,
  listTranslationCommentVersions,
  updateTranslationComment,
  type MentionInput,
  type MentionResponse,
  type RoleName,
  type TranslationCommentConflictResponse,
  type TranslationCommentPageResponse,
  type TranslationCommentResponse,
  type TranslationCommentVersionPageResponse,
  type TranslationCommentVersionResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../../components/ui/alert-dialog";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Skeleton } from "../../components/ui/skeleton";
import { useOptionalDirtyFormNavigationGuard } from "../../components/navigation/DirtyFormNavigationGuard";
import { MentionComposer } from "./MentionComposer";

const COMMENT_PAGE_SIZE = 5;
const COMMENT_HISTORY_PAGE_SIZE = 20;
const AUTHOR_ROLES = new Set<RoleName>([
  "admin",
  "product_manager_reviewer",
  "translator",
]);

type DiscussionStatus =
  "loading" | "ready" | "initial-error" | "older-loading" | "older-error";

export interface DiscussionPrincipal {
  id: string;
  roles: readonly RoleName[];
}

export interface DiscussionDraftState {
  dirty: boolean;
  submitting: boolean;
}

export interface DiscussionProps {
  onDraftStateChange?: (state: DiscussionDraftState) => void;
  accessToken: string;
  translationGroupId: string;
  language: string;
  principal: DiscussionPrincipal;
}

function validDate(value: string) {
  return value.length > 0 && Number.isFinite(Date.parse(value));
}

function compareCommentOrder(
  left: Pick<TranslationCommentResponse, "created_at" | "id">,
  right: Pick<TranslationCommentResponse, "created_at" | "id">,
) {
  const byTime = left.created_at.localeCompare(right.created_at);
  return byTime === 0 ? left.id.localeCompare(right.id) : byTime;
}

function validMention(body: string, mention: MentionResponse) {
  return (
    Boolean(mention.user_id) &&
    Boolean(mention.display_text) &&
    Number.isSafeInteger(mention.start_utf16) &&
    Number.isSafeInteger(mention.end_utf16) &&
    mention.start_utf16 >= 0 &&
    mention.end_utf16 > mention.start_utf16 &&
    mention.end_utf16 <= body.length &&
    body.slice(mention.start_utf16, mention.end_utf16) === mention.display_text
  );
}

function validComment(
  value: TranslationCommentResponse,
  translationGroupId: string,
  language: string,
) {
  if (
    !value ||
    !value.id ||
    value.translation_group_id !== translationGroupId ||
    value.language !== language ||
    !value.author?.id ||
    !value.author.display_name ||
    !Number.isSafeInteger(value.current_version) ||
    value.current_version < 1 ||
    !validDate(value.created_at) ||
    !validDate(value.updated_at) ||
    !Array.isArray(value.mentions)
  ) {
    return false;
  }
  if (value.status === "removed") {
    return value.body === null && value.mentions.length === 0;
  }
  if (value.status !== "available" || typeof value.body !== "string") {
    return false;
  }
  const sorted = [...value.mentions].sort(
    (left, right) => left.start_utf16 - right.start_utf16,
  );
  return sorted.every(
    (mention, index) =>
      validMention(value.body as string, mention) &&
      (index === 0 || sorted[index - 1].end_utf16 <= mention.start_utf16),
  );
}

function validCommentPage(
  page: TranslationCommentPageResponse,
  translationGroupId: string,
  language: string,
  retained: readonly TranslationCommentResponse[],
  requestedCursor: string | null,
  seenCursors: ReadonlySet<string>,
) {
  if (
    !page ||
    !Array.isArray(page.items) ||
    page.items.length > COMMENT_PAGE_SIZE
  ) {
    return false;
  }
  const ids = new Set(retained.map((item) => item.id));
  for (const [index, item] of page.items.entries()) {
    if (
      !validComment(item, translationGroupId, language) ||
      ids.has(item.id) ||
      (index > 0 && compareCommentOrder(page.items[index - 1], item) >= 0)
    ) {
      return false;
    }
    ids.add(item.id);
  }
  if (
    requestedCursor !== null &&
    retained.length > 0 &&
    page.items.length > 0 &&
    compareCommentOrder(page.items.at(-1)!, retained[0]) >= 0
  ) {
    return false;
  }
  const next = page.older_cursor ?? null;
  return !(
    (next !== null && !next.trim()) ||
    (next !== null && next === requestedCursor) ||
    (next !== null && seenCursors.has(next)) ||
    (next !== null && page.items.length === 0)
  );
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "long",
  }).format(new Date(value));
}

function MentionedText({
  body,
  mentions,
}: {
  body: string;
  mentions: MentionResponse[];
}) {
  const sorted = [...mentions].sort(
    (left, right) => left.start_utf16 - right.start_utf16,
  );
  if (
    !sorted.every(
      (mention, index) =>
        validMention(body, mention) &&
        (index === 0 || sorted[index - 1].end_utf16 <= mention.start_utf16),
    )
  ) {
    return body;
  }
  const parts: ReactNode[] = [];
  let offset = 0;
  for (const mention of sorted) {
    parts.push(body.slice(offset, mention.start_utf16));
    parts.push(
      <span
        key={`${mention.user_id}:${mention.start_utf16}:${mention.end_utf16}`}
        aria-label={`Mentioned user: ${mention.display_text.replace(/^@/, "")}`}
        className="rounded-sm bg-accent/15 px-0.5 text-foreground"
      >
        {mention.display_text}
      </span>,
    );
    offset = mention.end_utf16;
  }
  parts.push(body.slice(offset));
  return parts;
}

function validVersionPage(
  page: TranslationCommentVersionPageResponse,
  retained: readonly TranslationCommentVersionResponse[],
  requestedCursor: string | null,
  seenCursors: ReadonlySet<string>,
) {
  if (
    !page ||
    !Array.isArray(page.items) ||
    page.items.length > COMMENT_HISTORY_PAGE_SIZE
  ) {
    return false;
  }
  let previous = retained.at(-1)?.version ?? 0;
  for (const item of page.items) {
    if (
      !item ||
      !Number.isSafeInteger(item.version) ||
      item.version <= previous ||
      !item.actor?.id ||
      !item.actor.display_name ||
      !validDate(item.created_at) ||
      !Array.isArray(item.mentions) ||
      (item.status === "available" && typeof item.body !== "string") ||
      (item.status === "removed" &&
        (item.body !== null || item.mentions.length !== 0))
    ) {
      return false;
    }
    if (
      item.status === "available" &&
      !item.mentions.every((mention) =>
        validMention(item.body as string, mention),
      )
    ) {
      return false;
    }
    previous = item.version;
  }
  const next = page.next_cursor ?? null;
  return !(
    (next !== null && !next.trim()) ||
    (next !== null && next === requestedCursor) ||
    (next !== null && seenCursors.has(next)) ||
    (next !== null && page.items.length === 0)
  );
}

function CommentEditHistory({
  accessToken,
  translationGroupId,
  comment,
  position,
}: {
  accessToken: string;
  translationGroupId: string;
  comment: TranslationCommentResponse;
  position: number;
}) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">(
    "idle",
  );
  const [items, setItems] = useState<TranslationCommentVersionResponse[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const generation = useRef(0);
  const active = useRef<AbortController | null>(null);
  const seenCursors = useRef(new Set<string>());

  useEffect(
    () => () => {
      generation.current += 1;
      active.current?.abort();
    },
    [],
  );

  async function load(cursor: string | null) {
    active.current?.abort();
    const controller = new AbortController();
    const requestGeneration = ++generation.current;
    active.current = controller;
    setStatus("loading");
    try {
      const result = await listTranslationCommentVersions({
        auth: accessToken,
        path: {
          translation_group_id: translationGroupId,
          comment_id: comment.id,
        },
        query: { cursor },
        signal: controller.signal,
      });
      if (controller.signal.aborted || requestGeneration !== generation.current)
        return;
      const retained = cursor === null ? [] : items;
      if (
        !result.data ||
        !validVersionPage(result.data, retained, cursor, seenCursors.current)
      ) {
        throw new Error("Invalid comment history page");
      }
      if (cursor) seenCursors.current.add(cursor);
      if (result.data.next_cursor)
        seenCursors.current.add(result.data.next_cursor);
      setItems([...retained, ...result.data.items]);
      setNextCursor(result.data.next_cursor ?? null);
      setStatus("ready");
    } catch {
      if (
        !controller.signal.aborted &&
        requestGeneration === generation.current
      )
        setStatus("error");
    }
  }

  if (!open) {
    return (
      <Button
        type="button"
        variant="outline"
        className="min-h-[44px] h-auto whitespace-normal"
        onClick={() => {
          setOpen(true);
          void load(null);
        }}
      >
        View edit history
      </Button>
    );
  }

  return (
    <section
      aria-label={`Edit history for comment ${position}`}
      className="space-y-(--space-sm) rounded-md border p-(--space-md)"
    >
      <h4 className="font-semibold">Edit history</h4>
      {status === "loading" && items.length === 0 && (
        <p role="status">Loading edit history</p>
      )}
      {status === "error" && (
        <Alert role="alert">
          <AlertTitle>Edit history could not be loaded</AlertTitle>
          <AlertDescription>
            <Button
              type="button"
              variant="outline"
              onClick={() => void load(nextCursor)}
            >
              Retry edit history
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {items.length > 0 && (
        <ol className="space-y-(--space-sm)">
          {items.map((item) => (
            <li
              key={item.version}
              className="space-y-(--space-xs) border-t pt-(--space-sm)"
            >
              <p>Version {item.version}</p>
              <p>Edited by {item.actor.display_name}</p>
              <time dateTime={item.created_at}>
                {formatTimestamp(item.created_at)}
              </time>
              {item.status === "removed" ? (
                <p>Comment removed by an administrator</p>
              ) : (
                <p className="whitespace-pre-wrap wrap-anywhere" dir="auto">
                  <MentionedText
                    body={item.body ?? ""}
                    mentions={item.mentions}
                  />
                </p>
              )}
            </li>
          ))}
        </ol>
      )}
      {nextCursor && status !== "error" && (
        <Button
          type="button"
          variant="outline"
          disabled={status === "loading"}
          onClick={() => void load(nextCursor)}
        >
          Show more edit history
        </Button>
      )}
    </section>
  );
}

function CommentArticle({
  accessToken,
  translationGroupId,
  comment,
  position,
  principal,
  onReplace,
  onDraftStateChange,
}: {
  accessToken: string;
  translationGroupId: string;
  comment: TranslationCommentResponse;
  position: number;
  principal: DiscussionPrincipal;
  onReplace: (comment: TranslationCommentResponse) => void;
  onDraftStateChange: (id: string, state: DiscussionDraftState) => void;
}) {
  const editTrigger = useRef<HTMLButtonElement>(null);
  const restoreEditFocus = useRef(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const [editing, setEditing] = useState(false);
  const [editBody, setEditBody] = useState(comment.body ?? "");
  const [editMentions, setEditMentions] = useState<MentionInput[]>(
    comment.mentions,
  );
  const [saving, setSaving] = useState(false);
  const [failure, setFailure] = useState<"general" | "conflict" | null>(null);
  const [latestConflict, setLatestConflict] =
    useState<TranslationCommentResponse | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteFailure, setDeleteFailure] = useState(false);
  const mutation = useRef<AbortController | null>(null);
  const dirty =
    editing &&
    (editBody !== (comment.body ?? "") ||
      JSON.stringify(
        editMentions.map(({ user_id, start_utf16, end_utf16 }) => [
          user_id,
          start_utf16,
          end_utf16,
        ]),
      ) !==
        JSON.stringify(
          comment.mentions.map(({ user_id, start_utf16, end_utf16 }) => [
            user_id,
            start_utf16,
            end_utf16,
          ]),
        ));
  useEffect(() => {
    onDraftStateChange(comment.id, { dirty, submitting: saving || deleting });
  }, [comment.id, dirty, saving, deleting, onDraftStateChange]);
  useEffect(
    () => () =>
      onDraftStateChange(comment.id, { dirty: false, submitting: false }),
    [comment.id, onDraftStateChange],
  );
  const canAuthor = principal.roles.some((role) => AUTHOR_ROLES.has(role));
  const canEdit =
    comment.status === "available" &&
    canAuthor &&
    comment.author.id === principal.id;
  const canDelete =
    comment.status === "available" && principal.roles.includes("admin");

  useEffect(
    () => () => {
      mutation.current?.abort();
    },
    [],
  );

  useEffect(() => {
    if (!failure) return;
    queueMicrotask(() => errorRef.current?.focus());
  }, [failure]);

  useLayoutEffect(() => {
    if (!editing && restoreEditFocus.current) {
      restoreEditFocus.current = false;
      editTrigger.current?.focus({ preventScroll: true });
    }
  }, [editing]);

  async function save() {
    if (saving || !canEdit || !editBody.trim()) return;
    const controller = new AbortController();
    mutation.current?.abort();
    mutation.current = controller;
    setSaving(true);
    setFailure(null);
    setLatestConflict(null);
    try {
      const result = await updateTranslationComment({
        auth: accessToken,
        path: {
          translation_group_id: translationGroupId,
          comment_id: comment.id,
        },
        body: {
          body: editBody,
          expected_version: comment.current_version,
          mentions: editMentions,
        },
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (result.response?.status === 409 && result.error) {
        const conflict = result.error as TranslationCommentConflictResponse;
        if (
          validComment(conflict.latest, translationGroupId, comment.language)
        ) {
          setLatestConflict(conflict.latest);
        }
        setFailure("conflict");
        return;
      }
      if (
        !result.data ||
        !validComment(result.data, translationGroupId, comment.language) ||
        result.data.id !== comment.id ||
        result.data.current_version <= comment.current_version
      ) {
        throw new Error("Invalid edited comment projection");
      }
      onReplace(result.data);
      restoreEditFocus.current = true;
      setEditing(false);
      setFailure(null);
    } catch {
      if (!controller.signal.aborted) setFailure("general");
    } finally {
      if (!controller.signal.aborted) setSaving(false);
    }
  }

  async function remove() {
    if (deleting || !canDelete) return;
    const controller = new AbortController();
    mutation.current?.abort();
    mutation.current = controller;
    setDeleting(true);
    setDeleteFailure(false);
    try {
      const result = await deleteTranslationComment({
        auth: accessToken,
        path: {
          translation_group_id: translationGroupId,
          comment_id: comment.id,
        },
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (
        !result.data ||
        !validComment(result.data, translationGroupId, comment.language) ||
        result.data.id !== comment.id ||
        result.data.status !== "removed"
      ) {
        throw new Error("Invalid removed comment projection");
      }
      onReplace(result.data);
      setDeleteOpen(false);
    } catch {
      if (!controller.signal.aborted) setDeleteFailure(true);
    } finally {
      if (!controller.signal.aborted) setDeleting(false);
    }
  }

  return (
    <article
      id={`comment-${comment.id}`}
      tabIndex={-1}
      className="min-w-0 space-y-(--space-md) border-t pt-(--space-md) first:border-t-0 first:pt-0"
    >
      {comment.status === "removed" ? (
        <>
          <h3 className="font-semibold">Comment {position}</h3>
          <p>Comment removed by an administrator</p>
          {comment.deleted_at && (
            <time dateTime={comment.deleted_at}>
              {formatTimestamp(comment.deleted_at)}
            </time>
          )}
        </>
      ) : (
        <>
          <div className="flex min-w-0 flex-wrap items-center gap-(--space-sm)">
            <h3 className="font-semibold wrap-anywhere">
              {comment.author.display_name}
            </h3>
            {comment.edited && <Badge variant="outline">Edited</Badge>}
          </div>
          <time dateTime={comment.created_at}>
            {formatTimestamp(comment.created_at)}
          </time>
          <p className="whitespace-pre-wrap wrap-anywhere" dir="auto">
            <MentionedText
              body={comment.body ?? ""}
              mentions={comment.mentions}
            />
          </p>
          {editing && (
            <div className="space-y-(--space-sm)">
              <MentionComposer
                translationGroupId={translationGroupId}
                accessToken={accessToken}
                id={`edit-${comment.id}`}
                label="Edit comment text"
                body={editBody}
                mentions={editMentions}
                disabled={saving}
                onChange={(nextBody, nextMentions) => {
                  setEditBody(nextBody);
                  setEditMentions(nextMentions);
                  setFailure(null);
                }}
              />
              {failure && (
                <Alert ref={errorRef} tabIndex={-1} role="alert">
                  <AlertTitle>
                    {failure === "conflict"
                      ? "Comment changed in another session"
                      : "Comment was not saved"}
                  </AlertTitle>
                  <AlertDescription>
                    {failure === "conflict" ? (
                      <div className="space-y-(--space-sm)">
                        <p>
                          Your comment is still in the editor. Reload the latest
                          comment before replacing it.
                        </p>
                        {latestConflict?.body !== null && latestConflict && (
                          <div>
                            <p className="font-semibold">
                              Latest saved comment
                            </p>
                            <p
                              className="whitespace-pre-wrap wrap-anywhere"
                              dir="auto"
                            >
                              {latestConflict.body}
                            </p>
                          </div>
                        )}
                      </div>
                    ) : (
                      "Your comment is still in the editor. Review it and try again."
                    )}
                  </AlertDescription>
                </Alert>
              )}
              <div className="flex flex-wrap gap-(--space-sm)">
                <Button
                  type="button"
                  variant="outline"
                  disabled={saving}
                  onClick={() => {
                    restoreEditFocus.current = true;
                    setEditing(false);
                    setFailure(null);
                    setEditBody(comment.body ?? "");
                    setEditMentions(comment.mentions);
                  }}
                >
                  Stop editing comment
                </Button>
                <Button
                  type="button"
                  aria-busy={saving}
                  disabled={saving || !editBody.trim()}
                  onClick={() => void save()}
                >
                  Save comment
                </Button>
              </div>
            </div>
          )}
          {!editing && (
            <div className="flex flex-wrap gap-(--space-sm)">
              {canEdit && (
                <Button
                  ref={editTrigger}
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setEditBody(comment.body ?? "");
                    setEditMentions(comment.mentions);
                    setEditing(true);
                  }}
                >
                  Edit comment
                </Button>
              )}
              {comment.edited && (
                <CommentEditHistory
                  accessToken={accessToken}
                  translationGroupId={translationGroupId}
                  comment={comment}
                  position={position}
                />
              )}
              {canDelete && (
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => setDeleteOpen(true)}
                >
                  Delete comment
                </Button>
              )}
            </div>
          )}
          <AlertDialog
            open={deleteOpen}
            onOpenChange={(open) => !deleting && setDeleteOpen(open)}
          >
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this comment?</AlertDialogTitle>
                <AlertDialogDescription>
                  The comment text will no longer be visible. Its audit record
                  and existing notification links will remain.
                </AlertDialogDescription>
              </AlertDialogHeader>
              {deleteFailure && (
                <Alert role="alert">
                  <AlertTitle>Comment was not deleted</AlertTitle>
                  <AlertDescription>
                    The original comment is still visible.
                  </AlertDescription>
                </Alert>
              )}
              <AlertDialogFooter>
                <AlertDialogCancel disabled={deleting}>
                  Keep comment
                </AlertDialogCancel>
                <Button
                  type="button"
                  variant="destructive"
                  aria-busy={deleting}
                  disabled={deleting}
                  onClick={() => void remove()}
                >
                  Delete comment
                </Button>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </>
      )}
    </article>
  );
}

function DiscussionContent({
  accessToken,
  translationGroupId,
  language,
  principal,
  onDraftStateChange,
}: DiscussionProps) {
  const [status, setStatus] = useState<DiscussionStatus>("loading");
  const [items, setItems] = useState<TranslationCommentResponse[]>([]);
  const [olderCursor, setOlderCursor] = useState<string | null>(null);
  const generation = useRef(0);
  const active = useRef<AbortController | null>(null);
  const seenCursors = useRef(new Set<string>());
  const prependPosition = useRef<{
    scrollHeight: number;
    scrollY: number;
    focused: HTMLElement | null;
    fallbackCommentId: string | null;
  } | null>(null);
  const createdFocusId = useRef<string | null>(null);
  const [newBody, setNewBody] = useState("");
  const [newMentions, setNewMentions] = useState<MentionInput[]>([]);
  const [posting, setPosting] = useState(false);
  const [postFailure, setPostFailure] = useState(false);
  const postRequest = useRef<AbortController | null>(null);
  const [editedDrafts, setEditedDrafts] = useState<
    Record<string, DiscussionDraftState>
  >({});
  const trackEditedDraft = useCallback(
    (id: string, state: DiscussionDraftState) => {
      setEditedDrafts((current) => {
        if (
          (current[id]?.dirty ?? false) === state.dirty &&
          (current[id]?.submitting ?? false) === state.submitting
        )
          return current;
        const next = { ...current };
        if (state.dirty || state.submitting) next[id] = state;
        else delete next[id];
        return next;
      });
    },
    [],
  );
  const dirty =
    newBody.length > 0 ||
    newMentions.length > 0 ||
    Object.values(editedDrafts).some((state) => state.dirty);
  const submitting =
    posting || Object.values(editedDrafts).some((state) => state.submitting);
  useOptionalDirtyFormNavigationGuard(
    `discussion:${principal.id}:${translationGroupId}:${language}`,
    dirty || submitting,
  );
  useEffect(() => {
    onDraftStateChange?.({ dirty, submitting });
  }, [onDraftStateChange, dirty, submitting]);
  useEffect(
    () => () => onDraftStateChange?.({ dirty: false, submitting: false }),
    [onDraftStateChange],
  );
  const canComment = principal.roles.some((role) => AUTHOR_ROLES.has(role));

  useEffect(
    () => () => {
      generation.current += 1;
      active.current?.abort();
      postRequest.current?.abort();
    },
    [],
  );

  useLayoutEffect(() => {
    const pending = prependPosition.current;
    if (!pending) return;
    prependPosition.current = null;
    const delta = document.documentElement.scrollHeight - pending.scrollHeight;
    if (delta !== 0) window.scrollTo({ top: pending.scrollY + delta });
    if (pending.focused?.isConnected) {
      pending.focused.focus({ preventScroll: true });
    } else if (pending.fallbackCommentId) {
      document
        .getElementById(`comment-${pending.fallbackCommentId}`)
        ?.focus({ preventScroll: true });
    }
  }, [items]);

  useLayoutEffect(() => {
    const id = createdFocusId.current;
    if (!id) return;
    createdFocusId.current = null;
    document.getElementById(`comment-${id}`)?.focus({ preventScroll: true });
  }, [items]);

  async function load(cursor: string | null, initial: boolean) {
    active.current?.abort();
    const controller = new AbortController();
    const requestGeneration = ++generation.current;
    active.current = controller;
    setStatus(initial ? "loading" : "older-loading");
    try {
      const result = await listTranslationComments({
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
        !validCommentPage(
          result.data,
          translationGroupId,
          language,
          retained,
          cursor,
          seenCursors.current,
        )
      ) {
        throw new Error("Invalid comment page");
      }
      if (!initial) {
        prependPosition.current = {
          scrollHeight: document.documentElement.scrollHeight,
          scrollY: window.scrollY,
          focused:
            document.activeElement instanceof HTMLElement
              ? document.activeElement
              : null,
          fallbackCommentId: result.data.items[0]?.id ?? null,
        };
      } else {
        seenCursors.current = new Set();
      }
      if (cursor) seenCursors.current.add(cursor);
      if (result.data.older_cursor)
        seenCursors.current.add(result.data.older_cursor);
      setItems(
        initial ? result.data.items : [...result.data.items, ...retained],
      );
      setOlderCursor(result.data.older_cursor ?? null);
      setStatus("ready");
    } catch {
      if (
        !controller.signal.aborted &&
        requestGeneration === generation.current
      ) {
        setStatus(initial ? "initial-error" : "older-error");
      }
    } finally {
      if (requestGeneration === generation.current) active.current = null;
    }
  }

  useEffect(() => {
    const requestGeneration = generation.current;
    queueMicrotask(() => {
      if (generation.current === requestGeneration) void load(null, true);
    });
    return () => active.current?.abort();
    // A principal/token/group/language remount is owned by the caller key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function replaceComment(fresh: TranslationCommentResponse) {
    setItems((current) =>
      current.map((item) => (item.id === fresh.id ? fresh : item)),
    );
  }

  async function postComment() {
    if (!canComment || posting || !newBody.trim()) return;
    postRequest.current?.abort();
    const controller = new AbortController();
    postRequest.current = controller;
    setPosting(true);
    setPostFailure(false);
    try {
      const result = await createTranslationComment({
        auth: accessToken,
        path: { translation_group_id: translationGroupId },
        body: { body: newBody, mentions: newMentions },
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      const fresh = result.data;
      if (
        !fresh ||
        !validComment(fresh, translationGroupId, language) ||
        fresh.status !== "available" ||
        items.some((item) => item.id === fresh.id) ||
        (items.length > 0 && compareCommentOrder(items.at(-1)!, fresh) >= 0)
      ) {
        throw new Error("Invalid created comment projection");
      }
      createdFocusId.current = fresh.id;
      setItems((current) => [...current, fresh]);
      setNewBody("");
      setNewMentions([]);
    } catch {
      if (!controller.signal.aborted) setPostFailure(true);
    } finally {
      if (!controller.signal.aborted) {
        postRequest.current = null;
        setPosting(false);
      }
    }
  }

  return (
    <section
      aria-label="Discussion"
      className="min-w-0 space-y-(--space-md) rounded-lg border bg-secondary p-(--space-lg)"
    >
      <h2 className="text-heading font-semibold">Discussion</h2>
      {status === "loading" && (
        <div role="status" className="space-y-(--space-sm)">
          <p>Loading comments</p>
          {Array.from({ length: 3 }, (_, index) => (
            <Skeleton key={index} className="h-28 w-full" />
          ))}
        </div>
      )}
      {status === "initial-error" && (
        <Alert role="alert">
          <AlertTitle>Comments could not be loaded</AlertTitle>
          <AlertDescription>
            <Button
              type="button"
              variant="outline"
              onClick={() => void load(null, true)}
            >
              Reload comments
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {status !== "loading" &&
        status !== "initial-error" &&
        items.length === 0 && (
          <div className="space-y-(--space-xs)">
            <h3 className="font-semibold">No comments yet</h3>
          </div>
        )}
      {olderCursor && status !== "older-error" && (
        <Button
          type="button"
          variant="outline"
          disabled={status === "older-loading"}
          onClick={() => void load(olderCursor, false)}
        >
          {status === "older-loading"
            ? "Loading earlier comments"
            : "Show earlier comments"}
        </Button>
      )}
      {status === "older-error" && (
        <Alert role="alert">
          <AlertTitle>Earlier comments could not be loaded</AlertTitle>
          <AlertDescription>
            <Button
              type="button"
              variant="outline"
              onClick={() => void load(olderCursor, false)}
            >
              Retry earlier comments
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {items.length > 0 && (
        <div role="list" aria-label="Comments" className="space-y-(--space-md)">
          {items.map((comment, index) => (
            <div key={comment.id} role="listitem">
              <CommentArticle
                accessToken={accessToken}
                translationGroupId={translationGroupId}
                comment={comment}
                position={index + 1}
                principal={principal}
                onReplace={replaceComment}
                onDraftStateChange={trackEditedDraft}
              />
            </div>
          ))}
        </div>
      )}
      {canComment && (
        <form
          className="space-y-(--space-sm) border-t pt-(--space-md)"
          aria-busy={posting}
          onSubmit={(event) => {
            event.preventDefault();
            void postComment();
          }}
        >
          <MentionComposer
            translationGroupId={translationGroupId}
            accessToken={accessToken}
            id={`new-comment-${translationGroupId}`}
            label="Add a comment"
            body={newBody}
            mentions={newMentions}
            disabled={posting}
            onChange={(body, mentions) => {
              setNewBody(body);
              setNewMentions(mentions);
              setPostFailure(false);
            }}
          />
          {postFailure && (
            <Alert role="alert">
              <AlertTitle>Comment was not posted</AlertTitle>
              <AlertDescription>
                Your comment is still in the editor. Review it and try again.
              </AlertDescription>
            </Alert>
          )}
          {(newBody.length > 0 || newMentions.length > 0) && (
            <Button
              type="button"
              variant="outline"
              disabled={posting}
              onClick={() => {
                setNewBody("");
                setNewMentions([]);
                setPostFailure(false);
              }}
            >
              Discard comment draft
            </Button>
          )}
          <Button
            type="submit"
            aria-busy={posting}
            disabled={posting || !newBody.trim()}
          >
            Post comment
          </Button>
        </form>
      )}
    </section>
  );
}

export function Discussion(props: DiscussionProps) {
  return (
    <DiscussionContent
      key={JSON.stringify([
        props.accessToken,
        props.principal.id,
        props.principal.roles,
        props.translationGroupId,
        props.language,
      ])}
      {...props}
    />
  );
}
