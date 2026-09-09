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
import {
  createMemoryRouter,
  MemoryRouter,
  Route,
  RouterProvider,
  Routes,
  useLocation,
} from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getAdminBitbucketStatus,
  listAdminProducts,
  listAdminUsers,
  readSystemStatus,
  type CurrentUserResponse,
} from "../../api/client";
import { App } from "../../App";
import { useSession } from "../../features/auth/session";
import { AppShell } from "./AppShell";
import {
  DirtyFormNavigationProvider,
  useDirtyFormNavigationGuard,
} from "../navigation/DirtyFormNavigationGuard";

vi.mock("../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/client")>();
  return {
    ...original,
    getAdminBitbucketStatus: vi.fn(),
    listAdminProducts: vi.fn(),
    listAdminUsers: vi.fn(),
    readHealth: vi.fn(),
    readSystemStatus: vi.fn(),
  };
});

vi.mock("../../features/auth/session", () => ({
  useSession: vi.fn(),
}));

const getAdminBitbucketStatusMock = vi.mocked(getAdminBitbucketStatus);
const listAdminProductsMock = vi.mocked(listAdminProducts);
const listAdminUsersMock = vi.mocked(listAdminUsers);
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

function DirtyMobileShell() {
  useDirtyFormNavigationGuard("mobile-shell-probe", true);
  return (
    <AppShell
      accessToken="admin-server-token"
      onLogout={vi.fn()}
      principal={principal}
    >
      <LocationMarker />
    </AppShell>
  );
}

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  setViewportWidth(1440);
  getAdminBitbucketStatusMock.mockReset();
  getAdminBitbucketStatusMock.mockReturnValue(
    new Promise<never>(() => undefined),
  );
  listAdminProductsMock.mockReset();
  listAdminProductsMock.mockReturnValue(new Promise<never>(() => undefined));
  listAdminUsersMock.mockReset();
  listAdminUsersMock.mockReturnValue(new Promise<never>(() => undefined));
  readSystemStatusMock.mockReset();
  readSystemStatusMock.mockReturnValue(new Promise<never>(() => undefined));
  useSessionMock.mockReset();
});

