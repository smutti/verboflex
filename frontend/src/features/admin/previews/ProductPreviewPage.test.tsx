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
  confirmAdminPreviewJob,
  createAdminPreviewJob,
  getAdminPreviewJob,
  getAdminProduct,
  listAdminCandidateMappings,
  listAdminRevisionMappings,
  listAdminRepositoryBranches,
  publishAdminProductCandidate,
  reactivateAdminProduct,
  updateAdminProductCandidate,
  type AdminMappingResponse,
  type AdminPreviewJobResponse,
  type AdminPreviewLayoutCandidateResponse,
  type AdminProductLifecycleConflictResponse,
  type AdminProductResponse,
} from "../../../api/client";
import { ProductPreviewPage } from "./ProductPreviewPage";

vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();
  return {
    ...original,
    confirmAdminPreviewJob: vi.fn(),
    createAdminPreviewJob: vi.fn(),
    getAdminPreviewJob: vi.fn(),
    getAdminProduct: vi.fn(),
    listAdminCandidateMappings: vi.fn(),
    listAdminRevisionMappings: vi.fn(),
    listAdminRepositoryBranches: vi.fn(),
    publishAdminProductCandidate: vi.fn(),
    reactivateAdminProduct: vi.fn(),
    updateAdminProductCandidate: vi.fn(),
  };
});

const confirmMock = vi.mocked(confirmAdminPreviewJob);
const createJobMock = vi.mocked(createAdminPreviewJob);
const getJobMock = vi.mocked(getAdminPreviewJob);
const getProductMock = vi.mocked(getAdminProduct);
const listCandidateMappingsMock = vi.mocked(listAdminCandidateMappings);
const listRevisionMappingsMock = vi.mocked(listAdminRevisionMappings);
const listBranchesMock = vi.mocked(listAdminRepositoryBranches);
const publishMock = vi.mocked(publishAdminProductCandidate);
const reactivateMock = vi.mocked(reactivateAdminProduct);
const updateProductMock = vi.mocked(updateAdminProductCandidate);
const toastSuccessMock = vi.mocked(toast.success);

const product: AdminProductResponse = {
  active_revision: null,
  candidate_revision: {
    description: "Candidate localization configuration",
    id: "00000000-0000-4000-8000-000000000201",
    is_published: false,
    name: "Mobile Product",
    version: 5,
  },
  id: "00000000-0000-4000-8000-000000000101",
  is_active: false,
  name: "Mobile Product",
};

const mapping: AdminMappingResponse = {
  allowed_target_branches: ["release/2026"],
  candidate_version: 5,
  default_target_branch: "release/2026",
  id: "00000000-0000-4000-8000-000000000301",
  primary_repository_id: "00000000-0000-4000-8000-000000000401",
  primary_source_branch: "main",
  selected_layout_candidate_id: null,
  selected_layout_version: null,
  topology: "direct",
  translations_repository_id: null,
  translations_source_branch: null,
};

const inactiveActiveOnlyProduct: AdminProductResponse = {
  ...product,
  active_revision: {
    description: "Published localization configuration",
    id: "00000000-0000-4000-8000-000000000202",
    is_published: true,
    name: product.name,
    version: 7,
  },
  candidate_revision: null,
  is_active: false,
};

const confirmedActiveMapping: AdminMappingResponse = {
  ...mapping,
  candidate_version: inactiveActiveOnlyProduct.active_revision!.version,
  selected_layout_candidate_id: "00000000-0000-4000-8000-000000000501",
  selected_layout_version: 1,
};

const formats = [
  ["android_xml", "Android XML", "app/src/main/res"],
  ["qt_ts", "Qt TS", "translations/{locale}.ts"],
  ["json", "JSON", "locales/{locale}.json"],
  ["ios_strings", "iOS strings", "App/{locale}.lproj/Localizable.strings"],
] as const;

function candidate(
  format: (typeof formats)[number][0],
  layoutIdentity: string,
  index: number,
): AdminPreviewLayoutCandidateResponse {
  return {
    confidence: 1,
    files: [`localization/${format}/messages.${index}`],
    format,
    id: `00000000-0000-4000-8000-0000000005${index.toString().padStart(2, "0")}`,
    keys: ["button.ok", "welcome.title"],
    languages: ["en", "it"],
    layout_identity: layoutIdentity,
    repository_side: "direct",
    samples: [
      { key: "button.ok", language: "en", translation: "OK" },
      { key: "welcome.title", language: "it", translation: "Benvenuto" },
    ],
    samples_are_partial: true,
    version: 1,
  };
}

