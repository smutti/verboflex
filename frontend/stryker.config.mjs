// @ts-check

/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
const config = {
  testRunner: "vitest",
  plugins: ["@stryker-mutator/vitest-runner"],
  mutate: ["src/features/auth/session.tsx"],
  vitest: {
    configFile: "vite.config.ts",
    related: true,
  },
  reporters: ["clear-text", "json"],
  jsonReporter: {
    fileName: "/tmp/verboflex-phase01-stryker.json",
  },
  thresholds: {
    high: 100,
    low: 100,
    break: 100,
  },
  concurrency: 1,
  tempDirName: "/tmp/verboflex-phase01-stryker-tmp",
};

export default config;
