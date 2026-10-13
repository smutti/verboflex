import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
const require = createRequire(
  new URL("../frontend/package.json", import.meta.url),
);
const { chromium, expect: baseExpect } = require("@playwright/test");
// Cold disposable Docker services can take longer than Playwright's default 5s.
const expect = baseExpect.configure({ timeout: 15000 });
const [mode, fixturePath, backend, frontend, evidence] = process.argv.slice(2);
const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
let stage = "startup";
const browser = await chromium.launch({ headless: true });
const requests = new WeakMap();
const check = (condition) => {
  if (!condition) throw new Error("Contract rejected");
};
async function token(role) {
  const user = fixture.users[role];
  const response = await fetch(`${backend}/api/v1/auth/token`, {
    method: "POST",
    signal: AbortSignal.timeout(10000),
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      username: user.email,
      password: user.password,
    }),
  });
  if (!response.ok)
    console.log(`dashboard HTTP: /api/v1/auth/token ${response.status}`);
  check(response.status === 200);
  return (await response.json()).access_token;
}
async function api(path, bearer, method = "GET", body) {
  const response = await fetch(`${backend}/api/v1${path}`, {
    method,
    signal: AbortSignal.timeout(10000),
    headers: {
      Authorization: `Bearer ${bearer}`,
      "Content-Type": "application/json",
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok)
    console.log(`dashboard HTTP: /api/v1${path} ${response.status}`);
  check(response.ok);
  if (response.status === 204) return null;
  return response.json();
}
async function login(role) {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  });
  page.setDefaultTimeout(20000);
  requests.set(page, []);
  page.on("request", (request) =>
    requests.get(page).push(new URL(request.url()).pathname),
  );
  page.on("response", (response) => {
    if (response.url().startsWith(backend) && response.status() >= 400)
      console.log(
        `dashboard HTTP: ${new URL(response.url()).pathname} ${response.status()}`,
      );
  });
  await page.goto(`${frontend}/login`);
  await page
    .getByRole("textbox", { name: "Email" })
    .fill(fixture.users[role].email);
  await page
    .getByLabel("Password", { exact: true })
    .fill(fixture.users[role].password);
  await page
    .getByRole("button", { name: "Sign in to VerboFlex", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
  return page;
}

async function home(page) {
  await page.goto(frontend);
  await expect(
    page.getByRole("region", { name: "My recent activity" }),
  ).toBeVisible();
}
async function mention(bearer, roles, bodyPrefix = "Please review ") {
  let body = bodyPrefix;
  const mentions = roles.map((role) => {
    const user = fixture.users[role];
    const display_text = `@${user.name}`;
    const start_utf16 = body.length;
    body += display_text + " ";
    return {
      user_id: user.id,
      display_text,
      start_utf16,
      end_utf16: start_utf16 + display_text.length,
    };
  });
  return api(`/translations/${fixture.group}/comments`, bearer, "POST", {
    body,
    mentions,
  });
}
async function noOverflow(page) {
  if (mode === "product-summary") {
    const layout = await page.evaluate(() => ({
      width: window.innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      elements: [...document.querySelectorAll("body *")].flatMap((element) => {
        const rect = element.getBoundingClientRect();
        return rect.right > window.innerWidth
          ? [
              {
                tag: element.tagName,
                className: element.className,
                right: rect.right,
                width: rect.width,
              },
            ]
          : [];
      }),
    }));
    writeFileSync(
      `${evidence}/product-summary-layout.json`,
      JSON.stringify(layout, null, 2),
    );
  }
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  );
}

async function full(page, translatorToken) {
  stage = "initial-event-destinations";
  await home(page);
  await page
    .getByRole("region", { name: "Project updates" })
    .getByRole("link", { name: "Current import completed" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Strings", exact: true }),
  ).toBeVisible();
  await home(page);
  await page
    .getByRole("link", { name: "Submitted a change set", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Change set", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Change set unavailable", { exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Change set", exact: true }),
  ).toBeVisible();

  stage = "reviewer-and-admin-real-login";
  const reviewerToken = await token("product_manager_reviewer");
  const adminToken = await token("admin");
  const reviewer = await login("product_manager_reviewer");
  const admin = await login("admin");
  await expect(
    admin.getByRole("heading", { name: "Project statistics" }),
  ).toBeVisible();
  await expect(admin.getByText("4 loaded users")).toBeVisible();
  await expect(
    reviewer.getByRole("region", { name: "My recent activity" }),
  ).toContainText("No recent activity yet");
  const stream = reviewer.waitForResponse(
    (response) =>
      response.url().endsWith("/notifications/stream") &&
      response.status() === 200,
  );
  await reviewer.reload();
  await stream;
  await expect(
    reviewer.getByRole("button", {
      name: "Notifications, no unread notifications",
    }),
  ).toBeVisible();

  stage = "real-review-comments-and-mentions";
  await api(
    `/translations/${fixture.group}/proposal/state`,
    reviewerToken,
    "POST",
    { target_state: "approved", expected_version: 1 },
  );
  const comment = await mention(translatorToken, [
    "product_manager_reviewer",
    "admin",
  ]);
  await api(
    `/translations/${fixture.group}/comments/${comment.id}`,
    translatorToken,
    "PUT",
    { body: "Updated review note", expected_version: 1, mentions: [] },
  );
  const removed = await mention(
    translatorToken,
    ["product_manager_reviewer"],
    "Temporary note ",
  );
  await api(
    `/translations/${fixture.group}/comments/${removed.id}`,
    adminToken,
    "DELETE",
  );
  await expect(
    reviewer.getByRole("button", {
      name: "Notifications, 2 unread notifications",
    }),
  ).toBeVisible();
  const inbox = reviewer.getByRole("region", {
    name: "Notifications",
    exact: true,
  });
  await expect(inbox.getByText("2 unread")).toBeVisible();
  await inbox.getByRole("button", { name: "Refresh notifications" }).click();
  await expect(inbox.getByText("Comment no longer available")).toBeVisible();
  check(
    (await api("/notifications/unread-count", reviewerToken)).unread_count ===
      2,
  );

  stage = "explicit-read-shared-owner";
  const removedRow = inbox
    .getByRole("listitem")
    .filter({ hasText: "Comment no longer available" });
  await expect(removedRow.getByRole("link")).toHaveCount(0);
  await removedRow.getByRole("button", { name: "Mark as read" }).click();
  await expect(inbox.getByText("1 unread")).toBeVisible();
  await expect(
    reviewer.getByRole("button", {
      name: "Notifications, 1 unread notification",
    }),
  ).toBeVisible();
  check(
    (await api("/notifications/unread-count", adminToken)).unread_count === 1,
  );
  await inbox
    .getByRole("link", { name: /Mira Translator mentioned you/ })
    .click();
  await expect(
    reviewer.getByTestId(`exact-comment-${comment.id}`),
  ).toBeFocused();
  await expect(
    reviewer.getByRole("button", {
      name: "Notifications, no unread notifications",
    }),
  ).toBeVisible();

  stage = "domain-provenance-and-access";
  await home(page);
  await home(reviewer);
  const mine = reviewer.getByRole("region", { name: "My recent activity" });
  await expect(
    mine.getByRole("link", {
      name: /Changed review state from draft to approved/,
    }),
  ).toBeVisible();
  await expect(
    mine.getByRole("link", { name: /Saved a proposal/ }),
  ).toHaveCount(0);
  const project = reviewer.getByRole("region", { name: "Project updates" });
  await expect(
    project.getByRole("link", { name: /Saved a proposal/ }),
  ).toBeVisible();
  await expect(
    project.getByRole("link", { name: /Edited a comment/ }),
  ).toBeVisible();
  await expect(
    project.getByRole("link", { name: /Removed a comment/ }),
  ).toBeVisible();
  const events = await api("/dashboard", reviewerToken);
  check(
    events.my_activity.items.every(
      (event) => event.actor.id === fixture.users.product_manager_reviewer.id,
    ),
  );
  check(
    events.project_updates.items.every(
      (event) => !fixture.excluded_products.includes(event.product.id),
    ),
  );
  check(
    events.project_updates.items.every(
      (event, index, all) =>
        !index || event.occurred_at <= all[index - 1].occurred_at,
    ),
  );
  const denied = await fetch(
    `${backend}/api/v1/products/${fixture.excluded_products[0]}/change-sets`,
    { headers: { Authorization: `Bearer ${reviewerToken}` } },
  );
  check([403, 404].includes(denied.status));

  stage = "desktop-mobile-and-keyboard";
  await mention(reviewerToken, ["translator"], "A new review is ready ");
  await expect(
    page.getByRole("button", { name: "Notifications, 1 unread notification" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Refresh activity" }).click();
  await expect(
    page.getByRole("region", { name: "Project updates" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Refresh activity" }).focus();
  await page.keyboard.press("Tab");
  await expect(
    page
      .getByRole("region", { name: "Notifications", exact: true })
      .getByRole("button", { name: "Refresh notifications" }),
  ).toBeFocused();
  await noOverflow(page);
  await page.screenshot({
    path: `${evidence}/dashboard-desktop.png`,
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await noOverflow(page);
  await page.screenshot({
    path: `${evidence}/dashboard-mobile.png`,
    fullPage: true,
  });
  const personalLink = page
    .getByRole("region", { name: "My recent activity" })
    .getByRole("link", { name: /Edited a comment/ })
    .first();
  await personalLink.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId(`exact-comment-${comment.id}`)).toBeFocused();
  await page.reload();
  await expect(page.getByTestId(`exact-comment-${comment.id}`)).toBeFocused();

  stage = "isolated-error-retry";
  await home(reviewer);
  await reviewer.route("**/api/v1/dashboard", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"Dashboard unavailable"}',
    }),
  );
  await reviewer.getByRole("button", { name: "Refresh activity" }).click();
  await expect(
    reviewer.getByText("Activity could not be loaded. Please try again."),
  ).toBeVisible();
  await expect(
    reviewer.getByRole("region", { name: "Notifications", exact: true }),
  ).toBeVisible();
  await reviewer.unroute("**/api/v1/dashboard");
  await reviewer.getByRole("button", { name: "Retry activity" }).click();
  await expect(mine).toBeVisible();

  stage = "account-switch-and-empty-role";
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "Sign out of VerboFlex" }).click();
  await expect(page.getByRole("textbox", { name: "Email" })).toBeVisible();
  await page
    .getByRole("textbox", { name: "Email" })
    .fill(fixture.users.viewer.email);
  await page
    .getByLabel("Password", { exact: true })
    .fill(fixture.users.viewer.password);
  await page
    .getByRole("button", { name: "Sign in to VerboFlex", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "My recent activity" }),
  ).toContainText("No recent activity yet");
  await expect(
    page.getByRole("region", { name: "Notifications", exact: true }),
  ).toContainText("No notifications yet");
  await expect(
    page.getByRole("region", { name: "Project updates" }),
  ).toContainText("Mobile workspace");
  await expect(
    page.getByRole("heading", { name: "Project statistics" }),
  ).toHaveCount(0);
  check(!requests.get(page).some((path) => path.startsWith("/api/v1/admin/")));
  check(
    !requests.get(reviewer).some((path) => path.startsWith("/api/v1/admin/")),
  );

  stage = "bounded-latest-events";
  let version = 2;
  for (let index = 0; index < 11; index++) {
    const proposal = await api(
      `/translations/${fixture.group}/proposal`,
      translatorToken,
      "PUT",
      {
        ...fixture.proposal,
        values: fixture.proposal.values.map((value) => ({
          ...value,
          proposed_text: `Dashboard revision ${index}`,
        })),
        expected_version: version,
      },
    );
    version = proposal.version;
  }
  const bounded = await api("/dashboard", translatorToken);
  check(
    bounded.my_activity.items.length === 10 && bounded.my_activity.has_more,
  );
  check(
    bounded.project_updates.items.length === 10 &&
      bounded.project_updates.has_more,
  );
  await home(page);
  await expect(
    page.getByText(
      "Showing the latest 10 events. Open a workspace for more context.",
    ),
  ).toBeVisible();
  console.log(
    "full dashboard browser: PASS (four roles, real actions, SSE/read ownership, exact links, account switch, recovery, bounds, keyboard, desktop/mobile)",
  );
}
async function productSummary() {
  stage = "summary-real-login";
  const page = await login("admin");
  const productId = fixture.summary_product;
  const overview = `${frontend}/admin/products/${productId}/overview`;
  stage = "summary-exact-metrics";
  await page.goto(overview);
  await expect(
    page.getByRole("heading", { name: "Atlas Mobile", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Source strings", exact: true })
      .locator("p")
      .first(),
  ).toHaveText("2");
  await expect(
    page
      .getByRole("region", { name: "Translated", exact: true })
      .locator("p")
      .first(),
  ).toHaveText("3");
  await expect(
    page.getByRole("region", { name: "Translated", exact: true }),
  ).toContainText("of 4 target strings");
  await expect(
    page
      .getByRole("region", { name: "Missing or unfinished", exact: true })
      .locator("p")
      .first(),
  ).toHaveText("1");
  await expect(
    page
      .getByRole("region", { name: "Target languages", exact: true })
      .locator("p")
      .first(),
  ).toHaveText("2");
  await expect(
    page.getByRole("progressbar", {
      name: "Overall translation coverage",
      exact: true,
    }),
  ).toHaveAttribute("aria-valuenow", "75");
  await expect(
    page.getByRole("tab", { name: "Published", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("tab", { name: "Draft", exact: true }),
  ).toHaveCount(0);
  const rows = page
    .getByRole("table", { name: "Translation coverage by language" })
    .getByRole("row");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(1).getByRole("rowheader")).toHaveText("Vietnamesevi");
  await expect(rows.nth(1).getByRole("cell").nth(0)).toHaveText("1 / 2");
  await expect(rows.nth(1).getByRole("cell").nth(1)).toHaveText("1");
  await expect(rows.nth(2).getByRole("rowheader")).toHaveText("Englishen");
  await expect(rows.nth(2).getByRole("cell").nth(0)).toHaveText("2 / 2");
  await noOverflow(page);
  await page.screenshot({
    path: `${evidence}/product-summary-desktop.png`,
    fullPage: true,
  });
  stage = "summary-mobile";
  await page.setViewportSize({ width: 390, height: 844 });
  await noOverflow(page);
  await page.screenshot({
    path: `${evidence}/product-summary-mobile.png`,
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  stage = "summary-language-navigation";
  const languageRequest = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/translations/keys" &&
      url.searchParams.get("product_id") === productId &&
      url.searchParams.get("language") === "vi" &&
      response.status() === 200
    );
  });
  await rows
    .nth(1)
    .getByRole("link", { name: "Open language", exact: true })
    .click();
  const languageResponse = await languageRequest;
  const languageData = await languageResponse.json();
  check(
    languageData.items.length === 1 &&
      languageData.items.every(
        (item) => item.product_id === productId && item.language === "vi",
      ),
  );
  await expect(page).toHaveURL(
    `${frontend}/products/${productId}/strings?language=vi`,
  );
  await expect(
    page.getByRole("button", {
      name: "Remove Matching language: vi",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Product", exact: true }),
  ).toHaveCount(0);
  stage = "summary-language-reload";
  const reloadRequest = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/translations" &&
      url.searchParams.get("product_id") === productId &&
      url.searchParams.get("language") === "vi" &&
      response.status() === 200
    );
  });
  await page.reload();
  await reloadRequest;
  await expect(
    page.getByRole("button", {
      name: "Remove Matching language: vi",
      exact: true,
    }),
  ).toBeVisible();
  stage = "summary-language-history";
  for (const action of ["change", "clear"]) {
    if (action === "change") {
      await page.getByRole("button", { name: /^Filter/ }).click();
      await page
        .getByRole("combobox", { name: "Matching language", exact: true })
        .click();
      await page
        .getByRole("option", { name: "Italian (it)", exact: true })
        .click();
      await page.getByRole("button", { name: "Apply filters" }).click();
    } else {
      await page
        .getByRole("button", { name: "Clear filters", exact: true })
        .click();
    }
    const query = page.getByRole("textbox", {
      name: "Search keys and translations",
      exact: true,
    });
    await query.fill("status.precision");
    await query.press("Enter");
    const detailLink = page.locator(
      `a[data-translation-group-id="${fixture.summary_group}"]`,
    );
    await expect(detailLink).toBeVisible();
    await detailLink.click();
    await expect(
      page.getByRole("heading", { name: "Translation details", exact: true }),
    ).toBeVisible();
    await page.goBack();
    await expect(query).toHaveValue("status.precision");
    if (action === "change")
      await expect(
        page.getByRole("button", { name: "Remove Matching language: it" }),
      ).toBeVisible();
    else
      await expect(
        page.getByRole("button", { name: /^Remove Matching language:/ }),
      ).toHaveCount(0);
    await expect(detailLink).toBeVisible();
    await expect(detailLink).toBeFocused();
  }
  stage = "summary-configuration";
  await page.goto(overview);
  await page
    .getByRole("link", { name: "Configure product", exact: true })
    .click();
  await expect(page).toHaveURL(`${frontend}/admin/products/${productId}/edit`);
  await expect(
    page.getByRole("textbox", { name: "Name", exact: true }),
  ).toHaveValue("Atlas Mobile");
  stage = "summary-no-data";
  await page.goto(
    `${frontend}/admin/products/${fixture.empty_product}/overview`,
  );
  await expect(
    page.getByText("No successful imports yet.", { exact: false }),
  ).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveCount(0);
  await expect(
    page.getByRole("region", { name: "Translation coverage", exact: true }),
  ).toContainText("—");
  stage = "summary-retry";
  const summaryPath = `**/api/v1/admin/products/${productId}/summary`;
  await page.route(
    summaryPath,
    (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Summary unavailable" }),
      }),
    { times: 1 },
  );
  await page.goto(overview);
  await expect(
    page.getByText("Translation summary unavailable", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Configure product", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Source strings", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Retry summary", exact: true })
    .click();
  await expect(
    page.getByRole("progressbar", {
      name: "Overall translation coverage",
      exact: true,
    }),
  ).toHaveAttribute("aria-valuenow", "75");
  stage = "summary-inactive";
  await page
    .getByRole("button", { name: "Deactivate product", exact: true })
    .click();
  await page
    .getByRole("alertdialog")
    .getByRole("button", { name: "Deactivate product", exact: true })
    .click();
  await expect(
    page.getByText(
      "The strings workspace is available only for active products.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open language", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("progressbar", {
      name: "Overall translation coverage",
      exact: true,
    }),
  ).toHaveAttribute("aria-valuenow", "75");
  await page.reload();
  await expect(
    page.getByText(
      "The strings workspace is available only for active products.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open language", exact: true }),
  ).toHaveCount(0);
  await expect(
    page
      .getByRole("region", { name: "Translated", exact: true })
      .locator("p")
      .first(),
  ).toHaveText("3");
  await page.close();
  console.log(
    "product summary browser: PASS (real metrics, missing-first order, language request/reload, changed/cleared history, configuration, no-data, recovery, inactive view, desktop/mobile)",
  );
}

async function multilingualWorkspace() {
  const progress = (name) => {
    stage = "multilingual-" + name;
    writeFileSync(
      evidence + "/multilingual-progress.json",
      JSON.stringify({ stage }),
    );
  };
  progress("login");
  const bearer = await token("translator");
  const reviewerToken = await token("product_manager_reviewer");
  const page = await login("translator");
  const path = "/products/" + fixture.multilingual_product + "/strings";
  const group = (index, language) =>
    fixture.multilingual_groups[index + ":" + language];
  const detail = (index, language) =>
    api("/translations/" + group(index, language), bearer);
  const field = page.getByRole("textbox", {
    name: "Proposed translation",
    exact: true,
  });
  const edit = (index, language) =>
    page.getByRole("button", {
      name:
        "Edit translation for key-" +
        String(index).padStart(3, "0") +
        " (" +
        language +
        ")",
      exact: true,
    });
  const context = page.getByRole("complementary", {
    name: "Selected translation context",
  });
  const closeContext = () =>
    page.getByRole("button", { name: "Close translation context" }).click();
  const search = async (text) => {
    await page
      .getByRole("textbox", { name: "Search keys and translations" })
      .fill(text);
    await page
      .getByRole("textbox", { name: "Search keys and translations" })
      .press("Enter");
  };
  const filter = () =>
    page.getByRole("button", { name: /^Filter(?: \(|$)/ }).click();
  const choose = async (label, value) => {
    await page.getByRole("combobox", { name: label, exact: true }).click();
    await page.getByRole("option", { name: value, exact: true }).click();
  };
  const capture = async (name) => {
    if (name.endsWith("rows"))
      await page
        .getByRole("heading", { name: "Translation results", exact: true })
        .evaluate((element) => element.scrollIntoView({ block: "start" }));
    if (name.endsWith("editor"))
      await field.evaluate((element) =>
        element.closest("[data-group-id]").scrollIntoView({ block: "center" }),
      );
    await noOverflow(page);
    await page.screenshot({
      path: evidence + "/multilingual-" + name + ".png",
    });
  };
  const keyResponses = [];
  page.on("response", async (response) => {
    if (
      new URL(response.url()).pathname.endsWith("/translations/keys") &&
      response.status() === 200
    ) {
      const body = await response.json().catch(() => null);
      if (body) keyResponses.push({ url: response.url(), body });
    }
  });
  await page.goto(frontend + path);
  await expect(edit(0, "fr")).toBeVisible();
  await expect(page.getByText("key-000", { exact: true })).toHaveCount(1);
  await expect(
    page.getByRole("heading", { name: "Multilingual", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Product in focus", { exact: true })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("link", { name: "Change product", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Multilingual", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(context).toHaveCount(0);
  check(keyResponses[0].body.items.length === 50);
  check(keyResponses[0].body.items.every((key) => key.slots.length === 3));
  check(
    new Set(keyResponses[0].body.items.map((key) => key.translation_key_id))
      .size === 50,
  );
  await capture("desktop-rows");

  progress("independent-locale-writes");
  await edit(0, "fr").click();
  await expect(field).toHaveValue("");
  await field.fill("Cancelled French");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  check((await detail(0, "fr")).pending_change === null);
  await edit(0, "fr").click();
  await field.fill("Bonjour multilingual");
  await edit(0, "it").click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await page.getByRole("button", { name: "Keep editing", exact: true }).click();
  await expect(field).toHaveValue("Bonjour multilingual");
  await page.getByRole("button", { name: /^Languages/ }).click();
  await page.getByRole("checkbox", { name: "French (fr)" }).uncheck();
  await page.getByRole("button", { name: "Apply languages" }).click();
  await page.getByRole("button", { name: "Keep editing", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Languages (3)" }),
  ).toBeVisible();
  await capture("desktop-editor");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect
    .poll(async () => (await detail(0, "fr")).pending_change?.values[0].text)
    .toBe("Bonjour multilingual");
  await edit(0, "it").click();
  const italianField = page
    .locator('[data-group-id="' + group(0, "it") + '"]')
    .getByRole("textbox", { name: "Proposed translation", exact: true });
  await expect(italianField).toHaveValue("it 0");
  await italianField.fill("Ciao multilingual");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect
    .poll(async () => (await detail(0, "it")).pending_change?.values[0].text)
    .toBe("Ciao multilingual");
  await expect(field).toHaveCount(0);
  const french = await detail(0, "fr");
  const italian = await detail(0, "it");
  check(
    french.values[0].translated_text === "" &&
      italian.values[0].translated_text === "it 0",
  );
  check(
    french.pending_change.values[0].text === "Bonjour multilingual" &&
      italian.pending_change.values[0].text === "Ciao multilingual",
  );

  progress("source-and-plural");
  await edit(0, "en").click();
  await expect(field).toHaveValue("en 0");
  await field.fill("Updated base source");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect
    .poll(async () => (await detail(0, "en")).pending_change?.values[0].text)
    .toBe("Updated base source");
  check((await detail(0, "en")).values[0].source_text === "en 0");
  await expect(field).toHaveCount(0);
  await search("key-002");
  await expect(
    page.getByRole("button", { name: "Add translation", exact: true }),
  ).toBeVisible();
  await expect(edit(2, "it")).toHaveCount(0);
  await search("key-010");
  await edit(10, "fr").click();
  await expect(
    page.getByRole("textbox", { name: /quantity (one|other)/ }),
  ).toHaveCount(2);
  await page
    .getByRole("textbox", { name: "quantity one", exact: true })
    .fill("Un élément");
  await page
    .getByRole("textbox", { name: "quantity other", exact: true })
    .fill("Des éléments");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect
    .poll(async () => (await detail(10, "fr")).pending_change?.values.length)
    .toBe(2);
  await expect(
    page.getByRole("textbox", { name: /quantity (one|other)/ }),
  ).toHaveCount(0);

  progress("advanced-filters");
  await search("it 60");
  await expect(edit(60, "it")).toBeVisible();
  await expect(edit(60, "fr")).toBeVisible();
  await expect
    .poll(() =>
      keyResponses
        .at(-1)
        .body.items[0].slots.filter((slot) => slot.matches_filters)
        .map((slot) => slot.language),
    )
    .toEqual(["it"]);
  await filter();
  await choose("Imported approval state", "Approved");
  const beforeCancel = keyResponses.length;
  await capture("desktop-filters");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  check(keyResponses.length === beforeCancel);
  await filter();
  await choose("Imported approval state", "Approved");
  await choose("Imported length status", "No max length");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(edit(60, "it")).toBeVisible();
  await expect
    .poll(() => new URL(keyResponses.at(-1).url).searchParams.get("state"))
    .toBe("approved");
  await page
    .getByRole("button", { name: "Remove Imported state: Approved" })
    .click();
  await page
    .getByRole("button", { name: "Clear filters", exact: true })
    .click();
  await expect(edit(0, "fr")).toBeVisible();
  await filter();
  await page.getByRole("button", { name: "Needs review", exact: true }).click();
  await expect(edit(0, "fr")).toBeVisible();
  await expect
    .poll(() =>
      new URL(keyResponses.at(-1).url).searchParams.get("work_status"),
    )
    .toBe("needs_review");
  await page
    .getByRole("button", { name: "Clear filters", exact: true })
    .click();
  await filter();
  await page
    .getByRole("button", { name: "Needs translation", exact: true })
    .click();
  await expect(edit(1, "fr")).toBeVisible();
  await expect(edit(1, "it")).toBeVisible();
  await expect(page.getByText("key-002", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Add translation", exact: true }),
  ).toBeVisible();
  await expect
    .poll(() =>
      keyResponses
        .at(-1)
        .body.items.find((item) => item.raw_key === "key-002")
        ?.slots.filter((slot) => slot.matches_filters)
        .map((slot) => [slot.language, slot.kind]),
    )
    .toEqual([["it", "absent"]]);
  await capture("needs-translation-including-absent");
  await page
    .getByRole("button", { name: "Clear filters", exact: true })
    .click();
  await filter();
  await page
    .getByRole("button", { name: "Source changed", exact: true })
    .click();
  await expect(edit(0, "fr")).toBeVisible();
  await page
    .getByRole("button", { name: "Clear filters", exact: true })
    .click();

  progress("languages-preferences-back");
  await page.getByRole("button", { name: /^Languages/ }).click();
  await page.getByRole("checkbox", { name: "Italian (it)" }).uncheck();
  await page.getByRole("button", { name: "Apply languages" }).click();
  await expect(
    page.getByRole("button", { name: "Languages (2)" }),
  ).toBeVisible();
  await expect(edit(0, "it")).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Languages (2)" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /^Languages/ }).click();
  await page.getByRole("button", { name: "Use default languages" }).click();
  await expect(edit(0, "it")).toBeVisible();
  await page.goto(frontend + path + "?language=it");
  await expect(
    page.getByRole("button", { name: "Bilingual", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("button", { name: "Remove Matching language: it" }),
  ).toBeVisible();
  await search("key-060");
  await page
    .getByRole("link", { name: "Open details for key-060 (it)", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Translation details", exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole("textbox", { name: "Search keys and translations" }),
  ).toHaveValue("key-060");
  await expect(edit(60, "it")).toBeVisible();
  await page
    .getByRole("button", { name: "Clear filters", exact: true })
    .click();
  await page.getByRole("button", { name: "Multilingual", exact: true }).click();

  progress("comments-context-refresh");
  await search("key-000");
  const comments = page.getByRole("button", {
    name: /^Comments for key-000 \(fr\),/,
  });
  await comments.click();
  await expect(
    context.getByText("key-000 · fr", { exact: true }),
  ).toBeVisible();
  const commentField = context.getByRole("textbox", {
    name: "Add a comment",
    exact: true,
  });
  await commentField.fill("Unsent French discussion");
  await closeContext();
  await page
    .getByRole("button", { name: /^Comments for key-000 \(it\),/ })
    .click();
  await page.getByRole("button", { name: "Keep editing", exact: true }).click();
  await comments.click();
  await expect(commentField).toHaveValue("Unsent French discussion");
  await capture("desktop-context");
  await closeContext();
  const beforeExternal = await detail(0, "fr");
  const payload = {
    expected_version: beforeExternal.pending_change.version,
    values: beforeExternal.values.map((value) => ({
      translation_value_id: value.id,
      selector_version: value.selector_version,
      selector_digest: value.selector_digest,
      basis_revision_number: value.history[0].revision_number,
      basis_digest: value.history[0].revision_digest,
      proposed_text: "External French update",
    })),
  };
  await api(
    "/translations/" + group(0, "fr") + "/proposal",
    reviewerToken,
    "PUT",
    payload,
  );
  await comments.click();
  await expect(commentField).toHaveValue("Unsent French discussion");
  await expect(
    context.getByText("Pending: draft · Version 2", { exact: true }),
  ).toBeVisible();
  await commentField.fill("French discussion persisted");
  await context
    .getByRole("button", { name: "Post comment", exact: true })
    .click();
  await expect(
    context
      .getByRole("list", { name: "Comments", exact: true })
      .getByText("French discussion persisted", { exact: true }),
  ).toBeVisible();
  const savedComments = await api(
    "/translations/" + group(0, "fr") + "/comments",
    bearer,
  );
  check(
    savedComments.items.some(
      (comment) => comment.body === "French discussion persisted",
    ),
  );
  check(
    !(await api("/translations/" + group(0, "it") + "/comments", bearer)).items
      .length,
  );
  await context.getByRole("tab", { name: "History", exact: true }).click();
  await context
    .getByRole("button", { name: "Show activity history", exact: true })
    .click();
  await expect(
    context
      .getByRole("heading", { name: "Proposal saved", exact: true })
      .first(),
  ).toBeVisible();
  await context
    .getByRole("tab", { name: "Source changes", exact: true })
    .click();
  await expect(
    context.getByText(/Current imported source/).first(),
  ).toBeVisible();
  await closeContext();
  await expect(comments).toBeFocused();

  progress("desktop-mobile");
  await page.setViewportSize({ width: 390, height: 844 });
  await capture("mobile-rows");
  await edit(0, "it").click();
  await expect(
    page
      .locator('[data-group-id="' + group(0, "it") + '"]')
      .getByRole("textbox"),
  ).toBeEnabled();
  await field.scrollIntoViewIfNeeded();
  await capture("mobile-editor");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await filter();
  await capture("mobile-filters");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await comments.click();
  await capture("mobile-context");
  await closeContext();
  await page.setViewportSize({ width: 1440, height: 900 });

  progress("page-boundary");
  await page
    .getByRole("button", { name: "Clear filters", exact: true })
    .click();
  await expect(edit(0, "fr")).toBeVisible();
  for (let i = 0; i < 20 && !(await edit(49, "fr").count()); i++) {
    await page.mouse.wheel(0, 1400);
    await page.waitForTimeout(60);
  }
  await edit(49, "fr").click();
  await field.fill("French across page boundary");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect
    .poll(async () => (await detail(49, "fr")).pending_change?.values[0].text)
    .toBe("French across page boundary");
  await expect(field).toHaveCount(0);
  await page
    .getByRole("button", { name: "Load more translations", exact: true })
    .click();
  for (let i = 0; i < 20 && !(await edit(50, "fr").count()); i++) {
    await page.mouse.wheel(0, 1000);
    await page.waitForTimeout(60);
  }
  await edit(50, "fr").click();
  await expect(field).toHaveValue("fr 50");
  check(
    keyResponses.some((response) =>
      new URL(response.url).searchParams.get("cursor"),
    ),
  );
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await search("key-060");
  await edit(60, "fr").click();
  await field.fill("Final French");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect
    .poll(async () => (await detail(60, "fr")).pending_change?.values[0].text)
    .toBe("Final French");
  await expect(field).toHaveCount(0);

  progress("reviewer-first-save");
  const reviewer = await login("product_manager_reviewer");
  await reviewer.goto(frontend + path);
  await reviewer
    .getByRole("textbox", { name: "Search keys and translations" })
    .fill("key-011");
  await reviewer
    .getByRole("button", {
      name: "Edit translation for key-011 (fr)",
      exact: true,
    })
    .click();
  await reviewer
    .getByRole("button", { name: /^Review for key-011 \(fr\):/ })
    .click();
  const reviewContext = reviewer.getByRole("complementary", {
    name: "Selected translation context",
  });
  await expect(
    reviewContext.getByText("No saved proposal yet", { exact: true }),
  ).toBeVisible();
  await reviewer
    .getByRole("textbox", { name: "Proposed translation", exact: true })
    .fill("Premier brouillon");
  await reviewer.getByRole("button", { name: "Save", exact: true }).click();
  await expect(
    reviewContext.getByRole("button", {
      name: "Approve translation",
      exact: true,
    }),
  ).toBeEnabled();
  await reviewContext
    .getByRole("button", { name: "Approve translation", exact: true })
    .click();
  await expect(
    reviewContext.getByText("Pending: approved · Version 2", { exact: true }),
  ).toBeVisible();
  const approved = await api("/translations/" + group(11, "fr"), reviewerToken);
  check(
    approved.pending_change.state === "approved" &&
      approved.pending_change.version === 2 &&
      approved.values[0].translated_text === "fr 11",
  );
  progress("over-limit-review-guard");
  const adminToken = await token("admin");
  await api(
    "/translations/" + group(12, "fr") + "/constraints/fr",
    adminToken,
    "PUT",
    { max_chars: 0, expected_version: 0 },
  );
  await reviewer
    .getByRole("textbox", { name: "Search keys and translations" })
    .fill("key-012");
  await reviewer
    .getByRole("button", {
      name: "Edit translation for key-012 (fr)",
      exact: true,
    })
    .click();
  await expect(
    reviewer
      .locator('[data-group-id="' + group(12, "fr") + '"]')
      .getByRole("textbox", { name: "Proposed translation", exact: true }),
  ).toHaveValue("fr 12");
  await reviewer
    .getByRole("textbox", { name: "Proposed translation", exact: true })
    .fill("Too long");
  await reviewer.getByRole("button", { name: "Save", exact: true }).click();
  await expect
    .poll(
      async () =>
        (await api("/translations/" + group(12, "fr"), reviewerToken))
          .pending_change?.values[0].text,
    )
    .toBe("Too long");
  await reviewer
    .getByRole("button", { name: /^Review for key-012 \(fr\):/ })
    .click();
  await expect(
    reviewContext.getByText("Approval blocked", { exact: true }),
  ).toBeVisible();
  const blockedApproval = reviewContext.getByRole("button", {
    name: "Approve translation",
    exact: true,
  });
  if (await blockedApproval.count())
    await expect(blockedApproval).toBeDisabled();
  const blocked = await api("/translations/" + group(12, "fr"), reviewerToken);
  check(
    blocked.pending_change.state === "draft" &&
      blocked.pending_change.values[0].is_over_limit,
  );
  await reviewer.close();

  progress("source-only-and-cap");
  await page.goto(
    frontend + "/products/" + fixture.source_only_product + "/strings",
  );
  await expect(
    page.getByText("Keys-repository values are read-only in this workspace.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /^Edit translation/ }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Original", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Bilingual", exact: true }).click();
  await expect(
    page.getByText("Keys-repository values are read-only in this workspace.", {
      exact: true,
    }),
  ).toBeVisible();
  await capture("source-only");
  await page.goto(
    frontend + "/products/" + fixture.embedded_product + "/strings",
  );
  await expect(
    page.getByRole("button", {
      name: "Source details for greeting (en)",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Edit translation for greeting (en)",
      exact: true,
    }),
  ).toHaveCount(0);
  await page
    .getByRole("button", {
      name: "Source details for greeting (en)",
      exact: true,
    })
    .click();
  await expect(
    page
      .getByLabel("Source context", { exact: true })
      .getByText(
        "Embedded source text is read-only; edit it in the repository.",
      ),
  ).toBeVisible();
  await page.goto(
    frontend + "/products/" + fixture.language_catalog_product + "/strings",
  );
  await page.getByRole("button", { name: /^Languages/ }).click();
  await expect(
    page.getByRole("button", { name: "Select all", exact: true }),
  ).toBeDisabled();
  check((await page.getByRole("checkbox", { checked: true }).count()) === 20);
  check(
    (await page
      .getByRole("checkbox", { checked: false, disabled: true })
      .count()) === 1,
  );
  await page.getByRole("button", { name: "Cancel", exact: true }).click();

  progress("viewer-and-comment-link");
  await page.goto(
    frontend +
      "/products/" +
      fixture.language_catalog_product +
      "/strings?language=uk",
  );
  await expect(page.locator('[data-language="uk"]')).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Bilingual", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const viewer = await login("viewer");
  await viewer.goto(frontend + path);
  await expect(
    viewer.getByText("key-000", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    viewer.getByRole("button", { name: /^Edit translation/ }),
  ).toHaveCount(0);
  const commentId = savedComments.items.find(
    (comment) => comment.body === "French discussion persisted",
  ).id;
  await viewer.goto(
    frontend + path + "/" + group(0, "fr") + "?comment=" + commentId,
  );
  await expect(
    viewer.getByText("French discussion persisted", { exact: true }).first(),
  ).toBeVisible();
  await noOverflow(viewer);
  await viewer.close();
  const distinct = new Set(
    keyResponses.flatMap((response) =>
      response.body.items.map((key) => key.translation_key_id),
    ),
  );
  check(distinct.size >= 61);
  writeFileSync(
    evidence + "/multilingual-persistence.json",
    JSON.stringify(
      {
        canonicalKeys: 61,
        targetLanguages: ["fr", "it"],
        cancelWroteNothing: true,
        independentLocaleWrites: true,
        importedTextUnchanged: true,
        baseLeafDraft: true,
        completePluralMembers: 2,
        absentTargetNotEditable: true,
        needsTranslationIncludesAbsent: true,
        compactProductHeader: true,
        cursorContinuation: true,
        filterApplyCancel: true,
        languageLimit: 20,
        scopedPreferences: true,
        explicitLanguageBack: true,
        commentLocale: "fr",
        unsentCommentPreserved: true,
        externalProposalRefresh: true,
        firstSaveApproved: approved.pending_change.state,
        firstSaveVersion: approved.pending_change.version,
        overLimitApprovalBlocked: true,
        sourceOnlyReadOnly: true,
        embeddedSourceReadOnly: true,
        desktopMobileOverflow: false,
      },
      null,
      2,
    ),
  );
  await page.close();
  progress("complete");
  console.log("multilingual browser: PASS");
}

try {
  if (mode === "multilingual" || mode === "bilingual") {
    await multilingualWorkspace();
  } else if (mode === "product-summary") {
    await productSummary();
  } else {
    stage = "real-login";
    const bearer = await token("translator");
    const page = await login("translator");
    stage = "save-production-proposal";
    await api(
      `/translations/${fixture.group}/proposal`,
      bearer,
      "PUT",
      fixture.proposal,
    );
    stage = "dashboard-event";
    await page.getByRole("button", { name: "Refresh activity" }).click();
    const personal = page.getByRole("region", { name: "My recent activity" });
    const saved = personal.getByRole("link", { name: /Saved a proposal/ });
    await expect(saved).toBeVisible();
    await expect(saved).toHaveAttribute(
      "href",
      `/products/${fixture.product}/strings/${fixture.group}`,
    );
    stage = "translation-destination";
    await saved.click();
    await expect(
      page.getByRole("region", { name: "Pending proposal" }),
    ).toContainText("Welcome from the dashboard");
    console.log("real saved-proposal browser tracer: PASS");
    if (mode === "full") await full(page, bearer);
  }
} catch (error) {
  writeFileSync(
    `${evidence}/failure-details.json`,
    JSON.stringify(
      {
        stage,
        type: error.name,
        message: String(error.message).slice(0, 2000),
      },
      null,
      2,
    ),
  );
  console.error(`dashboard failure type: ${error.name}`);
  for (const context of browser.contexts()) {
    for (const page of context.pages()) {
      await page.screenshot({
        path: `${evidence}/failure.png`,
        fullPage: true,
        mask: [page.locator('input[type="password"]')],
      });
    }
  }
  console.error(`dashboard browser failed: ${stage}`);
  process.exitCode = 1;
} finally {
  await browser.close();
}
