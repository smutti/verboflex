import { expect, test } from "@playwright/test";

test.use({ locale: "it-IT" });
const admin = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "admin@example.com",
  display_name: "Synthetic Admin",
  roles: ["admin"],
  is_active: true,
  must_change_password: false,
};
const collaborator = {
  ...admin,
  id: "00000000-0000-4000-8000-000000000002",
  email: "collaborator@example.com",
  display_name: "Synthetic Collaborator",
  roles: ["viewer"],
};
for (const width of [1440, 320]) {
  test(`deactivate, confirm and delete an account at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    let target: typeof collaborator | null = { ...collaborator };
    let deletionRequests = 0;
    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/v1/auth/refresh") {
        await route.fulfill({
          json: {
            access_token: "synthetic-token",
            token_type: "bearer",
            expires_in: 900,
            must_change_password: false,
          },
        });
      } else if (path === "/api/v1/users/me") {
        await route.fulfill({ json: admin });
      } else if (path === "/api/v1/admin/users") {
        await route.fulfill({
          json: {
            items: target ? [admin, target] : [admin],
            next_cursor: null,
          },
        });
      } else if (path === `/api/v1/admin/users/${collaborator.id}/deactivate`) {
        expect(route.request().method()).toBe("POST");
        target = { ...collaborator, is_active: false };
        await route.fulfill({ json: target });
      } else if (path === `/api/v1/admin/users/${collaborator.id}`) {
        expect(route.request().method()).toBe("DELETE");
        expect(target?.is_active).toBe(false);
        deletionRequests++;
        target = null;
        await route.fulfill({ status: 204 });
      } else {
        await route.fulfill({
          status: 503,
          json: { detail: "Unrelated synthetic service" },
        });
      }
    });
    await page.goto("/admin/users");
    const actions = page.getByRole("button", {
      name: "Altre azioni per Synthetic Collaborator",
    });
    await actions.click();
    await expect(
      page.getByRole("menuitem", { name: "Elimina utente" }),
    ).toHaveCount(0);
    await page.getByRole("menuitem", { name: "Disattiva utente" }).click();
    let dialog = page.getByRole("alertdialog");
    await dialog.getByRole("button", { name: "Disattiva utente" }).click();
    await expect(dialog).toBeHidden();
    await actions.click();
    await page.getByRole("menuitem", { name: "Elimina utente" }).click();
    dialog = page.getByRole("alertdialog");
    await expect(dialog).toHaveAccessibleName(
      "Eliminare Synthetic Collaborator?",
    );
    await expect(dialog).toContainText(collaborator.email);
    await expect(dialog).toContainText(
      "L’account non potrà essere riattivato.",
    );
    expect(deletionRequests).toBe(0);
    await dialog.getByRole("button", { name: "Annulla" }).click();
    await expect(dialog).toBeHidden();
    expect(deletionRequests).toBe(0);
    await actions.click();
    await page.getByRole("menuitem", { name: "Elimina utente" }).click();
    await page
      .getByRole("alertdialog")
      .getByRole("button", { name: "Elimina utente" })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: "Utente eliminato." }),
    ).toBeVisible();
    await expect(actions).toHaveCount(0);
    expect(deletionRequests).toBe(1);
    await expect(
      page.getByRole("heading", { name: "Utenti", exact: true }),
    ).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Utenti", exact: true }),
    ).toBeVisible();
    await expect(actions).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Altre azioni per Synthetic Admin" }),
    ).toBeVisible();
  });
}
