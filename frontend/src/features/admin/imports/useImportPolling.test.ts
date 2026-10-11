import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getAdminImport,
  type AdminPublishedMappingImportResponse,
} from "../../../api/client";
import {
  importPollingIdentity,
  nextImportPollDelay,
  useImportPolling,
} from "./useImportPolling";

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();
  return { ...original, getAdminImport: vi.fn() };
});

const getImportMock = vi.mocked(getAdminImport);

function ok<T>(data: T) {
  return {
    data,
    error: undefined,
    request: new Request(
      "http://localhost/api/v1/admin/products/product-1/imports/import-1",
    ),
    response: new Response(null, { status: 200 }),
  };
}

function publishedImport(
  overrides: Partial<AdminPublishedMappingImportResponse> = {},
): AdminPublishedMappingImportResponse {
  return {
    action: "import_in_progress",
    active_baseline: null,
    active_revision_id: "revision-1",
    capability: "ready",
    dataset_status: "not_created",
    error_category: null,
    error_message: null,
    execution_number: 1,
    id: "import-1",
    latest_execution_at: "2026-09-03T12:00:00Z",
    mapping_id: "mapping-1",
    parser_issue_remaining_count: 0,
    parser_issues: [],
    repository_sides: [
      {
        repository_id: "repository-1",
        role: "direct",
        source_branch: "main",
      },
    ],
    retry_count: 0,
    state: "queued",
    topology: "direct",
    ...overrides,
  };
}