describe("authenticated application shell", () => {
  it("moves server identity and roles into a user menu beside logout", async () => {
    const user = userEvent.setup();
    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Home", level: 1 }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Signed-in identity" }),
    ).toBeNull();
    expect(screen.queryByText("person@example.com")).toBeNull();
    expect(
      screen.getByText(
        "Monitor VerboFlex services and review the current project portfolio.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Project statistics" }),
    ).toBeVisible();
    const userMenuTrigger = screen.getByRole("button", {
      name: "Open user menu for Person Example",
    });
    const logout = screen.getByRole("button", {
      name: "Sign out of VerboFlex",
    });
    expect(
      userMenuTrigger.compareDocumentPosition(logout) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    await user.click(userMenuTrigger);

    const menu = screen.getByRole("menu");
    expect(within(menu).getByText("Person Example")).toBeVisible();
    expect(within(menu).getByText("person@example.com")).toBeVisible();
    expect(within(menu).getByText("Administrator")).toBeVisible();
    expect(within(menu).getByText("Product manager / reviewer")).toBeVisible();
    expect(within(menu).getByText("Translator")).toBeVisible();
    expect(within(menu).getByText("Viewer")).toBeVisible();
    expect(
      within(menu).getByRole("menuitem", { name: "Profile" }),
    ).toHaveAttribute("href", "/profile");
  });

  it("announces a bounded loading state while generated service status is pending", () => {
    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    expect(screen.getByText("Checking service status")).toBeVisible();
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
    expect(screen.getByText("Checking service status")).toBeVisible();

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
    expect(screen.getByText("Checking service status")).toBeVisible();

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

    expect(screen.getByRole("heading", { name: "Home" })).toBeVisible();
    expect(screen.getByText("Person Example")).toBeVisible();
    expect(readSystemStatusMock).toHaveBeenCalledWith({
      auth: "ordinary-server-token",
    });
  });

  it("exposes a quiet desktop primary navigation landmark", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppShell
          accessToken="ordinary-server-token"
          onLogout={vi.fn()}
          principal={ordinaryPrincipal}
        />
      </MemoryRouter>,
    );

    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(navigation).toBeVisible();
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.queryByRole("button", { name: /product/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /repository/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /review/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /pull request/i })).toBeNull();
  });

  it("opens labelled sheet navigation from the icon control at mobile width", async () => {
    setViewportWidth(375);
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppShell
          accessToken="ordinary-server-token"
          onLogout={vi.fn()}
          principal={ordinaryPrincipal}
        />
      </MemoryRouter>,
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
    expect(within(sheet).getByRole("link", { name: "Home" })).toHaveAttribute(
      "aria-current",
      "page",
    );

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
    expect(
      within(navigation)
        .getAllByRole("link")
        .map((link) => link.textContent?.trim()),
    ).toEqual([
      "Home",
      "Product workspace",
      "All translations",
      "Product configuration",
      "Users",
      "Bitbucket",
    ]);

    await user.click(within(navigation).getByRole("link", { name: "Users" }));

    expect(screen.getByTestId("shell-current-route")).toHaveTextContent(
      "/admin/users",
    );
    expect(
      within(navigation).getByRole("link", {
        name: "Users",
        current: "page",
      }),
    ).toBeVisible();
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

    const trigger = screen.getByRole("button", { name: "Open navigation" });
    await user.click(trigger);
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
    expect(sheet).toHaveClass(
      "max-w-[calc(100vw-32px)]",
      "motion-reduce:animate-none",
      "motion-reduce:transition-none",
    );

    await user.click(
      within(navigation).getByRole("link", { name: "Product configuration" }),
    );

    expect(screen.getByTestId("shell-current-route")).toHaveTextContent(
      "/admin/products",
    );
    expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it("keeps a blocked mobile destination mounted for cancel focus and closes after discard", async () => {
    setViewportWidth(320);
    const router = createMemoryRouter(
      [
        {
          path: "*",
          element: (
            <DirtyFormNavigationProvider>
              <DirtyMobileShell />
            </DirtyFormNavigationProvider>
          ),
        },
      ],
      { initialEntries: ["/admin/users"] },
    );
    render(<RouterProvider router={router} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    const sheet = await screen.findByRole("dialog", { name: "Navigation" });
    const productsLink = within(sheet).getByRole("link", {
      name: "Product configuration",
    });
    await user.click(productsLink);

    expect(
      await screen.findByRole("alertdialog", { name: "Leave without saving?" }),
    ).toBeVisible();
    expect(
      document.querySelector('[data-slot="sheet-content"][data-state="open"]'),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/admin/users");
    await user.click(screen.getByRole("button", { name: "Keep editing" }));
    await waitFor(() => expect(productsLink).toHaveFocus());

    await user.click(productsLink);
    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/admin/products"),
    );
    expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();
  });

  it.each([
    ["/", "Home"],
    ["/products", "Product workspace"],
    ["/products/product-123/strings", "Product workspace"],
    ["/translations", "All translations"],
    ["/translations/group-123", "All translations"],
    ["/admin/products", "Product configuration"],
    ["/admin/products/product-123/preview", "Product configuration"],
    ["/admin/users", "Users"],
    ["/admin/bitbucket", "Bitbucket"],
  ])("marks only %s as the current primary destination", (path, label) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <AppShell
          accessToken="admin-server-token"
          onLogout={vi.fn()}
          principal={principal}
        >
          <h1>Current destination</h1>
        </AppShell>
      </MemoryRouter>,
    );

    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    const currentLinks = within(navigation).getAllByRole("link", {
      current: "page",
    });
    expect(currentLinks).toHaveLength(1);
    expect(currentLinks[0]).toHaveAccessibleName(label);
  });

  it("carries the selected product color into the primary navigation", () => {
    render(
      <MemoryRouter initialEntries={["/products/product-123/strings"]}>
        <AppShell
          accessToken="ordinary-server-token"
          onLogout={vi.fn()}
          principal={ordinaryPrincipal}
        >
          <h1>Product strings</h1>
        </AppShell>
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", {
      name: "Product workspace",
      current: "page",
    });
    expect(link.style.backgroundColor).not.toBe("");
    expect(link.style.borderLeftColor).not.toBe("");
    expect(link.style.color).not.toBe("");
  });

  it("closes mobile navigation and focuses the Home heading after selection", async () => {
    setViewportWidth(320);
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/admin/users"]}>
        <Routes>
          <Route
            path="/"
            element={
              <AppShell
                accessToken="admin-server-token"
                onLogout={vi.fn()}
                principal={principal}
              />
            }
          />
          <Route
            path="/admin/*"
            element={
              <AppShell
                accessToken="admin-server-token"
                onLogout={vi.fn()}
                principal={principal}
              >
                <h1>Users</h1>
              </AppShell>
            }
          />
        </Routes>
        <LocationMarker />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    const sheet = await screen.findByRole("dialog", { name: "Navigation" });
    expect(
      within(sheet).getAllByRole("link", { current: "page" }),
    ).toHaveLength(1);
    expect(
      within(sheet).getByRole("link", { name: "Users", current: "page" }),
    ).toBeVisible();

    await user.click(within(sheet).getByRole("link", { name: "Home" }));

    expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();
    expect(screen.getByTestId("shell-current-route")).toHaveTextContent("/");
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Home", level: 1 }),
      ).toHaveFocus();
    });
  });

  it("freezes the 320, 768, 1024, and wide shell containment contracts", () => {
    render(
      <MemoryRouter initialEntries={["/admin/products/product-123/mappings"]}>
        <AppShell
          accessToken="admin-server-token"
          onLogout={vi.fn()}
          principal={principal}
        >
          <h1 className="break-words [overflow-wrap:anywhere]">
            {"A-long-administration-label-".repeat(16)}
          </h1>
        </AppShell>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("app-shell")).toHaveClass(
      "min-w-0",
      "max-w-full",
      "overflow-x-clip",
    );
    expect(screen.getByTestId("app-shell-content")).toHaveClass(
      "min-w-0",
      "max-w-full",
      "px-(--space-lg)",
      "md:px-(--space-xl)",
    );
    expect(screen.getByTestId("desktop-navigation")).toHaveClass(
      "hidden",
      "lg:flex",
    );
    expect(screen.getByRole("button", { name: "Open navigation" })).toHaveClass(
      "lg:hidden",
    );

    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(
      within(navigation).getAllByRole("link", { current: "page" }),
    ).toHaveLength(1);
    expect(
      within(navigation).getByRole("link", {
        name: "Product configuration",
        current: "page",
      }),
    ).toBeVisible();

    for (const name of [
      "Product workspace",
      "All translations",
      "Product configuration",
      "Users",
      "Bitbucket",
    ]) {
      expect(screen.getByRole("link", { name })).toHaveClass(
        "min-w-0",
        "max-w-full",
      );
    }
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

  it.each<CurrentUserResponse["roles"][number]>([
    "admin",
    "product_manager_reviewer",
    "translator",
    "viewer",
  ])(
    "places accessible product and translation destinations after Workspace for %s",
    async (role) => {
      const user = userEvent.setup();
      render(
        <MemoryRouter>
          <AppShell
            accessToken="token"
            onLogout={vi.fn()}
            principal={{ ...principal, roles: [role] }}
          />
          <LocationMarker />
        </MemoryRouter>,
      );
      const navigation = screen.getByRole("navigation", {
        name: "Primary navigation",
      });
      const links = within(navigation).getAllByRole("link");
      expect(links.slice(0, 3).map((link) => link.textContent?.trim())).toEqual(
        ["Home", "Product workspace", "All translations"],
      );
      const translations = within(navigation).getByRole("link", {
        name: "All translations",
      });
      expect(translations).toHaveAttribute("href", "/translations");
      expect(translations).not.toHaveAttribute("aria-current");
      expect(translations).toHaveClass(
        "focus-visible:ring-[3px]",
        "min-h-[44px]",
        "min-w-0",
        "max-w-full",
        "whitespace-normal",
      );
      expect(translations.querySelector("svg")).toHaveAttribute(
        "aria-hidden",
        "true",
      );
      links[0].focus();
      await user.tab();
      expect(
        within(navigation).getByRole("link", { name: "Product workspace" }),
      ).toHaveFocus();
      await user.tab();
      expect(translations).toHaveFocus();
      await user.keyboard("{Enter}");
      expect(screen.getByTestId("shell-current-route")).toHaveTextContent(
        "/translations",
      );
      expect(translations).toHaveAttribute("aria-current", "page");
    },
  );

  it.each([320, 768, 1024])(
    "selects All translations from the collapsed Sheet at %ipx and restores trigger focus",
    async (width) => {
      setViewportWidth(width);
      const user = userEvent.setup();
      render(
        <MemoryRouter>
          <AppShell
            accessToken="token"
            onLogout={vi.fn()}
            principal={ordinaryPrincipal}
          />
          <LocationMarker />
        </MemoryRouter>,
      );
      const trigger = screen.getByRole("button", { name: "Open navigation" });
      await user.click(trigger);
      const sheet = await screen.findByRole("dialog", { name: "Navigation" });
      const navigation = within(sheet).getByRole("navigation", {
        name: "Primary navigation",
      });
      expect(
        within(navigation)
          .getAllByRole("link")
          .map((link) => link.textContent?.trim()),
      ).toEqual(["Home", "Product workspace", "All translations"]);
      const translations = within(navigation).getByRole("link", {
        name: "All translations",
      });
      translations.focus();
      await user.keyboard("{Enter}");
      expect(screen.getByTestId("shell-current-route")).toHaveTextContent(
        "/translations",
      );
      expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();
      expect(trigger).toHaveFocus();
      await user.keyboard("{Enter}");
      const reopened = await screen.findByRole("dialog", {
        name: "Navigation",
      });
      expect(
        within(reopened).getByRole("link", {
          name: "All translations",
          current: "page",
        }),
      ).toBeVisible();
    },
  );

  it("does not mark a similarly prefixed route as All translations", () => {
    render(
      <MemoryRouter initialEntries={["/translations-other"]}>
        <AppShell
          accessToken="token"
          onLogout={vi.fn()}
          principal={ordinaryPrincipal}
        />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("link", { name: "All translations" }),
    ).not.toHaveAttribute("aria-current");
  });
});
