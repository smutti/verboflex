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
import {
  createMemoryRouter,
  Link,
  RouterProvider,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createAdminCandidateMapping,
  getAdminProduct,
  getAdminRepositoryBranch,
  listAdminCandidateMappings,
  listAdminRepositories,
  listAdminRepositoryBranches,
  type AdminMappingResponse,
  type AdminRepositoryResponse,
} from "../../../api/client";
import { DirtyFormNavigationProvider } from "../../../components/navigation/DirtyFormNavigationGuard";
import { ProductMappingsPage } from "./ProductMappingsPage";

vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();
  return {
    ...original,
    createAdminCandidateMapping: vi.fn(),
    getAdminProduct: vi.fn(),
    getAdminRepositoryBranch: vi.fn(),
    listAdminCandidateMappings: vi.fn(),
    listAdminRepositories: vi.fn(),
    listAdminRepositoryBranches: vi.fn(),
  };
});

const createAdminCandidateMappingMock = vi.mocked(createAdminCandidateMapping);
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

function MappingNavigationHarness({
  accessToken,
  candidateVersion,
  productId,
}: {
  accessToken: string;
  candidateVersion?: number;
  productId: string;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <DirtyFormNavigationProvider>
      <nav aria-label="Test destinations">
        <Link to="/admin/users">Users destination</Link>
        <button type="button" onClick={() => void navigate("/admin/bitbucket")}>
          PUSH destination
        </button>
        <button type="button" onClick={() => void navigate(-1)}>
          Back intent
        </button>
      </nav>
      <output data-testid="current-location">{location.pathname}</output>
      <ProductMappingsPage
        accessToken={accessToken}
        candidateVersion={candidateVersion}
        productId={productId}
      />
    </DirtyFormNavigationProvider>
  );
}

function mappingRouter(
  productId = "product-one",
  accessToken = "memory-only-admin-bearer",
  candidateVersion?: number,
  initialEntries = [`/admin/products/${productId}/mappings`],
) {
  return createMemoryRouter(
    [
      {
        path: "*",
        element: (
          <MappingNavigationHarness
            accessToken={accessToken}
            candidateVersion={candidateVersion}
            productId={productId}
          />
        ),
      },
    ],
    { initialEntries, initialIndex: initialEntries.length - 1 },
  );
}

function renderMappings(productId = "product-one") {
  return render(
    <RouterProvider
      router={mappingRouter(productId, "memory-only-admin-bearer", 5)}
    />,
  );
}

function renderMappingsWithServerVersion(productId = "product-one") {
  return render(<RouterProvider router={mappingRouter(productId)} />);
}

