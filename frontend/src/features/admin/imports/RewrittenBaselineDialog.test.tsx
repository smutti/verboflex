import "@testing-library/jest-dom/vitest";

import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  confirmAdminImportRewriteBaseline,
  getAdminImportRewriteComparison,
  type AdminImportRewriteComparisonResponse,
  type AdminPublishedMappingImportResponse,
  type AdminRepositoryResponse,
} from "../../../api/client";
import { RewrittenBaselineDialog } from "./RewrittenBaselineDialog";

class TestResizeObserver implements ResizeObserver {
  disconnect() {}
  observe() {}
  unobserve() {}
}

vi.stubGlobal("ResizeObserver", TestResizeObserver);

vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();
  return {
    ...original,
    confirmAdminImportRewriteBaseline: vi.fn(),
    getAdminImportRewriteComparison: vi.fn(),
  };
});

const comparisonMock = vi.mocked(getAdminImportRewriteComparison);
const confirmationMock = vi.mocked(confirmAdminImportRewriteBaseline);

const repositories: AdminRepositoryResponse[] = [
  {
    descriptive_name: "Application source",
    id: "repository-1",
    repository_slug: "mobile-app",
    workspace: "product-team",
  },
  {
    descriptive_name: "Translations source",
    id: "repository-2",
    repository_slug: "translations",
    workspace: "product-team",
  },
];

function ok<T>(data: T, status = 200) {
  return {
    data,
    error: undefined,
    request: new Request("http://localhost/api/v1/admin"),
    response: new Response(null, { status }),
  };
}

function failed(status: number) {
  return {
    data: undefined,
    error: { detail: "provider body must stay private" },
    request: new Request("http://localhost/api/v1/admin"),
    response: new Response(null, { status }),
  };
}

function importRecord(
  overrides: Partial<AdminPublishedMappingImportResponse> = {},
): AdminPublishedMappingImportResponse {
  return {
    action: "review_baseline_change",
    active_baseline: null,
    active_revision_id: "revision-1",
    capability: "ready",
    error_category: null,
    error_message: null,
    execution_number: 2,
    id: "import-1",
    latest_execution_at: "2026-09-03T12:00:00Z",
    mapping_id: "mapping-1",
    repository_sides: [
      {
        repository_id: "repository-1",
        role: "direct",
        source_branch: "release/opaque-branch",
      },
    ],
    retry_count: 0,
    state: "review_required",
    topology: "direct",
    ...overrides,
  };
}

function comparison(
  overrides: Partial<AdminImportRewriteComparisonResponse> = {},
): AdminImportRewriteComparisonResponse {
  return {
    confirmable: true,
    files: [],
    import_id: "import-1",
    mapping_id: "mapping-1",
    proposal_digest: "f".repeat(64),
    proposal_id: "proposal-1",
    proposed_execution_id: "execution-2",
    sides: [
      {
        added_count: 0,
        modified_count: 0,
        new_commit_hash: "b".repeat(40),
        old_commit_hash: "a".repeat(40),
        removed_count: 0,
        repository_id: "repository-1",
        repository_side: "direct",
      },
    ],
    topology: "direct",
    ...overrides,
  };
}

function renderDialog(
  props: Partial<React.ComponentProps<typeof RewrittenBaselineDialog>> = {},
) {
  return render(
    <RewrittenBaselineDialog
      accessToken="memory-only-admin-bearer"
      importRecord={importRecord()}
      onClose={vi.fn()}
      onConfirmed={vi.fn().mockResolvedValue(true)}
      open
      productId="product-1"
      repositories={repositories}
      triggerElement={null}
      {...props}
    />,
  );
}

