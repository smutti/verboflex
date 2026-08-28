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
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createAdminCandidateMapping,
  createAdminProduct,
  createAdminRepository,
  deactivateAdminProduct,
  getAdminProduct,
  listAdminCandidateMappings,
  listAdminProducts,
  listAdminRepositories,
  listAdminRepositoryBranches,
  readSystemStatus,
  updateAdminProductCandidate,
  type AdminMappingResponse,
  type AdminProductResponse,
  type AdminRepositoryResponse,
} from "../../../api/client";
import { useSession } from "../../auth/session";
import { ProductOverviewPage } from "./ProductOverviewPage";
import { ProductsPage } from "./ProductsPage";
import { ProductWizardPage } from "./ProductWizardPage";
import { ProductDetailLayout } from "./ProductDetailLayout";
import { AppRouter } from "../../../router";

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

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
  },
}));

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();

  return {
    ...original,
    createAdminCandidateMapping: vi.fn(),
    createAdminProduct: vi.fn(),
    createAdminRepository: vi.fn(),
    deactivateAdminProduct: vi.fn(),
    getAdminProduct: vi.fn(),
    listAdminCandidateMappings: vi.fn(),
    listAdminProducts: vi.fn(),
    listAdminRepositories: vi.fn(),
    listAdminRepositoryBranches: vi.fn(),
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
const getAdminProductMock = vi.mocked(getAdminProduct);
const listAdminCandidateMappingsMock = vi.mocked(listAdminCandidateMappings);
const listAdminProductsMock = vi.mocked(listAdminProducts);
const listAdminRepositoriesMock = vi.mocked(listAdminRepositories);
const listAdminRepositoryBranchesMock = vi.mocked(listAdminRepositoryBranches);
const readSystemStatusMock = vi.mocked(readSystemStatus);
const useSessionMock = vi.mocked(useSession);
const updateAdminProductCandidateMock = vi.mocked(updateAdminProductCandidate);
const toastSuccessMock = vi.mocked(toast.success);

const activeProduct: AdminProductResponse = {
  id: "00000000-0000-4000-8000-000000000101",
  name: "Zulu Mobile",
  is_active: true,
  active_revision: {
    id: "00000000-0000-4000-8000-000000000201",
    description: "Published mobile strings",
    is_published: true,
    version: 4,
  },
  candidate_revision: {
    id: "00000000-0000-4000-8000-000000000202",
    description: "Candidate mobile strings",
    is_published: false,
    version: 5,
  },
};

const candidateOnlyProduct: AdminProductResponse = {
  id: "00000000-0000-4000-8000-000000000102",
  name: "Alpha Embedded",
  is_active: false,
  active_revision: null,
  candidate_revision: {
    id: "00000000-0000-4000-8000-000000000203",
    description: null,
    is_published: false,
    version: 1,
  },
};

const inactivePublishedProduct: AdminProductResponse = {
  id: "00000000-0000-4000-8000-000000000103",
  name: "Middle Desktop",
  is_active: false,
  active_revision: {
    id: "00000000-0000-4000-8000-000000000204",
    description: "Retained published desktop strings",
    is_published: true,
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
  return render(
    <MemoryRouter>
      <ProductWizardPage
        accessToken="memory-only-admin-bearer"
        initialProduct={initialProduct}
      />
    </MemoryRouter>,
  );
}

function renderOverview() {
  return render(
    <MemoryRouter>
      <ProductOverviewPage
        accessToken="memory-only-admin-bearer"
        productId={activeProduct.id}
      />
    </MemoryRouter>,
  );
}

describe("administrator product configuration tracer", () => {
  beforeEach(() => {
    createAdminCandidateMappingMock.mockReset();
    createAdminProductMock.mockReset();
    createAdminRepositoryMock.mockReset();
    deactivateAdminProductMock.mockReset();
    getAdminProductMock.mockReset();
    getAdminProductMock.mockResolvedValue(ok(activeProduct));
    listAdminCandidateMappingsMock.mockReset();
    listAdminCandidateMappingsMock.mockResolvedValue(
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
      screen.queryByRole("combobox", { name: "Product status" }),
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
    expect(alert).toHaveTextContent(
      "We could not load this page. Retry without leaving the administration area.",
    );
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

  it("keeps status, page size, cursor, and API row order server-owned", async () => {
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
      query: { cursor: null, limit: 50, status: null },
    });
    expect(
      screen.getByRole("button", { name: "Load more products" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Load more products" }),
    ).toHaveAttribute("aria-busy", "false");

    await userEvent.click(
      screen.getByRole("button", { name: "Load more products" }),
    );
    await waitFor(() => {
      expect(listAdminProductsMock).toHaveBeenNthCalledWith(2, {
        auth: "memory-only-admin-bearer",
        query: { cursor: "next-products", limit: 50, status: null },
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

    await userEvent.click(
      screen.getByRole("combobox", { name: "Product status" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "Inactive" }));
    await waitFor(() => {
      expect(listAdminProductsMock).toHaveBeenNthCalledWith(3, {
        auth: "memory-only-admin-bearer",
        query: { cursor: null, limit: 50, status: "inactive" },
      });
    });

    await userEvent.click(
      screen.getByRole("combobox", { name: "Products per page" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "100" }));
    await waitFor(() => {
      expect(listAdminProductsMock).toHaveBeenNthCalledWith(4, {
        auth: "memory-only-admin-bearer",
        query: { cursor: null, limit: 100, status: "inactive" },
      });
    });
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
    expect(
      within(table).getAllByText("Active", { selector: "[data-slot=badge]" }),
    ).toHaveLength(1);
    expect(
      within(table).getAllByText("Inactive", { selector: "[data-slot=badge]" }),
    ).toHaveLength(2);
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
    const loadMore = await screen.findByRole("button", {
      name: "Load more products",
    });
    act(() => {
      loadMore.click();
      loadMore.click();
    });
    expect(listAdminProductsMock).toHaveBeenCalledTimes(2);
    expect(loadMore).toBeDisabled();
    expect(loadMore).toHaveAttribute("aria-busy", "true");
    await act(async () => {
      resolveMore?.(
        ok({
          items: [candidateOnlyProduct],
          next_cursor: "after-more-products",
        }),
      );
    });
    expect(
      screen.getByRole("button", { name: "Load more products" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Load more products" }),
    ).toHaveAttribute("aria-busy", "false");

    await userEvent.click(
      screen.getByRole("combobox", { name: "Product status" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "Active" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Loading products",
    );
    expect(
      screen.getByRole("link", { name: "Create product" }),
    ).toHaveAttribute("aria-disabled", "true");
  });

  it("fails closed on generated no-data responses and ignores superseded product pages", async () => {
    listAdminProductsMock.mockResolvedValueOnce(failure());
    renderProducts();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not load this page. Retry without leaving the administration area.",
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

  it("renders exactly five responsive wizard steps with current and completed semantics", async () => {
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
      "Mappings",
      "Preview",
      "Review and publish",
    ]);
    for (const step of within(desktop).getAllByRole("button")) {
      expect(step).toHaveClass("whitespace-nowrap");
      expect(step).not.toHaveClass("break-words", "[overflow-wrap:anywhere]");
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
      "Mappings",
      "Preview",
      "Review and publish",
    ]) {
      expect(
        within(desktop).getByRole("button", { name: label }),
      ).not.toHaveAttribute("aria-current");
      expect(
        within(desktop).getByRole("button", { name: label }),
      ).not.toHaveAttribute("data-completed");
    }
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 1 of 5Product details",
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
      "Step 2 of 5Repositories",
    );
    expect(
      screen.getByRole("heading", { name: "No repositories added" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Add or reuse a Bitbucket repository before configuring a mapping.",
      ),
    ).toBeVisible();

    await userEvent.click(
      within(desktop).getByRole("button", { name: "Mappings" }),
    );
    expect(
      screen.getByRole("heading", { name: "No mappings configured" }),
    ).toBeVisible();
    await userEvent.click(
      within(desktop).getByRole("button", { name: "Preview" }),
    );
    expect(
      screen.getByRole("heading", { name: "Validation has not run" }),
    ).toBeVisible();
    await userEvent.click(
      within(desktop).getByRole("button", { name: "Review and publish" }),
    );
    expect(
      screen.getByRole("button", { name: "Publish product" }),
    ).toBeDisabled();
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 5 of 5Review and publish",
    );
    expect(
      within(desktop).getByRole("button", { name: "Review and publish" }),
    ).not.toHaveAttribute("data-completed");
    expect(
      within(desktop)
        .getAllByRole("button")
        .slice(0, 4)
        .every((step) => step.dataset.completed === "true"),
    ).toBe(true);
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
      "Step 2 of 5Repositories",
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
      "Mappings",
      "Preview",
      "Review and publish",
    ]) {
      expect(screen.getByRole("button", { name: label })).toBeDisabled();
    }
    expect(
      screen.getByRole("button", { name: "Product details" }),
    ).toBeEnabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Save and continue" }));
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
    await user.click(screen.getByRole("button", { name: "Save and continue" }));
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
    await user.click(screen.getByRole("button", { name: "Save and continue" }));
    expect(createAdminProductMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: { description: null, name: "Alpha Embedded" },
    });
    expect(toastSuccessMock).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "Save and continue" }),
    ).toBeDisabled();

    await act(async () => {
      resolveCreate?.(ok(canonicalCreatedProduct, 201));
    });

    expect(toastSuccessMock).toHaveBeenCalledWith("Draft saved");
    expect(
      screen.getByRole("button", { name: "Repositories", current: "step" }),
    ).toBeEnabled();
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 2 of 5Repositories",
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
      screen.getByRole("button", { name: "Save and continue" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Save and continue" }),
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
    await user.click(screen.getByRole("button", { name: "Save and continue" }));

    expect(
      await screen.findByText("A product already uses this name."),
    ).toBeVisible();
    expect(name).toHaveFocus();
    expect(name).toHaveValue("Duplicate Product");
    expect(description).toHaveValue("Still recoverable");
    expect(toastSuccessMock).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Save and continue" }));
    expect(
      screen.queryByText("A product already uses this name."),
    ).not.toBeInTheDocument();
    expect(name).toHaveAttribute("aria-invalid", "false");
    expect(
      screen.getByRole("button", { name: "Save and continue" }),
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
      screen.getByRole("button", { name: "Save and continue" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not save this draft. Your entries are still here. Review the error and try again.",
    );
    expect(name).toHaveValue("Recoverable Product");
    expect(screen.getByRole("alert")).not.toHaveTextContent("provider secret");
    expect(
      screen.getByRole("button", { name: "Save and continue" }),
    ).toBeEnabled();
    await userEvent.type(name, " revised");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    createAdminProductMock.mockReturnValueOnce(
      new Promise<ReturnType<typeof ok<AdminProductResponse>>>(() => undefined),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Save and continue" }),
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
    const form = screen
      .getByRole("button", { name: "Save and continue" })
      .closest("form");
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
    await user.click(screen.getByRole("button", { name: "Save and continue" }));

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
    await user.click(screen.getByRole("button", { name: "Save and continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not save this draft. Your entries are still here. Review the error and try again.",
    );
    expect(name).toHaveValue("Rejected Product");
    expect(description).toHaveValue("Conflict-safe description");
    expect(
      screen.getByRole("button", { name: "Save and continue" }),
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

  it("fails closed when a generated product has no editable candidate", async () => {
    renderWizard(inactivePublishedProduct);
    const user = userEvent.setup();
    expect(
      screen.getByRole("heading", { name: inactivePublishedProduct.name }),
    ).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Description" })).toHaveValue(
      "",
    );
    await user.type(
      screen.getByRole("textbox", { name: "Name" }),
      " candidate",
    );
    await user.click(screen.getByRole("button", { name: "Save and continue" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not save this draft. Your entries are still here. Review the error and try again.",
    );
    expect(updateAdminProductCandidateMock).not.toHaveBeenCalled();
  });

  it("clears duplicate ownership when conflicted edits are discarded", async () => {
    updateAdminProductCandidateMock.mockResolvedValueOnce(conflict());
    renderWizard(activeProduct);
    const user = userEvent.setup();
    const name = screen.getByRole("textbox", { name: "Name" });
    await user.clear(name);
    await user.type(name, "Duplicate Candidate");
    await user.click(screen.getByRole("button", { name: "Save and continue" }));
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
      "Step 2 of 5Repositories",
    );
    await user.click(screen.getByRole("button", { name: "Product details" }));
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue(
      activeProduct.name,
    );
    expect(screen.getByRole("textbox", { name: "Description" })).toHaveValue(
      activeProduct.candidate_revision?.description,
    );
  });

  it("keeps active and candidate summaries visibly distinct with the exact neutral banner", async () => {
    renderOverview();

    expect(
      await screen.findByRole("heading", { name: "Zulu Mobile" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Published configuration remains active while you edit this draft.",
      ),
    ).toBeVisible();
    const published = screen.getByRole("region", {
      name: "Published configuration",
    });
    const candidate = screen.getByRole("region", {
      name: "Draft configuration",
    });
    expect(within(published).getByText("Version 4")).toBeVisible();
    expect(
      within(published).getByText("Published mobile strings"),
    ).toBeVisible();
    expect(within(candidate).getByText("Version 5")).toBeVisible();
    expect(
      within(candidate).getByText("Candidate mobile strings"),
    ).toBeVisible();
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
      within(detailNavigation).getByRole("link", { name: "Mappings" }),
    ).toHaveAttribute("href", `/admin/products/${activeProduct.id}/mappings`);
    expect(
      within(detailNavigation).getByRole("link", { name: "Preview" }),
    ).toHaveAttribute("href", `/admin/products/${activeProduct.id}/preview`);
    expect(
      within(detailNavigation).getAllByRole("link", { current: "page" }),
    ).toHaveLength(1);
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
      screen.getByRole("link", { name: "Mappings", current: "page" }),
    ).toHaveAttribute("href", `/admin/products/${activeProduct.id}/mappings`);
    expect(
      screen.getByRole("link", { name: "Mappings", current: "page" }),
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
      "We could not load this page. Retry without leaving the administration area.",
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
      "We could not load this page. Retry without leaving the administration area.",
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
    expect(screen.getByText("Not configured")).toBeVisible();
    expect(screen.getByText("No description")).toBeVisible();
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

  it("mounts the product collection, new wizard, and URL-backed overview routes inside the guarded shell", async () => {
    const collectionView = render(
      <MemoryRouter initialEntries={["/admin/products"]}>
        <AppRouter />
      </MemoryRouter>,
    );

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
    render(
      <MemoryRouter
        initialEntries={[`/admin/products/${activeProduct.id}/overview`]}
      >
        <AppRouter />
      </MemoryRouter>,
    );

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
      await screen.findByRole("heading", { name: "Repositories" }),
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
      within(sectionNavigation).getByRole("link", { name: "Mappings" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Mappings" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Add a mapping that represents one localization format and layout.",
      ),
    ).toBeVisible();
    await userEvent.click(screen.getByRole("link", { name: "Preview" }));
    expect(
      await screen.findByRole("heading", { name: "Preview" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Run validation to detect files, languages, and partial translation samples.",
      ),
    ).toBeVisible();
  });

  it("reuses or registers credential-free repositories with responsive API ordering", async () => {
    exposeTask2Repositories();
    const registeredRepository: AdminRepositoryResponse = {
      id: "00000000-0000-4000-8000-000000000303",
      descriptive_name: null,
      workspace: "new-workspace",
      repository_slug: "new-repository",
    };
    createAdminRepositoryMock.mockResolvedValueOnce(
      ok(registeredRepository, 201),
    );
    render(
      <MemoryRouter
        initialEntries={[`/admin/products/${activeProduct.id}/repositories`]}
      >
        <AppRouter />
      </MemoryRouter>,
    );

    const table = await screen.findByRole("table", { name: "Repositories" });
    expect(listAdminRepositoriesMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      query: { cursor: null, limit: 50 },
    });
    expect(
      within(table)
        .getAllByRole("row")
        .slice(1)
        .map((row) => row.textContent),
    ).toEqual([
      expect.stringContaining("Mobile application source"),
      expect.stringContaining("localization-team/mobile-translations"),
    ]);
    expect(table.parentElement?.parentElement).toHaveClass(
      "hidden",
      "md:block",
    );
    const mobileList = screen.getByLabelText("Repositories mobile list");
    expect(mobileList).toHaveClass("md:hidden", "min-w-0", "max-w-full");
    expect(
      within(mobileList)
        .getAllByRole("article")
        .map((row) => row.textContent),
    ).toEqual([
      expect.stringContaining("Mobile application source"),
      expect.stringContaining("localization-team/mobile-translations"),
    ]);
    await userEvent.click(
      within(table).getByRole("button", {
        name: "Use Mobile application source",
      }),
    );
    expect(
      within(table).getByRole("button", {
        name: "Mobile application source selected",
      }),
    ).toBeDisabled();

    await userEvent.type(
      screen.getByRole("textbox", { name: "Workspace" }),
      "new-workspace",
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Repository slug" }),
      "new-repository",
    );
    expect(
      screen.queryByLabelText(/credential|password|token|secret/i),
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Register repository" }),
    );
    expect(createAdminRepositoryMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        descriptive_name: null,
        repository_slug: "new-repository",
        workspace: "new-workspace",
      },
    });
    expect(
      await screen.findByText("new-workspace/new-repository"),
    ).toBeVisible();
  });

  it("uses only live branch results for direct source and target controls", async () => {
    exposeTask2Repositories();
    renderWizard(activeProduct);
    await userEvent.click(screen.getByRole("button", { name: "Mappings" }));

    expect(
      await screen.findByRole("heading", { name: "Mappings" }),
    ).toBeVisible();
    expect(screen.getByRole("radio", { name: "Direct" })).toBeChecked();
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
    });

    const sourceBranch = await screen.findByRole("combobox", {
      name: "Source branch",
    });
    await userEvent.click(sourceBranch);
    expect(screen.getByRole("option", { name: "main" })).toBeVisible();
    expect(
      screen.getByRole("option", {
        name: "release/2026-with-a-very-long-opaque-provider-branch-name",
      }),
    ).toBeVisible();
    await userEvent.click(screen.getByRole("option", { name: "main" }));

    const defaultTarget = screen.getByRole("combobox", {
      name: "Default target",
    });
    expect(defaultTarget).toBeDisabled();
    await userEvent.click(
      screen.getByRole("checkbox", {
        name: "Allow target release/2026-with-a-very-long-opaque-provider-branch-name",
      }),
    );
    expect(defaultTarget).toBeEnabled();
    await userEvent.click(defaultTarget);
    await userEvent.click(
      screen.getByRole("option", {
        name: "release/2026-with-a-very-long-opaque-provider-branch-name",
      }),
    );

    expect(
      screen.queryByRole("button", { name: /delete mapping/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: /glob|path|file|locale|format/i }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(2);
  });

  it("confirms topology changes before clearing direct values and exposes explicit separate sides", async () => {
    exposeTask2Repositories();
    renderWizard(activeProduct);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Mappings" }));
    await screen.findByRole("heading", { name: "Mappings" });
    await user.click(screen.getByRole("combobox", { name: "Repository" }));
    await user.click(
      screen.getByRole("option", {
        name: "Mobile application source — product-team/mobile-app",
      }),
    );
    await user.click(screen.getByRole("radio", { name: "Separate" }));

    const dialog = screen.getByRole("alertdialog", {
      name: "Change mapping topology?",
    });
    expect(dialog).toHaveTextContent(
      "Changing topology clears the repository and branch selections in this unsaved mapping.",
    );
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("radio", { name: "Direct" })).toBeChecked();
    expect(
      screen.getByRole("combobox", { name: "Repository" }),
    ).toHaveTextContent("Mobile application source");

    await user.click(screen.getByRole("radio", { name: "Separate" }));
    await user.click(screen.getByRole("button", { name: "Change topology" }));
    expect(screen.getByRole("radio", { name: "Separate" })).toBeChecked();
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
    await user.click(screen.getByRole("button", { name: "Mappings" }));
    await screen.findByRole("heading", { name: "Mappings" });
    await user.click(screen.getByRole("combobox", { name: "Repository" }));
    await user.click(
      screen.getByRole("option", {
        name: "Mobile application source — product-team/mobile-app",
      }),
    );
    await user.click(
      await screen.findByRole("combobox", { name: "Source branch" }),
    );
    await user.click(screen.getByRole("option", { name: "main" }));
    const target = screen.getByRole("checkbox", {
      name: "Allow target release/2026-with-a-very-long-opaque-provider-branch-name",
    });
    await user.click(target);
    await user.click(screen.getByRole("combobox", { name: "Default target" }));
    await user.click(
      screen.getByRole("option", {
        name: "release/2026-with-a-very-long-opaque-provider-branch-name",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Save mapping" }));

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
    expect(target).toBeChecked();
    expect(
      screen.getByRole("combobox", { name: "Default target" }),
    ).toHaveTextContent(
      "release/2026-with-a-very-long-opaque-provider-branch-name",
    );

    await user.click(screen.getByRole("button", { name: "Save mapping" }));
    expect(toastSuccessMock).toHaveBeenCalledWith("Draft saved");
    expect(await screen.findAllByText("Draft version 6")).toHaveLength(2);
  });

  it("renders mapping tables as ordered stacks below 768px with local focusable branch overflow", async () => {
    exposeTask2Repositories();
    listAdminCandidateMappingsMock.mockResolvedValueOnce(
      ok({ items: [directMapping], next_cursor: null }),
    );
    renderWizard(activeProduct);
    await userEvent.click(screen.getByRole("button", { name: "Mappings" }));

    const table = await screen.findByRole("table", { name: "Mappings" });
    expect(table.parentElement?.parentElement).toHaveClass(
      "hidden",
      "md:block",
    );
    const mobileList = screen.getByLabelText("Mappings mobile list");
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
