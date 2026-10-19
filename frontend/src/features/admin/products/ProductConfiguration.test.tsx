import "@testing-library/jest-dom/vitest";

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  createMemoryRouter,
  MemoryRouter,
  Route,
  RouterProvider,
  Routes,
  useLocation,
} from "react-router-dom";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getAdminBitbucketWorkspace,
  listAdminBitbucketRepositories,
  selectAdminBitbucketRepository,
  getAdminRepository,
  createAdminCandidateMapping,
  updateAdminCandidateMapping,
  createAdminProduct,
  createAdminRepository,
  deactivateAdminProduct,
  deleteAdminProduct,
  getAdminProduct,
  getAdminProductSummary,
  getAdminLatestCandidatePreviewJob,
  getAdminRepositoryBranch,
  listAdminCandidateMappings,
  listAdminPublishedMappingImports,
  listAdminProducts,
  listAdminRepositories,
  listAdminRepositoryBranches,
  listAdminRevisionMappings,
  readSystemStatus,
  updateAdminProductCandidate,
  type AdminMappingResponse,
  type AdminProductResponse,
  type AdminProductSummaryResponse,
  type AdminRepositoryResponse,
} from "../../../api/client";
import { useSession } from "../../auth/session";
import { ProductOverviewPage } from "./ProductOverviewPage";
import { ProductsPage } from "./ProductsPage";
import { ProductWizardPage } from "./ProductWizardPage";
import { loadEditableProduct } from "./ProductWizardPage";
import { ProductDetailLayout } from "./ProductDetailLayout";
import { AppRouter } from "../../../router";
import { AppShell } from "../../../components/layout/AppShell";
import { DirtyFormNavigationProvider } from "../../../components/navigation/DirtyFormNavigationGuard";

class TestResizeObserver implements ResizeObserver {
  disconnect() {}
  observe() {}
  unobserve() {}
}

const intersectionObservers: TestIntersectionObserver[] = [];

class TestIntersectionObserver implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = "0px";
  readonly scrollMargin = "0px";
  readonly thresholds = [0];
  private target: Element | null = null;

  constructor(private readonly callback: IntersectionObserverCallback) {
    intersectionObservers.push(this);
  }

  disconnect() {
    this.target = null;
  }

  observe(target: Element) {
    this.target = target;
  }

  takeRecords() {
    return [];
  }

  unobserve(target: Element) {
    if (this.target === target) {
      this.target = null;
    }
  }

  intersect() {
    if (this.target === null) {
      return;
    }
    this.callback(
      [
        {
          boundingClientRect: this.target.getBoundingClientRect(),
          intersectionRatio: 1,
          intersectionRect: this.target.getBoundingClientRect(),
          isIntersecting: true,
          rootBounds: null,
          target: this.target,
          time: 0,
        },
      ],
      this,
    );
  }
}

vi.stubGlobal("ResizeObserver", TestResizeObserver);
vi.stubGlobal("IntersectionObserver", TestIntersectionObserver);
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

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
  },
}));

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();

  return {
    ...original,
    getAdminBitbucketWorkspace: vi.fn(),
    listAdminBitbucketRepositories: vi.fn(),
    selectAdminBitbucketRepository: vi.fn(),
    getAdminRepository: vi.fn(),
    createAdminCandidateMapping: vi.fn(),
    updateAdminCandidateMapping: vi.fn(),
    createAdminProduct: vi.fn(),
    createAdminRepository: vi.fn(),
    deactivateAdminProduct: vi.fn(),
    deleteAdminProduct: vi.fn(),
    getAdminProduct: vi.fn(),
    getAdminProductSummary: vi.fn(),
    getAdminLatestCandidatePreviewJob: vi.fn(),
    getAdminRepositoryBranch: vi.fn(),
    listAdminCandidateMappings: vi.fn(),
    listAdminPublishedMappingImports: vi.fn(),
    listAdminProducts: vi.fn(),
    listAdminRepositories: vi.fn(),
    listAdminRepositoryBranches: vi.fn(),
    listAdminRevisionMappings: vi.fn(),
    readSystemStatus: vi.fn(),
    updateAdminProductCandidate: vi.fn(),
  };
});

vi.mock("../../auth/session", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../auth/session")>();

  return {
    ...original,
    useSession: vi.fn(),
  };
});

const createAdminCandidateMappingMock = vi.mocked(createAdminCandidateMapping);
const createAdminProductMock = vi.mocked(createAdminProduct);
const createAdminRepositoryMock = vi.mocked(createAdminRepository);
const deactivateAdminProductMock = vi.mocked(deactivateAdminProduct);
const deleteAdminProductMock = vi.mocked(deleteAdminProduct);
const getAdminProductMock = vi.mocked(getAdminProduct);
const getAdminProductSummaryMock = vi.mocked(getAdminProductSummary);
const productSummary: AdminProductSummaryResponse = {
  product_id: "product-a",
  source_string_count: 4,
  expected_translation_count: 8,
  translated_count: 5,
  missing_count: 3,
  target_language_count: 2,
  coverage_percent: 62.5,
  imported_scope_count: 1,
  unimported_scope_count: 0,
  last_imported_at: "2026-10-01T12:00:00Z",
  languages_has_more: false,
  languages: [
    {
      language: "it",
      expected_count: 4,
      translated_count: 1,
      missing_count: 3,
      coverage_percent: 25,
    },
    {
      language: "vi",
      expected_count: 4,
      translated_count: 4,
      missing_count: 0,
      coverage_percent: 100,
    },
  ],
};
const getAdminRepositoryBranchMock = vi.mocked(getAdminRepositoryBranch);
const listAdminCandidateMappingsMock = vi.mocked(listAdminCandidateMappings);
const listAdminPublishedMappingImportsMock = vi.mocked(
  listAdminPublishedMappingImports,
);
const listAdminProductsMock = vi.mocked(listAdminProducts);
const listAdminRepositoriesMock = vi.mocked(listAdminRepositories);
const listAdminRepositoryBranchesMock = vi.mocked(listAdminRepositoryBranches);
const listAdminRevisionMappingsMock = vi.mocked(listAdminRevisionMappings);
const readSystemStatusMock = vi.mocked(readSystemStatus);
const useSessionMock = vi.mocked(useSession);
const updateAdminProductCandidateMock = vi.mocked(updateAdminProductCandidate);
const toastSuccessMock = vi.mocked(toast.success);

const activeProduct: AdminProductResponse = {
  id: "00000000-0000-4000-8000-000000000101",
  name: "Zulu Mobile",
  is_active: true,
  affected_mapping_count: 0,
  active_revision: {
    id: "00000000-0000-4000-8000-000000000201",
    description: "Published mobile strings",
    is_published: true,
    name: "Zulu Mobile",
    version: 4,
  },
  candidate_revision: {
    id: "00000000-0000-4000-8000-000000000202",
    description: "Candidate mobile strings",
    is_published: false,
    name: "Zulu Mobile",
    version: 5,
  },
};

const candidateOnlyProduct: AdminProductResponse = {
  id: "00000000-0000-4000-8000-000000000102",
  name: "Alpha Embedded",
  is_active: false,
  affected_mapping_count: 0,
  active_revision: null,
  candidate_revision: {
    id: "00000000-0000-4000-8000-000000000203",
    description: null,
    is_published: false,
    name: "Alpha Embedded",
    version: 1,
  },
};

const inactivePublishedProduct: AdminProductResponse = {
  id: "00000000-0000-4000-8000-000000000103",
  name: "Middle Desktop",
  is_active: false,
  affected_mapping_count: 0,
  active_revision: {
    id: "00000000-0000-4000-8000-000000000204",
    description: "Retained published desktop strings",
    is_published: true,
    name: "Middle Desktop",
    version: 2,
  },
  candidate_revision: null,
};

const activeWithoutCandidateProduct: AdminProductResponse = {
  ...inactivePublishedProduct,
  name: "Published Without Draft",
  is_active: true,
};

const applicationRepository: AdminRepositoryResponse = {
  id: "00000000-0000-4000-8000-000000000301",
  descriptive_name: "Mobile application source",
  workspace: "product-team",
  repository_slug: "mobile-app",
};

const translationRepository: AdminRepositoryResponse = {
  id: "00000000-0000-4000-8000-000000000302",
  descriptive_name: null,
  workspace: "localization-team",
  repository_slug: "mobile-translations",
};

const directMapping: AdminMappingResponse = {
  id: "00000000-0000-4000-8000-000000000401",
  topology: "direct",
  candidate_version: 5,
  primary_repository_id: applicationRepository.id,
  primary_source_branch: "main",
  translations_repository_id: null,
  translations_source_branch: null,
  allowed_target_branches: [
    "release/2026-with-a-very-long-opaque-provider-branch-name",
  ],
  default_target_branch:
    "release/2026-with-a-very-long-opaque-provider-branch-name",
  selected_layout_candidate_id: null,
  selected_layout_version: null,
};

const liveBranches = {
  items: [
    { name: "main", commit_hash: "a".repeat(40) },
    {
      name: "release/2026-with-a-very-long-opaque-provider-branch-name",
      commit_hash: "b".repeat(40),
    },
  ],
  next_cursor: null,
};

function exposeTask2Repositories() {
  listAdminRepositoriesMock.mockResolvedValue(
    ok({
      items: [applicationRepository, translationRepository],
      next_cursor: null,
    }),
  );
}

function ok<T>(data: T, status = 200) {
  return {
    data,
    error: undefined,
    request: new Request("http://localhost/api/v1/admin/products"),
    response: new Response(null, { status }),
  };
}

function conflict(field: "name" | null = "name") {
  return {
    data: undefined,
    error: { detail: "Product conflict", field },
    request: new Request("http://localhost/api/v1/admin/products"),
    response: new Response(null, { status: 409 }),
  };
}

function mappingConflict(
  field:
    | "mapping_identity"
    | "candidate_version"
    | "source_branch"
    | "keys_source_branch"
    | "translations_source_branch"
    | "allowed_target_branches",
) {
  return {
    data: undefined,
    error: { detail: "private provider conflict detail", field },
    request: new Request(
      "http://localhost/api/v1/admin/products/product-id/candidate/mappings",
    ),
    response: new Response(null, { status: 409 }),
  };
}

function failure(status = 503) {
  return {
    data: undefined,
    error: { detail: "bounded test failure" },
    request: new Request("http://localhost/api/v1/admin/products"),
    response: new Response(null, { status }),
  };
}

function renderProducts() {
  return render(
    <MemoryRouter>
      <ProductsPage accessToken="memory-only-admin-bearer" />
      <LocationMarker />
    </MemoryRouter>,
  );
}

function LocationMarker() {
  const location = useLocation();
  return <span data-testid="current-location">{location.pathname}</span>;
}

function renderWizard(initialProduct?: AdminProductResponse) {
  const router = createMemoryRouter([
    {
      path: "*",
      element: (
        <DirtyFormNavigationProvider>
          <ProductWizardPage
            accessToken="memory-only-admin-bearer"
            initialProduct={initialProduct}
          />
        </DirtyFormNavigationProvider>
      ),
    },
  ]);
  return render(<RouterProvider router={router} />);
}

function createRouteWizardRouter(accessToken: string) {
  return createMemoryRouter(
    [
      {
        path: "/admin/products/:productId/edit",
        element: (
          <DirtyFormNavigationProvider>
            <ProductWizardPage accessToken={accessToken} />
          </DirtyFormNavigationProvider>
        ),
      },
    ],
    { initialEntries: [`/admin/products/${activeProduct.id}/edit`] },
  );
}

function renderRouteWizard(accessToken = "memory-only-admin-bearer") {
  return render(
    <RouterProvider router={createRouteWizardRouter(accessToken)} />,
  );
}

function renderRoutedProductDetails({
  initialEntries = [`/admin/products/${activeProduct.id}/edit`],
  initialIndex,
}: {
  initialEntries?: string[];
  initialIndex?: number;
} = {}) {
  const router = createMemoryRouter(
    [
      {
        path: "*",
        element: (
          <DirtyFormNavigationProvider>
            <AppShell
              accessToken="memory-only-admin-bearer"
              onLogout={vi.fn()}
              principal={{
                id: "00000000-0000-4000-8000-000000000001",
                email: "admin@example.com",
                display_name: "Admin",
                must_change_password: false,
                roles: ["admin"],
              }}
            >
              <Routes>
                <Route
                  path={`/admin/products/${activeProduct.id}/edit`}
                  element={
                    <ProductWizardPage
                      accessToken="memory-only-admin-bearer"
                      initialProduct={activeProduct}
                    />
                  }
                />
                <Route
                  path="/admin/users"
                  element={<h1>Users destination</h1>}
                />
              </Routes>
              <LocationMarker />
            </AppShell>
          </DirtyFormNavigationProvider>
        ),
      },
    ],
    { initialEntries, initialIndex },
  );
  return { router, view: render(<RouterProvider router={router} />) };
}

