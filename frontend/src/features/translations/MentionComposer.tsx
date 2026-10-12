import {
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
} from "react";
import { X } from "lucide-react";

import {
  searchMentionUsers,
  type MentionInput,
  type MentionUserResponse,
} from "../../api/client";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";

const MENTION_DEBOUNCE_MS = 150;
const MAX_CANDIDATES = 8;

interface ActiveToken {
  end: number;
  query: string;
  start: number;
}

export interface MentionComposerProps {
  accessToken: string;
  translationGroupId?: string;
  body: string;
  disabled?: boolean;
  id: string;
  label: string;
  maxLength?: number;
  mentions: readonly MentionInput[];
  onChange: (body: string, mentions: MentionInput[]) => void;
}

function activeToken(
  body: string,
  caret: number,
  mentions: readonly MentionInput[],
): ActiveToken | null {
  if (
    mentions.some(
      (mention) =>
        validMention(body, mention) &&
        caret > mention.start_utf16 &&
        caret <= mention.end_utf16,
    )
  )
    return null;
  const beforeCaret = body.slice(0, caret);
  const match = /(^|\s)@([^\s@]*)$/u.exec(beforeCaret);
  if (!match) return null;
  return {
    start: caret - match[2].length - 1,
    end: caret,
    query: match[2],
  };
}

function validPerson(value: MentionUserResponse) {
  return Boolean(value?.id && value.display_name && value.email);
}

function validMention(body: string, mention: MentionInput) {
  return (
    Boolean(mention.user_id && mention.display_text) &&
    Number.isSafeInteger(mention.start_utf16) &&
    Number.isSafeInteger(mention.end_utf16) &&
    mention.start_utf16 >= 0 &&
    mention.end_utf16 > mention.start_utf16 &&
    mention.end_utf16 <= body.length &&
    body.slice(mention.start_utf16, mention.end_utf16) === mention.display_text
  );
}

// Browser string indices and textarea selection offsets are UTF-16 code units.
function reconcileMentions(
  previousBody: string,
  nextBody: string,
  mentions: readonly MentionInput[],
) {
  let prefix = 0;
  while (
    prefix < previousBody.length &&
    prefix < nextBody.length &&
    previousBody[prefix] === nextBody[prefix]
  ) {
    prefix += 1;
  }
  let suffix = 0;
  while (
    suffix < previousBody.length - prefix &&
    suffix < nextBody.length - prefix &&
    previousBody[previousBody.length - suffix - 1] ===
      nextBody[nextBody.length - suffix - 1]
  ) {
    suffix += 1;
  }
  const previousChangeEnd = previousBody.length - suffix;
  const nextChangeEnd = nextBody.length - suffix;
  const delta = nextChangeEnd - previousChangeEnd;
  return mentions
    .map((mention) => {
      if (mention.end_utf16 <= prefix) return { ...mention };
      if (mention.start_utf16 >= previousChangeEnd) {
        return {
          ...mention,
          start_utf16: mention.start_utf16 + delta,
          end_utf16: mention.end_utf16 + delta,
        };
      }
      return null;
    })
    .filter((mention): mention is MentionInput => mention !== null)
    .filter((mention) => validMention(nextBody, mention));
}

