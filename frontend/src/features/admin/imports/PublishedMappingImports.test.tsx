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
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  listAdminPublishedMappingImports,
  startAdminPublishedMappingImport,
  type AdminPublishedMappingImportResponse,
  type AdminRepositoryResponse,
  type ImportParserIssue,
  type RoleName,
} from "../../../api/client";
import { useSession } from "../../auth/session";
import { PublishedMappingImports } from "./PublishedMappingImports";
import { useImportPolling } from "./useImportPolling";

vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));
vi.mock("../../auth/session", () => ({ useSession: vi.fn() }));

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();
  return {
    ...original,
    listAdminPublishedMappingImports: vi.fn(),
    startAdminPublishedMappingImport: vi.fn(),
  };
});

vi.mock("./useImportPolling", async (importOriginal) => {
  const original = await importOriginal<typeof import("./useImportPolling")>();
  return { ...original, useImportPolling: vi.fn() };
});

const listImportsMock = vi.mocked(listAdminPublishedMappingImports);
const startImportMock = vi.mocked(startAdminPublishedMappingImport);
const useImportPollingMock = vi.mocked(useImportPolling);
const toastSuccessMock = vi.mocked(toast.success);
const publishedFinalizationDecisionMock = vi.hoisted(() => vi.fn());

vi.mock("./mutationAuthority", async (importOriginal) => {
  const original = await importOriginal<typeof import("./mutationAuthority")>();
  return {
    ...original,
    hasLivePublishedAuthority: (
      ...args: Parameters<typeof original.hasLivePublishedAuthority>
    ) => {
      const decision = original.hasLivePublishedAuthority(...args);
      publishedFinalizationDecisionMock(decision);
      return decision;
    },
  };
});

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

function ok<T>(data: T) {
  return {
    data,
    error: undefined,
    request: new Request("http://localhost/api/v1/admin"),
    response: new Response(null, { status: 200 }),
  };
}

function publishedImport(
  mappingId: string,
  overrides: Partial<AdminPublishedMappingImportResponse> = {},
): AdminPublishedMappingImportResponse {
  return {
    action: "run_import",
    active_baseline: null,
    active_revision_id: "revision-1",
    capability: "ready",
    dataset_status: "not_created",
    error_category: null,
    error_message: null,
    execution_number: null,
    id: null,
    latest_execution_at: null,
    mapping_id: mappingId,
    parser_issue_remaining_count: 0,
    parser_issues: [],
    repository_sides: [
      {
        repository_id: "repository-1",
        role: "direct",
        source_branch: `branch/${mappingId}`,
      },
    ],
    retry_count: 0,
    state: "not_imported",
    topology: "direct",
    ...overrides,
  };
}

function baseline(
  ...references: Array<{
    commit: string;
    repositoryId: string;
    role: "direct" | "keys" | "translations";
  }>
) {
  return {
    imported_at: "2026-09-03T12:00:00Z",
    source_references: references.map((reference, position) => ({
      commit_hash: reference.commit,
      path: `locales/source-${position}.json`,
      position,
      repository_id: reference.repositoryId,
      repository_side: reference.role,
      sha256: "a".repeat(64),
      size_bytes: 42,
      source_branch: "main",
    })),
  };
}

function renderImports(
  props: Partial<React.ComponentProps<typeof PublishedMappingImports>> = {},
) {
  return render(
    <PublishedMappingImports
      accessToken="memory-only-admin-bearer"
      productId="product-1"
      repositories={repositories}
      {...props}
    />,
    { wrapper: MemoryRouter },
  );
}

