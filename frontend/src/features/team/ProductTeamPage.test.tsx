import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProductTeamPage } from "./ProductTeamPage";
import {
  getProductTeam,
  addProductMember,
  removeProductMember,
  setProductMember,
} from "../../api/client";

vi.mock("../../api/client", () => ({
  getProductTeam: vi.fn(),
  addProductMember: vi.fn(),
  removeProductMember: vi.fn(),
  setProductMember: vi.fn(),
}));
const fixture = (admin = false) => ({
  access: {
    role: admin ? "admin" : "product_owner",
    roles: ["product_manager_reviewer"],
    can_manage_team: true,
  },
  members: [
    {
      user_id: "owner-id",
      email: "owner@example.com",
      display_name: "Product Owner",
      role: "product_owner",
      version: "owner-version",
      account_active: true,
    },
    {
      user_id: "member-id",
      email: "member@example.com",
      display_name: "Translator",
      role: "translator",
      version: "member-version",
      account_active: true,
    },
  ],
  has_active_owner: true,
});
function show() {
  return render(
    <MemoryRouter initialEntries={["/products/p1/team"]}>
      <Routes>
        <Route
          path="/products/:productId/team"
          element={<ProductTeamPage accessToken="test-token" />}
        />
      </Routes>
    </MemoryRouter>,
  );
}
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getProductTeam).mockResolvedValue({
    data: fixture(),
    response: new Response(),
  } as never);
  vi.mocked(addProductMember).mockResolvedValue({
    data: {
      user_id: "new-id",
      email: "new@example.com",
      account_created: true,
      temporary_password: "synthetic-temporary-password!",
    },
    response: new Response(null, { status: 201 }),
  } as never);
  vi.mocked(removeProductMember).mockResolvedValue({
    response: new Response(null, { status: 204 }),
  } as never);
});
afterEach(cleanup);

