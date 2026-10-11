// Real built-stack acceptance; never mocks browser networking or emits content.
import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
const require = createRequire(
  new URL("../frontend/package.json", import.meta.url),
);
const { chromium, expect } = require("@playwright/test");
const [mode, fixturePath, backend, frontend] = process.argv.slice(2);
const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
let browser;
let stage = "startup";
let lastStatus = 0;
function check(value) {
  if (!value) throw new Error("Contract rejected");
}
async function api(path, token, method = "GET", body) {
  const response = await fetch(`${backend}/api/v1${path}`, {
    method,
    signal: AbortSignal.timeout(10000),
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      "Content-Type": "application/json",
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  lastStatus = response.status;
  return { status: response.status, body: await response.json() };
}
async function login(role) {
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
  lastStatus = response.status;
  check(response.status === 200);
  return (await response.json()).access_token;
}
try {
  const admin = await login("admin");
  if (mode === "enqueue") {
    stage = "provider-connect";
    check(
      (await api("/admin/bitbucket/connect", admin, "POST")).status === 200,
    );
    for (const mapping of fixture.mappings) {
      stage = `enqueue-${mapping.format}`;
      const response = await api(
        `/admin/products/${mapping.product}/published/mappings/${mapping.mapping}/imports`,
        admin,
        "POST",
      );
      check(response.status === 202 && response.body.state === "queued");
      mapping.job = response.body.id;
    }
    writeFileSync(fixturePath, JSON.stringify(fixture), { mode: 0o600 });
  } else if (mode === "verify") {
    for (const mapping of fixture.mappings) {
      stage = `import-${mapping.format}`;
      const deadline = Date.now() + 120000;
      let job;
      do {
        const response = await api(
          `/admin/products/${mapping.product}/imports/${mapping.job}`,
          admin,
        );
        check(response.status === 200);
        job = response.body;
        if (!["queued", "running"].includes(job.state)) break;
        await new Promise((resolve) => setTimeout(resolve, 500));
      } while (Date.now() < deadline);
      if (job.state !== "current" || job.dataset_status !== "active") {
        const allowed = new Set([
          "queued",
          "running",
          "current",
          "may_be_stale",
          "review_required",
          "import_failed",
          "active",
          "retained",
          "not_created",
          "connection_required",
          "permission_denied",
          "rate_limited",
          "source_not_found",
          "timeout",
          "provider_unavailable",
          "bounded_failure",
          "malformed_file",
          "ambiguous_structure",
          "unsupported_structure",
          "duplicate_key",
          "base_language_required",
        ]);
        const codes = [
          job.state,
          job.dataset_status,
          job.error_category,
          ...(job.parser_issues ?? []).map((issue) => issue.issue_code),
        ].filter((code) => allowed.has(code));
        stage += "-" + codes.join("-");
        throw new Error("Import rejected");
      }
      stage = `search-detail-${mapping.format}`;
      const search = await api(
        `/translations?product_id=${mapping.product}&language=it&page_size=50&q=Smoke%20target`,
        admin,
      );
      check(search.status === 200 && search.body.items.length === 1);
      mapping.group = search.body.items[0].id;
      const detail = await api(`/translations/${mapping.group}`, admin);
      check(detail.status === 200 && detail.body.values.length === 1);
      check(detail.body.values[0].provenance.format === mapping.format);
      check(detail.body.values[0].translated_text === "Smoke target");
      check(detail.body.values[0].grapheme_count === 12);
    }
    // Persist server-issued opaque group ids for bounded smoke extensions that
    // execute before the owned stack is torn down.
    writeFileSync(fixturePath, JSON.stringify(fixture), { mode: 0o600 });
    stage = "role-matrix";
    const group = fixture.mappings[0].group;
    const path = `/translations/${group}/constraints/it`;
    check((await api(`/translations/${group}`)).status === 401);
    for (const role of Object.keys(fixture.users)) {
      stage = `role-${role}-login`;
      const token = role === "admin" ? admin : await login(role);
      stage = `role-${role}-read`;
      check((await api(`/translations/${group}`, token)).status === 200);
      const canWrite = ["admin", "product_manager_reviewer"].includes(role);
      stage = `role-${role}-put`;
      const put = await api(path, token, "PUT", {
        max_chars: 0,
        expected_version: 0,
      });
      check(put.status === (canWrite ? 200 : 403));
      if (canWrite) {
        check(
          put.body.violating_count === 1 &&
            put.body.values.find((value) => value.language === "it")?.constraint
              .status === "over_limit",
        );
        check(
          (
            await api(path, token, "PUT", {
              max_chars: 10,
              expected_version: 0,
            })
          ).status === 409,
        );
      }
      stage = `role-${role}-delete`;
      const removed = await api(path, token, "DELETE", {
        expected_version: canWrite ? put.body.version : 0,
      });
      check(removed.status === (canWrite ? 200 : 403));
      if (canWrite) check(removed.body.explicit_maximum === null);
    }
    stage = "built-browser-login";
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({
      viewport: { width: 1440, height: 900 },
      reducedMotion: "reduce",
    });
    page.setDefaultTimeout(15000);
    await page.goto(`${frontend}/login`);
    await page
      .getByRole("textbox", { name: "Email" })
      .fill(fixture.users.admin.email);
    await page
      .getByLabel("Password", { exact: true })
      .fill(fixture.users.admin.password);
    await page
      .getByRole("button", { name: "Sign in to VerboFlex", exact: true })
      .click();
    await expect(
      page.getByRole("link", { name: "All translations", exact: true }).first(),
    ).toBeVisible();
    for (const mapping of fixture.mappings) {
      stage = `built-browser-${mapping.format}`;
      await page
        .getByRole("link", { name: "All translations", exact: true })
        .first()
        .click();
      stage = `built-browser-${mapping.format}-product`;
      await page
        .getByRole("combobox", { name: "Product", exact: true })
        .click();
      await page
        .getByRole("option", { name: `Smoke ${mapping.format}`, exact: true })
        .click();
      stage = `built-browser-${mapping.format}-language`;
      await page
        .getByRole("combobox", { name: "Language", exact: true })
        .click();
      await page
        .getByRole("option", { name: "Italian (it)", exact: true })
        .click();
      const query = page.getByRole("textbox", {
        name: "Search keys and translations",
      });
      stage = `built-browser-${mapping.format}-search`;
      const searchResponse = page.waitForResponse((response) => {
        const url = new URL(response.url());
        return (
          url.pathname === "/api/v1/translations" &&
          url.searchParams.get("q") === "Smoke target" &&
          url.searchParams.get("product_id") === mapping.product &&
          url.searchParams.get("language") === "it"
        );
      });
      await query.fill("Smoke target");
      await query.press("Enter");
      const returned = await searchResponse;
      lastStatus = returned.status();
      check(lastStatus === 200);
      const searchBody = await returned.json();
      check(
        searchBody.items.length === 1 &&
          searchBody.items[0].id === mapping.group,
      );
      stage = `built-browser-${mapping.format}-render`;
      const link = page.locator(
        `a[data-translation-group-id="${mapping.group}"]`,
      );
      await expect(link).toBeVisible();
      await link.click();
      stage = `built-browser-${mapping.format}-detail`;
      await expect(
        page.getByRole("heading", { name: "Translation details", exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("Smoke target", { exact: true }),
      ).toBeVisible();
      stage = `built-browser-${mapping.format}-create`;
      await page.getByRole("button", { name: "Set max length" }).click();
      await page
        .getByRole("spinbutton", { name: "Maximum characters" })
        .fill("0");
      await page.getByRole("button", { name: "Save max length" }).click();
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(
        page.getByText("Over limit by 12", { exact: true }).first(),
      ).toBeVisible();
      stage = `built-browser-${mapping.format}-remove`;
      await page
        .getByRole("button", { name: "Remove language override" })
        .click();
      await page
        .getByRole("alertdialog")
        .getByRole("button", { name: "Remove language override", exact: true })
        .click();
      await expect(page.getByRole("alertdialog")).toHaveCount(0);
      stage = `built-browser-${mapping.format}-back`;
      await page.getByRole("link", { name: "Back to translations" }).click();
      await expect(query).toHaveValue("Smoke target");
      await expect(link).toBeFocused();
      stage = `built-browser-${mapping.format}-reload`;
      // Direct route reload verifies nginx SPA fallback and real session refresh.
      await page.goto(`${frontend}/translations/${mapping.group}`);
      await expect(
        page.getByRole("heading", { name: "Translation details", exact: true }),
      ).toBeVisible();
      const stored = await page.evaluate(() =>
        JSON.stringify({ ...localStorage, ...sessionStorage }),
      );
      check(!stored.includes("Smoke target") && !stored.includes(admin));
    }
  } else throw new Error("Unknown mode");
  console.log(`phase4 ${mode}: PASS (formats=4)`);
} catch {
  console.error(`phase4 smoke failed: ${stage}-http-${lastStatus}`);
  process.exitCode = 1;
} finally {
  await browser?.close();
}
