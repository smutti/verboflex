import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { client } from "../../api/client/client.gen";
import { SessionRoutes } from "../../router";
import { McpConsentPage } from "./McpConsentPage";
import { McpConnectionsPage } from "./McpConnectionsPage";

const originalClientConfig = client.getConfig();
beforeEach(() => {
  client.setConfig({
    baseUrl: "http://localhost",
    fetch: (...args) => globalThis.fetch(...args),
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  client.setConfig(originalClientConfig);
});

it("preserves the authorization request while signed out", () => {
  function Location() {
    const location = useLocation();
    return <p>{location.pathname + location.search}</p>;
  }
  render(
    <MemoryRouter initialEntries={["/mcp/authorize?request=opaque"]}>
      <SessionRoutes
        state={{ status: "signed_out" }}
        loginElement={<Location />}
        changePasswordElement={null}
        ordinaryElement={null}
      />
    </MemoryRouter>,
  );
  expect(screen.getByText("/mcp/authorize?request=opaque")).toBeVisible();
});

it("requires explicit consent and keeps write access unchecked", async () => {
  const request = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        client_name: "Test client",
        redirect_origin: "https://callback.example",
        scopes: ["verboflex:read", "verboflex:write"],
      }),
    )
    .mockResolvedValueOnce(new Response(null, { status: 503 }));
  vi.stubGlobal("fetch", request);
  render(
    <MemoryRouter initialEntries={["/mcp/authorize?request=opaque"]}>
      <McpConsentPage accessToken="ui-token" />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Test client")).toBeVisible();
  expect(screen.getByText("https://callback.example")).toBeVisible();
  expect(screen.getByRole("checkbox")).not.toBeChecked();
  expect(request).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole("button", { name: "Connect" }));
  await screen.findByRole("alert");
  const submitted = request.mock.calls[1][0] as Request;
  expect(submitted.method).toBe("POST");
  expect(submitted.headers.get("Authorization")).toBe("Bearer ui-token");
  expect(await submitted.json()).toEqual({ allow: true, allow_write: false });
});

it("does not offer consent when the authorization request expired", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(null, { status: 404 })),
  );
  render(
    <MemoryRouter initialEntries={["/mcp/authorize?request=expired"]}>
      <McpConsentPage accessToken="ui-token" />
    </MemoryRouter>,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("Request expired");
  expect(
    screen.queryByRole("button", { name: "Connect" }),
  ).not.toBeInTheDocument();
});

it("revokes the selected connection and refreshes the list", async () => {
  const request = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        items: [
          {
            id: "grant",
            client_name: "Codex",
            scopes: ["verboflex:read"],
            expires_at: "2026-10-10T00:00:00Z",
          },
        ],
      }),
    )
    .mockResolvedValueOnce(new Response(null, { status: 204 }))
    .mockResolvedValueOnce(Response.json({ items: [] }));
  vi.stubGlobal("fetch", request);
  render(<McpConnectionsPage accessToken="ui-token" />);
  await screen.findByText("Codex");
  await userEvent.click(screen.getByRole("button", { name: "Revoke access" }));
  await waitFor(() =>
    expect(screen.getByText("No connected apps.")).toBeVisible(),
  );
  const submitted = request.mock.calls[1][0] as Request;
  expect(new URL(submitted.url).pathname).toBe("/api/v1/mcp/connections/grant");
  expect(submitted.method).toBe("DELETE");
  expect(submitted.headers.get("Authorization")).toBe("Bearer ui-token");
});
