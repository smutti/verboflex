// Local-only browser companion for mcp_oauth_smoke.py. Never prints credentials/tokens.
import { chromium } from "../frontend/node_modules/playwright/index.mjs";
import fs from "node:fs";

const [mode, target, credentialFile, outputDir] = process.argv.slice(2);
const credentials = JSON.parse(fs.readFileSync(credentialFile, "utf8"));
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1100, height: 850 } });
try {
  let callback;
  if (mode === "consent") {
    const url = new URL(target);
    if (
      url.origin !== "http://localhost:8080" ||
      url.pathname !== "/oauth/authorize"
    )
      throw new Error("Local OAuth only");
    callback = new Promise((resolve) => {
      void page.route("http://127.0.0.1:19342/callback**", async (route) => {
        const result = new URL(route.request().url());
        await route.fulfill({ status: 200, body: "Connected" });
        resolve({
          code: result.searchParams.get("code"),
          state: result.searchParams.get("state"),
        });
      });
    });
    await page.goto(target);
  } else {
    await page.goto("http://localhost:8080/login");
  }
  await page
    .getByLabel("Email", { exact: true })
    .fill(credentials.email || credentials.username);
  await page.getByLabel("Password", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Sign in to VerboFlex" }).click();
  let result = { revoked: true };
  if (mode === "consent") {
    await page.getByRole("heading", { name: "Connect to VerboFlex" }).waitFor();
    // Least privilege: deliberately leave write permission unchecked.
    await page.screenshot({
      path: `${outputDir}/sdk-consent.png`,
      fullPage: true,
    });
    await page.getByRole("button", { name: "Connect", exact: true }).click();
    result = await callback;
    await page.getByText("Connected", { exact: true }).waitFor();
  } else {
    await page
      .getByRole("button", { name: "Sign out of VerboFlex", exact: true })
      .waitFor();
  }
  await page.goto("http://localhost:8080/mcp/connections");
  await page.getByRole("heading", { name: "Connected apps" }).waitFor();
  if (mode === "revoke") {
    const entry = page
      .getByRole("article")
      .filter({
        has: page.getByRole("heading", { name: target, exact: true }),
      });
    await entry.getByRole("button", { name: "Revoke access" }).click();
    await entry.waitFor({ state: "detached" });
    await page.screenshot({
      path: `${outputDir}/connections.png`,
      fullPage: true,
    });
  }
  await page
    .getByRole("button", { name: "Sign out of VerboFlex", exact: true })
    .click();
  await page.getByRole("button", { name: "Sign in to VerboFlex" }).waitFor();
  process.stdout.write(JSON.stringify(result));
} catch (error) {
  await page.screenshot({ path: `${outputDir}/failure.png`, fullPage: true });
  console.error(
    error.name,
    new URL(page.url()).pathname,
    error.message.split("\n")[0],
  );
  throw new Error("Browser interaction failed");
} finally {
  await browser.close();
}
