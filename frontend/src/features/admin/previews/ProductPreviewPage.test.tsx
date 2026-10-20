import "@testing-library/jest-dom/vitest";

import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { StrictMode } from "react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  confirmAdminActiveRevisionRevalidation,
  confirmAdminPreviewJob,
  createAdminActiveRevisionRevalidationJob,
  createAdminPreviewJob,
  getAdminRepositoryBranch,
  getAdminRepository,
  getAdminActiveRevisionRevalidationJob,
  getAdminLatestActiveRevisionRevalidationJob,
  getAdminLatestCandidatePreviewJob,
  getAdminPreviewJob,
  getAdminProduct,
  getAdminProductReactivationEligibility,
  listAdminCandidateMappings,
  listAdminRevisionMappings,
  listAdminRepositoryBranches,
  publishAdminProductCandidate,
  reactivateAdminProduct,
  updateAdminProductCandidate,
  type AdminActiveRevisionRevalidationJobResponse,
  type AdminMappingResponse,
  type AdminPreviewConfirmationResponse,
  type AdminPreviewJobResponse,
  type AdminPreviewLayoutCandidateResponse,
  type AdminProductLifecycleConflictResponse,
  type AdminProductReactivationEligibilityResponse,
  type AdminProductResponse,
} from "../../../api/client";
import { ProductPreviewPage } from "./ProductPreviewPage";

