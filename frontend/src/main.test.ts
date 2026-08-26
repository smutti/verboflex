import { describe, expect, it } from "vitest";

// @ts-expect-error -- Vitest supplies Node at runtime; Node types are not a direct app dependency.
import { readFileSync } from "node:fs";

const runtime = globalThis as typeof globalThis & {
  process: { cwd: () => string };
};
const appEntry = readFileSync(`${runtime.process.cwd()}/src/main.tsx`, "utf8");

describe("application bootstrap", () => {
  it("puts server-backed session authority in front of every application route", () => {
    expect(appEntry).toMatch(
      /<BrowserRouter>\s*<SessionProvider>\s*<AppRouter\s*\/>\s*<\/SessionProvider>\s*<\/BrowserRouter>/u,
    );
  });
});
