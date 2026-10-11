import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useSubmissionPolling } from "./useSubmissionPolling";
import { submissionFixture } from "./submissionTestFixture";
import { nextSubmissionPollDelay } from "./submissionStatus";
const api = vi.hoisted(() => ({ getChangeSet: vi.fn() }));
vi.mock("../../api/client", () => api);
const ok = (data: ReturnType<typeof submissionFixture>) => ({
  data,
  response: new Response(),
});
beforeEach(() => {
  vi.useFakeTimers();
  api.getChangeSet.mockReset();
  Object.defineProperty(document, "hidden", {
    configurable: true,
    value: false,
  });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});
it("uses two then five seconds and stops at ninety seconds", () => {
  expect(nextSubmissionPollDelay(0)).toBe(2000);
  expect(nextSubmissionPollDelay(30000)).toBe(5000);
  expect(nextSubmissionPollDelay(89500)).toBe(500);
  expect(nextSubmissionPollDelay(90000)).toBeNull();
});
it("polls transitions without stealing focus and preserves last status on error", async () => {
  const initial = submissionFixture();
  api.getChangeSet
    .mockResolvedValueOnce(ok({ ...initial, status: "running" }))
    .mockRejectedValue(new Error("offline"));
  const { result } = renderHook(() =>
    useSubmissionPolling("token", "product", initial),
  );
  const button = document.createElement("button");
  document.body.append(button);
  button.focus();
  await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(result.current.record.status).toBe("running");
  expect(document.activeElement).toBe(button);
  await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(result.current.error).toBe(true);
  expect(result.current.record.status).toBe("running");
  button.remove();
});
it("pauses hidden requests and reads once on return within the attempt window", async () => {
  const initial = submissionFixture();
  api.getChangeSet.mockResolvedValue(ok(initial));
  renderHook(() => useSubmissionPolling("token", "product", initial));
  Object.defineProperty(document, "hidden", { value: true });
  act(() => document.dispatchEvent(new Event("visibilitychange")));
  await act(() => vi.advanceTimersByTimeAsync(20000));
  expect(api.getChangeSet).not.toHaveBeenCalled();
  Object.defineProperty(document, "hidden", { value: false });
  await act(async () => document.dispatchEvent(new Event("visibilitychange")));
  expect(api.getChangeSet).toHaveBeenCalledTimes(1);
});
it.each(["queued", "succeeded"] as const)(
  "does not resume visibility polling past cutoff or terminal %s",
  async (status) => {
    const initial = submissionFixture({
      status,
      attempt_started_at: new Date(Date.now() - 100000).toISOString(),
    });
    api.getChangeSet.mockResolvedValue(ok(initial));
    const { result } = renderHook(() =>
      useSubmissionPolling("token", "product", initial),
    );
    await act(async () =>
      document.dispatchEvent(new Event("visibilitychange")),
    );
    await act(() => vi.advanceTimersByTimeAsync(10000));
    expect(api.getChangeSet).not.toHaveBeenCalled();
    await act(async () => result.current.refresh());
    expect(api.getChangeSet).toHaveBeenCalledTimes(1);
    await act(() => vi.advanceTimersByTimeAsync(10000));
    expect(api.getChangeSet).toHaveBeenCalledTimes(1);
  },
);
it("discards late principal responses and refuses same-attempt terminal regression", async () => {
  const initial = submissionFixture();
  let resolve!: (result: ReturnType<typeof ok>) => void;
  api.getChangeSet.mockImplementationOnce(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  const { result, rerender } = renderHook(
    ({ token }) => useSubmissionPolling(token, "product", initial),
    { initialProps: { token: "old" } },
  );
  await act(() => vi.advanceTimersByTimeAsync(2000));
  rerender({ token: "new" });
  await act(async () =>
    resolve(ok({ ...initial, status: "succeeded", pr_id: 41 })),
  );
  expect(result.current.record.pr_id).toBeNull();
  act(() => result.current.accept({ ...initial, status: "succeeded" }));
  act(() => result.current.accept({ ...initial, status: "failed" }));
  expect(result.current.record.status).toBe("succeeded");
  act(() => result.current.accept({ ...initial, status: "resolved" }));
  act(() => result.current.accept({ ...initial, status: "succeeded" }));
  expect(result.current.record.status).toBe("resolved");
});
