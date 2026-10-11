// Phase 5 extension for the disposable, built Docker stack owned by phase4_smoke.sh.
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
const require = createRequire(new URL("../frontend/package.json", import.meta.url));
const { chromium, expect } = require("@playwright/test");
const [mode, fixturePath, backend, frontend] = process.argv.slice(2);
const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
let browser;
let stage = "startup";
let lastStatus = 0;
const check = (value) => { if (!value) throw new Error("Contract rejected"); };
async function loginToken(role) {
  const user = fixture.users[role];
  const response = await fetch(`${backend}/api/v1/auth/token`, {
    method: "POST", signal: AbortSignal.timeout(10_000),
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: user.email, password: user.password }),
  });
  lastStatus = response.status; check(response.status === 200);
  return (await response.json()).access_token;
}
async function api(path, token, method = "GET", body) {
  const response = await fetch(`${backend}/api/v1${path}`, {
    method, signal: AbortSignal.timeout(10_000),
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  lastStatus = response.status;
  return { status: response.status, body: await response.json() };
}
async function loginPage(role, requireStream = false) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  page.setDefaultTimeout(20_000);
  const streamReady = requireStream
    ? page.waitForResponse((response) =>
        new URL(response.url()).pathname === "/api/v1/notifications/stream" &&
        response.status() === 200,
      )
    : null;
  await page.goto(`${frontend}/login`);
  await page.getByRole("textbox", { name: "Email" }).fill(fixture.users[role].email);
  await page.getByLabel("Password", { exact: true }).fill(fixture.users[role].password);
  await page.getByRole("button", { name: "Sign in to VerboFlex", exact: true }).click();
  await expect(page.getByRole("button", { name: /Notifications/ })).toBeVisible();
  await streamReady;
  return page;
}
try {
  check(mode === "verify");
  browser = await chromium.launch({ headless: true });
  const group = fixture.mappings[0].group;
  const authorToken = await loginToken("admin");
  const mentions = await api("/users/mentions?q=Smoke", authorToken);
  check(mentions.status === 200 && mentions.body.length > 0);
  const recipient = mentions.body.find((person) => person.email === fixture.users.product_manager_reviewer.email);
  check(recipient);
  const recipientToken = await loginToken("product_manager_reviewer");

  stage = "recipient-stream";
  const recipientPage = await loginPage("product_manager_reviewer", true);
  const initialBell = recipientPage.getByRole("button", { name: "Notifications, no unread notifications" });
  await expect(initialBell).toBeVisible();
  await recipientPage.evaluate(({ backend, token }) => {
    const state = {};
    state.ready = new Promise((resolve) => { state.markReady = resolve; });
    state.event = (async () => {
      const response = await fetch(`${backend}/api/v1/notifications/stream`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      state.markReady(response.status);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) throw new Error("SSE ended before invalidation");
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          if (!block.includes("event: notification-invalidation")) continue;
          const data = block.split("\n").find((line) => line.startsWith("data: "));
          if (data) return JSON.parse(data.slice(6));
        }
      }
    })();
    globalThis.__phase5SseState = state;
  }, { backend, token: recipientToken });
  check((await recipientPage.evaluate(() => globalThis.__phase5SseState.ready)) === 200);

  stage = "proposal-browser";
  const translatorPage = await loginPage("admin");
  stage = "proposal-detail";
  await translatorPage.goto(`${frontend}/translations/${group}`);
  stage = "proposal-edit";
  await translatorPage.getByRole("button", { name: "Edit translation" }).click();
  const unicode = "Phase 5 smoke 家族 مرحبا";
  stage = "proposal-fill";
  await translatorPage.getByRole("textbox", { name: "Proposed translation" }).fill(unicode);
  stage = "proposal-save";
  await translatorPage.getByRole("button", { name: "Save translation" }).click();
  stage = "proposal-render";
  await expect(translatorPage.getByRole("region", { name: "Pending proposal" })).toContainText(unicode);
  stage = "proposal-reload";
  await translatorPage.reload();
  await expect(translatorPage.getByRole("region", { name: "Pending proposal" })).toContainText(unicode);

  stage = "comment-browser";
  const composer = translatorPage.getByRole("textbox", { name: "Add a comment" });
  await composer.fill("Phase 5 smoke @Smok");
  await composer.pressSequentially("e");
  await expect(translatorPage.getByRole("listbox", { name: "Mention a person" })).toBeVisible();
  const option = translatorPage.getByRole("option").filter({ hasText: recipient.email });
  await option.click();
  await translatorPage.getByRole("button", { name: "Post comment" }).click();
  await expect(translatorPage.getByText(/Phase 5 smoke @Smoke principal/)).toBeVisible();
  await translatorPage.reload();
  await expect(translatorPage.getByText(/Phase 5 smoke @Smoke principal/)).toBeVisible();

  stage = "notification-durable";
  const createdUnread = await api("/notifications/unread-count", recipientToken);
  check(createdUnread.status === 200 && createdUnread.body.unread_count === 1);
  stage = "post-commit-invalidation";
  const invalidation = await recipientPage.evaluate(() => Promise.race([
    globalThis.__phase5SseState.event,
    new Promise((_, reject) => setTimeout(() => reject(new Error("SSE timeout")), 20_000)),
  ]));
  check(
    invalidation.kind === "notifications_changed" &&
      typeof invalidation.id === "string" &&
      Object.keys(invalidation).sort().join(",") === "id,kind",
  );
  stage = "live-reconciliation";
  await recipientPage.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect(recipientPage.getByRole("button", { name: "Notifications, 1 unread notification" })).toBeVisible({ timeout: 20_000 });
  await recipientPage.getByRole("button", { name: "Notifications, 1 unread notification" }).click();
  const notification = recipientPage
    .getByRole("article", { name: /Notification from/ })
    .getByRole("menuitem")
    .first();
  await expect(notification).toBeVisible();
  await notification.click();
  await expect(recipientPage.getByTestId(/exact-comment-/)).toBeFocused();
  await expect(recipientPage.getByRole("button", { name: "Notifications, no unread notifications" })).toBeVisible();

  stage = "rest-authority";
  const unread = await api("/notifications/unread-count", recipientToken);
  check(unread.status === 200 && unread.body.unread_count === 0);
  console.log("phase5 verify: PASS (proposal=1, comment=1, authenticated-stream=1, rest-reconciliation=1)");
} catch {
  console.error(`phase5 smoke failed: ${stage}-http-${lastStatus}`);
  process.exitCode = 1;
} finally {
  await browser?.close();
}
