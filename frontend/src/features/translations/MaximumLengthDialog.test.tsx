import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import {
  getTranslationGroup,
  putTranslationConstraint,
  deleteTranslationConstraint,
  type TranslationGroupDetailResponse,
  type TranslationConstraintMutationResponse,
  type RoleName,
} from "../../api/client";
import { MaximumLengthDialog } from "./MaximumLengthDialog";

vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));
vi.mock("../../api/client", () => ({
  getTranslationGroup: vi.fn(),
  putTranslationConstraint: vi.fn(),
  deleteTranslationConstraint: vi.fn(),
}));
function fixture(): TranslationGroupDetailResponse {
  return {
    id: "group",
    product_id: "product",
    product_name: "Product",
    raw_key: "key",
    language: "it",
    language_label: "Italian",
    base_language: "en",
    base_maximum: 8,
    explicit_maximum: 5,
    constraint_version: 2,
    states: ["draft"],
    state_summary: "draft",
    is_deleted: false,
    pending_change: null,
    comment_count: 0,
    mutation_eligible: true,
    review_eligible: true,
    values: [
      {
        id: "value",
        selector_kind: "scalar",
        selector_version: 1,
        selector_digest: "a".repeat(64),
        selector_fields: [],
        source_text: "Source",
        translated_text: "Target",
        display_text: "Target",
        structure: [],
        grapheme_count: 6,
        review_state: "draft",
        is_deleted: false,
        deleted_at: null,
        provenance: null,
        history: [],
        history_has_more: false,
        constraint: {
          actual: 6,
          maximum: 5,
          source: "language_override",
          status: "over_limit",
          overage: 1,
        },
      },
    ],
  };
}
function mutation(): TranslationConstraintMutationResponse {
  return {
    translation_group_id: "group",
    language: "it",
    base_language: "en",
    explicit_maximum: 9,
    version: 3,
    violating_count: 0,
    total_count: 1,
    values: [
      {
        id: "value",
        language: "it",
        constraint: {
          actual: 6,
          maximum: 9,
          source: "language_override",
          status: "within_limit",
          overage: 0,
        },
        approval_eligible: true,
        submission_eligible: true,
      },
    ],
  };
}
function fresh() {
  const data = fixture();
  data.explicit_maximum = 9;
  data.constraint_version = 3;
  data.values[0].constraint = mutation().values[0].constraint;
  return data;
}
const success = <T,>(data: T) => ({ data, error: undefined });
const failure = (status: number) => ({
  data: undefined,
  error: { detail: "Translation constraint conflict" as const },
  response: new Response(null, { status }),
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((r, j) => {
    resolve = r;
    reject = j;
  });
  return { promise, resolve, reject };
}
function props() {
  return {
    accessToken: "token",
    detail: fixture(),
    roles: ["admin"] as RoleName[],
    mode: "edit" as const,
    onClose: vi.fn(),
    onChanged: vi.fn(),
    triggerElement: null as HTMLButtonElement | null,
  };
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(putTranslationConstraint).mockResolvedValue(success(mutation()));
  vi.mocked(deleteTranslationConstraint).mockResolvedValue(
    success({ ...mutation(), explicit_maximum: null, version: null }),
  );
  vi.mocked(getTranslationGroup).mockResolvedValue(success(fresh()));
});
afterEach(() => cleanup());

