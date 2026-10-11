import { describe, expect, it } from "vitest";

// @ts-expect-error -- Vitest supplies Node at runtime; Node types are not a direct app dependency.
import { readFileSync } from "node:fs";

const runtime = globalThis as typeof globalThis & {
  process: { cwd: () => string };
};
const appEntry = readFileSync(`${runtime.process.cwd()}/src/main.tsx`, "utf8");

describe("application bootstrap", () => {
  it("uses one stable data router containing session and dirty-form authority", () => {
    expect(appEntry).toMatch(/createVerboFlexBrowserRouter\(\)/u);
    expect(appEntry).toMatch(/<RouterProvider\s+router=\{router\}\s*\/>/u);
    expect(appEntry).not.toMatch(/<BrowserRouter>/u);
  });
});
