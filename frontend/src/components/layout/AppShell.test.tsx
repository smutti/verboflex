import "@testing-library/jest-dom/vitest";

import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { readSystemStatus, type CurrentUserResponse } from "../../api/client";
import { App } from "../../App";
import { useSession } from "../../features/auth/session";
import { AppShell } from "./AppShell";

vi.mock("../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/client")>();
  return {
    ...original,
    readHealth: vi.fn(),
    readSystemStatus: vi.fn(),
  };
});

vi.mock("../../features/auth/session", () => ({
  useSession: vi.fn(),
}));

const readSystemStatusMock = vi.mocked(readSystemStatus);
const useSessionMock = vi.mocked(useSession);
type ReadSystemStatusResult = Awaited<
  ReturnType<typeof readSystemStatus<false>>
>;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

class TestResizeObserver implements ResizeObserver {
  disconnect() {}
  observe() {}
  unobserve() {}
}

Object.defineProperty(globalThis, "ResizeObserver", {
  configurable: true,
  value: TestResizeObserver,
});

function setViewportWidth(width: number) {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: width,
  });
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("max-width") ? width < 768 : width >= 768,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

const principal: CurrentUserResponse = {
  id: "73f123f7-ebad-4dad-8b5d-dcc3214b3b06",
  email: "person@example.com",
  display_name: "Person Example",
  roles: ["admin", "product_manager_reviewer", "translator", "viewer"],
  must_change_password: false,
};

const ordinaryPrincipal: CurrentUserResponse = {
  ...principal,
  roles: ["translator"],
};

function LocationMarker() {
  const location = useLocation();
  return <div data-testid="shell-current-route">{location.pathname}</div>;
}

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  setViewportWidth(1440);
  readSystemStatusMock.mockReset();
  readSystemStatusMock.mockReturnValue(new Promise<never>(() => undefined));
  useSessionMock.mockReset();
});

