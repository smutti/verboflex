import "@testing-library/jest-dom/vitest";

import {
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
  listAdminRepositories,
  listAdminRevisionMappings,
  type AdminMappingResponse,
  type AdminProductResponse,
  type AdminRepositoryResponse,
} from "../../../api/client";
import { ProductRepositoriesPage } from "./ProductRepositoriesPage";

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();
  return {
    ...original,
    getAdminProduct: vi.fn(),
    listAdminRepositories: vi.fn(),
    listAdminRevisionMappings: vi.fn(),
  };
});

const getProductMock = vi.mocked(getAdminProduct);
const listRepositoriesMock = vi.mocked(listAdminRepositories);
const listRevisionMappingsMock = vi.mocked(listAdminRevisionMappings);

const productId = "00000000-0000-4000-8000-000000000100";
const revisionId = "00000000-0000-4000-8000-000000000200";

const product: AdminProductResponse = {
  id: productId,
  name: "Door Station",
  is_active: true,
  affected_mapping_count: 0,
  active_revision: null,
  candidate_revision: {
    id: revisionId,
    description: null,
    is_published: false,
    name: "Door Station",
    version: 2,
  },
};

function repository(index: number): AdminRepositoryResponse {
  return {
    id: `00000000-0000-4000-8000-${index.toString().padStart(12, "0")}`,
    descriptive_name: `Repository ${index}`,
    workspace: "product-team",
    repository_slug: `repository-${index}`,
  };
}

function ok<T>(data: T) {
  return {
    data,
    error: undefined,
    request: new Request("http://localhost/api/v1/admin/repositories"),
    response: new Response(null, { status: 200 }),
  };
}

function directMapping(repositoryId: string, index = 1): AdminMappingResponse {
  return {
    id: `00000000-0000-4000-8000-${(400 + index).toString().padStart(12, "0")}`,
    topology: "direct",
    candidate_version: 2,
    primary_repository_id: repositoryId,
    primary_source_branch: "main",
    primary_localization_root: null,
    translations_repository_id: null,
    translations_source_branch: null,
    translations_localization_root: null,
    allowed_target_branches: ["main"],
    default_target_branch: "main",
    selected_layout_candidate_id: null,
    selected_layout_version: null,
  };
}

