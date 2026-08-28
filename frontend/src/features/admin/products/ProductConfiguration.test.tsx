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
import { MemoryRouter, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createAdminProduct,
  deactivateAdminProduct,
  getAdminProduct,
  listAdminProducts,
  readSystemStatus,
  updateAdminProductCandidate,
  type AdminProductResponse,
} from "../../../api/client";
import { useSession } from "../../auth/session";
import { ProductOverviewPage } from "./ProductOverviewPage";
import { ProductsPage } from "./ProductsPage";
import { ProductWizardPage } from "./ProductWizardPage";
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
    createAdminProduct: vi.fn(),
    deactivateAdminProduct: vi.fn(),
    getAdminProduct: vi.fn(),
    listAdminProducts: vi.fn(),
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

const createAdminProductMock = vi.mocked(createAdminProduct);
const deactivateAdminProductMock = vi.mocked(deactivateAdminProduct);
const getAdminProductMock = vi.mocked(getAdminProduct);
const listAdminProductsMock = vi.mocked(listAdminProducts);
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
    createAdminProductMock.mockReset();
    deactivateAdminProductMock.mockReset();
    getAdminProductMock.mockReset();
    getAdminProductMock.mockResolvedValue(ok(activeProduct));
    listAdminProductsMock.mockReset();
    listAdminProductsMock.mockResolvedValue(
      ok({ items: [activeProduct, candidateOnlyProduct], next_cursor: null }),
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
    listAdminProductsMock.mockReturnValueOnce(
      new Promise<never>(() => undefined),
    );
    const loadingView = renderProducts();

    expect(screen.getByRole("heading", { name: "Products" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Loading products");
    expect(
      screen.getByRole("link", { name: "Create product" }),
    ).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(
      screen.getByRole("link", { name: "Create product" }),
    );
    expect(screen.getByTestId("current-location")).toHaveTextContent("/");
    await waitFor(() => expect(listAdminProductsMock).toHaveBeenCalledOnce());

    loadingView.unmount();
    listAdminProductsMock.mockRejectedValueOnce(
      new Error("provider response containing Secret-That-Must-Not-Leak"),
    );
    listAdminProductsMock.mockResolvedValueOnce(
      ok({ items: [], next_cursor: null }),
    );
    renderProducts();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "We could not load this page. Retry without leaving the administration area.",
    );
    expect(alert).not.toHaveTextContent("Secret-That-Must-Not-Leak");
    await userEvent.click(
      screen.getByRole("button", { name: "Retry loading page" }),
    );

    expect(
      await screen.findByRole("heading", { name: "No products configured" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Create a product to connect repositories and validate a localization layout.",
      ),
    ).toBeVisible();
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
    renderProducts();

    const table = await screen.findByRole("table", { name: "Products" });
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
    ]);
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
    expect(
      await screen.findAllByText(candidateOnlyProduct.name),
    ).toHaveLength(2);

    await act(async () => {
      resolveFirst?.(ok({ items: [activeProduct], next_cursor: null }));
    });
    expect(screen.queryByText(activeProduct.name)).not.toBeInTheDocument();
  });

  it("renders exactly five responsive wizard steps with current and completed semantics", async () => {
    renderWizard(activeProduct);

    const desktop = screen.getByRole("navigation", {
      name: "Product setup steps",
    });
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
    expect(
      within(desktop).getByRole("button", {
        name: "Product details",
        current: "step",
      }),
    ).toBeVisible();
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 1 of 5Product details",
    );

    const description = screen.getByRole("textbox", { name: "Description" });
    await userEvent.clear(description);
    await userEvent.type(description, "Changed candidate details");
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
  });

  it("creates a product with an optional description and announces Draft saved only after the response", async () => {
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
    expect(screen.getByRole("button", { name: "Repositories" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Save and continue" }));
    const name = screen.getByRole("textbox", { name: "Name" });
    expect(name).toHaveFocus();
    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(createAdminProductMock).not.toHaveBeenCalled();

    await user.type(name, "Alpha Embedded");
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
      resolveCreate?.(ok(candidateOnlyProduct, 201));
    });

    expect(toastSuccessMock).toHaveBeenCalledWith("Draft saved");
    expect(
      screen.getByRole("button", { name: "Repositories", current: "step" }),
    ).toBeEnabled();
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 2 of 5Repositories",
    );
  });

  it("focuses Name and preserves every attempted field on a duplicate-name conflict", async () => {
    createAdminProductMock.mockResolvedValueOnce(conflict());
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
    cleanup();

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
    fireEvent.submit(form!);
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

    await user.click(repositories);
    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(screen.getByLabelText("Product setup progress")).toHaveTextContent(
      "Step 2 of 5Repositories",
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
  });

  it("fails closed without product authority and retries generated no-data overview results", async () => {
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
      .mockResolvedValueOnce(ok(candidateOnlyProduct));
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
    expect(
      await screen.findByRole("heading", { name: candidateOnlyProduct.name }),
    ).toBeVisible();
    expect(screen.getByText("Not configured")).toBeVisible();
    expect(screen.getByText("No description")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Deactivate product" }),
    ).not.toBeInTheDocument();
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
    expect(screen.getByText("Active")).toBeVisible();
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
    await user.click(confirm);
    expect(deactivateAdminProductMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { product_id: activeProduct.id },
    });
    expect(screen.getByText("Active")).toBeVisible();
    expect(confirm).toBeDisabled();

    await act(async () => {
      resolveDeactivate?.(ok({ ...activeProduct, is_active: false }));
    });
    expect(await screen.findByText("Inactive")).toBeVisible();

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
  });
});