const candidates = formats.map(([format, , identity], index) =>
  candidate(format, identity, index + 1),
);

function previewJob(
  overrides: Partial<AdminPreviewJobResponse> = {},
): AdminPreviewJobResponse {
  return {
    attempt: 1,
    candidate_revision_id: product.candidate_revision!.id,
    candidate_revision_version: 5,
    connection_generation: 7,
    created_at: "2026-08-28T12:00:00Z",
    detector_version: "detector-v1",
    error_code: null,
    finished_at: "2026-08-28T12:00:05Z",
    id: "00000000-0000-4000-8000-000000000601",
    input_digest: "a".repeat(64),
    is_current: true,
    mapping_id: mapping.id,
    product_id: product.id,
    repository_sides: [
      {
        commit_hash: "b".repeat(40),
        repository_id: mapping.primary_repository_id,
        role: "direct",
        source_branch: "main",
      },
    ],
    result: {
      detector_version: "detector-v1",
      digest: "c".repeat(64),
      layout_candidates: candidates,
    },
    started_at: "2026-08-28T12:00:01Z",
    state: "succeeded",
    ...overrides,
  };
}

function ok<T>(data: T, status = 200) {
  return {
    data,
    error: undefined,
    request: new Request("http://localhost/api/v1/admin/preview"),
    response: new Response(null, { status }),
  };
}

function failure<T>(error: T, status = 503) {
  return {
    data: undefined,
    error,
    request: new Request("http://localhost/api/v1/admin/preview"),
    response: new Response(null, { status }),
  };
}

function renderPage(productId = product.id) {
  return render(
    <MemoryRouter>
      <ProductPreviewPage
        accessToken="memory-only-admin-bearer"
        productId={productId}
      />
    </MemoryRouter>,
  );
}

function mappingAt(
  index: number,
  overrides: Partial<AdminMappingResponse> = {},
): AdminMappingResponse {
  return {
    ...mapping,
    id: `00000000-0000-4000-8000-${index.toString().padStart(12, "0")}`,
    ...overrides,
  };
}

async function runValidation() {
  await userEvent.click(
    await screen.findByRole("button", { name: "Run validation" }),
  );
  return screen.findByText("Succeeded");
}

