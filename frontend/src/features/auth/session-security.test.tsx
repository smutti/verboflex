import {
  act,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PropsWithChildren } from "react";
import {
  createMemoryRouter,
  Navigate,
  RouterProvider,
  useLocation,
} from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { issueToken, readCurrentUser } from "../../api/client";
import { client } from "../../api/client/client.gen";
import { SessionProvider, useSession } from "./session";
import { SessionNavigationBoundary } from "./SessionNavigationBoundary";
import { useDirtyFormNavigationGuard } from "../../components/navigation/DirtyFormNavigationGuard";

vi.mock("../../api/client", () => ({
  changePassword: vi.fn(),
  issueToken: vi.fn(),
  logout: vi.fn(),
  readCurrentUser: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

const principal = {
  id: "73f123f7-ebad-4dad-8b5d-dcc3214b3b06",
  email: "person@example.com",
  display_name: "Person",
  roles: ["admin" as const],
  must_change_password: false,
};
function Wrapper({ children }: PropsWithChildren) {
  return <SessionProvider restoreOnMount={false}>{children}</SessionProvider>;
}

function DirtyEditor() {
  useDirtyFormNavigationGuard("revoked-editor", true);
  return <textarea aria-label="Draft" defaultValue="Unsaved private text" />;
}

function SecurityRoutes() {
  const { state, login } = useSession();
  const { pathname } = useLocation();
  if (state.status === "authenticated") {
    return pathname === "/edit" ? <DirtyEditor /> : <Navigate to="/edit" />;
  }
  return pathname === "/login" ? (
    <button
      onClick={() =>
        void login({ email: principal.email, password: "fixture password" })
      }
    >
      Sign in
    </button>
  ) : (
    <Navigate to="/login" replace />
  );
}
async function deniedRequest(
  token: string,
  status = 401,
  detail = "Invalid access token",
) {
  return client.get({
    baseUrl: "http://localhost",
    url: "/api/v1/me",
    headers: { Authorization: `Bearer ${token}` },
    fetch: async () =>
      new Response(JSON.stringify({ detail }), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
  });
}

describe("session revocation", () => {
  beforeEach(() => {
    vi.mocked(issueToken).mockReset();
    vi.mocked(readCurrentUser).mockReset();
    vi.mocked(issueToken).mockResolvedValue({
      error: undefined,
      data: {
        access_token: "current-token",
        token_type: "bearer",
        expires_in: 900,
        must_change_password: false,
      },
    });
    vi.mocked(readCurrentUser).mockResolvedValue({
      data: principal,
      error: undefined,
    });
  });

  it("drops authenticated state when the server rejects its current token", async () => {
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    await act(() =>
      result.current.login({
        email: principal.email,
        password: "test password",
      }),
    );
    expect(result.current.state.status).toBe("authenticated");
    await act(() => deniedRequest("current-token"));
    expect(result.current.state).toEqual({ status: "signed_out" });
  });

  it("removes dirty editors and allows the authentication redirect after revocation", async () => {
    const router = createMemoryRouter(
      [
        {
          path: "*",
          element: (
            <Wrapper>
              <SessionNavigationBoundary>
                <SecurityRoutes />
              </SessionNavigationBoundary>
            </Wrapper>
          ),
        },
      ],
      { initialEntries: ["/login"] },
    );
    render(<RouterProvider router={router} />);
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByRole("textbox", { name: "Draft" });
    await act(() => deniedRequest("current-token"));
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(screen.queryByRole("textbox", { name: "Draft" })).toBeNull();
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("does not sign out a newer login when an old request fails", async () => {
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    await act(() =>
      result.current.login({
        email: principal.email,
        password: "test password",
      }),
    );
    await act(() => deniedRequest("old-token"));
    expect(result.current.state.status).toBe("authenticated");
  });

  it("keeps a valid session on an ordinary forbidden action", async () => {
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    await act(() =>
      result.current.login({
        email: principal.email,
        password: "test password",
      }),
    );
    await act(() =>
      deniedRequest("current-token", 403, "Insufficient permissions"),
    );
    expect(result.current.state.status).toBe("authenticated");
  });

  it("restricts an ordinary session when password replacement becomes required", async () => {
    const { result } = renderHook(() => useSession(), { wrapper: Wrapper });
    await act(() =>
      result.current.login({
        email: principal.email,
        password: "test password",
      }),
    );
    await act(() =>
      deniedRequest("current-token", 403, "Password change required"),
    );
    expect(result.current.state).toEqual({
      status: "password_change_required",
      accessToken: "current-token",
    });
  });
});