describe("ProductRepositoriesPage cursor boundaries", () => {
  beforeEach(() => {
    getProductMock.mockReset();
    getProductMock.mockResolvedValue(ok(product));
    listRepositoriesMock.mockReset();
    listRevisionMappingsMock.mockReset();
    listRevisionMappingsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
  });

  afterEach(cleanup);

  it.each([
    [0, "No repositories added"],
    [1, "All 1 repository loaded"],
    [50, "All 50 repositories loaded"],
  ])(
    "renders the complete %i-item first page in one request",
    async (count, copy) => {
      listRepositoriesMock.mockResolvedValue(
        ok({
          items: Array.from({ length: count }, (_, index) =>
            repository(index + 1),
          ),
          next_cursor: null,
        }),
      );

      render(
        <ProductRepositoriesPage accessToken="memory-only-admin-bearer" />,
      );

      expect(await screen.findByText(copy)).toBeInTheDocument();
      expect(listRepositoriesMock).toHaveBeenCalledTimes(1);
      expect(listRepositoriesMock).toHaveBeenCalledWith({
        auth: "memory-only-admin-bearer",
        query: { cursor: null, limit: 50 },
        signal: expect.any(AbortSignal),
      });
    },
  );

  it("loads repository 51 with one opaque-cursor request and no duplicate identity", async () => {
    const firstPage = Array.from({ length: 50 }, (_, index) =>
      repository(index + 1),
    );
    listRepositoriesMock
      .mockResolvedValueOnce(
        ok({ items: firstPage, next_cursor: "opaque-repository-page-2" }),
      )
      .mockResolvedValueOnce(
        ok({ items: [firstPage[49], repository(51)], next_cursor: null }),
      );
    const user = userEvent.setup();

    render(<ProductRepositoriesPage accessToken="memory-only-admin-bearer" />);

    expect(
      await screen.findByText("50 repositories loaded — more available"),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Load more repositories" }),
    );

    expect(
      await screen.findByText("All 51 repositories loaded"),
    ).toBeInTheDocument();
    expect(listRepositoriesMock).toHaveBeenCalledTimes(2);
    expect(listRepositoriesMock).toHaveBeenNthCalledWith(2, {
      auth: "memory-only-admin-bearer",
      query: { cursor: "opaque-repository-page-2", limit: 50 },
      signal: expect.any(AbortSignal),
    });
    await waitFor(() =>
      expect(
        screen.getAllByRole("button", { name: /Use Repository 51/ }),
      ).toHaveLength(2),
    );
    expect(
      screen.getAllByRole("button", { name: /Use Repository 50/ }),
    ).toHaveLength(2);
  });

  it("retries rejected initial and continuation pages without losing loaded repositories", async () => {
    listRepositoriesMock
      .mockResolvedValueOnce(ok(undefined as never))
      .mockResolvedValueOnce(
        ok({ items: [repository(1)], next_cursor: "opaque-page-2" }),
      )
      .mockResolvedValueOnce(ok(undefined as never))
      .mockResolvedValueOnce(ok({ items: [repository(2)], next_cursor: null }));
    const user = userEvent.setup();

    render(<ProductRepositoriesPage accessToken="recovery-admin-bearer" />);

    expect(await screen.findByText("Repositories unavailable")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Retry loading page" }),
    );
    expect((await screen.findAllByText("Repository 1"))[0]).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Load more repositories" }),
    );
    expect(
      await screen.findByText("More repositories unavailable"),
    ).toBeVisible();
    expect(screen.getAllByText("Repository 1")[0]).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Retry loading repositories" }),
    );
    expect((await screen.findAllByText("Repository 2"))[0]).toBeVisible();
    expect(listRepositoriesMock).toHaveBeenCalledTimes(4);
  });

  it("explains that the embedded catalogue is global and mapping persistence happens next", async () => {
    listRepositoriesMock.mockResolvedValue(
      ok({ items: [repository(1)], next_cursor: null }),
    );

    render(
      <ProductRepositoriesPage
        accessToken="memory-only-admin-bearer"
        embedded
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Repository catalogue" }),
    ).toBeVisible();
    expect(screen.getByRole("note")).toHaveTextContent(
      "The product association is saved only when you save a mapping in the next step.",
    );
    expect(
      screen.getByRole("form", { name: "Register a Bitbucket repository" }),
    ).toBeVisible();
  });

  it("announces required catalogue fields and focuses the first invalid control", async () => {
    listRepositoriesMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    const user = userEvent.setup();

    render(
      <ProductRepositoriesPage
        accessToken="memory-only-admin-bearer"
        embedded
      />,
    );

    await screen.findByText("No repositories added");
    await user.click(
      screen.getByRole("button", { name: "Register repository" }),
    );

    const workspace = screen.getByRole("textbox", { name: "Workspace" });
    const slug = screen.getByRole("textbox", { name: "Repository slug" });
    expect(workspace).toHaveFocus();
    expect(workspace).toHaveAttribute("aria-invalid", "true");
    expect(slug).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Enter the Bitbucket workspace.")).toBeVisible();
    expect(screen.getByText("Enter the repository slug.")).toBeVisible();
  });

  it("shows only repositories referenced by this product mappings", async () => {
    const linked = repository(1);
    const unrelated = repository(2);
    listRepositoriesMock.mockResolvedValue(
      ok({ items: [linked, unrelated], next_cursor: null }),
    );
    listRevisionMappingsMock.mockResolvedValue(
      ok({ items: [directMapping(linked.id)], next_cursor: null }),
    );

    render(
      <MemoryRouter>
        <ProductRepositoriesPage
          accessToken="memory-only-admin-bearer"
          productId={productId}
        />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Repositories used by this product",
      }),
    ).toBeVisible();
    const list = screen.getByRole("list", {
      name: "Repositories used by this product",
    });
    expect(within(list).getByText("Repository 1")).toBeVisible();
    expect(within(list).queryByText("Repository 2")).not.toBeInTheDocument();
    expect(screen.queryByText("Register repository")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Use Repository/ }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("1 repository in use")).toHaveAttribute(
      "data-variant",
      "success",
    );
    expect(
      screen.getByRole("link", { name: "Manage mappings" }),
    ).toHaveAttribute("href", `/admin/products/${productId}/mappings`);
    expect(listRevisionMappingsMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { product_id: productId, revision_id: revisionId },
      query: { cursor: null, limit: 50 },
      signal: expect.any(AbortSignal),
    });
  });

  it("automatically resolves a mapped repository beyond the first catalogue page", async () => {
    const firstPage = Array.from({ length: 50 }, (_, index) =>
      repository(index + 1),
    );
    const linked = repository(51);
    listRepositoriesMock
      .mockResolvedValueOnce(
        ok({ items: firstPage, next_cursor: "opaque-repository-page-2" }),
      )
      .mockResolvedValueOnce(ok({ items: [linked], next_cursor: null }));
    listRevisionMappingsMock.mockResolvedValue(
      ok({ items: [directMapping(linked.id)], next_cursor: null }),
    );

    render(
      <MemoryRouter>
        <ProductRepositoriesPage
          accessToken="memory-only-admin-bearer"
          productId={productId}
        />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Repository 51")).toBeVisible();
    expect(listRepositoriesMock).toHaveBeenCalledTimes(2);
    expect(
      screen.queryByRole("button", { name: "Load more repositories" }),
    ).not.toBeInTheDocument();
  });

  it("renders an icon-led empty state and a direct mapping action", async () => {
    listRepositoriesMock.mockResolvedValue(
      ok({ items: [repository(1)], next_cursor: null }),
    );

    render(
      <MemoryRouter>
        <ProductRepositoriesPage
          accessToken="memory-only-admin-bearer"
          productId={productId}
        />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "No repositories in use",
      }),
    ).toBeVisible();
    expect(screen.getByTestId("product-repositories-empty-icon")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Configure a mapping" }),
    ).toHaveAttribute("href", `/admin/products/${productId}/mappings`);
  });

  it("focuses a bounded error when product mapping resolution fails", async () => {
    listRepositoriesMock.mockResolvedValue(
      ok({ items: [repository(1)], next_cursor: null }),
    );
    listRevisionMappingsMock.mockResolvedValueOnce(ok(undefined as never));

    render(
      <MemoryRouter>
        <ProductRepositoriesPage
          accessToken="memory-only-admin-bearer"
          productId={productId}
        />
      </MemoryRouter>,
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Product repositories unavailable");
    await waitFor(() => expect(alert).toHaveFocus());
    expect(alert).not.toHaveTextContent("repository mappings unavailable");
  });
});