describe("administrator product preview and publication page", () => {
  beforeEach(() => {
    confirmMock.mockReset();
    createJobMock.mockReset();
    createJobMock.mockResolvedValue(ok(previewJob(), 202));
    getJobMock.mockReset();
    getProductMock.mockReset();
    getProductMock.mockResolvedValue(ok(product));
    listCandidateMappingsMock.mockReset();
    listRevisionMappingsMock.mockReset();
    listRevisionMappingsMock.mockResolvedValue(
      ok({ items: [mapping], next_cursor: null }),
    );
    listBranchesMock.mockReset();
    listBranchesMock.mockResolvedValue(
      ok({
        items: [
          { commit_hash: "b".repeat(40), name: "main" },
          { commit_hash: "d".repeat(40), name: "release/2026" },
        ],
        next_cursor: null,
      }),
    );
    publishMock.mockReset();
    reactivateMock.mockReset();
    updateProductMock.mockReset();
    toastSuccessMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders approved loading, bounded error, and not-run states", async () => {
    getProductMock.mockReturnValueOnce(new Promise<never>(() => undefined));
    const view = renderPage();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading product preview",
    );
    await waitFor(() => expect(getProductMock).toHaveBeenCalledTimes(1));

    view.unmount();
    getProductMock.mockRejectedValueOnce(
      new Error("provider_token=private-diagnostic"),
    );
    renderPage();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "We could not load this page. Retry without leaving the administration area.",
    );
    expect(alert).not.toHaveTextContent("private-diagnostic");

    cleanup();
    getProductMock.mockResolvedValueOnce(ok(product));
    renderPage();
    expect(await screen.findByText("Validation has not run")).toBeVisible();
    expect(screen.getByText(/Run validation to detect files/)).toBeVisible();
  });

  it("fails closed on missing product and revision data, then retries the same page", async () => {
    getProductMock
      .mockResolvedValueOnce(ok(undefined as never))
      .mockResolvedValueOnce(
        ok({ ...product, candidate_revision: null, is_active: true }),
      )
      .mockResolvedValueOnce(ok(product));
    renderPage();

    expect(
      await screen.findByText("Product preview unavailable"),
    ).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Retry loading page" }),
    );
    await waitFor(() => expect(getProductMock).toHaveBeenCalledTimes(2));
    await userEvent.click(
      screen.getByRole("button", { name: "Retry loading page" }),
    );
    expect(await screen.findByText("Validation has not run")).toBeVisible();
  });

  it("renders mapping loading and bounded retry states", async () => {
    let rejectMappings!: (reason: Error) => void;
    listRevisionMappingsMock.mockReturnValueOnce(
      new Promise((_, reject) => {
        rejectMappings = reject;
      }) as never,
    );
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(
        "Loading product preview",
      );
    });
    await waitFor(() =>
      expect(listRevisionMappingsMock).toHaveBeenCalledOnce(),
    );
    rejectMappings(new Error("bounded mapping failure"));
    expect(
      await screen.findByText("Product preview unavailable"),
    ).toBeVisible();
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [mapping], next_cursor: null }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Retry loading page" }),
    );
    expect(await screen.findByText("Validation has not run")).toBeVisible();
  });

  it("admits only one pending validation submission", async () => {
    let resolveJob!: (
      value: ReturnType<typeof ok<AdminPreviewJobResponse>>,
    ) => void;
    createJobMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveJob = resolve;
      }) as never,
    );
    renderPage();
    const run = await screen.findByRole("button", { name: "Run validation" });
    await waitFor(() => expect(run).toBeEnabled());
    act(() => {
      run.click();
      run.click();
    });
    await waitFor(() => expect(createJobMock).toHaveBeenCalledOnce());
    resolveJob(ok(previewJob(), 202));
    expect(await screen.findByText("Succeeded")).toBeVisible();
  });

  it.each([0, 1, 50, 51])(
    "consumes the terminal cursor before rendering %i mappings as complete",
    async (mappingCount) => {
      const mappings = Array.from({ length: mappingCount }, (_, index) =>
        mappingAt(index + 1),
      );
      listRevisionMappingsMock.mockImplementation(async (options) => {
        const cursor = options.query?.cursor ?? null;
        if (mappingCount === 51 && cursor === null) {
          return ok({ items: mappings.slice(0, 50), next_cursor: "page-2" });
        }
        if (mappingCount === 51 && cursor === "page-2") {
          return ok({ items: mappings.slice(50), next_cursor: null });
        }
        return ok({ items: mappings, next_cursor: null });
      });

      renderPage();

      if (mappingCount === 0) {
        expect(await screen.findByText("No mappings configured")).toBeVisible();
      } else {
        expect(
          await screen.findByRole("heading", {
            name: `Mapping ${mappingCount}`,
          }),
        ).toBeVisible();
      }
      await waitFor(() =>
        expect(listRevisionMappingsMock).toHaveBeenCalledTimes(
          mappingCount === 51 ? 2 : 1,
        ),
      );
      expect(
        listRevisionMappingsMock.mock.calls.map(
          ([options]) => options.query?.cursor ?? null,
        ),
      ).toEqual(mappingCount === 51 ? [null, "page-2"] : [null]);
    },
  );

  it("keeps page-1 preview and lifecycle authority disabled after page-2 failure, then retries without duplicates", async () => {
    const firstPage = Array.from({ length: 50 }, (_, index) =>
      mappingAt(index + 1),
    );
    const boundaryMapping = mappingAt(51);
    listRevisionMappingsMock
      .mockResolvedValueOnce(ok({ items: firstPage, next_cursor: "page-2" }))
      .mockResolvedValueOnce(
        failure({ detail: "provider diagnostic must stay bounded" }),
      )
      .mockResolvedValueOnce(
        ok({
          items: [firstPage[0], boundaryMapping],
          next_cursor: null,
        }),
      );

    renderPage();

    const incomplete = await screen.findByRole("alert", {
      name: "Mapping collection incomplete",
    });
    expect(incomplete).toHaveTextContent("50 mappings loaded");
    expect(incomplete).not.toHaveTextContent("provider diagnostic");
    const runValidationButtons = screen.getAllByRole("button", {
      name: "Run validation",
    });
    expect(runValidationButtons).toHaveLength(50);
    expect(
      runValidationButtons.every((button) => button.hasAttribute("disabled")),
    ).toBe(true);
    expect(
      screen.getByRole("button", { name: "Publish product" }),
    ).toBeDisabled();
    expect(createJobMock).not.toHaveBeenCalled();
    expect(publishMock).not.toHaveBeenCalled();

    await userEvent.click(
      within(incomplete).getByRole("button", {
        name: "Retry loading mappings",
      }),
    );

    expect(
      await screen.findByRole("heading", { name: "Mapping 51" }),
    ).toBeVisible();
    await waitFor(() =>
      expect(
        screen.getAllByRole("button", { name: "Run validation" }),
      ).toHaveLength(51),
    );
    expect(listRevisionMappingsMock).toHaveBeenCalledTimes(3);
    expect(
      listRevisionMappingsMock.mock.calls.map(
        ([options]) => options.query?.cursor ?? null,
      ),
    ).toEqual([null, "page-2", "page-2"]);
    expect(createJobMock).not.toHaveBeenCalled();
    expect(publishMock).not.toHaveBeenCalled();
  });

  it("waits for mapping 51 and lets its missing active confirmation block reactivation", async () => {
    let releaseBoundaryPage!: () => void;
    const boundaryGate = new Promise<void>((resolve) => {
      releaseBoundaryPage = resolve;
    });
    const firstPage = Array.from({ length: 50 }, (_, index) =>
      mappingAt(index + 1, {
        candidate_version: inactiveActiveOnlyProduct.active_revision!.version,
        selected_layout_candidate_id:
          confirmedActiveMapping.selected_layout_candidate_id,
        selected_layout_version: 1,
      }),
    );
    const boundaryMapping = mappingAt(51, {
      candidate_version: inactiveActiveOnlyProduct.active_revision!.version,
      selected_layout_candidate_id: null,
      selected_layout_version: null,
    });
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock
      .mockResolvedValueOnce(ok({ items: firstPage, next_cursor: "page-2" }))
      .mockImplementationOnce(async () => {
        await boundaryGate;
        return ok({ items: [boundaryMapping], next_cursor: null });
      });

    renderPage();

    expect(
      await screen.findByText(
        "Loading complete mapping set: 50 mappings loaded.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Reactivate product" }),
    ).toBeDisabled();
    expect(reactivateMock).not.toHaveBeenCalled();

    releaseBoundaryPage();

    expect(
      await screen.findByText("Mapping 51: Preview confirmation required"),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Reactivate product" }),
    ).toBeDisabled();
    expect(reactivateMock).not.toHaveBeenCalled();
  });

  it("ignores a late mapping page from a superseded product generation", async () => {
    const nextProduct: AdminProductResponse = {
      ...product,
      candidate_revision: {
        ...product.candidate_revision!,
        id: "00000000-0000-4000-8000-000000000299",
      },
      id: "00000000-0000-4000-8000-000000000199",
      name: "Next Product",
    };
    let releaseStalePage!: () => void;
    const staleGate = new Promise<void>((resolve) => {
      releaseStalePage = resolve;
    });
    const staleBoundary = mappingAt(51);
    getProductMock
      .mockResolvedValueOnce(ok(product))
      .mockResolvedValueOnce(ok(nextProduct));
    listRevisionMappingsMock
      .mockResolvedValueOnce(
        ok({ items: [mappingAt(1)], next_cursor: "page-2" }),
      )
      .mockImplementationOnce(async () => {
        await staleGate;
        return ok({ items: [staleBoundary], next_cursor: null });
      })
      .mockResolvedValueOnce(ok({ items: [mappingAt(2)], next_cursor: null }));

    const view = renderPage(product.id);
    expect(
      await screen.findByText(
        "Loading complete mapping set: 1 mapping loaded.",
      ),
    ).toBeVisible();
    view.rerender(
      <MemoryRouter>
        <ProductPreviewPage
          accessToken="memory-only-admin-bearer"
          productId={nextProduct.id}
        />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Next Product/)).toBeVisible();
    releaseStalePage();
    await waitFor(() =>
      expect(listRevisionMappingsMock).toHaveBeenCalledTimes(3),
    );
    expect(
      screen.queryByRole("heading", { name: "Mapping 51" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Mapping 1" })).toBeVisible();
  });

  it("ignores a late preview poll from a superseded product and revision generation", async () => {
    const nextProduct: AdminProductResponse = {
      ...product,
      candidate_revision: {
        ...product.candidate_revision!,
        id: "00000000-0000-4000-8000-000000000298",
      },
      id: "00000000-0000-4000-8000-000000000198",
      name: "Polling Successor",
    };
    const queuedJob = previewJob({
      created_at: new Date().toISOString(),
      finished_at: null,
      result: null,
      started_at: null,
      state: "queued",
    });
    let releaseStalePoll!: () => void;
    const stalePollGate = new Promise<void>((resolve) => {
      releaseStalePoll = resolve;
    });
    getProductMock
      .mockResolvedValueOnce(ok(product))
      .mockResolvedValueOnce(ok(nextProduct));
    listRevisionMappingsMock
      .mockResolvedValueOnce(ok({ items: [mapping], next_cursor: null }))
      .mockResolvedValueOnce(ok({ items: [mappingAt(2)], next_cursor: null }));
    createJobMock.mockResolvedValueOnce(ok(queuedJob, 202));
    getJobMock.mockImplementationOnce(async () => {
      await stalePollGate;
      return ok(previewJob());
    });

    const view = renderPage(product.id);
    await userEvent.click(
      await screen.findByRole("button", { name: "Run validation" }),
    );
    expect(await screen.findByText("Queued", { exact: true })).toBeVisible();
    await waitFor(() => expect(getJobMock).toHaveBeenCalledTimes(1), {
      timeout: 3_000,
    });

    view.rerender(
      <MemoryRouter>
        <ProductPreviewPage
          accessToken="memory-only-admin-bearer"
          productId={nextProduct.id}
        />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/Polling Successor/)).toBeVisible();
    releaseStalePoll();

    await waitFor(() =>
      expect(
        screen.queryByText("Succeeded", { exact: true }),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "Confirm preview" }),
    ).not.toBeInTheDocument();
  });

  it("resolves exact commits and renders every four-format layout as a separate radio", async () => {
    renderPage();
    await runValidation();

    expect(listBranchesMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { repository_id: mapping.primary_repository_id },
      query: { cursor: null, limit: 100 },
    });
    expect(createJobMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        commits: [{ commit_hash: "b".repeat(40), role: "direct" }],
        expected_candidate_version: 5,
      },
      path: { mapping_id: mapping.id, product_id: product.id },
    });
    expect(screen.getAllByRole("radio")).toHaveLength(4);
    for (const [, label, identity] of formats) {
      expect(
        screen.getByRole("radio", { name: `${label} — ${identity}` }),
      ).toBeVisible();
    }

    await userEvent.click(
      screen.getByRole("radio", {
        name: "JSON — locales/{locale}.json",
      }),
    );
    const preview = screen.getByRole("region", {
      name: "Selected layout preview",
    });
    expect(preview).toHaveTextContent("Repository sidedirect");
    expect(preview).toHaveTextContent("Branchmain");
    expect(preview).toHaveTextContent("bbbbbbbbbbbb");
    expect(preview).toHaveTextContent("localization/json/messages.3");
    expect(preview).toHaveTextContent("en, it");
    expect(preview).toHaveTextContent(
      "Preview samples are partial: up to 10 per language and 100 total.",
    );
    const sampleTable = within(preview).getByRole("table", {
      name: "Partial translation samples",
    });
    expect(within(sampleTable).getAllByRole("row")[1]).toHaveTextContent(
      "enbutton.okOK",
    );
    expect(within(sampleTable).getAllByRole("row")[2]).toHaveTextContent(
      "itwelcome.titleBenvenuto",
    );
  });

  it.each([
    [
      "empty result",
      previewJob({
        result: {
          detector_version: "detector-v1",
          digest: "c".repeat(64),
          layout_candidates: [],
        },
      }),
      "No supported localization layout was found in this source branch.",
    ],
    [
      "low confidence",
      previewJob({
        result: {
          detector_version: "detector-v1",
          digest: "c".repeat(64),
          layout_candidates: [
            {
              ...candidates[0],
              confidence: 0.9,
            } as AdminPreviewLayoutCandidateResponse,
          ],
        },
      }),
      "This preview cannot be confirmed.",
    ],
    [
      "stale identity",
      previewJob({ is_current: false }),
      "This preview no longer matches the current draft. Run validation again.",
    ],
  ])("omits confirmation for %s", async (_name, invalidJob, expectedCopy) => {
    createJobMock.mockResolvedValueOnce(ok(invalidJob, 202));
    renderPage();
    await runValidation();

    expect(screen.getByRole("alert")).toHaveTextContent(expectedCopy);
    expect(
      screen.queryByRole("button", { name: "Confirm preview" }),
    ).not.toBeInTheDocument();
  });

  it("requires explicit current confirmation before named publication and trusts only backend success", async () => {
    confirmMock.mockResolvedValueOnce(
      ok({
        confirmed_at: "2026-08-28T12:01:00Z",
        confirmed_by: "00000000-0000-4000-8000-000000000001",
        job_id: previewJob().id,
        layout_candidate_id: candidates[2].id,
        layout_candidate_version: 1 as const,
        mapping_id: mapping.id,
        preview_digest: "c".repeat(64),
      }),
    );
    const publishedProduct: AdminProductResponse = {
      ...product,
      active_revision: { ...product.candidate_revision!, is_published: true },
      candidate_revision: null,
      is_active: true,
    };
    publishMock.mockResolvedValueOnce(ok(publishedProduct));
    renderPage();
    await runValidation();

    const publish = screen.getByRole("button", { name: "Publish product" });
    expect(publish).toBeDisabled();
    await userEvent.click(
      screen.getByRole("radio", {
        name: "JSON — locales/{locale}.json",
      }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );
    expect(confirmMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        layout_candidate_id: candidates[2].id,
        layout_candidate_version: 1,
        preview_digest: "c".repeat(64),
      },
      path: { job_id: previewJob().id },
    });
    expect(await screen.findByText("Confirmed")).toBeVisible();
    expect(publish).toBeEnabled();

    await userEvent.click(publish);
    const dialog = screen.getByRole("alertdialog", {
      name: "Publish Mobile Product?",
    });
    expect(dialog).toHaveTextContent(
      "The validated draft will atomically replace the current configuration for 1 mapping.",
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Publish product" }),
    );
    expect(publishMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        candidate_revision_id: product.candidate_revision!.id,
        expected_candidate_version: 5,
      },
      path: { product_id: product.id },
    });
    expect(await screen.findByText("Active")).toBeVisible();
    expect(toastSuccessMock).toHaveBeenCalledWith("Product published");
  });

  it("preserves current preview evidence and links blockers after publication conflict", async () => {
    confirmMock.mockResolvedValueOnce(
      ok({
        confirmed_at: "2026-08-28T12:01:00Z",
        confirmed_by: "admin-id",
        job_id: previewJob().id,
        layout_candidate_id: candidates[0].id,
        layout_candidate_version: 1 as const,
        mapping_id: mapping.id,
        preview_digest: "c".repeat(64),
      }),
    );
    publishMock.mockResolvedValueOnce(
      failure<
        AdminProductLifecycleConflictResponse & { provider_body: string }
      >(
        {
          blockers: ["preview_confirmation_required"],
          detail: "Product publication blocked",
          provider_body: "never render",
        },
        409,
      ),
    );
    renderPage();
    await runValidation();
    await userEvent.click(screen.getAllByRole("radio")[0]);
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Publish product" }),
    );
    await userEvent.click(
      screen
        .getByRole("alertdialog")
        .querySelector("button[data-variant='default']")!,
    );

    const alert = await screen.findByRole("alert", {
      name: "Publication blocked",
    });
    expect(alert).toHaveTextContent("Preview confirmation required");
    expect(alert).not.toHaveTextContent("never render");
    expect(
      within(alert).getByRole("link", { name: "Review mapping 1" }),
    ).toHaveAttribute("href", `#preview-${mapping.id}`);
    expect(screen.getByText("Confirmed")).toBeVisible();
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });

  it("loads Product before the exact active revision and never creates candidate state", async () => {
    let releaseProduct!: () => void;
    const productGate = new Promise<void>((resolve) => {
      releaseProduct = resolve;
    });
    getProductMock.mockImplementationOnce(async () => {
      await productGate;
      return ok(inactiveActiveOnlyProduct);
    });
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );

    renderPage();
    await waitFor(() => expect(getProductMock).toHaveBeenCalledTimes(1));
    expect(listRevisionMappingsMock).not.toHaveBeenCalled();

    releaseProduct();

    const reactivate = await screen.findByRole("button", {
      name: "Reactivate product",
    });
    await waitFor(() => expect(reactivate).toBeEnabled());
    expect(listRevisionMappingsMock).toHaveBeenCalledTimes(1);
    expect(listRevisionMappingsMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: {
        product_id: inactiveActiveOnlyProduct.id,
        revision_id: inactiveActiveOnlyProduct.active_revision!.id,
      },
      query: { cursor: null, limit: 50 },
    });
    expect(listCandidateMappingsMock).not.toHaveBeenCalled();
    expect(updateProductMock).not.toHaveBeenCalled();
    expect(createJobMock).not.toHaveBeenCalled();
    expect(publishMock).not.toHaveBeenCalled();
  });

  it.each([
    [
      "missing",
      { ...confirmedActiveMapping, selected_layout_candidate_id: null },
    ],
    ["stale", { ...confirmedActiveMapping, selected_layout_version: null }],
    [
      "failed",
      {
        ...confirmedActiveMapping,
        selected_layout_candidate_id: null,
        selected_layout_version: null,
      },
    ],
  ])(
    "keeps reactivation disabled for a %s active confirmation without sending a lifecycle request",
    async (_state, blockedMapping) => {
      getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
      listRevisionMappingsMock.mockResolvedValueOnce(
        ok({ items: [blockedMapping], next_cursor: null }),
      );

      renderPage();

      expect(
        await screen.findByText("Mapping 1: Preview confirmation required"),
      ).toBeVisible();
      expect(
        screen.getByRole("button", { name: "Reactivate product" }),
      ).toBeDisabled();
      expect(reactivateMock).not.toHaveBeenCalled();
      expect(updateProductMock).not.toHaveBeenCalled();
    },
  );

  it("sends only the exact active revision authority and renders the returned terminal state", async () => {
    const reactivatedProduct: AdminProductResponse = {
      ...inactiveActiveOnlyProduct,
      is_active: true,
    };
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    reactivateMock.mockResolvedValueOnce(ok(reactivatedProduct));

    renderPage();

    await userEvent.click(
      await screen.findByRole("button", { name: "Reactivate product" }),
    );
    const dialog = screen.getByRole("alertdialog", {
      name: "Reactivate Mobile Product?",
    });
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Reactivate product" }),
    );

    expect(reactivateMock).toHaveBeenCalledTimes(1);
    expect(reactivateMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        active_revision_id: inactiveActiveOnlyProduct.active_revision!.id,
        expected_active_version:
          inactiveActiveOnlyProduct.active_revision!.version,
      },
      path: { product_id: inactiveActiveOnlyProduct.id },
    });
    expect(await screen.findByText("Active")).toBeVisible();
    expect(toastSuccessMock).toHaveBeenCalledWith("Product reactivated");
    expect(listCandidateMappingsMock).not.toHaveBeenCalled();
    expect(updateProductMock).not.toHaveBeenCalled();
    expect(publishMock).not.toHaveBeenCalled();
  });

  it("deduplicates pending reactivation and retries a 409 against the unchanged active revision", async () => {
    let releaseConflict!: () => void;
    const conflictGate = new Promise<void>((resolve) => {
      releaseConflict = resolve;
    });
    const conflictResponse = failure<AdminProductLifecycleConflictResponse>(
      {
        blockers: ["preview_confirmation_required"],
        detail: "Product publication blocked",
      },
      409,
    );
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    reactivateMock
      .mockImplementationOnce(async () => {
        await conflictGate;
        return conflictResponse;
      })
      .mockResolvedValueOnce(
        ok({ ...inactiveActiveOnlyProduct, is_active: true }),
      );

    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: "Reactivate product" }),
    );
    const confirm = within(screen.getByRole("alertdialog")).getByRole(
      "button",
      { name: "Reactivate product" },
    );
    await userEvent.click(confirm);
    await userEvent.click(confirm);
    expect(reactivateMock).toHaveBeenCalledTimes(1);

    releaseConflict();
    expect(
      await screen.findByRole("alert", { name: "Publication blocked" }),
    ).toHaveTextContent("Preview confirmation required");
    expect(screen.getByText("Inactive")).toBeVisible();

    await userEvent.click(
      screen.getByRole("button", { name: "Reactivate product" }),
    );
    await userEvent.click(
      within(screen.getByRole("alertdialog")).getByRole("button", {
        name: "Reactivate product",
      }),
    );

    expect(reactivateMock).toHaveBeenCalledTimes(2);
    expect(reactivateMock.mock.calls[0]).toEqual(reactivateMock.mock.calls[1]);
    expect(await screen.findByText("Active")).toBeVisible();
    expect(listCandidateMappingsMock).not.toHaveBeenCalled();
    expect(updateProductMock).not.toHaveBeenCalled();
  });

  it("ignores superseded lifecycle results and bounds current transport failures", async () => {
    const successorProduct = {
      ...inactiveActiveOnlyProduct,
      id: "00000000-0000-4000-8000-000000000199",
    };
    let resolveObsolete!: (
      value: ReturnType<typeof ok<AdminProductResponse>>,
    ) => void;
    getProductMock
      .mockResolvedValueOnce(ok(inactiveActiveOnlyProduct))
      .mockResolvedValueOnce(ok(successorProduct));
    listRevisionMappingsMock.mockResolvedValue(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    reactivateMock
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveObsolete = resolve;
        }) as never,
      )
      .mockRejectedValueOnce(new Error("bounded lifecycle failure"));
    const view = renderPage(inactiveActiveOnlyProduct.id);
    const first = await screen.findByRole("button", {
      name: "Reactivate product",
    });
    await waitFor(() => expect(first).toBeEnabled());
    await userEvent.click(first);
    await userEvent.click(
      within(screen.getByRole("alertdialog")).getByRole("button", {
        name: "Reactivate product",
      }),
    );

    view.rerender(
      <MemoryRouter>
        <ProductPreviewPage
          accessToken="successor-admin-bearer"
          productId={successorProduct.id}
        />
      </MemoryRouter>,
    );
    await waitFor(() => expect(getProductMock).toHaveBeenCalledTimes(2));
    resolveObsolete(ok({ ...inactiveActiveOnlyProduct, is_active: true }));
    await waitFor(() => expect(screen.getByText("Inactive")).toBeVisible());

    view.unmount();
    getProductMock.mockResolvedValueOnce(ok(successorProduct));
    renderPage(successorProduct.id);
    const successor = await screen.findByRole("button", {
      name: "Reactivate product",
    });
    await waitFor(() => expect(successor).toBeEnabled());

    await userEvent.click(successor);
    await userEvent.click(
      within(screen.getByRole("alertdialog")).getByRole("button", {
        name: "Reactivate product",
      }),
    );
    expect(
      await screen.findByText("Publication did not complete"),
    ).toBeVisible();
    expect(screen.getByText("Inactive")).toBeVisible();
  });

  it("ignores a rejected lifecycle request after product authority changes", async () => {
    let rejectObsolete!: (reason: Error) => void;
    getProductMock
      .mockResolvedValueOnce(ok(inactiveActiveOnlyProduct))
      .mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValue(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    reactivateMock.mockReturnValueOnce(
      new Promise((_resolve, reject) => {
        rejectObsolete = reject;
      }) as never,
    );
    const view = renderPage(inactiveActiveOnlyProduct.id);
    const reactivate = await screen.findByRole("button", {
      name: "Reactivate product",
    });
    await waitFor(() => expect(reactivate).toBeEnabled());
    await userEvent.click(reactivate);
    await userEvent.click(
      within(screen.getByRole("alertdialog")).getByRole("button", {
        name: "Reactivate product",
      }),
    );
    view.rerender(
      <MemoryRouter>
        <ProductPreviewPage
          accessToken="successor-lifecycle-authority"
          productId={inactiveActiveOnlyProduct.id}
        />
      </MemoryRouter>,
    );
    await waitFor(() => expect(getProductMock).toHaveBeenCalledTimes(2));
    rejectObsolete(new Error("stale lifecycle failure"));
    await act(async () => Promise.resolve());
    expect(
      screen.queryByText("Publication did not complete"),
    ).not.toBeInTheDocument();
  });
});
