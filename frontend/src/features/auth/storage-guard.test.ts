import ts from "typescript";
import { describe, expect, it } from "vitest";

type ForbiddenSurface =
  | "analytics"
  | "indexeddb"
  | "logs"
  | "url"
  | "web-storage";

interface Violation {
  file: string;
  surface: ForbiddenSurface;
  text: string;
}

const credentialPattern =
  /\b(?:access[_-]?token|refresh[_-]?token|authorization|bearer|credential)\b/i;

function scanCredentialPersistence(file: string, sourceText: string): Violation[] {
  const source = ts.createSourceFile(
    file,
    sourceText,
    ts.ScriptTarget.Latest,
    true,
    file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const violations: Violation[] = [];
  const report = (surface: ForbiddenSurface, node: ts.Node) => {
    violations.push({
      file,
      surface,
      text: node.getText(source),
    });
  };

  const visit = (node: ts.Node) => {
    const nodeText = node.getText(source);
    if (ts.isCallExpression(node) && credentialPattern.test(nodeText)) {
      const target = node.expression.getText(source).toLowerCase();
      if (
        /(?:^|\.)(?:localstorage|sessionstorage)\.setitem$/.test(target)
      ) {
        report("web-storage", node);
      } else if (
        /(?:store|objectstore|indexeddb|\bdb)\.(?:add|put)$/.test(target)
      ) {
        report("indexeddb", node);
      } else if (
        /(?:params|search|url)\.(?:append|set)$/.test(target) ||
        /(?:history\.(?:pushstate|replacestate)|location\.(?:assign|replace))$/.test(
          target,
        )
      ) {
        report("url", node);
      } else if (/^console\.(?:debug|error|info|log|warn)$/.test(target)) {
        report("logs", node);
      } else if (
        /(?:analytics|telemetry|amplitude|mixpanel|sentry)\.(?:capture|event|log|track)$/.test(
          target,
        )
      ) {
        report("analytics", node);
      }
    }
    if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
      credentialPattern.test(nodeText)
    ) {
      const target = node.left.getText(source).toLowerCase();
      if (/(?:localstorage|sessionstorage)/.test(target)) {
        report("web-storage", node);
      } else if (/(?:location|document)\.(?:hash|href|search)$/.test(target)) {
        report("url", node);
      }
    }
    ts.forEachChild(node, visit);
  };

  visit(source);
  return violations;
}

const productionFiles = import.meta.glob("/src/**/*.{ts,tsx}", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

describe("browser credential persistence guard", () => {
  it("finds no forbidden credential persistence in handwritten production source", () => {
    expect(Object.keys(productionFiles)).toContain(
      "/src/features/auth/session.tsx",
    );
    const violations = Object.entries(productionFiles)
      .filter(
        ([file]) =>
          !file.includes("/api/client/") && !file.includes(".test."),
      )
      .flatMap(([file, source]) => scanCredentialPersistence(file, source));

    expect(violations).toEqual([]);
  });

  it("rejects known-bad persistence on every prohibited browser surface", () => {
    const knownBad = `
      localStorage.setItem("access_token", accessToken);
      tokenStore.put({ refresh_token: refreshToken });
      searchParams.set("access_token", accessToken);
      console.info("bearer", accessToken);
      analytics.track("login", { credential: accessToken });
    `;

    expect(
      scanCredentialPersistence("known-bad.ts", knownBad).map(
        (violation) => violation.surface,
      ),
    ).toEqual(["web-storage", "indexeddb", "url", "logs", "analytics"]);
  });

  it("allows unrelated browser APIs and non-credential diagnostics", () => {
    const knownGood = `
      localStorage.setItem("theme", "dark");
      indexedDB.open("app-cache");
      searchParams.set("language", "it");
      console.info("session restored");
      analytics.track("page-view", { page: "workspace" });
    `;

    expect(scanCredentialPersistence("known-good.ts", knownGood)).toEqual([]);
  });
});
