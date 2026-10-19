import ts from "typescript";
import { describe, expect, it } from "vitest";
import en from "./locales/en.json";
import itCatalog from "./locales/it.json";
import de from "./locales/de.json";
import es from "./locales/es.json";
import fr from "./locales/fr.json";
import nl from "./locales/nl.json";

const placeholders = (value: string) =>
  [...value.matchAll(/\{\{\s*([^}]+?)\s*\}\}/g)]
    .map((match) => match[1])
    .sort();
describe("bundled UI catalogs", () => {
  it.each(Object.entries({ it: itCatalog, de, es, fr, nl }))(
    "keeps %s complete and preserves interpolation placeholders",
    (_language, catalog) => {
      expect(Object.keys(catalog).sort()).toEqual(Object.keys(en).sort());
      for (const key of Object.keys(en) as (keyof typeof en)[]) {
        expect(catalog[key].trim(), key).not.toBe("");
        expect(placeholders(catalog[key]), key).toEqual(placeholders(en[key]));
        expect(catalog[key], key).not.toMatch(/VFXPH\d+X/);
      }
    },
  );
  it("uses software terminology for strings and commits in all languages", () => {
    expect([
      itCatalog.Strings,
      de.Strings,
      es.Strings,
      fr.Strings,
      nl.Strings,
    ]).toEqual([
      "Stringhe",
      "Zeichenfolgen",
      "Cadenas",
      "Chaînes",
      "Tekenreeksen",
    ]);
    for (const catalog of [en, itCatalog, de, es, fr, nl])
      expect(catalog.Commit).toBe("Commit");
  });
  it("covers literal UI calls and keeps translations out of comparisons and API value fields", () => {
    const failures: string[] = [];
    const sources = import.meta.glob<string>(
      ["../**/*.{ts,tsx}", "!../**/*.test.*", "!../api/**"],
      { query: "?raw", import: "default", eager: true },
    );
    for (const [file, contents] of Object.entries(sources)) {
      const source = ts.createSourceFile(
        file,
        contents,
        ts.ScriptTarget.Latest,
        true,
      );
      function visit(node: ts.Node) {
        if (
          ts.isCallExpression(node) &&
          node.expression.getText(source) === "t" &&
          node.arguments[0] &&
          ts.isStringLiteral(node.arguments[0])
        ) {
          const key = node.arguments[0].text.trim();
          if (!(key in en)) failures.push(`${file}: missing ${key}`);
          const parent = node.parent;
          if (
            ts.isBinaryExpression(parent) &&
            [
              ts.SyntaxKind.EqualsEqualsEqualsToken,
              ts.SyntaxKind.ExclamationEqualsEqualsToken,
            ].includes(parent.operatorToken.kind)
          )
            failures.push(`${file}: translated comparison ${key}`);
          if (
            ts.isPropertyAssignment(parent) &&
            ["value", "state", "status", "section", "identity_kind"].includes(
              parent.name.getText(source),
            )
          )
            failures.push(`${file}: translated machine value ${key}`);
        }
        ts.forEachChild(node, visit);
      }
      visit(source);
    }
    expect(failures).toEqual([]);
  });
});
