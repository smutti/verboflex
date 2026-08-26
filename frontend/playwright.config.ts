import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  reporter: "line",
  outputDir:
    process.env.PLAYWRIGHT_OUTPUT_DIR ??
    "/tmp/verboflex-phase01-plan13-playwright",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:8080",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
  },
});
