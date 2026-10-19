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
  getAdminBitbucketWorkspace,
  listAdminBitbucketRepositories,
  selectAdminBitbucketRepository,
  getAdminRepository,
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
    getAdminBitbucketWorkspace: vi.fn(),
    listAdminBitbucketRepositories: vi.fn(),
    selectAdminBitbucketRepository: vi.fn(),
    getAdminRepository: vi.fn(),
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
    vi.mocked(getAdminBitbucketWorkspace).mockReset();
    vi.mocked(getAdminBitbucketWorkspace).mockResolvedValue(
      ok({ workspace: "product-team" }),
    );
    vi.mocked(getAdminRepository).mockResolvedValue(ok(repository(1)));
    vi.mocked(selectAdminBitbucketRepository).mockReset();
    vi.mocked(selectAdminBitbucketRepository).mockResolvedValue(
      ok(repository(1)),
    );
    vi.mocked(listAdminBitbucketRepositories).mockReset();
    vi.mocked(listAdminBitbucketRepositories).mockResolvedValue(
      ok({
        workspace: "product-team",
        items: [
          {
            workspace: "product-team",
            repository_slug: "repository-1",
            name: "Repository 1",
          },
        ],
        next_cursor: null,
      }),
    );
    getProductMock.mockReset();
    getProductMock.mockResolvedValue(ok(product));
    listRepositoriesMock.mockReset();
    listRevisionMappingsMock.mockReset();
    listRevisionMappingsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
  });

  afterEach(cleanup);

  function picker(onRepositorySelected = vi.fn()) {
    return render(
      <MemoryRouter>
        <ProductRepositoriesPage
          accessToken="token"
          embedded
          onRepositorySelected={onRepositorySelected}
        />
      </MemoryRouter>,
    );
  }

  it("replaces manual registration and global catalogue with a workspace search", async () => {
    const selected = vi.fn();
    picker(selected);
    expect(await screen.findByText("Workspace: product-team")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Connect a Bitbucket repository" }),
    ).toBeVisible();
    expect(screen.queryByText("Use repository")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Repository selection prepares the mapping"),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Workspace")).not.toBeInTheDocument();
    await userEvent.click(
      await screen.findByRole("button", { name: "Connect Repository 1" }),
    );
    await waitFor(() => expect(selected).toHaveBeenCalledWith(repository(1)));
    expect(selectAdminBitbucketRepository).toHaveBeenCalledWith({
      auth: "token",
      body: { workspace: "product-team" },
      path: { repository_slug: "repository-1" },
    });
    expect(listRepositoriesMock).not.toHaveBeenCalled();
  });

  it("requires admin workspace setup without sending a discovery request", async () => {
    vi.mocked(getAdminBitbucketWorkspace).mockResolvedValue(
      ok({ workspace: null }),
    );
    picker();
    expect(
      await screen.findByRole("link", { name: "Open Bitbucket connection" }),
    ).toHaveAttribute("href", "/admin/bitbucket");
    expect(listAdminBitbucketRepositories).not.toHaveBeenCalled();
  });

  it("filters through Bitbucket instead of only searching the loaded results", async () => {
    picker();
    await screen.findByRole("button", { name: "Connect Repository 1" });
    vi.mocked(listAdminBitbucketRepositories).mockResolvedValue(
      ok({ workspace: "product-team", items: [], next_cursor: null }),
    );
    await userEvent.type(
      screen.getByRole("searchbox", { name: "Search repositories" }),
      "missing",
    );
    expect(await screen.findByText("No repositories found.")).toBeVisible();
    expect(listAdminBitbucketRepositories).toHaveBeenLastCalledWith(
      expect.objectContaining({
        query: { q: "missing", limit: 20, cursor: null },
      }),
    );
  });

  it("loads bounded continuation pages and retains results after a failed continuation", async () => {
    vi.mocked(listAdminBitbucketRepositories).mockResolvedValueOnce(
      ok({
        workspace: "product-team",
        items: [
          { workspace: "product-team", repository_slug: "one", name: "One" },
        ],
        next_cursor: "opaque",
      }),
    );
    picker();
    await screen.findByRole("button", { name: "Connect One" });
    vi.mocked(listAdminBitbucketRepositories).mockRejectedValueOnce(
      new Error("private diagnostics"),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Load more repositories" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not load more results",
    );
    expect(screen.getByRole("button", { name: "Connect One" })).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Load more repositories" }),
    );
    expect(
      await screen.findByRole("button", { name: "Connect Repository 1" }),
    ).toBeVisible();
    expect(listAdminBitbucketRepositories).toHaveBeenLastCalledWith(
      expect.objectContaining({
        query: { q: "", limit: 20, cursor: "opaque" },
      }),
    );
  });

  it("retains the picker and allows retry when linking fails", async () => {
    vi.mocked(selectAdminBitbucketRepository).mockRejectedValueOnce(
      new Error("private diagnostics"),
    );
    picker();
    await userEvent.click(
      await screen.findByRole("button", { name: "Connect Repository 1" }),
    );
    expect(await screen.findByText("Repository not connected")).toBeVisible();
    expect(screen.queryByText("private diagnostics")).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Connect Repository 1" }),
    );
    expect(
      await screen.findByRole("region", { name: "Connected repositories" }),
    ).toBeVisible();
  });

  it("ignores an older search response after the filter changes", async () => {
    picker();
    await screen.findByRole("button", { name: "Connect Repository 1" });
    let resolveOld!: (
      value: ReturnType<
        typeof ok<{
          workspace: string;
          items: { workspace: string; repository_slug: string; name: string }[];
          next_cursor: null;
        }>
      >,
    ) => void;
    vi.mocked(listAdminBitbucketRepositories).mockImplementationOnce(
      () =>
        new Promise<Parameters<typeof resolveOld>[0]>((resolve) => {
          resolveOld = resolve;
        }),
    );
    const search = screen.getByRole("searchbox", {
      name: "Search repositories",
    });
    await userEvent.type(search, "old");
    await waitFor(() =>
      expect(listAdminBitbucketRepositories).toHaveBeenLastCalledWith(
        expect.objectContaining({
          query: { q: "old", limit: 20, cursor: null },
        }),
      ),
    );
    vi.mocked(listAdminBitbucketRepositories).mockResolvedValueOnce(
      ok({ workspace: "product-team", items: [], next_cursor: null }),
    );
    await userEvent.clear(search);
    await userEvent.type(search, "new");
    await screen.findByText("No repositories found.");
    await act(async () =>
      resolveOld(
        ok({
          workspace: "product-team",
          items: [
            { workspace: "product-team", repository_slug: "old", name: "Old" },
          ],
          next_cursor: null,
        }),
      ),
    );
    expect(
      screen.queryByRole("button", { name: "Connect Old" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("No repositories found.")).toBeVisible();
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
    const list = await screen.findByRole("list", {
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