describe("administrator mapping cursor collections", () => {
  beforeEach(() => {
    createAdminCandidateMappingMock.mockReset();
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
      <RouterProvider
        router={mappingRouter("new-product", "replacement-authority", 5)}
      />,
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

  it("fails closed on missing collection and version payloads, then retries all authorities", async () => {
    listAdminRepositoriesMock
      .mockResolvedValueOnce(ok(undefined as never))
      .mockResolvedValueOnce(ok({ items: [repository], next_cursor: null }));
    listAdminCandidateMappingsMock
      .mockResolvedValueOnce(ok(undefined as never))
      .mockResolvedValueOnce(ok({ items: [], next_cursor: null }));
    getAdminProductMock
      .mockResolvedValueOnce(ok(undefined as never))
      .mockResolvedValueOnce(
        ok({ candidate_revision: { version: 5 } } as never),
      );
    renderMappingsWithServerVersion();

    expect(await screen.findByText("Mappings unavailable")).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Retry loading page" }),
    );
    expect(await screen.findByText("No mappings configured")).toBeVisible();
    expect(listAdminRepositoriesMock).toHaveBeenCalledTimes(2);
    expect(listAdminCandidateMappingsMock).toHaveBeenCalledTimes(2);
    expect(getAdminProductMock).toHaveBeenCalledTimes(2);
  });

  it("keeps configured branches absent when provider results are missing", async () => {
    const configured = mapping(7, "release/configured");
    listAdminCandidateMappingsMock.mockResolvedValueOnce(
      ok({ items: [configured], next_cursor: null }),
    );
    listAdminRepositoryBranchesMock.mockResolvedValueOnce(
      ok(undefined as never),
    );
    getAdminRepositoryBranchMock.mockResolvedValueOnce(ok(undefined as never));
    renderMappings();

    await userEvent.click(
      (await screen.findAllByRole("button", { name: "Edit mapping" }))[0],
    );
    expect(await screen.findByText("Branches unavailable")).toBeVisible();
    expect(
      screen.getByRole("combobox", { name: "Source branch" }),
    ).not.toHaveTextContent("release/configured");
  });

  it("drops queued loads superseded before their microtasks run", async () => {
    listAdminCandidateMappingsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    getAdminProductMock.mockResolvedValue(
      ok({ candidate_revision: { version: 5 } } as never),
    );
    const view = renderMappings("obsolete-product");
    view.rerender(
      <RouterProvider
        router={mappingRouter("successor-product", "successor-authority")}
      />,
    );

    expect(await screen.findByText("No mappings configured")).toBeVisible();
    expect(getAdminProductMock).toHaveBeenCalledOnce();
  });

  it("loads separate mapping sides and validates the live translations branch", async () => {
    const translationsRepository = {
      ...repository,
      id: "00000000-0000-4000-8000-000000000302",
      descriptive_name: "Translations source",
      repository_slug: "translations",
    };
    const separateMapping: AdminMappingResponse = {
      ...mapping(8, "keys/main"),
      topology: "separate",
      translations_repository_id: translationsRepository.id,
      translations_source_branch: "translations/main",
      allowed_target_branches: ["release/2026"],
      default_target_branch: "release/2026",
    };
    listAdminRepositoriesMock.mockResolvedValueOnce(
      ok({ items: [repository, translationsRepository], next_cursor: null }),
    );
    listAdminCandidateMappingsMock.mockResolvedValueOnce(
      ok({ items: [separateMapping], next_cursor: null }),
    );
    listAdminRepositoryBranchesMock.mockResolvedValue(
      ok({
        items: [
          { name: "keys/main", commit_hash: "a".repeat(40) },
          { name: "translations/main", commit_hash: "b".repeat(40) },
          { name: "release/2026", commit_hash: "c".repeat(40) },
        ],
        next_cursor: null,
      }),
    );
    getAdminRepositoryBranchMock.mockImplementation(async (options) => {
      const branch = {
        name: options.query.branch_name,
        commit_hash: "d".repeat(40),
      };
      const response = ok(branch);
      let reads = 0;
      Object.defineProperty(response, "data", {
        get: () => (++reads === 1 ? branch : undefined),
      });
      return response;
    });
    createAdminCandidateMappingMock.mockResolvedValueOnce(ok(separateMapping));
    renderMappings();

    await userEvent.click(
      (await screen.findAllByRole("button", { name: "Edit mapping" }))[0],
    );
    expect(screen.getByRole("radio", { name: "Separate" })).toBeChecked();
    await waitFor(() => {
      expect(
        screen.getByRole("combobox", { name: "Translations source branch" }),
      ).toHaveTextContent("translations/main");
    });
    await userEvent.click(screen.getByRole("button", { name: "Cancel edit" }));
    await userEvent.click(
      screen.getByRole("link", { name: "Users destination" }),
    );
    expect(
      screen.queryByRole("alertdialog", { name: "Leave without saving?" }),
    ).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("radio", { name: "Separate" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Change topology" }),
    );
    await userEvent.click(
      screen.getByRole("combobox", { name: "Keys repository" }),
    );
    await userEvent.click(
      screen.getByRole("option", { name: /Application source/ }),
    );
    await userEvent.click(
      screen.getByRole("combobox", { name: "Translations repository" }),
    );
    await userEvent.click(
      screen.getByRole("option", { name: /Translations source/ }),
    );
    await waitFor(() =>
      expect(listAdminRepositoryBranchesMock).toHaveBeenCalled(),
    );
    await userEvent.click(
      screen.getByRole("combobox", { name: "Keys source branch" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "keys/main" }));
    await userEvent.click(
      screen.getByRole("combobox", { name: "Translations source branch" }),
    );
    await userEvent.click(
      screen.getByRole("option", { name: "translations/main" }),
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Allow target release/2026" }),
    );
    await userEvent.click(
      screen.getByRole("combobox", { name: "Default target" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "release/2026" }));
    await userEvent.click(screen.getByRole("button", { name: "Save mapping" }));
    await waitFor(() =>
      expect(createAdminCandidateMappingMock).toHaveBeenCalledOnce(),
    );
    await userEvent.click(
      screen.getByRole("link", { name: "Users destination" }),
    );
    expect(
      screen.queryByRole("alertdialog", { name: "Leave without saving?" }),
    ).not.toBeInTheDocument();
  });

  it("maps rejected server-version loads to the bounded page error", async () => {
    listAdminCandidateMappingsMock.mockResolvedValueOnce(
      ok({ items: [], next_cursor: null }),
    );
    getAdminProductMock.mockRejectedValueOnce(
      new Error("private version failure"),
    );
    renderMappingsWithServerVersion();
    expect(await screen.findByText("Mappings unavailable")).toBeVisible();
  });

  it("ignores a rejected version load after authority is replaced", async () => {
    let rejectObsolete!: (reason: Error) => void;
    getAdminProductMock
      .mockReturnValueOnce(
        new Promise((_resolve, reject) => {
          rejectObsolete = reject;
        }) as never,
      )
      .mockResolvedValueOnce(
        ok({ candidate_revision: { version: 5 } } as never),
      );
    listAdminCandidateMappingsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    const view = renderMappingsWithServerVersion("obsolete-product");
    await waitFor(() => expect(getAdminProductMock).toHaveBeenCalledOnce());
    view.rerender(
      <RouterProvider
        router={mappingRouter("successor-product", "successor-authority")}
      />,
    );
    expect(await screen.findByText("No mappings configured")).toBeVisible();
    rejectObsolete(new Error("stale version failure"));
    await act(async () => Promise.resolve());
    expect(screen.queryByText("Mappings unavailable")).not.toBeInTheDocument();
  });

  it("ignores a successful version load after authority is replaced", async () => {
    let resolveObsolete!: (value: ReturnType<typeof ok<unknown>>) => void;
    getAdminProductMock
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveObsolete = resolve;
        }) as never,
      )
      .mockResolvedValueOnce(
        ok({ candidate_revision: { version: 5 } } as never),
      );
    listAdminCandidateMappingsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    const view = renderMappingsWithServerVersion("obsolete-product");
    await waitFor(() => expect(getAdminProductMock).toHaveBeenCalledOnce());
    view.rerender(
      <RouterProvider
        router={mappingRouter("successor-product", "successor-authority")}
      />,
    );
    expect(await screen.findByText("No mappings configured")).toBeVisible();
    resolveObsolete(ok({ candidate_revision: { version: 99 } }));
    await act(async () => Promise.resolve());
    expect(screen.queryByText("Mappings unavailable")).not.toBeInTheDocument();
  });

  it("rejects an incomplete mapping before any mutation", async () => {
    listAdminCandidateMappingsMock.mockResolvedValueOnce(
      ok({ items: [], next_cursor: null }),
    );
    renderMappings();
    await userEvent.click(
      await screen.findByRole("button", { name: "Save mapping" }),
    );
    expect(await screen.findByText("Mapping not saved")).toBeVisible();
    expect(createAdminCandidateMappingMock).not.toHaveBeenCalled();
  });

  it("blocks confirmed topology changes for Link, PUSH, and Back while topology cancellation stays clean", async () => {
    listAdminCandidateMappingsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    render(
      <RouterProvider
        router={mappingRouter("product-one", "memory-only-admin-bearer", 5, [
          "/admin/users",
          "/admin/products/product-one/mappings",
        ])}
      />,
    );
    const user = userEvent.setup();

    expect(
      await screen.findByRole("heading", { name: "Add mapping" }),
    ).toBeVisible();
    await user.click(screen.getByRole("radio", { name: "Separate" }));
    const topologyDialog = screen.getByRole("alertdialog", {
      name: "Change mapping topology?",
    });
    await user.click(
      within(topologyDialog).getByRole("button", { name: "Cancel" }),
    );
    await user.click(screen.getByRole("link", { name: "Users destination" }));
    expect(screen.getByTestId("current-location")).toHaveTextContent(
      "/admin/users",
    );

    await user.click(screen.getByRole("radio", { name: "Separate" }));
    await user.click(screen.getByRole("button", { name: "Change topology" }));
    const push = screen.getByRole("button", { name: "PUSH destination" });
    push.focus();
    await user.click(push);
    const dialog = await screen.findByRole("alertdialog", {
      name: "Leave without saving?",
    });
    expect(dialog).toHaveTextContent(
      "Your unsaved entries on this page will be lost.",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Keep editing" }),
    );
    expect(screen.getByRole("radio", { name: "Separate" })).toBeChecked();
    expect(push).toHaveFocus();
    expect(screen.getByTestId("current-location")).toHaveTextContent(
      "/admin/users",
    );

    await user.click(screen.getByRole("button", { name: "Back intent" }));
    expect(
      await screen.findByRole("alertdialog", {
        name: "Leave without saving?",
      }),
    ).toBeVisible();
  });

  it("treats an unchanged edit and reordered target set as clean but exact field changes as dirty", async () => {
    const configured = {
      ...mapping(11),
      allowed_target_branches: ["main", "release/2026"],
      default_target_branch: "main",
    };
    listAdminCandidateMappingsMock.mockResolvedValue(
      ok({ items: [configured], next_cursor: null }),
    );
    listAdminRepositoryBranchesMock.mockResolvedValue(
      ok({
        items: [
          { name: "main", commit_hash: "a".repeat(40) },
          { name: "release/2026", commit_hash: "b".repeat(40) },
        ],
        next_cursor: null,
      }),
    );
    getAdminRepositoryBranchMock.mockImplementation(async (options) =>
      ok({
        name: options.query.branch_name,
        commit_hash: "c".repeat(40),
      }),
    );
    renderMappings();
    const user = userEvent.setup();

    await user.click(
      (await screen.findAllByRole("button", { name: "Edit mapping" }))[0],
    );
    await user.click(screen.getByLabelText("Allow target main"));
    await user.click(screen.getByLabelText("Allow target main"));
    await user.click(screen.getByRole("combobox", { name: "Default target" }));
    await user.click(screen.getByRole("option", { name: "main" }));
    await user.click(screen.getByRole("link", { name: "Users destination" }));
    expect(
      screen.queryByRole("alertdialog", { name: "Leave without saving?" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("combobox", { name: "Default target" }));
    await user.click(screen.getByRole("option", { name: "release/2026" }));
    await user.click(screen.getByRole("link", { name: "Users destination" }));
    const dialog = await screen.findByRole("alertdialog", {
      name: "Leave without saving?",
    });
    await user.click(
      within(dialog).getByRole("button", { name: "Keep editing" }),
    );
    expect(
      screen.getByRole("combobox", { name: "Default target" }),
    ).toHaveTextContent("release/2026");

    await user.click(screen.getByRole("combobox", { name: "Default target" }));
    await user.click(screen.getByRole("option", { name: "main" }));
    await user.click(screen.getByRole("link", { name: "Users destination" }));
    expect(
      screen.queryByRole("alertdialog", { name: "Leave without saving?" }),
    ).not.toBeInTheDocument();
  });

  it("keeps invalid mapping attempts dirty and protected with values and focus intact", async () => {
    listAdminCandidateMappingsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    renderMappings();
    const user = userEvent.setup();

    await user.click(
      await screen.findByRole("combobox", { name: "Repository" }),
    );
    await user.click(
      screen.getByRole("option", { name: /Application source/ }),
    );
    await user.click(screen.getByRole("button", { name: "Save mapping" }));
    expect(await screen.findByText("Mapping not saved")).toBeVisible();
    const link = screen.getByRole("link", { name: "Users destination" });
    link.focus();
    await user.click(link);
    const dialog = await screen.findByRole("alertdialog", {
      name: "Leave without saving?",
    });
    await user.click(
      within(dialog).getByRole("button", { name: "Keep editing" }),
    );
    expect(
      screen.getByRole("combobox", { name: "Repository" }),
    ).toHaveTextContent("Application source");
    expect(link).toHaveFocus();
  });

  it("protects every separate-side field through generic and conflict save failures", async () => {
    const translationsRepository = {
      ...repository,
      id: "00000000-0000-4000-8000-000000000302",
      descriptive_name: "Translations source",
      repository_slug: "translations",
    };
    listAdminRepositoriesMock.mockResolvedValue(
      ok({
        items: [repository, translationsRepository],
        next_cursor: null,
      }),
    );
    listAdminCandidateMappingsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    listAdminRepositoryBranchesMock.mockResolvedValue(
      ok({
        items: [
          { name: "keys/main", commit_hash: "a".repeat(40) },
          { name: "translations/main", commit_hash: "b".repeat(40) },
          { name: "release/2026", commit_hash: "c".repeat(40) },
        ],
        next_cursor: null,
      }),
    );
    createAdminCandidateMappingMock
      .mockResolvedValueOnce({
        data: undefined,
        error: { detail: "bounded failure" },
        request: new Request("http://localhost/api/v1/admin"),
        response: new Response(null, { status: 503 }),
      } as never)
      .mockResolvedValueOnce({
        data: undefined,
        error: { detail: "Candidate revision conflict" },
        request: new Request("http://localhost/api/v1/admin"),
        response: new Response(null, { status: 409 }),
      } as never);
    renderMappings();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("radio", { name: "Separate" }));
    await user.click(screen.getByRole("button", { name: "Change topology" }));
    await user.click(screen.getByRole("combobox", { name: "Keys repository" }));
    await user.click(
      screen.getByRole("option", { name: /Application source/ }),
    );
    await user.click(
      screen.getByRole("combobox", { name: "Translations repository" }),
    );
    await user.click(
      screen.getByRole("option", { name: /Translations source/ }),
    );
    await user.click(
      screen.getByRole("combobox", { name: "Keys source branch" }),
    );
    await user.click(screen.getByRole("option", { name: "keys/main" }));
    await user.click(
      screen.getByRole("combobox", { name: "Translations source branch" }),
    );
    await user.click(screen.getByRole("option", { name: "translations/main" }));
    await user.click(screen.getByLabelText("Allow target release/2026"));
    await user.click(screen.getByRole("combobox", { name: "Default target" }));
    await user.click(screen.getByRole("option", { name: "release/2026" }));

    await user.click(screen.getByRole("button", { name: "Save mapping" }));
    expect(await screen.findByText("Mapping not saved")).toBeVisible();
    const push = screen.getByRole("button", { name: "PUSH destination" });
    await user.click(push);
    let dialog = await screen.findByRole("alertdialog", {
      name: "Leave without saving?",
    });
    await user.click(
      within(dialog).getByRole("button", { name: "Keep editing" }),
    );
    expect(
      screen.getByRole("combobox", { name: "Keys source branch" }),
    ).toHaveTextContent("keys/main");
    expect(
      screen.getByRole("combobox", { name: "Translations source branch" }),
    ).toHaveTextContent("translations/main");
    expect(screen.getByLabelText("Allow target release/2026")).toBeChecked();

    await user.click(screen.getByRole("button", { name: "Save mapping" }));
    expect(
      await screen.findByText(/mapping conflicts with the current draft/i),
    ).toBeVisible();
    await user.click(screen.getByRole("link", { name: "Users destination" }));
    dialog = await screen.findByRole("alertdialog", {
      name: "Leave without saving?",
    });
    expect(dialog).toBeVisible();
  });
});
