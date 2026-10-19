import "@testing-library/jest-dom/vitest";

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createAdminUser,
  deactivateAdminUser,
  listAdminUsers,
  listAdminProducts,
  listAdminUserProducts,
  reactivateAdminUser,
  resetAdminUserPassword,
  updateAdminUser,
  type AdminUserCredentialResponse,
  type AdminUserResponse,
  type AdminProductResponse,
  type AdminUserProductAccess,
} from "../../../api/client";
import { TemporaryPasswordDialog } from "./TemporaryPasswordDialog";
import { UserDialog } from "./UserDialog";
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
    deactivateAdminUser: vi.fn(),
    listAdminUsers: vi.fn(),
    listAdminProducts: vi.fn(),
    listAdminUserProducts: vi.fn(),
    reactivateAdminUser: vi.fn(),
    resetAdminUserPassword: vi.fn(),
    updateAdminUser: vi.fn(),
  };
});

const createAdminUserMock = vi.mocked(createAdminUser);
const deactivateAdminUserMock = vi.mocked(deactivateAdminUser);
const listAdminUsersMock = vi.mocked(listAdminUsers);
const listAdminProductsMock = vi.mocked(listAdminProducts);
const listAdminUserProductsMock = vi.mocked(listAdminUserProducts);
const reactivateAdminUserMock = vi.mocked(reactivateAdminUser);
const resetAdminUserPasswordMock = vi.mocked(resetAdminUserPassword);
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

