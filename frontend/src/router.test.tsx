import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  changePassword as generatedChangePassword,
  issueToken,
} from "./api/client";
import { SessionProvider } from "./features/auth/session";
import { AppRouter, SessionRoutes } from "./router";

vi.mock("./api/client", () => ({
  changePassword: vi.fn(),
  issueToken: vi.fn(),
  logout: vi.fn(),
  readCurrentUser: vi.fn(),
  readHealth: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

const issueTokenMock = vi.mocked(issueToken);
const changePasswordMock = vi.mocked(generatedChangePassword);

const ordinaryPrincipal = {
  id: "73f123f7-ebad-4dad-8b5d-dcc3214b3b06",
  email: "person@example.com",
  display_name: "Person",
  roles: ["translator" as const],
  must_change_password: false,
};

const adminPrincipal = {
  ...ordinaryPrincipal,
  roles: ["admin" as const, "translator" as const],
};

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  issueTokenMock.mockReset();
  changePasswordMock.mockReset();
});

function LocationMarker() {
  const location = useLocation();
  return <div data-testid="current-route">{location.pathname}</div>;
}

function renderRoutes(
  state: Parameters<typeof SessionRoutes>[0]["state"],
  initialEntry = "/",
  adminRequest = vi.fn(),
) {
  function AdminRouteProbe() {
    adminRequest();
    return <h1>Users administration route</h1>;
  }

  const routeProps = {
    state,
    loginElement: <h1>Login route</h1>,
    changePasswordElement: <h1>Password change route</h1>,
    ordinaryElement: <h1>Ordinary route</h1>,
    adminElement: <AdminRouteProbe />,
  };

  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <SessionRoutes {...routeProps} />
      <LocationMarker />
    </MemoryRouter>,
  );
}

describe("session routes", () => {
  it("shows the approved session loading state while server authority is checked", () => {
    renderRoutes({ status: "checking_session" });

    expect(screen.getByRole("status")).toHaveTextContent("Checking session");
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });

  it("renders the login route for signed-out authority", () => {
    renderRoutes({ status: "signed_out" }, "/login");

    expect(screen.getByRole("heading", { name: "Login route" })).toBeVisible();
    expect(screen.getByTestId("current-route")).toHaveTextContent("/login");
  });

  it("redirects signed-out direct navigation to login", async () => {
    renderRoutes({ status: "signed_out" }, "/private-route");

    expect(
      await screen.findByRole("heading", { name: "Login route" }),
    ).toBeVisible();
    expect(screen.getByTestId("current-route")).toHaveTextContent("/login");
  });

  it("renders only the password-change route for restricted authority", () => {
    renderRoutes(
      {
        status: "password_change_required",
        accessToken: "restricted-server-token",
      },
      "/change-password",
    );

    expect(
      screen.getByRole("heading", { name: "Password change route" }),
    ).toBeVisible();
    expect(screen.getByTestId("current-route")).toHaveTextContent(
      "/change-password",
    );
  });

  it.each(["/", "/login", "/private-route"])(
    "redirects restricted direct navigation from %s to password change",
    async (initialEntry) => {
      renderRoutes(
        {
          status: "password_change_required",
          accessToken: "restricted-server-token",
        },
        initialEntry,
      );

      expect(
        await screen.findByRole("heading", { name: "Password change route" }),
      ).toBeVisible();
      expect(screen.getByTestId("current-route")).toHaveTextContent(
        "/change-password",
      );
      expect(
        screen.queryByRole("heading", { name: "Ordinary route" }),
      ).not.toBeInTheDocument();
    },
  );

  it("renders the ordinary application route for authenticated authority", () => {
    renderRoutes(
      {
        status: "authenticated",
        accessToken: "ordinary-server-token",
        principal: ordinaryPrincipal,
      },
      "/",
    );

    expect(
      screen.getByRole("heading", { name: "Ordinary route" }),
    ).toBeVisible();
    expect(screen.getByTestId("current-route")).toHaveTextContent("/");
  });

  it.each(["/login", "/change-password", "/private-route"])(
    "redirects authenticated direct navigation from %s to the application",
    async (initialEntry) => {
      renderRoutes(
        {
          status: "authenticated",
          accessToken: "ordinary-server-token",
          principal: ordinaryPrincipal,
        },
        initialEntry,
      );

      expect(
        await screen.findByRole("heading", { name: "Ordinary route" }),
      ).toBeVisible();
      expect(screen.getByTestId("current-route")).toHaveTextContent("/");
      expect(
        screen.queryByRole("heading", { name: "Password change route" }),
      ).not.toBeInTheDocument();
    },
  );

  it("opens the administrator users route only for a server-loaded admin role", () => {
    const adminRequest = vi.fn();

    renderRoutes(
      {
        status: "authenticated",
        accessToken: "admin-server-token",
        principal: adminPrincipal,
      },
      "/admin/users",
      adminRequest,
    );

    expect(
      screen.getByRole("heading", { name: "Users administration route" }),
    ).toBeVisible();
    expect(screen.getByTestId("current-route")).toHaveTextContent(
      "/admin/users",
    );
    expect(adminRequest).toHaveBeenCalledOnce();
  });

  it("denies every direct administrator route before mounting admin requests", async () => {
    const adminRequest = vi.fn();
    const user = userEvent.setup();

    renderRoutes(
      {
        status: "authenticated",
        accessToken: "ordinary-server-token",
        principal: ordinaryPrincipal,
      },
      "/admin/products/private-candidate",
      adminRequest,
    );

    const heading = await screen.findByRole("heading", {
      name: "Administrator access required",
    });
    expect(heading).toHaveFocus();
    expect(
      screen.getByText(
        "Your account does not have permission to open administration.",
      ),
    ).toBeVisible();
    expect(adminRequest).not.toHaveBeenCalled();
    expect(screen.getByTestId("current-route")).toHaveTextContent(
      "/admin/products/private-candidate",
    );

    await user.click(screen.getByRole("link", { name: "Return to workspace" }));
    expect(screen.getByTestId("current-route")).toHaveTextContent("/");
  });

  it("returns a successful required-password change to signed-out login", async () => {
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
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <SessionProvider restoreOnMount={false}>
          <AppRouter />
          <LocationMarker />
        </SessionProvider>
      </MemoryRouter>,
    );

    await user.type(
      screen.getByRole("textbox", { name: "Email" }),
      "person@example.com",
    );
    await user.type(
      screen.getByLabelText("Password"),
      "temporary phrase 2026!",
    );
    await user.click(
      screen.getByRole("button", { name: "Sign in to VerboFlex" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Set a new password" }),
    ).toBeVisible();
    expect(screen.getByTestId("current-route")).toHaveTextContent(
      "/change-password",
    );

    await user.type(
      screen.getByLabelText("Current password"),
      "temporary phrase 2026!",
    );
    await user.type(
      screen.getByLabelText("New password"),
      "replacement phrase 2026!",
    );
    await user.type(
      screen.getByLabelText("Confirm new password"),
      "replacement phrase 2026!",
    );
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    expect(
      await screen.findByRole("heading", { name: "VerboFlex" }),
    ).toBeVisible();
    expect(screen.getByTestId("current-route")).toHaveTextContent("/login");
  });
});
