import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  listAdminRepositories,
  type AdminRepositoryResponse,
} from "../../../api/client";
import { ProductRepositoriesPage } from "./ProductRepositoriesPage";

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();
  return { ...original, listAdminRepositories: vi.fn() };
});

const listRepositoriesMock = vi.mocked(listAdminRepositories);

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

describe("ProductRepositoriesPage cursor boundaries", () => {
  beforeEach(() => {
    listRepositoriesMock.mockReset();
  });

  afterEach(cleanup);

  it.each([
    [0, "No repositories added"],
    [1, "All 1 repository loaded"],
    [50, "All 50 repositories loaded"],
  ])("renders the complete %i-item first page in one request", async (count, copy) => {
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
  });

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

    render(
      <ProductRepositoriesPage accessToken="memory-only-admin-bearer" />,
    );

    expect(
      await screen.findByText("50 repositories loaded — more available"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Load more repositories" }));

    expect(await screen.findByText("All 51 repositories loaded")).toBeInTheDocument();
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
});
