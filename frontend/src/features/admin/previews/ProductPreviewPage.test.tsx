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
  selected_layout_candidate_id:
    "00000000-0000-4000-8000-000000000501",
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

function renderPage() {
  return render(
    <MemoryRouter>
      <ProductPreviewPage
        accessToken="memory-only-admin-bearer"
        productId={product.id}
      />
    </MemoryRouter>,
  );
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
    let resolveProduct!: (value: ReturnType<typeof ok<AdminProductResponse>>) => void;
    getProductMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveProduct = resolve;
      }),
    );
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );

    renderPage();
    await waitFor(() => expect(getProductMock).toHaveBeenCalledTimes(1));
    expect(listRevisionMappingsMock).not.toHaveBeenCalled();

    resolveProduct(ok(inactiveActiveOnlyProduct));

    expect(
      await screen.findByRole("button", { name: "Reactivate product" }),
    ).toBeEnabled();
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
    ["missing", { ...confirmedActiveMapping, selected_layout_candidate_id: null }],
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
        await screen.findByText(
          "Mapping 1: Preview confirmation required",
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
    let resolveConflict!: (
      value: ReturnType<
        typeof failure<AdminProductLifecycleConflictResponse>
      >,
    ) => void;
    getProductMock.mockResolvedValueOnce(ok(inactiveActiveOnlyProduct));
    listRevisionMappingsMock.mockResolvedValueOnce(
      ok({ items: [confirmedActiveMapping], next_cursor: null }),
    );
    reactivateMock
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveConflict = resolve;
        }),
      )
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

    resolveConflict(
      failure(
        {
          blockers: ["preview_confirmation_required"],
          detail: "Product publication blocked",
        },
        409,
      ),
    );
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
});
