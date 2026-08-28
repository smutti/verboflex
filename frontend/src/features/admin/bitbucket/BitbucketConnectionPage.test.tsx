import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getAdminBitbucketStatus,
  reconnectAdminBitbucketOauth,
  revokeAdminBitbucketConnectionLocally,
  startAdminBitbucketOauth,
  type AdminBitbucketStatusResponse,
} from "../../../api/client";
import { AdminApplicationRoutes } from "../../../router";
import { BitbucketConnectionPage } from "./BitbucketConnectionPage";

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();

  return {
    ...original,
    getAdminBitbucketStatus: vi.fn(),
    reconnectAdminBitbucketOauth: vi.fn(),
    revokeAdminBitbucketConnectionLocally: vi.fn(),
    startAdminBitbucketOauth: vi.fn(),
  };
});

const getStatusMock = vi.mocked(getAdminBitbucketStatus);
const reconnectMock = vi.mocked(reconnectAdminBitbucketOauth);
const revokeMock = vi.mocked(revokeAdminBitbucketConnectionLocally);
const startMock = vi.mocked(startAdminBitbucketOauth);

const disconnected: AdminBitbucketStatusResponse = {
  connected_at: null,
  expires_at: null,
  revoked_at: "2026-08-28T14:05:59.987654Z",
  status: "Disconnected",
};

const connected: AdminBitbucketStatusResponse = {
  connected_at: "2026-08-28T12:34:56.123456Z",
  expires_at: "2026-09-27T12:34:56.123456Z",
  revoked_at: null,
  scope_label: "Read-only repository access",
  scope_profile: "repository",
  status: "Connected",
};

function ok<T>(data: T, status = 200) {
  return {
    data,
    error: undefined,
    request: new Request("http://localhost/api/v1/admin/bitbucket"),
    response: new Response(null, { status }),
  };
}

function failure(status = 503) {
  return {
    data: undefined,
    error: { detail: "provider_token=secret-provider-body" },
    request: new Request("http://localhost/api/v1/admin/bitbucket"),
    response: new Response(null, { status }),
  };
}

function renderPage(navigateTo: (url: string) => void = vi.fn()) {
  return render(
    <BitbucketConnectionPage
      accessToken="memory-only-admin-bearer"
      navigateTo={navigateTo}
    />,
  );
}