describe("authenticated application shell", () => {
  it("shows server identity, human role labels, and the approved neutral workspace copy", () => {
    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Workspace overview", level: 1 }),
    ).toBeVisible();
    expect(screen.getByText("Person Example")).toBeVisible();
    expect(screen.getByText("person@example.com")).toBeVisible();
    expect(screen.getByText("Administrator")).toBeVisible();
    expect(screen.getByText("Product manager / reviewer")).toBeVisible();
    expect(screen.getByText("Translator")).toBeVisible();
    expect(screen.getByText("Viewer")).toBeVisible();
    expect(
      screen.getByText(
        "Your review workspace will appear here as products and repositories are configured.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", {
        name: "Workspace ready for configuration",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Phase 1 confirms the platform shell, session, and services. Product and translation workflows will appear after configuration is added.",
      ),
    ).toBeVisible();
  });

  it("announces a bounded loading state while generated service status is pending", () => {
    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking service status",
    );
    expect(readSystemStatusMock).toHaveBeenCalledWith({
      auth: "ordinary-server-token",
    });
  });

  it("renders every server service enum as an explicit text label", async () => {
    readSystemStatusMock.mockResolvedValue({
      data: {
        api: "online",
        database: "online",
        redis: "unavailable",
        worker: "pending",
        checked_at: "2026-08-24T20:10:00Z",
      },
      error: undefined,
    });

    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Service status" }),
    ).toBeVisible();
    expect(screen.getByText("API online")).toBeVisible();
    expect(screen.getByText("Database online")).toBeVisible();
    expect(screen.getByText("Redis unavailable")).toBeVisible();
    expect(screen.getByText("Worker pending")).toBeVisible();
    expect(
      screen.queryByText("Checking service status"),
    ).not.toBeInTheDocument();
  });

  it("sanitizes service failures, never fabricates online, and retries", async () => {
    readSystemStatusMock
      .mockResolvedValueOnce({
        data: undefined,
        error: { detail: "redis://cache.internal:6379/0" },
      })
      .mockResolvedValueOnce({
        data: {
          api: "online",
          database: "online",
          redis: "online",
          worker: "online",
          checked_at: "2026-08-24T20:11:00Z",
        },
        error: undefined,
      });
    const user = userEvent.setup();

    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "We could not reach the API. Check that the backend is running, then retry the connection.",
    );
    expect(alert).not.toHaveTextContent("cache.internal");
    expect(screen.queryByText("API online")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry connection" }));

    expect(await screen.findByText("API online")).toBeVisible();
    expect(readSystemStatusMock).toHaveBeenCalledTimes(2);
  });

  it("sanitizes rejected status requests and keeps a failed retry recoverable", async () => {
    readSystemStatusMock
      .mockRejectedValueOnce(new Error("postgresql://internal-primary"))
      .mockRejectedValueOnce(new Error("redis://internal-cache"));
    const user = userEvent.setup();

    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    const initialAlert = await screen.findByRole("alert");
    expect(initialAlert).toHaveTextContent(
      "We could not reach the API. Check that the backend is running, then retry the connection.",
    );
    expect(initialAlert).not.toHaveTextContent("internal-primary");

    await user.click(screen.getByRole("button", { name: "Retry connection" }));

    const retryAlert = await screen.findByRole("alert");
    expect(retryAlert).toHaveTextContent(
      "We could not reach the API. Check that the backend is running, then retry the connection.",
    );
    expect(retryAlert).not.toHaveTextContent("internal-cache");
    expect(readSystemStatusMock).toHaveBeenCalledTimes(2);
  });

  it("ignores an initial status response superseded by newer authority", async () => {
    const stale = deferred<ReadSystemStatusResult>();
    const current = deferred<ReadSystemStatusResult>();
    readSystemStatusMock
      .mockReturnValueOnce(stale.promise)
      .mockReturnValueOnce(current.promise);
    const view = render(
      <AppShell
        accessToken="superseded-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    view.rerender(
      <AppShell
        accessToken="current-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );
    await act(async () => {
      stale.resolve({
        data: {
          api: "online",
          database: "online",
          redis: "online",
          worker: "online",
          checked_at: "2026-08-24T20:12:00Z",
        },
        error: undefined,
      });
    });

    expect(screen.queryByText("API online")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking service status",
    );

    await act(async () => {
      current.resolve({
        data: {
          api: "online",
          database: "online",
          redis: "pending",
          worker: "online",
          checked_at: "2026-08-24T20:13:00Z",
        },
        error: undefined,
      });
    });
    expect(await screen.findByText("Redis pending")).toBeVisible();
  });

  it("ignores a retry response superseded by a new access token", async () => {
    const staleRetry = deferred<ReadSystemStatusResult>();
    const current = deferred<ReadSystemStatusResult>();
    readSystemStatusMock
      .mockResolvedValueOnce({
        data: undefined,
        error: { detail: "status unavailable" },
      })
      .mockReturnValueOnce(staleRetry.promise)
      .mockReturnValueOnce(current.promise);
    const user = userEvent.setup();
    const view = render(
      <AppShell
        accessToken="retry-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "Retry connection" }),
    );
    view.rerender(
      <AppShell
        accessToken="replacement-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );
    await act(async () => {
      staleRetry.resolve({
        data: {
          api: "online",
          database: "online",
          redis: "unavailable",
          worker: "online",
          checked_at: "2026-08-24T20:14:00Z",
        },
        error: undefined,
      });
    });

    expect(screen.queryByText("Redis unavailable")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking service status",
    );

    await act(async () => {
      current.resolve({
        data: {
          api: "online",
          database: "online",
          redis: "online",
          worker: "pending",
          checked_at: "2026-08-24T20:15:00Z",
        },
        error: undefined,
      });
    });
    expect(await screen.findByText("Worker pending")).toBeVisible();
  });

  it("offers the exact reversible logout action through session authority", async () => {
    const onLogout = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={onLogout}
        principal={principal}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "Sign out of VerboFlex" }),
    );

    expect(onLogout).toHaveBeenCalledOnce();
  });

  it("wires the production ordinary route only from authenticated session data", () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    useSessionMock.mockReturnValue({
      state: {
        status: "authenticated",
        accessToken: "ordinary-server-token",
        principal,
      },
      login: vi.fn(),
      changePassword: vi.fn(),
      restoreSession: vi.fn(),
      logout,
    });

    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Workspace overview" }),
    ).toBeVisible();
    expect(screen.getByText("Person Example")).toBeVisible();
    expect(readSystemStatusMock).toHaveBeenCalledWith({
      auth: "ordinary-server-token",
    });
  });

  it("exposes a quiet desktop navigation landmark with only the current workspace", () => {
    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(navigation).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Workspace overview" }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("button", { name: /product/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /repository/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /review/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /pull request/i })).toBeNull();
  });

  it("opens labelled sheet navigation from the icon control at mobile width", async () => {
    setViewportWidth(375);
    const user = userEvent.setup();
    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    const trigger = screen.getByRole("button", { name: "Open navigation" });
    expect(trigger).toHaveAttribute("aria-label", "Open navigation");

    await user.hover(trigger);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "Open navigation",
    );

    await user.click(trigger);

    const sheet = await screen.findByRole("dialog", { name: "Navigation" });
    expect(
      within(sheet).getByRole("navigation", { name: "Primary navigation" }),
    ).toBeVisible();
    expect(
      within(sheet).getByRole("button", { name: "Workspace overview" }),
    ).toHaveAttribute("aria-current", "page");

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();
    expect(trigger).toHaveFocus();

    await user.keyboard("{Enter}");
    const reopenedSheet = await screen.findByRole("dialog", {
      name: "Navigation",
    });
    expect(screen.queryByRole("tooltip")).toBeNull();
    expect(reopenedSheet.contains(document.activeElement)).toBe(true);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it("shows one desktop Administration group for admins and opens Users", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AppShell
          accessToken="admin-server-token"
          onLogout={vi.fn()}
          principal={principal}
        />
        <LocationMarker />
      </MemoryRouter>,
    );

    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(
      within(navigation).getAllByRole("heading", {
        name: "Administration",
        level: 2,
      }),
    ).toHaveLength(1);

    await user.click(within(navigation).getByRole("link", { name: "Users" }));

    expect(screen.getByTestId("shell-current-route")).toHaveTextContent(
      "/admin/users",
    );
  });

  it("shows the same Administration destination in the mobile Sheet", async () => {
    setViewportWidth(375);
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AppShell
          accessToken="admin-server-token"
          onLogout={vi.fn()}
          principal={principal}
        />
        <LocationMarker />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    const sheet = await screen.findByRole("dialog", { name: "Navigation" });
    const navigation = within(sheet).getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(
      within(navigation).getAllByRole("heading", {
        name: "Administration",
        level: 2,
      }),
    ).toHaveLength(1);

    await user.click(within(navigation).getByRole("link", { name: "Users" }));

    expect(screen.getByTestId("shell-current-route")).toHaveTextContent(
      "/admin/users",
    );
    expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();
  });

  it("omits Administration from desktop and mobile navigation for non-admins", async () => {
    setViewportWidth(375);
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AppShell
          accessToken="ordinary-server-token"
          onLogout={vi.fn()}
          principal={ordinaryPrincipal}
        />
      </MemoryRouter>,
    );

    expect(screen.queryByText("Administration")).toBeNull();
    expect(screen.queryByRole("link", { name: "Users" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    const sheet = await screen.findByRole("dialog", { name: "Navigation" });
    expect(within(sheet).queryByText("Administration")).toBeNull();
    expect(within(sheet).queryByRole("link", { name: "Users" })).toBeNull();
  });
});
