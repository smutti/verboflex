import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  saveTranslationProposal,
  type TranslationGroupDetailResponse,
  type TranslationProposalResponse,
} from "../../api/client";
import {
  createActiveTranslationDraft,
  writableTranslationDetail,
  TranslationEditor,
  type ActiveTranslationDraft,
} from "./TranslationEditor";
import { TranslationConflictDialog } from "./TranslationConflictDialog";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, saveTranslationProposal: vi.fn() };
});

function detail(): TranslationGroupDetailResponse {
  const value = (id: string, text: string, digest: string) => ({
    id,
    selector_version: 1 as const,
    selector_digest: digest.repeat(64),
    selector_kind: "android_quantity" as const,
    selector_fields: [{ name: "quantity", value: id }],
    source_text: `source-${id}`,
    translated_text: text,
    display_text: text,
    structure: [],
    grapheme_count: text.length,
    constraint: {
      actual: text.length,
      maximum: 12,
      source: "language_override" as const,
      status: "within_limit" as const,
      overage: 0,
    },
    review_state: "approved" as const,
    is_deleted: false,
    deleted_at: null,
    provenance: null,
    history: [
      {
        revision_number: 3,
        revision_digest: `${digest}basis`.padEnd(64, digest),
        review_state: "approved" as const,
        is_deleted: false,
        created_at: "2026-09-10T00:00:00Z",
        commit_hash: "a".repeat(40),
        execution_id: "execution",
      },
    ],
    history_has_more: false,
  });
  return {
    id: "group",
    product_id: "product",
    product_name: "Mobile",
    raw_key: "items",
    language: "ja",
    language_label: "Japanese",
    base_language: "en",
    base_maximum: 12,
    explicit_maximum: 12,
    constraint_version: 1,
    states: ["approved"],
    state_summary: "approved",
    is_deleted: false,
    pending_change: null,
    comment_count: 2,
    mutation_eligible: true,
    review_eligible: true,
    values: [value("one", "公開一", "b"), value("many", "公開多", "c")],
  };
}

