import "@testing-library/jest-dom/vitest";

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  connectAdminBitbucketOauth,
  getAdminBitbucketStatus,
  reconnectAdminBitbucketOauth,
  revokeAdminBitbucketConnectionLocally,
  type AdminBitbucketStatusResponse,
} from "../../../api/client";
import { AdminApplicationRoutes } from "../../../router";
import { BitbucketConnectionPage } from "./BitbucketConnectionPage";

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();

  return {
    ...original,
    connectAdminBitbucketOauth: vi.fn(),
    getAdminBitbucketStatus: vi.fn(),
    reconnectAdminBitbucketOauth: vi.fn(),
    revokeAdminBitbucketConnectionLocally: vi.fn(),
  };
});

const connectMock = vi.mocked(connectAdminBitbucketOauth);
const getStatusMock = vi.mocked(getAdminBitbucketStatus);
const reconnectMock = vi.mocked(reconnectAdminBitbucketOauth);
const revokeMock = vi.mocked(revokeAdminBitbucketConnectionLocally);

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
    error: { detail: "Bitbucket connection unavailable" },
    request: new Request("http://localhost/api/v1/admin/bitbucket"),
    response: new Response(null, { status }),
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

function renderPage() {
  return render(
    <BitbucketConnectionPage accessToken="memory-only-admin-bearer" />,
  );
}

