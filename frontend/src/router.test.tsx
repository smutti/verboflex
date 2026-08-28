import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  changePassword as generatedChangePassword,
  issueToken,
  readCurrentUser,
  readSystemStatus,
} from "./api/client";
import { ProductDetailLayout } from "./features/admin/products/ProductDetailLayout";
import { SessionProvider } from "./features/auth/session";
import { AppRouter, SessionRoutes } from "./router";

vi.mock("./api/client", () => ({
  changePassword: vi.fn(),
  issueToken: vi.fn(),
  logout: vi.fn(),
  readCurrentUser: vi.fn(),
  readHealth: vi.fn(),
  readSystemStatus: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

const issueTokenMock = vi.mocked(issueToken);
const changePasswordMock = vi.mocked(generatedChangePassword);
const readCurrentUserMock = vi.mocked(readCurrentUser);
const readSystemStatusMock = vi.mocked(readSystemStatus);

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
  readCurrentUserMock.mockReset();
  readSystemStatusMock.mockReset();
  readSystemStatusMock.mockReturnValue(new Promise<never>(() => undefined));
});

function LocationMarker() {
  const location = useLocation();
  return <div data-testid="current-route">{location.pathname}</div>;
}

function renderRoutes(
  state: Parameters<typeof SessionRoutes>[0]["state"],
  initialEntry = "/",
  adminRequest = vi.fn(),
  adminRouteState?: Parameters<typeof SessionRoutes>[0]["adminRouteState"],
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
    adminRouteState,
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

  it("announces administrator loading without mounting protected content", () => {
    const adminRequest = vi.fn();

    renderRoutes(
      {
        status: "authenticated",
        accessToken: "admin-server-token",
        principal: adminPrincipal,
      },
      "/admin/users",
      adminRequest,
      { status: "loading" },
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading administration page",
    );
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
    expect(
      screen.queryByRole("heading", { name: "Users administration route" }),
    ).not.toBeInTheDocument();
    expect(adminRequest).not.toHaveBeenCalled();
  });

  it("keeps administrator load errors bounded, recoverable, and free of protected content", async () => {
    const adminRequest = vi.fn();
    const retry = vi.fn();
    const user = userEvent.setup();

    renderRoutes(
      {
        status: "authenticated",
        accessToken: "admin-server-token",
        principal: adminPrincipal,
      },
      "/admin/users",
      adminRequest,
      { status: "error", onRetry: retry },
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(
      "We could not load this page. Retry without leaving the administration area.",
    );
    expect(
      screen.queryByRole("heading", { name: "Users administration route" }),
    ).not.toBeInTheDocument();
    expect(adminRequest).not.toHaveBeenCalled();

    await user.click(
      screen.getByRole("button", { name: "Retry loading page" }),
    );
    expect(retry).toHaveBeenCalledOnce();
  });

  it("keeps product navigation URL-backed, ordered, singular, and locally contained", async () => {
    const user = userEvent.setup();
    const longProductName = `Product ${"localization-".repeat(24)}`;

    render(
      <MemoryRouter initialEntries={["/admin/products/product-123/mappings"]}>
        <ProductDetailLayout productName={longProductName}>
          <p>Current product section</p>
        </ProductDetailLayout>
        <LocationMarker />
      </MemoryRouter>,
    );

    const layout = screen.getByTestId("product-detail-layout");
    expect(layout).toHaveClass("min-w-0", "max-w-full", "overflow-x-clip");
    expect(
      screen.getByRole("heading", { name: longProductName, level: 1 }),
    ).toHaveClass("break-words", "[overflow-wrap:anywhere]");

    const navigation = screen.getByRole("navigation", {
      name: "Product configuration",
    });
    expect(
      within(navigation)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Overview", "Repositories", "Mappings", "Preview"]);
    expect(
      within(navigation).getAllByRole("link", { current: "page" }),
    ).toHaveLength(1);
    expect(
      within(navigation).getByRole("link", {
        name: "Mappings",
        current: "page",
      }),
    ).toBeVisible();

    await user.click(within(navigation).getByRole("link", { name: "Preview" }));
    expect(screen.getByTestId("current-route")).toHaveTextContent(
      "/admin/products/product-123/preview",
    );
    expect(
      within(navigation).getAllByRole("link", { current: "page" }),
    ).toHaveLength(1);
    expect(
      within(navigation).getByRole("link", {
        name: "Preview",
        current: "page",
      }),
    ).toBeVisible();
  });

  it("defaults an unknown product section to one Overview current link", () => {
    render(
      <MemoryRouter
        initialEntries={["/admin/products/product-123/unsupported-section"]}
      >
        <ProductDetailLayout />
      </MemoryRouter>,
    );

    const navigation = screen.getByRole("navigation", {
      name: "Product configuration",
    });
    expect(
      within(navigation).getAllByRole("link", { current: "page" }),
    ).toHaveLength(1);
    expect(
      within(navigation).getByRole("link", {
        name: "Overview",
        current: "page",
      }),
    ).toBeVisible();
  });

  it("projects authenticated session authority into the guarded application route", async () => {
    issueTokenMock.mockResolvedValue({
      data: {
        access_token: "admin-server-token",
        expires_in: 300,
        must_change_password: false,
        token_type: "bearer",
      },
      error: undefined,
    });
    readCurrentUserMock.mockResolvedValue({
      data: adminPrincipal,
      error: undefined,
    });
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
      "admin@example.com",
    );
    await user.type(screen.getByLabelText("Password"), "admin phrase 2026!");
    await user.click(
      screen.getByRole("button", { name: "Sign in to VerboFlex" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Workspace overview" }),
    ).toBeVisible();
    await user.click(screen.getByRole("link", { name: "Users" }));
    expect(
      await screen.findByRole("heading", { name: "Users", level: 1 }),
    ).toBeVisible();
    expect(screen.getByTestId("current-route")).toHaveTextContent(
      "/admin/users",
    );
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