function projection(
  local: TranslationGroupDetailResponse,
  texts: string[],
): TranslationProposalResponse {
  return {
    translation_group_id: local.id,
    language: local.language,
    version: 1,
    state: "draft",
    reconciliation_required: false,
    updated_by: "person",
    updated_at: "2026-09-10T01:00:00Z",
    published: local.values.map((value) => ({
      translation_value_id: value.id,
      selector_version: value.selector_version,
      selector_digest: value.selector_digest,
      text: value.translated_text,
      review_state: value.review_state,
      revision_number: value.history[0].revision_number,
      revision_digest: value.history[0].revision_digest,
    })),
    pending: local.values.map((value, index) => ({
      translation_value_id: value.id,
      selector_version: value.selector_version,
      selector_digest: value.selector_digest,
      text: texts[index],
      basis_revision_number: value.history[0].revision_number,
      basis_digest: value.history[0].revision_digest,
      grapheme_count: texts[index].length,
      maximum: 12,
      is_over_limit: false,
      approval_eligible: true,
      submission_eligible: true,
    })),
    activity: null,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("TranslationEditor", () => {
  it("shows split-source context without guessing unequal plural pairs and confirms saving only on success", async () => {
    const source = detail();
    source.values[0].source_resolution = "matched";
    source.values[0].source_value_id = "base-one";
    source.values[1].source_text = null;
    source.values[1].source_resolution = "unmatched";
    source.source_context = [
      {
        source_value_id: "base-one",
        origin: "base_language",
        language: "en",
        selector_kind: "android_quantity",
        selector_fields: [{ name: "quantity", value: "one" }],
        source_text: "One item",
        provenance: null,
        source_comparison: null,
      },
    ];
    const onSaved = vi.fn();
    render(
      <TranslationEditor
        accessToken="token"
        draft={createActiveTranslationDraft(source, "person")}
        onDraftChange={vi.fn()}
        onSaved={onSaved}
        onStop={vi.fn()}
        bilingual
      />,
    );
    expect(screen.getByText("No matching source variant")).toBeVisible();
    expect(
      screen.getByRole("region", { name: "Source variants (en)" }),
    ).toHaveTextContent("One item");
    vi.mocked(saveTranslationProposal)
      .mockRejectedValueOnce(new Error("unavailable"))
      .mockResolvedValueOnce({
        data: projection(source, ["公開一", "公開多"]),
      } as never);
    await userEvent.click(
      screen.getByRole("button", { name: "Save translation" }),
    );
    expect(await screen.findByText("Translation was not saved")).toBeVisible();
    expect(onSaved).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Save translation" }),
    );
    await waitFor(() =>
      expect(onSaved).toHaveBeenCalledWith(expect.anything()),
    );
  });
  it("keeps complete structured and empty pending text separate from published authority", async () => {
    const source = detail();
    const draft = createActiveTranslationDraft(source, "person");
    draft.values[0].text = "編集中\n完全";
    draft.values[1].text = "";
    render(
      <TranslationEditor
        accessToken="token"
        draft={draft}
        onDraftChange={vi.fn()}
        onSaved={vi.fn()}
        onStop={vi.fn()}
      />,
    );
    const published = screen.getByRole("region", {
      name: "Published translation",
    });
    expect(within(published).getByText("公開一")).toBeVisible();
    expect(within(published).getByText("公開多")).toBeVisible();
    expect(screen.getByRole("textbox", { name: /quantity one/i })).toHaveValue(
      "編集中\n完全",
    );
    expect(screen.getByRole("textbox", { name: /quantity many/i })).toHaveValue(
      "",
    );
    expect(screen.getByText("Empty pending translation")).toBeVisible();
    expect(screen.getAllByText(/Actual:/)).toHaveLength(2);
  });

  it("saves the complete group once, preserves text on failure, and returns focus after success", async () => {
    const user = userEvent.setup();
    const source = detail();
    const draft = createActiveTranslationDraft(source, "person");
    const changed = {
      ...draft,
      values: draft.values.map((value, index) => ({
        ...value,
        text: index ? "" : "私の完全な値",
      })),
    };
    const onDraftChange = vi.fn();
    const onSaved = vi.fn();
    const trigger = document.createElement("button");
    document.body.append(trigger);
    let rejectFirst!: (reason: Error) => void;
    vi.mocked(saveTranslationProposal)
      .mockImplementationOnce(
        () =>
          new Promise((_, reject) => {
            rejectFirst = reject;
          }) as never,
      )
      .mockResolvedValueOnce({
        data: projection(source, ["私の完全な値", ""]),
        error: undefined,
      } as never);
    const view = render(
      <TranslationEditor
        accessToken="token"
        draft={changed}
        onDraftChange={onDraftChange}
        onSaved={onSaved}
        onStop={vi.fn()}
        returnFocusTo={trigger}
      />,
    );
    const save = screen.getByRole("button", { name: "Save translation" });
    await user.click(save);
    await user.click(save);
    expect(saveTranslationProposal).toHaveBeenCalledTimes(1);
    rejectFirst(new Error("private failure"));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveFocus();
    expect(alert).toHaveTextContent("Translation was not saved");
    expect(screen.getByRole("textbox", { name: /quantity one/i })).toHaveValue(
      "私の完全な値",
    );
    await user.click(save);
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    expect(trigger).toHaveFocus();
    expect(saveTranslationProposal).toHaveBeenLastCalledWith(
      expect.objectContaining({
        auth: "token",
        path: { translation_group_id: "group" },
        body: expect.objectContaining({
          expected_version: 0,
          values: expect.arrayContaining([
            expect.objectContaining({
              translation_value_id: "one",
              proposed_text: "私の完全な値",
            }),
            expect.objectContaining({
              translation_value_id: "many",
              proposed_text: "",
            }),
          ]),
        }),
      }),
    );
    view.unmount();
    trigger.remove();
  });
});

describe("TranslationConflictDialog", () => {
  it("rebases local edits on the current imported revision instead of the stale proposal basis", async () => {
    const source = detail();
    const draft = createActiveTranslationDraft(source, "person");
    draft.values[0].text = "My preserved edit";
    const latest = projection(source, ["Old saved draft", "Old plural draft"]);
    latest.reconciliation_required = true;
    latest.published[0] = {
      ...latest.published[0],
      text: "New repository translation",
      revision_number: 7,
      revision_digest: "f".repeat(64),
    };
    const onReconcile = vi.fn();
    render(
      <TranslationConflictDialog
        open
        draft={draft}
        latest={latest}
        onKeepEditing={vi.fn()}
        onReconcile={onReconcile}
      />,
    );
    expect(screen.getByText("New repository translation")).toBeVisible();
    expect(onReconcile).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Reconcile with latest" }),
    );
    const reconciled = onReconcile.mock.calls[0][0] as ActiveTranslationDraft;
    expect(reconciled.values[0]).toMatchObject({
      text: "My preserved edit",
      publishedText: "New repository translation",
      basisRevisionNumber: 7,
      basisDigest: "f".repeat(64),
    });
    expect(draft.values[0].basisRevisionNumber).not.toBe(7);
    vi.mocked(saveTranslationProposal).mockResolvedValue({
      data: {
        ...latest,
        reconciliation_required: false,
        version: latest.version + 1,
      },
    } as never);
    cleanup();
    render(
      <TranslationEditor
        accessToken="token"
        draft={reconciled}
        onDraftChange={vi.fn()}
        onSaved={vi.fn()}
        onStop={vi.fn()}
        compact
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(saveTranslationProposal).toHaveBeenCalledWith(
      expect.objectContaining({
        body: expect.objectContaining({
          expected_version: latest.version,
          values: expect.arrayContaining([
            expect.objectContaining({
              basis_revision_number: 7,
              basis_digest: "f".repeat(64),
              proposed_text: "My preserved edit",
            }),
          ]),
        }),
      }),
    );
  });
  it("compares every complete value and only reconciles the basis explicitly", async () => {
    const user = userEvent.setup();
    const source = detail();
    const draft = createActiveTranslationDraft(source, "person");
    draft.values[0].text = "私の\nunsaved value";
    const latest = projection(source, [
      "server latest one",
      "server latest many",
    ]);
    latest.version = 9;
    const onReconcile = vi.fn();
    render(
      <TranslationConflictDialog
        open
        draft={draft}
        latest={latest}
        onKeepEditing={vi.fn()}
        onReconcile={onReconcile}
      />,
    );
    expect(screen.getByRole("dialog")).toHaveClass("sm:max-w-4xl");
    expect(screen.getByText("Your unsaved version")).toBeVisible();
    expect(screen.getByText("Latest saved version")).toBeVisible();
    expect(
      screen.getByRole("region", { name: "Your unsaved version" }),
    ).toHaveTextContent("私の unsaved value");
    expect(screen.getByText("server latest many")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /overwrite|merge|save/i }),
    ).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Reconcile with latest" }),
    );
    expect(onReconcile).toHaveBeenCalledWith(
      expect.objectContaining({
        expectedVersion: 9,
        reconciliationRequired: true,
        values: expect.arrayContaining([
          expect.objectContaining({ text: "私の\nunsaved value" }),
        ]),
      }),
    );
  });
});

