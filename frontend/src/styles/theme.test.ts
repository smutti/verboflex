import { describe, expect, it } from "vitest";

// @ts-expect-error -- Vitest supplies Node at runtime; Node types are not a direct app dependency.
import { readFileSync } from "node:fs";

const runtime = globalThis as typeof globalThis & {
  process: { cwd: () => string };
};
const sourceRoot = `${runtime.process.cwd()}/src`;
const stylesheet = readFileSync(`${sourceRoot}/index.css`, "utf8");
const appEntry = readFileSync(`${sourceRoot}/main.tsx`, "utf8");

function readBlock(source: string, selector: string): string {
  const selectorIndex = source.indexOf(selector);
  if (selectorIndex < 0) {
    throw new Error(`Missing required CSS block: ${selector}`);
  }

  const openingBrace = source.indexOf("{", selectorIndex + selector.length);
  if (openingBrace < 0) {
    throw new Error(`Malformed CSS block: ${selector}`);
  }

  let depth = 1;
  for (let index = openingBrace + 1; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") depth -= 1;
    if (depth === 0) return source.slice(openingBrace + 1, index);
  }

  throw new Error(`Unclosed CSS block: ${selector}`);
}

function readProperties(block: string): Record<string, string> {
  const properties: Record<string, string> = {};
  const declaration = /^\s*(--[a-z0-9-]+):\s*([^;]+);/gim;

  for (const match of block.matchAll(declaration)) {
    const [, name, value] = match;
    if (name in properties) {
      throw new Error(`Duplicate CSS property: ${name}`);
    }
    properties[name] = value.trim();
  }

  return properties;
}

const rootProperties = readProperties(readBlock(stylesheet, ":root"));
const themeProperties = readProperties(readBlock(stylesheet, "@theme inline"));

function selectProperties(
  properties: Record<string, string>,
  pattern: RegExp,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(properties).filter(([name]) => pattern.test(name)),
  );
}

describe("approved Phase 1 theme contract", () => {
  it("defines exactly four typography sizes and two weights", () => {
    expect(selectProperties(rootProperties, /^--type-.+-size$/)).toEqual({
      "--type-label-size": "12px",
      "--type-body-size": "14px",
      "--type-heading-size": "20px",
      "--type-display-size": "28px",
    });
    expect(selectProperties(rootProperties, /^--type-.+-line-height$/)).toEqual({
      "--type-label-line-height": "1.3",
      "--type-body-line-height": "1.5",
      "--type-heading-line-height": "1.25",
      "--type-display-line-height": "1.15",
    });
    expect(selectProperties(rootProperties, /^--weight-/)).toEqual({
      "--weight-regular": "400",
      "--weight-semibold": "600",
    });
    expect(selectProperties(themeProperties, /^--text-(?!.*line-height)/)).toEqual({
      "--text-label": "var(--type-label-size)",
      "--text-body": "var(--type-body-size)",
      "--text-heading": "var(--type-heading-size)",
      "--text-display": "var(--type-display-size)",
    });
    expect(stylesheet).not.toMatch(/(?:clamp|min|max)\([^)]*\b(?:vw|vh)\b/iu);
  });

  it("defines the exact 4px-multiple spacing scale", () => {
    const spacing = selectProperties(rootProperties, /^--space-/);
    expect(spacing).toEqual({
      "--space-xs": "4px",
      "--space-sm": "8px",
      "--space-md": "16px",
      "--space-lg": "24px",
      "--space-xl": "32px",
      "--space-2xl": "48px",
      "--space-3xl": "64px",
    });

    for (const value of Object.values(spacing)) {
      expect(Number.parseInt(value, 10) % 4).toBe(0);
    }
  });

  it("uses only the approved visual color literals", () => {
    const colors = selectProperties(
      rootProperties,
      /^--(?:dominant|secondary|accent|destructive|text-primary|text-secondary|text-muted|border|success|warning)$/,
    );
    expect(colors).toEqual({
      "--dominant": "#f8fafc",
      "--secondary": "#ffffff",
      "--accent": "#0f766e",
      "--destructive": "#dc2626",
      "--text-primary": "#111827",
      "--text-secondary": "#4b5563",
      "--text-muted": "#6b7280",
      "--border": "#e5e7eb",
      "--success": "#15803d",
      "--warning": "#b45309",
    });
    expect(new Set(stylesheet.match(/#[0-9a-f]{6}\b/giu))).toEqual(
      new Set(Object.values(colors)),
    );
  });

  it("uses the system font stack without a remote font source", () => {
    expect(rootProperties["--font-system"]).toBe(
      '"Inter", ui-sans-serif, system-ui, sans-serif',
    );
    expect(stylesheet).not.toMatch(/@font-face|url\s*\(|https?:\/\//iu);
  });

  it("keeps the accent focus indicator visible", () => {
    const focusRule = readBlock(stylesheet, ":focus-visible");
    expect(focusRule).toMatch(/outline:\s*2px solid var\(--accent\);/u);
    expect(focusRule).toMatch(/outline-offset:\s*2px;/u);
    expect(rootProperties["--ring"]).toBe("var(--accent)");
  });

  it("caps every governed radius at eight pixels", () => {
    expect(rootProperties["--panel-radius"]).toBe("8px");

    const radii = selectProperties(themeProperties, /^--radius-/);
    expect(Object.keys(radii)).toEqual([
      "--radius-xs",
      "--radius-sm",
      "--radius-md",
      "--radius-lg",
      "--radius-xl",
      "--radius-2xl",
      "--radius-3xl",
      "--radius-4xl",
    ]);

    for (const value of Object.values(radii)) {
      const resolved =
        value === "var(--panel-radius)" ? rootProperties["--panel-radius"] : value;
      expect(Number.parseInt(resolved, 10)).toBeLessThanOrEqual(8);
    }
  });

  it("imports the governed stylesheet exactly once at the app entry", () => {
    expect(appEntry.match(/import\s+["']\.\/index\.css["'];/gu)).toHaveLength(1);
  });
});
