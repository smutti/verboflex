import "@testing-library/jest-dom/vitest";

import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
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
  capability_profile: {
    evaluated_at: null,
    pull_request: "disconnected",
    source_read: "disconnected",
    source_write: "disconnected",
  },
  connected_at: null,
  expires_at: null,
  revoked_at: "2026-08-28T14:05:59.987654Z",
  status: "Disconnected",
};

const connected: AdminBitbucketStatusResponse = {
  capability_profile: {
    evaluated_at: "2026-08-28T12:35:01.123456Z",
    pull_request: "ready_for_later_phase",
    source_read: "ready",
    source_write: "ready_for_later_phase",
  },
  connected_at: "2026-08-28T12:34:56.123456Z",
  expires_at: "2026-09-27T12:34:56.123456Z",
  revoked_at: null,
  scope_label: "Repository and pull-request access",
  scope_profile: "repository_and_pull_request",
  status: "Connected",
};

const reauthorizationRequired: AdminBitbucketStatusResponse = {
  ...connected,
  capability_profile: {
    evaluated_at: "2026-08-28T12:35:01.123456Z",
    pull_request: "reauthorization_required",
    source_read: "reauthorization_required",
    source_write: "reauthorization_required",
  },
  scope_label: undefined,
  scope_profile: undefined,
  status: "Reauthorization required",
};

const mixedReadiness: AdminBitbucketStatusResponse = {
  ...connected,
  capability_profile: {
    evaluated_at: "2026-08-28T12:35:01.123456Z",
    pull_request: "unavailable",
    source_read: "ready",
    source_write: "reauthorization_required",
  },
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

function capabilityRow(profile: HTMLElement, label: string) {
  return within(profile).getByRole("group", { name: label });
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

  it("UI3-C05 renders geometry-matched capability Skeletons during initial load", async () => {
    getStatusMock.mockReturnValueOnce(new Promise<never>(() => undefined));
    const view = renderPage();

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading Bitbucket connection",
    );
    expect(screen.getByRole("heading", { name: "Bitbucket" })).toBeVisible();
    const loadingProfile = screen.getByRole("region", {
      name: "Capability profile",
    });
    expect(
      within(loadingProfile).getAllByLabelText("Loading capability readiness"),
    ).toHaveLength(3);
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
    expect((await screen.findAllByText("Disconnected"))[0]).toBeVisible();
  });

  it("UI3-C01 keeps every capability row present with a named disconnected state", async () => {
    getStatusMock.mockResolvedValueOnce(ok(disconnected));
    renderPage();

    await screen.findByRole("button", { name: "Connect Bitbucket" });
    const profile = screen.getByRole("region", {
      name: "Capability profile",
    });
    for (const label of [
      "Read localization sources",
      "Create branches and source commits",
      "Open pull requests",
    ]) {
      expect(capabilityRow(profile, label)).toHaveTextContent("Disconnected");
    }
  });

  it("UI3-C13 renders exactly three server-ordered capability rows with text-first readiness", async () => {
    getStatusMock.mockResolvedValueOnce(ok(connected));
    renderPage();

    await screen.findByText("Repository and pull-request access");
    const profile = screen.getByRole("region", {
      name: "Capability profile",
    });
    expect(
      Array.from(profile.querySelectorAll("dt"), (term) => term.textContent),
    ).toEqual([
      "Read localization sources",
      "Create branches and source commits",
      "Open pull requests",
    ]);
    expect(
      capabilityRow(profile, "Read localization sources"),
    ).toHaveTextContent("Ready");
    for (const label of [
      "Create branches and source commits",
      "Open pull requests",
    ]) {
      const row = capabilityRow(profile, label);
      expect(row).toHaveTextContent("Ready for a later phase");
      expect(row).toHaveTextContent("Not used during imports.");
    }
    expect(
      screen.getByText("Repository and pull-request access"),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", {
        name: /create branch|create commit|open pull request/i,
      }),
    ).not.toBeInTheDocument();
  });

  it("UI3-C17 keeps mixed server-projected readiness visible without client inference", async () => {
    getStatusMock.mockResolvedValueOnce(ok(mixedReadiness));
    renderPage();

    await screen.findByRole("button", { name: "Revoke connection" });
    const profile = screen.getByRole("region", {
      name: "Capability profile",
    });
    expect(
      capabilityRow(profile, "Read localization sources"),
    ).toHaveTextContent("Ready");
    expect(
      capabilityRow(profile, "Create branches and source commits"),
    ).toHaveTextContent("Reauthorization required");
    expect(capabilityRow(profile, "Open pull requests")).toHaveTextContent(
      "Unavailable",
    );
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
    expect((await screen.findAllByText("Disconnected"))[0]).toBeVisible();
    obsolete.resolve(ok(connected));
    await waitFor(() => {
      expect(screen.queryByText("Connected")).not.toBeInTheDocument();
      expect(screen.getAllByText("Disconnected")[0]).toBeVisible();
    });
  });

  it.each([
    ["Disconnected", disconnected],
    ["Connected", connected],
    ["Reauthorization required", reauthorizationRequired],
    [
      "Unavailable",
      {
        ...mixedReadiness,
        capability_profile: {
          ...mixedReadiness.capability_profile,
          source_read: "unavailable" as const,
        },
        status: "Unavailable" as const,
      },
    ],
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
      expect(statusPanel).toHaveTextContent(
        "Repository and pull-request access",
      );
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

    expect((await screen.findAllByText("Disconnected"))[0]).toBeVisible();
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
          : reauthorizationRequired;
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
      expect(statusPanel).toHaveTextContent(
        "Repository and pull-request access",
      );
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
      .mockResolvedValueOnce(ok(reauthorizationRequired))
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

  it("UI3-C10 keeps capability failure in-region and preserves the prior visible profile", async () => {
    getStatusMock.mockResolvedValueOnce(ok(reauthorizationRequired));
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
    const profile = screen.getByRole("region", { name: "Capability profile" });
    for (const label of [
      "Read localization sources",
      "Create branches and source commits",
      "Open pull requests",
    ]) {
      expect(capabilityRow(profile, label)).toHaveTextContent(
        "Reauthorization required",
      );
    }
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
      "New imports, branch reads, previews, confirmations, and publications will be blocked until an administrator reconnects. Existing successful baselines remain recorded.",
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Revoke connection" }),
    );
    expect(await screen.findByText("Connection not revoked")).toBeVisible();
    expect(screen.getAllByText("Connected")[0]).toBeVisible();

    await userEvent.click(
      screen.getByRole("button", { name: "Revoke connection" }),
    );
    expect((await screen.findAllByText("Disconnected"))[0]).toBeVisible();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(revokeMock).toHaveBeenCalledTimes(2);
  });
});