const productAlpha: AdminProductResponse = {
  id: "00000000-0000-4000-8000-000000000010",
  name: "Synthetic Alpha",
  is_active: true,
  affected_mapping_count: 0,
  active_revision: null,
  candidate_revision: null,
};
const productBeta: AdminProductResponse = {
  ...productAlpha,
  id: "00000000-0000-4000-8000-000000000011",
  name: "Synthetic Beta",
};
const assignedAlpha: AdminUserProductAccess = {
  product_id: productAlpha.id,
  name: productAlpha.name,
  is_active: true,
  role: "translator",
  version: "00000000-0000-4000-8000-000000000101",
};
const assignedBeta: AdminUserProductAccess = {
  ...assignedAlpha,
  product_id: productBeta.id,
  name: productBeta.name,
  role: "product_owner",
  version: "00000000-0000-4000-8000-000000000102",
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

function failure(status = 503) {
  return {
    data: undefined,
    error: { detail: "bounded test failure" },
    request: new Request("http://localhost/api/v1/admin/users"),
    response: new Response(null, { status }),
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

async function chooseRowAction(userName: string, actionName: string) {
  const user = userEvent.setup();
  const table = await screen.findByRole("table", { name: "Internal users" });
  const row = within(table).getByRole("row", {
    name: new RegExp(userName, "i"),
  });
  await user.click(
    within(row).getByRole("button", {
      name: `More actions for ${userName}`,
    }),
  );
  await user.click(await screen.findByRole("menuitem", { name: actionName }));
  return user;
}

describe("administrator users page tracer", () => {
  beforeEach(() => {
    listAdminUserProductsMock.mockReset();
    listAdminUserProductsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    listAdminProductsMock.mockReset();
    listAdminProductsMock.mockResolvedValue(
      ok({ items: [], next_cursor: null }),
    );
    listAdminUsersMock.mockReset();
    listAdminUsersMock.mockResolvedValue(
      ok({ items: [currentAdmin, translator], next_cursor: null }),
    );
    createAdminUserMock.mockReset();
    deactivateAdminUserMock.mockReset();
    reactivateAdminUserMock.mockReset();
    resetAdminUserPasswordMock.mockReset();
    updateAdminUserMock.mockReset();
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("creates an account with independent product roles and allows clearing an assignment", async () => {
    listAdminProductsMock.mockResolvedValue(
      ok({ items: [productAlpha, productBeta], next_cursor: null }),
    );
    const created = {
      ...translator,
      email: "created@example.com",
      temporary_password: "synthetic-temporary-password!",
    };
    createAdminUserMock.mockResolvedValue(ok(created, 201));
    renderUsers();
    const user = await openAddDialog();
    const alpha = await screen.findByRole("combobox", {
      name: productAlpha.name,
    });
    const beta = screen.getByRole("combobox", { name: productBeta.name });
    expect(alpha).toHaveValue("none");
    expect(beta).toHaveValue("none");
    await user.selectOptions(alpha, "translator");
    await user.selectOptions(beta, "product_manager_reviewer");
    await user.selectOptions(beta, "none");
    expect(beta).toHaveValue("none");
    await user.selectOptions(beta, "product_owner");
    await user.type(
      screen.getByRole("textbox", { name: "Corporate email" }),
      created.email,
    );
    await user.type(
      screen.getByRole("textbox", { name: "Display name" }),
      "New Person",
    );
    await user.click(screen.getByRole("button", { name: "Create user" }));
    expect(createAdminUserMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        email: created.email,
        display_name: "New Person",
        roles: ["viewer"],
        product_assignments: [
          { product_id: productAlpha.id, role: "translator" },
          { product_id: productBeta.id, role: "product_owner" },
        ],
      },
    });
    expect(
      await screen.findByRole("dialog", { name: "Temporary password created" }),
    ).toHaveTextContent(created.temporary_password);
  });

  it("preserves product choices across pagination failures and retry", async () => {
    listAdminProductsMock
      .mockResolvedValueOnce(
        ok({ items: [productAlpha], next_cursor: "next-products" }),
      )
      .mockRejectedValueOnce(new Error("synthetic failure"))
      .mockResolvedValueOnce(ok({ items: [productBeta], next_cursor: null }));
    renderUsers();
    const user = await openAddDialog();
    const alpha = await screen.findByRole("combobox", {
      name: productAlpha.name,
    });
    await user.selectOptions(alpha, "viewer");
    await user.click(
      screen.getByRole("button", { name: "Load more products" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your selections are still here",
    );
    expect(alpha).toHaveValue("viewer");
    await user.click(
      screen.getByRole("button", { name: "Retry loading more products" }),
    );
    expect(
      await screen.findByRole("combobox", { name: productBeta.name }),
    ).toHaveValue("none");
    expect(alpha).toHaveValue("viewer");
    expect(listAdminProductsMock).toHaveBeenLastCalledWith({
      auth: "memory-only-admin-bearer",
      query: { cursor: "next-products", limit: 50, status: "active" },
      signal: expect.any(AbortSignal),
    });
  });

  it("keeps fields and roles when a selected product becomes unavailable", async () => {
    listAdminProductsMock.mockResolvedValue(
      ok({ items: [productAlpha], next_cursor: null }),
    );
    createAdminUserMock.mockResolvedValue({
      ...failure(422),
      error: { detail: "Selected products unavailable" },
    });
    renderUsers();
    const user = await openAddDialog();
    const alpha = await screen.findByRole("combobox", {
      name: productAlpha.name,
    });
    await user.selectOptions(alpha, "product_manager_reviewer");
    await user.type(
      screen.getByRole("textbox", { name: "Corporate email" }),
      "new@example.com",
    );
    await user.type(
      screen.getByRole("textbox", { name: "Display name" }),
      "New Person",
    );
    await user.click(screen.getByRole("button", { name: "Create user" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No account was created",
    );
    expect(screen.getByRole("alert")).toHaveFocus();
    expect(alpha).toHaveValue("product_manager_reviewer");
    expect(
      screen.getByRole("textbox", { name: "Corporate email" }),
    ).toHaveValue("new@example.com");
    expect(screen.getByRole("textbox", { name: "Display name" })).toHaveValue(
      "New Person",
    );
    expect(
      screen.queryByText("An account already uses this corporate email."),
    ).not.toBeInTheDocument();
    await user.selectOptions(alpha, "none");
    await user.click(screen.getByRole("button", { name: "Create user" }));
    expect(createAdminUserMock).toHaveBeenLastCalledWith({
      auth: "memory-only-admin-bearer",
      body: {
        email: "new@example.com",
        display_name: "New Person",
        roles: ["viewer"],
      },
    });
  });

  it("retries initial product loading without clearing account fields", async () => {
    listAdminProductsMock
      .mockResolvedValueOnce(failure())
      .mockResolvedValueOnce(ok({ items: [], next_cursor: null }));
    renderUsers();
    const user = await openAddDialog();
    await user.type(
      screen.getByRole("textbox", { name: "Display name" }),
      "Draft Name",
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Products unavailable",
    );
    await user.click(
      screen.getByRole("button", { name: "Retry loading products" }),
    );
    expect(
      await screen.findByText("No active products available."),
    ).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Display name" })).toHaveValue(
      "Draft Name",
    );
  });

  it("loads current roles and saves explicit additions, changes and removals with the account", async () => {
    const unassigned: AdminUserProductAccess = {
      ...assignedAlpha,
      product_id: "00000000-0000-4000-8000-000000000012",
      name: "Synthetic Gamma",
      role: null,
      version: null,
    };
    listAdminUserProductsMock.mockResolvedValue(
      ok({
        items: [assignedAlpha, assignedBeta, unassigned],
        next_cursor: null,
      }),
    );
    updateAdminUserMock.mockResolvedValue(ok(translator));
    renderUsers();
    const user = await openEditDialog(translator.display_name);
    const alpha = await screen.findByRole("combobox", {
      name: assignedAlpha.name,
    });
    const beta = screen.getByRole("combobox", { name: assignedBeta.name });
    expect(alpha).toHaveValue("translator");
    expect(beta).toHaveValue("product_owner");
    await user.selectOptions(alpha, "product_manager_reviewer");
    await user.selectOptions(beta, "none");
    expect(beta).toHaveValue("none");
    await user.selectOptions(
      screen.getByRole("combobox", { name: unassigned.name }),
      "product_owner",
    );
    expect(updateAdminUserMock).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Save user" }));
    expect(updateAdminUserMock).toHaveBeenCalledWith({
      auth: "memory-only-admin-bearer",
      path: { user_id: translator.id },
      body: {
        display_name: translator.display_name,
        roles: translator.roles,
        product_assignments: [
          {
            product_id: assignedAlpha.product_id,
            role: "product_manager_reviewer",
            expected_version: assignedAlpha.version,
          },
          {
            product_id: assignedBeta.product_id,
            role: null,
            expected_version: assignedBeta.version,
          },
          {
            product_id: unassigned.product_id,
            role: "product_owner",
            expected_version: null,
          },
        ],
      },
    });
    expect(listAdminProductsMock).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("preserves edits and membership versions while retrying another product page", async () => {
    listAdminUserProductsMock
      .mockResolvedValueOnce(
        ok({ items: [assignedAlpha], next_cursor: "next-products" }),
      )
      .mockResolvedValueOnce(failure())
      .mockResolvedValueOnce(ok({ items: [assignedBeta], next_cursor: null }));
    updateAdminUserMock.mockResolvedValue(ok(translator));
    renderUsers();
    const user = await openEditDialog(translator.display_name);
    const alpha = await screen.findByRole("combobox", {
      name: assignedAlpha.name,
    });
    await user.selectOptions(alpha, "viewer");
    await user.click(
      screen.getByRole("button", { name: "Load more products" }),
    );
    await user.click(
      await screen.findByRole("button", {
        name: "Retry loading more products",
      }),
    );
    expect(
      await screen.findByRole("combobox", { name: assignedBeta.name }),
    ).toHaveValue("product_owner");
    expect(alpha).toHaveValue("viewer");
    expect(listAdminUserProductsMock).toHaveBeenLastCalledWith({
      auth: "memory-only-admin-bearer",
      path: { user_id: translator.id },
      query: { cursor: "next-products", limit: 50 },
      signal: expect.any(AbortSignal),
    });
    await user.click(screen.getByRole("button", { name: "Save user" }));
    expect(
      updateAdminUserMock.mock.calls[0][0]?.body?.product_assignments,
    ).toEqual([
      {
        product_id: assignedAlpha.product_id,
        role: "viewer",
        expected_version: assignedAlpha.version,
      },
    ]);
  });

  it("does not rewrite unchanged roles or undo a membership when product loading fails", async () => {
    listAdminUserProductsMock
      .mockResolvedValueOnce(failure())
      .mockResolvedValueOnce(
        ok({ items: [assignedAlpha], next_cursor: "unloaded" }),
      );
    updateAdminUserMock.mockResolvedValue(ok(translator));
    renderUsers();
    const user = await openEditDialog(translator.display_name);
    await user.click(
      await screen.findByRole("button", { name: "Retry loading products" }),
    );
    const alpha = await screen.findByRole("combobox", {
      name: assignedAlpha.name,
    });
    await user.selectOptions(alpha, "none");
    await user.selectOptions(alpha, "translator");
    await user.click(screen.getByRole("button", { name: "Save user" }));
    expect(updateAdminUserMock.mock.calls[0][0]?.body).toEqual({
      display_name: translator.display_name,
      roles: translator.roles,
    });
  });

  it("retains account and product edits on conflicts and loads current roles when reopened", async () => {
    listAdminUserProductsMock
      .mockResolvedValueOnce(ok({ items: [assignedAlpha], next_cursor: null }))
      .mockResolvedValueOnce(
        ok({
          items: [
            { ...assignedAlpha, role: "viewer", version: "current-version" },
          ],
          next_cursor: null,
        }),
      );
    updateAdminUserMock.mockResolvedValue(
      conflict("Product access changed or unavailable"),
    );
    renderUsers();
    const user = await openEditDialog(translator.display_name);
    const alpha = await screen.findByRole("combobox", {
      name: assignedAlpha.name,
    });
    await user.selectOptions(alpha, "product_owner");
    await user.type(
      screen.getByRole("textbox", { name: "Display name" }),
      " draft",
    );
    await user.click(screen.getByRole("button", { name: "Save user" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No changes were saved");
    expect(alert).toHaveFocus();
    expect(alpha).toHaveValue("product_owner");
    expect(screen.getByRole("textbox", { name: "Display name" })).toHaveValue(
      `${translator.display_name} draft`,
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await openEditDialog(translator.display_name);
    expect(
      await screen.findByRole("combobox", { name: assignedAlpha.name }),
    ).toHaveValue("viewer");
  });

  it("allows removing an inactive account's membership on an inactive product", async () => {
    listAdminUsersMock.mockResolvedValue(
      ok({ items: [currentAdmin, inactiveViewer], next_cursor: null }),
    );
    listAdminUserProductsMock.mockResolvedValue(
      ok({
        items: [{ ...assignedAlpha, is_active: false }],
        next_cursor: null,
      }),
    );
    updateAdminUserMock.mockResolvedValue(ok(inactiveViewer));
    renderUsers();
    const user = await openEditDialog(inactiveViewer.display_name);
    const alpha = await screen.findByRole("combobox", {
      name: `${assignedAlpha.name} (inactive)`,
    });
    expect(
      within(alpha).getByRole("option", { name: "Product Owner" }),
    ).toBeDisabled();
    await user.selectOptions(alpha, "none");
    await user.click(screen.getByRole("button", { name: "Save user" }));
    expect(
      updateAdminUserMock.mock.calls[0][0]?.body?.product_assignments,
    ).toEqual([
      {
        product_id: assignedAlpha.product_id,
        role: null,
        expected_version: assignedAlpha.version,
      },
    ]);
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
      expect(alert).toHaveTextContent("Users unavailable");
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

  it("fails closed when the generated user list has no response data", async () => {
    listAdminUsersMock.mockResolvedValueOnce(failure());

    renderUsers();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Users unavailable",
    );
  });

  it("ignores a user list response superseded by newer access authority", async () => {
    let resolveFirst:
      | ((
          value: ReturnType<
            typeof ok<{ items: AdminUserResponse[]; next_cursor: null }>
          >,
        ) => void)
      | undefined;
    const firstLoad = new Promise<
      ReturnType<typeof ok<{ items: AdminUserResponse[]; next_cursor: null }>>
    >((resolve) => {
      resolveFirst = resolve;
    });
    listAdminUsersMock
      .mockReturnValueOnce(firstLoad)
      .mockResolvedValueOnce(ok({ items: [translator], next_cursor: null }));
    const view = render(
      <UsersPage
        accessToken="first-memory-only-bearer"
        currentUserId={currentAdmin.id}
      />,
    );

    await waitFor(() => {
      expect(listAdminUsersMock).toHaveBeenCalledWith({
        auth: "first-memory-only-bearer",
        query: { cursor: null, limit: 50 },
      });
    });

    view.rerender(
      <UsersPage
        accessToken="second-memory-only-bearer"
        currentUserId={currentAdmin.id}
      />,
    );
    expect(await screen.findAllByText(translator.display_name)).toHaveLength(2);

    await act(async () => {
      resolveFirst?.(ok({ items: [currentAdmin], next_cursor: null }));
    });

    expect(
      screen.queryByText(currentAdmin.display_name),
    ).not.toBeInTheDocument();
    expect(listAdminUsersMock).toHaveBeenNthCalledWith(2, {
      auth: "second-memory-only-bearer",
      query: { cursor: null, limit: 50 },
    });
  });

  it("ignores a rejected user list request superseded by newer access authority", async () => {
    let rejectFirst: ((reason: unknown) => void) | undefined;
    const firstLoad = new Promise<never>((_resolve, reject) => {
      rejectFirst = reject;
    });
    listAdminUsersMock
      .mockReturnValueOnce(firstLoad)
      .mockResolvedValueOnce(ok({ items: [translator], next_cursor: null }));
    const view = render(
      <UsersPage
        accessToken="first-rejected-memory-bearer"
        currentUserId={currentAdmin.id}
      />,
    );
    await waitFor(() => {
      expect(listAdminUsersMock).toHaveBeenCalledWith({
        auth: "first-rejected-memory-bearer",
        query: { cursor: null, limit: 50 },
      });
    });

    view.rerender(
      <UsersPage
        accessToken="replacement-memory-bearer"
        currentUserId={currentAdmin.id}
      />,
    );
    expect(await screen.findAllByText(translator.display_name)).toHaveLength(2);

    await act(async () => {
      rejectFirst?.(new Error("stale authority failure"));
    });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Internal users" })).toBeVisible();
  });

  it("does not start a queued user load after the page unmounts", async () => {
    const view = renderUsers();

    view.unmount();
    await act(async () => Promise.resolve());

    expect(listAdminUsersMock).not.toHaveBeenCalled();
  });

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
    expect(screen.getByText("Clear filters to see all users.")).toBeVisible();
  });

  it("projects the active filter without reordering or retaining inactive rows", async () => {
    listAdminUsersMock.mockResolvedValueOnce(
      ok({
        items: [currentAdmin, inactiveViewer, translator],
        next_cursor: null,
      }),
    );
    renderUsers();

    await userEvent.click(
      await screen.findByRole("combobox", { name: "User status" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "Active users" }));

    const table = screen.getByRole("table", { name: "Internal users" });
    expect(within(table).getByText("Zulu Admin")).toBeVisible();
    expect(within(table).getByText("Alpha Translator")).toBeVisible();
    expect(within(table).queryByText("Middle Viewer")).not.toBeInTheDocument();
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

  it("focuses each missing identity field and closes only through the explicit cancel action", async () => {
    const onOpenChange = vi.fn();
    const onSubmit = vi.fn();
    render(
      <UserDialog
        accessToken="memory-only-admin-bearer"
        currentUserId={currentAdmin.id}
        onOpenChange={onOpenChange}
        onSubmit={onSubmit}
        open
        user={null}
      />,
    );
    const user = userEvent.setup();
    const email = screen.getByRole("textbox", { name: "Corporate email" });
    const displayName = screen.getByRole("textbox", { name: "Display name" });

    await user.click(screen.getByRole("button", { name: "Create user" }));
    expect(screen.getByText("Enter a corporate email.")).toBeVisible();
    expect(email).toHaveFocus();
    expect(onSubmit).not.toHaveBeenCalled();

    await user.type(email, "required@example.com");
    await user.click(screen.getByRole("button", { name: "Create user" }));
    expect(screen.getByText("Enter a display name.")).toBeVisible();
    expect(displayName).toHaveFocus();
    expect(onSubmit).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("prevents duplicate pending user submissions and sanitizes failure", async () => {
    let resolveSubmission: ((value: { status: "error" }) => void) | undefined;
    const pendingSubmission = new Promise<{ status: "error" }>((resolve) => {
      resolveSubmission = resolve;
    });
    const onOpenChange = vi.fn();
    const onSubmit = vi.fn(() => pendingSubmission);
    render(
      <UserDialog
        accessToken="memory-only-admin-bearer"
        currentUserId={currentAdmin.id}
        onOpenChange={onOpenChange}
        onSubmit={onSubmit}
        open
        user={null}
      />,
    );
    const user = userEvent.setup();
    await user.type(
      screen.getByRole("textbox", { name: "Corporate email" }),
      "pending@example.com",
    );
    await user.type(
      screen.getByRole("textbox", { name: "Display name" }),
      "Pending User",
    );
    await user.click(screen.getByRole("button", { name: "Create user" }));

    const submit = screen.getByRole("button", { name: "Create user" });
    expect(submit).toBeDisabled();
    await user.click(submit);
    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onOpenChange).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Add user" })).toBeVisible();

    await act(async () => resolveSubmission?.({ status: "error" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your entries are still here. Review them and try again.",
    );
  });

  it("maps a rejected user submission to bounded generic copy", async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValueOnce(
        new Error("provider detail with User-Secret-That-Must-Not-Leak"),
      );
    render(
      <UserDialog
        accessToken="memory-only-admin-bearer"
        currentUserId={currentAdmin.id}
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
        open
        user={null}
      />,
    );
    const user = userEvent.setup();
    await user.type(
      screen.getByRole("textbox", { name: "Corporate email" }),
      "rejected@example.com",
    );
    await user.type(
      screen.getByRole("textbox", { name: "Display name" }),
      "Rejected User",
    );
    await user.click(screen.getByRole("button", { name: "Create user" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Your entries are still here. Review them and try again.",
    );
    expect(alert).not.toHaveTextContent("User-Secret-That-Must-Not-Leak");
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

  it("keeps create fields on a bounded non-conflict server failure", async () => {
    createAdminUserMock.mockResolvedValueOnce(failure());
    renderUsers();
    const user = await openAddDialog();
    const email = screen.getByRole("textbox", { name: "Corporate email" });
    const displayName = screen.getByRole("textbox", { name: "Display name" });

    await user.type(email, "retry-create@example.com");
    await user.type(displayName, "Retry Create");
    await user.click(screen.getByRole("button", { name: "Create user" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your entries are still here. Review them and try again.",
    );
    expect(email).toHaveValue("retry-create@example.com");
    expect(displayName).toHaveValue("Retry Create");
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

  it("keeps edit fields on a bounded non-conflict server failure", async () => {
    updateAdminUserMock.mockResolvedValueOnce(failure());
    renderUsers();
    const user = await openEditDialog(translator.display_name);
    const displayName = screen.getByRole("textbox", { name: "Display name" });

    await user.clear(displayName);
    await user.type(displayName, "Retry Edit");
    await user.click(screen.getByRole("button", { name: "Save user" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your entries are still here. Review them and try again.",
    );
    expect(displayName).toHaveValue("Retry Edit");
  });

  it("renders an unknown server role literally instead of inventing a label", async () => {
    const roleOutsideCurrentClientEnum = {
      ...translator,
      roles: ["future_server_role" as AdminUserResponse["roles"][number]],
    };
    listAdminUsersMock.mockResolvedValueOnce(
      ok({ items: [roleOutsideCurrentClientEnum], next_cursor: null }),
    );

    renderUsers();

    expect(await screen.findAllByText("future_server_role")).toHaveLength(2);
  });

  it("reveals a created credential only in a non-dismissible acknowledgement dialog", async () => {
    const temporaryPassword = "Create-Only-Secret!2048";
    const createdUser: AdminUserResponse = {
      id: "00000000-0000-4000-8000-000000000004",
      email: "created@example.com",
      display_name: "Created User",
      is_active: true,
      must_change_password: true,
      roles: ["viewer"],
    };
    listAdminUsersMock
      .mockResolvedValueOnce(
        ok({ items: [currentAdmin, translator], next_cursor: null }),
      )
      .mockResolvedValueOnce(
        ok({
          items: [currentAdmin, translator, createdUser],
          next_cursor: null,
        }),
      );
    createAdminUserMock.mockResolvedValueOnce(
      ok({ ...createdUser, temporary_password: temporaryPassword }, 201),
    );
    renderUsers();
    const user = await openAddDialog();
    const writeClipboard = vi.spyOn(navigator.clipboard, "writeText");

    await user.type(
      screen.getByRole("textbox", { name: "Corporate email" }),
      createdUser.email,
    );
    await user.type(
      screen.getByRole("textbox", { name: "Display name" }),
      createdUser.display_name,
    );
    await user.click(screen.getByRole("button", { name: "Create user" }));

    const credentialDialog = await screen.findByRole("dialog", {
      name: "Temporary password created",
    });
    expect(within(credentialDialog).getByText(temporaryPassword)).toBeVisible();
    expect(
      within(credentialDialog).queryByRole("button", { name: "Close" }),
    ).not.toBeInTheDocument();
    expect(within(credentialDialog).getByRole("status")).toBeEmptyDOMElement();
    expect(writeClipboard).not.toHaveBeenCalled();

    await user.keyboard("{Escape}");
    expect(credentialDialog).toBeVisible();
    fireEvent.pointerDown(document.body);
    expect(credentialDialog).toBeVisible();

    writeClipboard.mockRejectedValueOnce(
      new Error(`clipboard failed with ${temporaryPassword}`),
    );
    await user.click(
      within(credentialDialog).getByRole("button", {
        name: "Copy temporary password",
      }),
    );
    const copyStatus = within(credentialDialog).getByRole("status");
    expect(copyStatus).toHaveTextContent(
      "The password could not be copied. Select it and copy it manually.",
    );
    expect(copyStatus).not.toHaveTextContent(temporaryPassword);

    writeClipboard.mockResolvedValueOnce(undefined);
    await user.click(
      within(credentialDialog).getByRole("button", {
        name: "Copy temporary password",
      }),
    );
    expect(writeClipboard).toHaveBeenCalledTimes(2);
    expect(writeClipboard).toHaveBeenCalledWith(temporaryPassword);
    expect(copyStatus).toHaveTextContent("Temporary password copied");
    expect(copyStatus).not.toHaveTextContent(temporaryPassword);

    await user.click(
      within(credentialDialog).getByRole("button", {
        name: "I saved the password",
      }),
    );
    expect(
      screen.queryByRole("dialog", { name: "Temporary password created" }),
    ).not.toBeInTheDocument();
    expect(document.documentElement.textContent).not.toContain(
      temporaryPassword,
    );
    expect(window.location.href).not.toContain(temporaryPassword);
    expect(JSON.stringify(Object.entries(localStorage))).not.toContain(
      temporaryPassword,
    );
    expect(JSON.stringify(Object.entries(sessionStorage))).not.toContain(
      temporaryPassword,
    );
    expect(JSON.stringify(createAdminUserMock.mock.calls)).not.toContain(
      temporaryPassword,
    );
  });

  it("zeroes the temporary password before notifying its acknowledgement owner", async () => {
    const temporaryPassword = "Erase-Before-Close!2048";
    const onAcknowledged = vi.fn(() => {
      expect(
        screen.getByRole("dialog", { name: "Temporary password created" }),
      ).toBeVisible();
      expect(screen.queryByText(temporaryPassword)).not.toBeInTheDocument();
      expect(screen.getByLabelText("Temporary password")).toBeEmptyDOMElement();
    });
    render(
      <TemporaryPasswordDialog
        displayName="Erase Check"
        temporaryPassword={temporaryPassword}
        onAcknowledged={onAcknowledged}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "I saved the password" }),
    );

    expect(onAcknowledged).toHaveBeenCalledOnce();
  });

  it.each([
    {
      actionName: "Reset password",
      confirmTitle: "Reset password for Alpha Translator?",
      confirmLabel: "Reset password",
      temporaryPassword: "Reset-Only-Secret!2048",
      operation: resetAdminUserPasswordMock,
    },
    {
      actionName: "Reactivate user",
      confirmTitle: "Reactivate Middle Viewer?",
      confirmLabel: "Reactivate user",
      temporaryPassword: "Reactivate-Only-Secret!2048",
      operation: reactivateAdminUserMock,
    },
  ])(
    "$actionName requires named confirmation and opens the one-time credential boundary",
    async ({
      actionName,
      confirmTitle,
      confirmLabel,
      temporaryPassword,
      operation,
    }) => {
      const target =
        actionName === "Reset password" ? translator : inactiveViewer;
      listAdminUsersMock.mockResolvedValueOnce(
        ok({
          items: [currentAdmin, translator, inactiveViewer],
          next_cursor: null,
        }),
      );
      operation.mockResolvedValueOnce(
        ok({
          ...target,
          is_active: true,
          must_change_password: true,
          temporary_password: temporaryPassword,
        }),
      );
      renderUsers();
      const user = await chooseRowAction(target.display_name, actionName);

      const confirmation = screen.getByRole("alertdialog", {
        name: confirmTitle,
      });
      const submit = within(confirmation).getByRole("button", {
        name: confirmLabel,
      });
      await user.click(submit);

      expect(operation).toHaveBeenCalledOnce();
      expect(operation).toHaveBeenCalledWith({
        auth: "memory-only-admin-bearer",
        path: { user_id: target.id },
      });
      const credentialDialog = await screen.findByRole("dialog", {
        name: "Temporary password created",
      });
      expect(
        within(credentialDialog).getByText(temporaryPassword),
      ).toBeVisible();
      expect(
        screen.queryByRole("alertdialog", { hidden: true }),
      ).not.toBeInTheDocument();
      if (actionName === "Reactivate user") {
        const table = screen.getByRole("table", {
          name: "Internal users",
          hidden: true,
        });
        const row = within(table).getByRole("row", {
          name: /Middle Viewer/i,
          hidden: true,
        });
        expect(within(row).getByText("Active")).toBeVisible();
      }
    },
  );

  it("prevents duplicate reset submission while the named confirmation is pending", async () => {
    let resolveReset:
      | ((value: ReturnType<typeof ok<AdminUserCredentialResponse>>) => void)
      | undefined;
    const pendingReset = new Promise<
      ReturnType<typeof ok<AdminUserCredentialResponse>>
    >((resolve) => {
      resolveReset = resolve;
    });
    resetAdminUserPasswordMock.mockReturnValueOnce(pendingReset);
    renderUsers();
    const user = await chooseRowAction(
      translator.display_name,
      "Reset password",
    );
    const confirmation = screen.getByRole("alertdialog", {
      name: "Reset password for Alpha Translator?",
    });
    const submit = within(confirmation).getByRole("button", {
      name: "Reset password",
    });

    await user.click(submit);
    expect(submit).toBeDisabled();
    expect(submit).toHaveAttribute("aria-busy", "true");
    await user.keyboard("{Escape}");
    expect(confirmation).toBeVisible();
    await user.click(submit);
    expect(resetAdminUserPasswordMock).toHaveBeenCalledOnce();

    await act(async () => {
      resolveReset?.(
        ok({
          ...translator,
          must_change_password: true,
          temporary_password: "Pending-Reset-Secret!2048",
        }),
      );
    });
    expect(
      await screen.findByRole("dialog", { name: "Temporary password created" }),
    ).toBeVisible();
  });

  it("cancels a named confirmation without mutating and restores the invoking control", async () => {
    renderUsers();
    const user = await chooseRowAction(
      translator.display_name,
      "Reset password",
    );
    const confirmation = screen.getByRole("alertdialog", {
      name: "Reset password for Alpha Translator?",
    });

    await user.click(
      within(confirmation).getByRole("button", { name: "Cancel" }),
    );

    expect(confirmation).not.toBeInTheDocument();
    expect(resetAdminUserPasswordMock).not.toHaveBeenCalled();
    const table = screen.getByRole("table", { name: "Internal users" });
    expect(
      within(table).getByRole("button", {
        name: "More actions for Alpha Translator",
      }),
    ).toHaveFocus();
  });

  it("keeps reset conflicts bounded to their named dialog and preserves the row", async () => {
    let resolveRetry:
      | ((value: ReturnType<typeof ok<AdminUserCredentialResponse>>) => void)
      | undefined;
    const pendingRetry = new Promise<
      ReturnType<typeof ok<AdminUserCredentialResponse>>
    >((resolve) => {
      resolveRetry = resolve;
    });
    resetAdminUserPasswordMock
      .mockResolvedValueOnce(
        conflict("stale authority with Reset-Secret-That-Must-Not-Leak"),
      )
      .mockReturnValueOnce(pendingRetry);
    const successfulRetry = ok({
      ...translator,
      must_change_password: true,
      temporary_password: "Retry-Reset-Secret!2048",
    });
    renderUsers();
    const user = await chooseRowAction(
      translator.display_name,
      "Reset password",
    );
    const confirmation = screen.getByRole("alertdialog", {
      name: "Reset password for Alpha Translator?",
    });

    await user.click(
      within(confirmation).getByRole("button", { name: "Reset password" }),
    );

    const alert = await within(confirmation).findByRole("alert");
    expect(alert).toHaveTextContent(
      "This user changed in another session or administrator authority must be preserved.",
    );
    expect(alert).not.toHaveTextContent("Reset-Secret-That-Must-Not-Leak");
    expect(alert).toHaveFocus();
    expect(confirmation).toBeVisible();
    expect(
      within(confirmation).getByRole("button", { name: "Reset password" }),
    ).toBeEnabled();

    await user.click(
      within(confirmation).getByRole("button", { name: "Reset password" }),
    );
    await waitFor(() => {
      expect(within(confirmation).queryByRole("alert")).not.toBeInTheDocument();
      expect(
        within(confirmation).getByRole("button", { name: "Reset password" }),
      ).toBeDisabled();
    });
    await act(async () => resolveRetry?.(successfulRetry));
    expect(await screen.findByText("Retry-Reset-Secret!2048")).toBeVisible();
    expect(
      screen.queryByRole("alertdialog", { hidden: true }),
    ).not.toBeInTheDocument();
  });

  it("maps a non-conflict lifecycle denial to bounded generic copy", async () => {
    resetAdminUserPasswordMock.mockResolvedValueOnce({
      data: undefined,
      error: { detail: "server detail with Generic-Lifecycle-Leak" },
      request: new Request("http://localhost/api/v1/admin/users"),
      response: new Response(null, { status: 503 }),
    });
    renderUsers();
    const user = await chooseRowAction(
      translator.display_name,
      "Reset password",
    );
    const confirmation = screen.getByRole("alertdialog", {
      name: "Reset password for Alpha Translator?",
    });

    await user.click(
      within(confirmation).getByRole("button", { name: "Reset password" }),
    );

    const alert = await within(confirmation).findByRole("alert");
    expect(alert).toHaveTextContent(
      "The current user state is unchanged. Try again.",
    );
    expect(alert).not.toHaveTextContent("Generic-Lifecycle-Leak");
    expect(alert).toHaveFocus();
    expect(
      within(confirmation).getByRole("button", { name: "Reset password" }),
    ).toBeEnabled();
  });

  it("maps a non-conflict deactivation denial without altering the active row", async () => {
    deactivateAdminUserMock.mockResolvedValueOnce({
      data: undefined,
      error: { detail: "deactivate detail with Deactivate-Lifecycle-Leak" },
      request: new Request("http://localhost/api/v1/admin/users"),
      response: new Response(null, { status: 503 }),
    });
    renderUsers();
    const user = await chooseRowAction(
      translator.display_name,
      "Deactivate user",
    );
    const confirmation = screen.getByRole("alertdialog", {
      name: "Deactivate Alpha Translator?",
    });

    await user.click(
      within(confirmation).getByRole("button", { name: "Deactivate user" }),
    );

    const alert = await within(confirmation).findByRole("alert");
    expect(alert).toHaveTextContent(
      "The current user state is unchanged. Try again.",
    );
    expect(alert).not.toHaveTextContent("Deactivate-Lifecycle-Leak");
    expect(alert).toHaveFocus();
    const table = screen.getByRole("table", {
      name: "Internal users",
      hidden: true,
    });
    const row = within(table).getByRole("row", {
      name: /Alpha Translator/i,
      hidden: true,
    });
    expect(within(row).getByText("Active")).toBeVisible();
  });

  it("sanitizes rejected lifecycle requests and preserves the inactive row", async () => {
    listAdminUsersMock.mockResolvedValueOnce(
      ok({ items: [currentAdmin, inactiveViewer], next_cursor: null }),
    );
    reactivateAdminUserMock.mockRejectedValueOnce(
      new Error("provider=https://example.invalid?token=Lifecycle-Leak"),
    );
    renderUsers();
    const user = await chooseRowAction(
      inactiveViewer.display_name,
      "Reactivate user",
    );
    const confirmation = screen.getByRole("alertdialog", {
      name: "Reactivate Middle Viewer?",
    });

    await user.click(
      within(confirmation).getByRole("button", { name: "Reactivate user" }),
    );

    const alert = await within(confirmation).findByRole("alert");
    expect(alert).toHaveTextContent(
      "The current user state is unchanged. Try again.",
    );
    expect(alert).not.toHaveTextContent("Lifecycle-Leak");
    expect(alert).toHaveFocus();
    const table = screen.getByRole("table", {
      name: "Internal users",
      hidden: true,
    });
    const row = within(table).getByRole("row", {
      name: /Middle Viewer/i,
      hidden: true,
    });
    expect(within(row).getByText("Inactive")).toBeVisible();
  });

  it("keeps the named deactivate dialog and active row intact on server denial", async () => {
    deactivateAdminUserMock.mockResolvedValueOnce(
      conflict("last active administrator cannot be deactivated"),
    );
    renderUsers();
    const user = await chooseRowAction(
      currentAdmin.display_name,
      "Deactivate user",
    );

    const confirmation = screen.getByRole("alertdialog", {
      name: "Deactivate Zulu Admin?",
    });
    await user.click(
      within(confirmation).getByRole("button", { name: "Deactivate user" }),
    );

    const alert = await within(confirmation).findByRole("alert");
    expect(alert).toHaveTextContent(
      "This account cannot be deactivated because administrator authority must be preserved.",
    );
    expect(alert).toHaveFocus();
    expect(confirmation).toBeVisible();
    const table = screen.getByRole("table", {
      name: "Internal users",
      hidden: true,
    });
    const row = within(table).getByRole("row", {
      name: /Zulu Admin/i,
      hidden: true,
    });
    expect(within(row).getByText("Active")).toBeVisible();
    expect(deactivateAdminUserMock).toHaveBeenCalledOnce();
  });

  it("applies deactivation only from the backend response", async () => {
    deactivateAdminUserMock.mockResolvedValueOnce(
      ok({ ...translator, is_active: false }),
    );
    renderUsers();
    const user = await chooseRowAction(
      translator.display_name,
      "Deactivate user",
    );
    const confirmation = screen.getByRole("alertdialog", {
      name: "Deactivate Alpha Translator?",
    });

    await user.click(
      within(confirmation).getByRole("button", { name: "Deactivate user" }),
    );

    await waitFor(() => {
      const table = screen.getByRole("table", { name: "Internal users" });
      const row = within(table).getByRole("row", { name: /Alpha Translator/i });
      expect(within(row).getByText("Inactive")).toBeVisible();
    });
    expect(
      within(screen.getByRole("table", { name: "Internal users" })).getByRole(
        "button",
        {
          name: "More actions for Alpha Translator",
        },
      ),
    ).toHaveFocus();
  });
});