describe("administrator Bitbucket connection page", () => {
  beforeEach(() => {
    getStatusMock.mockReset();
    getStatusMock.mockResolvedValue(ok(disconnected));
    connectMock.mockReset();
    reconnectMock.mockReset();
    revokeMock.mockReset();
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
    getStatusMock.mockRejectedValueOnce(new Error("bounded status failure"));
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

  it("rejects missing status data and ignores an obsolete successful load", async () => {
    getStatusMock.mockResolvedValueOnce(ok(undefined as never));
    const first = renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not load this page",
    );
    first.unmount();

    const obsolete =
      deferred<ReturnType<typeof ok<AdminBitbucketStatusResponse>>>();
    getStatusMock
      .mockReturnValueOnce(obsolete.promise as never)
      .mockResolvedValueOnce(ok(disconnected));
    const view = render(
      <BitbucketConnectionPage accessToken="first-admin-bearer" />,
    );
    await waitFor(() => expect(getStatusMock).toHaveBeenCalledTimes(2));
    view.rerender(
      <BitbucketConnectionPage accessToken="successor-admin-bearer" />,
    );
    await waitFor(() => expect(getStatusMock).toHaveBeenCalledTimes(3));
    expect(await screen.findByText("Disconnected")).toBeVisible();
    obsolete.resolve(ok(connected));
    await waitFor(() => {
      expect(screen.queryByText("Connected")).not.toBeInTheDocument();
      expect(screen.getByText("Disconnected")).toBeVisible();
    });
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
    ["Connect Bitbucket", "connect", connectMock],
    ["Reconnect Bitbucket", "reconnect", reconnectMock],
  ] as const)(
    "%s uses one direct mutation, remains in the SPA, and refetches public status",
    async (actionLabel, actionName, operation) => {
      const status =
        actionLabel === "Connect Bitbucket"
          ? disconnected
          : { ...connected, status: "Reauthorization required" as const };
      getStatusMock
        .mockResolvedValueOnce(ok(status))
        .mockResolvedValueOnce(ok(connected));
      const mutation =
        deferred<ReturnType<typeof ok<AdminBitbucketStatusResponse>>>();
      operation.mockReturnValueOnce(mutation.promise as never);
      const initialLocation = window.location.href;
      const initialHistoryLength = window.history.length;
      renderPage();

      const action = await screen.findByRole("button", { name: actionLabel });
      await userEvent.click(action);
      expect(action).toBeDisabled();
      expect(action).toHaveAttribute("aria-busy", "true");
      expect(operation).toHaveBeenCalledTimes(1);
      expect(
        screen.getByRole("status", { name: "Bitbucket connection mutation" }),
      ).toHaveTextContent(
        actionName === "connect"
          ? "Connecting Bitbucket"
          : "Reconnecting Bitbucket",
      );

      mutation.resolve(ok(connected));
      expect((await screen.findAllByText("Connected"))[0]).toBeVisible();
      await waitFor(() => {
        expect(getStatusMock).toHaveBeenCalledTimes(2);
      });
      expect(
        screen.getByRole("status", { name: "Bitbucket connection mutation" }),
      ).toHaveTextContent(
        actionName === "connect"
          ? "Bitbucket connected"
          : "Bitbucket reconnected",
      );
      const statusPanel = screen.getByRole("region", {
        name: "Bitbucket connection status",
      });
      expect(statusPanel).toHaveTextContent("Read-only repository access");
      expect(statusPanel).toHaveTextContent("27 Sept 2026, 12:34 UTC");
      expect(statusPanel).not.toHaveTextContent("workspace");
      expect(window.location.href).toBe(initialLocation);
      expect(window.history.length).toBe(initialHistoryLength);
      expect(localStorage).toHaveLength(0);
      expect(sessionStorage).toHaveLength(0);
    },
  );

  it("keeps only reconnect pending, announces recovery, and preserves revoke availability", async () => {
    getStatusMock
      .mockResolvedValueOnce(
        ok({ ...connected, status: "Reauthorization required" }),
      )
      .mockResolvedValueOnce(ok(connected));
    const mutation =
      deferred<ReturnType<typeof ok<AdminBitbucketStatusResponse>>>();
    reconnectMock.mockReturnValueOnce(mutation.promise as never);
    renderPage();

    const reconnect = await screen.findByRole("button", {
      name: "Reconnect Bitbucket",
    });
    await userEvent.click(reconnect);

    expect(reconnect).toBeDisabled();
    expect(reconnect).toHaveAttribute("aria-busy", "true");
    expect(
      screen.getByRole("button", { name: "Revoke connection" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("status", { name: "Bitbucket connection mutation" }),
    ).toHaveTextContent("Reconnecting Bitbucket");
    expect(reconnectMock).toHaveBeenCalledTimes(1);

    mutation.resolve(ok(connected));
    expect((await screen.findAllByText("Connected"))[0]).toBeVisible();
    expect(reconnectMock).toHaveBeenCalledTimes(1);
  });

  it("keeps a failed direct recovery on the page with bounded retry guidance", async () => {
    getStatusMock.mockResolvedValueOnce(
      ok({ ...connected, status: "Reauthorization required" }),
    );
    reconnectMock.mockResolvedValueOnce(failure() as never);
    const initialLocation = window.location.href;
    renderPage();

    await userEvent.click(
      await screen.findByRole("button", { name: "Reconnect Bitbucket" }),
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Bitbucket connection unavailable");
    expect(alert).toHaveTextContent(
      "Verify the server configuration, then try again. The current connection status is unchanged.",
    );
    expect(screen.getAllByText("Reauthorization required")[0]).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Reconnect Bitbucket" }),
    ).toBeEnabled();
    expect(reconnectMock).toHaveBeenCalledTimes(1);
    expect(window.location.href).toBe(initialLocation);
    for (const forbidden of [
      "authorization_url",
      "callback",
      "client_secret",
      "ciphertext",
      "refresh_token",
    ]) {
      expect(document.body.innerHTML).not.toContain(forbidden);
      expect(JSON.stringify(window.history.state)).not.toContain(forbidden);
      expect(JSON.stringify(Object.entries(localStorage))).not.toContain(
        forbidden,
      );
      expect(JSON.stringify(Object.entries(sessionStorage))).not.toContain(
        forbidden,
      );
    }
  });

  it("bounds duplicate connection actions and every failure boundary", async () => {
    getStatusMock
      .mockResolvedValueOnce(ok(disconnected))
      .mockResolvedValueOnce(ok(undefined as never));
    const pending =
      deferred<ReturnType<typeof ok<AdminBitbucketStatusResponse>>>();
    connectMock
      .mockReturnValueOnce(pending.promise as never)
      .mockResolvedValueOnce(ok(undefined as never))
      .mockResolvedValueOnce(ok(connected))
      .mockRejectedValueOnce(new Error("bounded connection failure"));
    renderPage();

    const connect = await screen.findByRole("button", {
      name: "Connect Bitbucket",
    });
    act(() => {
      connect.click();
      connect.click();
    });
    expect(connectMock).toHaveBeenCalledTimes(1);
    pending.resolve(ok(undefined as never));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Bitbucket connection unavailable",
    );

    await userEvent.click(connect);
    await waitFor(() => expect(connectMock).toHaveBeenCalledTimes(2));

    await userEvent.click(connect);
    await waitFor(() => expect(getStatusMock).toHaveBeenCalledTimes(2));

    await userEvent.click(connect);
    await waitFor(() => expect(screen.getByRole("alert")).toBeVisible());
    expect(connectMock).toHaveBeenCalledTimes(4);
  });

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