export function MentionComposer({
  accessToken,
  translationGroupId,
  body,
  disabled = false,
  id,
  label,
  maxLength = 65_536,
  mentions,
  onChange,
}: MentionComposerProps) {
  const reactId = useId().replaceAll(":", "");
  const listboxId = `${id}-${reactId}-mentions`;
  const textarea = useRef<HTMLTextAreaElement>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const pendingCaret = useRef<number | null>(null);
  const [caret, setCaret] = useState(body.length);
  const [candidates, setCandidates] = useState<MentionUserResponse[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [dismissedToken, setDismissedToken] = useState<string | null>(null);
  const [searchState, setSearchState] = useState<
    "closed" | "searching" | "ready" | "empty" | "error" | "duplicate"
  >(() => (activeToken(body, body.length, mentions) ? "searching" : "closed"));
  const token = useMemo(
    () => activeToken(body, caret, mentions),
    [body, caret, mentions],
  );
  const tokenIdentity = token
    ? `${token.start}:${token.end}:${token.query}`
    : null;
  const expanded =
    token !== null &&
    searchState !== "closed" &&
    dismissedToken !== tokenIdentity;

  useLayoutEffect(() => {
    const position = pendingCaret.current;
    if (position === null) return;
    pendingCaret.current = null;
    textarea.current?.focus({ preventScroll: true });
    textarea.current?.setSelectionRange(position, position);
    setCaret(position);
  }, [body]);

  useEffect(() => {
    activeRequest.current?.abort();
    generation.current += 1;
    if (!token || disabled) {
      return;
    }
    const requestGeneration = generation.current;
    const controller = new AbortController();
    activeRequest.current = controller;
    const timer = window.setTimeout(async () => {
      try {
        const result = await searchMentionUsers({
          auth: accessToken,
          query: {
            q: token.query,
            ...(translationGroupId
              ? { translation_group_id: translationGroupId }
              : {}),
          },
          signal: controller.signal,
        });
        if (
          controller.signal.aborted ||
          generation.current !== requestGeneration
        )
          return;
        if (!result.data || !Array.isArray(result.data))
          throw new Error("Invalid people search");
        const next = result.data.filter(validPerson).slice(0, MAX_CANDIDATES);
        setCandidates(next);
        setActiveIndex(0);
        setSearchState(next.length > 0 ? "ready" : "empty");
      } catch {
        if (
          !controller.signal.aborted &&
          generation.current === requestGeneration
        ) {
          setCandidates([]);
          setSearchState("error");
        }
      }
    }, MENTION_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [accessToken, translationGroupId, disabled, token]);

  useEffect(
    () => () => {
      generation.current += 1;
      activeRequest.current?.abort();
    },
    [],
  );

  function change(event: ChangeEvent<HTMLTextAreaElement>) {
    const nextBody = event.currentTarget.value;
    const nextCaret = event.currentTarget.selectionStart ?? nextBody.length;
    setCaret(nextCaret);
    setCandidates([]);
    setActiveIndex(0);
    setDismissedToken(null);
    const nextMentions = reconcileMentions(body, nextBody, mentions);
    setSearchState(
      activeToken(nextBody, nextCaret, nextMentions) ? "searching" : "closed",
    );
    onChange(nextBody, nextMentions);
  }

  function moveCaret(nextCaret: number) {
    if (nextCaret === caret) return;
    setCaret(nextCaret);
    setCandidates([]);
    setActiveIndex(0);
    setDismissedToken(null);
    setSearchState(
      activeToken(body, nextCaret, mentions) ? "searching" : "closed",
    );
  }

  function select(person: MentionUserResponse) {
    if (!token || !validPerson(person)) return;
    if (mentions.some((mention) => mention.user_id === person.id)) {
      setCandidates([]);
      setSearchState("duplicate");
      return;
    }
    const displayText = `@${person.display_name}`;
    const nextBody =
      body.slice(0, token.start) + displayText + body.slice(token.end);
    const delta = displayText.length - (token.end - token.start);
    const shifted = mentions.map((mention) =>
      mention.start_utf16 >= token.end
        ? {
            ...mention,
            start_utf16: mention.start_utf16 + delta,
            end_utf16: mention.end_utf16 + delta,
          }
        : { ...mention },
    );
    const nextMention: MentionInput = {
      user_id: person.id,
      display_text: displayText,
      start_utf16: token.start,
      end_utf16: token.start + displayText.length,
    };
    generation.current += 1;
    activeRequest.current?.abort();
    const nextCaret = nextMention.end_utf16;
    pendingCaret.current = nextCaret;
    setCandidates([]);
    setSearchState("closed");
    onChange(
      nextBody,
      [...shifted, nextMention].sort(
        (left, right) => left.start_utf16 - right.start_utf16,
      ),
    );
  }

  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (!expanded) return;
    if (event.key === "Escape") {
      event.preventDefault();
      generation.current += 1;
      activeRequest.current?.abort();
      setCandidates([]);
      setDismissedToken(tokenIdentity);
      setSearchState("closed");
      return;
    }
    if (candidates.length === 0) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const direction = event.key === "ArrowDown" ? 1 : -1;
      setActiveIndex(
        (current) =>
          (current + direction + candidates.length) % candidates.length,
      );
      return;
    }
    if (event.key === "Enter" || event.key === "Tab") {
      event.preventDefault();
      select(candidates[activeIndex]);
    }
  }

  function removeMention(mention: MentionInput) {
    onChange(
      body,
      mentions.filter(
        (item) =>
          item.user_id !== mention.user_id ||
          item.start_utf16 !== mention.start_utf16 ||
          item.end_utf16 !== mention.end_utf16,
      ),
    );
    textarea.current?.focus({ preventScroll: true });
  }

  return (
    <div className="relative space-y-(--space-sm)">
      <Label htmlFor={id}>{label}</Label>
      <Textarea
        ref={textarea}
        id={id}
        value={body}
        disabled={disabled}
        maxLength={maxLength}
        dir="auto"
        className="min-h-24 resize-y whitespace-pre-wrap"
        aria-autocomplete="list"
        aria-expanded={expanded}
        aria-controls={expanded ? listboxId : undefined}
        aria-activedescendant={
          expanded && candidates[activeIndex]
            ? `${listboxId}-option-${activeIndex}`
            : undefined
        }
        onChange={change}
        onClick={(event) =>
          moveCaret(event.currentTarget.selectionStart ?? body.length)
        }
        onKeyUp={(event) => {
          if (
            !["ArrowDown", "ArrowUp", "Enter", "Tab", "Escape"].includes(
              event.key,
            )
          ) {
            moveCaret(event.currentTarget.selectionStart ?? body.length);
          }
        }}
        onKeyDown={keyDown}
      />
      <p className="text-label text-muted-foreground">
        {body.length.toLocaleString()} / {maxLength.toLocaleString()} characters
      </p>
      {mentions.length > 0 && (
        <div
          aria-label="Selected mentions"
          className="flex flex-wrap gap-(--space-xs)"
        >
          {mentions.map((mention) => (
            <Badge
              key={`${mention.user_id}:${mention.start_utf16}:${mention.end_utf16}`}
              variant="outline"
              className="gap-(--space-xs) whitespace-normal"
            >
              {mention.display_text}
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                disabled={disabled}
                aria-label={`Remove mention ${mention.display_text}`}
                onClick={() => removeMention(mention)}
              >
                <X aria-hidden="true" />
              </Button>
            </Badge>
          ))}
        </div>
      )}
      {expanded && candidates.length > 0 && (
        <div
          id={listboxId}
          role="listbox"
          aria-label="Mention a person"
          className="absolute z-20 max-h-72 w-full overflow-y-auto rounded-md border bg-popover p-(--space-xs) text-popover-foreground shadow-md"
        >
          {candidates.map((person, index) => (
            <div
              id={`${listboxId}-option-${index}`}
              key={person.id}
              role="option"
              tabIndex={-1}
              aria-selected={index === activeIndex}
              className="cursor-pointer rounded-sm px-3 py-2 aria-selected:bg-accent"
              onMouseDown={(event) => {
                event.preventDefault();
                select(person);
              }}
            >
              <p className="wrap-anywhere font-semibold">
                {person.display_name}
              </p>
              <p className="wrap-anywhere text-label text-muted-foreground">
                {person.email}
              </p>
            </div>
          ))}
        </div>
      )}
      <p aria-live="polite" className="text-label text-muted-foreground">
        {searchState === "searching" && "Searching people"}
        {searchState === "empty" &&
          "No active people found. You can still post ordinary text."}
        {searchState === "error" &&
          "People search is unavailable. You can still post ordinary text."}
        {searchState === "duplicate" &&
          "That person is already selected. The text remains ordinary text."}
      </p>
    </div>
  );
}
