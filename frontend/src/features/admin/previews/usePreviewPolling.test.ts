import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getAdminPreviewJob,
  type AdminPreviewJobResponse,
} from "../../../api/client";
import {
  nextPreviewPollDelay,
  previewJobIdentity,
  usePreviewPolling,
} from "./usePreviewPolling";

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();
  return { ...original, getAdminPreviewJob: vi.fn() };
});

const getJobMock = vi.mocked(getAdminPreviewJob);

function ok<T>(data: T) {
  return {
    data,
    error: undefined,
    request: new Request("http://localhost/api/v1/admin/preview-jobs/job-id"),
    response: new Response(null, { status: 200 }),
  };
}

function job(
  overrides: Partial<AdminPreviewJobResponse> = {},
): AdminPreviewJobResponse {
  return {
    attempt: 1,
    candidate_revision_id: "candidate-1",
    candidate_revision_version: 5,
    connection_generation: 7,
    created_at: "2026-08-28T12:00:00Z",
    detector_version: "detector-v1",
    error_code: null,
    finished_at: null,
    id: "job-1",
    input_digest: "a".repeat(64),
    is_current: true,
    mapping_id: "mapping-1",
    product_id: "product-1",
    repository_sides: [
      {
        commit_hash: "b".repeat(40),
        repository_id: "repository-1",
        role: "direct",
        source_branch: "main",
      },
    ],
    result: null,
    started_at: null,
    state: "queued",
    ...overrides,
  };
}

describe("bounded preview polling state machine", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-28T12:00:00Z"));
    getJobMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it.each([
    [0, 2_000],
    [2_000, 2_000],
    [28_000, 2_000],
    [30_000, 5_000],
    [85_000, 5_000],
    [89_000, 1_000],
    [90_000, null],
    [120_000, null],
  ])("uses the exact delay at %dms", (elapsedMs, expected) => {
    expect(nextPreviewPollDelay(elapsedMs)).toBe(expected);
  });

  it("polls at two seconds, announces transitions only, and stops at a terminal state", async () => {
    const announce = vi.fn();
    getJobMock
      .mockResolvedValueOnce(ok(job()))
      .mockResolvedValueOnce(ok(job({ state: "running" })))
      .mockResolvedValueOnce(
        ok(
          job({
            state: "succeeded",
            finished_at: "2026-08-28T12:00:06Z",
            result: {
              detector_version: "detector-v1",
              digest: "c".repeat(64),
              layout_candidates: [],
            },
          }),
        ),
      );
    const { result } = renderHook(() =>
      usePreviewPolling({
        accessToken: "memory-only-admin-bearer",
        initialJob: job(),
        onAnnouncement: announce,
      }),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(getJobMock).toHaveBeenCalledTimes(1);
    expect(announce).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(result.current.job.state).toBe("running");
    expect(announce).toHaveBeenCalledTimes(1);
    expect(announce).toHaveBeenLastCalledWith("Running");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
      await vi.advanceTimersByTimeAsync(20_000);
    });
    expect(result.current.job.state).toBe("succeeded");
    expect(announce).toHaveBeenCalledTimes(2);
    expect(announce).toHaveBeenLastCalledWith("Succeeded");
    expect(getJobMock).toHaveBeenCalledTimes(3);
  });

  it("pauses at ninety seconds and supports one explicit refresh", async () => {
    getJobMock.mockResolvedValue(ok(job({ state: "running" })));
    const { result } = renderHook(() =>
      usePreviewPolling({
        accessToken: "memory-only-admin-bearer",
        initialJob: job({ state: "running" }),
      }),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(90_000);
    });
    expect(result.current.automaticUpdatesPaused).toBe(true);
    const callsAtCutoff = getJobMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(getJobMock).toHaveBeenCalledTimes(callsAtCutoff);

    await act(async () => {
      await result.current.refreshStatus();
    });
    expect(getJobMock).toHaveBeenCalledTimes(callsAtCutoff + 1);
  });

  it("ignores a superseded job response across complete job and revision identity", async () => {
    let resolveOld:
      | ((value: ReturnType<typeof ok<AdminPreviewJobResponse>>) => void)
      | undefined;
    getJobMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveOld = resolve;
      }),
    );
    const oldJob = job();
    const newJob = job({
      id: "job-2",
      attempt: 2,
      candidate_revision_id: "candidate-2",
      candidate_revision_version: 6,
      connection_generation: 8,
      input_digest: "d".repeat(64),
      state: "running",
    });
    const { result, rerender } = renderHook(
      ({ currentJob }) =>
        usePreviewPolling({
          accessToken: "memory-only-admin-bearer",
          initialJob: currentJob,
        }),
      { initialProps: { currentJob: oldJob } },
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    rerender({ currentJob: newJob });
    expect(previewJobIdentity(oldJob)).not.toBe(previewJobIdentity(newJob));
    resolveOld?.(ok(job({ state: "failed", error_code: "processing_failed" })));
    await act(async () => Promise.resolve());

    expect(result.current.job.id).toBe("job-2");
    expect(result.current.job.state).toBe("running");
  });

  it("leaves the durable backend job running across navigation unmount", async () => {
    getJobMock.mockResolvedValue(ok(job({ state: "running" })));
    const first = renderHook(() =>
      usePreviewPolling({
        accessToken: "memory-only-admin-bearer",
        initialJob: job(),
      }),
    );
    first.unmount();

    const second = renderHook(() =>
      usePreviewPolling({
        accessToken: "memory-only-admin-bearer",
        initialJob: job(),
      }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    await waitFor(() => {
      expect(second.result.current.job.state).toBe("running");
    });
    expect(getJobMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { job_id: "job-1" },
    });
  });
});
