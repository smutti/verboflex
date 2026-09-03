import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getAdminBitbucketStatus,
  listAdminProducts,
  listAdminUsers,
  readSystemStatus,
  type AdminBitbucketCapabilityProfile,
  type CurrentUserResponse,
  type RoleName,
} from "../../api/client";
import { App } from "../../App";
import { useSession } from "../auth/session";
import { WorkspaceOverviewPage } from "./WorkspaceOverviewPage";

vi.mock("../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/client")>();
  return {
    ...original,
    getAdminBitbucketStatus: vi.fn(),
    listAdminProducts: vi.fn(),
    listAdminUsers: vi.fn(),
    readSystemStatus: vi.fn(),
  };
});

vi.mock("../auth/session", () => ({
  useSession: vi.fn(),
}));

const getAdminBitbucketStatusMock = vi.mocked(getAdminBitbucketStatus);
const listAdminProductsMock = vi.mocked(listAdminProducts);
const listAdminUsersMock = vi.mocked(listAdminUsers);
const readSystemStatusMock = vi.mocked(readSystemStatus);
const useSessionMock = vi.mocked(useSession);

const ROLE_LABELS: Record<RoleName, string> = {
  admin: "Administrator",
  product_manager_reviewer: "Product manager / reviewer",
  translator: "Translator",
  viewer: "Viewer",
};

const disconnectedCapabilityProfile: AdminBitbucketCapabilityProfile = {
  evaluated_at: null,
  pull_request: "disconnected",
  source_read: "disconnected",
  source_write: "disconnected",
};

function principalFor(role: RoleName): CurrentUserResponse {
  return {
    id: `principal-${role}`,
    email: `${role.replaceAll("_", "-")}@example.com`,
    display_name: `${ROLE_LABELS[role]} Example`,
    roles: [role],
    must_change_password: false,
  };
}

function authenticateAs(role: RoleName) {
  const principal = principalFor(role);
  useSessionMock.mockReturnValue({
    state: {
      status: "authenticated",
      accessToken: `${role}-server-token`,
      principal,
    },
    login: vi.fn(),
    changePassword: vi.fn(),
    restoreSession: vi.fn(),
    logout: vi.fn(),
  });
  return principal;
}

function renderWorkspace() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
}

function expectNoAdministratorReads() {
  expect(listAdminProductsMock).not.toHaveBeenCalled();
  expect(listAdminUsersMock).not.toHaveBeenCalled();
  expect(getAdminBitbucketStatusMock).not.toHaveBeenCalled();
}

function resolveOrdinaryStatus() {
  readSystemStatusMock.mockResolvedValue({
    data: {
      api: "online",
      checked_at: "2026-08-29T20:00:00Z",
      database: "online",
      redis: "online",
      worker: "online",
    },
    error: undefined,
  });
}

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  getAdminBitbucketStatusMock.mockReset();
  listAdminProductsMock.mockReset();
  listAdminUsersMock.mockReset();
  readSystemStatusMock.mockReset();
  useSessionMock.mockReset();
});

