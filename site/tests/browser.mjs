// Uses the repository's existing Playwright installation; no new site dependencies.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { cpSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const require = createRequire(
  new URL("../../frontend/package.json", import.meta.url),
);
const { chromium, webkit, expect } = require("@playwright/test");
const temp = mkdtempSync(join(tmpdir(), "verboflex-site-"));
cpSync(
  fileURLToPath(new URL("../dist", import.meta.url)),
  join(temp, "verboflex"),
  { recursive: true },
);
const port = Number(process.env.SITE_TEST_PORT ?? 4175);
const origin = `http://127.0.0.1:${port}`;
const base = `${origin}/verboflex/`;
const server = spawn(
  "python3",
  [
    "-m",
    "http.server",
    String(port),
    "--bind",
    "127.0.0.1",
    "--directory",
    temp,
  ],
  { stdio: "ignore" },
);
let browser;
try {
  for (let i = 0; i < 50; i++) {
    if (server.exitCode !== null)
      throw new Error(`Preview server exited with ${server.exitCode}`);
    try {
      if ((await fetch(base)).ok) break;
    } catch {
      /* wait for startup */
    }
    if (i === 49) throw new Error("Preview server did not start");
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  const engine = process.env.SITE_BROWSER === "webkit" ? webkit : chromium;
  browser = await engine.launch();
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  const external = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400)
      errors.push(`${response.status()} ${response.url()}`);
  });
  page.on("request", (request) => {
    if (!request.url().startsWith(origin)) external.push(request.url());
  });
  await page.goto(base);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "The right words.In every product.",
  );
  const field = page.getByRole("textbox", {
    name: "Edit the Italian translation",
  });
  const save = page.getByRole("button", { name: "Save draft", exact: true });
  const approve = page.getByRole("button", {
    name: "Approve proposal",
    exact: true,
  });
  await expect(save).toBeDisabled();
  await field.fill("Conferma ordine");
  await save.click();
  await expect(page.getByRole("status")).toContainText("Demo draft saved");
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await expect(page.locator("[data-proposal]")).toHaveText("Conferma ordine");
  await approve.click();
  await expect(page.locator("[data-review-state]")).toContainText("Approved");
  await expect(approve).toBeDisabled();
  await page.getByRole("button", { name: "Translations", exact: true }).click();
  await field.fill("This translation exceeds the limit by a lot");
  await page.getByRole("button", { name: "Translations", exact: true }).focus();
  await expect(field).toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#demo-counter")).toContainText("over limit");
  assert.equal(
    await field.evaluate((el) => getComputedStyle(el).borderTopColor),
    "rgb(167, 40, 40)",
  );
  await save.click();
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await expect(approve).toBeDisabled();
  await expect(page.locator("[data-review-state]")).toContainText("shorten");
  await page.getByRole("button", { name: "Translations", exact: true }).click();
  await field.fill("e\u0301".repeat(24));
  await expect(field).toHaveAttribute("aria-invalid", "false");
  await expect(page.locator("#demo-counter")).toHaveText("24 / 24 characters");
  await field.fill("<img src=x onerror=alert(1)>");
  await save.click();
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await expect(page.locator("[data-proposal]")).toHaveText(
    "<img src=x onerror=alert(1)>",
  );
  assert.equal(await page.locator("[data-proposal] img").count(), 0);
  await page.getByRole("button", { name: "Start again" }).click();
  await expect(field).toHaveValue("Conferma");
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(page.getByText("2,940", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Coverage by language", { exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: "/tmp/verboflex-site-overview.png" });

  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ["", "guide.html"]) {
      await page.goto(base + path);
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
        `${width}px ${path}: horizontal overflow`,
      );
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(base);
  const menu = page.getByRole("button", { name: "Menu" });
  await menu.focus();
  await page.keyboard.press("Enter");
  await expect(menu).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("Escape");
  await expect(menu).toBeFocused();
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await menu.click();
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Guide", exact: true })
    .click();
  await expect(page).toHaveURL(base + "guide.html");
  await page
    .locator(".guide-toc")
    .getByRole("link", { name: "Codex and Claude Code" })
    .click();
  await expect(page).toHaveURL(base + "guide.html#mcp");
  await expect(page.locator("#mcp")).toContainText("codex mcp login");
  await page.emulateMedia({ reducedMotion: "reduce" });
  assert.equal(
    await page.evaluate(
      () => getComputedStyle(document.documentElement).scrollBehavior,
    ),
    "auto",
  );
  await page.goto(base);
  await page.screenshot({ path: "/tmp/verboflex-site-mobile-fold.png" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(base + "guide.html");
  await page.screenshot({ path: "/tmp/verboflex-site-guide.png" });
  const noScript = await browser.newPage({
    javaScriptEnabled: false,
    viewport: { width: 390, height: 844 },
  });
  await noScript.goto(base);
  await expect(
    noScript.getByRole("navigation", { name: "Main navigation" }),
  ).toBeVisible();
  await expect(
    noScript.getByText("This is an illustrative preview.", { exact: false }),
  ).toBeVisible();
  await noScript.goto(base + "guide.html");
  await expect(
    noScript.getByRole("heading", {
      name: "Use Codex or Claude Code with OAuth.",
    }),
  ).toBeVisible();
  assert.deepEqual(errors, [], "No page errors or failed resources");
  assert.deepEqual(external, [], "No third-party requests");
  console.log(
    "PASS: project subpath, demo draft/review/limits/reset, safe text rendering, grapheme count, 5 responsive widths, keyboard/mobile navigation, guide anchors, reduced motion, no-JS content and no external requests.",
  );
} finally {
  await browser?.close();
  server.kill();
  await new Promise((resolve) => {
    if (server.exitCode !== null) resolve();
    else server.once("exit", resolve);
  });
  rmSync(temp, { recursive: true, force: true });
}
