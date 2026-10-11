import "@testing-library/jest-dom/vitest";
import * as React from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  searchMentionUsers,
  type MentionInput,
  type MentionUserResponse,
} from "../../api/client";
import { MentionComposer } from "./MentionComposer";

vi.mock("../../api/client", () => ({ searchMentionUsers: vi.fn() }));

const people: MentionUserResponse[] = Array.from(
  { length: 10 },
  (_, index) => ({
    id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    display_name: index === 0 ? "Ada 👩🏽‍💻" : `Person ${index + 1}`,
    email: `person${index + 1}@example.test`,
  }),
);

function Harness({
  initial = "",
  selected = [],
}: {
  initial?: string;
  selected?: MentionInput[];
}) {
  const [body, setBody] = React.useState(initial);
  const [mentions, setMentions] = React.useState(selected);
  return (
    <form>
      <MentionComposer
        accessToken="token"
        id="comment-composer"
        label="Add a comment"
        body={body}
        mentions={mentions}
        onChange={(nextBody, nextMentions) => {
          setBody(nextBody);
          setMentions(nextMentions);
        }}
      />
      <button type="submit" disabled={!body.trim()}>
        Post comment
      </button>
      <output data-testid="mentions">{JSON.stringify(mentions)}</output>
    </form>
  );
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(searchMentionUsers).mockResolvedValue({
    data: people,
    error: undefined,
  } as never);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe("MentionComposer autocomplete", () => {
  it("dispatches at exactly 150ms, caps active results at eight, and keeps textarea focus", async () => {
    render(<Harness />);
    const textbox = screen.getByRole("textbox", {
      name: "Add a comment",
    }) as HTMLTextAreaElement;
    textbox.focus();
    fireEvent.change(textbox, {
      target: { value: "Hi @ad", selectionStart: 6 },
    });
    expect(textbox).toHaveAttribute("aria-expanded", "true");
    expect(searchMentionUsers).not.toHaveBeenCalled();
    await act(() => vi.advanceTimersByTimeAsync(149));
    expect(searchMentionUsers).not.toHaveBeenCalled();
    await act(() => vi.advanceTimersByTimeAsync(1));
    expect(searchMentionUsers).toHaveBeenCalledWith(
      expect.objectContaining({
        auth: "token",
        query: { q: "ad" },
        signal: expect.any(AbortSignal),
      }),
    );
    const listbox = screen.getByRole("listbox", { name: "Mention a person" });
    expect(within(listbox).getAllByRole("option")).toHaveLength(8);
    expect(textbox).toHaveFocus();
  });

  it("supports arrows, Enter, Tab, Escape, and immutable UTF-16 identity", async () => {
    render(<Harness initial="👨‍👩‍👧‍👦 مرحبا @a" />);
    const textbox = screen.getByRole("textbox", {
      name: "Add a comment",
    }) as HTMLTextAreaElement;
    textbox.focus();
    const queried = `${textbox.value}d`;
    fireEvent.change(textbox, {
      target: { value: queried, selectionStart: queried.length },
    });
    await act(() => vi.advanceTimersByTimeAsync(150));
    expect(screen.getByRole("listbox")).toBeVisible();
    fireEvent.keyDown(textbox, { key: "ArrowDown" });
    fireEvent.keyDown(textbox, { key: "Enter" });
    expect(textbox).toHaveValue("👨‍👩‍👧‍👦 مرحبا @Person 2");
    const selected = JSON.parse(
      screen.getByTestId("mentions").textContent ?? "[]",
    ) as MentionInput[];
    expect(selected).toEqual([
      {
        user_id: people[1].id,
        display_text: "@Person 2",
        start_utf16: "👨‍👩‍👧‍👦 مرحبا ".length,
        end_utf16: "👨‍👩‍👧‍👦 مرحبا @Person 2".length,
      },
    ]);
    const tabQuery = `${textbox.value} @p`;
    fireEvent.change(textbox, {
      target: { value: tabQuery, selectionStart: tabQuery.length },
    });
    await act(() => vi.advanceTimersByTimeAsync(150));
    fireEvent.keyDown(textbox, { key: "Tab" });
    expect(textbox).toHaveFocus();
    const escapeQuery = `${textbox.value} @x`;
    fireEvent.change(textbox, {
      target: { value: escapeQuery, selectionStart: escapeQuery.length },
    });
    await act(() => vi.advanceTimersByTimeAsync(150));
    fireEvent.keyDown(textbox, { key: "Escape" });
    expect(textbox).toHaveAttribute("aria-expanded", "false");
  });

  it("supports pointer selection without transferring DOM focus", async () => {
    render(<Harness initial="@a" />);
    const textbox = screen.getByRole("textbox", {
      name: "Add a comment",
    }) as HTMLTextAreaElement;
    textbox.focus();
    textbox.setSelectionRange(2, 2);
    await act(() => vi.advanceTimersByTimeAsync(150));
    const option = screen.getByRole("option", { name: /Ada/ });
    fireEvent.mouseDown(option);
    expect(textbox).toHaveFocus();
    expect(textbox).toHaveValue("@Ada 👩🏽‍💻");
  });

  it("aborts superseded requests and ignores stale responses", async () => {
    let resolveOld!: (value: unknown) => void;
    vi.mocked(searchMentionUsers)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveOld = resolve;
        }) as never,
      )
      .mockResolvedValueOnce({ data: [people[1]], error: undefined } as never);
    render(<Harness />);
    const textbox = screen.getByRole("textbox", {
      name: "Add a comment",
    }) as HTMLTextAreaElement;
    fireEvent.change(textbox, { target: { value: "@a", selectionStart: 2 } });
    await act(() => vi.advanceTimersByTimeAsync(150));
    const oldSignal = vi.mocked(searchMentionUsers).mock.calls[0][0].signal;
    fireEvent.change(textbox, { target: { value: "@ab", selectionStart: 3 } });
    await act(() => vi.advanceTimersByTimeAsync(150));
    expect(oldSignal?.aborted).toBe(true);
    resolveOld({ data: [people[0]], error: undefined });
    const listbox = screen.getByRole("listbox");
    expect(within(listbox).getByRole("option")).toHaveAccessibleName(
      /Person 2/,
    );
  });

  it("keeps ordinary @ text submittable through no-result and failed searches", async () => {
    vi.mocked(searchMentionUsers).mockRejectedValue(
      new Error("private failure"),
    );
    render(<Harness />);
    const textbox = screen.getByRole("textbox", {
      name: "Add a comment",
    }) as HTMLTextAreaElement;
    fireEvent.change(textbox, {
      target: { value: "Plain @nobody", selectionStart: 13 },
    });
    await act(() => vi.advanceTimersByTimeAsync(150));
    expect(
      screen.getByText(
        "People search is unavailable. You can still post ordinary text.",
      ),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Post comment" })).toBeEnabled();
    expect(screen.getByTestId("mentions")).toHaveTextContent("[]");
    expect(document.body).not.toHaveTextContent("private failure");
  });
});