describe("published mapping import collection", () => {
  beforeEach(() => {
    vi.mocked(useSession).mockReturnValue({
      state: {
        status: "authenticated",
        accessToken: "memory-only-admin-bearer",
        principal: {
          id: "admin-1",
          roles: ["admin"],
          email: "admin@example.com",
          must_change_password: false,
        },
      },
    } as ReturnType<typeof useSession>);
    listImportsMock.mockReset();
    startImportMock.mockReset();
    toastSuccessMock.mockReset();
    publishedFinalizationDecisionMock.mockClear();
    listImportsMock.mockResolvedValue(ok({ items: [], next_cursor: null }));
    useImportPollingMock.mockImplementation((options) => ({
      automaticUpdatesPaused: false,
      importRecord: options.initialImport,
      pollingError: false,
      refreshStatus: vi.fn(),
    }));
  });

  afterEach(() => cleanup());

  function parserIssue(
    issue_code: ImportParserIssue["issue_code"] = "malformed_file",
    overrides: Partial<ImportParserIssue> = {},
  ): ImportParserIssue {
    return {
      issue_code,
      message_key: `import.parser.${issue_code}`,
      path: "locales/en.json",
      repository_side: "direct",
      line: null,
      column: null,
      ...overrides,
    };
  }

  function parserFailure(
    overrides: Partial<AdminPublishedMappingImportResponse> = {},
  ) {
    return publishedImport("mapping-1", {
      id: "import-1",
      execution_number: 2,
      action: "retry_import",
      state: "import_failed",
      error_category: "bounded_failure",
      parser_issues: [parserIssue()],
      ...overrides,
    });
  }

  it.each([false, true])(
    "renders the exact atomic parser failure with retained dataset=%s",
    async (retained) => {
      listImportsMock.mockResolvedValue(
        ok({
          items: [
            parserFailure({
              dataset_status: retained ? "retained" : "not_created",
              state: retained ? "may_be_stale" : "import_failed",
              active_baseline: retained
                ? baseline({
                    commit: "a".repeat(40),
                    repositoryId: "repository-1",
                    role: "direct",
                  })
                : null,
              error_message: "SECRET provider body <xml>source</xml>",
            }),
          ],
          next_cursor: null,
        }),
      );
      renderImports();
      const row = await screen.findByTestId("published-import-row-mapping-1");
      const alert = within(row).getByRole("alert");
      expect(alert).toHaveTextContent(
        "Localization files could not be imported",
      );
      expect(alert).toHaveTextContent(
        `One or more configured files are malformed, ambiguous, or contain unsupported structure. ${retained ? "The last successful translation dataset remains active." : "No translation dataset was created."}`,
      );
      expect(row).toHaveTextContent(
        retained ? "May be stale" : "Import failed",
      );
      if (retained) expect(row).toHaveTextContent("a".repeat(12));
      expect(within(row).getAllByRole("button")).toHaveLength(1);
      expect(
        within(row).getByRole("button", { name: "Retry import" }),
      ).toBeEnabled();
      expect(document.body).not.toHaveTextContent("SECRET provider body");
      expect(within(row).queryByRole("link")).not.toBeInTheDocument();
    },
  );

  it.each([0, 1, 5, 7])(
    "bounds %s parser issues and preserves provider order within Keys before Translations",
    async (count) => {
      const categories = [
        "malformed_file",
        "ambiguous_structure",
        "unsupported_structure",
        "duplicate_key",
        "base_language_required",
      ] as const;
      const issues = Array.from({ length: count }, (_, index) =>
        parserIssue(categories[index % 5], {
          path: `locales/${count - index}.json`,
          repository_side: index % 2 ? "keys" : "translations",
          line: index === 0 ? 12 : null,
          column: index === 0 ? 4 : null,
        }),
      );
      listImportsMock.mockResolvedValue(
        ok({
          items: [
            parserFailure({
              error_category: count === 0 ? null : "bounded_failure",
              topology: "separate",
              parser_issues: issues,
              parser_issue_remaining_count: count > 5 ? 8 : 0,
            }),
          ],
          next_cursor: null,
        }),
      );
      renderImports();
      const row = await screen.findByTestId("published-import-row-mapping-1");
      const alert = within(row).getByRole("alert");
      expect(alert).toHaveTextContent(
        "Localization files could not be imported",
      );
      const shown = within(alert).queryAllByRole("listitem");
      expect(shown).toHaveLength(Math.min(5, count));
      const ordered = [...issues]
        .sort(
          (a, b) =>
            Number(a.repository_side === "translations") -
            Number(b.repository_side === "translations"),
        )
        .slice(0, 5);
      ordered.forEach((issue, index) => {
        expect(shown[index]).toHaveTextContent(issue.path);
        expect(shown[index]).toHaveTextContent(
          issue.repository_side === "keys" ? "Keys" : "Translations",
        );
        if (issue.line !== null)
          expect(shown[index]).toHaveTextContent("Line 12, column 4");
        else expect(shown[index]).not.toHaveTextContent(/Line|column/);
      });
      if (count > 5) expect(alert).toHaveTextContent("And 10 more errors.");
      else expect(alert).not.toHaveTextContent(/And .* more errors/);
    },
  );

  it("uses all five closed categories and literal paths without exposing extra issue fields", async () => {
    const codes = [
      "malformed_file",
      "ambiguous_structure",
      "unsupported_structure",
      "duplicate_key",
      "base_language_required",
    ] as const;
    listImportsMock.mockResolvedValue(
      ok({
        items: [
          parserFailure({
            parser_issues: codes.map((code) => ({
              ...parserIssue(code, {
                path: '<img src=x onerror="alert(1)">.json',
                line: 9,
              }),
              message: "SECRET source excerpt",
              exception: "SQL provider exception",
            })),
          }),
        ],
        next_cursor: null,
      }),
    );
    renderImports();
    const row = await screen.findByTestId("published-import-row-mapping-1");
    for (const label of [
      "Malformed file",
      "Ambiguous structure",
      "Unsupported structure",
      "Duplicate key",
      "Base language required",
    ])
      expect(within(row).getByText(label)).toBeVisible();
    expect(row).toHaveTextContent('<img src=x onerror="alert(1)">.json');
    expect(row.querySelector("img")).toBeNull();
    expect(row).not.toHaveTextContent(/SECRET|SQL provider|column/);
    expect(row).toHaveTextContent("Line 9");
  });

  it.each<RoleName>([
    "admin",
    "product_manager_reviewer",
    "translator",
    "viewer",
  ])(
    "offers exact product base-language recovery only for admin, role=%s",
    async (role) => {
      const session = vi.mocked(useSession).getMockImplementation()!();
      if (session.state.status === "authenticated")
        session.state.principal.roles = [role];
      vi.mocked(useSession).mockReturnValue(session);
      listImportsMock.mockResolvedValue(
        ok({
          items: [
            parserFailure({
              parser_issues: [parserIssue("base_language_required")],
            }),
          ],
          next_cursor: null,
        }),
      );
      renderImports({ productId: "product-specific-42" });
      const row = await screen.findByTestId("published-import-row-mapping-1");
      if (role === "admin")
        expect(
          within(row).getByRole("link", { name: "Configure base language" }),
        ).toHaveAttribute(
          "href",
          "/admin/products/product-specific-42/preview",
        );
      else expect(within(row).queryByRole("link")).not.toBeInTheDocument();
      expect(within(row).getAllByRole("button")).toHaveLength(1);
      expect(
        within(row).getByRole("button", { name: "Retry import" }),
      ).toBeEnabled();
    },
  );

  it("UI3-C02 renders the named empty state after the complete collection loads", async () => {
    renderImports();

    expect(
      await screen.findByRole("heading", {
        name: "No published mappings to import",
      }),
    ).toBeVisible();
    expect(screen.getByText(/Publish a validated mapping/)).toBeVisible();
  });

  it("UI3-C06 preserves named loading geometry while the page chain is pending", () => {
    listImportsMock.mockReturnValueOnce(new Promise(() => undefined) as never);
    renderImports();

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading published mappings",
    );
    expect(screen.getByTestId("published-import-skeleton")).toHaveClass("h-24");
  });

  it("UI3-C14 accumulates every cursor page in server order and keeps only the first duplicate", async () => {
    const first = publishedImport("mapping-1");
    const duplicate = publishedImport("mapping-2", {
      repository_sides: [
        {
          repository_id: "repository-1",
          role: "direct",
          source_branch: "branch/first-occurrence",
        },
      ],
    });
    const ignoredDuplicate = publishedImport("mapping-2", {
      repository_sides: [
        {
          repository_id: "repository-1",
          role: "direct",
          source_branch: "branch/ignored-duplicate",
        },
      ],
    });
    const third = publishedImport("mapping-3");
    listImportsMock
      .mockResolvedValueOnce(
        ok({ items: [first, duplicate], next_cursor: "opaque-page-2" }),
      )
      .mockResolvedValueOnce(
        ok({ items: [ignoredDuplicate, third], next_cursor: null }),
      );

    renderImports();

    const table = await screen.findByRole("table", {
      name: "Published mapping imports",
    });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    expect(rows.map((row) => row.getAttribute("data-mapping-id"))).toEqual([
      "mapping-1",
      "mapping-2",
      "mapping-3",
    ]);
    expect(table).toHaveTextContent("branch/first-occurrence");
    expect(table).not.toHaveTextContent("branch/ignored-duplicate");
    expect(listImportsMock).toHaveBeenNthCalledWith(1, {
      auth: "memory-only-admin-bearer",
      path: { product_id: "product-1" },
      query: { cursor: null, limit: 50, status: "all" },
      signal: expect.any(AbortSignal),
    });
    expect(listImportsMock).toHaveBeenNthCalledWith(2, {
      auth: "memory-only-admin-bearer",
      path: { product_id: "product-1" },
      query: { cursor: "opaque-page-2", limit: 50, status: "all" },
      signal: expect.any(AbortSignal),
    });
  });

  it("discards an obsolete page chain when product authority changes", async () => {
    let resolveOldSecond:
      ((value: ReturnType<typeof ok<unknown>>) => void) | undefined;
    listImportsMock.mockImplementation((options) => {
      if (options.path.product_id === "old-product") {
        if (options.query?.cursor === null) {
          return Promise.resolve(
            ok({
              items: [publishedImport("old-mapping-1")],
              next_cursor: "old-page-2",
            }),
          ) as never;
        }
        return new Promise((resolve) => {
          resolveOldSecond = resolve;
        }) as never;
      }
      return Promise.resolve(
        ok({ items: [publishedImport("new-mapping")], next_cursor: null }),
      ) as never;
    });
    const view = renderImports({ productId: "old-product" });
    await waitFor(() => expect(listImportsMock).toHaveBeenCalledTimes(2));
    const oldSignal = listImportsMock.mock.calls[1]?.[0].signal;

    view.rerender(
      <PublishedMappingImports
        accessToken="replacement-authority"
        productId="new-product"
        repositories={repositories}
      />,
    );
    expect((await screen.findAllByText("branch/new-mapping"))[0]).toBeVisible();
    expect(oldSignal?.aborted).toBe(true);
    await act(async () => {
      resolveOldSecond?.(
        ok({ items: [publishedImport("old-mapping-2")], next_cursor: null }),
      );
    });
    expect(screen.queryByText(/old-mapping/)).not.toBeInTheDocument();
  });

  it("fails the whole chain closed when a cursor repeats and retries from page one", async () => {
    listImportsMock
      .mockResolvedValueOnce(
        ok({ items: [publishedImport("mapping-1")], next_cursor: "repeat" }),
      )
      .mockResolvedValueOnce(
        ok({ items: [publishedImport("mapping-2")], next_cursor: "repeat" }),
      )
      .mockResolvedValueOnce(
        ok({ items: [publishedImport("mapping-3")], next_cursor: null }),
      );
    renderImports();

    expect(
      await screen.findByRole("heading", {
        name: "Published imports unavailable",
      }),
    ).toBeVisible();
    expect(screen.queryByText("branch/mapping-1")).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", {
        name: "Retry loading published imports",
      }),
    );
    expect((await screen.findAllByText("branch/mapping-3"))[0]).toBeVisible();
    expect(listImportsMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        query: { cursor: null, limit: 50, status: "all" },
      }),
    );
  });

  it("renders every closed status and only the exact server-projected action", async () => {
    const items = [
      publishedImport("not-imported"),
      publishedImport("queued", {
        action: "import_in_progress",
        execution_number: 1,
        id: "import-queued",
        latest_execution_at: "2026-09-03T12:00:00Z",
        state: "queued",
      }),
      publishedImport("running", {
        action: "import_in_progress",
        execution_number: 1,
        id: "import-running",
        latest_execution_at: "2026-09-03T12:00:00Z",
        state: "running",
      }),
      publishedImport("current", {
        action: "refresh_import",
        active_baseline: baseline({
          commit: "c".repeat(40),
          repositoryId: "repository-1",
          role: "direct",
        }),
        execution_number: 1,
        id: "import-current",
        state: "current",
      }),
      publishedImport("stale", {
        action: "retry_import",
        active_baseline: baseline({
          commit: "d".repeat(40),
          repositoryId: "repository-1",
          role: "direct",
        }),
        error_category: "timeout",
        error_message: "Published import unavailable",
        execution_number: 2,
        id: "import-stale",
        state: "may_be_stale",
      }),
      publishedImport("review", {
        action: "review_baseline_change",
        active_baseline: baseline({
          commit: "e".repeat(40),
          repositoryId: "repository-1",
          role: "direct",
        }),
        execution_number: 2,
        id: "import-review",
        state: "review_required",
      }),
      publishedImport("failed", {
        action: "retry_import",
        error_category: "bounded_failure",
        error_message: "Published import unavailable",
        execution_number: 1,
        id: "import-failed",
        state: "import_failed",
      }),
    ];
    listImportsMock.mockResolvedValueOnce(ok({ items, next_cursor: null }));
    renderImports();

    const table = await screen.findByRole("table", {
      name: "Published mapping imports",
    });
    for (const label of [
      "Not imported",
      "Queued",
      "Running",
      "Current",
      "May be stale",
      "Review required",
      "Import failed",
    ]) {
      expect(within(table).getByText(label)).toBeVisible();
    }
    expect(
      within(table).getByRole("button", { name: "Run import" }),
    ).toBeEnabled();
    expect(
      within(table).getByRole("button", { name: "Refresh import" }),
    ).toBeEnabled();
    expect(
      within(table).getAllByRole("button", { name: "Retry import" }),
    ).toHaveLength(2);
    expect(
      within(table).getAllByRole("button", { name: "Import in progress" }),
    ).toHaveLength(2);
    expect(
      within(table).getByRole("button", { name: "Review baseline change" }),
    ).toBeEnabled();
  });

  it("UI3-C03 renders the exact missing-baseline value instead of a blank cell", async () => {
    listImportsMock.mockResolvedValueOnce(
      ok({ items: [publishedImport("mapping-1")], next_cursor: null }),
    );
    renderImports();

    expect(
      await screen.findAllByText("No successful import yet"),
    ).not.toHaveLength(0);
  });

  it("UI3-C11 renders a fixed row-local action-free error without server prose", async () => {
    listImportsMock.mockResolvedValueOnce(
      ok({
        items: [
          publishedImport("mapping-1", {
            action: "retry_import",
            error_category: "connection_required",
            error_message: "SECRET provider body https://unsafe.example/token",
            execution_number: 1,
            id: "import-1",
            state: "import_failed",
          }),
        ],
        next_cursor: null,
      }),
    );
    renderImports();

    const alert = (await screen.findAllByRole("alert"))[0];
    expect(alert).toHaveTextContent("Bitbucket connection required");
    expect(alert).toHaveTextContent(
      "The organizational Bitbucket connection is not ready for imports.",
    );
    expect(within(alert).queryByRole("button")).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("SECRET provider body");
    expect(document.body).not.toHaveTextContent("unsafe.example");
  });

  it("UI3-C18 keeps Keys and Translations selectors and baseline commits in one mapping boundary", async () => {
    const keysCommit = "1".repeat(40);
    const translationsCommit = "2".repeat(40);
    listImportsMock.mockResolvedValueOnce(
      ok({
        items: [
          publishedImport("mapping-1", {
            action: "refresh_import",
            active_baseline: baseline(
              {
                commit: keysCommit,
                repositoryId: "repository-1",
                role: "keys",
              },
              {
                commit: translationsCommit,
                repositoryId: "repository-2",
                role: "translations",
              },
            ),
            id: "import-1",
            repository_sides: [
              {
                repository_id: "repository-1",
                role: "keys",
                source_branch: "keys/main",
              },
              {
                repository_id: "repository-2",
                role: "translations",
                source_branch: "translations/main",
              },
            ],
            state: "current",
            topology: "separate",
          }),
        ],
        next_cursor: null,
      }),
    );
    renderImports();

    const row = await screen.findByTestId("published-import-row-mapping-1");
    expect(row).toHaveTextContent("Keys");
    expect(row).toHaveTextContent("Translations");
    expect(row).toHaveTextContent(keysCommit.slice(0, 12));
    expect(row).toHaveTextContent(translationsCommit.slice(0, 12));
  });

  it("UI3-C19 retains the complete successful baseline after a failed refresh", async () => {
    const commit = "3".repeat(40);
    listImportsMock.mockResolvedValueOnce(
      ok({
        items: [
          publishedImport("mapping-1", {
            action: "retry_import",
            active_baseline: baseline({
              commit,
              repositoryId: "repository-1",
              role: "direct",
            }),
            error_category: "provider_unavailable",
            error_message: "Published import unavailable",
            execution_number: 2,
            id: "import-1",
            retry_count: 1,
            state: "may_be_stale",
          }),
        ],
        next_cursor: null,
      }),
    );
    renderImports();

    const row = await screen.findByTestId("published-import-row-mapping-1");
    expect(row).toHaveTextContent("May be stale");
    expect(row).toHaveTextContent(commit.slice(0, 12));
    expect(row).toHaveTextContent("Retry 1");
    expect(row).toHaveTextContent("Bitbucket unavailable");
  });

  it("UI3-C21 renders stacked mobile articles and 44px wrapping action controls", async () => {
    listImportsMock.mockResolvedValueOnce(
      ok({ items: [publishedImport("mapping-1")], next_cursor: null }),
    );
    renderImports();

    const mobileList = await screen.findByLabelText(
      "Published mapping imports mobile list",
    );
    expect(mobileList).toHaveClass("min-w-0", "max-w-full", "overflow-x-clip");
    expect(within(mobileList).getByRole("article")).toBeVisible();
    expect(
      within(mobileList).getByRole("button", { name: "Run import" }),
    ).toHaveClass("min-h-[44px]", "w-full");
  });

  it("UI3-C22 confines opaque repository and branch values to keyboard-accessible local overflow", async () => {
    const longBranch = `release/${"opaque-segment/".repeat(30)}final`;
    listImportsMock.mockResolvedValueOnce(
      ok({
        items: [
          publishedImport("mapping-1", {
            repository_sides: [
              {
                repository_id: "repository-1",
                role: "direct",
                source_branch: longBranch,
              },
            ],
          }),
        ],
        next_cursor: null,
      }),
    );
    renderImports();

    const regions = await screen.findAllByRole("region", {
      name: "Source repository and branch",
    });
    expect(regions[0]).toHaveAttribute("tabindex", "0");
    expect(regions[0]).toHaveClass("max-w-full", "overflow-x-auto");
    expect(regions[0]).toHaveTextContent(longBranch);
  });

  it("UI3-C25 preserves complete long names, fixed prose, and visible action labels", async () => {
    const longName = `Application ${"localization-".repeat(20)}source`;
    const longRepositories = [
      { ...repositories[0], descriptive_name: longName },
    ];
    listImportsMock.mockResolvedValueOnce(
      ok({ items: [publishedImport("mapping-1")], next_cursor: null }),
    );
    renderImports({ repositories: longRepositories });

    expect((await screen.findAllByText(longName))[0]).toBeVisible();
    expect(
      screen.getAllByRole("button", { name: "Run import" })[0],
    ).toHaveTextContent("Run import");
  });

  it("submits one generated mutation, keeps server state visible, and then reloads every page", async () => {
    let resolveStart:
      ((value: ReturnType<typeof ok<unknown>>) => void) | undefined;
    const initial = publishedImport("mapping-1");
    const queued = publishedImport("mapping-1", {
      action: "import_in_progress",
      execution_number: 1,
      id: "import-1",
      latest_execution_at: "2026-09-03T12:00:00Z",
      state: "queued",
    });
    listImportsMock
      .mockResolvedValueOnce(ok({ items: [initial], next_cursor: null }))
      .mockResolvedValueOnce(ok({ items: [queued], next_cursor: null }));
    startImportMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveStart = resolve;
      }) as never,
    );
    renderImports();
    const desktopTable = await screen.findByRole("table", {
      name: "Published mapping imports",
    });
    const run = within(desktopTable).getByRole("button", {
      name: "Run import",
    });

    act(() => {
      run.click();
      run.click();
    });
    await waitFor(() => expect(startImportMock).toHaveBeenCalledOnce());
    expect(within(desktopTable).getByText("Not imported")).toBeVisible();
    expect(startImportMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { mapping_id: "mapping-1", product_id: "product-1" },
      signal: expect.any(AbortSignal),
    });
    await act(async () => {
      resolveStart?.(ok(queued));
    });
    expect(await within(desktopTable).findByText("Queued")).toBeVisible();
    expect(listImportsMock).toHaveBeenCalledTimes(2);
    expect(publishedFinalizationDecisionMock).toHaveBeenLastCalledWith(true);
  });

  it("ignores a deferred start response after product authority changes", async () => {
    let resolveOldStart:
      ((value: ReturnType<typeof ok<unknown>>) => void) | undefined;
    const oldItem = publishedImport("old-mapping");
    const newItem = publishedImport("new-mapping");
    listImportsMock.mockImplementation(
      (options) =>
        Promise.resolve(
          ok({
            items: [
              options.path.product_id === "old-product" ? oldItem : newItem,
            ],
            next_cursor: null,
          }),
        ) as never,
    );
    startImportMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveOldStart = resolve;
      }) as never,
    );

    const view = renderImports({ productId: "old-product" });
    const oldTable = await screen.findByRole("table", {
      name: "Published mapping imports",
    });
    await userEvent.click(
      within(oldTable).getByRole("button", { name: "Run import" }),
    );
    await waitFor(() => expect(startImportMock).toHaveBeenCalledOnce());

    view.rerender(
      <PublishedMappingImports
        accessToken="replacement-authority"
        productId="new-product"
        repositories={repositories}
      />,
    );
    const newTable = await screen.findByRole("table", {
      name: "Published mapping imports",
    });
    const newAction = within(newTable).getByRole("button", {
      name: "Run import",
    });
    newAction.focus();
    expect(newAction).toHaveFocus();
    const callsBeforeOldCompletion = listImportsMock.mock.calls.length;

    await act(async () => {
      resolveOldStart?.(
        ok(
          publishedImport("old-mapping", {
            action: "import_in_progress",
            execution_number: 1,
            id: "old-import",
            state: "queued",
          }),
        ),
      );
    });

    await waitFor(() => expect(newAction).toHaveFocus());
    expect(toastSuccessMock).not.toHaveBeenCalled();
    expect(listImportsMock).toHaveBeenCalledTimes(callsBeforeOldCompletion);
    expect(screen.queryByText("branch/old-mapping")).not.toBeInTheDocument();
    expect(screen.getAllByText("branch/new-mapping")[0]).toBeVisible();
    expect(newAction).toBeEnabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("invalidates a deferred start response when the component unmounts", async () => {
    let resolveStart:
      ((value: ReturnType<typeof ok<unknown>>) => void) | undefined;
    listImportsMock.mockResolvedValueOnce(
      ok({ items: [publishedImport("mapping-1")], next_cursor: null }),
    );
    startImportMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveStart = resolve;
      }) as never,
    );
    const outsideFocus = document.createElement("button");
    outsideFocus.textContent = "Outside import screen";
    document.body.append(outsideFocus);
    const view = renderImports();

    const table = await screen.findByRole("table", {
      name: "Published mapping imports",
    });
    await userEvent.click(
      within(table).getByRole("button", { name: "Run import" }),
    );
    await waitFor(() => expect(startImportMock).toHaveBeenCalledOnce());
    const requestSignal = startImportMock.mock.calls[0]?.[0].signal;
    const collectionCallsBeforeUnmount = listImportsMock.mock.calls.length;

    view.unmount();
    outsideFocus.focus();
    expect(outsideFocus).toHaveFocus();
    await act(async () => {
      resolveStart?.(
        ok(
          publishedImport("mapping-1", {
            action: "import_in_progress",
            execution_number: 1,
            id: "import-1",
            state: "queued",
          }),
        ),
      );
    });

    expect(requestSignal).toBeInstanceOf(AbortSignal);
    expect(requestSignal?.aborted).toBe(true);
    expect(toastSuccessMock).not.toHaveBeenCalled();
    expect(listImportsMock).toHaveBeenCalledTimes(collectionCallsBeforeUnmount);
    expect(outsideFocus).toHaveFocus();
    expect(publishedFinalizationDecisionMock).toHaveBeenLastCalledWith(false);
    outsideFocus.remove();
  });

  it("shows bounded manual observation recovery after polling pauses", async () => {
    const refreshStatus = vi.fn();
    useImportPollingMock.mockImplementation((options) => ({
      automaticUpdatesPaused: true,
      importRecord: options.initialImport,
      pollingError: false,
      refreshStatus,
    }));
    listImportsMock.mockResolvedValueOnce(
      ok({
        items: [
          publishedImport("mapping-1", {
            action: "import_in_progress",
            execution_number: 1,
            id: "import-1",
            latest_execution_at: "2026-09-03T12:00:00Z",
            state: "running",
          }),
        ],
        next_cursor: null,
      }),
    );
    renderImports();

    expect(
      await screen.findAllByText("Automatic status updates paused"),
    ).not.toHaveLength(0);
    await userEvent.click(
      screen.getAllByRole("button", { name: "Refresh status" })[0],
    );
    expect(refreshStatus).toHaveBeenCalledOnce();
  });

  it("opens one mapping-scoped rewrite review from the activated responsive action", async () => {
    listImportsMock.mockResolvedValueOnce(
      ok({
        items: [
          publishedImport("mapping-1", {
            action: "review_baseline_change",
            execution_number: 2,
            id: "import-1",
            state: "review_required",
          }),
        ],
        next_cursor: null,
      }),
    );
    renderImports();

    const table = await screen.findByRole("table", {
      name: "Published mapping imports",
    });
    await userEvent.click(
      within(table).getByRole("button", { name: "Review baseline change" }),
    );
    expect(
      screen.getByRole("alertdialog", {
        name: "Review rewritten source history",
      }),
    ).toBeVisible();
  });
});
