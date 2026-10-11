import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  transitionTranslationProposal,
  type TranslationGroupDetailResponse,
  type TranslationProposalResponse,
} from "../../api/client";
import { TranslationReviewActions } from "./TranslationReviewActions";

vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  transitionTranslationProposal: vi.fn(),
}));
const pending = {
  translation_value_id: "value",
  selector_version: 1 as const,
  selector_digest: "a".repeat(64),
  basis_revision_number: 1,
  basis_digest: "b".repeat(64),
  text: "Saved",
  grapheme_count: 5,
  maximum: null,
  is_over_limit: false,
  approval_eligible: true,
  submission_eligible: true,
};
const detail = {
  id: "group",
  product_id: "product",
  language: "fr",
  is_deleted: false,
  review_eligible: true,
  constraint_version: null,
  values: [
    {
      id: "value",
      selector_version: 1,
      selector_digest: pending.selector_digest,
      is_deleted: false,
    },
  ],
  pending_change: {
    version: 1,
    state: "draft",
    reconciliation_required: false,
    values: [pending],
  },
} as TranslationGroupDetailResponse;
const projection = (
  state: "draft" | "approved" | "rejected" = "approved",
): TranslationProposalResponse => ({
  translation_group_id: "group",
  language: "fr",
  version: 2,
  state,
  reconciliation_required: false,
  updated_at: "2026-10-01T00:00:00Z",
  updated_by: "reviewer",
  activity: null,
  pending: [pending],
  published: [
    {
      translation_value_id: "value",
      selector_version: 1,
      selector_digest: pending.selector_digest,
      text: "Old",
      review_state: "draft",
      revision_number: 1,
      revision_digest: pending.basis_digest,
    },
  ],
});
const props = () => ({
  accessToken: "token",
  principal: { id: "reviewer", roles: ["product_manager_reviewer" as const] },
  detail,
  dirty: false,
  onChanged: vi.fn(),
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("shared translation review", () => {
  it.each([false, true])(
    "reports actual length violations separately from stale source (over limit: %s)",
    (isOverLimit) => {
      render(
        <TranslationReviewActions
          {...props()}
          detail={{
            ...detail,
            review_eligible: false,
            pending_change: {
              ...detail.pending_change!,
              reconciliation_required: true,
              values: [
                {
                  ...pending,
                  approval_eligible: false,
                  is_over_limit: isOverLimit,
                },
              ],
            },
          }}
        />,
      );
      expect(screen.getByText("Reconciliation required")).toBeVisible();
      expect(
        screen.queryByRole("button", { name: "Approve translation" }),
      ).not.toBeInTheDocument();
      const lengthWarning = screen.queryByText(
        "Resolve every maximum-length violation before approval.",
      );
      if (isOverLimit) expect(lengthWarning).toBeVisible();
      else expect(lengthWarning).not.toBeInTheDocument();
      expect(transitionTranslationProposal).not.toHaveBeenCalled();
    },
  );
  it("blocks dirty text and submits the saved version only once", async () => {
    const current = props();
    const view = render(<TranslationReviewActions {...current} dirty />);
    expect(
      screen.getByRole("button", { name: "Approve translation" }),
    ).toBeDisabled();
    expect(
      screen.getByText("Save your changes before reviewing this proposal."),
    ).toBeVisible();
    view.rerender(<TranslationReviewActions {...current} />);
    vi.mocked(transitionTranslationProposal).mockResolvedValue({
      data: projection(),
    } as never);
    await userEvent.click(
      screen.getByRole("button", { name: "Approve translation" }),
    );
    await waitFor(() =>
      expect(current.onChanged).toHaveBeenCalledWith(projection()),
    );
    expect(transitionTranslationProposal).toHaveBeenCalledWith(
      expect.objectContaining({
        body: { expected_version: 1, target_state: "approved", reason: null },
      }),
    );
  });
  it.each(["translator", "viewer"] as const)(
    "keeps review controls absent for %s",
    (role) => {
      render(
        <TranslationReviewActions
          {...props()}
          principal={{ id: "user", roles: [role] }}
        />,
      );
      expect(
        screen.queryByRole("button", { name: "Approve translation" }),
      ).not.toBeInTheDocument();
    },
  );
  it.each(["wrong group", "duplicate member", "wrong state", "stale version"])(
    "rejects a %s success projection",
    async (failure) => {
      const current = props();
      const fresh = projection();
      if (failure === "wrong group") fresh.translation_group_id = "other";
      if (failure === "duplicate member") fresh.pending.push(fresh.pending[0]);
      if (failure === "wrong state") fresh.state = "draft";
      if (failure === "stale version") fresh.version = 1;
      vi.mocked(transitionTranslationProposal).mockResolvedValue({
        data: fresh,
      } as never);
      render(<TranslationReviewActions {...current} />);
      await userEvent.click(
        screen.getByRole("button", { name: "Approve translation" }),
      );
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Review action did not complete",
      );
      expect(current.onChanged).not.toHaveBeenCalled();
    },
  );
  it("aborts an old principal response and rejects unrelated conflict data", async () => {
    const current = props();
    let resolve!: (value: unknown) => void;
    vi.mocked(transitionTranslationProposal).mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }) as never,
    );
    const view = render(<TranslationReviewActions {...current} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Approve translation" }),
    );
    const signal = vi.mocked(transitionTranslationProposal).mock.lastCall?.[0]
      ?.signal;
    view.rerender(
      <TranslationReviewActions
        {...current}
        accessToken="new-token"
        principal={{ id: "another", roles: ["admin"] }}
      />,
    );
    expect(signal?.aborted).toBe(true);
    resolve({ data: projection() });
    await Promise.resolve();
    expect(current.onChanged).not.toHaveBeenCalled();
    vi.mocked(transitionTranslationProposal).mockResolvedValue({
      response: { status: 409 },
      error: { latest: { ...projection(), language: "de" } },
    } as never);
    await userEvent.click(
      screen.getByRole("button", { name: "Approve translation" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Review action did not complete",
    );
    expect(current.onChanged).not.toHaveBeenCalled();
  });
});