describe("MentionComposer range maintenance", () => {
  it.each(["😀 ", "e\u0301 ", "👩‍👩‍👧‍👦 ", "line\r\n", "漢字 ", "مرحبا "])(
    "records browser UTF-16 coordinates after %s",
    async (prefix) => {
      render(<Harness initial={`${prefix}@a`} />);
      const textbox = screen.getByRole("textbox", {
        name: "Add a comment",
      }) as HTMLTextAreaElement;
      textbox.focus();
      textbox.setSelectionRange(textbox.value.length, textbox.value.length);
      await act(() => vi.advanceTimersByTimeAsync(150));
      fireEvent.keyDown(textbox, { key: "Enter" });
      const selected = JSON.parse(
        screen.getByTestId("mentions").textContent ?? "[]",
      ) as MentionInput[];
      expect(selected[0].start_utf16).toBe(prefix.length);
      expect(selected[0].end_utf16).toBe(`${prefix}@Ada 👩🏽‍💻`.length);
    },
  );

  it("shifts unaffected ranges and visibly drops identity when its exact slice changes", async () => {
    const display = "@Ada 👩🏽‍💻";
    const initial = `Before ${display} after`;
    const mention = {
      user_id: people[0].id,
      display_text: display,
      start_utf16: 7,
      end_utf16: 7 + display.length,
    };
    render(<Harness initial={initial} selected={[mention]} />);
    const textbox = screen.getByRole("textbox", {
      name: "Add a comment",
    }) as HTMLTextAreaElement;
    fireEvent.change(textbox, {
      target: { value: `X${initial}`, selectionStart: 1 },
    });
    expect(screen.getByTestId("mentions")).toHaveTextContent('"start_utf16":8');
    const changed = `XBefore @B${display.slice(2)} after`;
    fireEvent.change(textbox, {
      target: { value: changed, selectionStart: 9 },
    });
    expect(screen.getByTestId("mentions")).toHaveTextContent("[]");
    expect(screen.queryByRole("button", { name: /Remove mention/ })).toBeNull();
  });
});

describe("selected mention dismissal", () => {
  it.each(["pointer", "Enter", "Tab"])(
    "does not reopen a single-word mention after %s selection or caret movement",
    async (method) => {
      vi.mocked(searchMentionUsers).mockResolvedValue({
        data: [{ ...people[0], display_name: "Administrator" }],
        error: undefined,
      } as never);
      render(<Harness initial="Hi @ad" />);
      const field = screen.getByRole("textbox") as HTMLTextAreaElement;
      field.focus();
      field.setSelectionRange(field.value.length, field.value.length);
      await act(() => vi.advanceTimersByTimeAsync(150));
      if (method === "pointer") fireEvent.mouseDown(screen.getByRole("option"));
      else fireEvent.keyDown(field, { key: method });
      await act(() => vi.advanceTimersByTimeAsync(300));
      expect(field).toHaveValue("Hi @Administrator");
      expect(field).toHaveAttribute("aria-expanded", "false");
      expect(screen.queryByRole("listbox")).toBeNull();
      field.setSelectionRange(8, 8);
      fireEvent.click(field);
      await act(() => vi.advanceTimersByTimeAsync(300));
      expect(screen.queryByRole("listbox")).toBeNull();
      expect(searchMentionUsers).toHaveBeenCalledTimes(1);
      const next = `${field.value} @new`;
      fireEvent.change(field, {
        target: { value: next, selectionStart: next.length },
      });
      await act(() => vi.advanceTimersByTimeAsync(150));
      expect(screen.getByRole("listbox")).toBeVisible();
      expect(searchMentionUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({ query: { q: "new" } }),
      );
    },
  );
});