describe("compact cells", () => {
  it.each(["direct", "translations"] as const)(
    "initializes %s base leaves from actual source text and never fills empty Qt targets",
    (side) => {
      const source = detail();
      source.language = "en";
      source.values = [source.values[0]];
      source.values[0].selector_kind = "json_path";
      source.values[0].translated_text = null;
      source.values[0].source_text = "Real base value";
      source.values[0].display_text = "Real base value";
      source.values[0].provenance = {
        repository_id: "repo",
        repository_name: "Repo",
        repository_side: side,
        branch: "main",
        path: "en.json",
        format: "json",
        commit_hash: "a",
        execution_id: "e",
        line: null,
        column: null,
      };
      const draft = createActiveTranslationDraft(source, "person");
      expect(draft.values[0].text).toBe("Real base value");
      expect(draft.values[0].publishedText).toBe("Real base value");
      expect(writableTranslationDetail(source, "source_text")).toBe(true);
      source.values[0].provenance.repository_side = "keys";
      expect(writableTranslationDetail(source, "source_text")).toBe(false);
      source.values[0].provenance.repository_side = side;
      source.language = "it";
      source.values[0].provenance.format = "qt_ts";
      expect(
        createActiveTranslationDraft(source, "person").values[0].text,
      ).toBe("");
    },
  );
  it("keeps all member fields inside the cell with Save and Cancel and no duplicated source columns", async () => {
    const onStop = vi.fn();
    render(
      <TranslationEditor
        accessToken="token"
        draft={createActiveTranslationDraft(detail(), "person")}
        onDraftChange={vi.fn()}
        onSaved={vi.fn()}
        onStop={onStop}
        compact
      />,
    );
    expect(screen.getAllByRole("textbox")).toHaveLength(2);
    expect(
      screen.queryByRole("region", { name: "Published translation" }),
    ).toBeNull();
    expect(
      screen.queryByRole("heading", { name: "Pending proposal" }),
    ).toBeNull();
    expect(screen.getByRole("button", { name: "Save" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onStop).toHaveBeenCalledOnce();
    expect(saveTranslationProposal).not.toHaveBeenCalled();
  });
});

it("accepts refreshed current locators when unchanged text retains an older revision basis", () => {
  const source = detail();
  for (const value of source.values)
    value.provenance = {
      repository_id: "repo",
      repository_name: "Repo",
      repository_side: "translations",
      branch: "main",
      path: "fr.xml",
      format: "android_xml",
      commit_hash: "new-unchanged-import",
      execution_id: "new-import",
      line: null,
      column: null,
    };
  expect(writableTranslationDetail(source, "translated_text")).toBe(true);
  source.values[1].provenance!.repository_side = "keys";
  expect(writableTranslationDetail(source, "translated_text")).toBe(false);
});

it("keeps length violations red after blur and clears them when corrected", async () => {
  function Editor() {
    const [draft, setDraft] = useState(
      createActiveTranslationDraft(detail(), "person"),
    );
    return (
      <TranslationEditor
        accessToken="token"
        draft={draft}
        onDraftChange={setDraft}
        onSaved={vi.fn()}
        onStop={vi.fn()}
        compact
      />
    );
  }
  render(<Editor />);
  const field = screen.getByRole("textbox", { name: /quantity one/i });
  await userEvent.clear(field);
  await userEvent.type(field, "abcdefghijklmno");
  await userEvent.tab();
  expect(field).not.toHaveFocus();
  expect(field).toHaveAttribute("aria-invalid", "true");
  expect(field).toHaveClass("border-destructive", "bg-red-50");
  expect(field).toHaveAccessibleDescription(/Over limit by/);
  expect(screen.getByText(/Over limit by/)).toHaveClass("text-destructive");
  expect(screen.queryByRole("button", { name: "Save and next" })).toBeNull();
  await userEvent.clear(field);
  await userEvent.type(field, "ok");
  expect(field).toHaveAttribute("aria-invalid", "false");
  expect(field).not.toHaveClass("border-destructive", "bg-red-50");
  expect(screen.queryByText(/Over limit by/)).toBeNull();
});

it("does not inherit an imported violation when the pending proposal is within the limit", () => {
  const source = detail();
  source.values[0].constraint.overage = 10;
  const saved = projection(source, ["ok", "ok"]);
  source.pending_change = {
    version: saved.version,
    state: saved.state,
    reconciliation_required: false,
    updated_at: saved.updated_at,
    updated_by: saved.updated_by,
    values: saved.pending,
  };
  expect(createActiveTranslationDraft(source, "person").values[0].overage).toBe(
    0,
  );
});