describe("Product team", () => {
  it("lets owners add operational roles but never appoint or demote an owner", async () => {
    const user = userEvent.setup();
    show();
    await screen.findByText("owner@example.com");
    expect(
      screen.queryByRole("button", { name: "Edit owner@example.com" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add collaborator" }));
    expect(
      screen.queryByRole("button", { name: "Assign Product Owner" }),
    ).not.toBeInTheDocument();
    const select = screen.getByRole("combobox", { name: "Collaborator role" });
    expect(
      within(select).queryByRole("option", { name: "Product Owner" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: "Remove owner@example.com from product",
      }),
    ).not.toBeInTheDocument();
    await user.type(
      screen.getByLabelText("Collaborator email"),
      "new@example.com",
    );
    await user.type(screen.getByLabelText("Display name"), "New Translator");
    await user.selectOptions(select, "product_manager_reviewer");
    await user.click(screen.getByRole("button", { name: "Add to team" }));
    expect(addProductMember).toHaveBeenCalledWith(
      expect.objectContaining({
        auth: "test-token",
        path: { product_id: "p1" },
        body: {
          email: "new@example.com",
          display_name: "New Translator",
          role: "product_manager_reviewer",
        },
      }),
    );
  });
  it("requires an explicit removal confirmation and sends the current version", async () => {
    const user = userEvent.setup();
    show();
    await user.click(
      await screen.findByRole("button", { name: "Edit member@example.com" }),
    );
    await user.click(
      screen.getByRole("button", {
        name: "Remove member@example.com from product",
      }),
    );
    expect(removeProductMember).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirm removal" }));
    expect(removeProductMember).toHaveBeenCalledWith(
      expect.objectContaining({
        path: { product_id: "p1", user_id: "member-id" },
        query: { expected_version: "member-version" },
      }),
    );
  });
  it("lets the administrator appoint an owner without exposing an admin grant", async () => {
    const user = userEvent.setup();
    vi.mocked(getProductTeam).mockResolvedValue({
      data: fixture(true),
    } as never);
    vi.mocked(setProductMember).mockResolvedValue({
      response: new Response(null, { status: 204 }),
    } as never);
    show();
    await user.click(
      await screen.findByRole("button", { name: "Assign Product Owner" }),
    );
    await user.type(
      screen.getByLabelText("Account email"),
      "new-owner@example.com",
    );
    await user.click(screen.getByRole("button", { name: "Appoint owner" }));
    expect(setProductMember).toHaveBeenCalledWith(
      expect.objectContaining({
        body: { email: "new-owner@example.com", role: "product_owner" },
      }),
    );
    expect(
      screen.queryByRole("option", { name: "Admin" }),
    ).not.toBeInTheDocument();
  });
  it("shows a conflict without claiming success or dropping the entered email", async () => {
    const user = userEvent.setup();
    vi.mocked(addProductMember).mockResolvedValue({
      response: new Response(null, { status: 409 }),
      error: { detail: "Already a member." },
    } as never);
    show();
    await user.click(
      await screen.findByRole("button", { name: "Add collaborator" }),
    );
    const input = screen.getByLabelText("Collaborator email");
    await user.type(input, "duplicate@example.com");
    await user.type(screen.getByLabelText("Display name"), "Duplicate");
    await user.click(screen.getByRole("button", { name: "Add to team" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Already a member."),
    );
    expect(input).toHaveValue("duplicate@example.com");
    expect(screen.queryByText("Collaborator added.")).not.toBeInTheDocument();
  });
});

it("keeps the only credential visible through refresh, copies it, then clears it on acknowledgment", async () => {
  const user = userEvent.setup();
  const write = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
  show();
  await user.click(
    await screen.findByRole("button", { name: "Add collaborator" }),
  );
  await user.type(
    screen.getByLabelText("Collaborator email"),
    "new@example.com",
  );
  await user.type(screen.getByLabelText("Display name"), "New Translator");
  await user.click(screen.getByRole("button", { name: "Add to team" }));
  const dialog = await screen.findByRole("dialog", {
    name: "Temporary password created",
  });
  await waitFor(() => expect(getProductTeam).toHaveBeenCalledTimes(2));
  expect(within(dialog).getByLabelText("Temporary password")).toHaveTextContent(
    "synthetic-temporary-password!",
  );
  expect(dialog).toHaveTextContent("new@example.com");
  expect(dialog).toHaveTextContent("must be changed at the next sign-in");
  await user.keyboard("{Escape}");
  expect(dialog).toBeInTheDocument();
  await user.click(
    within(dialog).getByRole("button", { name: "Copy temporary password" }),
  );
  expect(write).toHaveBeenCalledWith("synthetic-temporary-password!");
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
  await user.click(
    within(dialog).getByRole("button", { name: "I saved the password" }),
  );
  expect(
    screen.queryByText("synthetic-temporary-password!"),
  ).not.toBeInTheDocument();
});

it("adds existing accounts without a password dialog", async () => {
  vi.mocked(addProductMember).mockResolvedValue({
    data: {
      user_id: "other",
      email: "existing@example.com",
      account_created: false,
      temporary_password: null,
    },
    response: new Response(null, { status: 201 }),
  } as never);
  const user = userEvent.setup();
  show();
  await user.click(
    await screen.findByRole("button", { name: "Add collaborator" }),
  );
  await user.type(
    screen.getByLabelText("Collaborator email"),
    "existing@example.com",
  );
  await user.type(screen.getByLabelText("Display name"), "Existing");
  await user.click(screen.getByRole("button", { name: "Add to team" }));
  expect(
    await screen.findByText(
      "Existing account added. They can sign in with their current credentials.",
    ),
  ).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("separates owners and collaborators with roles and hides forms until requested", async () => {
  show();
  const owners = await screen.findByRole("region", { name: "Product Owner" });
  const collaborators = screen.getByRole("region", { name: "Collaborators" });
  expect(within(owners).getByText("owner@example.com")).toBeVisible();
  expect(
    within(owners).queryByText("member@example.com"),
  ).not.toBeInTheDocument();
  expect(within(collaborators).getByText("member@example.com")).toBeVisible();
  expect(
    within(collaborators).queryByText("owner@example.com"),
  ).not.toBeInTheDocument();
  expect(within(collaborators).getAllByText("Translator")).toHaveLength(2);
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Add collaborator" }),
  ).toHaveAttribute("aria-expanded", "false");
});

it("preserves a failed role edit and saves with its membership version before closing", async () => {
  const user = userEvent.setup();
  vi.mocked(setProductMember).mockResolvedValueOnce({
    response: new Response(null, { status: 409 }),
    error: { detail: "Membership changed. Refresh the team." },
  } as never);
  show();
  await user.click(
    await screen.findByRole("button", { name: "Edit member@example.com" }),
  );
  const select = screen.getByRole("combobox", {
    name: "Role for member@example.com",
  });
  await user.selectOptions(select, "product_manager_reviewer");
  await user.click(screen.getByRole("button", { name: "Save role" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Membership changed.",
  );
  expect(select).toHaveValue("product_manager_reviewer");
  expect(screen.queryByText("Role updated.")).not.toBeInTheDocument();
  const updated = fixture();
  updated.members[1] = {
    ...updated.members[1],
    role: "product_manager_reviewer",
    version: "new-version",
  };
  vi.mocked(getProductTeam).mockResolvedValue({ data: updated } as never);
  vi.mocked(setProductMember).mockResolvedValue({
    response: new Response(null, { status: 204 }),
  } as never);
  await user.click(screen.getByRole("button", { name: "Save role" }));
  expect(setProductMember).toHaveBeenLastCalledWith(
    expect.objectContaining({
      body: {
        email: "member@example.com",
        role: "product_manager_reviewer",
        expected_version: "member-version",
      },
    }),
  );
  expect(await screen.findByText("Reviewer")).toBeVisible();
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
});

it("moves a promoted collaborator into Product Owner after the administrator saves", async () => {
  const user = userEvent.setup();
  vi.mocked(getProductTeam).mockResolvedValueOnce({
    data: fixture(true),
  } as never);
  const promoted = fixture(true);
  promoted.members[1] = {
    ...promoted.members[1],
    role: "product_owner",
    version: "promoted-version",
  };
  vi.mocked(getProductTeam).mockResolvedValue({ data: promoted } as never);
  vi.mocked(setProductMember).mockResolvedValue({
    response: new Response(null, { status: 204 }),
  } as never);
  show();
  await user.click(
    await screen.findByRole("button", { name: "Edit member@example.com" }),
  );
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Role for member@example.com" }),
    "product_owner",
  );
  await user.click(screen.getByRole("button", { name: "Save role" }));
  const owners = screen.getByRole("region", { name: "Product Owner" });
  expect(await within(owners).findByText("member@example.com")).toBeVisible();
  expect(
    screen.getByRole("region", { name: "Collaborators" }),
  ).toHaveTextContent("No collaborators yet.");
});

it("shows clear empty sections and lets an admin cancel owner assignment without saving", async () => {
  const user = userEvent.setup();
  vi.mocked(getProductTeam).mockResolvedValue({
    data: { ...fixture(true), members: [], has_active_owner: false },
  } as never);
  show();
  expect(await screen.findByText("No active Product Owner")).toBeVisible();
  expect(screen.getByText("No collaborators yet.")).toBeVisible();
  await user.click(
    screen.getByRole("button", { name: "Assign Product Owner" }),
  );
  await user.type(
    screen.getByLabelText("Account email"),
    "new-owner@example.com",
  );
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(setProductMember).not.toHaveBeenCalled();
});