describe("rewritten baseline reconciliation", () => {
  beforeEach(() => {
    comparisonMock.mockReset();
    confirmationMock.mockReset();
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  afterEach(() => cleanup());

  it("UI3-C08 names reconciliation loading and preserves bounded skeleton geometry", () => {
    comparisonMock.mockReturnValueOnce(new Promise(() => undefined) as never);
    renderDialog();

    const dialog = screen.getByRole("alertdialog", {
      name: "Review rewritten source history",
    });
    expect(within(dialog).getByRole("status")).toHaveTextContent(
      "Loading baseline comparison",
    );
    expect(
      within(dialog).getByTestId("rewrite-comparison-skeleton"),
    ).toHaveClass("h-32");
  });

  it("UI3-C04 keeps a complete zero-delta rewrite confirmable", async () => {
    comparisonMock.mockResolvedValueOnce(ok(comparison()));
    renderDialog();

    expect(
      await screen.findByText("No localization file changes detected"),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Confirm new baseline" }),
    ).toBeEnabled();
  });

  it("UI3-C15 renders exact opaque commit pairs and copies only on request", async () => {
    const oldCommit = "1".repeat(40);
    const newCommit = "2".repeat(40);
    comparisonMock.mockResolvedValueOnce(
      ok(
        comparison({
          sides: [
            {
              ...comparison().sides[0],
              old_commit_hash: oldCommit,
              new_commit_hash: newCommit,
            },
          ],
        }),
      ),
    );
    renderDialog();

    const source = await screen.findByRole("region", {
      name: "Source baseline comparison",
    });
    expect(source).toHaveTextContent(oldCommit);
    expect(source).toHaveTextContent(newCommit);
    expect(screen.queryByText("Full commit copied")).not.toBeInTheDocument();
    const copyControls = within(source).getAllByRole("button", {
      name: "Copy full commit",
    });
    await userEvent.click(copyControls[1]);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(newCommit);
    expect(screen.getByText("Full commit copied")).toBeVisible();
  });

  it("UI3-C16 preserves Added Modified Removed counts and ordered metadata-only deltas", async () => {
    comparisonMock.mockResolvedValueOnce(
      ok(
        comparison({
          files: [
            {
              change: "added",
              path: "locales/new.json",
              position: 0,
              repository_side: "direct",
            },
            {
              change: "modified",
              path: "locales/current.json",
              position: 1,
              repository_side: "direct",
            },
            {
              change: "removed",
              path: "locales/old.json",
              position: 2,
              repository_side: "direct",
            },
          ],
          sides: [
            {
              ...comparison().sides[0],
              added_count: 1,
              modified_count: 1,
              removed_count: 1,
            },
          ],
        }),
      ),
    );
    renderDialog();

    const summary = await screen.findByLabelText("Source change summary");
    expect(
      within(summary)
        .getAllByText(/^(Added|Modified|Removed) 1$/)
        .map((node) => node.textContent),
    ).toEqual(["Added 1", "Modified 1", "Removed 1"]);
    const rows = within(
      screen.getByRole("table", { name: "Localization file changes" }),
    )
      .getAllByRole("row")
      .slice(1);
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringContaining("AddedSourcelocales/new.json"),
      expect.stringContaining("ModifiedSourcelocales/current.json"),
      expect.stringContaining("RemovedSourcelocales/old.json"),
    ]);
    expect(document.body).not.toHaveTextContent("provider body");
    expect(document.body).not.toHaveTextContent("raw source");
  });

  it("UI3-C20 focuses a bounded comparison error and omits confirmation for incomplete evidence", async () => {
    comparisonMock.mockResolvedValueOnce(failed(503) as never);
    renderDialog();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Baseline comparison unavailable");
    expect(alert).toHaveTextContent(
      "The proposed source could not be read safely. Close this review and retry the import later.",
    );
    await waitFor(() => expect(alert).toHaveFocus());
    expect(
      screen.queryByRole("button", { name: "Confirm new baseline" }),
    ).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(
      "provider body must stay private",
    );
  });

  it("UI3-C12 keeps stale confirmation open, focused, and guarded by exact proposal identity", async () => {
    comparisonMock.mockResolvedValueOnce(ok(comparison()));
    confirmationMock.mockResolvedValueOnce(failed(409) as never);
    renderDialog();

    await userEvent.click(
      await screen.findByRole("button", { name: "Confirm new baseline" }),
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Baseline changed again");
    expect(alert).toHaveTextContent(
      "The proposed baseline is no longer current. Close this review and run the import again.",
    );
    expect(alert).toHaveFocus();
    expect(
      screen.getByRole("alertdialog", {
        name: "Review rewritten source history",
      }),
    ).toBeVisible();
    expect(confirmationMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        proposal_digest: "f".repeat(64),
        proposal_id: "proposal-1",
        proposed_execution_id: "execution-2",
      },
      path: {
        import_id: "import-1",
        mapping_id: "mapping-1",
        product_id: "product-1",
      },
    });
  });

  it("confirms separate sides once, locks dismissal while pending, and restores the exact trigger after fresh refetch", async () => {
    let resolveConfirmation:
      | ((
          value: ReturnType<typeof ok<AdminPublishedMappingImportResponse>>,
        ) => void)
      | undefined;
    const trigger = document.createElement("button");
    trigger.textContent = "Review baseline change";
    document.body.append(trigger);
    const separateImport = importRecord({
      repository_sides: [
        {
          repository_id: "repository-1",
          role: "keys",
          source_branch: "keys/rebased",
        },
        {
          repository_id: "repository-2",
          role: "translations",
          source_branch: "translations/rebased",
        },
      ],
      topology: "separate",
    });
    comparisonMock.mockResolvedValueOnce(
      ok(
        comparison({
          sides: [
            {
              ...comparison().sides[0],
              repository_side: "keys",
            },
            {
              ...comparison().sides[0],
              repository_id: "repository-2",
              repository_side: "translations",
            },
          ],
          topology: "separate",
        }),
      ),
    );
    confirmationMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveConfirmation = resolve;
      }) as never,
    );
    const onClose = vi.fn();
    const onConfirmed = vi.fn().mockResolvedValue(true);
    const view = renderDialog({
      importRecord: separateImport,
      onClose,
      onConfirmed,
      triggerElement: trigger,
    });
    onClose.mockImplementation(() => {
      view.rerender(
        <RewrittenBaselineDialog
          accessToken="memory-only-admin-bearer"
          importRecord={separateImport}
          onClose={onClose}
          onConfirmed={onConfirmed}
          open={false}
          productId="product-1"
          repositories={repositories}
          triggerElement={trigger}
        />,
      );
    });

    const keys = await screen.findByRole("region", {
      name: "Keys baseline comparison",
    });
    const translations = screen.getByRole("region", {
      name: "Translations baseline comparison",
    });
    expect(keys.compareDocumentPosition(translations)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    const confirm = screen.getByRole("button", {
      name: "Confirm new baseline",
    });
    act(() => {
      confirm.click();
      confirm.click();
    });
    expect(confirmationMock).toHaveBeenCalledOnce();
    expect(confirm).toBeDisabled();
    expect(confirm).toHaveAttribute("aria-busy", "true");
    expect(
      screen.getByRole("button", { name: "Keep current baseline" }),
    ).toBeDisabled();
    await userEvent.keyboard("{Escape}");
    expect(onClose).not.toHaveBeenCalled();

    await act(async () => {
      resolveConfirmation?.(ok(separateImport));
    });
    await waitFor(() =>
      expect(onConfirmed).toHaveBeenCalledWith(separateImport),
    );
    expect(onClose).toHaveBeenCalledOnce();
    await waitFor(() => expect(trigger).toHaveFocus());
    trigger.remove();
  });
});
