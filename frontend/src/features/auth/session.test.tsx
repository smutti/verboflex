import { act, renderHook } from "@testing-library/react";
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

describe("session transitions", () => {
  beforeEach(() => {
    issueTokenMock.mockReset();
    readCurrentUserMock.mockReset();
    refreshAccessTokenMock.mockReset();
    logoutMock.mockReset();
    changePasswordMock.mockReset();
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
    readCurrentUserMock.mockResolvedValue({ data: principal, error: undefined });
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
});
