import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { SessionRoutes } from "./router";

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
    </MemoryRouter>,
  );
}

describe("session routes", () => {
  it("shows the approved session loading state while server authority is checked", () => {
    renderRoutes({ status: "checking_session" });

    expect(screen.getByRole("status")).toHaveTextContent("Checking session");
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });
});
