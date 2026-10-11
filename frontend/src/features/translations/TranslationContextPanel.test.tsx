import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getTranslationGroup,
  type TranslationGroupDetailResponse,
  type TranslationProposalResponse,
  type TranslationSourceContextResponse,
} from "../../api/client";
import { TranslationContextPanel } from "./TranslationContextPanel";
import { completeTranslationDetail } from "./translationDetailAuthority";
const mounts = vi.hoisted(() => vi.fn());
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  getTranslationGroup: vi.fn(),
}));
vi.mock("./Discussion", () => ({
  Discussion: (props: {
    translationGroupId: string;
    principal: { id: string };
  }) => {
    mounts(props);
    return (
      <div>
        Discussion {props.translationGroupId} for {props.principal.id}
        <input aria-label="Unsent comment" />
      </div>
    );
  },
}));
vi.mock("./ActivityHistory", () => ({
  ActivityHistory: () => <p>Recorded activity</p>,
}));
const source: TranslationSourceContextResponse = {
  source_value_id: "base",
  origin: "base_language",
  language: "en",
  selector_kind: "android_quantity",
  selector_fields: [{ name: "quantity", value: "other" }],
  source_text: "New <script>",
  provenance: null,
  source_comparison: {
    source_value_id: "base",
    origin: "base_language",
    previous_revision_number: 2,
    current_revision_number: 3,
    previous_commit_hash: "a".repeat(40),
    current_commit_hash: "b".repeat(40),
    previous_execution_id: "previous",
    current_execution_id: "current",
    previous_text: "Old <script>",
    current_text: "New <script>",
    previous_truncated: false,
    current_truncated: true,
    changed: true,
  },
};
const detail = {
  id: "group",
  product_id: "product",
  raw_key: "key",
  language: "fr",
  base_language: "en",
  values: [
    {
      id: "target",
      selector_version: 1,
      selector_digest: "a".repeat(64),
      selector_kind: "scalar",
      selector_fields: [],
      source_text: "Source",
      translated_text: "Target",
      display_text: "Target",
      structure: [],
      review_state: "draft",
      grapheme_count: 6,
      is_deleted: false,
      deleted_at: null,
      history: [],
      history_has_more: false,
      provenance: null,
      constraint: {
        actual: 6,
        maximum: null,
        source: "none",
        status: "no_max",
        overage: null,
      },
    },
  ],
  comment_count: 0,
  mutation_eligible: true,
  review_eligible: true,
  states: ["draft"],
  state_summary: "draft",
  explicit_maximum: null,
  constraint_version: null,
  pending_change: null,
  source_context: [source],
} as unknown as TranslationGroupDetailResponse;
const props = () => ({
  detail,
  accessToken: "token",
  principal: { id: "one", roles: ["translator" as const] },
  dirty: false,
  onReviewed: vi.fn(),
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
describe("selected translation context", () => {
  it("refreshes server eligibility after a reviewer's first inline save without reopening", async () => {
    const current = {
      ...props(),
      principal: {
        id: "reviewer",
        roles: ["product_manager_reviewer" as const],
      },
      detail: { ...detail, review_eligible: false },
    };
    const view = render(<TranslationContextPanel {...current} />);
    expect(
      screen.queryByRole("button", { name: "Approve translation" }),
    ).not.toBeInTheDocument();
    const pending = {
      translation_value_id: "target",
      selector_version: 1 as const,
      selector_digest: "a".repeat(64),
      basis_revision_number: 1,
      basis_digest: "b".repeat(64),
      text: "First saved target",
      grapheme_count: 18,
      maximum: null,
      is_over_limit: false,
      approval_eligible: true,
      submission_eligible: true,
    };
    const proposal: TranslationProposalResponse = {
      translation_group_id: "group",
      language: "fr",
      version: 1,
      state: "draft",
      reconciliation_required: false,
      updated_at: "2026-10-01T00:00:00Z",
      updated_by: "reviewer",
      activity: null,
      pending: [pending],
      published: [
        {
          translation_value_id: "target",
          selector_version: 1,
          selector_digest: pending.selector_digest,
          text: "Target",
          review_state: "draft",
          revision_number: 1,
          revision_digest: pending.basis_digest,
        },
      ],
    };
    // SearchPage merges only the saved proposal into the pre-save detail.
    const synthetic = {
      ...current.detail,
      pending_change: {
        version: proposal.version,
        state: proposal.state,
        reconciliation_required: proposal.reconciliation_required,
        updated_at: proposal.updated_at,
        updated_by: proposal.updated_by,
        values: proposal.pending,
      },
    };
    const serverDetail = { ...synthetic, review_eligible: true };
    expect(completeTranslationDetail(serverDetail, "group")).toBe(true);
    vi.mocked(getTranslationGroup).mockResolvedValue({
      data: serverDetail,
    } as never);
    view.rerender(
      <TranslationContextPanel
        {...current}
        detail={synthetic}
        proposal={proposal}
      />,
    );
    expect(
      await screen.findByRole("button", { name: "Approve translation" }),
    ).toBeEnabled();
    expect(getTranslationGroup).toHaveBeenCalledOnce();
    expect(getTranslationGroup).toHaveBeenCalledWith(
      expect.objectContaining({
        path: { translation_group_id: "group" },
        auth: "token",
      }),
    );
  });
  it("adopts a same-group detail reload after an external save without resetting discussion", async () => {
    const current = props();
    const view = render(<TranslationContextPanel {...current} />);
    await userEvent.type(screen.getByRole("textbox"), "Keep this comment");
    const fresh = {
      ...detail,
      pending_change: { version: 1, state: "draft" },
    } as TranslationGroupDetailResponse;
    expect(completeTranslationDetail(fresh, "group")).toBe(true);
    view.rerender(<TranslationContextPanel {...current} detail={fresh} />);
    expect(screen.getByText("Pending: draft · Version 1")).toBeVisible();
    expect(
      screen.queryByText("Refreshing saved proposal…"),
    ).not.toBeInTheDocument();
    view.rerender(
      <TranslationContextPanel {...current} detail={fresh} dirty />,
    );
    expect(screen.getByRole("textbox")).toHaveValue("Keep this comment");
    expect(getTranslationGroup).not.toHaveBeenCalled();
  });
  it("adopts a source-only detail update at the same proposal version", async () => {
    const current = props();
    const view = render(<TranslationContextPanel {...current} />);
    await userEvent.click(screen.getByRole("tab", { name: "Source changes" }));
    const fresh = {
      ...detail,
      source_context: [
        {
          ...source,
          source_text: "New import",
          source_comparison: {
            ...source.source_comparison!,
            current_text: "New import",
            current_revision_number: 4,
          },
        },
      ],
    };
    expect(completeTranslationDetail(fresh, "group")).toBe(true);
    view.rerender(<TranslationContextPanel {...current} detail={fresh} />);
    expect(screen.getByText("New import")).toBeVisible();
    expect(screen.queryByText("New <script>")).not.toBeInTheDocument();
    expect(getTranslationGroup).not.toHaveBeenCalled();
  });
  it("cancels an older proposal refetch when a fresh detail supplies that proposal", async () => {
    let resolve!: (value: unknown) => void;
    vi.mocked(getTranslationGroup).mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }) as never,
    );
    const current = props();
    const proposal = { version: 1 } as TranslationProposalResponse;
    const saved = {
      ...detail,
      pending_change: { version: 1, state: "draft" },
    } as TranslationGroupDetailResponse;
    expect(completeTranslationDetail(saved, "group")).toBe(true);
    const view = render(
      <TranslationContextPanel
        {...current}
        detail={detail}
        proposal={proposal}
      />,
    );
    const signal = vi.mocked(getTranslationGroup).mock.lastCall?.[0]?.signal;
    const resolveSuperseded = resolve;
    const comparison = {
      ...source.source_comparison!,
      current_text: "Fresh source",
      current_revision_number: 4,
    };
    const fresh = {
      ...saved,
      source_context: [
        {
          ...source,
          source_text: "Fresh source",
          source_comparison: comparison,
        },
      ],
    };
    view.rerender(
      <TranslationContextPanel
        {...current}
        detail={fresh}
        proposal={proposal}
      />,
    );
    expect(signal?.aborted).toBe(true);
    await userEvent.click(screen.getByRole("tab", { name: "Source changes" }));
    expect(screen.getByText("Fresh source")).toBeVisible();
    await act(async () => resolveSuperseded({ data: saved }));
    expect(screen.getByText("Fresh source")).toBeVisible();
    expect(screen.queryByText("New <script>")).not.toBeInTheDocument();
  });
  it("shows actual base-source revisions and truncation without HTML execution or last-edit claims", async () => {
    render(<TranslationContextPanel {...props()} />);
    await userEvent.click(screen.getByRole("tab", { name: "Source changes" }));
    expect(
      screen.getByText("Previous imported source · Revision 2"),
    ).toBeVisible();
    expect(
      screen.getByText("Current imported source · Revision 3"),
    ).toBeVisible();
    expect(screen.getByText("New <script>")).toBeVisible();
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getByText(/Excerpt truncated/)).toBeVisible();
    expect(screen.getByText(/Latest two source imports/)).toBeVisible();
  });
  it("changes discussion ownership with group and principal and explains unavailable comparisons", async () => {
    const current = props();
    const view = render(<TranslationContextPanel {...current} />);
    expect(screen.getByText("Discussion group for one")).toBeVisible();
    view.rerender(
      <TranslationContextPanel
        {...current}
        principal={{ id: "two", roles: ["viewer"] }}
        detail={{
          ...detail,
          id: "other",
          source_context: [{ ...source, source_comparison: null }],
        }}
      />,
    );
    expect(screen.getByText("Discussion other for two")).toBeVisible();
    expect(
      screen.queryByText("Discussion group for one"),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Source changes" }));
    expect(
      screen.getByText("Two source revisions are needed to compare changes."),
    ).toBeVisible();
  });
  it("rejects oversized or cross-source comparisons before using a detail projection", () => {
    const member: TranslationGroupDetailResponse["values"][number] = {
      id: "target",
      selector_version: 1,
      selector_digest: "a".repeat(64),
      deleted_at: null,
      is_deleted: false,
      history: [],
      history_has_more: false,
      provenance: null,
      selector_kind: "scalar",
      selector_fields: [],
      source_text: "Source",
      translated_text: "Target",
      display_text: "Target",
      structure: [],
      review_state: "draft",
      grapheme_count: 6,
      constraint: {
        actual: 6,
        maximum: null,
        source: "none",
        status: "no_max",
        overage: null,
      },
    };
    const valid = {
      ...detail,
      comment_count: 0,
      mutation_eligible: true,
      review_eligible: true,
      states: ["draft"],
      state_summary: "draft",
      explicit_maximum: null,
      constraint_version: null,
      values: [member],
    } as TranslationGroupDetailResponse;
    expect(completeTranslationDetail(valid, "group")).toBe(true);
    expect(
      completeTranslationDetail(
        {
          ...valid,
          source_context: [
            {
              ...source,
              source_comparison: {
                ...source.source_comparison!,
                source_value_id: "another",
              },
            },
          ],
        },
        "group",
      ),
    ).toBe(false);
    expect(
      completeTranslationDetail(
        {
          ...valid,
          source_context: [
            {
              ...source,
              source_comparison: {
                ...source.source_comparison!,
                current_text: "x".repeat(4097),
              },
            },
          ],
        },
        "group",
      ),
    ).toBe(false);
  });
});