describe("role-aware Workspace overview", () => {
  it.each<RoleName>(["product_manager_reviewer", "translator", "viewer"])(
    "keeps %s on ordinary identity and status operations through error and retry",
    async (role) => {
      const principal = authenticateAs(role);
      readSystemStatusMock
        .mockRejectedValueOnce(new Error("private infrastructure detail"))
        .mockResolvedValueOnce({
          data: {
            api: "online",
            checked_at: "2026-08-29T20:01:00Z",
            database: "online",
            redis: "pending",
            worker: "online",
          },
          error: undefined,
        });
      const user = userEvent.setup();

      renderWorkspace();

      expect(
        screen.getByRole("heading", { name: "Workspace", level: 1 }),
      ).toBeVisible();
      expect(screen.getByText(principal.display_name)).toBeVisible();
      expect(screen.getByText(ROLE_LABELS[role])).toBeVisible();
      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(
        "We could not reach the API. Check that the backend is running, then retry the connection.",
      );
      expect(alert).not.toHaveTextContent("private infrastructure detail");
      expectNoAdministratorReads();

      await user.click(
        screen.getByRole("button", { name: "Retry connection" }),
      );

      expect(await screen.findByText("Redis pending")).toBeVisible();
      expect(readSystemStatusMock).toHaveBeenNthCalledWith(1, {
        auth: `${role}-server-token`,
      });
      expect(readSystemStatusMock).toHaveBeenNthCalledWith(2, {
        auth: `${role}-server-token`,
      });
      expectNoAdministratorReads();
    },
  );

  it("loads exactly three bounded administrator summaries from server authority", async () => {
    const principal = authenticateAs("admin");
    resolveOrdinaryStatus();
    listAdminProductsMock.mockResolvedValue({
      data: {
        items: [
          {
            active_revision: {
              description: null,
              id: "active-revision",
              is_published: true,
              name: "Published product",
              version: 3,
            },
            candidate_revision: null,
            affected_mapping_count: 0,
            id: "published-product",
            is_active: true,
            name: "Published product",
          },
          {
            active_revision: null,
            affected_mapping_count: 0,
            candidate_revision: {
              description: "Draft configuration",
              id: "draft-revision",
              is_published: false,
              name: "Draft product",
              version: 1,
            },
            id: "draft-product",
            is_active: false,
            name: "Draft product",
          },
        ],
        next_cursor: "more-products",
      },
      error: undefined,
    });
    listAdminUsersMock.mockResolvedValue({
      data: {
        items: [
          {
            display_name: "Admin Example",
            email: "admin@example.com",
            id: "admin-user",
            is_active: true,
            must_change_password: false,
            roles: ["admin"],
          },
          {
            display_name: "Viewer Example",
            email: "viewer@example.com",
            id: "viewer-user",
            is_active: true,
            must_change_password: false,
            roles: ["viewer"],
          },
        ],
        next_cursor: null,
      },
      error: undefined,
    });
    getAdminBitbucketStatusMock.mockResolvedValue({
      data: {
        capability_profile: {
          evaluated_at: "2026-08-29T19:00:01Z",
          pull_request: "ready_for_later_phase",
          source_read: "ready",
          source_write: "ready_for_later_phase",
        },
        connected_at: "2026-08-29T19:00:00Z",
        expires_at: "2026-08-29T21:00:00Z",
        revoked_at: null,
        scope_label: "Repository and pull-request access",
        scope_profile: "repository_and_pull_request",
        status: "Connected",
      },
      error: undefined,
    });

    renderWorkspace();

    expect(screen.getByText(principal.display_name)).toBeVisible();
    expect(await screen.findByText("2 loaded products")).toBeVisible();
    expect(screen.getByText("1 loaded draft")).toBeVisible();
    expect(screen.getByText("2 loaded users")).toBeVisible();
    expect(screen.getByText("Connected", { exact: true })).toBeVisible();
    expect(
      screen.getByText("Loaded summaries cover the first bounded page."),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Open Products" })).toHaveAttribute(
      "href",
      "/admin/products",
    );
    expect(screen.getByRole("link", { name: "Open Users" })).toHaveAttribute(
      "href",
      "/admin/users",
    );
    expect(
      screen.getByRole("link", { name: "Open Bitbucket" }),
    ).toHaveAttribute("href", "/admin/bitbucket");
    expect(listAdminProductsMock).toHaveBeenCalledOnce();
    expect(listAdminProductsMock).toHaveBeenCalledWith({
      auth: "admin-server-token",
      query: { cursor: null, limit: 50, status: null },
    });
    expect(listAdminUsersMock).toHaveBeenCalledOnce();
    expect(listAdminUsersMock).toHaveBeenCalledWith({
      auth: "admin-server-token",
      query: { cursor: null, limit: 50 },
    });
    expect(getAdminBitbucketStatusMock).toHaveBeenCalledOnce();
    expect(getAdminBitbucketStatusMock).toHaveBeenCalledWith({
      auth: "admin-server-token",
    });
  });

  it("keeps identity visible while ordinary and administrator reads are loading", () => {
    authenticateAs("admin");
    readSystemStatusMock.mockReturnValue(new Promise<never>(() => undefined));
    listAdminProductsMock.mockReturnValue(new Promise<never>(() => undefined));
    listAdminUsersMock.mockReturnValue(new Promise<never>(() => undefined));
    getAdminBitbucketStatusMock.mockReturnValue(
      new Promise<never>(() => undefined),
    );

    renderWorkspace();

    expect(screen.getByText("Administrator Example")).toBeVisible();
    expect(screen.getByText("Checking service status")).toBeVisible();
    expect(screen.getByText("Loading administrator summaries")).toBeVisible();
  });

  it("keeps identity and bounded recovery when administrator summaries fail", async () => {
    authenticateAs("admin");
    resolveOrdinaryStatus();
    listAdminProductsMock
      .mockRejectedValueOnce(new Error("private product diagnostic"))
      .mockResolvedValueOnce({
        data: { items: [], next_cursor: null },
        error: undefined,
      });
    listAdminUsersMock.mockResolvedValue({
      data: { items: [], next_cursor: null },
      error: undefined,
    });
    getAdminBitbucketStatusMock.mockResolvedValue({
      data: {
        capability_profile: disconnectedCapabilityProfile,
        connected_at: null,
        expires_at: null,
        revoked_at: null,
        status: "Disconnected",
      },
      error: undefined,
    });
    const user = userEvent.setup();

    renderWorkspace();

    expect(screen.getByText("Administrator Example")).toBeVisible();
    const alert = await screen.findByRole("alert", {
      name: "Administrator summaries unavailable",
    });
    expect(alert).toHaveTextContent(
      "We could not load administrator summaries. Your identity and service status remain available.",
    );
    expect(alert).not.toHaveTextContent("private product diagnostic");

    await user.click(
      screen.getByRole("button", { name: "Retry administrator summaries" }),
    );

    expect(await screen.findByText("0 loaded products")).toBeVisible();
    expect(screen.getByText("0 loaded drafts")).toBeVisible();
    expect(screen.getByText("0 loaded users")).toBeVisible();
    expect(screen.getByText("Disconnected", { exact: true })).toBeVisible();
    expect(listAdminProductsMock).toHaveBeenCalledTimes(2);
    expect(listAdminUsersMock).toHaveBeenCalledTimes(2);
    expect(getAdminBitbucketStatusMock).toHaveBeenCalledTimes(2);
  });

  it("uses plain links outside a router and maps incomplete summaries to bounded recovery", async () => {
    const principal = principalFor("admin");
    listAdminProductsMock
      .mockResolvedValueOnce({ data: undefined, error: undefined } as never)
      .mockResolvedValueOnce({
        data: { items: [], next_cursor: null },
        error: undefined,
      });
    listAdminUsersMock.mockResolvedValue({
      data: { items: [], next_cursor: null },
      error: undefined,
    });
    getAdminBitbucketStatusMock.mockResolvedValue({
      data: {
        capability_profile: disconnectedCapabilityProfile,
        connected_at: null,
        expires_at: null,
        revoked_at: null,
        status: "Disconnected",
      },
      error: undefined,
    });
    const user = userEvent.setup();

    render(
      <WorkspaceOverviewPage
        accessToken="direct-admin-token"
        principal={principal}
      />,
    );

    expect(
      await screen.findByText("Administrator summaries unavailable"),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Retry administrator summaries" }),
    );

    expect(await screen.findByText("0 loaded products")).toBeVisible();
    expect(screen.getByRole("link", { name: "Open Products" })).toHaveAttribute(
      "href",
      "/admin/products",
    );
  });

  it("ignores successful summaries superseded by new administrator authority", async () => {
    let resolveOld!: (value: {
      data: { items: never[]; next_cursor: null };
      error: undefined;
    }) => void;
    const oldProducts = new Promise<{
      data: { items: never[]; next_cursor: null };
      error: undefined;
    }>((resolve) => {
      resolveOld = resolve;
    });
    listAdminProductsMock
      .mockReturnValueOnce(oldProducts)
      .mockResolvedValueOnce({
        data: { items: [], next_cursor: null },
        error: undefined,
      });
    listAdminUsersMock.mockResolvedValue({
      data: { items: [], next_cursor: null },
      error: undefined,
    });
    getAdminBitbucketStatusMock.mockResolvedValue({
      data: {
        capability_profile: disconnectedCapabilityProfile,
        connected_at: null,
        expires_at: null,
        revoked_at: null,
        status: "Disconnected",
      },
      error: undefined,
    });
    const first = principalFor("admin");
    const { rerender } = render(
      <WorkspaceOverviewPage accessToken="old-token" principal={first} />,
    );
    await screen.findByText("Loading administrator summaries");

    const successor = { ...first, id: "successor-admin" };
    rerender(
      <WorkspaceOverviewPage
        accessToken="successor-token"
        principal={successor}
      />,
    );
    expect(await screen.findByText("0 loaded products")).toBeVisible();
    resolveOld({ data: { items: [], next_cursor: null }, error: undefined });
    await Promise.resolve();

    expect(
      screen.queryByText("Administrator summaries unavailable"),
    ).toBeNull();
  });

  it("ignores rejected summaries superseded by new administrator authority", async () => {
    let rejectOld!: (reason: Error) => void;
    listAdminProductsMock
      .mockReturnValueOnce(
        new Promise((_resolve, reject) => {
          rejectOld = reject;
        }) as never,
      )
      .mockResolvedValueOnce({
        data: { items: [], next_cursor: null },
        error: undefined,
      });
    listAdminUsersMock.mockResolvedValue({
      data: { items: [], next_cursor: null },
      error: undefined,
    });
    getAdminBitbucketStatusMock.mockResolvedValue({
      data: {
        capability_profile: disconnectedCapabilityProfile,
        connected_at: null,
        expires_at: null,
        revoked_at: null,
        status: "Disconnected",
      },
      error: undefined,
    });
    const principal = principalFor("admin");
    const view = render(
      <WorkspaceOverviewPage accessToken="obsolete" principal={principal} />,
    );
    await screen.findByText("Loading administrator summaries");
    view.rerender(
      <WorkspaceOverviewPage accessToken="successor" principal={principal} />,
    );
    expect(await screen.findByText("0 loaded products")).toBeVisible();
    rejectOld(new Error("stale summary failure"));
    await Promise.resolve();
    expect(
      screen.queryByText("Administrator summaries unavailable"),
    ).toBeNull();
  });
});