describe("Maximum length — CONS-01..05 pending/conflict/input authority", () => {
  it.each(["mutation", "detail"])(
    "rejects a foreign %s projection without retrying a durable write",
    async (projection) => {
      if (projection === "mutation")
        vi.mocked(putTranslationConstraint).mockResolvedValue(
          success({ ...mutation(), language: "fr" }),
        );
      else
        vi.mocked(getTranslationGroup).mockResolvedValue(
          success({ ...fresh(), language: "fr" }),
        );
      const p = props();
      render(<MaximumLengthDialog {...p} />);
      await userEvent.click(
        screen.getByRole("button", { name: "Save max length" }),
      );
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Maximum length saved; current details could not be loaded",
      );
      expect(p.onChanged).not.toHaveBeenCalled();
      expect(
        screen.getByRole("button", { name: "Save max length" }),
      ).toBeDisabled();
      expect(putTranslationConstraint).toHaveBeenCalledOnce();
    },
  );
  it("dismisses conflict replacement confirmation without discarding entered input", async () => {
    vi.mocked(putTranslationConstraint).mockResolvedValue(failure(409));
    render(<MaximumLengthDialog {...props()} />);
    fireEvent.change(screen.getByRole("spinbutton"), {
      target: { value: "27" },
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Save max length" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Reload current value" }),
    );
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(screen.getByRole("spinbutton")).toHaveValue(27);
    expect(getTranslationGroup).not.toHaveBeenCalled();
  });
  it.each([0, 1048576])(
    "accepts inclusive integer %s with exact expected version",
    async (value) => {
      const p = props();
      render(<MaximumLengthDialog {...p} />);
      const input = screen.getByRole("spinbutton", {
        name: "Maximum characters",
      });
      fireEvent.change(input, { target: { value: String(value) } });
      await userEvent.click(
        screen.getByRole("button", { name: "Save max length" }),
      );
      await waitFor(() => expect(p.onChanged).toHaveBeenCalledWith(fresh()));
      expect(putTranslationConstraint).toHaveBeenCalledWith(
        expect.objectContaining({
          body: { max_chars: value, expected_version: 2 },
          path: { translation_group_id: "group", language: "it" },
          auth: "token",
          signal: expect.any(AbortSignal),
        }),
      );
      expect(toast.success).toHaveBeenCalledWith("Maximum length saved");
      expect(p.onClose).toHaveBeenCalledTimes(1);
    },
  );
  it.each(["", "1.5", "-1", "1048577"])(
    "rejects %s and focuses the field",
    async (value) => {
      render(<MaximumLengthDialog {...props()} />);
      const input = screen.getByRole("spinbutton");
      fireEvent.change(input, { target: { value } });
      await userEvent.click(
        screen.getByRole("button", { name: "Save max length" }),
      );
      expect(input).toHaveAttribute("aria-invalid", "true");
      expect(input).toHaveFocus();
      expect(putTranslationConstraint).not.toHaveBeenCalled();
    },
  );
  it.each<RoleName>(["viewer", "translator"])(
    "provides no mutation path for %s",
    (role) => {
      render(<MaximumLengthDialog {...props()} roles={[role]} />);
      expect(screen.queryByRole("dialog")).toBeNull();
      expect(screen.queryByRole("button")).toBeNull();
    },
  );
  it.each<RoleName>(["admin", "product_manager_reviewer"])(
    "supports the authorized role %s",
    (role) => {
      render(<MaximumLengthDialog {...props()} roles={[role]} />);
      expect(screen.getByRole("dialog")).toBeVisible();
    },
  );
  it.each(["save", "remove"] as const)(
    "synchronously suppresses duplicate %s and prevents pending dismissal",
    async (action) => {
      const pending =
        deferred<Awaited<ReturnType<typeof putTranslationConstraint<false>>>>();
      if (action === "save")
        vi.mocked(putTranslationConstraint).mockReturnValue(pending.promise);
      else
        vi.mocked(deleteTranslationConstraint).mockReturnValue(pending.promise);
      const p = props();
      render(
        <MaximumLengthDialog
          {...p}
          mode={action === "remove" ? "remove" : "edit"}
        />,
      );
      const submit = screen.getByRole("button", {
        name:
          action === "save" ? "Save max length" : "Remove language override",
      });
      const cancel = screen.getByRole("button", {
        name:
          action === "save"
            ? "Discard max length changes"
            : "Keep language override",
      });
      act(() => {
        fireEvent.click(submit);
        fireEvent.click(submit);
        if (action === "save") {
          fireEvent.submit(submit.closest("form")!);
          fireEvent.submit(submit.closest("form")!);
        }
      });
      expect(submit).toBeDisabled();
      expect(cancel).toBeDisabled();
      expect(submit).toHaveAttribute("aria-busy", "true");
      expect(cancel).not.toHaveAttribute("aria-busy", "true");
      await userEvent.keyboard("{Escape}");
      fireEvent.pointerDown(document.body);
      if (action === "save") {
        const overlay = document.querySelector('[data-slot="dialog-overlay"]')!;
        fireEvent.pointerDown(overlay, { button: 0 });
        fireEvent.click(overlay);
      }
      expect(p.onClose).not.toHaveBeenCalled();
      expect(
        action === "save"
          ? putTranslationConstraint
          : deleteTranslationConstraint,
      ).toHaveBeenCalledTimes(1);
      await act(async () => pending.resolve(failure(503)));
      expect(await screen.findByRole("alert")).toHaveFocus();
      expect(p.onChanged).not.toHaveBeenCalled();
    },
  );
  it.each([403, 503])(
    "preserves input on bounded %s failure",
    async (status) => {
      vi.mocked(putTranslationConstraint).mockResolvedValue(failure(status));
      render(<MaximumLengthDialog {...props()} />);
      const input = screen.getByRole("spinbutton");
      fireEvent.change(input, { target: { value: "17" } });
      await userEvent.click(
        screen.getByRole("button", { name: "Save max length" }),
      );
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Maximum length was not saved",
      );
      expect(screen.getByRole("alert")).toHaveFocus();
      expect(input).toHaveValue(17);
      expect(screen.queryByText("Translation constraint conflict")).toBeNull();
    },
  );
  it("maps 422 validation to input focus without replacing user input", async () => {
    vi.mocked(putTranslationConstraint).mockResolvedValue(failure(422));
    render(<MaximumLengthDialog {...props()} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Save max length" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("spinbutton")).toHaveAttribute(
        "aria-invalid",
        "true",
      ),
    );
    expect(screen.getByRole("spinbutton")).toHaveFocus();
  });
  it("preserves conflict input until separate replacement confirmation and never auto-retries", async () => {
    const p = props();
    vi.mocked(putTranslationConstraint).mockResolvedValueOnce(failure(409));
    render(<MaximumLengthDialog {...p} />);
    const input = screen.getByRole("spinbutton");
    fireEvent.change(input, { target: { value: "17" } });
    await userEvent.click(
      screen.getByRole("button", { name: "Save max length" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Maximum length changed",
    );
    expect(input).toHaveValue(17);
    expect(
      screen.getByRole("button", { name: "Save max length" }),
    ).toBeDisabled();
    await userEvent.click(
      screen.getByRole("button", { name: "Reload current value" }),
    );
    expect(
      screen.getByRole("alertdialog", { name: "Replace your entered value?" }),
    ).toBeVisible();
    expect(getTranslationGroup).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Keep entered value" }),
    );
    expect(input).toHaveValue(17);
    await userEvent.click(
      screen.getByRole("button", { name: "Reload current value" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Replace entered value" }),
    );
    await waitFor(() => expect(input).toHaveValue(9));
    expect(putTranslationConstraint).toHaveBeenCalledTimes(1);
    expect(p.onClose).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Save max length" }),
    );
    await waitFor(() => expect(p.onChanged).toHaveBeenCalled());
    expect(
      vi.mocked(putTranslationConstraint).mock.calls[1][0].body
        ?.expected_version,
    ).toBe(3);
  });
  it.each(["resolve", "reject"])(
    "silences late %s after unmount and aborts",
    async (finish) => {
      const pending =
        deferred<Awaited<ReturnType<typeof putTranslationConstraint<false>>>>();
      vi.mocked(putTranslationConstraint).mockReturnValue(pending.promise);
      const p = props();
      const view = render(<MaximumLengthDialog {...p} />);
      await userEvent.click(
        screen.getByRole("button", { name: "Save max length" }),
      );
      const signal = vi.mocked(putTranslationConstraint).mock.calls[0][0]
        .signal;
      view.unmount();
      expect(signal?.aborted).toBe(true);
      await act(async () => {
        if (finish === "resolve") pending.resolve(success(mutation()));
        else pending.reject(new Error("private"));
      });
      expect(p.onChanged).not.toHaveBeenCalled();
      expect(p.onClose).not.toHaveBeenCalled();
      expect(toast.success).not.toHaveBeenCalled();
      expect(getTranslationGroup).not.toHaveBeenCalled();
    },
  );
  it.each(["token", "group", "version"])(
    "silences superseded %s success and failure",
    async (authority) => {
      const pending =
        deferred<Awaited<ReturnType<typeof putTranslationConstraint<false>>>>();
      vi.mocked(putTranslationConstraint).mockReturnValue(pending.promise);
      const p = props();
      const view = render(<MaximumLengthDialog {...p} />);
      await userEvent.click(
        screen.getByRole("button", { name: "Save max length" }),
      );
      view.rerender(
        <MaximumLengthDialog
          {...p}
          accessToken={authority === "token" ? "new-token" : "token"}
          detail={{
            ...p.detail,
            id: authority === "group" ? "new-group" : "group",
            constraint_version: authority === "version" ? 3 : 2,
          }}
        />,
      );
      await act(async () => pending.resolve(success(mutation())));
      expect(p.onChanged).not.toHaveBeenCalled();
      expect(p.onClose).not.toHaveBeenCalled();
      expect(toast.success).not.toHaveBeenCalled();
    },
  );
  it("silences a late detail refresh after authority is superseded", async () => {
    const pending =
      deferred<Awaited<ReturnType<typeof getTranslationGroup<false>>>>();
    vi.mocked(getTranslationGroup).mockReturnValue(pending.promise);
    const p = props();
    const view = render(<MaximumLengthDialog {...p} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Save max length" }),
    );
    await waitFor(() => expect(getTranslationGroup).toHaveBeenCalled());
    view.rerender(<MaximumLengthDialog {...p} accessToken="new-token" />);
    await act(async () => pending.resolve(success(fresh())));
    expect(p.onChanged).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  });
  it("never resubmits a committed mutation when its projection refresh fails", async () => {
    vi.mocked(getTranslationGroup).mockRejectedValueOnce(new Error("network"));
    const p = props();
    render(<MaximumLengthDialog {...p} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Save max length" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Maximum length saved; current details could not be loaded",
    );
    expect(
      screen.getByRole("button", { name: "Save max length" }),
    ).toBeDisabled();
    await userEvent.click(
      screen.getByRole("button", { name: "Reload current value" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Replace entered value" }),
    );
    await waitFor(() => expect(p.onClose).toHaveBeenCalledTimes(1));
    expect(putTranslationConstraint).toHaveBeenCalledTimes(1);
  });
  it.each([true, false])(
    "explains base removal and override independence (base=%s)",
    (isBase) => {
      const p = props();
      if (isBase) p.detail.language = "en";
      else p.detail.base_maximum = null;
      render(<MaximumLengthDialog {...p} mode="remove" />);
      expect(screen.getByRole("alertdialog")).toHaveTextContent(
        isBase
          ? "Languages without their own override will have no maximum length. Existing language overrides will remain."
          : "This language will have no maximum length.",
      );
    },
  );
  it("explains override fallback and removes non-optimistically with version authority", async () => {
    const p = props();
    render(<MaximumLengthDialog {...p} mode="remove" />);
    expect(screen.getByRole("alertdialog")).toHaveTextContent(
      "This language will inherit the current en maximum of 8 characters.",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Remove language override" }),
    );
    await waitFor(() => expect(p.onChanged).toHaveBeenCalled());
    expect(deleteTranslationConstraint).toHaveBeenCalledWith(
      expect.objectContaining({ body: { expected_version: 2 } }),
    );
    expect(toast.success).toHaveBeenCalledWith("Maximum length removed");
  });
  it("restores the connected invoking action only after explicit close", async () => {
    const p = props();
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();
    p.triggerElement = trigger;
    const view = render(<MaximumLengthDialog {...p} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Discard max length changes" }),
    );
    view.unmount();
    await waitFor(() => expect(trigger).toHaveFocus());
    trigger.remove();
  });
});
