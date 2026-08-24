import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    expect(screen.queryByText("Checking service status")).not.toBeInTheDocument();
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

    await user.click(
      screen.getByRole("button", { name: "Retry connection" }),
    );

    expect(await screen.findByText("API online")).toBeVisible();
    expect(readSystemStatusMock).toHaveBeenCalledTimes(2);
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
});
