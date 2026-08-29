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
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getAdminProduct,
  getAdminRepositoryBranch,
  listAdminCandidateMappings,
  listAdminRepositories,
  listAdminRepositoryBranches,
  type AdminMappingResponse,
  type AdminRepositoryResponse,
} from "../../../api/client";
import { ProductMappingsPage } from "./ProductMappingsPage";

vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();
  return {
    ...original,
    getAdminProduct: vi.fn(),
    getAdminRepositoryBranch: vi.fn(),
    listAdminCandidateMappings: vi.fn(),
    listAdminRepositories: vi.fn(),
    listAdminRepositoryBranches: vi.fn(),
  };
});

const getAdminProductMock = vi.mocked(getAdminProduct);
const getAdminRepositoryBranchMock = vi.mocked(getAdminRepositoryBranch);
const listAdminCandidateMappingsMock = vi.mocked(listAdminCandidateMappings);
const listAdminRepositoriesMock = vi.mocked(listAdminRepositories);
const listAdminRepositoryBranchesMock = vi.mocked(listAdminRepositoryBranches);

class TestResizeObserver implements ResizeObserver {
  disconnect() {}
  observe() {}
  unobserve() {}
}

vi.stubGlobal("ResizeObserver", TestResizeObserver);
Object.defineProperties(HTMLElement.prototype, {
  hasPointerCapture: {
    configurable: true,
    value: () => false,
  },
  releasePointerCapture: {
    configurable: true,
    value: () => undefined,
  },
  scrollIntoView: {
    configurable: true,
    value: () => undefined,
  },
  setPointerCapture: {
    configurable: true,
    value: () => undefined,
  },
});

const repository: AdminRepositoryResponse = {
  id: "00000000-0000-4000-8000-000000000301",
  descriptive_name: "Application source",
  workspace: "product-team",
  repository_slug: "mobile-app",
};

function mapping(index: number, sourceBranch = "main"): AdminMappingResponse {
  return {
    id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    topology: "direct",
    candidate_version: 5,
    primary_repository_id: repository.id,
    primary_source_branch: sourceBranch,
    translations_repository_id: null,
    translations_source_branch: null,
    allowed_target_branches: [sourceBranch],
    default_target_branch: sourceBranch,
    selected_layout_candidate_id: null,
    selected_layout_version: null,
  };
}

function ok<T>(data: T) {
  return {
    data,
    error: undefined,
    request: new Request("http://localhost/api/v1/admin"),
    response: new Response(null, { status: 200 }),
  };
}

function renderMappings(productId = "product-one") {
  return render(
    <MemoryRouter>
      <ProductMappingsPage
        accessToken="memory-only-admin-bearer"
        candidateVersion={5}
        productId={productId}
      />
    </MemoryRouter>,
  );
}

