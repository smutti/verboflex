import { expect, test } from "@playwright/test";

const principal = {
  id: "73f123f7-ebad-4dad-8b5d-dcc3214b3b06",
  email: "session-test@example.com",
  display_name: "Session Test",
  roles: ["translator"],
  must_change_password: false,
};
const authority = (version: number) => ({
  access_token: `synthetic-bearer-${version}`,
  token_type: "bearer",
  expires_in: 900,
  must_change_password: false,
});

test("renews an idle session without replacing its form, then redirects only after revocation", async ({
  page,
}) => {
  let version = 0;
  let revoked = false;
  const bearerRequests: string[] = [];
  await page.clock.install({ time: new Date("2026-10-14T12:00:00Z") });
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const bearer = route.request().headers().authorization;
    if (bearer) bearerRequests.push(bearer);
    if (path === "/api/v1/auth/refresh") {
      await route.fulfill({
        status: revoked ? 401 : 200,
        json: revoked
          ? { detail: "Invalid refresh session" }
          : authority(++version),
      });
    } else if (path === "/api/v1/users/me") {
      await route.fulfill({ json: principal });
    } else {
      // Unrelated shell services are deliberately unavailable in this fixture.
      await route.fulfill({
        status: 503,
        json: { detail: "Synthetic service unavailable" },
      });
    }
  });
  await page.goto("/profile");
  await expect(
    page.getByRole("heading", { name: "Profile", exact: true }),
  ).toBeVisible();
  expect(version).toBe(1);
  await page
    .getByLabel("Current password", { exact: true })
    .fill("synthetic unsaved input");

  await page.clock.setSystemTime(new Date("2026-10-14T12:16:00Z"));
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect.poll(() => version).toBe(2);
  await expect
    .poll(() => bearerRequests.includes("Bearer synthetic-bearer-2"))
    .toBe(true);
  await expect(page).toHaveURL(/\/profile$/);
  await expect(
    page.getByLabel("Current password", { exact: true }),
  ).toHaveValue("synthetic unsaved input");
  await expect(
    page.getByRole("button", { name: "Sign in to VerboFlex" }),
  ).toHaveCount(0);

  revoked = true;
  await page.clock.setSystemTime(new Date("2026-10-14T12:32:00Z"));
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect(
    page.getByRole("button", { name: "Sign in to VerboFlex" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test("initial service failure offers a working retry instead of login", async ({
  page,
}) => {
  let unavailable = true;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/refresh" && !unavailable) {
      await route.fulfill({ json: authority(1) });
    } else if (path === "/api/v1/users/me") {
      await route.fulfill({ json: principal });
    } else {
      await route.fulfill({
        status: 503,
        json: { detail: "Synthetic service unavailable" },
      });
    }
  });
  await page.goto("/profile");
  await expect(page.getByRole("alert")).toContainText(
    "We could not check your session",
  );
  await expect(
    page.getByRole("button", { name: "Sign in to VerboFlex" }),
  ).toHaveCount(0);
  unavailable = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { name: "Profile", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/profile$/);
});

test("two tabs serialize refresh cookie rotation with browser Web Locks", async ({
  context,
}) => {
  let active = 0;
  let maximum = 0;
  let version = 0;
  await context.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/refresh") {
      active += 1;
      maximum = Math.max(maximum, active);
      await new Promise((resolve) => setTimeout(resolve, 100));
      active -= 1;
      await route.fulfill({ json: authority(++version) });
    } else if (path === "/api/v1/users/me") {
      await route.fulfill({ json: principal });
    } else {
      await route.fulfill({
        status: 503,
        json: { detail: "Synthetic service unavailable" },
      });
    }
  });
  const first = await context.newPage();
  const second = await context.newPage();
  await Promise.all([first.goto("/profile"), second.goto("/profile")]);
  await expect(
    first.getByRole("heading", { name: "Profile", exact: true }),
  ).toBeVisible();
  await expect(
    second.getByRole("heading", { name: "Profile", exact: true }),
  ).toBeVisible();
  expect(version).toBe(2);
  expect(maximum).toBe(1);
});
