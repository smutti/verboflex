import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  listProductWorkspaces,
  type CurrentUserResponse,
} from "../../api/client";
import { ProductFocusWorkspace } from "./ProductWorkspace";

vi.mock("../../api/client", () => ({ listProductWorkspaces: vi.fn() }));
vi.mock("../translations/TranslationsWorkspace", () => ({
  TranslationsWorkspace: () => <p>String workspace content</p>,
}));
const principal: CurrentUserResponse = {
  id: "synthetic-admin",
  email: "admin@example.com",
  display_name: "Admin",
  roles: ["admin"],
  must_change_password: false,
};
function show(path = "/products/p1/strings", user = principal) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/products/:productId"
          element={
            <ProductFocusWorkspace
              accessToken="synthetic-token"
              principal={user}
            />
          }
        >
          <Route path="strings" />
          <Route path="change-sets/*" element={<p>Change set content</p>} />
          <Route path="team" element={<p>Team content</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}
beforeEach(() => {
  vi.mocked(listProductWorkspaces).mockResolvedValue({
    data: {
      items: [
        {
          id: "p1",
          name: "Synthetic product",
          coverage: null,
          imported_scope_count: 0,
          unimported_scope_count: 0,
          last_imported_at: null,
        },
      ],
      total: 1,
      page: 1,
      has_more: false,
    },
    error: undefined,
  });
});
afterEach(cleanup);

it("moves the visible active highlight through all three product links", async () => {
  const user = userEvent.setup();
  show();
  const nav = await screen.findByRole("navigation", {
    name: "Synthetic product workspace",
  });
  const strings = within(nav).getByRole("link", { name: "Strings" });
  const changes = within(nav).getByRole("link", { name: "Change sets" });
  const team = within(nav).getByRole("link", { name: "Team" });
  const activeBackground = strings.style.backgroundColor;
  expect(activeBackground).not.toBe("");
  for (const [link, content] of [
    [changes, "Change set content"],
    [team, "Team content"],
    [strings, "String workspace content"],
  ] as const) {
    await user.click(link);
    expect(screen.getByText(content)).toBeVisible();
    expect(link).toHaveAttribute("aria-current", "page");
    expect(link.style.backgroundColor).toBe(activeBackground);
    for (const other of [strings, changes, team].filter(
      (item) => item !== link,
    )) {
      expect(other).not.toHaveAttribute("aria-current");
      expect(other.style.backgroundColor).toBe("");
    }
  }
});

it("keeps Team selected when its URL has a trailing slash", async () => {
  show("/products/p1/team/");
  expect(await screen.findByText("Team content")).toBeVisible();
  expect(screen.getByRole("link", { name: "Team" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(
    screen.queryByText("String workspace content"),
  ).not.toBeInTheDocument();
});

it.each([false, true])(
  "shows Team only for an administrator or a managed product (owner: %s)",
  async (owner) => {
    show("/products/p1/strings", {
      ...principal,
      roles: ["viewer"],
      managed_product_ids: owner ? ["p1"] : [],
    });
    const nav = await screen.findByRole("navigation", {
      name: "Synthetic product workspace",
    });
    expect(within(nav).queryByRole("link", { name: "Team" }) !== null).toBe(
      owner,
    );
  },
);