describe("administrator Bitbucket connection page", () => {
  beforeEach(() => {
    getStatusMock.mockReset();
    getStatusMock.mockResolvedValue(ok(disconnected));
    reconnectMock.mockReset();
    revokeMock.mockReset();
    startMock.mockReset();
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders stable loading and bounded retry states without provider diagnostics", async () => {
    getStatusMock.mockReturnValueOnce(new Promise<never>(() => undefined));
    const view = renderPage();

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading Bitbucket connection",
    );
    expect(screen.getByRole("heading", { name: "Bitbucket" })).toBeVisible();
    await waitFor(() => {
      expect(getStatusMock).toHaveBeenCalledTimes(1);
    });

    view.unmount();
    getStatusMock.mockRejectedValueOnce(
      new Error("refresh_token=secret-provider-body"),
    );
    getStatusMock.mockResolvedValueOnce(ok(disconnected));
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "We could not load this page. Retry without leaving the administration area.",
    );
    expect(alert).not.toHaveTextContent("secret-provider-body");
    await userEvent.click(
      screen.getByRole("button", { name: "Retry loading page" }),
    );
    expect(await screen.findByText("Disconnected")).toBeVisible();
  });

  it.each([
    ["Disconnected", disconnected],
    ["Connected", connected],
    [
      "Reauthorization required",
      { ...connected, status: "Reauthorization required" as const },
    ],
    ["Unavailable", { ...connected, status: "Unavailable" as const }],
  ])("projects only the approved %s status", async (label, status) => {
    getStatusMock.mockResolvedValueOnce(ok(status));
    renderPage();

    expect((await screen.findAllByText(label))[0]).toBeVisible();
    const statusPanel = screen.getByRole("region", {
      name: "Bitbucket connection status",
    });
    expect(statusPanel).not.toHaveTextContent("token");
    expect(statusPanel).not.toHaveTextContent("provider");
    expect(statusPanel).not.toHaveTextContent("repository:write");
    if (label === "Connected") {
      expect(statusPanel).toHaveTextContent("Read-only repository access");
      expect(statusPanel).toHaveTextContent("28 Aug 2026, 12:34 UTC");
      expect(statusPanel).toHaveTextContent("27 Sept 2026, 12:34 UTC");
      expect(statusPanel).not.toHaveTextContent("56.123456");
    }
  });

  it("reaches the guarded Bitbucket route", async () => {
    render(
      <MemoryRouter initialEntries={["/admin/bitbucket"]}>
        <Routes>
          <Route
            path="/admin/*"
            element={
              <AdminApplicationRoutes
                accessToken="memory-only-admin-bearer"
                currentUserId="admin-id"
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Disconnected")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Bitbucket" })).toBeVisible();
    expect(getStatusMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
    });
  });

  it.each([
    ["Connect Bitbucket", startMock],
    ["Reconnect Bitbucket", reconnectMock],
  ])(
    "%s uses one generated start operation and same-tab top-level navigation",
    async (actionLabel, operation) => {
      const status =
        actionLabel === "Connect Bitbucket"
          ? disconnected
          : { ...connected, status: "Reauthorization required" as const };
      getStatusMock.mockResolvedValueOnce(ok(status));
      let resolveOperation:
        | ((
            value: ReturnType<
              typeof ok<{
                authorization_url: string;
                state_expires_in: 600;
              }>
            >,
          ) => void)
        | undefined;
      const pendingOperation = new Promise<
        ReturnType<
          typeof ok<{
            authorization_url: string;
            state_expires_in: 600;
          }>
        >
      >((resolve) => {
        resolveOperation = resolve;
      });
      operation.mockReturnValueOnce(pendingOperation as never);
      const navigateTo = vi.fn();
      renderPage(navigateTo);

      const action = await screen.findByRole("button", { name: actionLabel });
      await userEvent.click(action);
      expect(action).toBeDisabled();
      expect(action).toHaveAttribute("aria-busy", "true");
      expect(operation).toHaveBeenCalledTimes(1);

      const authorizationUrl =
        "https://bitbucket.org/site/oauth2/authorize?state=opaque-state&provider_secret=never-render";
      resolveOperation?.(
        ok({ authorization_url: authorizationUrl, state_expires_in: 600 }),
      );
      await waitFor(() => {
        expect(navigateTo).toHaveBeenCalledWith(authorizationUrl);
      });
      expect(document.body).not.toHaveTextContent("opaque-state");
      expect(document.body).not.toHaveTextContent("never-render");
      expect(JSON.stringify(Object.entries(localStorage))).not.toContain(
        authorizationUrl,
      );
      expect(JSON.stringify(Object.entries(sessionStorage))).not.toContain(
        authorizationUrl,
      );
    },
  );

  it("revokes only after named confirmation and keeps server authority on failure", async () => {
    getStatusMock.mockResolvedValueOnce(ok(connected));
    revokeMock
      .mockResolvedValueOnce(failure())
      .mockResolvedValueOnce(ok(disconnected));
    renderPage();

    await userEvent.click(
      await screen.findByRole("button", { name: "Revoke connection" }),
    );
    expect(
      screen.getByRole("heading", {
        name: "Revoke the Bitbucket connection?",
      }),
    ).toBeVisible();
    expect(screen.getByRole("alertdialog")).toHaveTextContent(
      "New branch reads, previews, confirmations, and publications will be blocked until an administrator reconnects.",
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Revoke connection" }),
    );
    expect(await screen.findByText("Connection not revoked")).toBeVisible();
    expect(screen.getAllByText("Connected")[0]).toBeVisible();

    await userEvent.click(
      screen.getByRole("button", { name: "Revoke connection" }),
    );
    expect(await screen.findByText("Disconnected")).toBeVisible();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(revokeMock).toHaveBeenCalledTimes(2);
  });
});
