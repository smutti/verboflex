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
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createAdminUser,
  listAdminUsers,
  updateAdminUser,
  type AdminUserCredentialResponse,
  type AdminUserResponse,
} from "../../../api/client";
import { UsersPage } from "./UsersPage";

class TestResizeObserver implements ResizeObserver {
  disconnect() {}
  observe() {}
  unobserve() {}
}

vi.stubGlobal("ResizeObserver", TestResizeObserver);
Object.defineProperties(HTMLElement.prototype, {
  hasPointerCapture: {
    configurable: true,
    value: () => false,
  },
  releasePointerCapture: {
    configurable: true,
    value: () => undefined,
  },
  scrollIntoView: {
    configurable: true,
    value: () => undefined,
  },
  setPointerCapture: {
    configurable: true,
    value: () => undefined,
  },
});

vi.mock("../../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api/client")>();

  return {
    ...original,
    createAdminUser: vi.fn(),
    listAdminUsers: vi.fn(),
    updateAdminUser: vi.fn(),
  };
});

const createAdminUserMock = vi.mocked(createAdminUser);
const listAdminUsersMock = vi.mocked(listAdminUsers);
const updateAdminUserMock = vi.mocked(updateAdminUser);

const currentAdmin: AdminUserResponse = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "zulu.admin@example.com",
  display_name: "Zulu Admin",
  is_active: true,
  must_change_password: false,
  roles: ["admin", "viewer"],
};

const translator: AdminUserResponse = {
  id: "00000000-0000-4000-8000-000000000002",
  email: "alpha.translator@example.com",
  display_name: "Alpha Translator",
  is_active: true,
  must_change_password: false,
  roles: ["translator"],
};

const inactiveViewer: AdminUserResponse = {
  id: "00000000-0000-4000-8000-000000000003",
  email: "middle.viewer@example.com",
  display_name: "Middle Viewer",
  is_active: false,
  must_change_password: true,
  roles: ["viewer"],
};

function ok<T>(data: T, status = 200) {
  return {
    data,
    error: undefined,
    request: new Request("http://localhost/api/v1/admin/users"),
    response: new Response(null, { status }),
  };
}

function conflict(detail: string) {
  return {
    data: undefined,
    error: { detail },
    request: new Request("http://localhost/api/v1/admin/users"),
    response: new Response(null, { status: 409 }),
  };
}

function renderUsers() {
  return render(
    <UsersPage
      accessToken="memory-only-admin-bearer"
      currentUserId={currentAdmin.id}
    />,
  );
}

async function openAddDialog() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add user" }));
  return user;
}

async function openEditDialog(userName: string) {
  const user = userEvent.setup();
  const editButtons = await screen.findAllByRole("button", {
    name: `Edit ${userName}`,
  });
  await user.click(editButtons[0]);
  return user;
}

