import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import {
  getAdminProduct,
  getAdminRepository,
  listAdminRevisionMappings,
  listAdminPublishedMappingImports,
  startAdminPublishedMappingImport,
  getAdminImport,
  type AdminPublishedMappingImportResponse,
} from "../../api/client";
import { ProductSourceUpdatesPage } from "./ProductSourceUpdatesPage";

vi.mock("../../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/client")>()),
  getAdminProduct: vi.fn(),
  getAdminRepository: vi.fn(),
  listAdminRevisionMappings: vi.fn(),
  listAdminPublishedMappingImports: vi.fn(),
  startAdminPublishedMappingImport: vi.fn(),
  getAdminImport: vi.fn(),
}));
vi.mock("../auth/session", () => ({
  useSession: () => ({
    state: { status: "authenticated", principal: { roles: ["admin"] } },
  }),
}));

function ok<T>(data: T) {
  return {
    data,
    error: undefined,
    request: new Request("http://localhost/api/v1"),
    response: new Response(null),
  };
}

const imported: AdminPublishedMappingImportResponse = {
  id: "import-1",
  mapping_id: "mapping-1",
  active_revision_id: "published-1",
  topology: "separate",
  repository_sides: [
    { role: "keys", repository_id: "app", source_branch: "main" },
    {
      role: "translations",
      repository_id: "translations",
      source_branch: "master",
    },
  ],
  state: "current",
  action: "refresh_import",
  capability: "ready",
  dataset_status: "active",
  execution_number: 1,
  latest_execution_at: "2026-01-01T12:00:00Z",
  retry_count: 0,
  error_category: null,
  error_message: null,
  parser_issues: [],
  parser_issue_remaining_count: 0,
  active_baseline: {
    imported_at: "2026-01-01T12:00:00Z",
    source_references: [
      {
        position: 0,
        repository_side: "keys",
        repository_id: "app",
        source_branch: "main",
        commit_hash: "a".repeat(40),
        path: "src/Main.kt",
        sha256: "a".repeat(64),
        size_bytes: 20,
      },
      {
        position: 1,
        repository_side: "translations",
        repository_id: "translations",
        source_branch: "master",
        commit_hash: "b".repeat(40),
        path: "base/strings.xml",
        sha256: "b".repeat(64),
        size_bytes: 30,
      },
    ],
  },
};

function show() {
  return render(
    <MemoryRouter initialEntries={["/products/p1/source-updates"]}>
      <Routes>
        <Route
          path="/products/:productId/source-updates"
          element={<ProductSourceUpdatesPage accessToken="synthetic-token" />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getAdminProduct).mockResolvedValue(
    ok({
      id: "p1",
      name: "Synthetic project",
      is_active: true,
      affected_mapping_count: 0,
      active_revision: {
        id: "published-1",
        version: 1,
        is_published: true,
        name: "Synthetic project",
        description: null,
      },
      candidate_revision: {
        id: "draft-2",
        version: 2,
        is_published: false,
        name: "Draft",
        description: null,
      },
    }),
  );
  vi.mocked(listAdminRevisionMappings).mockResolvedValue(
    ok({
      items: [
        {
          id: "mapping-1",
          topology: "separate",
          primary_repository_id: "app",
          primary_source_branch: "main",
          translations_repository_id: "translations",
          translations_source_branch: "master",
          allowed_target_branches: ["release"],
          default_target_branch: "release",
          selected_layout_candidate_id: "layout-1",
          selected_layout_version: 1,
          candidate_version: 1,
        },
      ],
      next_cursor: null,
    }),
  );
  vi.mocked(getAdminRepository).mockImplementation(async ({ path }) =>
    ok({
      id: path.repository_id,
      workspace: "synthetic-team",
      repository_slug: path.repository_id,
      descriptive_name:
        path.repository_id === "app" ? "Application" : "Shared translations",
      provider: "bitbucket",
    }),
  );
  vi.mocked(listAdminPublishedMappingImports).mockResolvedValue(
    ok({ items: [imported], next_cursor: null }),
  );
  vi.mocked(getAdminImport).mockResolvedValue(ok(imported));
});
afterEach(cleanup);

