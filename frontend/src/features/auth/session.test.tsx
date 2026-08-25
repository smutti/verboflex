import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  issueToken,
  logout as generatedLogout,
  readCurrentUser,
  refreshAccessToken,
  changePassword as generatedChangePassword,
} from "../../api/client";
import { SessionProvider, useSession } from "./session";

vi.mock("../../api/client", () => ({
  changePassword: vi.fn(),
  issueToken: vi.fn(),
  logout: vi.fn(),
  readCurrentUser: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

const issueTokenMock = vi.mocked(issueToken);
const readCurrentUserMock = vi.mocked(readCurrentUser);
const refreshAccessTokenMock = vi.mocked(refreshAccessToken);
const logoutMock = vi.mocked(generatedLogout);
const changePasswordMock = vi.mocked(generatedChangePassword);

const principal = {
  id: "73f123f7-ebad-4dad-8b5d-dcc3214b3b06",
  email: "person@example.com",
  display_name: "Person",
  roles: ["translator" as const],
  must_change_password: false,
};

function Wrapper({ children }: PropsWithChildren) {
  return <SessionProvider restoreOnMount={false}>{children}</SessionProvider>;
}

function RestoringWrapper({ children }: PropsWithChildren) {
  return <SessionProvider>{children}</SessionProvider>;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

describe("session transitions", () => {
  beforeEach(() => {
    issueTokenMock.mockReset();
    readCurrentUserMock.mockReset();
    refreshAccessTokenMock.mockReset();
    logoutMock.mockReset();
    changePasswordMock.mockReset();
  });

  it("starts signed out when automatic restoration is disabled", () => {
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });

    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("rejects session access outside the provider boundary", () => {
    expect(() => renderHook(() => useSession())).toThrow(
      "useSession must be used within SessionProvider",
    );
  });

  it("ordinary login keeps access authority in React memory and confirms identity through me", async () => {
    issueTokenMock.mockResolvedValue({
      data: {
        access_token: "ordinary-memory-token",
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      },
      error: undefined,
    });
    readCurrentUserMock.mockResolvedValue({
      data: principal,
      error: undefined,
    });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });

    await act(async () => {
      await result.current.login({
        email: "person@example.com",
        password: "ordinary login phrase!",
      });
    });

    expect(issueTokenMock).toHaveBeenCalledWith({
      body: {
        username: "person@example.com",
        password: "ordinary login phrase!",
      },
    });
    expect(readCurrentUserMock).toHaveBeenCalledWith({
      auth: "ordinary-memory-token",
    });
    expect(result.current.state).toEqual({
      status: "authenticated",
      accessToken: "ordinary-memory-token",
      principal,
    });
  });

  it("temporary login enters the restricted state without exposing an ordinary principal", async () => {
    issueTokenMock.mockResolvedValue({
      data: {
        access_token: "password-change-only-token",
        expires_in: 300,
        must_change_password: true,
        token_type: "bearer",
      },
      error: undefined,
    });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });

    await act(async () => {
      await result.current.login({
        email: "person@example.com",
        password: "temporary password phrase!",
      });
    });

    expect(readCurrentUserMock).not.toHaveBeenCalled();
    expect(result.current.state).toEqual({
      status: "password_change_required",
      accessToken: "password-change-only-token",
    });
    expect(result.current.state).not.toHaveProperty("principal");
  });

  it("rejects an invalid login result without exposing backend diagnostics", async () => {
    issueTokenMock.mockResolvedValue({
      data: undefined,
      error: { detail: "Invalid credentials" },
    });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });

    await act(async () => {
      await expect(
        result.current.login({
          email: "person@example.com",
          password: "wrong phrase 2026!",
        }),
      ).rejects.toThrow("Session action failed");
    });

    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("fails closed when login authority has no matching identity", async () => {
    issueTokenMock.mockResolvedValue({
      data: {
        access_token: "orphaned-memory-token",
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      },
      error: undefined,
    });
    readCurrentUserMock.mockResolvedValue({
      data: undefined,
      error: { detail: "Identity unavailable" },
    });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });

    await act(async () => {
      await result.current.login({
        email: "person@example.com",
        password: "ordinary login phrase!",
      });
    });

    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("ignores a login authority response invalidated by logout", async () => {
    const token = deferred<Awaited<ReturnType<typeof issueToken>>>();
    issueTokenMock.mockReturnValue(
      token.promise as ReturnType<typeof issueToken>,
    );
    logoutMock.mockResolvedValue({ data: undefined, error: undefined });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    let pendingLogin!: Promise<void>;

    act(() => {
      pendingLogin = result.current.login({
        email: "person@example.com",
        password: "ordinary login phrase!",
      });
    });
    await act(async () => {
      await result.current.logout();
    });
    await act(async () => {
      token.resolve({
        data: {
          access_token: "stale-token",
          expires_in: 900,
          must_change_password: false,
          token_type: "bearer",
        },
        error: undefined,
      });
      await pendingLogin;
    });

    expect(readCurrentUserMock).not.toHaveBeenCalled();
    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("ignores a login identity response invalidated by logout", async () => {
    const identity = deferred<Awaited<ReturnType<typeof readCurrentUser>>>();
    issueTokenMock.mockResolvedValue({
      data: {
        access_token: "stale-token",
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      },
      error: undefined,
    });
    readCurrentUserMock.mockReturnValue(
      identity.promise as ReturnType<typeof readCurrentUser>,
    );
    logoutMock.mockResolvedValue({ data: undefined, error: undefined });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    let pendingLogin!: Promise<void>;

    await act(async () => {
      pendingLogin = result.current.login({
        email: "person@example.com",
        password: "ordinary login phrase!",
      });
      await vi.waitFor(() =>
        expect(readCurrentUserMock).toHaveBeenCalledOnce(),
      );
    });
    await act(async () => {
      await result.current.logout();
    });
    await act(async () => {
      identity.resolve({ data: principal, error: undefined });
      await pendingLogin;
    });

    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("successful required password change clears authority and becomes signed out", async () => {
    issueTokenMock.mockResolvedValue({
      data: {
        access_token: "password-change-only-token",
        expires_in: 300,
        must_change_password: true,
        token_type: "bearer",
      },
      error: undefined,
    });
    changePasswordMock.mockResolvedValue({ data: undefined, error: undefined });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    await act(async () => {
      await result.current.login({
        email: "person@example.com",
        password: "temporary password phrase!",
      });
    });

    await act(async () => {
      await result.current.changePassword({
        currentPassword: "temporary password phrase!",
        newPassword: "replacement password phrase!",
      });
    });

    expect(changePasswordMock).toHaveBeenCalledWith({
      auth: "password-change-only-token",
      body: {
        current_password: "temporary password phrase!",
        new_password: "replacement password phrase!",
      },
    });
    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("does not send a password change without restricted authority", async () => {
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });

    await act(async () => {
      await result.current.changePassword({
        currentPassword: "temporary password phrase!",
        newPassword: "replacement password phrase!",
      });
    });

    expect(changePasswordMock).not.toHaveBeenCalled();
    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("ignores a password-change response invalidated by logout", async () => {
    const change =
      deferred<Awaited<ReturnType<typeof generatedChangePassword>>>();
    issueTokenMock.mockResolvedValue({
      data: {
        access_token: "password-change-only-token",
        expires_in: 300,
        must_change_password: true,
        token_type: "bearer",
      },
      error: undefined,
    });
    changePasswordMock.mockReturnValue(
      change.promise as ReturnType<typeof generatedChangePassword>,
    );
    logoutMock.mockResolvedValue({ data: undefined, error: undefined });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    await act(async () => {
      await result.current.login({
        email: "person@example.com",
        password: "temporary password phrase!",
      });
    });
    let pendingChange!: Promise<void>;

    act(() => {
      pendingChange = result.current.changePassword({
        currentPassword: "temporary password phrase!",
        newPassword: "replacement password phrase!",
      });
    });
    await act(async () => {
      await result.current.logout();
    });
    await act(async () => {
      change.resolve({ data: undefined, error: undefined });
      await pendingChange;
    });

    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("rejects a failed password change without exposing backend diagnostics", async () => {
    issueTokenMock.mockResolvedValue({
      data: {
        access_token: "password-change-only-token",
        expires_in: 300,
        must_change_password: true,
        token_type: "bearer",
      },
      error: undefined,
    });
    changePasswordMock.mockResolvedValue({
      data: undefined,
      error: { detail: "Current password is incorrect" },
    });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    await act(async () => {
      await result.current.login({
        email: "person@example.com",
        password: "temporary password phrase!",
      });
    });

    await act(async () => {
      await expect(
        result.current.changePassword({
          currentPassword: "wrong temporary phrase!",
          newPassword: "replacement password phrase!",
        }),
      ).rejects.toThrow("Session action failed");
    });

    expect(result.current.state).toEqual({
      status: "password_change_required",
      accessToken: "password-change-only-token",
    });
  });

  it("reload starts checking then restores through generated refresh and me operations", async () => {
    let resolveRefresh: (() => void) | undefined;
    refreshAccessTokenMock.mockReturnValue(
      new Promise((resolve) => {
        resolveRefresh = () =>
          resolve({
            data: {
              access_token: "restored-memory-token",
              expires_in: 900,
              must_change_password: false,
              token_type: "bearer",
            },
            error: undefined,
          });
      }) as ReturnType<typeof refreshAccessToken>,
    );
    readCurrentUserMock.mockResolvedValue({
      data: principal,
      error: undefined,
    });
    const { result } = renderHook(() => useSession(), {
      wrapper: RestoringWrapper,
    });

    expect(result.current.state).toEqual({ status: "checking_session" });
    expect(refreshAccessTokenMock).toHaveBeenCalledWith();

    await act(async () => {
      resolveRefresh?.();
    });

    await waitFor(() => {
      expect(result.current.state).toEqual({
        status: "authenticated",
        accessToken: "restored-memory-token",
        principal,
      });
    });
    expect(readCurrentUserMock).toHaveBeenCalledWith({
      auth: "restored-memory-token",
    });
  });

  it("refresh failure signs out without retaining a stale identity", async () => {
    issueTokenMock.mockResolvedValue({
      data: {
        access_token: "ordinary-memory-token",
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      },
      error: undefined,
    });
    readCurrentUserMock.mockResolvedValue({
      data: principal,
      error: undefined,
    });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    await act(async () => {
      await result.current.login({
        email: "person@example.com",
        password: "ordinary login phrase!",
      });
    });
    refreshAccessTokenMock.mockRejectedValue(new Error("network unavailable"));

    await act(async () => {
      await result.current.restoreSession().catch(() => undefined);
    });

    expect(result.current.state).toEqual({ status: "signed_out" });
    expect(result.current.state).not.toHaveProperty("principal");
    expect(readCurrentUserMock).toHaveBeenCalledOnce();
  });

  it.each([
    ["missing", undefined],
    [
      "password-change-only",
      {
        access_token: "refresh-password-change-token",
        expires_in: 300,
        must_change_password: true,
        token_type: "bearer" as const,
      },
    ],
  ])("fails closed for %s restored authority", async (_kind, authority) => {
    refreshAccessTokenMock.mockResolvedValue({
      data: authority,
      error: authority === undefined ? { detail: "No session" } : undefined,
    } as Awaited<ReturnType<typeof refreshAccessToken>>);
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });

    await act(async () => {
      await result.current.restoreSession();
    });

    expect(readCurrentUserMock).not.toHaveBeenCalled();
    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("fails closed when restored authority has no matching identity", async () => {
    refreshAccessTokenMock.mockResolvedValue({
      data: {
        access_token: "orphaned-restored-token",
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      },
      error: undefined,
    });
    readCurrentUserMock.mockResolvedValue({
      data: undefined,
      error: { detail: "Identity unavailable" },
    });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });

    await act(async () => {
      await result.current.restoreSession();
    });

    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("ignores a refresh rejection invalidated by logout", async () => {
    const refresh = deferred<Awaited<ReturnType<typeof refreshAccessToken>>>();
    refreshAccessTokenMock.mockReturnValue(
      refresh.promise as ReturnType<typeof refreshAccessToken>,
    );
    logoutMock.mockResolvedValue({ data: undefined, error: undefined });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    let pendingRestore!: Promise<void>;

    act(() => {
      pendingRestore = result.current.restoreSession();
    });
    await act(async () => {
      await result.current.logout();
    });
    await act(async () => {
      refresh.reject(new Error("stale refresh rejection"));
      await pendingRestore;
    });

    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("ignores a restored identity response invalidated by logout", async () => {
    const identity = deferred<Awaited<ReturnType<typeof readCurrentUser>>>();
    refreshAccessTokenMock.mockResolvedValue({
      data: {
        access_token: "stale-restored-token",
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      },
      error: undefined,
    });
    readCurrentUserMock.mockReturnValue(
      identity.promise as ReturnType<typeof readCurrentUser>,
    );
    logoutMock.mockResolvedValue({ data: undefined, error: undefined });
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    let pendingRestore!: Promise<void>;

    await act(async () => {
      pendingRestore = result.current.restoreSession();
      await vi.waitFor(() =>
        expect(readCurrentUserMock).toHaveBeenCalledOnce(),
      );
    });
    await act(async () => {
      await result.current.logout();
    });
    await act(async () => {
      identity.resolve({ data: principal, error: undefined });
      await pendingRestore;
    });

    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("logout clears React memory even when the generated network call fails", async () => {
    issueTokenMock.mockResolvedValue({
      data: {
        access_token: "ordinary-memory-token",
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      },
      error: undefined,
    });
    readCurrentUserMock.mockResolvedValue({
      data: principal,
      error: undefined,
    });
    logoutMock.mockRejectedValue(new Error("logout network unavailable"));
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    await act(async () => {
      await result.current.login({
        email: "person@example.com",
        password: "ordinary login phrase!",
      });
    });

    await act(async () => {
      await result.current.logout().catch(() => undefined);
    });

    expect(logoutMock).toHaveBeenCalledWith();
    expect(result.current.state).toEqual({ status: "signed_out" });
    expect(result.current.state).not.toHaveProperty("accessToken");
    expect(result.current.state).not.toHaveProperty("principal");
  });

  it("a refresh response arriving after logout cannot restore stale authority", async () => {
    let resolveRefresh: (() => void) | undefined;
    refreshAccessTokenMock.mockReturnValue(
      new Promise((resolve) => {
        resolveRefresh = () =>
          resolve({
            data: {
              access_token: "stale-restored-token",
              expires_in: 900,
              must_change_password: false,
              token_type: "bearer",
            },
            error: undefined,
          });
      }) as ReturnType<typeof refreshAccessToken>,
    );
    readCurrentUserMock.mockResolvedValue({
      data: principal,
      error: undefined,
    });
    logoutMock.mockResolvedValue({ data: undefined, error: undefined });
    const { result } = renderHook(() => useSession(), {
      wrapper: RestoringWrapper,
    });
    expect(result.current.state).toEqual({ status: "checking_session" });

    await act(async () => {
      await result.current.logout();
    });
    await act(async () => {
      resolveRefresh?.();
    });

    expect(result.current.state).toEqual({ status: "signed_out" });
    expect(readCurrentUserMock).not.toHaveBeenCalled();
  });
});