describe("administrator users page tracer", () => {
  beforeEach(() => {
    listAdminUsersMock.mockResolvedValue(
      ok({ items: [currentAdmin, translator], next_cursor: null }),
    );
    createAdminUserMock.mockReset();
    updateAdminUserMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders an approved stable loading state while the first API page is pending", () => {
    listAdminUsersMock.mockReturnValue(new Promise<never>(() => undefined));

    renderUsers();

    expect(screen.getByRole("status")).toHaveTextContent("Loading users");
    expect(screen.getByRole("heading", { name: "Users" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Add user" })).toBeDisabled();
  });

  it.each([
    new Error("Failed to fetch https://api.internal/users?secret=value"),
    new Error("403 administrator only"),
  ])(
    "renders one bounded retryable page error without raw detail",
    async (reason) => {
      listAdminUsersMock.mockRejectedValueOnce(reason);
      renderUsers();

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(
        "We could not load this page. Retry without leaving the administration area.",
      );
      expect(alert).not.toHaveTextContent(reason.message);

      listAdminUsersMock.mockResolvedValueOnce(
        ok({ items: [currentAdmin], next_cursor: null }),
      );
      await userEvent.click(
        screen.getByRole("button", { name: "Retry loading page" }),
      );
      expect(await screen.findAllByText(currentAdmin.email)).toHaveLength(2);
    },
  );

  it("preserves API order and cursor pagination without client re-sorting or de-duplicating", async () => {
    listAdminUsersMock
      .mockResolvedValueOnce(
        ok({ items: [currentAdmin, translator], next_cursor: "next-users" }),
      )
      .mockResolvedValueOnce(
        ok({ items: [inactiveViewer], next_cursor: null }),
      );

    renderUsers();

    const table = await screen.findByRole("table", { name: "Internal users" });
    expect(
      within(table)
        .getAllByRole("row")
        .slice(1)
        .map((row) => row.textContent),
    ).toEqual([
      expect.stringContaining("Zulu Admin"),
      expect.stringContaining("Alpha Translator"),
    ]);
    expect(listAdminUsersMock).toHaveBeenNthCalledWith(1, {
      auth: "memory-only-admin-bearer",
      query: { cursor: null, limit: 50 },
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Load more users" }),
    );

    await waitFor(() => {
      expect(listAdminUsersMock).toHaveBeenNthCalledWith(2, {
        auth: "memory-only-admin-bearer",
        query: { cursor: "next-users", limit: 50 },
      });
      expect(within(table).getByText("Middle Viewer")).toBeVisible();
    });
    expect(
      within(table)
        .getAllByRole("row")
        .slice(1)
        .map((row) => row.textContent),
    ).toEqual([
      expect.stringContaining("Zulu Admin"),
      expect.stringContaining("Alpha Translator"),
      expect.stringContaining("Middle Viewer"),
    ]);
  });

  it("renders filter-empty and populated states with visible lifecycle and role labels", async () => {
    renderUsers();

    const table = await screen.findByRole("table", { name: "Internal users" });
    expect(within(table).getByText("Administrator")).toBeVisible();
    expect(within(table).getByText("Viewer")).toBeVisible();
    expect(within(table).getByText("Translator")).toBeVisible();
    expect(within(table).getAllByText("Active")).toHaveLength(2);

    await userEvent.click(
      screen.getByRole("combobox", { name: "User status" }),
    );
    await userEvent.click(
      screen.getByRole("option", { name: "Inactive users" }),
    );

    expect(
      screen.getByRole("heading", { name: "No users match these filters" }),
    ).toBeVisible();
    expect(
      screen.getByText("Clear the filters to see the full user list."),
    ).toBeVisible();
  });

  it("opens Add user with the fixed role set and enforces a non-empty selection", async () => {
    renderUsers();
    const user = await openAddDialog();

    expect(screen.getByRole("dialog", { name: "Add user" })).toBeVisible();
    expect(
      screen.getByRole("textbox", { name: "Corporate email" }),
    ).toBeEnabled();
    expect(screen.getByRole("textbox", { name: "Display name" })).toBeEnabled();
    expect(
      screen.getByRole("checkbox", { name: "Administrator" }),
    ).not.toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Product manager / reviewer" }),
    ).not.toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Translator" }),
    ).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Viewer" })).toBeChecked();

    await user.type(
      screen.getByRole("textbox", { name: "Corporate email" }),
      "role-check@example.com",
    );
    await user.type(
      screen.getByRole("textbox", { name: "Display name" }),
      "Role Check",
    );
    await user.click(screen.getByRole("checkbox", { name: "Viewer" }));
    await user.click(screen.getByRole("button", { name: "Create user" }));

    expect(screen.getByText("Select at least one role.")).toBeVisible();
    expect(screen.getByRole("group", { name: "Roles" })).toHaveFocus();
    expect(createAdminUserMock).not.toHaveBeenCalled();
  });

  it("prevents duplicate create submission and replaces attempted values only with the backend response", async () => {
    let resolveCreate:
      | ((value: ReturnType<typeof ok<AdminUserCredentialResponse>>) => void)
      | undefined;
    const createdUser: AdminUserResponse = {
      id: "00000000-0000-4000-8000-000000000004",
      email: "canonical@example.com",
      display_name: "Canonical Response",
      is_active: true,
      must_change_password: true,
      roles: ["translator", "viewer"],
    };
    listAdminUsersMock
      .mockResolvedValueOnce(
        ok({ items: [currentAdmin, translator], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        ok({
          items: [translator, createdUser, currentAdmin],
          next_cursor: null,
        }),
      );
    const pendingCreate = new Promise<
      ReturnType<typeof ok<AdminUserCredentialResponse>>
    >((resolve) => {
      resolveCreate = resolve;
    });
    createAdminUserMock.mockReturnValueOnce(pendingCreate);
    renderUsers();
    const user = await openAddDialog();

    await user.type(
      screen.getByRole("textbox", { name: "Corporate email" }),
      "attempted@example.com",
    );
    await user.type(
      screen.getByRole("textbox", { name: "Display name" }),
      "Attempted Name",
    );
    const submit = screen.getByRole("button", { name: "Create user" });
    await user.click(submit);

    await waitFor(() => {
      expect(submit).toBeDisabled();
      expect(submit).toHaveAttribute("aria-busy", "true");
    });
    await user.click(submit);
    expect(createAdminUserMock).toHaveBeenCalledOnce();
    expect(createAdminUserMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        display_name: "Attempted Name",
        email: "attempted@example.com",
        roles: ["viewer"],
      },
    });

    await act(async () => {
      resolveCreate?.(
        ok(
          {
            ...createdUser,
            temporary_password: "shown-in-task-two",
          },
          201,
        ),
      );
    });

    expect(await screen.findAllByText("Canonical Response")).toHaveLength(2);
    expect(screen.getAllByText("canonical@example.com")).toHaveLength(2);
    expect(screen.queryByText("Attempted Name")).not.toBeInTheDocument();
  });

  it("keeps create fields and focuses their owning control on a 409 conflict", async () => {
    createAdminUserMock.mockResolvedValueOnce(
      conflict("normalized corporate email already exists"),
    );
    renderUsers();
    const user = await openAddDialog();
    const email = screen.getByRole("textbox", { name: "Corporate email" });
    const displayName = screen.getByRole("textbox", { name: "Display name" });

    await user.type(email, "duplicate@example.com");
    await user.type(displayName, "Still Here");
    await user.click(screen.getByRole("button", { name: "Create user" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "An account already uses this corporate email.",
    );
    expect(email).toHaveValue("duplicate@example.com");
    expect(displayName).toHaveValue("Still Here");
    expect(email).toHaveFocus();
  });

  it("shows immutable email and prevents the current administrator from unchecking admin", async () => {
    renderUsers();
    await openEditDialog(currentAdmin.display_name);

    expect(
      screen.getByRole("dialog", { name: "Edit Zulu Admin" }),
    ).toBeVisible();
    expect(
      within(screen.getByRole("dialog", { name: "Edit Zulu Admin" })).getByText(
        currentAdmin.email,
      ),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Email cannot be changed. Create a new account to correct it.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("textbox", { name: "Corporate email" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: "Administrator" }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Administrator" }),
    ).toBeDisabled();
    expect(
      screen.getByText("You cannot remove your own administrator role."),
    ).toBeVisible();
  });

  it("updates a row only from the backend response", async () => {
    updateAdminUserMock.mockResolvedValueOnce(
      ok({
        ...translator,
        email: "server-owned@example.com",
        display_name: "Server-owned Name",
        roles: ["product_manager_reviewer"],
      }),
    );
    renderUsers();
    const user = await openEditDialog(translator.display_name);
    const displayName = screen.getByRole("textbox", { name: "Display name" });

    await user.clear(displayName);
    await user.type(displayName, "Attempted Edit");
    await user.click(screen.getByRole("checkbox", { name: "Translator" }));
    await user.click(
      screen.getByRole("checkbox", { name: "Product manager / reviewer" }),
    );
    await user.click(screen.getByRole("button", { name: "Save user" }));

    expect(updateAdminUserMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { user_id: translator.id },
      body: {
        display_name: "Attempted Edit",
        roles: ["product_manager_reviewer"],
      },
    });
    expect(await screen.findAllByText("Server-owned Name")).toHaveLength(2);
    expect(screen.getAllByText("server-owned@example.com")).toHaveLength(2);
    expect(screen.queryByText("Attempted Edit")).not.toBeInTheDocument();
  });

  it("keeps edit fields and focuses the owning alert on a 409 authority conflict", async () => {
    updateAdminUserMock.mockResolvedValueOnce(
      conflict("last active administrator cannot be removed"),
    );
    renderUsers();
    const user = await openEditDialog(translator.display_name);
    const displayName = screen.getByRole("textbox", { name: "Display name" });

    await user.clear(displayName);
    await user.type(displayName, "Preserved Edit");
    await user.click(screen.getByRole("button", { name: "Save user" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "This user changed in another session or the administrator role must be preserved.",
    );
    expect(alert).toHaveFocus();
    expect(displayName).toHaveValue("Preserved Edit");
    expect(
      screen.getByRole("dialog", { name: "Edit Alpha Translator" }),
    ).toBeVisible();
    expect(
      within(
        screen.getByRole("table", { name: "Internal users", hidden: true }),
      ).getByText("Alpha Translator"),
    ).toBeVisible();
  });
});