function renderApplicationRouter(initialEntry: string) {
  const router = createMemoryRouter(
    [
      {
        path: "*",
        element: (
          <DirtyFormNavigationProvider>
            <AppRouter />
          </DirtyFormNavigationProvider>
        ),
      },
    ],
    { initialEntries: [initialEntry] },
  );
  return render(<RouterProvider router={router} />);
}

function renderOverview() {
  return render(
    <MemoryRouter>
      <ProductOverviewPage
        accessToken="memory-only-admin-bearer"
        productId={activeProduct.id}
      />
      <LocationMarker />
    </MemoryRouter>,
  );
}

describe("administrator product configuration tracer", () => {
  it("protects unsaved mapping fields when entering the combined preview step", async () => {
    renderWizard(activeProduct);
    const user = userEvent.setup();
    const steps = screen.getByRole("navigation", {
      name: "Product setup steps",
    });
    await user.click(
      within(steps).getByRole("button", { name: "Translation sources" }),
    );
    await user.click(
      await screen.findByText("Limit the search to a folder (optional)"),
    );
    const folder = screen.getByRole("textbox", {
      name: "Localization root (optional)",
    });
    await user.type(folder, "app/translations");
    await user.click(
      within(steps).getByRole("button", { name: "Preview and import" }),
    );
    expect(
      screen.getByRole("alertdialog", { name: "Leave without saving?" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(folder).toHaveValue("app/translations");
    await user.click(
      screen.getByRole("button", { name: "Next: Preview and import" }),
    );
    expect(await screen.findByText("Mapping not saved")).toBeVisible();
    expect(folder).toHaveValue("app/translations");
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 3 of 4",
    );
    expect(createAdminCandidateMappingMock).not.toHaveBeenCalled();
  });

  it("embeds the real preview in one combined final setup step", async () => {
    getAdminProductMock.mockResolvedValue(ok(activeProduct));
    listAdminRevisionMappingsMock.mockResolvedValue(
      ok({ items: [directMapping], next_cursor: null }),
    );
    vi.mocked(getAdminLatestCandidatePreviewJob).mockResolvedValue({
      data: undefined,
    } as never);
    renderWizard(activeProduct);
    const steps = screen.getByRole("navigation", {
      name: "Product setup steps",
    });
    expect(within(steps).getAllByRole("button")).toHaveLength(4);
    await userEvent.click(
      within(steps).getByRole("button", { name: "Preview and import" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Preview and import" }),
    ).toBeVisible();
    await waitFor(() =>
      expect(getAdminLatestCandidatePreviewJob).toHaveBeenCalled(),
    );
    expect(
      screen.queryByRole("link", { name: "Open product preview" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 4 of 4",
    );
  });

  beforeEach(() => {
    getAdminProductSummaryMock.mockImplementation(async (request) =>
      ok({ ...productSummary, product_id: request!.path.product_id }),
    );
    intersectionObservers.splice(0);
    vi.mocked(getAdminBitbucketWorkspace).mockResolvedValue(
      ok({ workspace: applicationRepository.workspace }),
    );
    vi.mocked(getAdminRepository).mockImplementation(async (options) =>
      ok(
        options.path.repository_id === applicationRepository.id
          ? applicationRepository
          : translationRepository,
      ),
    );
    vi.mocked(listAdminBitbucketRepositories).mockImplementation(async () =>
      ok({
        workspace: applicationRepository.workspace,
        items: [applicationRepository, translationRepository].map((item) => ({
          workspace: item.workspace,
          repository_slug: item.repository_slug,
          name: item.descriptive_name ?? item.repository_slug,
        })),
        next_cursor: null,
      }),
    );
    vi.mocked(selectAdminBitbucketRepository).mockImplementation(
      async (options) =>
        ok(
          options.path.repository_slug === applicationRepository.repository_slug
            ? applicationRepository
            : translationRepository,
        ),
    );
    createAdminCandidateMappingMock.mockReset();
    vi.mocked(updateAdminCandidateMapping).mockReset();
    createAdminProductMock.mockReset();
    createAdminRepositoryMock.mockReset();
    deactivateAdminProductMock.mockReset();
    deleteAdminProductMock.mockReset();
    vi.mocked(getAdminLatestCandidatePreviewJob).mockReset();
    vi.mocked(getAdminLatestCandidatePreviewJob).mockResolvedValue({
      data: undefined,
    } as never);
    getAdminProductMock.mockReset();
    getAdminProductMock.mockResolvedValue(ok(activeProduct));
    getAdminRepositoryBranchMock.mockReset();
    listAdminCandidateMappingsMock.mockReset();
    listAdminCandidateMappingsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    listAdminPublishedMappingImportsMock.mockReset();
    listAdminPublishedMappingImportsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    listAdminProductsMock.mockReset();
    listAdminProductsMock.mockResolvedValue(
      ok({ items: [activeProduct, candidateOnlyProduct], next_cursor: null }),
    );
    listAdminRepositoriesMock.mockReset();
    listAdminRepositoriesMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    listAdminRepositoryBranchesMock.mockReset();
    listAdminRepositoryBranchesMock.mockResolvedValue(ok(liveBranches));
    listAdminRevisionMappingsMock.mockReset();
    listAdminRevisionMappingsMock.mockResolvedValue(
      ok({ items: [directMapping], next_cursor: null }),
    );
    readSystemStatusMock.mockReset();
    readSystemStatusMock.mockReturnValue(new Promise<never>(() => undefined));
    useSessionMock.mockReset();
    useSessionMock.mockReturnValue({
      changePassword: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
      restoreSession: vi.fn(),
      state: {
        status: "authenticated",
        accessToken: "memory-only-admin-bearer",
        principal: {
          id: "00000000-0000-4000-8000-000000000001",
          email: "admin@example.com",
          display_name: "Admin",
          must_change_password: false,
          roles: ["admin"],
        },
      },
    });
    updateAdminProductCandidateMock.mockReset();
    toastSuccessMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders stable loading, bounded retry, and exact empty collection states", async () => {
    let resolveRetry:
      | ((
          value: ReturnType<
            typeof ok<{
              items: AdminProductResponse[];
              next_cursor: string | null;
            }>
          >,
        ) => void)
      | undefined;
    const pendingRetry = new Promise<
      ReturnType<
        typeof ok<{
          items: AdminProductResponse[];
          next_cursor: string | null;
        }>
      >
    >((resolve) => {
      resolveRetry = resolve;
    });
    listAdminProductsMock.mockReturnValueOnce(
      new Promise<never>(() => undefined),
    );
    const loadingView = renderProducts();

    expect(screen.getByRole("heading", { name: "Products" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Loading products");
    expect(
      screen.queryByRole("textbox", { name: "Search products" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Create product" }),
    ).toHaveAttribute("aria-disabled", "true");
    expect(
      screen.getByRole("link", { name: "Create product" }),
    ).toHaveAttribute("tabindex", "-1");
    expect(
      screen.getByRole("link", { name: "Create product" }),
    ).toHaveAttribute("href", "/");
    await userEvent.click(screen.getByRole("link", { name: "Create product" }));
    expect(screen.getByTestId("current-location")).toHaveTextContent("/");
    await waitFor(() => expect(listAdminProductsMock).toHaveBeenCalledOnce());

    loadingView.unmount();
    listAdminProductsMock.mockRejectedValueOnce(
      new Error("provider response containing Secret-That-Must-Not-Leak"),
    );
    listAdminProductsMock.mockReturnValueOnce(pendingRetry);
    renderProducts();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Products unavailable");
    expect(alert).not.toHaveTextContent("Secret-That-Must-Not-Leak");
    await userEvent.click(
      screen.getByRole("button", { name: "Retry loading page" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Loading products",
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await act(async () => {
      resolveRetry?.(ok({ items: [], next_cursor: null }));
    });

    expect(
      await screen.findByRole("heading", { name: "No products configured" }),
    ).toBeVisible();
    expect(screen.getByTestId("products-empty-icon")).toBeVisible();
    expect(
      screen
        .getByRole("heading", { name: "No products configured" })
        .closest("section"),
    ).toHaveClass("place-items-center", "text-center");
    expect(
      screen.queryByRole("button", { name: "Load more products" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "Create a product to connect repositories and validate a localization layout.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Create product" }),
    ).toHaveAttribute("aria-disabled", "false");
    expect(
      screen.getByRole("link", { name: "Create product" }),
    ).not.toHaveAttribute("tabindex");
    expect(
      screen.getByRole("link", { name: "Create product" }),
    ).toHaveAttribute("href", "/admin/products/new");
  });

  it("keeps name, status, fixed pages, cursor, and API row order server-owned", async () => {
    listAdminProductsMock
      .mockResolvedValueOnce(
        ok({
          items: [activeProduct, candidateOnlyProduct],
          next_cursor: "next-products",
        }),
      )
      .mockResolvedValueOnce(ok({ items: [activeProduct], next_cursor: null }))
      .mockResolvedValueOnce(
        ok({ items: [inactivePublishedProduct], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        ok({ items: [candidateOnlyProduct], next_cursor: null }),
      );
    renderProducts();

    const table = await screen.findByRole("table", { name: "Products" });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(
      within(table)
        .getAllByRole("row")
        .slice(1)
        .map((row) => row.textContent),
    ).toEqual([
      expect.stringContaining("Zulu Mobile"),
      expect.stringContaining("Alpha Embedded"),
    ]);
    expect(listAdminProductsMock).toHaveBeenNthCalledWith(1, {
      auth: "memory-only-admin-bearer",
      query: { cursor: null, limit: 50, name: null, status: null },
    });
    expect(
      screen.queryByRole("combobox", { name: "Products per page" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Product status" })).toBeVisible();
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await waitFor(() =>
      expect(intersectionObservers.length).toBeGreaterThan(0),
    );
    act(() => intersectionObservers.at(-1)?.intersect());
    await waitFor(() => {
      expect(listAdminProductsMock).toHaveBeenNthCalledWith(2, {
        auth: "memory-only-admin-bearer",
        query: {
          cursor: "next-products",
          limit: 50,
          name: null,
          status: null,
        },
      });
    });
    expect(
      within(table)
        .getAllByRole("row")
        .slice(1)
        .map((row) => row.textContent),
    ).toEqual([
      expect.stringContaining("Zulu Mobile"),
      expect.stringContaining("Alpha Embedded"),
      expect.stringContaining("Zulu Mobile"),
    ]);

    await userEvent.click(screen.getByRole("button", { name: "Inactive" }));
    await waitFor(() => {
      expect(listAdminProductsMock).toHaveBeenNthCalledWith(3, {
        auth: "memory-only-admin-bearer",
        query: { cursor: null, limit: 50, name: null, status: "inactive" },
      });
    });

    await userEvent.type(
      screen.getByRole("textbox", { name: "Search products" }),
      "  Alpha  ",
    );
    await waitFor(() => {
      expect(listAdminProductsMock).toHaveBeenNthCalledWith(4, {
        auth: "memory-only-admin-bearer",
        query: { cursor: null, limit: 50, name: "Alpha", status: "inactive" },
      });
    });
  });

  it("keeps the search mounted and focused while filtered results refresh", async () => {
    let resolveSearch:
      | ((
          value: ReturnType<
            typeof ok<{
              items: AdminProductResponse[];
              next_cursor: string | null;
            }>
          >,
        ) => void)
      | undefined;
    const pendingSearch = new Promise<
      ReturnType<
        typeof ok<{
          items: AdminProductResponse[];
          next_cursor: string | null;
        }>
      >
    >((resolve) => {
      resolveSearch = resolve;
    });
    listAdminProductsMock
      .mockResolvedValueOnce(ok({ items: [activeProduct], next_cursor: null }))
      .mockReturnValueOnce(pendingSearch);
    renderProducts();

    await screen.findByRole("table", { name: "Products" });
    const search = screen.getByRole("textbox", { name: "Search products" });
    await userEvent.type(search, "Zulu");
    await waitFor(() => expect(listAdminProductsMock).toHaveBeenCalledTimes(2));

    expect(search.isConnected).toBe(true);
    expect(screen.getByRole("textbox", { name: "Search products" })).toBe(
      search,
    );
    expect(search).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent("Updating products");
    expect(screen.getByRole("table", { name: "Products" })).toBeVisible();

    await act(async () => {
      resolveSearch?.(ok({ items: [activeProduct], next_cursor: null }));
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(search).toHaveFocus();
  });

  it("uses a semantic table at 768px and an ordered stacked list below it without page overflow", async () => {
    listAdminProductsMock.mockResolvedValueOnce(
      ok({
        items: [activeProduct, candidateOnlyProduct, inactivePublishedProduct],
        next_cursor: null,
      }),
    );
    renderProducts();

    const table = await screen.findByRole("table", { name: "Products" });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Load more products" }),
    ).not.toBeInTheDocument();
    expect(table.parentElement?.parentElement).toHaveClass(
      "hidden",
      "md:block",
    );
    const mobileList = screen.getByLabelText("Products mobile list");
    expect(mobileList).toHaveClass("md:hidden", "min-w-0", "max-w-full");
    expect(mobileList.closest("section")).toHaveClass(
      "min-w-0",
      "max-w-full",
      "overflow-x-clip",
    );
    expect(
      within(mobileList)
        .getAllByRole("article")
        .map((row) => row.textContent),
    ).toEqual([
      expect.stringContaining("Zulu Mobile"),
      expect.stringContaining("Alpha Embedded"),
      expect.stringContaining("Middle Desktop"),
    ]);
    expect(within(table).getByText("Published version 4")).toBeVisible();
    expect(within(table).getByText("Draft version 5")).toBeVisible();
    expect(within(table).getByText("Not published")).toBeVisible();
    expect(within(table).getByText("No draft")).toBeVisible();
    expect(
      within(table).getByRole("link", { name: activeProduct.name }),
    ).toHaveAttribute("href", `/admin/products/${activeProduct.id}/overview`);
    const [activeBadge] = within(table).getAllByText("Active", {
      selector: "[data-slot=badge]",
    });
    expect(activeBadge).toHaveAttribute("data-variant", "success");
    const inactiveBadges = within(table).getAllByText("Inactive", {
      selector: "[data-slot=badge]",
    });
    expect(inactiveBadges).toHaveLength(2);
    for (const inactiveBadge of inactiveBadges) {
      expect(inactiveBadge).toHaveAttribute("data-variant", "warning");
    }
    expect(
      within(mobileList).getByRole("link", { name: activeProduct.name }),
    ).toHaveAttribute("href", `/admin/products/${activeProduct.id}/overview`);
  });

  it("keeps paged and filtered loading transitions bounded and single-flight", async () => {
    let resolveMore:
      | ((
          value: ReturnType<
            typeof ok<{
              items: AdminProductResponse[];
              next_cursor: string | null;
            }>
          >,
        ) => void)
      | undefined;
    const pendingMore = new Promise<
      ReturnType<
        typeof ok<{
          items: AdminProductResponse[];
          next_cursor: string | null;
        }>
      >
    >((resolve) => {
      resolveMore = resolve;
    });
    listAdminProductsMock
      .mockResolvedValueOnce(
        ok({ items: [activeProduct], next_cursor: "next-products" }),
      )
      .mockReturnValueOnce(pendingMore)
      .mockReturnValueOnce(new Promise<never>(() => undefined));
    renderProducts();
    await screen.findByRole("table", { name: "Products" });
    await waitFor(() =>
      expect(intersectionObservers.length).toBeGreaterThan(0),
    );
    act(() => {
      intersectionObservers.at(-1)?.intersect();
      intersectionObservers.at(-1)?.intersect();
    });
    expect(listAdminProductsMock).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading more products",
    );
    await act(async () => {
      resolveMore?.(
        ok({
          items: [candidateOnlyProduct],
          next_cursor: "after-more-products",
        }),
      );
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Active" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Updating products",
    );
    expect(
      screen.getByRole("link", { name: "Create product" }),
    ).toHaveAttribute("aria-disabled", "false");
  });

  it("fails closed on generated no-data responses and ignores superseded product pages", async () => {
    listAdminProductsMock.mockResolvedValueOnce(failure());
    renderProducts();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Products unavailable",
    );
    cleanup();

    let resolveFirst:
      | ((
          value: ReturnType<
            typeof ok<{
              items: AdminProductResponse[];
              next_cursor: null;
            }>
          >,
        ) => void)
      | undefined;
    const firstLoad = new Promise<
      ReturnType<
        typeof ok<{ items: AdminProductResponse[]; next_cursor: null }>
      >
    >((resolve) => {
      resolveFirst = resolve;
    });
    listAdminProductsMock
      .mockReturnValueOnce(firstLoad)
      .mockResolvedValueOnce(
        ok({ items: [candidateOnlyProduct], next_cursor: null }),
      );
    const view = render(
      <MemoryRouter>
        <ProductsPage accessToken="first-product-authority" />
      </MemoryRouter>,
    );
    await waitFor(() => expect(listAdminProductsMock).toHaveBeenCalledOnce());
    view.rerender(
      <MemoryRouter>
        <ProductsPage accessToken="replacement-product-authority" />
      </MemoryRouter>,
    );
    expect(await screen.findAllByText(candidateOnlyProduct.name)).toHaveLength(
      2,
    );

    await act(async () => {
      resolveFirst?.(ok({ items: [activeProduct], next_cursor: null }));
    });
    expect(screen.queryByText(activeProduct.name)).not.toBeInTheDocument();

    cleanup();
    let rejectStale: ((reason?: unknown) => void) | undefined;
    const staleRejection = new Promise<
      ReturnType<
        typeof ok<{ items: AdminProductResponse[]; next_cursor: null }>
      >
    >((_resolve, reject) => {
      rejectStale = reject;
    });
    listAdminProductsMock.mockReset();
    listAdminProductsMock
      .mockReturnValueOnce(staleRejection)
      .mockResolvedValueOnce(ok({ items: [activeProduct], next_cursor: null }));
    const rejectionView = render(
      <MemoryRouter>
        <ProductsPage accessToken="stale-rejection-authority" />
      </MemoryRouter>,
    );
    await waitFor(() => expect(listAdminProductsMock).toHaveBeenCalledOnce());
    rejectionView.rerender(
      <MemoryRouter>
        <ProductsPage accessToken="current-rejection-authority" />
      </MemoryRouter>,
    );
    expect(await screen.findAllByText(activeProduct.name)).toHaveLength(2);
    await act(async () => {
      rejectStale?.(new Error("stale provider detail"));
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    cleanup();
    listAdminProductsMock.mockReset();
    const unmountedView = renderProducts();
    unmountedView.unmount();
    await act(async () => Promise.resolve());
    expect(listAdminProductsMock).not.toHaveBeenCalled();
  });

  it("renders exactly four responsive wizard steps with current and completed semantics", async () => {
    renderWizard(activeProduct);

    expect(
      screen.getByRole("heading", { name: activeProduct.name }),
    ).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue(
      activeProduct.name,
    );
    expect(screen.getByRole("textbox", { name: "Description" })).toHaveValue(
      activeProduct.candidate_revision?.description,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    const desktop = screen.getByRole("navigation", {
      name: "Product setup steps",
    });
    expect(
      screen
        .getByRole("heading", { name: activeProduct.name })
        .closest("section"),
    ).toHaveClass("mx-auto", "w-full", "max-w-3xl");
    expect(
      within(desktop)
        .getAllByRole("button")
        .map((step) => step.textContent),
    ).toEqual([
      "Product details",
      "Repositories",
      "Translation sources",
      "Preview and import",
    ]);
    for (const step of within(desktop).getAllByRole("button")) {
      expect(step).toHaveClass("whitespace-normal", "break-words");
    }
    expect(
      within(desktop).getByRole("button", {
        name: "Product details",
        current: "step",
      }),
    ).toBeVisible();
    expect(
      within(desktop).getByRole("button", { name: "Product details" }),
    ).not.toHaveAttribute("data-completed");
    for (const label of [
      "Repositories",
      "Translation sources",
      "Preview and import",
    ]) {
      expect(
        within(desktop).getByRole("button", { name: label }),
      ).not.toHaveAttribute("aria-current");
      expect(
        within(desktop).getByRole("button", { name: label }),
      ).not.toHaveAttribute("data-completed");
    }
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 1 of 4Product details",
    );
    await userEvent.click(
      within(desktop).getByRole("button", { name: "Product details" }),
    );
    expect(
      screen.queryByRole("alertdialog", { name: "Leave without saving?" }),
    ).not.toBeInTheDocument();

    const description = screen.getByRole("textbox", { name: "Description" });
    await userEvent.clear(description);
    await userEvent.type(description, "Changed candidate details");
    await userEvent.click(
      within(desktop).getByRole("button", { name: "Product details" }),
    );
    expect(
      screen.queryByRole("alertdialog", { name: "Leave without saving?" }),
    ).not.toBeInTheDocument();
    await userEvent.click(
      within(desktop).getByRole("button", { name: "Repositories" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Discard changes" }),
    );

    expect(
      within(desktop).getByRole("button", {
        name: "Repositories",
        current: "step",
      }),
    ).toBeVisible();
    expect(
      within(desktop).getByRole("button", { name: "Product details" }),
    ).toHaveAttribute("data-completed", "true");
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 2 of 4Repositories",
    );
    expect(
      screen.getByRole("heading", { name: "Connect a Bitbucket repository" }),
    ).toBeVisible();
    expect(
      await screen.findByRole("searchbox", { name: "Search repositories" }),
    ).toBeVisible();

    await userEvent.click(
      within(desktop).getByRole("button", { name: "Translation sources" }),
    );
    expect(screen.getByText("Configure a translation source")).toBeVisible();
    await userEvent.click(
      within(desktop).getByRole("button", { name: "Preview and import" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Preview and import" }),
    ).toBeVisible();
    await waitFor(() =>
      expect(getAdminLatestCandidatePreviewJob).toHaveBeenCalled(),
    );
    expect(
      screen.queryByRole("link", { name: "Open product preview" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 4 of 4Preview and import",
    );
    expect(
      within(desktop).getByRole("button", { name: "Preview and import" }),
    ).not.toHaveAttribute("data-completed");
    expect(
      within(desktop)
        .getAllByRole("button")
        .slice(0, 3)
        .every((step) => step.dataset.completed === "true"),
    ).toBe(true);
  });

  it("loads every revision mapping cursor before restoring wizard repository selections", async () => {
    const firstPage = Array.from({ length: 50 }, (_, index) => ({
      ...directMapping,
      id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
      primary_repository_id: `repository-${String(index + 1).padStart(3, "0")}`,
    }));
    const finalMapping = {
      ...directMapping,
      id: "00000000-0000-4000-8000-000000000451",
      primary_repository_id: "repository-051",
    };
    listAdminRevisionMappingsMock
      .mockResolvedValueOnce(
        ok({ items: firstPage, next_cursor: "opaque-revision-page-2" }),
      )
      .mockResolvedValueOnce(ok({ items: [finalMapping], next_cursor: null }));

    const loaded = await loadEditableProduct(
      "memory-only-admin-bearer",
      activeProduct.id,
    );

    expect(loaded.mappedRepositoryIds).toHaveLength(51);
    expect(loaded.mappedRepositoryIds.at(-1)).toBe("repository-051");
    expect(listAdminRevisionMappingsMock).toHaveBeenNthCalledWith(1, {
      auth: "memory-only-admin-bearer",
      path: {
        product_id: activeProduct.id,
        revision_id: activeProduct.candidate_revision!.id,
      },
      query: { cursor: null, limit: 50 },
      signal: expect.any(AbortSignal),
    });
    expect(listAdminRevisionMappingsMock).toHaveBeenNthCalledWith(2, {
      auth: "memory-only-admin-bearer",
      path: {
        product_id: activeProduct.id,
        revision_id: activeProduct.candidate_revision!.id,
      },
      query: { cursor: "opaque-revision-page-2", limit: 50 },
      signal: expect.any(AbortSignal),
    });
  });

  it("fails closed across editable-product pagination and cancellation boundaries", async () => {
    getAdminProductMock.mockResolvedValueOnce(ok(undefined as never));
    await expect(
      loadEditableProduct("memory-only-admin-bearer", activeProduct.id),
    ).rejects.toThrow("product unavailable");

    getAdminProductMock.mockResolvedValueOnce(
      ok({ ...activeProduct, active_revision: null, candidate_revision: null }),
    );
    await expect(
      loadEditableProduct("memory-only-admin-bearer", activeProduct.id),
    ).resolves.toEqual({
      mappedRepositoryIds: [],
      product: {
        ...activeProduct,
        active_revision: null,
        candidate_revision: null,
      },
    });

    const alreadyAborted = new AbortController();
    alreadyAborted.abort();
    await expect(
      loadEditableProduct(
        "memory-only-admin-bearer",
        activeProduct.id,
        alreadyAborted.signal,
      ),
    ).rejects.toMatchObject({ name: "AbortError" });

    const abortedDuringPage = new AbortController();
    listAdminRevisionMappingsMock.mockImplementationOnce(async () => {
      abortedDuringPage.abort();
      return ok({ items: [], next_cursor: null });
    });
    await expect(
      loadEditableProduct(
        "memory-only-admin-bearer",
        activeProduct.id,
        abortedDuringPage.signal,
      ),
    ).rejects.toMatchObject({ name: "AbortError" });

    listAdminRevisionMappingsMock.mockResolvedValueOnce(ok(undefined as never));
    await expect(
      loadEditableProduct("memory-only-admin-bearer", activeProduct.id),
    ).rejects.toThrow("product mappings unavailable");

    listAdminRevisionMappingsMock
      .mockResolvedValueOnce(
        ok({ items: [directMapping], next_cursor: "repeated-cursor" }),
      )
      .mockResolvedValueOnce(
        ok({ items: [directMapping], next_cursor: "repeated-cursor" }),
      );
    await expect(
      loadEditableProduct("memory-only-admin-bearer", activeProduct.id),
    ).rejects.toThrow("product mappings repeated cursor");

    let page = 0;
    listAdminRevisionMappingsMock.mockImplementation(async () =>
      ok({ items: [], next_cursor: `cursor-${++page}` }),
    );
    await expect(
      loadEditableProduct("memory-only-admin-bearer", activeProduct.id),
    ).rejects.toThrow("product mappings exceeded page limit");

    const abortedAfterCursor = new AbortController();
    listAdminRevisionMappingsMock.mockReset();
    listAdminRevisionMappingsMock.mockResolvedValueOnce(
      ok({
        items: [],
        get next_cursor() {
          abortedAfterCursor.abort();
          return null;
        },
      }),
    );
    await expect(
      loadEditableProduct(
        "memory-only-admin-bearer",
        activeProduct.id,
        abortedAfterCursor.signal,
      ),
    ).rejects.toMatchObject({ name: "AbortError" });
  });

  it("retries a bounded route-load failure and ignores obsolete product authority", async () => {
    getAdminProductMock
      .mockRejectedValueOnce(new Error("bounded route failure"))
      .mockResolvedValueOnce(ok(activeProduct));
    const failed = renderRouteWizard();
    expect(await screen.findByText("Product draft unavailable")).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Retry loading page" }),
    );
    expect(await screen.findByRole("textbox", { name: "Name" })).toHaveValue(
      activeProduct.name,
    );
    failed.unmount();

    let resolveObsolete!: (
      value: ReturnType<typeof ok<AdminProductResponse>>,
    ) => void;
    getAdminProductMock
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveObsolete = resolve;
        }) as never,
      )
      .mockResolvedValueOnce(ok(candidateOnlyProduct));
    const view = renderRouteWizard("obsolete-authority");
    await waitFor(() => expect(getAdminProductMock).toHaveBeenCalledTimes(3));
    view.rerender(
      <RouterProvider
        router={createRouteWizardRouter("successor-authority")}
      />,
    );
    expect(await screen.findByRole("textbox", { name: "Name" })).toHaveValue(
      candidateOnlyProduct.name,
    );
    resolveObsolete(
      ok({ ...activeProduct, active_revision: null, candidate_revision: null }),
    );
    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue(
        candidateOnlyProduct.name,
      );
    });
  });

  it.each(["Name", "Description"])(
    "blocks routed shell navigation for a dirty %s and preserves its values on cancel",
    async (fieldName) => {
      const { router } = renderRoutedProductDetails();
      const user = userEvent.setup();
      const name = screen.getByRole("textbox", { name: "Name" });
      const description = screen.getByRole("textbox", { name: "Description" });
      const field = screen.getByRole("textbox", { name: fieldName });
      await user.type(field, " unsaved");
      const usersLink = screen.getAllByRole("link", { name: "Users" })[0];
      await user.click(usersLink);

      const dialog = await screen.findByRole("alertdialog", {
        name: "Leave without saving?",
      });
      expect(dialog).toHaveTextContent(
        "Your unsaved entries on this page will be lost.",
      );
      expect(router.state.location.pathname).toBe(
        `/admin/products/${activeProduct.id}/edit`,
      );
      await user.click(
        within(dialog).getByRole("button", { name: "Keep editing" }),
      );
      await waitFor(() => expect(usersLink).toHaveFocus());
      expect(name).toHaveValue(
        fieldName === "Name"
          ? `${activeProduct.name} unsaved`
          : activeProduct.name,
      );
      expect(description).toHaveValue(
        fieldName === "Description"
          ? `${activeProduct.candidate_revision?.description} unsaved`
          : activeProduct.candidate_revision?.description,
      );

      const beforeUnload = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(beforeUnload);
      expect(beforeUnload.defaultPrevented).toBe(true);
    },
  );

  it("blocks browser Back before unmount and discards exactly the stored product route", async () => {
    const editPath = `/admin/products/${activeProduct.id}/edit`;
    const { router } = renderRoutedProductDetails({
      initialEntries: ["/admin/users", editPath],
      initialIndex: 1,
    });
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox", { name: "Name" }), " dirty");

    await router.navigate(-1);
    expect(
      await screen.findByRole("alertdialog", { name: "Leave without saving?" }),
    ).toBeVisible();
    expect(router.state.location.pathname).toBe(editPath);
    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/admin/users"),
    );
    expect(
      screen.getByRole("heading", { name: "Users destination" }),
    ).toBeVisible();
  });

  it("cancels a queued route load before it reaches the generated client", async () => {
    getAdminProductMock.mockClear();
    const view = renderRouteWizard();
    view.unmount();
    await act(async () => Promise.resolve());
    expect(getAdminProductMock).not.toHaveBeenCalled();
  });

  it("ignores a rejected route load after authority is replaced", async () => {
    let rejectObsolete!: (reason: Error) => void;
    getAdminProductMock
      .mockReturnValueOnce(
        new Promise((_resolve, reject) => {
          rejectObsolete = reject;
        }) as never,
      )
      .mockResolvedValueOnce(ok(candidateOnlyProduct));
    const view = renderRouteWizard("obsolete-authority");
    await waitFor(() => expect(getAdminProductMock).toHaveBeenCalledOnce());
    view.rerender(
      <RouterProvider
        router={createRouteWizardRouter("successor-authority")}
      />,
    );
    expect(await screen.findByRole("textbox", { name: "Name" })).toHaveValue(
      candidateOnlyProduct.name,
    );
    rejectObsolete(new Error("stale route failure"));
    await act(async () => Promise.resolve());
    expect(
      screen.queryByText("Product draft unavailable"),
    ).not.toBeInTheDocument();
  });

  it("bounds products without revisions and responses without candidate authority", async () => {
    const orphan = {
      ...activeProduct,
      active_revision: null,
      candidate_revision: null,
    };
    const first = renderWizard(orphan);
    await userEvent.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );
    expect(await screen.findByText("Draft not saved")).toBeVisible();
    expect(updateAdminProductCandidateMock).not.toHaveBeenCalled();
    first.unmount();

    updateAdminProductCandidateMock.mockResolvedValueOnce(
      ok(activeWithoutCandidateProduct),
    );
    renderWizard(activeWithoutCandidateProduct);
    await userEvent.type(
      screen.getByRole("textbox", { name: "Name" }),
      " changed",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );
    expect(await screen.findByText("Draft not saved")).toBeVisible();
  });

  it("uses mobile next and back controls with repository step validation", async () => {
    exposeTask2Repositories();
    updateAdminProductCandidateMock.mockResolvedValueOnce(ok(activeProduct));
    renderWizard(activeProduct);

    await userEvent.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Connect a Bitbucket repository",
      }),
    ).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("textbox", { name: "Name" })).toBeVisible();

    await userEvent.click(
      screen
        .getByRole("navigation", { name: "Product setup steps" })
        .querySelectorAll("button")[1],
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Next: Translation sources" }),
    );
    expect(await screen.findByText("Complete this step")).toBeVisible();
    await userEvent.click(
      (
        await screen.findAllByRole("button", {
          name: "Connect Mobile application source",
        })
      )[0],
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Next: Translation sources" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Translation sources" }),
    ).toBeVisible();

    await userEvent.click(
      screen
        .getByRole("navigation", { name: "Product setup steps" })
        .querySelectorAll("button")[3],
    );
    expect(
      screen.queryByRole("button", { name: "Next" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 4 of 4",
    );

    await userEvent.click(
      screen
        .getByRole("navigation", { name: "Product setup steps" })
        .querySelectorAll("button")[0],
    );
    const firstBack = screen.getByRole("button", { name: "Back" });
    expect(firstBack).toBeDisabled();
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 1 of 4",
    );
  });

  it("deduplicates both sides of separate mappings", async () => {
    listAdminRevisionMappingsMock.mockResolvedValueOnce(
      ok({
        items: [
          directMapping,
          {
            ...directMapping,
            id: "00000000-0000-4000-8000-000000000499",
            topology: "separate",
            translations_repository_id: translationRepository.id,
            translations_source_branch: "translations/main",
          },
        ],
        next_cursor: null,
      }),
    );

    const loaded = await loadEditableProduct(
      "memory-only-admin-bearer",
      activeProduct.id,
    );
    expect(loaded.mappedRepositoryIds).toEqual([
      applicationRepository.id,
      translationRepository.id,
    ]);
  });

  it("keeps all four wizard steps reachable through persistent 320px keyboard and pointer controls", async () => {
    exposeTask2Repositories();
    listAdminCandidateMappingsMock.mockResolvedValue(
      ok({ items: [directMapping], next_cursor: null }),
    );
    renderWizard(activeProduct);
    const user = userEvent.setup();

    const wizard = screen
      .getByRole("heading", { name: activeProduct.name })
      .closest("section");
    expect(wizard).toHaveClass("min-w-0", "max-w-3xl", "overflow-x-clip");
    const mobileNavigation = screen.getByRole("navigation", {
      name: "Wizard navigation",
    });
    expect(mobileNavigation).not.toHaveClass("md:hidden");
    expect(
      within(mobileNavigation).getByRole("button", { name: "Back" }),
    ).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Repositories" }));
    const nextToMappings = within(mobileNavigation).getByRole("button", {
      name: "Next: Translation sources",
    });
    nextToMappings.focus();
    await user.keyboard("{Enter}");
    const validationAlert = await screen.findByRole("alert", {
      name: "Wizard step incomplete",
    });
    expect(validationAlert).toHaveTextContent(
      "Select a repository before continuing.",
    );
    expect(validationAlert).toHaveFocus();
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 2 of 4Repositories",
    );

    await user.click(
      screen.getAllByRole("button", {
        name: "Connect Mobile application source",
      })[0],
    );
    await user.click(nextToMappings);
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 3 of 4Translation sources",
    );

    await user.keyboard("{Tab}");
    await user.click(
      within(mobileNavigation).getByRole("button", {
        name: "Next: Preview and import",
      }),
    );
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 4 of 4Preview and import",
    );
    expect(
      within(mobileNavigation).queryByRole("button", { name: "Next" }),
    ).not.toBeInTheDocument();

    for (const expectedStep of [3, 2, 1]) {
      await user.click(
        within(mobileNavigation).getByRole("button", { name: "Back" }),
      );
      expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
        `Step ${expectedStep} of 4`,
      );
    }
  });

  it("navigates unchanged details directly and guards name-only edits", async () => {
    renderWizard(activeProduct);
    const user = userEvent.setup();
    const repositories = screen.getByRole("button", { name: "Repositories" });
    await user.click(repositories);
    expect(
      screen.queryByRole("alertdialog", { name: "Leave without saving?" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 2 of 4Repositories",
    );

    await user.click(screen.getByRole("button", { name: "Product details" }));
    await user.type(screen.getByRole("textbox", { name: "Name" }), " changed");
    await user.click(repositories);
    expect(
      screen.getByRole("alertdialog", { name: "Leave without saving?" }),
    ).toBeVisible();
  });

  it("creates a product with an optional description and announces Draft saved only after the response", async () => {
    const canonicalCreatedProduct: AdminProductResponse = {
      ...candidateOnlyProduct,
      name: "Canonical Embedded Product",
      candidate_revision: {
        ...candidateOnlyProduct.candidate_revision!,
        description: "Canonical server description",
        name: "Canonical Embedded Product",
      },
    };
    let resolveCreate:
      | ((value: ReturnType<typeof ok<AdminProductResponse>>) => void)
      | undefined;
    const pendingCreate = new Promise<
      ReturnType<typeof ok<AdminProductResponse>>
    >((resolve) => {
      resolveCreate = resolve;
    });
    createAdminProductMock.mockReturnValueOnce(pendingCreate);
    renderWizard();
    const user = userEvent.setup();
    for (const label of [
      "Repositories",
      "Translation sources",
      "Preview and import",
    ]) {
      expect(screen.getByRole("button", { name: label })).toBeDisabled();
    }
    expect(
      screen.getByRole("button", { name: "Product details" }),
    ).toBeEnabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );
    const name = screen.getByRole("textbox", { name: "Name" });
    expect(name).toHaveFocus();
    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(name).toHaveAttribute(
      "aria-describedby",
      `${name.getAttribute("id")}-error`,
    );
    expect(screen.getByText("Enter a product name.")).toBeVisible();
    expect(screen.getByText("Enter a product name.")).toHaveAttribute(
      "id",
      `${name.getAttribute("id")}-error`,
    );
    expect(createAdminProductMock).not.toHaveBeenCalled();

    await user.type(name, "   ");
    await user.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );
    expect(name).toHaveFocus();
    expect(createAdminProductMock).not.toHaveBeenCalled();
    await user.clear(name);
    await user.type(name, "Alpha Embedded");
    expect(name).toHaveAttribute("aria-invalid", "false");
    expect(name).not.toHaveAttribute("aria-describedby");
    expect(screen.queryByText("Enter a product name.")).not.toBeInTheDocument();
    await user.type(
      screen.getByRole("textbox", { name: "Description" }),
      "   ",
    );
    await user.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );
    expect(createAdminProductMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: { description: null, name: "Alpha Embedded" },
    });
    expect(toastSuccessMock).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "Next: Repositories" }),
    ).toBeDisabled();

    await act(async () => {
      resolveCreate?.(ok(canonicalCreatedProduct, 201));
    });

    expect(toastSuccessMock).toHaveBeenCalledWith("Draft saved");
    expect(
      screen.getByRole("button", { name: "Repositories", current: "step" }),
    ).toBeEnabled();
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 2 of 4Repositories",
    );
    await user.click(screen.getByRole("button", { name: "Product details" }));
    expect(
      screen.getByRole("heading", { name: canonicalCreatedProduct.name }),
    ).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue(
      canonicalCreatedProduct.name,
    );
    expect(screen.getByRole("textbox", { name: "Description" })).toHaveValue(
      canonicalCreatedProduct.candidate_revision?.description,
    );
    expect(
      screen.getByRole("button", { name: "Next: Repositories" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Next: Repositories" }),
    ).toHaveAttribute("aria-busy", "false");
    await user.click(screen.getByRole("button", { name: "Repositories" }));
    expect(
      screen.queryByRole("alertdialog", { name: "Leave without saving?" }),
    ).not.toBeInTheDocument();
  });

  it("focuses Name and preserves every attempted field on a duplicate-name conflict", async () => {
    createAdminProductMock
      .mockResolvedValueOnce(conflict())
      .mockReturnValueOnce(new Promise<never>(() => undefined));
    renderWizard();
    const user = userEvent.setup();
    const name = screen.getByRole("textbox", { name: "Name" });
    const description = screen.getByRole("textbox", { name: "Description" });

    await user.type(name, "Duplicate Product");
    await user.type(description, "Still recoverable");
    await user.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );

    expect(
      await screen.findByText("A product already uses this name."),
    ).toBeVisible();
    expect(name).toHaveFocus();
    expect(name).toHaveValue("Duplicate Product");
    expect(description).toHaveValue("Still recoverable");
    expect(toastSuccessMock).not.toHaveBeenCalled();
    await user.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );
    expect(
      screen.queryByText("A product already uses this name."),
    ).not.toBeInTheDocument();
    expect(name).toHaveAttribute("aria-invalid", "false");
    expect(
      screen.getByRole("button", { name: "Next: Repositories" }),
    ).toBeDisabled();
    await user.type(name, " revised");
    expect(name).toHaveAttribute("aria-invalid", "false");
    expect(
      screen.queryByText("A product already uses this name."),
    ).not.toBeInTheDocument();
  });

  it("fails closed on rejected creates and admits only one in-flight submission", async () => {
    createAdminProductMock.mockRejectedValueOnce(new Error("provider secret"));
    renderWizard();
    const name = screen.getByRole("textbox", { name: "Name" });
    await userEvent.type(name, "Recoverable Product");
    await userEvent.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not save this draft. Your entries are still here. Review the error and try again.",
    );
    expect(name).toHaveValue("Recoverable Product");
    expect(screen.getByRole("alert")).not.toHaveTextContent("provider secret");
    expect(
      screen.getByRole("button", { name: "Next: Repositories" }),
    ).toBeEnabled();
    await userEvent.type(name, " revised");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    createAdminProductMock.mockReturnValueOnce(
      new Promise<ReturnType<typeof ok<AdminProductResponse>>>(() => undefined),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await userEvent.type(
      screen.getByRole("textbox", { name: "Description" }),
      "still editable",
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    cleanup();
    createAdminProductMock.mockReset();

    createAdminProductMock.mockReturnValue(
      new Promise<ReturnType<typeof ok<AdminProductResponse>>>(() => undefined),
    );
    renderWizard();
    await userEvent.type(
      screen.getByRole("textbox", { name: "Name" }),
      "Single Flight Product",
    );
    const form = screen.getByRole("textbox", { name: "Name" }).closest("form");
    expect(form).not.toBeNull();
    const nativeSubmit = new Event("submit", {
      bubbles: true,
      cancelable: true,
    });
    expect(form!.dispatchEvent(nativeSubmit)).toBe(false);
    expect(nativeSubmit.defaultPrevented).toBe(true);
    fireEvent.submit(form!);

    expect(createAdminProductMock).toHaveBeenCalledOnce();
  });

  it("uses expected candidate version and preserves edits on conflict or failure", async () => {
    updateAdminProductCandidateMock
      .mockResolvedValueOnce(conflict())
      .mockResolvedValueOnce(failure());
    renderWizard(activeProduct);
    const user = userEvent.setup();
    const name = screen.getByRole("textbox", { name: "Name" });
    const description = screen.getByRole("textbox", { name: "Description" });

    await user.clear(name);
    await user.type(name, "Conflicting Product");
    await user.clear(description);
    await user.type(description, "Conflict-safe description");
    await user.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );

    expect(updateAdminProductCandidateMock).toHaveBeenNthCalledWith(1, {
      auth: "memory-only-admin-bearer",
      path: { product_id: activeProduct.id },
      body: {
        description: "Conflict-safe description",
        expected_candidate_version: 5,
        name: "Conflicting Product",
      },
    });
    expect(
      await screen.findByText("A product already uses this name."),
    ).toBeVisible();
    expect(name).toHaveFocus();
    expect(description).toHaveValue("Conflict-safe description");

    await user.clear(name);
    await user.type(name, "Rejected Product");
    await user.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not save this draft. Your entries are still here. Review the error and try again.",
    );
    expect(name).toHaveValue("Rejected Product");
    expect(description).toHaveValue("Conflict-safe description");
    expect(
      screen.getByRole("button", { name: "Next: Repositories" }),
    ).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Repositories" }));
    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    await user.click(screen.getByRole("button", { name: "Product details" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue(
      activeProduct.name,
    );
    expect(screen.getByRole("textbox", { name: "Description" })).toHaveValue(
      activeProduct.candidate_revision?.description,
    );
  });

  it("creates one candidate from an active revision only after a real details mutation", async () => {
    const createdCandidate = {
      ...inactivePublishedProduct,
      candidate_revision: {
        id: "00000000-0000-4000-8000-000000000205",
        description: inactivePublishedProduct.active_revision!.description,
        is_published: false,
        name: `${inactivePublishedProduct.name} candidate`,
        version: 3,
      },
    };
    updateAdminProductCandidateMock.mockResolvedValueOnce(ok(createdCandidate));
    renderWizard(inactivePublishedProduct);
    const user = userEvent.setup();
    expect(
      screen.getByRole("heading", { name: inactivePublishedProduct.name }),
    ).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Description" })).toHaveValue(
      inactivePublishedProduct.active_revision?.description,
    );
    expect(updateAdminProductCandidateMock).not.toHaveBeenCalled();
    await user.type(
      screen.getByRole("textbox", { name: "Name" }),
      " candidate",
    );
    await user.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );

    expect(updateAdminProductCandidateMock).toHaveBeenCalledOnce();
    expect(updateAdminProductCandidateMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { product_id: inactivePublishedProduct.id },
      body: {
        description: inactivePublishedProduct.active_revision?.description,
        expected_candidate_version: 2,
        name: `${inactivePublishedProduct.name} candidate`,
      },
    });
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 2 of 4Repositories",
    );
  });

  it("clears duplicate ownership when conflicted edits are discarded", async () => {
    updateAdminProductCandidateMock.mockResolvedValueOnce(conflict());
    renderWizard(activeProduct);
    const user = userEvent.setup();
    const name = screen.getByRole("textbox", { name: "Name" });
    await user.clear(name);
    await user.type(name, "Duplicate Candidate");
    await user.click(
      screen.getByRole("button", { name: "Next: Repositories" }),
    );
    expect(
      await screen.findByText("A product already uses this name."),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Repositories" }));
    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    await user.click(screen.getByRole("button", { name: "Product details" }));
    expect(
      screen.queryByText("A product already uses this name."),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue(
      activeProduct.name,
    );
  });

  it("guards dirty step navigation with the exact discard confirmation", async () => {
    renderWizard(activeProduct);
    const user = userEvent.setup();
    const description = screen.getByRole("textbox", { name: "Description" });
    await user.clear(description);
    await user.type(description, "Unsaved draft details");

    const repositories = screen.getByRole("button", { name: "Repositories" });
    await user.click(repositories);
    const dialog = screen.getByRole("alertdialog", {
      name: "Leave without saving?",
    });
    expect(dialog).toHaveTextContent(
      "Your unsaved entries on this page will be lost.",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Keep editing" }),
    );
    expect(description).toHaveValue("Unsaved draft details");
    expect(repositories).toHaveFocus();

    await user.type(screen.getByRole("textbox", { name: "Name" }), " changed");
    await user.click(repositories);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(repositories).toHaveFocus());
    expect(
      screen.queryByRole("alertdialog", { name: "Leave without saving?" }),
    ).not.toBeInTheDocument();

    await user.click(repositories);
    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 2 of 4Repositories",
    );
    await user.click(screen.getByRole("button", { name: "Product details" }));
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue(
      activeProduct.name,
    );
    expect(screen.getByRole("textbox", { name: "Description" })).toHaveValue(
      activeProduct.candidate_revision?.description,
    );
  });

  it.each(["no-import", "no-targets", "no-source"])(
    "explains unknown coverage without claiming completion (%s)",
    async (kind) => {
      getAdminProductSummaryMock.mockResolvedValueOnce(
        ok({
          ...productSummary,
          product_id: activeProduct.id,
          source_string_count: kind === "no-targets" ? 4 : 0,
          imported_scope_count: kind === "no-import" ? 0 : 1,
          unimported_scope_count: kind === "no-import" ? 1 : 0,
          expected_translation_count: 0,
          translated_count: 0,
          missing_count: 0,
          coverage_percent: null,
          languages: [],
          target_language_count: 0,
          last_imported_at: null,
        }),
      );
      renderOverview();
      const coverage = await screen.findByRole("region", {
        name: "Translation coverage",
      });
      expect(within(coverage).getByText("—")).toBeVisible();
      expect(screen.queryByRole("progressbar")).toBeNull();
      expect(coverage).toHaveTextContent(
        kind === "no-import"
          ? "Import translations to see coverage."
          : kind === "no-targets"
            ? "Only source strings imported; no target languages yet."
            : "No source strings imported.",
      );
      if (kind === "no-import")
        expect(coverage).toHaveTextContent(
          "1 translation source has not been imported yet",
        );
    },
  );

  it("keeps configuration usable on summary failure and retries only the summary", async () => {
    getAdminProductSummaryMock.mockResolvedValueOnce(failure());
    renderOverview();
    expect(
      await screen.findByText("Translation summary unavailable"),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Configure product" }),
    ).toBeVisible();
    expect(screen.queryByRole("region", { name: "Translated" })).toBeNull();
    await userEvent.click(
      screen.getByRole("button", { name: "Retry summary" }),
    );
    expect(
      await screen.findByRole("region", { name: "Translated" }),
    ).toHaveTextContent("5");
    expect(getAdminProductMock).toHaveBeenCalledTimes(1);
    expect(getAdminProductSummaryMock).toHaveBeenCalledTimes(2);
  });
  it.each(["initial", "deactivate"])(
    "retains inactive coverage without offering forbidden language actions (%s)",
    async (kind) => {
      const inactive = { ...activeProduct, is_active: false };
      if (kind === "initial")
        getAdminProductMock.mockResolvedValueOnce(ok(inactive));
      else deactivateAdminProductMock.mockResolvedValueOnce(ok(inactive));
      renderOverview();
      expect(
        await screen.findByRole("region", { name: "Translated" }),
      ).toHaveTextContent("5");
      if (kind === "deactivate") {
        expect(
          screen.getAllByRole("link", { name: "Open language" }),
        ).toHaveLength(2);
        await userEvent.click(
          screen.getByRole("button", { name: "Deactivate product" }),
        );
        await userEvent.click(
          within(screen.getByRole("alertdialog")).getByRole("button", {
            name: "Deactivate product",
          }),
        );
      }
      expect(
        await screen.findByText("Activate the product to access its strings."),
      ).toBeVisible();
      expect(screen.queryByRole("link", { name: "Open language" })).toBeNull();
      expect(
        screen.getByRole("region", { name: "Translated" }),
      ).toHaveTextContent("5");
      expect(
        screen.getByRole("link", { name: "Configure product" }),
      ).toBeVisible();
    },
  );

  it.each(["token", "product"])(
    "aborts old summary authority on %s change and ignores a late completion",
    async (change) => {
      let resolve!: (
        value: ReturnType<typeof ok<AdminProductSummaryResponse>>,
      ) => void;
      getAdminProductSummaryMock.mockReturnValueOnce(
        new Promise<ReturnType<typeof ok<AdminProductSummaryResponse>>>(
          (done) => {
            resolve = done;
          },
        ),
      );
      const tree = (token: string, productId: string) => (
        <MemoryRouter>
          <ProductOverviewPage accessToken={token} productId={productId} />
        </MemoryRouter>
      );
      const view = render(tree("first-token", activeProduct.id));
      await screen.findByText("Loading translation summary");
      await waitFor(() =>
        expect(getAdminProductSummaryMock).toHaveBeenCalledTimes(1),
      );
      const signal = getAdminProductSummaryMock.mock.calls[0][0]?.signal;
      const nextId =
        change === "product" ? candidateOnlyProduct.id : activeProduct.id;
      getAdminProductMock.mockResolvedValueOnce(
        ok(change === "product" ? candidateOnlyProduct : activeProduct),
      );
      view.rerender(tree("second-token", nextId));
      expect(
        await screen.findByRole("region", { name: "Source strings" }),
      ).toHaveTextContent("4");
      expect(signal?.aborted).toBe(true);
      await act(async () =>
        resolve(
          ok({
            ...productSummary,
            product_id: activeProduct.id,
            source_string_count: 999,
          }),
        ),
      );
      expect(
        screen.getByRole("region", { name: "Source strings" }),
      ).not.toHaveTextContent("999");
      expect(getAdminProductSummaryMock.mock.lastCall?.[0]).toMatchObject({
        auth: "second-token",
        path: { product_id: nextId },
      });
    },
  );

  it("rejects a mismatched product summary and discloses bounded language lists", async () => {
    getAdminProductSummaryMock.mockResolvedValueOnce(
      ok({ ...productSummary, product_id: "other-product" }),
    );
    getAdminProductSummaryMock.mockResolvedValueOnce(
      ok({
        ...productSummary,
        product_id: activeProduct.id,
        languages_has_more: true,
        target_language_count: 501,
      }),
    );
    renderOverview();
    expect(
      await screen.findByText("Translation summary unavailable"),
    ).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Retry summary" }),
    );
    expect(
      await screen.findByText(
        "Top 2 languages by missing strings. Totals cover all 501 languages.",
      ),
    ).toBeVisible();
  });

  it("prioritizes source and target coverage while keeping configuration accessible", async () => {
    renderOverview();

    expect(
      await screen.findByRole("heading", { name: "Zulu Mobile" }),
    ).toBeVisible();
    expect(screen.getByText("Unpublished configuration changes")).toBeVisible();
    expect(screen.getByText("Published mobile strings")).toBeVisible();
    expect(screen.queryByRole("tab", { name: "Published" })).toBeNull();
    expect(
      await screen.findByRole("region", { name: "Source strings" }),
    ).toHaveTextContent("4");
    expect(
      screen.getByRole("region", { name: "Translated" }),
    ).toHaveTextContent("5");
    expect(
      screen.getByRole("region", { name: "Missing or unfinished" }),
    ).toHaveTextContent("3");
    expect(
      screen.getByRole("progressbar", { name: "Overall translation coverage" }),
    ).toHaveAttribute("aria-valuenow", "62.5");
    const rows = within(
      screen.getByRole("table", { name: "Translation coverage by language" }),
    ).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("it");
    expect(rows[2]).toHaveTextContent("vi");
    expect(
      within(rows[1]).getByRole("link", { name: "Open language" }),
    ).toHaveAttribute(
      "href",
      `/products/${activeProduct.id}/strings?language=it`,
    );
    expect(
      screen.getByText("Active", { selector: "[data-slot=badge]" }),
    ).toHaveAttribute("data-variant", "success");
    expect(getAdminProductMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { product_id: activeProduct.id },
    });
    const detailNavigation = screen.getByRole("navigation", {
      name: "Product configuration",
    });
    expect(
      within(detailNavigation).getByRole("link", {
        name: "Overview",
        current: "page",
      }),
    ).toHaveAttribute("href", `/admin/products/${activeProduct.id}/overview`);
    expect(
      within(detailNavigation).getByRole("link", { name: "Repositories" }),
    ).toHaveAttribute(
      "href",
      `/admin/products/${activeProduct.id}/repositories`,
    );
    expect(
      within(detailNavigation).getByRole("link", {
        name: "Translation sources",
      }),
    ).toHaveAttribute("href", `/admin/products/${activeProduct.id}/mappings`);
    expect(
      within(detailNavigation).getByRole("link", {
        name: "Preview and import",
      }),
    ).toHaveAttribute("href", `/admin/products/${activeProduct.id}/preview`);
    expect(
      within(detailNavigation).getAllByRole("link", { current: "page" }),
    ).toHaveLength(1);
    expect(
      screen.getByRole("link", { name: "Configure product" }),
    ).toHaveAttribute("href", `/admin/products/${activeProduct.id}/edit`);
  });

  it("UI3-C24 renders the complete server-owned freshness zero-one-many cardinality matrix", async () => {
    const user = userEvent.setup();
    const zeroView = renderOverview();

    expect(
      await screen.findByRole("heading", { name: activeProduct.name }),
    ).toBeVisible();
    expect(
      screen.queryByText(/mapping(?:s)? may be stale/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Import failed. Showing the last successful import."),
    ).not.toBeInTheDocument();
    expect(listAdminPublishedMappingImportsMock).not.toHaveBeenCalled();
    zeroView.unmount();

    getAdminProductMock.mockResolvedValueOnce(
      ok({ ...activeProduct, affected_mapping_count: 1 }),
    );
    const oneView = renderOverview();
    const singular = await screen.findByText("1 mapping may be stale");
    const singularSummary = singular.closest("section");
    expect(singularSummary).not.toBeNull();
    expect(singularSummary).toHaveTextContent(
      "Import failed. Showing the last successful import.",
    );
    expect(
      within(singularSummary!).queryByRole("link"),
    ).not.toBeInTheDocument();
    expect(
      within(singularSummary!).queryByRole("button"),
    ).not.toBeInTheDocument();
    expect(
      singularSummary!.compareDocumentPosition(
        await screen.findByRole("region", { name: "Translation coverage" }),
      ) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      screen
        .getByRole("button", { name: "Deactivate product" })
        .compareDocumentPosition(singularSummary!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    oneView.unmount();

    getAdminProductMock.mockResolvedValueOnce(
      ok({ ...activeProduct, affected_mapping_count: 37 }),
    );
    renderOverview();
    expect(await screen.findByText("37 mappings may be stale")).toBeVisible();
    expect(
      screen.queryByText("37 mapping may be stale"),
    ).not.toBeInTheDocument();
    expect(listAdminPublishedMappingImportsMock).not.toHaveBeenCalled();

    await user.tab();
    expect(document.body).not.toHaveTextContent("all current");
  });

  it("renders the default product detail title and nested outlet contract", () => {
    render(
      <MemoryRouter
        initialEntries={[`/admin/products/${activeProduct.id}/mappings`]}
      >
        <Routes>
          <Route
            path="admin/products/:productId"
            element={<ProductDetailLayout />}
          >
            <Route path="mappings" element={<p>Nested mapping content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    const layout = screen.getByTestId("product-detail-layout");
    expect(layout).toHaveAttribute("aria-labelledby", "product-detail-title");
    expect(layout).not.toHaveAttribute("aria-label");
    expect(
      screen.getByRole("heading", { name: "Product configuration" }),
    ).toHaveAttribute("id", "product-detail-title");
    expect(screen.getByText("Nested mapping content")).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: "Translation sources",
        current: "page",
      }),
    ).toHaveAttribute("href", `/admin/products/${activeProduct.id}/mappings`);
    expect(
      screen.getByRole("link", {
        name: "Translation sources",
        current: "page",
      }),
    ).toHaveClass("min-h-11", "break-words");

    cleanup();
    render(
      <MemoryRouter>
        <ProductDetailLayout>
          <p>Missing route identity remains bounded</p>
        </ProductDetailLayout>
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
      "href",
      "/admin/products/overview",
    );
  });

  it("renders bounded overview loading and cancels queued work on unmount", async () => {
    getAdminProductMock.mockReturnValueOnce(
      new Promise<never>(() => undefined),
    );
    const loadingView = renderOverview();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading product overview",
    );
    await waitFor(() => expect(getAdminProductMock).toHaveBeenCalledOnce());
    loadingView.unmount();

    getAdminProductMock.mockReset();
    const queuedView = renderOverview();
    queuedView.unmount();
    await act(async () => Promise.resolve());
    expect(getAdminProductMock).not.toHaveBeenCalled();
  });

  it("fails closed without product authority and retries generated no-data overview results", async () => {
    let resolveOverviewRetry:
      | ((value: ReturnType<typeof ok<AdminProductResponse>>) => void)
      | undefined;
    const pendingOverviewRetry = new Promise<
      ReturnType<typeof ok<AdminProductResponse>>
    >((resolve) => {
      resolveOverviewRetry = resolve;
    });
    const missingIdView = render(
      <MemoryRouter>
        <ProductOverviewPage accessToken="memory-only-admin-bearer" />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Product unavailable",
    );
    expect(getAdminProductMock).not.toHaveBeenCalled();
    missingIdView.unmount();

    getAdminProductMock
      .mockResolvedValueOnce(failure())
      .mockReturnValueOnce(pendingOverviewRetry);
    render(
      <MemoryRouter>
        <ProductOverviewPage
          accessToken="memory-only-admin-bearer"
          productId={candidateOnlyProduct.id}
        />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Product unavailable",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Retry loading page" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Loading product overview",
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await act(async () => {
      resolveOverviewRetry?.(ok(candidateOnlyProduct));
    });
    expect(
      await screen.findByRole("heading", { name: candidateOnlyProduct.name }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Configure product" }),
    ).toBeVisible();
    expect(screen.queryByText("No description")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Deactivate product" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        "Published configuration remains active while you edit this draft.",
      ),
    ).not.toBeInTheDocument();

    cleanup();
    getAdminProductMock.mockResolvedValueOnce(
      ok(activeWithoutCandidateProduct),
    );
    render(
      <MemoryRouter>
        <ProductOverviewPage
          accessToken="memory-only-admin-bearer"
          productId={activeWithoutCandidateProduct.id}
        />
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole("heading", {
        name: activeWithoutCandidateProduct.name,
      }),
    ).toBeVisible();
    expect(
      screen.queryByText(
        "Published configuration remains active while you edit this draft.",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Deactivate product" }),
    ).toBeVisible();
  });

  it("ignores superseded overview loads", async () => {
    let resolveFirst:
      | ((value: ReturnType<typeof ok<AdminProductResponse>>) => void)
      | undefined;
    const firstLoad = new Promise<ReturnType<typeof ok<AdminProductResponse>>>(
      (resolve) => {
        resolveFirst = resolve;
      },
    );
    getAdminProductMock
      .mockReturnValueOnce(firstLoad)
      .mockResolvedValueOnce(ok(candidateOnlyProduct));
    const view = render(
      <MemoryRouter>
        <ProductOverviewPage
          accessToken="first-overview-authority"
          productId={activeProduct.id}
        />
      </MemoryRouter>,
    );
    await waitFor(() => expect(getAdminProductMock).toHaveBeenCalledOnce());
    view.rerender(
      <MemoryRouter>
        <ProductOverviewPage
          accessToken="replacement-overview-authority"
          productId={candidateOnlyProduct.id}
        />
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole("heading", { name: candidateOnlyProduct.name }),
    ).toBeVisible();

    await act(async () => {
      resolveFirst?.(ok(activeProduct));
    });
    expect(
      screen.queryByRole("heading", { name: activeProduct.name }),
    ).not.toBeInTheDocument();

    cleanup();
    let rejectFirst: ((reason?: unknown) => void) | undefined;
    const staleRejection = new Promise<
      ReturnType<typeof ok<AdminProductResponse>>
    >((_resolve, reject) => {
      rejectFirst = reject;
    });
    getAdminProductMock.mockReset();
    getAdminProductMock
      .mockReturnValueOnce(staleRejection)
      .mockResolvedValueOnce(ok(candidateOnlyProduct));
    const rejectionView = render(
      <MemoryRouter>
        <ProductOverviewPage
          accessToken="stale-overview-authority"
          productId={activeProduct.id}
        />
      </MemoryRouter>,
    );
    await waitFor(() => expect(getAdminProductMock).toHaveBeenCalledOnce());
    rejectionView.rerender(
      <MemoryRouter>
        <ProductOverviewPage
          accessToken="current-overview-authority"
          productId={candidateOnlyProduct.id}
        />
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole("heading", { name: candidateOnlyProduct.name }),
    ).toBeVisible();
    await act(async () => {
      rejectFirst?.(new Error("stale provider detail"));
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("returns focus when deactivation is cancelled and bounds rejected failures", async () => {
    deactivateAdminProductMock.mockRejectedValueOnce(
      new Error("provider response with private details"),
    );
    renderOverview();
    const user = userEvent.setup();
    const trigger = await screen.findByRole("button", {
      name: "Deactivate product",
    });
    await user.click(trigger);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen
        .getByRole("alertdialog", { name: "Deactivate Zulu Mobile?" })
        .contains(document.activeElement),
    ).toBe(true);
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(trigger).toHaveFocus());

    await user.click(trigger);
    await user.click(
      screen.getByRole("button", { name: "Deactivate product" }),
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "We could not deactivate this product. Its active state is unchanged.",
    );
    expect(alert).not.toHaveTextContent("private details");
    expect(alert).toHaveFocus();
    expect(alert).toHaveAttribute("tabindex", "-1");
    expect(screen.getByText("Active")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Deactivate product" }),
    ).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(trigger);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("deactivates only after named backend confirmation and keeps state unchanged on failure", async () => {
    let resolveDeactivate:
      | ((value: ReturnType<typeof ok<AdminProductResponse>>) => void)
      | undefined;
    const pendingDeactivate = new Promise<
      ReturnType<typeof ok<AdminProductResponse>>
    >((resolve) => {
      resolveDeactivate = resolve;
    });
    deactivateAdminProductMock
      .mockReturnValueOnce(pendingDeactivate)
      .mockResolvedValueOnce(failure());
    renderOverview();
    const user = userEvent.setup();

    await user.click(
      await screen.findByRole("button", { name: "Deactivate product" }),
    );
    const dialog = screen.getByRole("alertdialog", {
      name: "Deactivate Zulu Mobile?",
    });
    expect(dialog).toHaveTextContent(
      "Its mappings will stop operating, but its published configuration will be kept.",
    );
    const confirm = within(dialog).getByRole("button", {
      name: "Deactivate product",
    });
    act(() => {
      confirm.click();
      confirm.click();
    });
    expect(deactivateAdminProductMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { product_id: activeProduct.id },
    });
    expect(deactivateAdminProductMock).toHaveBeenCalledOnce();
    expect(screen.getByText("Active")).toBeVisible();
    expect(confirm).toBeDisabled();
    expect(confirm).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    await user.keyboard("{Escape}");
    expect(
      screen.getByRole("alertdialog", { name: "Deactivate Zulu Mobile?" }),
    ).toBeVisible();

    await act(async () => {
      resolveDeactivate?.(ok({ ...activeProduct, is_active: false }));
    });
    expect(await screen.findByText("Inactive")).toBeVisible();
    expect(
      screen.queryByRole("alertdialog", { name: "Deactivate Zulu Mobile?" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Deactivate product" }),
    ).not.toBeInTheDocument();

    getAdminProductMock.mockResolvedValueOnce(ok(activeProduct));
    cleanup();
    renderOverview();
    await user.click(
      await screen.findByRole("button", { name: "Deactivate product" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Deactivate product" }),
    );
    const failureAlert = await screen.findByRole("alert");
    expect(failureAlert).toHaveTextContent(
      "We could not deactivate this product. Its active state is unchanged.",
    );
    expect(screen.getByText("Active")).toBeVisible();
    expect(
      screen.getByRole("alertdialog", { name: "Deactivate Zulu Mobile?" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Deactivate product" }),
    ).toBeEnabled();
    let resolveRetryDeactivate:
      | ((value: ReturnType<typeof ok<AdminProductResponse>>) => void)
      | undefined;
    deactivateAdminProductMock.mockReturnValueOnce(
      new Promise<ReturnType<typeof ok<AdminProductResponse>>>((resolve) => {
        resolveRetryDeactivate = resolve;
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Deactivate product" }),
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Deactivate product" }),
    ).toBeDisabled();
    await act(async () => {
      resolveRetryDeactivate?.(ok({ ...activeProduct, is_active: false }));
    });
    expect(await screen.findByText("Inactive")).toBeVisible();
  });

  it("deletes only after explicit named confirmation and returns to Products", async () => {
    deleteAdminProductMock.mockResolvedValueOnce(ok(undefined, 204));
    renderOverview();
    const user = userEvent.setup();
    const trigger = await screen.findByRole("button", {
      name: "Delete product",
    });
    await user.click(trigger);
    const dialog = screen.getByRole("alertdialog", {
      name: "Delete Zulu Mobile?",
    });
    expect(dialog).toHaveTextContent(
      "VerboFlex will hide this product. Its retained data may be permanently removed under the configured maintenance policy.",
    );
    expect(dialog).toHaveTextContent("Bitbucket will not be changed.");

    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(deleteAdminProductMock).not.toHaveBeenCalled();
    await waitFor(() => expect(trigger).toHaveFocus());

    await user.click(trigger);
    await user.click(
      within(
        screen.getByRole("alertdialog", { name: "Delete Zulu Mobile?" }),
      ).getByRole("button", { name: "Delete product" }),
    );
    expect(deleteAdminProductMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { product_id: activeProduct.id },
    });
    expect(deleteAdminProductMock).toHaveBeenCalledOnce();
    await waitFor(() =>
      expect(screen.getByTestId("current-location")).toHaveTextContent(
        "/admin/products",
      ),
    );
  });

  it("keeps the delete dialog actionable when active work blocks deletion", async () => {
    deleteAdminProductMock.mockResolvedValueOnce({
      data: undefined,
      error: {
        detail: "Product deletion blocked",
        blockers: ["active_work"],
      },
      request: new Request("http://localhost/api/v1/admin/products/product-id"),
      response: new Response(null, { status: 409 }),
    });
    renderOverview();
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Delete product" }),
    );
    await user.click(screen.getByRole("button", { name: "Delete product" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Product deletion is temporarily blocked");
    expect(alert).toHaveTextContent(
      "Wait for the running import or preview to finish, then try again.",
    );
    expect(alert).toHaveFocus();
    expect(screen.getByText("Active")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Delete product" }),
    ).toBeEnabled();
  });

  it("keeps deletion single-flight, blocks dismissal, and ignores completion after unmount", async () => {
    let resolveDelete:
      ((value: ReturnType<typeof ok<undefined>>) => void) | undefined;
    deleteAdminProductMock.mockReturnValueOnce(
      new Promise<ReturnType<typeof ok<undefined>>>((resolve) => {
        resolveDelete = resolve;
      }),
    );
    const view = renderOverview();
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Delete product" }),
    );
    const submit = screen.getByRole("button", { name: "Delete product" });
    await user.click(submit);
    expect(deleteAdminProductMock).toHaveBeenCalledOnce();
    expect(submit).toBeDisabled();
    // A hostile imperative event must still be fenced by the synchronous ref,
    // even if it bypasses the browser's disabled-button behavior.
    submit.removeAttribute("disabled");
    fireEvent.click(submit);
    expect(deleteAdminProductMock).toHaveBeenCalledOnce();

    await user.keyboard("{Escape}");
    expect(
      screen.getByRole("alertdialog", { name: "Delete Zulu Mobile?" }),
    ).toBeVisible();
    view.unmount();
    await act(async () => resolveDelete?.(ok(undefined, 204)));
    expect(deleteAdminProductMock).toHaveBeenCalledOnce();
  });

  it("sanitizes a rejected deletion and keeps the named retry available", async () => {
    deleteAdminProductMock.mockRejectedValueOnce(
      new Error("provider_token=private-diagnostic"),
    );
    renderOverview();
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Delete product" }),
    );
    await user.click(screen.getByRole("button", { name: "Delete product" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Product not deleted");
    expect(alert).not.toHaveTextContent("private-diagnostic");
    expect(alert).toHaveFocus();
    expect(
      screen.getByRole("button", { name: "Delete product" }),
    ).toBeEnabled();
  });

  it("mounts the product collection, new wizard, and URL-backed overview routes inside the guarded shell", async () => {
    listAdminRevisionMappingsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    const collectionView = renderApplicationRouter("/admin/products");

    expect(
      await screen.findByRole("heading", { name: "Products" }),
    ).toBeVisible();
    await userEvent.click(screen.getByRole("link", { name: "Create product" }));
    expect(
      await screen.findByRole("heading", { name: "Create product" }),
    ).toBeVisible();
    expect(
      screen.getByRole("navigation", { name: "Product setup steps" }),
    ).toBeVisible();

    collectionView.unmount();
    renderApplicationRouter(`/admin/products/${activeProduct.id}/overview`);

    expect(
      await screen.findByRole("heading", { name: activeProduct.name }),
    ).toBeVisible();
    expect(
      screen.getByRole("navigation", { name: "Product configuration" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Overview", current: "page" }),
    ).toBeVisible();
    await userEvent.click(screen.getByRole("link", { name: "Repositories" }));
    expect(
      await screen.findByRole("heading", {
        name: "Repositories used by this product",
      }),
    ).toBeVisible();
    const detailLayout = screen.getByTestId("product-detail-layout");
    expect(detailLayout).toHaveAttribute("aria-label", "Product configuration");
    expect(detailLayout).not.toHaveAttribute("aria-labelledby");
    const sectionNavigation = within(detailLayout).getByRole("navigation", {
      name: "Product configuration",
    });
    expect(
      within(sectionNavigation).getAllByRole("link", { current: "page" }),
    ).toHaveLength(1);
    expect(
      within(sectionNavigation).getByRole("link", {
        name: "Repositories",
        current: "page",
      }),
    ).toHaveClass("border-primary", "text-primary");
    await userEvent.click(
      within(sectionNavigation).getByRole("link", {
        name: "Translation sources",
      }),
    );
    expect(
      await screen.findByRole("heading", { name: "Translation sources" }),
    ).toBeVisible();
    expect(
      await screen.findByText(
        "Select the repository and branch with your translations.",
      ),
    ).toBeVisible();
    getAdminProductMock.mockClear();
    listAdminCandidateMappingsMock.mockClear();
    listAdminRevisionMappingsMock.mockClear();
    await userEvent.click(
      screen.getByRole("link", { name: "Preview and import" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Preview and import" }),
    ).toBeVisible();
    expect(await screen.findByText("No mappings configured")).toBeVisible();
    expect(
      await screen.findByText(
        "Add a translation source before previewing its files.",
      ),
    ).toBeVisible();
    expect(getAdminProductMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { product_id: activeProduct.id },
    });
    expect(listAdminRevisionMappingsMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: {
        product_id: activeProduct.id,
        revision_id: activeProduct.candidate_revision!.id,
      },
      query: { cursor: null, limit: 50 },
    });
    expect(getAdminProductMock.mock.invocationCallOrder[0]).toBeLessThan(
      listAdminRevisionMappingsMock.mock.invocationCallOrder[0],
    );
    expect(listAdminCandidateMappingsMock).not.toHaveBeenCalled();
  });

  it("routes the product repository tab to mapping-derived repository usage", async () => {
    exposeTask2Repositories();
    render(
      <MemoryRouter
        initialEntries={[`/admin/products/${activeProduct.id}/repositories`]}
      >
        <AppRouter />
      </MemoryRouter>,
    );

    const list = await screen.findByRole("list", {
      name: "Repositories used by this product",
    });
    expect(within(list).getByText("Mobile application source")).toBeVisible();
    expect(
      within(list).queryByText("localization-team/mobile-translations"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Register repository" }),
    ).not.toBeInTheDocument();
    expect(listAdminRevisionMappingsMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: {
        product_id: activeProduct.id,
        revision_id: activeProduct.candidate_revision!.id,
      },
      query: { cursor: null, limit: 50 },
      signal: expect.any(AbortSignal),
    });
  });

  it("selects a live Bitbucket repository for the next mapping step", async () => {
    exposeTask2Repositories();
    renderWizard(activeProduct);
    await userEvent.click(screen.getByRole("button", { name: "Repositories" }));
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Connect Mobile application source",
      }),
    );
    await waitFor(() =>
      expect(selectAdminBitbucketRepository).toHaveBeenCalled(),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Next: Translation sources" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Translation sources" }),
    ).toBeVisible();
    expect(screen.queryByText("Use repository")).not.toBeInTheDocument();
  });

  it("saves through Next once, locks navigation while pending and advances only after success", async () => {
    exposeTask2Repositories();
    let resolveSave!: (
      value: ReturnType<typeof ok<AdminMappingResponse>>,
    ) => void;
    createAdminCandidateMappingMock.mockReturnValueOnce(
      new Promise<ReturnType<typeof ok<AdminMappingResponse>>>((resolve) => {
        resolveSave = resolve;
      }),
    );
    renderWizard(activeProduct);
    await userEvent.click(
      screen.getByRole("button", { name: "Translation sources" }),
    );
    await userEvent.click(
      await screen.findByRole("combobox", { name: "Repository" }),
    );
    await userEvent.click(
      screen.getByRole("option", { name: /Mobile application source/ }),
    );
    await userEvent.type(
      await screen.findByRole("combobox", { name: "Source branch" }),
      "main",
    );
    await userEvent.click(screen.getByRole("option", { name: "main" }));
    await userEvent.type(
      screen.getByRole("searchbox", { name: "Search target branches" }),
      "main",
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Allow target main" }),
    );
    expect(
      screen.queryByRole("button", { name: "Save mapping" }),
    ).not.toBeInTheDocument();
    const next = screen.getByRole("button", {
      name: "Next: Preview and import",
    });
    await userEvent.dblClick(next);
    expect(createAdminCandidateMappingMock).toHaveBeenCalledOnce();
    expect(next).toBeDisabled();
    expect(screen.getByRole("button", { name: "Back" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Repositories" })).toBeDisabled();
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 3 of 4",
    );
    await act(async () =>
      resolveSave(ok({ ...directMapping, candidate_version: 6 })),
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
        "Step 4 of 4",
      ),
    );
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("keeps a failed Next save editable and focused for retry", async () => {
    exposeTask2Repositories();
    createAdminCandidateMappingMock.mockRejectedValueOnce(
      new Error("private details"),
    );
    renderWizard(activeProduct);
    await userEvent.click(
      screen.getByRole("button", { name: "Translation sources" }),
    );
    await userEvent.click(
      await screen.findByRole("combobox", { name: "Repository" }),
    );
    await userEvent.click(
      screen.getByRole("option", { name: /Mobile application source/ }),
    );
    await userEvent.type(
      await screen.findByRole("combobox", { name: "Source branch" }),
      "main",
    );
    await userEvent.click(screen.getByRole("option", { name: "main" }));
    await userEvent.type(
      screen.getByRole("searchbox", { name: "Search target branches" }),
      "main",
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Allow target main" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Next: Preview and import" }),
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveFocus();
    expect(alert).not.toHaveTextContent("private details");
    expect(
      screen.getByRole("combobox", { name: "Source branch" }),
    ).toHaveAccessibleDescription("Selected branch: main");
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 3 of 4",
    );
    expect(
      screen.getByRole("button", { name: "Next: Preview and import" }),
    ).toBeEnabled();
  });

  it("updates an edited source through the same wizard submission path", async () => {
    exposeTask2Repositories();
    listAdminCandidateMappingsMock.mockResolvedValue(
      ok({ items: [directMapping], next_cursor: null }),
    );
    getAdminRepositoryBranchMock.mockImplementation(async (options) =>
      ok({ name: options.query.branch_name, commit_hash: "a".repeat(40) }),
    );
    vi.mocked(updateAdminCandidateMapping).mockResolvedValueOnce(
      ok({
        ...directMapping,
        candidate_version: 6,
        primary_localization_root: "locales",
      }),
    );
    renderWizard(activeProduct);
    await userEvent.click(
      screen.getByRole("button", { name: "Translation sources" }),
    );
    await userEvent.click(
      (await screen.findAllByRole("button", { name: "Edit mapping" }))[0],
    );
    await waitFor(() =>
      expect(
        screen.getByRole("combobox", { name: "Source branch" }),
      ).toBeEnabled(),
    );
    await userEvent.click(
      screen.getByText("Limit the search to a folder (optional)"),
    );
    const folder = screen.getByRole("textbox", {
      name: "Localization root (optional)",
    });
    await userEvent.type(folder, "locales");
    fireEvent.submit(folder.closest("form")!);
    await waitFor(() =>
      expect(vi.mocked(updateAdminCandidateMapping)).toHaveBeenCalledOnce(),
    );
    expect(updateAdminCandidateMapping).toHaveBeenCalledWith(
      expect.objectContaining({
        path: { product_id: activeProduct.id, mapping_id: directMapping.id },
        body: expect.objectContaining({
          expected_candidate_version: 5,
          localization_root: "locales",
        }),
      }),
    );
    expect(createAdminCandidateMappingMock).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
        "Step 4 of 4",
      ),
    );
  });

  it("continues from an unchanged existing source without another write", async () => {
    exposeTask2Repositories();
    listAdminCandidateMappingsMock.mockResolvedValue(
      ok({ items: [directMapping], next_cursor: null }),
    );
    renderWizard(activeProduct);
    await userEvent.click(
      screen.getByRole("button", { name: "Translation sources" }),
    );
    await screen.findByRole("table", { name: "Translation sources" });
    await userEvent.click(
      screen.getByRole("button", { name: "Next: Preview and import" }),
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
        "Step 4 of 4",
      ),
    );
    expect(createAdminCandidateMappingMock).not.toHaveBeenCalled();
  });

  it("uses only live branch results for direct source and target controls", async () => {
    exposeTask2Repositories();
    renderWizard(activeProduct);
    await userEvent.click(
      screen.getByRole("button", { name: "Translation sources" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Translation sources" }),
    ).toBeVisible();
    expect(
      screen.getByRole("radio", { name: "Same repository" }),
    ).toBeChecked();
    await userEvent.click(screen.getByRole("combobox", { name: "Repository" }));
    await userEvent.click(
      screen.getByRole("option", {
        name: "Mobile application source — product-team/mobile-app",
      }),
    );
    expect(listAdminRepositoryBranchesMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { repository_id: applicationRepository.id },
      query: { cursor: null, limit: 100 },
      signal: expect.any(AbortSignal),
    });

    const sourceBranch = await screen.findByRole("combobox", {
      name: "Source branch",
    });
    expect(
      screen.queryByRole("option", { name: "main" }),
    ).not.toBeInTheDocument();
    await userEvent.type(sourceBranch, "a");
    expect(screen.getByRole("option", { name: "main" })).toBeVisible();
    expect(
      screen.getByRole("option", {
        name: "release/2026-with-a-very-long-opaque-provider-branch-name",
      }),
    ).toBeVisible();
    await userEvent.click(screen.getByRole("option", { name: "main" }));

    expect(
      screen.queryByRole("combobox", { name: "Default target" }),
    ).not.toBeInTheDocument();
    await userEvent.type(
      screen.getByRole("searchbox", { name: "Search target branches" }),
      "release/2026",
    );
    await userEvent.click(
      screen.getByRole("checkbox", {
        name: "Allow target release/2026-with-a-very-long-opaque-provider-branch-name",
      }),
    );
    expect(
      screen.getByText(
        "release/2026-with-a-very-long-opaque-provider-branch-name is the default target",
      ),
    ).toBeVisible();

    expect(
      screen.queryByRole("button", { name: /delete mapping/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: /glob|path|file|locale|format/i }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
  });

  it("confirms topology changes before clearing direct values and exposes explicit separate sides", async () => {
    exposeTask2Repositories();
    renderWizard(activeProduct);
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: "Translation sources" }),
    );
    await screen.findByRole("heading", { name: "Translation sources" });
    await user.click(screen.getByRole("combobox", { name: "Repository" }));
    await user.click(
      screen.getByRole("option", {
        name: "Mobile application source — product-team/mobile-app",
      }),
    );
    await user.click(
      screen.getByRole("radio", { name: "Separate repositories" }),
    );

    const dialog = screen.getByRole("alertdialog", {
      name: "Change mapping topology?",
    });
    expect(dialog).toHaveTextContent(
      "Changing topology clears the repository and branch selections in this unsaved mapping.",
    );
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(
      screen.getByRole("radio", { name: "Same repository" }),
    ).toBeChecked();
    expect(
      screen.getByRole("combobox", { name: "Repository" }),
    ).toHaveTextContent("Mobile application source");

    await user.click(
      screen.getByRole("radio", { name: "Separate repositories" }),
    );
    await user.click(screen.getByRole("button", { name: "Change topology" }));
    expect(
      screen.getByRole("radio", { name: "Separate repositories" }),
    ).toBeChecked();
    expect(
      screen.getByRole("combobox", { name: "Keys repository" }),
    ).toBeVisible();
    expect(
      screen.getByRole("combobox", { name: "Translations repository" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("combobox", { name: "Repository" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText(/credential|password|token|secret/i),
    ).not.toBeInTheDocument();
  });

  it("writes an expected-version mapping, preserves conflicts, and keeps default membership valid", async () => {
    exposeTask2Repositories();
    createAdminCandidateMappingMock
      .mockResolvedValueOnce(mappingConflict("allowed_target_branches"))
      .mockResolvedValueOnce(
        ok(
          {
            ...directMapping,
            id: "00000000-0000-4000-8000-000000000402",
            candidate_version: 6,
          },
          201,
        ),
      );
    renderWizard(activeProduct);
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: "Translation sources" }),
    );
    await screen.findByRole("heading", { name: "Translation sources" });
    await user.click(screen.getByRole("combobox", { name: "Repository" }));
    await user.click(
      screen.getByRole("option", {
        name: "Mobile application source — product-team/mobile-app",
      }),
    );
    await user.type(
      await screen.findByRole("combobox", { name: "Source branch" }),
      "main",
    );
    await user.click(screen.getByRole("option", { name: "main" }));
    await user.type(
      screen.getByRole("searchbox", { name: "Search target branches" }),
      "release/2026",
    );
    const target = screen.getByRole("checkbox", {
      name: "Allow target release/2026-with-a-very-long-opaque-provider-branch-name",
    });
    await user.click(target);
    await user.click(
      screen.getByRole("button", { name: "Next: Preview and import" }),
    );

    expect(createAdminCandidateMappingMock).toHaveBeenNthCalledWith(1, {
      auth: "memory-only-admin-bearer",
      path: { product_id: activeProduct.id },
      body: {
        allowed_target_branches: [
          "release/2026-with-a-very-long-opaque-provider-branch-name",
        ],
        default_target_branch:
          "release/2026-with-a-very-long-opaque-provider-branch-name",
        expected_candidate_version: 5,
        repository_id: applicationRepository.id,
        source_branch: "main",
        topology: "direct",
      },
    });
    const conflictAlert = await screen.findByRole("alert");
    expect(conflictAlert).toHaveTextContent(
      "The allowed target branches changed. Your selections are still here. Refresh branches and try again.",
    );
    expect(conflictAlert).not.toHaveTextContent(
      "private provider conflict detail",
    );
    expect(
      screen.getByRole("checkbox", {
        name: "Allow target release/2026-with-a-very-long-opaque-provider-branch-name",
      }),
    ).toBeChecked();
    expect(
      screen.getByText(
        "release/2026-with-a-very-long-opaque-provider-branch-name is the default target",
      ),
    ).toBeVisible();

    // The read after a successful write returns the persisted mapping.
    listAdminCandidateMappingsMock.mockResolvedValue(
      ok({
        items: [
          {
            ...directMapping,
            id: "00000000-0000-4000-8000-000000000402",
            candidate_version: 6,
          },
        ],
        next_cursor: null,
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Next: Preview and import" }),
    );
    expect(toastSuccessMock).toHaveBeenCalledWith("Draft saved");
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 4 of 4",
    );
    expect(createAdminCandidateMappingMock).toHaveBeenCalledTimes(2);
  });

  it("renders mapping tables as ordered stacks below 768px with local focusable branch overflow", async () => {
    exposeTask2Repositories();
    listAdminCandidateMappingsMock.mockResolvedValueOnce(
      ok({ items: [directMapping], next_cursor: null }),
    );
    renderWizard(activeProduct);
    await userEvent.click(
      screen.getByRole("button", { name: "Translation sources" }),
    );

    const table = await screen.findByRole("table", {
      name: "Translation sources",
    });
    expect(table.parentElement?.parentElement).toHaveClass(
      "hidden",
      "md:block",
    );
    const mobileList = screen.getByLabelText("Translation sources mobile list");
    expect(mobileList).toHaveClass("md:hidden", "min-w-0", "max-w-full");
    expect(within(mobileList).getAllByRole("article")).toHaveLength(1);
    const overflowRegions = screen.getAllByRole("region", {
      name: "Mapping branch details",
    });
    expect(overflowRegions.length).toBeGreaterThan(0);
    for (const region of overflowRegions) {
      expect(region).toHaveAttribute("tabindex", "0");
      expect(region).toHaveClass("max-w-full", "overflow-x-auto");
    }
    expect(
      screen.getAllByText(
        "release/2026-with-a-very-long-opaque-provider-branch-name",
      ).length,
    ).toBeGreaterThan(0);
    expect(
      screen.queryByRole("button", { name: /delete mapping/i }),
    ).not.toBeInTheDocument();
  });
});
