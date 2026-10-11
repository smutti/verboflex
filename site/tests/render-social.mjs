// Regenerate the local social card with the existing frontend Playwright toolchain.
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
const require = createRequire(
  new URL("../../frontend/package.json", import.meta.url),
);
const { chromium } = require("playwright");
const browser = await chromium.launch();
try {
  const page = await browser.newPage({
    viewport: { width: 1200, height: 630 },
    deviceScaleFactor: 1,
  });
  await page.goto(new URL("../social.html", import.meta.url).href);
  await page.screenshot({
    path: fileURLToPath(new URL("../assets/social.png", import.meta.url)),
  });
} finally {
  await browser.close();
}
