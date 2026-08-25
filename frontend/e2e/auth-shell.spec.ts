import { expect, test, type Page } from "@playwright/test";

const email = requireEnvironment("E2E_EMAIL");
const temporaryPassword = requireEnvironment("E2E_TEMP_PASSWORD");
const ordinaryPassword = requireEnvironment("E2E_PASSWORD");

const workspaceIntro =
  "Your review workspace will appear here as products and repositories are configured.";
const emptyStateCopy =
  "Phase 1 confirms the platform shell, session, and services. Product and translation workflows will appear after configuration is added.";

function requireEnvironment(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.length === 0) {
    throw new Error(`${name} must be set for the isolated auth shell test`);
  }
  return value;
}

async function expectNoAuthInWebStorage(page: Page) {
  const storage = await page.evaluate(() => ({
    local: Object.entries(localStorage),
    session: Object.entries(sessionStorage),
  }));

  expect(storage).toEqual({ local: [], session: [] });
}

async function expectBoundedLayout(page: Page) {
  const layout = await page.evaluate(() => {
    const visibleElements = Array.from(document.querySelectorAll("*"))
      .filter(
        (element): element is HTMLElement => element instanceof HTMLElement,
      )
      .filter((element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== "none" && rect.width > 0 && rect.height > 0;
      });
    const radii = visibleElements.flatMap((element) => {
      const style = getComputedStyle(element);
      return [
        style.borderTopLeftRadius,
        style.borderTopRightRadius,
        style.borderBottomRightRadius,
        style.borderBottomLeftRadius,
      ].map((value) => Number.parseFloat(value) || 0);
    });

    return {
      bodyWidth: document.body.scrollWidth,
      documentWidth: document.documentElement.scrollWidth,
      innerWidth,
      maxRadius: Math.max(0, ...radii),
      gradientCount: visibleElements.filter((element) =>
        /(?:linear|radial|conic)-gradient/.test(
          getComputedStyle(element).backgroundImage,
        ),
      ).length,
      nestedSectionCount: document.querySelectorAll("section section").length,
    };
  });

  expect(layout.bodyWidth).toBeLessThanOrEqual(layout.innerWidth);
  expect(layout.documentWidth).toBeLessThanOrEqual(layout.innerWidth);
  expect(layout.maxRadius).toBeLessThanOrEqual(8);
  expect(layout.gradientCount).toBe(0);
  expect(layout.nestedSectionCount).toBe(0);
}

async function expectWorkspaceCopy(page: Page) {
  await expect(
    page.getByRole("heading", { name: "Workspace overview", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText(workspaceIntro, { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Workspace ready for configuration",
      level: 2,
    }),
  ).toBeVisible();
  await expect(page.getByText(emptyStateCopy, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /product/i })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /repository/i })).toHaveCount(
    0,
  );
  await expect(page.getByRole("button", { name: /review/i })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /pull request/i })).toHaveCount(
    0,
  );
}

test("auth shell completes forced change, refresh, responsive navigation, and logout", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/login");

  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", { name: "VerboFlex", level: 1 }),
  ).toBeVisible();

  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Email")).toBeFocused();
  await page.keyboard.type(email);
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password")).toBeFocused();
  await page.keyboard.type(temporaryPassword);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Sign in to VerboFlex" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL(/\/change-password$/);
  await expect(
    page.getByRole("heading", { name: "Set a new password", level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Your temporary password must be replaced before you can continue.",
      { exact: true },
    ),
  ).toBeVisible();

  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Current password")).toBeFocused();
  await page.keyboard.type(temporaryPassword);
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("New password", { exact: true })).toBeFocused();
  await page.keyboard.type(ordinaryPassword);
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Confirm new password")).toBeFocused();
  await page.keyboard.type(ordinaryPassword);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Set new password" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(ordinaryPassword);
  await page.getByRole("button", { name: "Sign in to VerboFlex" }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText("Phase Thirteen", { exact: true })).toBeVisible();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await expect(page.getByText("Administrator", { exact: true })).toBeVisible();
  await expectWorkspaceCopy(page);
  await expect(page.getByText("API online", { exact: true })).toBeVisible();
  await expect(
    page.getByText(/^Database (?:online|unavailable|pending)$/),
  ).toBeVisible();
  await expect(
    page.getByText(/^Redis (?:online|unavailable|pending)$/),
  ).toBeVisible();
  await expect(
    page.getByText(/^Worker (?:online|unavailable|pending)$/),
  ).toBeVisible();
  await expectNoAuthInWebStorage(page);

  await page.reload();
  await expectWorkspaceCopy(page);
  await expect(page.getByText("API online", { exact: true })).toBeVisible();
  await expectNoAuthInWebStorage(page);

  for (const width of [1440, 768, 375]) {
    await page.setViewportSize({ width, height: 900 });
    await expectWorkspaceCopy(page);
    await expectBoundedLayout(page);

    const navigationTrigger = page.getByRole("button", {
      name: "Open navigation",
    });
    if (width === 1440) {
      await expect(navigationTrigger).toBeHidden();
      await expect(
        page.locator("aside").getByRole("navigation", {
          name: "Primary navigation",
        }),
      ).toBeVisible();
    } else {
      await expect(navigationTrigger).toBeVisible();
      await navigationTrigger.focus();
      await expect(navigationTrigger).toBeFocused();
      await page.keyboard.press("Enter");
      const sheet = page.getByRole("dialog", { name: "Navigation" });
      await expect(sheet).toBeVisible();
      await expect(sheet.locator(":focus")).toHaveCount(1);
      await expect(
        sheet.getByRole("button", { name: "Workspace overview" }),
      ).toHaveAttribute("aria-current", "page");
      await page.keyboard.press("Escape");
      await expect(sheet).toBeHidden();
    }
  }

  await page.getByRole("button", { name: "Sign out of VerboFlex" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expectNoAuthInWebStorage(page);
});