it("shows both published branches and commit IDs, then explicitly queues their shared refresh", async () => {
  const user = userEvent.setup();
  show();
  const table = await screen.findByRole("article", {
    name: "Application · Shared translations",
  });
  expect(table).toHaveTextContent("Application");
  expect(table).toHaveTextContent("Shared translations");
  expect(table).toHaveTextContent("main");
  expect(table).toHaveTextContent("master");
  expect(table).toHaveTextContent("aaaaaaaaaaaa");
  expect(table).toHaveTextContent("bbbbbbbbbbbb");
  expect(listAdminRevisionMappings).toHaveBeenCalledWith(
    expect.objectContaining({
      path: { product_id: "p1", revision_id: "published-1" },
    }),
  );
  expect(startAdminPublishedMappingImport).not.toHaveBeenCalled();
  const queued = {
    ...imported,
    state: "queued" as const,
    action: "import_in_progress" as const,
    execution_number: 2,
  };
  vi.mocked(startAdminPublishedMappingImport).mockResolvedValue(ok(queued));
  vi.mocked(listAdminPublishedMappingImports).mockResolvedValue(
    ok({ items: [queued], next_cursor: null }),
  );
  vi.mocked(getAdminImport).mockResolvedValue(ok(queued));
  await user.click(
    within(table).getByRole("button", { name: "Update catalog" }),
  );
  await waitFor(() =>
    expect(startAdminPublishedMappingImport).toHaveBeenCalledTimes(1),
  );
  expect(startAdminPublishedMappingImport).toHaveBeenCalledWith(
    expect.objectContaining({
      auth: "synthetic-token",
      path: { product_id: "p1", mapping_id: "mapping-1" },
    }),
  );
  expect(
    within(table).getByRole("button", { name: "Update in progress" }),
  ).toBeDisabled();
});

it("retries unavailable repository names without starting an import", async () => {
  vi.mocked(getAdminRepository).mockRejectedValueOnce(new Error("Unavailable"));
  const user = userEvent.setup();
  show();
  await user.click(
    await screen.findByRole("button", { name: "Retry loading sources" }),
  );
  expect(await screen.findByRole("article")).toHaveTextContent(
    "Shared translations",
  );
  expect(startAdminPublishedMappingImport).not.toHaveBeenCalled();
});

it("aborts source discovery when leaving the page", async () => {
  const view = show();
  await screen.findByRole("article");
  const signal = vi.mocked(getAdminProduct).mock.calls[0][0].signal;
  view.unmount();
  expect(signal?.aborted).toBe(true);
});

it("keeps the previous catalog available when an update times out", async () => {
  vi.mocked(listAdminPublishedMappingImports).mockResolvedValue(
    ok({
      items: [
        {
          ...imported,
          state: "may_be_stale",
          action: "retry_import",
          error_category: "timeout",
          dataset_status: "retained",
        },
      ],
      next_cursor: null,
    }),
  );
  show();
  expect(await screen.findByText("Catalog update unsuccessful")).toBeVisible();
  expect(
    screen.getByText(
      "The source did not respond in time. Try again in a few minutes.",
    ),
  ).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Open translation catalog" }),
  ).toHaveAttribute("href", "/products/p1/strings");
  expect(screen.getByRole("button", { name: "Retry update" })).toBeEnabled();
  expect(
    screen.queryByRole("link", {
      name: "Review translations with changed source text",
    }),
  ).toBeNull();
  expect(startAdminPublishedMappingImport).not.toHaveBeenCalled();
});

it("does not offer an empty catalog after the first update fails", async () => {
  vi.mocked(listAdminPublishedMappingImports).mockResolvedValue(
    ok({
      items: [
        {
          ...imported,
          state: "import_failed",
          action: "retry_import",
          active_baseline: null,
          dataset_status: "not_created",
        },
      ],
      next_cursor: null,
    }),
  );
  show();
  expect(
    await screen.findByText(
      "Strings will appear here after the first successful update.",
    ),
  ).toBeVisible();
  expect(
    screen.queryByRole("link", { name: "Open translation catalog" }),
  ).toBeNull();
});
