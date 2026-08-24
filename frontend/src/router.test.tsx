import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { SessionRoutes } from "./router";

const ordinaryPrincipal = {
  id: "73f123f7-ebad-4dad-8b5d-dcc3214b3b06",
  email: "person@example.com",
  display_name: "Person",
  roles: ["translator" as const],
  must_change_password: false,
};

afterEach(() => {
  cleanup();
});

function LocationMarker() {
  const location = useLocation();
  return <div data-testid="current-route">{location.pathname}</div>;
}

function renderRoutes(
  state: Parameters<typeof SessionRoutes>[0]["state"],
  initialEntry = "/",
) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <SessionRoutes
        state={state}
        loginElement={<h1>Login route</h1>}
        changePasswordElement={<h1>Password change route</h1>}
        ordinaryElement={<h1>Ordinary route</h1>}
      />
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
});