describe("administrator mapping cursor collections", () => {
  beforeEach(() => {
    getAdminProductMock.mockReset();
    getAdminRepositoryBranchMock.mockReset();
    listAdminCandidateMappingsMock.mockReset();
    listAdminRepositoriesMock.mockReset();
    listAdminRepositoriesMock.mockResolvedValue(
      ok({ items: [repository], next_cursor: null }),
    );
    listAdminRepositoryBranchesMock.mockReset();
  });

  afterEach(() => cleanup());

  it("appends mapping 51 in API order with one request and no repeated identity", async () => {
    const firstPage = Array.from({ length: 50 }, (_, index) =>
      mapping(index + 1),
    );
    listAdminCandidateMappingsMock
      .mockResolvedValueOnce(
        ok({ items: firstPage, next_cursor: "opaque-mapping-page-2" }),
      )
      .mockResolvedValueOnce(
        ok({ items: [firstPage[49], mapping(51)], next_cursor: null }),
      );
    renderMappings();

    expect(
      await screen.findByText("50 mappings loaded — more available"),
    ).toBeVisible();
    const loadMore = screen.getByRole("button", {
      name: "Load more mappings",
    });
    act(() => {
      loadMore.click();
      loadMore.click();
    });

    await waitFor(() =>
      expect(listAdminCandidateMappingsMock).toHaveBeenCalledTimes(2),
    );
    expect(listAdminCandidateMappingsMock).toHaveBeenNthCalledWith(1, {
      auth: "memory-only-admin-bearer",
      path: { product_id: "product-one" },
      query: { cursor: null, limit: 50 },
      signal: expect.any(AbortSignal),
    });
    expect(listAdminCandidateMappingsMock).toHaveBeenNthCalledWith(2, {
      auth: "memory-only-admin-bearer",
      path: { product_id: "product-one" },
      query: { cursor: "opaque-mapping-page-2", limit: 50 },
      signal: expect.any(AbortSignal),
    });
    expect(await screen.findByText("All 51 mappings loaded")).toBeVisible();
    expect(
      within(screen.getByRole("table", { name: "Mappings" }))
        .getAllByRole("row")
        .slice(1)
        .map((row) =>
          row
            .querySelector("button")
            ?.closest("tr")
            ?.textContent?.match(/Draft version 5/),
        ),
    ).toHaveLength(51);
    expect(
      screen.getAllByRole("button", { name: "Edit mapping" }),
    ).toHaveLength(102);
    expect(
      screen.getByLabelText("Mappings mobile list").closest("section"),
    ).toHaveClass("min-w-0", "max-w-full", "overflow-x-clip");
  });

  it("aborts and rejects stale mapping pages when product authority changes", async () => {
    let resolveOld:
      | ((
          value: ReturnType<
            typeof ok<{ items: AdminMappingResponse[]; next_cursor: null }>
          >,
        ) => void)
      | undefined;
    const oldPage = new Promise<
      ReturnType<
        typeof ok<{ items: AdminMappingResponse[]; next_cursor: null }>
      >
    >((resolve) => {
      resolveOld = resolve;
    });
    listAdminCandidateMappingsMock
      .mockReturnValueOnce(oldPage)
      .mockResolvedValueOnce(ok({ items: [mapping(902)], next_cursor: null }));

    const view = renderMappings("old-product");
    await waitFor(() =>
      expect(listAdminCandidateMappingsMock).toHaveBeenCalledTimes(1),
    );
    const oldSignal = listAdminCandidateMappingsMock.mock.calls[0]?.[0].signal;
    view.rerender(
      <MemoryRouter>
        <ProductMappingsPage
          accessToken="replacement-authority"
          candidateVersion={5}
          productId="new-product"
        />
      </MemoryRouter>,
    );

    expect(await screen.findByText("All 1 mapping loaded")).toBeVisible();
    expect(oldSignal?.aborted).toBe(true);
    await act(async () => {
      resolveOld?.(ok({ items: [mapping(901)], next_cursor: null }));
    });
    expect(screen.queryByText(/000000000901/)).not.toBeInTheDocument();
    expect(listAdminCandidateMappingsMock).toHaveBeenNthCalledWith(2, {
      auth: "replacement-authority",
      path: { product_id: "new-product" },
      query: { cursor: null, limit: 50 },
      signal: expect.any(AbortSignal),
    });
  });

  it("restores configured branch 101 exactly and pages one cursor per action", async () => {
    const configuredBranch =
      "release/2026-with-a-very-long-opaque-provider-branch-name";
    const configuredMapping = mapping(1, configuredBranch);
    const firstHundred = Array.from({ length: 100 }, (_, index) => ({
      name: `provider-branch-${String(index + 1).padStart(3, "0")}`,
      commit_hash: String(index + 1).padStart(40, "0"),
    }));
    listAdminCandidateMappingsMock.mockResolvedValueOnce(
      ok({ items: [configuredMapping], next_cursor: null }),
    );
    listAdminRepositoryBranchesMock
      .mockResolvedValueOnce(
        ok({ items: firstHundred, next_cursor: "opaque-branch-page-2" }),
      )
      .mockResolvedValueOnce(
        ok({
          items: [
            firstHundred[99],
            { name: configuredBranch, commit_hash: "f".repeat(40) },
          ],
          next_cursor: null,
        }),
      );
    getAdminRepositoryBranchMock.mockResolvedValueOnce(
      ok({ name: configuredBranch, commit_hash: "f".repeat(40) }),
    );
    renderMappings();

    await userEvent.click(
      (await screen.findAllByRole("button", { name: "Edit mapping" }))[0],
    );
    const sourceBranch = await screen.findByRole("combobox", {
      name: "Source branch",
    });
    await waitFor(() =>
      expect(sourceBranch).toHaveTextContent(configuredBranch),
    );
    expect(
      screen.getByText("100 branches loaded — more available"),
    ).toBeVisible();
    expect(getAdminRepositoryBranchMock).toHaveBeenCalledOnce();
    expect(getAdminRepositoryBranchMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { repository_id: repository.id },
      query: { branch_name: configuredBranch },
      signal: expect.any(AbortSignal),
    });
    expect(listAdminRepositoryBranchesMock).toHaveBeenNthCalledWith(1, {
      auth: "memory-only-admin-bearer",
      path: { repository_id: repository.id },
      query: { cursor: null, limit: 100 },
      signal: expect.any(AbortSignal),
    });

    const loadMore = screen.getByRole("button", {
      name: "Load more branches for Source branch",
    });
    act(() => {
      loadMore.click();
      loadMore.click();
    });
    await waitFor(() =>
      expect(listAdminRepositoryBranchesMock).toHaveBeenCalledTimes(2),
    );
    expect(listAdminRepositoryBranchesMock).toHaveBeenNthCalledWith(2, {
      auth: "memory-only-admin-bearer",
      path: { repository_id: repository.id },
      query: { cursor: "opaque-branch-page-2", limit: 100 },
      signal: expect.any(AbortSignal),
    });
    expect(await screen.findByText("All 101 branches loaded")).toBeVisible();
    expect(sourceBranch).toHaveTextContent(configuredBranch);
    expect(getAdminRepositoryBranchMock).toHaveBeenCalledOnce();
  });
});