vi.mock("../imports/PublishedMappingImports", () => ({
  PublishedMappingImports: ({ autoStart }: { autoStart?: boolean }) => (
    <div data-testid="import-progress" data-auto-start={autoStart}>
      Import progress
    </div>
  ),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();
  return {
    ...original,
    confirmAdminActiveRevisionRevalidation: vi.fn(),
    confirmAdminPreviewJob: vi.fn(),
    createAdminActiveRevisionRevalidationJob: vi.fn(),
    createAdminPreviewJob: vi.fn(),
    getAdminRepositoryBranch: vi.fn(),
    getAdminRepository: vi.fn(),
    getAdminActiveRevisionRevalidationJob: vi.fn(),
    getAdminLatestActiveRevisionRevalidationJob: vi.fn(),
    getAdminLatestCandidatePreviewJob: vi.fn(),
    getAdminPreviewJob: vi.fn(),
    getAdminProduct: vi.fn(),
    getAdminProductReactivationEligibility: vi.fn(),
    listAdminCandidateMappings: vi.fn(),
    listAdminRevisionMappings: vi.fn(),
    listAdminRepositoryBranches: vi.fn(),
    publishAdminProductCandidate: vi.fn(),
    reactivateAdminProduct: vi.fn(),
    updateAdminProductCandidate: vi.fn(),
  };
});

const confirmActiveRevalidationMock = vi.mocked(
  confirmAdminActiveRevisionRevalidation,
);
const confirmMock = vi.mocked(confirmAdminPreviewJob);
const createActiveRevalidationMock = vi.mocked(
  createAdminActiveRevisionRevalidationJob,
);
const createJobMock = vi.mocked(createAdminPreviewJob);
const getBranchMock = vi.mocked(getAdminRepositoryBranch);
const getActiveRevalidationMock = vi.mocked(
  getAdminActiveRevisionRevalidationJob,
);
const getLatestActiveRevalidationMock = vi.mocked(
  getAdminLatestActiveRevisionRevalidationJob,
);
const getLatestCandidatePreviewMock = vi.mocked(
  getAdminLatestCandidatePreviewJob,
);
const getJobMock = vi.mocked(getAdminPreviewJob);
const getProductMock = vi.mocked(getAdminProduct);
const getReactivationEligibilityMock = vi.mocked(
  getAdminProductReactivationEligibility,
);
const listCandidateMappingsMock = vi.mocked(listAdminCandidateMappings);
const listRevisionMappingsMock = vi.mocked(listAdminRevisionMappings);
const listBranchesMock = vi.mocked(listAdminRepositoryBranches);
const publishMock = vi.mocked(publishAdminProductCandidate);
const reactivateMock = vi.mocked(reactivateAdminProduct);
const updateProductMock = vi.mocked(updateAdminProductCandidate);
const toastSuccessMock = vi.mocked(toast.success);

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

const product: AdminProductResponse = {
  active_revision: null,
  affected_mapping_count: 0,
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

function reactivationEligibility(
  isCurrent: boolean,
): AdminProductReactivationEligibilityResponse {
  return {
    active_revision_id: inactiveActiveOnlyProduct.active_revision!.id,
    active_revision_version: inactiveActiveOnlyProduct.active_revision!.version,
    blocker_codes: isCurrent ? [] : ["revalidation_confirmation_required"],
    eligible: isCurrent,
    mappings: [
      {
        blocker_codes: isCurrent ? [] : ["revalidation_confirmation_required"],
        is_current: isCurrent,
        mapping_id: confirmedActiveMapping.id,
      },
    ],
    product_id: inactiveActiveOnlyProduct.id,
  };
}

const formats = [
  ["android_xml", "Android XML", "app/src/main/res"],
  ["qt_ts", "Qt TS", "translations/{locale}.ts"],
  ["json", "JSON", "locales/{locale}.json"],
  ["ios_strings", "iOS strings", "App/{locale}.lproj/Localizable.strings"],
  ["xliff", "XLIFF", "translations/{locale}/messages.xliff"],
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

function activeRevalidationJob(
  overrides: Partial<AdminActiveRevisionRevalidationJobResponse> = {},
): AdminActiveRevisionRevalidationJobResponse {
  return {
    active_revision_id: inactiveActiveOnlyProduct.active_revision!.id,
    active_revision_version: inactiveActiveOnlyProduct.active_revision!.version,
    attempt: 1,
    connection_generation: 8,
    created_at: new Date().toISOString(),
    detector_version: "detector-v1",
    diagnostic_code: null,
    error_code: null,
    finished_at: "2026-08-31T17:00:05Z",
    id: "00000000-0000-4000-8000-000000000701",
    input_digest: "e".repeat(64),
    is_current: true,
    mapping_id: confirmedActiveMapping.id,
    product_id: inactiveActiveOnlyProduct.id,
    repository_sides: [
      {
        commit_hash: "b".repeat(40),
        repository_id: confirmedActiveMapping.primary_repository_id,
        role: "direct",
        source_branch: confirmedActiveMapping.primary_source_branch,
      },
    ],
    result: {
      detector_version: "detector-v1",
      digest: "f".repeat(64),
      layout_candidates: [candidates[0]],
    },
    started_at: "2026-08-31T17:00:01Z",
    state: "succeeded",
    ...overrides,
  };
}

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
    diagnostic_code: null,
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

function previewConfirmation(
  selectedCandidate: AdminPreviewLayoutCandidateResponse,
  baseLanguage: string,
): AdminPreviewConfirmationResponse {
  return {
    base_language: baseLanguage,
    confirmed_at: "2026-09-05T10:00:00Z",
    confirmed_by: "00000000-0000-4000-8000-000000000001",
    job_id: previewJob().id,
    layout_candidate_id: selectedCandidate.id,
    layout_candidate_version: selectedCandidate.version,
    mapping_id: mapping.id,
    // Confirmation binds the selected language; it is not the preview request digest.
    preview_digest: "d".repeat(64),
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
    primary_source_branch: `branch-${index}`,
    ...overrides,
  };
}

async function runValidation() {
  await waitFor(() => expect(getLatestCandidatePreviewMock).toHaveBeenCalled());
  return screen.findByText("Succeeded");
}

async function selectBaseLanguage(language = "en") {
  await userEvent.click(
    screen.getByRole("combobox", { name: "Base language" }),
  );
  await userEvent.click(screen.getByRole("option", { name: language }));
}

describe("administrator product preview and publication page", () => {
  it("shows published configuration and next actions when an active product has no draft", async () => {
    getProductMock.mockResolvedValue(
      ok({
        ...product,
        is_active: true,
        active_revision: { ...product.candidate_revision!, is_published: true },
        candidate_revision: null,
      }),
    );
    renderPage();
    expect(
      await screen.findByText("Import progress", { exact: true }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open product strings" }),
    ).toHaveAttribute("href", `/products/${product.id}/strings`);
    expect(screen.getByTestId("import-progress")).toHaveAttribute(
      "data-auto-start",
      "true",
    );
    expect(
      screen.queryByText("Product preview unavailable"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Run validation" }),
    ).not.toBeInTheDocument();
    expect(getLatestCandidatePreviewMock).not.toHaveBeenCalled();
    expect(createJobMock).not.toHaveBeenCalled();
    expect(publishMock).not.toHaveBeenCalled();
  });

  it("reports a rejected current preview confirmation without granting publication authority", async () => {
    confirmMock.mockRejectedValueOnce(new Error("private transport failure"));
    renderPage();
    await runValidation();

    await userEvent.click(
      screen.getByRole("combobox", { name: "Base language" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "en" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );
    expect(await screen.findByText("Preview not confirmed")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Import strings" }),
    ).toBeDisabled();
    expect(document.body).not.toHaveTextContent("private transport failure");
  });
  it("ignores an active confirmation response after the recovery page unmounts", async () => {
    let resolveConfirmation!: (
      value: ReturnType<typeof failure<{ detail: string }>>,
    ) => void;
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock.mockResolvedValueOnce(
      ok(reactivationEligibility(false)),
    );
    createActiveRevalidationMock.mockResolvedValue(
      ok(activeRevalidationJob(), 202),
    );
    confirmActiveRevalidationMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveConfirmation = resolve;
      }) as never,
    );
    const view = renderPage(inactiveActiveOnlyProduct.id);
    await userEvent.click(
      await screen.findByRole("button", { name: "Run validation again" }),
    );

    await selectBaseLanguage();
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );
    await waitFor(() =>
      expect(confirmActiveRevalidationMock).toHaveBeenCalledOnce(),
    );
    const eligibilityCalls = getReactivationEligibilityMock.mock.calls.length;
    view.unmount();
    await act(async () =>
      resolveConfirmation(failure({ detail: "private stale response" })),
    );
    expect(getReactivationEligibilityMock).toHaveBeenCalledTimes(
      eligibilityCalls,
    );
    expect(reactivateMock).not.toHaveBeenCalled();
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.mocked(getAdminRepository).mockReset();
    vi.mocked(getAdminRepository).mockImplementation(async (options) =>
      ok({
        id: options.path.repository_id,
        descriptive_name: "Mobile app",
        repository_slug: "mobile-app",
        workspace: "team",
      }),
    );
    confirmActiveRevalidationMock.mockReset();
    confirmMock.mockReset();
    createActiveRevalidationMock.mockReset();
    createJobMock.mockReset();
    createJobMock.mockResolvedValue(ok(previewJob(), 202));
    getBranchMock.mockReset();
    getBranchMock.mockResolvedValue(
      ok({ commit_hash: "b".repeat(40), name: "main" }),
    );
    getActiveRevalidationMock.mockReset();
    getLatestActiveRevalidationMock.mockReset();
    getLatestActiveRevalidationMock.mockResolvedValue(
      failure({ detail: "Active revision revalidation unavailable" }, 404),
    );
    getLatestCandidatePreviewMock.mockReset();
    getLatestCandidatePreviewMock.mockResolvedValue(
      failure({ detail: "Preview unavailable" }, 404),
    );
    getJobMock.mockReset();
    getProductMock.mockReset();
    getProductMock.mockResolvedValue(ok(product));
    getReactivationEligibilityMock.mockReset();
    getReactivationEligibilityMock.mockImplementation(async (options) =>
      ok({
        ...reactivationEligibility(true),
        active_revision_id: options.path.revision_id,
        active_revision_version: options.query.expected_active_revision_version,
        product_id: options.path.product_id,
      }),
    );
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

  it("waits for a reliable status read before automatically starting a missing preview", async () => {
    getLatestCandidatePreviewMock.mockRejectedValueOnce(
      new Error("private offline error"),
    );
    renderPage();
    expect(await screen.findByText("Preview status unavailable")).toBeVisible();
    expect(createJobMock).not.toHaveBeenCalled();
    expect(screen.queryByText("private offline error")).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Retry preview status" }),
    );
    expect(await screen.findByText("Succeeded")).toBeVisible();
    expect(createJobMock).toHaveBeenCalledOnce();
    expect(
      screen.getByRole("heading", { name: "Mobile app · main" }),
    ).toBeVisible();
    expect(screen.queryByText("Mapping 1")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("list", { name: "Preview and publication workflow" }),
    ).not.toBeInTheDocument();
  });

  it("refreshes an outdated restored analysis automatically", async () => {
    getLatestCandidatePreviewMock.mockResolvedValueOnce(
      ok(previewJob({ is_current: false })),
    );
    renderPage();
    expect(await screen.findByText("Succeeded")).toBeVisible();
    expect(createJobMock).toHaveBeenCalledOnce();
  });

  it("keeps a failed restored preview available for explicit retry", async () => {
    getLatestCandidatePreviewMock.mockResolvedValueOnce(
      ok(previewJob({ state: "failed", result: null })),
    );
    renderPage();
    expect(
      await screen.findByRole("button", { name: "Retry validation" }),
    ).toBeVisible();
    expect(createJobMock).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Retry validation" }),
    );
    expect(await screen.findByText("Succeeded")).toBeVisible();
    expect(createJobMock).toHaveBeenCalledOnce();
  });

  it("does not enqueue a preview after leaving while branch resolution is pending", async () => {
    let resolveBranch!: (
      value: ReturnType<typeof ok<{ name: string; commit_hash: string }>>,
    ) => void;
    getBranchMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveBranch = resolve;
      }) as never,
    );
    const view = renderPage();
    await waitFor(() => expect(getBranchMock).toHaveBeenCalledOnce());
    view.unmount();
    await act(async () =>
      resolveBranch(ok({ name: "main", commit_hash: "b".repeat(40) })),
    );
    expect(createJobMock).not.toHaveBeenCalled();
  });

  it("restores the latest candidate validation after remount", async () => {
    const createdAt = new Date().toISOString();
    const queuedJob = previewJob({
      created_at: createdAt,
      finished_at: null,
      result: null,
      started_at: null,
      state: "queued",
    });
    createJobMock.mockResolvedValueOnce(ok(queuedJob, 202));
    const firstVisit = renderPage();
    await waitFor(() =>
      expect(getLatestCandidatePreviewMock).toHaveBeenCalled(),
    );
    expect(
      await screen.findByText("Queued", {
        exact: true,
        selector: "[data-slot='badge']",
      }),
    ).toBeVisible();
    firstVisit.unmount();

    getLatestCandidatePreviewMock.mockResolvedValueOnce(
      ok(previewJob({ created_at: createdAt, id: queuedJob.id })),
    );
    renderPage();

    expect(
      await screen.findByText("Succeeded", {
        exact: true,
        selector: "[data-slot='badge']",
      }),
    ).toBeVisible();
    expect(getLatestCandidatePreviewMock).toHaveBeenLastCalledWith({
      auth: "memory-only-admin-bearer",
      path: { mapping_id: mapping.id, product_id: product.id },
    });
    expect(createJobMock).toHaveBeenCalledOnce();
  });

  it("rediscovers a candidate validation when browser storage is empty", async () => {
    const recoveredJob = previewJob();
    getLatestCandidatePreviewMock.mockResolvedValueOnce(ok(recoveredJob));

    renderPage();

    expect(
      await screen.findByText("Succeeded", {
        exact: true,
        selector: "[data-slot='badge']",
      }),
    ).toBeVisible();
    expect(getLatestCandidatePreviewMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { mapping_id: mapping.id, product_id: product.id },
    });
    expect(getJobMock).not.toHaveBeenCalled();
  });

  it("restores an active-revision validation after remount", async () => {
    const createdAt = new Date().toISOString();
    const queuedJob = activeRevalidationJob({
      created_at: createdAt,
      finished_at: null,
      result: null,
      started_at: null,
      state: "queued",
    });
    getProductMock.mockResolvedValue(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValue(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock.mockResolvedValue(
      ok(reactivationEligibility(false)),
    );
    createActiveRevalidationMock.mockResolvedValueOnce(ok(queuedJob, 202));
    const firstVisit = renderPage(inactiveActiveOnlyProduct.id);
    await userEvent.click(
      await screen.findByRole("button", { name: "Run validation again" }),
    );
    expect(
      await screen.findByText("Queued", {
        exact: true,
        selector: "[data-slot='badge']",
      }),
    ).toBeVisible();
    firstVisit.unmount();

    getLatestActiveRevalidationMock.mockResolvedValueOnce(
      ok(activeRevalidationJob({ created_at: createdAt, id: queuedJob.id })),
    );
    renderPage(inactiveActiveOnlyProduct.id);

    expect(
      await screen.findByText("Succeeded", {
        exact: true,
        selector: "[data-slot='badge']",
      }),
    ).toBeVisible();
    expect(getLatestActiveRevalidationMock).toHaveBeenLastCalledWith({
      auth: "memory-only-admin-bearer",
      path: {
        mapping_id: confirmedActiveMapping.id,
        product_id: inactiveActiveOnlyProduct.id,
        revision_id: inactiveActiveOnlyProduct.active_revision!.id,
      },
    });
    expect(createActiveRevalidationMock).toHaveBeenCalledOnce();
  });

  it("rediscovers an active validation when browser storage is empty", async () => {
    const recoveredJob = activeRevalidationJob();
    getProductMock.mockResolvedValue(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValue(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock.mockResolvedValue(
      ok(reactivationEligibility(false)),
    );
    getLatestActiveRevalidationMock.mockResolvedValueOnce(ok(recoveredJob));

    renderPage(inactiveActiveOnlyProduct.id);

    expect(
      await screen.findByText("Succeeded", {
        exact: true,
        selector: "[data-slot='badge']",
      }),
    ).toBeVisible();
    expect(getLatestActiveRevalidationMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: {
        mapping_id: confirmedActiveMapping.id,
        product_id: inactiveActiveOnlyProduct.id,
        revision_id: inactiveActiveOnlyProduct.active_revision!.id,
      },
    });
    expect(getActiveRevalidationMock).not.toHaveBeenCalled();
  });

  it("recovers a candidate validation accepted after the page was left", async () => {
    const createdAt = new Date().toISOString();
    const queuedJob = previewJob({
      created_at: createdAt,
      finished_at: null,
      result: null,
      started_at: null,
      state: "queued",
    });
    let acceptValidation!: (
      value: ReturnType<typeof ok<AdminPreviewJobResponse>>,
    ) => void;
    createJobMock.mockReturnValueOnce(
      new Promise((resolve) => {
        acceptValidation = resolve;
      }) as never,
    );

    const firstVisit = renderPage();
    await waitFor(() =>
      expect(getLatestCandidatePreviewMock).toHaveBeenCalled(),
    );
    await waitFor(() => expect(createJobMock).toHaveBeenCalledOnce());
    firstVisit.unmount();
    await act(async () => acceptValidation(ok(queuedJob, 202)));

    getLatestCandidatePreviewMock.mockResolvedValueOnce(
      ok(previewJob({ id: queuedJob.id })),
    );
    renderPage();

    expect(
      await screen.findByText("Succeeded", {
        exact: true,
        selector: "[data-slot='badge']",
      }),
    ).toBeVisible();
  });

  it("recovers an active validation accepted after the page was left", async () => {
    const createdAt = new Date().toISOString();
    const queuedJob = activeRevalidationJob({
      created_at: createdAt,
      finished_at: null,
      result: null,
      started_at: null,
      state: "queued",
    });
    let acceptValidation!: (
      value: ReturnType<typeof ok<AdminActiveRevisionRevalidationJobResponse>>,
    ) => void;
    getProductMock.mockResolvedValue(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValue(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock.mockResolvedValue(
      ok(reactivationEligibility(false)),
    );
    createActiveRevalidationMock.mockReturnValueOnce(
      new Promise((resolve) => {
        acceptValidation = resolve;
      }) as never,
    );

    const firstVisit = renderPage(inactiveActiveOnlyProduct.id);
    await userEvent.click(
      await screen.findByRole("button", { name: "Run validation again" }),
    );
    await waitFor(() =>
      expect(createActiveRevalidationMock).toHaveBeenCalledOnce(),
    );
    firstVisit.unmount();
    await act(async () => acceptValidation(ok(queuedJob, 202)));

    getLatestActiveRevalidationMock.mockResolvedValueOnce(
      ok(activeRevalidationJob({ id: queuedJob.id })),
    );
    renderPage(inactiveActiveOnlyProduct.id);

    expect(
      await screen.findByText("Succeeded", {
        exact: true,
        selector: "[data-slot='badge']",
      }),
    ).toBeVisible();
  });

  it.each([
    [
      "repository scan limit",
      "repository_scan_limit_reached" as const,
      "The repository scan limit was reached. Set a narrower localization root in the mapping, then retry validation.",
    ],
    [
      "unknown worker failure",
      null,
      "Validation did not complete. Review the reason, then retry.",
    ],
  ])(
    "renders safe recovery guidance for a %s",
    async (_name, diagnosticCode, copy) => {
      createJobMock.mockResolvedValueOnce(
        ok(
          previewJob({
            diagnostic_code: diagnosticCode,
            error_code: "processing_failed",
            finished_at: "2026-09-06T12:00:00Z",
            result: null,
            state: "failed",
          }),
          202,
        ),
      );
      renderPage();
      await waitFor(() =>
        expect(getLatestCandidatePreviewMock).toHaveBeenCalled(),
      );
      expect(await screen.findByText("Failed", { exact: true })).toBeVisible();

      expect(screen.getByRole("alert")).toHaveTextContent(copy);
      expect(
        screen.getByRole("button", { name: "Retry validation" }),
      ).toBeVisible();
    },
  );

  it("offers duplicate diagnostics only when the worker stored an actionable summary", async () => {
    renderPage();
    await runValidation();
    expect(
      screen.queryByRole("button", { name: "View duplicate keys" }),
    ).not.toBeInTheDocument();

    cleanup();
    createJobMock.mockResolvedValueOnce(
      ok(
        previewJob({
          duplicate_report_summary: {
            complete: true,
            group_count: 2,
            repeated_occurrences: 2,
          },
          result: {
            detector_version: "detector-v1",
            digest: "c".repeat(64),
            layout_candidates: [candidates[0]],
          },
        }),
        202,
      ),
    );
    renderPage();
    await runValidation();
    expect(
      screen.getByRole("button", { name: "View duplicate keys" }),
    ).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Duplicate keys detected",
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "2 duplicate groups and 2 repeated occurrences",
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Unique strings remain available",
    );
    expect(screen.queryByText("No supported layout")).not.toBeInTheDocument();
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
    expect(alert).toHaveTextContent("Product preview unavailable");
    expect(alert).not.toHaveTextContent("private-diagnostic");

    cleanup();
    getProductMock.mockResolvedValueOnce(ok(product));
    renderPage();
    expect(await screen.findByText("Succeeded")).toBeVisible();
    expect(createJobMock).toHaveBeenCalledOnce();
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
    expect(await screen.findByText("Succeeded")).toBeVisible();
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
    expect(await screen.findByText("Succeeded")).toBeVisible();
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
    render(
      <StrictMode>
        <MemoryRouter>
          <ProductPreviewPage
            accessToken="memory-only-admin-bearer"
            productId={product.id}
          />
        </MemoryRouter>
      </StrictMode>,
    );
    expect(await screen.findByText("Reading files and strings…")).toBeVisible();
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
            name: `Mobile app · branch-${mappingCount}`,
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
    getBranchMock.mockImplementation(async (options) =>
      ok({ commit_hash: "b".repeat(40), name: options.query.branch_name }),
    );
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
    expect(
      screen.getByRole("button", { name: "Import strings" }),
    ).toBeDisabled();
    expect(createJobMock).not.toHaveBeenCalled();
    expect(publishMock).not.toHaveBeenCalled();

    await userEvent.click(
      within(incomplete).getByRole("button", {
        name: "Retry loading mappings",
      }),
    );

    expect(
      await screen.findByRole("heading", { name: "Mobile app · branch-51" }),
    ).toBeVisible();
    await waitFor(() => expect(createJobMock).toHaveBeenCalledTimes(51));
    expect(listRevisionMappingsMock).toHaveBeenCalledTimes(3);
    expect(
      listRevisionMappingsMock.mock.calls.map(
        ([options]) => options.query?.cursor ?? null,
      ),
    ).toEqual([null, "page-2", "page-2"]);
    expect(createJobMock).toHaveBeenCalledTimes(51);
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
    getReactivationEligibilityMock.mockResolvedValueOnce(
      ok(reactivationEligibility(false)),
    );
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
      await screen.findByText(
        "Choose a base language and confirm the sources above to continue.",
      ),
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
      screen.queryByRole("heading", { name: "Mobile app · branch-51" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Mobile app · branch-2" }),
    ).toBeVisible();
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
    createJobMock
      .mockResolvedValueOnce(ok(queuedJob, 202))
      .mockResolvedValueOnce(
        failure({ detail: "provider_unavailable" }, 503) as never,
      );
    getJobMock.mockImplementationOnce(async () => {
      await stalePollGate;
      return ok(previewJob());
    });

    const view = renderPage(product.id);
    await waitFor(() =>
      expect(getLatestCandidatePreviewMock).toHaveBeenCalled(),
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

  it("resolves exact commits and shows every file and language without layout choices or samples", async () => {
    renderPage();
    await runValidation();

    expect(getBranchMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { repository_id: mapping.primary_repository_id },
      query: { branch_name: mapping.primary_source_branch },
    });
    expect(listBranchesMock).not.toHaveBeenCalled();
    expect(createJobMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        commits: [{ commit_hash: "b".repeat(40), role: "direct" }],
        expected_candidate_version: 5,
      },
      path: { mapping_id: mapping.id, product_id: product.id },
    });
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    const details = screen.getByRole("region", {
      name: "Files, languages and source details",
    });
    expect(details).toBeVisible();
    expect(details).toHaveTextContent("5 files · 2 languages");
    for (const item of candidates)
      expect(within(details).getByText(item.files[0])).toBeVisible();
    expect(details).toHaveTextContent("Translation files · main");
    expect(details).toHaveTextContent("bbbbbbbbbbbb");
    expect(
      within(details).getByRole("list", { name: "Languages to import" }),
    ).toHaveTextContent("enit");
    expect(screen.queryByText("Translation samples")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("Benvenuto")).not.toBeInTheDocument();
  });

  it("resolves branch 101 through exact detail for a candidate direct source", async () => {
    const branch = "Release/101%2F?query#fragment Ω ";
    const commit = "1".repeat(40);
    const branch101Mapping = {
      ...mapping,
      primary_source_branch: branch,
    };
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [branch101Mapping], next_cursor: null }),
    );
    listBranchesMock.mockResolvedValueOnce(
      ok({
        items: Array.from({ length: 100 }, (_, index) => ({
          commit_hash: String(index + 1).padStart(40, "0"),
          name: `unrelated-${index + 1}`,
        })),
        next_cursor: "page-2",
      }),
    );
    getBranchMock.mockResolvedValueOnce(
      ok({ commit_hash: commit, name: branch }),
    );

    renderPage();
    await waitFor(() =>
      expect(getLatestCandidatePreviewMock).toHaveBeenCalled(),
    );

    await waitFor(() =>
      expect(getBranchMock).toHaveBeenCalledWith({
        auth: "memory-only-admin-bearer",
        path: { repository_id: branch101Mapping.primary_repository_id },
        query: { branch_name: branch },
      }),
    );
    expect(listBranchesMock).not.toHaveBeenCalled();
    expect(createJobMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        commits: [{ commit_hash: commit, role: "direct" }],
        expected_candidate_version: branch101Mapping.candidate_version,
      },
      path: { mapping_id: branch101Mapping.id, product_id: product.id },
    });
  });

  it("resolves branch 101 through exact detail for candidate keys and translations sources", async () => {
    const keysBranch = "keys/101%2F?# Ω";
    const translationsBranch = "translations/102%2F?# Ω";
    const keysCommit = "2".repeat(40);
    const translationsCommit = "3".repeat(40);
    const separate = {
      ...mapping,
      primary_source_branch: keysBranch,
      topology: "separate" as const,
      translations_repository_id: "00000000-0000-4000-8000-000000000402",
      translations_source_branch: translationsBranch,
    };
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [separate], next_cursor: null }),
    );
    listBranchesMock.mockResolvedValue(
      ok({
        items: Array.from({ length: 100 }, (_, index) => ({
          commit_hash: String(index + 1).padStart(40, "0"),
          name: `unrelated-${index + 1}`,
        })),
        next_cursor: "page-2",
      }),
    );
    getBranchMock.mockImplementation(async (options) =>
      ok(
        options.path.repository_id === separate.primary_repository_id
          ? { commit_hash: keysCommit, name: keysBranch }
          : { commit_hash: translationsCommit, name: translationsBranch },
      ),
    );

    renderPage();
    await waitFor(() =>
      expect(getLatestCandidatePreviewMock).toHaveBeenCalled(),
    );

    await waitFor(() => expect(getBranchMock).toHaveBeenCalledTimes(2));
    expect(getBranchMock.mock.calls.map(([options]) => options)).toEqual([
      {
        auth: "memory-only-admin-bearer",
        path: { repository_id: separate.primary_repository_id },
        query: { branch_name: keysBranch },
      },
      {
        auth: "memory-only-admin-bearer",
        path: { repository_id: separate.translations_repository_id },
        query: { branch_name: translationsBranch },
      },
    ]);
    expect(listBranchesMock).not.toHaveBeenCalled();
    expect(createJobMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        commits: [
          { commit_hash: keysCommit, role: "keys" },
          { commit_hash: translationsCommit, role: "translations" },
        ],
        expected_candidate_version: separate.candidate_version,
      },
      path: { mapping_id: separate.id, product_id: product.id },
    });
  });

  it.each([
    [
      "direct",
      {
        ...confirmedActiveMapping,
        primary_source_branch: "active/101%2F?# Ω",
      },
    ],
    [
      "separate",
      {
        ...confirmedActiveMapping,
        primary_source_branch: "keys/101%2F?# Ω",
        topology: "separate" as const,
        translations_repository_id: "00000000-0000-4000-8000-000000000402",
        translations_source_branch: "translations/102%2F?# Ω",
      },
    ],
  ])(
    "resolves branch 101 through exact detail for active %s sources",
    async (_topology, activeMapping) => {
      const expectedSides =
        activeMapping.topology === "direct"
          ? [
              {
                branch: activeMapping.primary_source_branch,
                commit: "4".repeat(40),
                repositoryId: activeMapping.primary_repository_id,
                role: "direct" as const,
              },
            ]
          : [
              {
                branch: activeMapping.primary_source_branch,
                commit: "4".repeat(40),
                repositoryId: activeMapping.primary_repository_id,
                role: "keys" as const,
              },
              {
                branch: activeMapping.translations_source_branch!,
                commit: "5".repeat(40),
                repositoryId: activeMapping.translations_repository_id!,
                role: "translations" as const,
              },
            ];
      getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
      listRevisionMappingsMock.mockResolvedValueOnce(
        ok({ items: [activeMapping], next_cursor: null }),
      );
      getReactivationEligibilityMock.mockResolvedValueOnce(
        ok(reactivationEligibility(false)),
      );
      listBranchesMock.mockResolvedValue(
        ok({
          items: Array.from({ length: 100 }, (_, index) => ({
            commit_hash: String(index + 1).padStart(40, "0"),
            name: `unrelated-${index + 1}`,
          })),
          next_cursor: "page-2",
        }),
      );
      getBranchMock.mockImplementation(async (options) => {
        const side = expectedSides.find(
          (candidateSide) =>
            candidateSide.repositoryId === options.path.repository_id,
        )!;
        return ok({ commit_hash: side.commit, name: side.branch });
      });
      createActiveRevalidationMock.mockResolvedValueOnce(
        ok(activeRevalidationJob(), 202),
      );

      renderPage(inactiveActiveOnlyProduct.id);
      await userEvent.click(
        await screen.findByRole("button", { name: "Run validation again" }),
      );

      await waitFor(() =>
        expect(getBranchMock).toHaveBeenCalledTimes(expectedSides.length),
      );
      expect(getBranchMock.mock.calls.map(([options]) => options)).toEqual(
        expectedSides.map((side) => ({
          auth: "memory-only-admin-bearer",
          path: { repository_id: side.repositoryId },
          query: { branch_name: side.branch },
        })),
      );
      expect(listBranchesMock).not.toHaveBeenCalled();
      expect(createActiveRevalidationMock).toHaveBeenCalledWith({
        auth: "memory-only-admin-bearer",
        body: {
          commits: expectedSides.map((side) => ({
            commit_hash: side.commit,
            role: side.role,
          })),
          expected_active_revision_version:
            inactiveActiveOnlyProduct.active_revision!.version,
        },
        path: {
          mapping_id: activeMapping.id,
          product_id: inactiveActiveOnlyProduct.id,
          revision_id: inactiveActiveOnlyProduct.active_revision!.id,
        },
      });
      expect(createJobMock).not.toHaveBeenCalled();
      expect(publishMock).not.toHaveBeenCalled();
      expect(reactivateMock).not.toHaveBeenCalled();
    },
  );

  it.each([
    ["case", "release/opaque"],
    ["surrounding character", "xRelease/Opaque"],
    ["Unicode", "Release/Opaque Ω"],
    ["percent", "Release/Opaque%2F"],
    ["slash", "Release/Opaque/"],
    ["question mark", "Release/Opaque?"],
    ["hash", "Release/Opaque#"],
  ])(
    "resolves branch 101 through exact detail and rejects a %s mismatch",
    async (_difference, returnedName) => {
      const requestedName = "Release/Opaque";
      const mismatchedMapping = {
        ...mapping,
        primary_source_branch: requestedName,
      };
      listRevisionMappingsMock.mockResolvedValueOnce(
        ok({ items: [mismatchedMapping], next_cursor: null }),
      );
      listBranchesMock.mockResolvedValueOnce(
        ok({
          items: [{ commit_hash: "6".repeat(40), name: requestedName }],
          next_cursor: null,
        }),
      );
      getBranchMock.mockResolvedValueOnce(
        ok({ commit_hash: "7".repeat(40), name: returnedName }),
      );

      renderPage();
      await waitFor(() =>
        expect(getLatestCandidatePreviewMock).toHaveBeenCalled(),
      );

      await waitFor(() => expect(getBranchMock).toHaveBeenCalledOnce());
      await waitFor(() =>
        expect(
          screen.getByText("The source could not be read. Try again."),
        ).toBeVisible(),
      );
      expect(createJobMock).not.toHaveBeenCalled();
      expect(createActiveRevalidationMock).not.toHaveBeenCalled();
      expect(publishMock).not.toHaveBeenCalled();
      expect(reactivateMock).not.toHaveBeenCalled();
    },
  );

  it.each(["rejected", "empty"])(
    "resolves branch 101 through exact detail and fails closed for a %s response",
    async (failureMode) => {
      const requestedName = "Release/opaque%2F?# Ω";
      const exactMapping = { ...mapping, primary_source_branch: requestedName };
      listRevisionMappingsMock.mockResolvedValueOnce(
        ok({ items: [exactMapping], next_cursor: null }),
      );
      listBranchesMock.mockResolvedValueOnce(
        ok({
          items: [{ commit_hash: "8".repeat(40), name: requestedName }],
          next_cursor: null,
        }),
      );
      if (failureMode === "rejected") {
        getBranchMock.mockRejectedValueOnce(
          new Error("bounded lookup failure"),
        );
      } else {
        getBranchMock.mockResolvedValueOnce(ok(undefined as never));
      }

      renderPage();
      await waitFor(() =>
        expect(getLatestCandidatePreviewMock).toHaveBeenCalled(),
      );

      await waitFor(() => expect(getBranchMock).toHaveBeenCalledOnce());
      expect(
        await screen.findByText("The source could not be read. Try again."),
      ).toBeVisible();
      expect(createJobMock).not.toHaveBeenCalled();
      expect(createActiveRevalidationMock).not.toHaveBeenCalled();
      expect(publishMock).not.toHaveBeenCalled();
      expect(reactivateMock).not.toHaveBeenCalled();
    },
  );

  it("resolves branch 101 through exact detail and fails closed when one separate side fails", async () => {
    const separate = {
      ...mapping,
      primary_source_branch: "keys/101",
      topology: "separate" as const,
      translations_repository_id: "00000000-0000-4000-8000-000000000402",
      translations_source_branch: "translations/102",
    };
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [separate], next_cursor: null }),
    );
    listBranchesMock.mockResolvedValue(
      ok({
        items: [
          { commit_hash: "9".repeat(40), name: separate.primary_source_branch },
          {
            commit_hash: "a".repeat(40),
            name: separate.translations_source_branch,
          },
        ],
        next_cursor: null,
      }),
    );
    getBranchMock
      .mockResolvedValueOnce(
        ok({
          commit_hash: "9".repeat(40),
          name: separate.primary_source_branch,
        }),
      )
      .mockRejectedValueOnce(new Error("bounded translations lookup failure"));

    renderPage();
    await waitFor(() =>
      expect(getLatestCandidatePreviewMock).toHaveBeenCalled(),
    );

    await waitFor(() => expect(getBranchMock).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByText("The source could not be read. Try again."),
    ).toBeVisible();
    expect(createJobMock).not.toHaveBeenCalled();
    expect(createActiveRevalidationMock).not.toHaveBeenCalled();
    expect(publishMock).not.toHaveBeenCalled();
    expect(reactivateMock).not.toHaveBeenCalled();
  });

  it("resolves branch 101 through exact detail and rejects missing separate-side identity", async () => {
    const incomplete = {
      ...mapping,
      topology: "separate" as const,
      translations_repository_id: null,
      translations_source_branch: null,
    };
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [incomplete], next_cursor: null }),
    );

    renderPage();
    await waitFor(() =>
      expect(getLatestCandidatePreviewMock).toHaveBeenCalled(),
    );

    expect(
      await screen.findByText("The source could not be read. Try again."),
    ).toBeVisible();
    expect(createJobMock).not.toHaveBeenCalled();
    expect(createActiveRevalidationMock).not.toHaveBeenCalled();
    expect(publishMock).not.toHaveBeenCalled();
    expect(reactivateMock).not.toHaveBeenCalled();
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

  it("visibly selects the sole detected base language and waits for backend confirmation", async () => {
    const soleLanguageCandidate = {
      ...candidates[0],
      languages: ["fr-FR"],
    };
    createJobMock.mockResolvedValueOnce(
      ok(
        previewJob({
          result: {
            detector_version: "detector-v1",
            digest: "c".repeat(64),
            layout_candidates: [soleLanguageCandidate],
          },
        }),
        202,
      ),
    );
    let resolveConfirmation!: (
      value: ReturnType<typeof ok<AdminPreviewConfirmationResponse>>,
    ) => void;
    confirmMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveConfirmation = resolve;
      }) as never,
    );

    renderPage();
    await runValidation();

    const baseLanguage = screen.getByRole("combobox", {
      name: "Base language",
    });
    expect(baseLanguage).toHaveTextContent("fr-FR");
    expect(baseLanguage).toHaveClass(
      "min-h-[44px]",
      "w-full",
      "min-w-0",
      "motion-reduce:transition-none",
    );
    expect(baseLanguage).toHaveAttribute("aria-invalid", "false");
    expect(
      screen.getByText(
        "Used as the reference language for translation limits. All other languages are imported too.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("textbox", { name: "Base language" }),
    ).not.toBeInTheDocument();
    const publish = screen.getByRole("button", { name: "Import strings" });
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );
    expect(publish).toBeDisabled();
    expect(confirmMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        base_language: "fr-FR",
        layout_candidate_id: soleLanguageCandidate.id,
        layout_candidate_version: 1,
        preview_digest: "c".repeat(64),
      },
      path: { job_id: previewJob().id },
    });

    resolveConfirmation(
      ok(previewConfirmation(soleLanguageCandidate, "fr-FR")),
    );
    expect(await screen.findByText("Confirmed")).toBeVisible();
    expect(publish).toBeEnabled();
  });

  it.each([{ languages: ["default"] }, { languages: ["default", "bg"] }])(
    "requires an explicit canonical language for default layout $languages",
    async ({ languages }) => {
      const candidate = { ...candidates[0], languages };
      createJobMock.mockResolvedValueOnce(
        ok(
          previewJob({
            result: {
              detector_version: "detector-v1",
              digest: "c".repeat(64),
              layout_candidates: [candidate],
            },
          }),
          202,
        ),
      );
      confirmMock.mockResolvedValueOnce(
        ok(previewConfirmation(candidate, "en")),
      );
      renderPage();
      await runValidation();
      const language = screen.getByRole("textbox", { name: "Base language" });
      const confirm = screen.getByRole("button", { name: "Confirm preview" });
      expect(language).toHaveValue("");
      expect(confirm).toBeDisabled();
      for (const invalid of ["default", "EN", "en-us", "english"]) {
        await userEvent.clear(language);
        await userEvent.type(language, invalid);
        expect(language).toHaveAttribute("aria-invalid", "true");
        expect(confirm).toBeDisabled();
      }
      expect(confirmMock).not.toHaveBeenCalled();
      await userEvent.clear(language);
      await userEvent.type(language, "en");
      expect(language).toHaveAttribute("aria-invalid", "false");
      await userEvent.click(confirm);
      expect(confirmMock).toHaveBeenCalledWith(
        expect.objectContaining({
          body: {
            base_language: "en",
            layout_candidate_id: candidate.id,
            layout_candidate_version: 1,
            preview_digest: "c".repeat(64),
          },
        }),
      );
      expect(await screen.findByText("Confirmed")).toBeVisible();
      await userEvent.clear(language);
      await userEvent.type(language, "it");
      expect(screen.queryByText("Confirmed")).not.toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Import strings" }),
      ).toBeDisabled();
    },
  );

  it("offers the union of detected languages and confirms the matching source without excluding other files", async () => {
    const allCandidates = candidates.slice(0, 3).map((item, index) => ({
      ...item,
      languages: [["en"], ["fr", "it"], ["it"]][index],
    }));
    createJobMock.mockResolvedValueOnce(
      ok(
        previewJob({
          result: {
            detector_version: "detector-v1",
            digest: "c".repeat(64),
            layout_candidates: allCandidates,
          },
        }),
        202,
      ),
    );
    confirmMock.mockResolvedValueOnce(
      ok(previewConfirmation(allCandidates[1], "fr")),
    );
    renderPage();
    await runValidation();
    const baseLanguage = screen.getByRole("combobox", {
      name: "Base language",
    });
    expect(baseLanguage).toHaveTextContent("Select base language");
    await userEvent.click(baseLanguage);
    expect(
      screen.getAllByRole("option").map((option) => option.textContent),
    ).toEqual(["en", "fr", "it"]);
    await userEvent.click(screen.getByRole("option", { name: "fr" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );
    expect(confirmMock).toHaveBeenCalledWith(
      expect.objectContaining({
        body: {
          base_language: "fr",
          layout_candidate_id: allCandidates[1].id,
          layout_candidate_version: 1,
          preview_digest: "c".repeat(64),
        },
      }),
    );
    expect(await screen.findByText("Confirmed")).toBeVisible();
    const details = screen.getByRole("region", {
      name: "Files, languages and source details",
    });
    for (const item of allCandidates)
      expect(within(details).getByText(item.files[0])).toBeVisible();
    expect(
      within(details).getByRole("list", { name: "Languages to import" }),
    ).toHaveTextContent("enfrit");
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Import strings" }),
    ).toBeEnabled();
  });

  it.each(["en", "default"])(
    "shows both repository sides and ignores keys-only %s for base choice",
    async (keysLanguage) => {
      const separate = {
        ...mapping,
        topology: "separate" as const,
        translations_repository_id: "00000000-0000-4000-8000-000000000402",
        translations_source_branch: "main",
      };
      listRevisionMappingsMock.mockResolvedValueOnce(
        ok({ items: [separate], next_cursor: null }),
      );
      const sourceCandidates = [
        {
          ...candidates[0],
          repository_side: "keys" as const,
          languages: [keysLanguage],
        },
        {
          ...candidates[1],
          repository_side: "translations" as const,
          languages: ["fr", "it"],
        },
      ];
      createJobMock.mockResolvedValueOnce(
        ok(
          previewJob({
            repository_sides: [
              { ...previewJob().repository_sides[0], role: "keys" },
              {
                ...previewJob().repository_sides[0],
                role: "translations",
                repository_id: separate.translations_repository_id,
              },
            ],
            result: {
              detector_version: "detector-v1",
              digest: "c".repeat(64),
              layout_candidates: sourceCandidates,
            },
          }),
          202,
        ),
      );
      renderPage();
      await runValidation();
      const details = screen.getByRole("region", {
        name: "Files, languages and source details",
      });
      expect(
        within(details).getByRole("region", { name: "keys files" }),
      ).toHaveTextContent(candidates[0].files[0]);
      expect(
        within(details).getByRole("region", { name: "translations files" }),
      ).toHaveTextContent(candidates[1].files[0]);
      await userEvent.click(
        screen.getByRole("combobox", { name: "Base language" }),
      );
      expect(
        screen.getAllByRole("option").map((option) => option.textContent),
      ).toEqual(["fr", "it"]);
    },
  );

  it("binds a separate default declaration to the translation side only", async () => {
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({
        items: [
          {
            ...mapping,
            topology: "separate" as const,
            translations_repository_id: "00000000-0000-4000-8000-000000000402",
            translations_source_branch: "main",
          },
        ],
        next_cursor: null,
      }),
    );
    const sourceCandidates = [
      {
        ...candidates[0],
        repository_side: "keys" as const,
        languages: ["default"],
      },
      {
        ...candidates[1],
        repository_side: "translations" as const,
        languages: ["default", "bg"],
      },
    ];
    createJobMock.mockResolvedValueOnce(
      ok(
        previewJob({
          result: {
            detector_version: "detector-v1",
            digest: "c".repeat(64),
            layout_candidates: sourceCandidates,
          },
        }),
        202,
      ),
    );
    confirmMock.mockResolvedValueOnce(
      ok(previewConfirmation(sourceCandidates[1], "en")),
    );
    renderPage();
    await runValidation();
    await userEvent.type(
      screen.getByRole("textbox", { name: "Base language" }),
      "en",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );
    expect(confirmMock).toHaveBeenCalledWith(
      expect.objectContaining({
        body: expect.objectContaining({
          base_language: "en",
          layout_candidate_id: sourceCandidates[1].id,
        }),
      }),
    );
    expect(await screen.findByText("Confirmed")).toBeVisible();
  });

  it("requires an explicit default language during active revalidation", async () => {
    const candidate = { ...candidates[0], languages: ["default", "bg"] };
    const job = activeRevalidationJob({
      result: {
        detector_version: "detector-v1",
        digest: "f".repeat(64),
        layout_candidates: [candidate],
      },
    });
    getProductMock.mockResolvedValue(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValue(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock.mockResolvedValue(
      ok(reactivationEligibility(false)),
    );
    getLatestActiveRevalidationMock.mockResolvedValueOnce(ok(job));
    confirmActiveRevalidationMock.mockResolvedValueOnce(
      ok({
        active_revision_id: job.active_revision_id,
        active_revision_version: job.active_revision_version,
        base_language: "en",
        commits: job.repository_sides,
        confirmed_at: "2026-09-30T18:00:00Z",
        confirmed_by: "00000000-0000-4000-8000-000000000001",
        connection_generation: job.connection_generation,
        job_id: job.id,
        layout_candidate_id: candidate.id,
        layout_candidate_version: candidate.version,
        mapping_id: job.mapping_id,
        preview_digest: "d".repeat(64),
        product_id: job.product_id,
      }),
    );
    renderPage(inactiveActiveOnlyProduct.id);
    const language = await screen.findByRole("textbox", {
      name: "Base language",
    });
    const confirm = screen.getByRole("button", { name: "Confirm preview" });
    expect(language).toHaveValue("");
    expect(confirm).toBeDisabled();
    await userEvent.type(language, "en");
    await userEvent.click(confirm);
    expect(confirmActiveRevalidationMock).toHaveBeenCalledWith(
      expect.objectContaining({
        body: expect.objectContaining({
          base_language: "en",
          layout_candidate_id: candidate.id,
          active_revision_id: job.active_revision_id,
          preview_digest: job.result!.digest,
        }),
      }),
    );
    expect(
      await screen.findByText("Confirmed", { selector: "[data-slot='badge']" }),
    ).toBeVisible();
  });

  it("starts multiple detected languages unselected and exposes only detected language options", async () => {
    const multipleLanguageCandidate = {
      ...candidates[0],
      languages: ["en", "it"],
    };
    createJobMock.mockResolvedValueOnce(
      ok(
        previewJob({
          result: {
            detector_version: "detector-v1",
            digest: "c".repeat(64),
            layout_candidates: [multipleLanguageCandidate],
          },
        }),
        202,
      ),
    );

    renderPage();
    await runValidation();

    const baseLanguage = screen.getByRole("combobox", {
      name: "Base language",
    });
    expect(baseLanguage).toHaveTextContent("Select base language");
    expect(baseLanguage).toHaveAttribute("aria-invalid", "true");
    expect(baseLanguage).toHaveAccessibleName("Base language");
    expect(screen.getByText("Base language required")).toBeVisible();
    expect(screen.getByText("Base language required")).toHaveClass(
      "font-semibold",
    );
    expect(
      screen.getByRole("button", { name: "Confirm preview" }),
    ).toBeDisabled();
    await userEvent.click(baseLanguage);
    expect(
      screen.getAllByRole("option").map((option) => option.textContent),
    ).toEqual(["en", "it"]);
    await userEvent.click(screen.getByRole("option", { name: "it" }));
    expect(baseLanguage).toHaveTextContent("it");
    expect(
      screen.queryByText("Base language required"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Confirm preview" }),
    ).toBeEnabled();
  });

  it("renders a bounded base-language blocker when detection has no language", async () => {
    createJobMock.mockResolvedValueOnce(
      ok(
        previewJob({
          result: {
            detector_version: "detector-v1",
            digest: "c".repeat(64),
            layout_candidates: [{ ...candidates[0], languages: [] }],
          },
        }),
        202,
      ),
    );

    renderPage();
    await runValidation();

    expect(screen.getByText("Base language required")).toBeVisible();
    expect(
      screen.queryByRole("combobox", { name: "Base language" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm preview" }),
    ).not.toBeInTheDocument();
  });

  it("preserves the selected language and focuses bounded backend rejection", async () => {
    confirmMock.mockResolvedValueOnce(
      failure({ detail: "base_language_required" }, 409) as never,
    );
    renderPage();
    await runValidation();

    const baseLanguage = screen.getByRole("combobox", {
      name: "Base language",
    });
    await userEvent.click(baseLanguage);
    await userEvent.click(screen.getByRole("option", { name: "it" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );

    const error = await screen.findByRole("alert", {
      name: "Base language required",
    });
    await waitFor(() => expect(error).toHaveFocus());
    expect(baseLanguage).toHaveTextContent("it");
    expect(
      screen.getByRole("region", {
        name: "Files, languages and source details",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Import strings" }),
    ).toBeDisabled();
  });

  it("rejects a foreign backend language projection without enabling publication", async () => {
    confirmMock.mockResolvedValueOnce(
      ok(previewConfirmation(candidates[0], "fr")),
    );
    renderPage();
    await runValidation();

    const baseLanguage = screen.getByRole("combobox", {
      name: "Base language",
    });
    await userEvent.click(baseLanguage);
    await userEvent.click(screen.getByRole("option", { name: "it" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );

    const error = await screen.findByRole("alert", {
      name: "Preview not confirmed",
    });
    await waitFor(() => expect(error).toHaveFocus());
    expect(baseLanguage).toHaveTextContent("it");
    expect(screen.queryByText("Confirmed")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Import strings" }),
    ).toBeDisabled();
  });

  it.each([
    { job_id: "foreign-job" },
    { mapping_id: "foreign-mapping" },
    { layout_candidate_id: "foreign-layout" },
    { preview_digest: "not-a-sha256-digest" },
  ])(
    "rejects foreign or malformed language-bound draft authority %j",
    async (mismatch) => {
      confirmMock.mockResolvedValueOnce(
        ok({ ...previewConfirmation(candidates[0], "en"), ...mismatch }),
      );
      renderPage();
      await runValidation();

      await selectBaseLanguage();
      await userEvent.click(
        screen.getByRole("button", { name: "Confirm preview" }),
      );
      expect(
        await screen.findByRole("alert", { name: "Preview not confirmed" }),
      ).toBeVisible();
      expect(
        screen.getByRole("button", { name: "Import strings" }),
      ).toBeDisabled();
    },
  );

  it.each([
    { base_language: "it" },
    { job_id: "foreign-job" },
    { active_revision_version: 99 },
    { connection_generation: 99 },
    { preview_digest: "not-a-sha256-digest" },
  ])(
    "rejects foreign or malformed language-bound active authority %j",
    async (mismatch) => {
      const job = activeRevalidationJob();
      getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
      listRevisionMappingsMock.mockResolvedValueOnce(
        ok({ items: [confirmedActiveMapping], next_cursor: null }),
      );
      getReactivationEligibilityMock.mockResolvedValueOnce(
        ok(reactivationEligibility(false)),
      );
      createActiveRevalidationMock.mockResolvedValueOnce(ok(job));
      confirmActiveRevalidationMock.mockResolvedValueOnce(
        ok({
          active_revision_id: job.active_revision_id,
          active_revision_version: job.active_revision_version,
          base_language: "en",
          commits: job.repository_sides,
          confirmed_at: "2026-08-31T17:00:06Z",
          confirmed_by: "admin",
          connection_generation: job.connection_generation,
          job_id: job.id,
          layout_candidate_id: candidates[0].id,
          layout_candidate_version: candidates[0].version,
          mapping_id: job.mapping_id,
          preview_digest: "d".repeat(64),
          product_id: job.product_id,
          ...mismatch,
        }),
      );
      renderPage(inactiveActiveOnlyProduct.id);
      await userEvent.click(
        await screen.findByRole("button", { name: "Run validation again" }),
      );

      await selectBaseLanguage();
      await userEvent.click(
        screen.getByRole("button", { name: "Confirm preview" }),
      );
      expect(
        await screen.findByRole("alert", { name: "Preview not confirmed" }),
      ).toBeVisible();
      expect(
        screen.getByRole("button", { name: "Reactivate product" }),
      ).toBeDisabled();
      expect(getReactivationEligibilityMock).toHaveBeenCalledTimes(1);
    },
  );

  it("invalidates stale confirmation on language change and deduplicates submission", async () => {
    let resolveConfirmation!: (
      value: ReturnType<typeof ok<AdminPreviewConfirmationResponse>>,
    ) => void;
    confirmMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveConfirmation = resolve;
      }) as never,
    );
    renderPage();
    await runValidation();

    const firstLanguage = screen.getByRole("combobox", {
      name: "Base language",
    });
    await userEvent.click(firstLanguage);
    await userEvent.click(screen.getByRole("option", { name: "en" }));
    const confirm = screen.getByRole("button", { name: "Confirm preview" });
    act(() => {
      confirm.click();
      confirm.click();
    });
    await waitFor(() => expect(confirmMock).toHaveBeenCalledOnce());

    const secondLanguage = screen.getByRole("combobox", {
      name: "Base language",
    });
    await userEvent.click(secondLanguage);
    await userEvent.click(screen.getByRole("option", { name: "it" }));
    resolveConfirmation(ok(previewConfirmation(candidates[0], "en")));
    await act(async () => Promise.resolve());

    expect(confirmMock).toHaveBeenCalledOnce();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(secondLanguage).toHaveTextContent("it");
    expect(screen.queryByText("Confirmed")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Import strings" }),
    ).toBeDisabled();
  });

  it("invalidates a confirmed language while retaining all detected sources", async () => {
    confirmMock.mockResolvedValueOnce(
      ok(previewConfirmation(candidates[0], "en")),
    );
    renderPage();
    await runValidation();

    const baseLanguage = screen.getByRole("combobox", {
      name: "Base language",
    });
    await userEvent.click(baseLanguage);
    await userEvent.click(screen.getByRole("option", { name: "en" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );
    expect(await screen.findByText("Confirmed")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Import strings" }),
    ).toBeEnabled();

    await userEvent.click(baseLanguage);
    await userEvent.click(screen.getByRole("option", { name: "it" }));

    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(baseLanguage).toHaveTextContent("it");
    expect(screen.queryByText("Confirmed")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Import strings" }),
    ).toBeDisabled();
  });

  it("requires explicit current confirmation before named publication and trusts only backend success", async () => {
    confirmMock.mockResolvedValueOnce(
      ok({
        base_language: "en",
        confirmed_at: "2026-08-28T12:01:00Z",
        confirmed_by: "00000000-0000-4000-8000-000000000001",
        job_id: previewJob().id,
        layout_candidate_id: candidates[0].id,
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

    const publish = screen.getByRole("button", { name: "Import strings" });
    expect(publish).toBeDisabled();

    await selectBaseLanguage();
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );
    expect(confirmMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        base_language: "en",
        layout_candidate_id: candidates[0].id,
        layout_candidate_version: 1,
        preview_digest: "c".repeat(64),
      },
      path: { job_id: previewJob().id },
    });
    expect(await screen.findByText("Confirmed")).toBeVisible();
    expect(publish).toBeEnabled();

    await userEvent.click(publish);
    const dialog = screen.getByRole("alertdialog", {
      name: "Import strings for Mobile Product?",
    });
    expect(dialog).toHaveTextContent(
      "Save this configuration and import strings from 1 confirmed source. Progress will appear on this page.",
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Import strings" }),
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
        base_language: "en",
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

    await selectBaseLanguage();
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Import strings" }),
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
      within(alert).getByRole("link", { name: "Review Mobile app · main" }),
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

  it("recovers generation-stale active mappings with a language-bound confirmation digest without candidate mutation", async () => {
    const staleEligibility = reactivationEligibility(false);
    const currentEligibility = reactivationEligibility(true);
    const queuedJob = activeRevalidationJob({
      finished_at: null,
      is_current: false,
      result: null,
      started_at: null,
      state: "queued",
    });
    const succeededJob = activeRevalidationJob();
    const reactivatedProduct: AdminProductResponse = {
      ...inactiveActiveOnlyProduct,
      is_active: true,
    };
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock
      .mockResolvedValueOnce(ok(staleEligibility))
      .mockResolvedValueOnce(ok(currentEligibility));
    createActiveRevalidationMock
      .mockResolvedValueOnce(
        failure({ detail: "provider_token=must-not-render" }, 503) as never,
      )
      .mockResolvedValueOnce(ok(queuedJob, 202));
    getActiveRevalidationMock.mockResolvedValueOnce(ok(succeededJob));
    confirmActiveRevalidationMock.mockResolvedValueOnce(
      ok({
        active_revision_id: succeededJob.active_revision_id,
        active_revision_version: succeededJob.active_revision_version,
        base_language: "en",
        commits: succeededJob.repository_sides,
        confirmed_at: "2026-08-31T17:00:06Z",
        confirmed_by: "00000000-0000-4000-8000-000000000001",
        connection_generation: succeededJob.connection_generation,
        job_id: succeededJob.id,
        layout_candidate_id: candidates[0].id,
        layout_candidate_version: candidates[0].version,
        mapping_id: succeededJob.mapping_id,
        preview_digest: "d".repeat(64),
        product_id: succeededJob.product_id,
      }),
    );
    reactivateMock.mockResolvedValueOnce(ok(reactivatedProduct));

    const view = renderPage(inactiveActiveOnlyProduct.id);

    expect(await screen.findByText("Preview out of date")).toBeVisible();
    expect(
      screen.getByText(
        "This preview no longer matches the current draft. Run validation again.",
      ),
    ).toBeVisible();
    const runAgain = screen.getByRole("button", {
      name: "Run validation again",
    });
    const reactivate = screen.getByRole("button", {
      name: "Reactivate product",
    });
    expect(reactivate).toBeDisabled();

    await userEvent.click(runAgain);
    const recoveryStatus = await screen.findByRole("status", {
      name: "Active revision recovery status",
    });
    expect(recoveryStatus).toHaveTextContent(
      "Validation did not complete. Try again.",
    );
    expect(recoveryStatus).not.toHaveTextContent("must-not-render");
    await waitFor(() => expect(runAgain).toHaveFocus());

    await userEvent.click(runAgain);
    expect(
      (await screen.findAllByText("Queued", { exact: true }))[0],
    ).toBeVisible();
    expect(createActiveRevalidationMock).toHaveBeenLastCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        commits: [{ commit_hash: "b".repeat(40), role: "direct" }],
        expected_active_revision_version:
          inactiveActiveOnlyProduct.active_revision!.version,
      },
      path: {
        mapping_id: confirmedActiveMapping.id,
        product_id: inactiveActiveOnlyProduct.id,
        revision_id: inactiveActiveOnlyProduct.active_revision!.id,
      },
    });
    await waitFor(
      () => expect(getActiveRevalidationMock).toHaveBeenCalledOnce(),
      { timeout: 3_000 },
    );
    expect(
      (await screen.findAllByText("Succeeded", { exact: true }))[0],
    ).toBeVisible();

    await selectBaseLanguage();
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );
    expect(confirmActiveRevalidationMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        active_revision_id: succeededJob.active_revision_id,
        active_revision_version: succeededJob.active_revision_version,
        base_language: "en",
        commits: [{ commit_hash: "b".repeat(40), role: "direct" }],
        connection_generation: succeededJob.connection_generation,
        layout_candidate_id: candidates[0].id,
        layout_candidate_version: candidates[0].version,
        mapping_id: succeededJob.mapping_id,
        preview_digest: succeededJob.result!.digest,
      },
      path: { job_id: succeededJob.id },
    });
    expect((await screen.findAllByText("Confirmed"))[0]).toBeVisible();
    await waitFor(() => expect(reactivate).toBeEnabled());
    expect(getReactivationEligibilityMock).toHaveBeenCalledTimes(2);

    await userEvent.click(reactivate);
    await userEvent.click(
      within(screen.getByRole("alertdialog")).getByRole("button", {
        name: "Reactivate product",
      }),
    );
    expect(await screen.findByText("Active")).toBeVisible();

    expect(confirmMock).not.toHaveBeenCalled();
    expect(createJobMock).not.toHaveBeenCalled();
    expect(listCandidateMappingsMock).not.toHaveBeenCalled();
    expect(updateProductMock).not.toHaveBeenCalled();
    expect(publishMock).not.toHaveBeenCalled();

    view.unmount();
    const pollCountAfterUnmount = getActiveRevalidationMock.mock.calls.length;
    await new Promise((resolve) => window.setTimeout(resolve, 25));
    expect(getActiveRevalidationMock).toHaveBeenCalledTimes(
      pollCountAfterUnmount,
    );
  });

  it("bounds unavailable and failed active-revision polling and restores recovery focus", async () => {
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock.mockResolvedValueOnce(
      ok(reactivationEligibility(false)),
    );
    createActiveRevalidationMock.mockImplementation(async () =>
      ok(
        activeRevalidationJob({
          created_at: new Date(Date.now() - 89_900).toISOString(),
          finished_at: null,
          is_current: false,
          result: null,
          started_at: null,
          state: "queued",
        }),
        202,
      ),
    );
    getActiveRevalidationMock
      .mockResolvedValueOnce(
        failure({ detail: "provider_token=must-not-render" }),
      )
      .mockRejectedValueOnce(new Error("bounded polling failure"))
      .mockResolvedValueOnce(
        ok(
          activeRevalidationJob({
            error_code: "processing_failed",
            is_current: false,
            result: null,
            state: "failed",
          }),
        ),
      );

    renderPage(inactiveActiveOnlyProduct.id);
    const runAgain = await screen.findByRole("button", {
      name: "Run validation again",
    });

    await userEvent.click(runAgain);
    await waitFor(() =>
      expect(
        screen.getByRole("status", {
          name: "Active revision recovery status",
        }),
      ).toHaveTextContent("Validation status is unavailable. Try again."),
    );
    await waitFor(() => expect(runAgain).toHaveFocus());
    expect(
      screen.getByText("Status unavailable").closest("[role='alert']"),
    ).not.toHaveTextContent("provider_token");

    await userEvent.click(runAgain);
    await waitFor(() =>
      expect(getActiveRevalidationMock).toHaveBeenCalledTimes(2),
    );
    await waitFor(() => expect(runAgain).toHaveFocus());

    await userEvent.click(runAgain);
    expect(
      await screen.findByText("Failed", { selector: "span" }),
    ).toBeVisible();
    await waitFor(() => expect(runAgain).toHaveFocus());
    expect(getActiveRevalidationMock).toHaveBeenCalledTimes(3);
  });

  it("pauses an expired active-revision job without issuing another provider read", async () => {
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock.mockResolvedValueOnce(
      ok(reactivationEligibility(false)),
    );
    createActiveRevalidationMock
      .mockResolvedValueOnce(
        ok(
          activeRevalidationJob({
            created_at: "2000-01-01T00:00:00Z",
            finished_at: null,
            is_current: false,
            result: null,
            started_at: null,
            state: "running",
          }),
          202,
        ),
      )
      .mockRejectedValueOnce(new Error("bounded create failure"))
      .mockResolvedValueOnce(
        ok(
          activeRevalidationJob({
            created_at: "not-a-timestamp",
            finished_at: null,
            is_current: false,
            result: null,
            started_at: null,
            state: "queued",
          }),
          202,
        ),
      );

    renderPage(inactiveActiveOnlyProduct.id);
    const runAgain = await screen.findByRole("button", {
      name: "Run validation again",
    });
    await userEvent.click(runAgain);

    await waitFor(() =>
      expect(
        screen.getByRole("status", {
          name: "Active revision recovery status",
        }),
      ).toHaveTextContent("Automatic updates paused. Try again."),
    );
    await waitFor(() => expect(runAgain).toHaveFocus());
    expect(getActiveRevalidationMock).not.toHaveBeenCalled();

    await userEvent.click(runAgain);
    await waitFor(() =>
      expect(
        screen.getByRole("status", {
          name: "Active revision recovery status",
        }),
      ).toHaveTextContent("Validation did not complete. Try again."),
    );
    await waitFor(() => expect(runAgain).toHaveFocus());

    await userEvent.click(runAgain);
    expect(
      (await screen.findAllByText("Queued", { exact: true }))[0],
    ).toBeVisible();
    expect(getActiveRevalidationMock).not.toHaveBeenCalled();
  });

  it("ignores a superseded poll and bounds the current poll transport failure", async () => {
    let resolveObsoletePoll!: (
      value: ReturnType<typeof ok<AdminActiveRevisionRevalidationJobResponse>>,
    ) => void;
    let rejectObsoletePoll!: (reason: Error) => void;
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock.mockResolvedValueOnce(
      ok(reactivationEligibility(false)),
    );
    createActiveRevalidationMock.mockImplementation(async () =>
      ok(
        activeRevalidationJob({
          created_at: new Date(Date.now() - 89_900).toISOString(),
          finished_at: null,
          is_current: false,
          result: null,
          started_at: null,
          state: "queued",
        }),
        202,
      ),
    );
    getActiveRevalidationMock
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveObsoletePoll = resolve;
        }) as never,
      )
      .mockReturnValueOnce(
        new Promise((_resolve, reject) => {
          rejectObsoletePoll = reject;
        }) as never,
      )
      .mockRejectedValueOnce(new Error("bounded current poll failure"));

    renderPage(inactiveActiveOnlyProduct.id);
    const runAgain = await screen.findByRole("button", {
      name: "Run validation again",
    });
    await userEvent.click(runAgain);
    await waitFor(() =>
      expect(getActiveRevalidationMock).toHaveBeenCalledOnce(),
    );

    await userEvent.click(runAgain);
    await waitFor(() =>
      expect(getActiveRevalidationMock).toHaveBeenCalledTimes(2),
    );
    await act(async () => {
      resolveObsoletePoll(ok(activeRevalidationJob()));
    });

    await userEvent.click(runAgain);
    await waitFor(() =>
      expect(getActiveRevalidationMock).toHaveBeenCalledTimes(3),
    );
    expect(await screen.findByText("Status unavailable")).toBeVisible();
    await act(async () => {
      rejectObsoletePoll(new Error("superseded polling failure"));
    });

    expect(
      screen.getByRole("status", {
        name: "Active revision recovery status",
      }),
    ).toHaveTextContent("Validation status is unavailable. Try again.");
    expect(
      screen.queryByText("Succeeded", { selector: "span" }),
    ).not.toBeInTheDocument();
  });

  it("deduplicates active-revision validation and ignores its superseded result", async () => {
    let resolveValidation!: (
      value: ReturnType<typeof ok<AdminActiveRevisionRevalidationJobResponse>>,
    ) => void;
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock.mockResolvedValueOnce(
      ok(reactivationEligibility(false)),
    );
    createActiveRevalidationMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveValidation = resolve;
      }) as never,
    );

    const view = renderPage(inactiveActiveOnlyProduct.id);
    const runAgain = await screen.findByRole("button", {
      name: "Run validation again",
    });
    await waitFor(() => expect(runAgain).toBeEnabled());
    act(() => {
      runAgain.click();
      runAgain.click();
    });
    await waitFor(() =>
      expect(createActiveRevalidationMock).toHaveBeenCalledOnce(),
    );

    view.unmount();
    await act(async () => {
      resolveValidation(ok(activeRevalidationJob(), 202));
    });
    expect(createActiveRevalidationMock).toHaveBeenCalledOnce();
    expect(getActiveRevalidationMock).not.toHaveBeenCalled();
  });

  it("ignores a rejected active validation after recovery authority unmounts", async () => {
    let rejectValidation!: (reason: Error) => void;
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock.mockResolvedValueOnce(
      ok(reactivationEligibility(false)),
    );
    createActiveRevalidationMock.mockReturnValueOnce(
      new Promise((_resolve, reject) => {
        rejectValidation = reject;
      }) as never,
    );

    const view = renderPage(inactiveActiveOnlyProduct.id);
    await userEvent.click(
      await screen.findByRole("button", { name: "Run validation again" }),
    );
    await waitFor(() =>
      expect(createActiveRevalidationMock).toHaveBeenCalledOnce(),
    );
    view.unmount();
    await act(async () => {
      rejectValidation(new Error("superseded create failure"));
    });

    expect(getActiveRevalidationMock).not.toHaveBeenCalled();
  });

  it("deduplicates confirmation and bounds empty and rejected responses", async () => {
    let resolveConfirmation!: (
      value: ReturnType<typeof failure<{ detail: string }>>,
    ) => void;
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock.mockResolvedValueOnce(
      ok(reactivationEligibility(false)),
    );
    createActiveRevalidationMock.mockResolvedValue(
      ok(activeRevalidationJob(), 202),
    );
    confirmActiveRevalidationMock
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveConfirmation = resolve;
        }) as never,
      )
      .mockRejectedValueOnce(new Error("bounded confirmation failure"));

    renderPage(inactiveActiveOnlyProduct.id);
    const runAgain = await screen.findByRole("button", {
      name: "Run validation again",
    });
    await userEvent.click(runAgain);

    await selectBaseLanguage();
    const confirm = screen.getByRole("button", { name: "Confirm preview" });
    act(() => {
      confirm.click();
      confirm.click();
    });
    await waitFor(() =>
      expect(confirmActiveRevalidationMock).toHaveBeenCalledOnce(),
    );
    await act(async () => {
      resolveConfirmation(failure({ detail: "provider_token=must-not-render" }));
    });
    const rejected = (await screen.findByText("Preview not confirmed")).closest(
      "[role='alert']",
    );
    expect(rejected).not.toHaveTextContent("provider_token");
    await waitFor(() => expect(rejected).toHaveFocus());

    await userEvent.click(runAgain);

    await selectBaseLanguage();
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm preview" }),
    );
    const rejectedAgain = (
      await screen.findByText("Preview not confirmed")
    ).closest("[role='alert']");
    expect(rejectedAgain).toBeVisible();
    await waitFor(() => expect(rejectedAgain).toHaveFocus());
    expect(confirmActiveRevalidationMock).toHaveBeenCalledTimes(2);
  });

  it("fails closed on invalid eligibility, retries transport errors, and accepts only exact authority", async () => {
    const invalidEligibility = {
      ...reactivationEligibility(true),
      product_id: "00000000-0000-4000-8000-000000000999",
    };
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock
      .mockRejectedValueOnce(new Error("bounded eligibility failure"))
      .mockResolvedValueOnce(ok(invalidEligibility))
      .mockResolvedValueOnce(ok(reactivationEligibility(true)));

    renderPage(inactiveActiveOnlyProduct.id);
    expect(
      await screen.findByText("Reactivation status unavailable"),
    ).toBeVisible();

    await userEvent.click(
      screen.getByRole("button", { name: "Retry confirmation check" }),
    );
    await waitFor(() =>
      expect(getReactivationEligibilityMock).toHaveBeenCalledTimes(2),
    );
    expect(
      await screen.findByText("Reactivation status unavailable"),
    ).toBeVisible();

    await userEvent.click(
      screen.getByRole("button", { name: "Retry confirmation check" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Reactivate product" }),
      ).toBeEnabled(),
    );
    expect(getReactivationEligibilityMock).toHaveBeenCalledTimes(3);
  });

  it("cancels queued eligibility loading when the page unmounts", async () => {
    const view = renderPage();
    view.unmount();

    await act(async () => Promise.resolve());
    expect(getReactivationEligibilityMock).not.toHaveBeenCalled();
  });

  it("ignores superseded eligibility and omits already-current mappings from blockers", async () => {
    let resolveEligibility!: (
      value: ReturnType<typeof ok<AdminProductReactivationEligibilityResponse>>,
    ) => void;
    let rejectEligibility!: (reason: Error) => void;
    const secondMapping = {
      ...confirmedActiveMapping,
      id: "00000000-0000-4000-8000-000000000302",
    };
    const mixedEligibility: AdminProductReactivationEligibilityResponse = {
      ...reactivationEligibility(false),
      mappings: [
        {
          blocker_codes: [],
          is_current: true,
          mapping_id: confirmedActiveMapping.id,
        },
        {
          blocker_codes: ["revalidation_confirmation_required"],
          is_current: false,
          mapping_id: secondMapping.id,
        },
      ],
    };
    getProductMock.mockResolvedValue(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValue(
      ok({ items: [confirmedActiveMapping, secondMapping], next_cursor: null }),
    );
    getReactivationEligibilityMock
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveEligibility = resolve;
        }) as never,
      )
      .mockReturnValueOnce(
        new Promise((_resolve, reject) => {
          rejectEligibility = reject;
        }) as never,
      )
      .mockResolvedValueOnce(ok(mixedEligibility));

    const view = renderPage(inactiveActiveOnlyProduct.id);
    await waitFor(() =>
      expect(getReactivationEligibilityMock).toHaveBeenCalledOnce(),
    );
    view.rerender(
      <MemoryRouter>
        <ProductPreviewPage
          accessToken="successor-admin-bearer"
          productId={inactiveActiveOnlyProduct.id}
        />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(getReactivationEligibilityMock).toHaveBeenCalledTimes(3),
    );
    resolveEligibility(ok(reactivationEligibility(true)));
    rejectEligibility(new Error("superseded eligibility failure"));

    expect(
      await screen.findByText(
        "Choose a base language and confirm the sources above to continue.",
      ),
    ).toBeVisible();
    expect(screen.getAllByText("Confirmed", { exact: true })).toHaveLength(1);
    expect(
      screen.getByRole("button", { name: "Reactivate product" }),
    ).toBeDisabled();
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
      getReactivationEligibilityMock.mockResolvedValueOnce(
        ok(reactivationEligibility(false)),
      );
      listRevisionMappingsMock.mockResolvedValueOnce(
        ok({ items: [blockedMapping], next_cursor: null }),
      );

      renderPage();

      expect(
        await screen.findByText(
          "Choose a base language and confirm the sources above to continue.",
        ),
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