describe("bounded published import polling", () => {
  it.each(["missing", "foreign"])(
    "discards %s polling authority without replacing the visible execution",
    async (kind) => {
      getImportMock.mockResolvedValue(
        kind === "missing"
          ? ({ data: undefined } as never)
          : ok(publishedImport({ id: "foreign", state: "current" })),
      );
      const announce = vi.fn();
      const { result } = renderHook(() =>
        useImportPolling({
          accessToken: "token",
          initialImport: publishedImport(),
          productId: "product-1",
          onAnnouncement: announce,
        }),
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });
      expect(result.current.importRecord).toEqual(publishedImport());
      expect(announce).not.toHaveBeenCalled();
      expect(result.current.pollingError).toBe(kind === "missing");
    },
  );
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-03T12:00:00Z"));
    getImportMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it.each([
    [0, 2_000],
    [2_000, 2_000],
    [28_000, 2_000],
    [29_000, 1_000],
    [30_000, 5_000],
    [85_000, 5_000],
    [89_000, 1_000],
    [90_000, null],
    [120_000, null],
  ])("UI3-C07 uses the exact bounded delay at %dms", (elapsedMs, expected) => {
    expect(nextImportPollDelay(elapsedMs)).toBe(expected);
  });

  it("binds identity to the logical import, execution, product, revision, and mapping", () => {
    const current = publishedImport();

    expect(importPollingIdentity("product-1", current)).not.toBe(
      importPollingIdentity("product-2", current),
    );
    expect(importPollingIdentity("product-1", current)).not.toBe(
      importPollingIdentity(
        "product-1",
        publishedImport({ execution_number: 2 }),
      ),
    );
    expect(importPollingIdentity("product-1", current)).not.toBe(
      importPollingIdentity(
        "product-1",
        publishedImport({ active_revision_id: "revision-2" }),
      ),
    );
    expect(importPollingIdentity("product-1", current)).not.toBe(
      importPollingIdentity(
        "product-1",
        publishedImport({ mapping_id: "mapping-2" }),
      ),
    );
    expect(importPollingIdentity("product-1", current)).not.toBe(
      importPollingIdentity("product-1", publishedImport({ id: "import-2" })),
    );
  });

  it("polls one execution, announces transitions once, and stops for review", async () => {
    const announce = vi.fn();
    getImportMock
      .mockResolvedValueOnce(ok(publishedImport()))
      .mockResolvedValueOnce(ok(publishedImport({ state: "running" })))
      .mockResolvedValueOnce(
        ok(
          publishedImport({
            action: "review_baseline_change",
            state: "review_required",
          }),
        ),
      );
    const { result } = renderHook(() =>
      useImportPolling({
        accessToken: "memory-only-admin-bearer",
        initialImport: publishedImport(),
        onAnnouncement: announce,
        productId: "product-1",
      }),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(announce).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(result.current.importRecord.state).toBe("running");
    expect(announce).toHaveBeenCalledTimes(1);
    expect(announce).toHaveBeenLastCalledWith("Running");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
      await vi.advanceTimersByTimeAsync(20_000);
    });
    expect(result.current.importRecord.state).toBe("review_required");
    expect(announce).toHaveBeenCalledTimes(2);
    expect(announce).toHaveBeenLastCalledWith("Review required");
    expect(getImportMock).toHaveBeenCalledTimes(3);
    expect(getImportMock).toHaveBeenLastCalledWith({
      auth: "memory-only-admin-bearer",
      path: { import_id: "import-1", product_id: "product-1" },
      signal: expect.any(AbortSignal),
    });
  });

  it.each([
    ["not_imported", "run_import"],
    ["current", "refresh_import"],
    ["may_be_stale", "retry_import"],
    ["import_failed", "retry_import"],
  ] as const)(
    "does not poll the terminal %s projection",
    async (state, action) => {
      renderHook(() =>
        useImportPolling({
          accessToken: "memory-only-admin-bearer",
          initialImport: publishedImport({ action, state }),
          productId: "product-1",
        }),
      );

      await act(async () => {
        await vi.advanceTimersByTimeAsync(120_000);
      });

      expect(getImportMock).not.toHaveBeenCalled();
    },
  );

  it("pauses at ninety seconds and allows explicit status refresh without resuming", async () => {
    getImportMock.mockResolvedValue(ok(publishedImport({ state: "running" })));
    const { result } = renderHook(() =>
      useImportPolling({
        accessToken: "memory-only-admin-bearer",
        initialImport: publishedImport({ state: "running" }),
        productId: "product-1",
      }),
    );

    for (let poll = 0; poll < 15; poll += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_000);
      });
    }
    for (let poll = 0; poll < 12; poll += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5_000);
      });
    }

    expect(getImportMock).toHaveBeenCalledTimes(27);
    expect(result.current.automaticUpdatesPaused).toBe(true);
    const callsAtCutoff = getImportMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(getImportMock).toHaveBeenCalledTimes(callsAtCutoff);

    await act(async () => {
      await result.current.refreshStatus();
    });
    expect(getImportMock).toHaveBeenCalledTimes(callsAtCutoff + 1);
    expect(result.current.automaticUpdatesPaused).toBe(true);
  });

  it("ignores a superseded response across the complete import identity", async () => {
    let resolveOld:
      | ((
          value: ReturnType<typeof ok<AdminPublishedMappingImportResponse>>,
        ) => void)
      | undefined;
    const oldRequest = new Promise<
      ReturnType<typeof ok<AdminPublishedMappingImportResponse>>
    >((resolve) => {
      resolveOld = resolve;
    });
    getImportMock.mockReturnValueOnce(oldRequest as never);
    const oldImport = publishedImport();
    const newImport = publishedImport({
      active_revision_id: "revision-2",
      execution_number: 2,
      id: "import-2",
      mapping_id: "mapping-2",
      state: "running",
    });
    const { result, rerender } = renderHook(
      ({ currentImport, currentProduct }) =>
        useImportPolling({
          accessToken: "memory-only-admin-bearer",
          initialImport: currentImport,
          productId: currentProduct,
        }),
      {
        initialProps: {
          currentImport: oldImport,
          currentProduct: "product-1",
        },
      },
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    rerender({ currentImport: newImport, currentProduct: "product-2" });
    resolveOld?.(
      ok(
        publishedImport({
          action: "retry_import",
          error_category: "provider_unavailable",
          error_message: "Import unavailable",
          state: "import_failed",
        }),
      ),
    );
    await act(async () => Promise.resolve());

    expect(result.current.importRecord.id).toBe("import-2");
    expect(result.current.importRecord.state).toBe("running");
    expect(result.current.pollingError).toBe(false);
  });

  it("pauses observation after a bounded status-read failure", async () => {
    getImportMock.mockRejectedValueOnce(new Error("provider detail excluded"));
    const { result } = renderHook(() =>
      useImportPolling({
        accessToken: "memory-only-admin-bearer",
        initialImport: publishedImport(),
        productId: "product-1",
      }),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });

    expect(result.current.pollingError).toBe(true);
    expect(result.current.automaticUpdatesPaused).toBe(true);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });
    expect(getImportMock).toHaveBeenCalledTimes(1);
  });

  it("drops late responses after unmount without cancelling durable worker work", async () => {
    let resolveRequest:
      | ((
          value: ReturnType<typeof ok<AdminPublishedMappingImportResponse>>,
        ) => void)
      | undefined;
    getImportMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRequest = resolve;
      }) as never,
    );
    const hook = renderHook(() =>
      useImportPolling({
        accessToken: "memory-only-admin-bearer",
        initialImport: publishedImport(),
        productId: "product-1",
      }),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    hook.unmount();
    resolveRequest?.(ok(publishedImport({ state: "running" })));
    await act(async () => Promise.resolve());

    expect(getImportMock).toHaveBeenCalledTimes(1);
    expect(getImportMock.mock.calls[0]?.[0].signal?.aborted).toBe(true);
  });
});
