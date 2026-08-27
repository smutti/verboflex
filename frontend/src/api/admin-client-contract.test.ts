import ts from "typescript";
import { describe, expect, expectTypeOf, it } from "vitest";

import openApiDocument from "../../openapi.json";
import { createClient } from "./client/client";
import { listAdminUsers } from "./client/sdk.gen";
import type {
  AdminUserListResponse,
  ListAdminUsersResponse,
} from "./client/types.gen";

type OpenApiSchema = {
  properties?: Record<string, unknown>;
  items?: OpenApiSchema;
  anyOf?: OpenApiSchema[];
  allOf?: OpenApiSchema[];
  oneOf?: OpenApiSchema[];
  $ref?: string;
};

type OpenApiOperation = {
  requestBody?: unknown;
};

type OpenApiDocument = {
  components: {
    schemas: Record<string, OpenApiSchema>;
  };
  paths: Record<string, Record<string, OpenApiOperation>>;
};

const openApi = openApiDocument as OpenApiDocument;
const sensitiveAdminProperties = new Set([
  "access_token",
  "access_token_ciphertext",
  "client_secret",
  "encryption_key",
  "provider_body",
  "raw_body",
  "refresh_token",
  "refresh_token_ciphertext",
  "source_bytes",
  "temporary_password",
  "token_ciphertext",
]);

const handwrittenSources = import.meta.glob("/src/**/*.{ts,tsx}", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

function referencedSchemaName(reference: string): string {
  return reference.slice(reference.lastIndexOf("/") + 1);
}

function collectSchemaProperties(
  schema: OpenApiSchema,
  visited = new Set<string>(),
): Set<string> {
  const properties = new Set(Object.keys(schema.properties ?? {}));
  const nestedSchemas = [
    ...(schema.items ? [schema.items] : []),
    ...(schema.anyOf ?? []),
    ...(schema.allOf ?? []),
    ...(schema.oneOf ?? []),
    ...Object.values(schema.properties ?? {}).map(
      (value) => value as OpenApiSchema,
    ),
  ];

  for (const nested of nestedSchemas) {
    if (nested.$ref) {
      const name = referencedSchemaName(nested.$ref);
      if (!visited.has(name)) {
        visited.add(name);
        const referenced = openApi.components.schemas[name];
        if (referenced) {
          collectSchemaProperties(referenced, visited).forEach((property) =>
            properties.add(property),
          );
        }
      }
    } else {
      collectSchemaProperties(nested, visited).forEach((property) =>
        properties.add(property),
      );
    }
  }

  return properties;
}

function typeMemberNames(members: ts.NodeArray<ts.TypeElement>): string[] {
  return members
    .map((member) => {
      if (!member.name) {
        return undefined;
      }
      if (
        ts.isIdentifier(member.name) ||
        ts.isStringLiteral(member.name) ||
        ts.isNumericLiteral(member.name)
      ) {
        return member.name.text;
      }
      return undefined;
    })
    .filter((name): name is string => name !== undefined)
    .sort();
}

const forbiddenWireShapes = [
  ["items", "next_cursor"],
  ["display_name", "email", "id", "is_active", "must_change_password", "roles"],
].map((shape) => shape.sort().join("\u0000"));

function findHandwrittenAdminUserWireTypes(
  file: string,
  sourceText: string,
): string[] {
  const source = ts.createSourceFile(
    file,
    sourceText,
    ts.ScriptTarget.Latest,
    true,
    file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const duplicates: string[] = [];

  const visit = (node: ts.Node) => {
    let members: ts.NodeArray<ts.TypeElement> | undefined;
    let name: string | undefined;

    if (ts.isInterfaceDeclaration(node)) {
      members = node.members;
      name = node.name.text;
    } else if (
      ts.isTypeAliasDeclaration(node) &&
      ts.isTypeLiteralNode(node.type)
    ) {
      members = node.type.members;
      name = node.name.text;
    }

    if (
      members &&
      name &&
      forbiddenWireShapes.includes(typeMemberNames(members).join("\u0000"))
    ) {
      duplicates.push(`${file}:${name}`);
    }

    ts.forEachChild(node, visit);
  };

  visit(source);
  return duplicates;
}

describe("canonical generated Phase 2 admin client", () => {
  it("calls the generated user list with its exact response type and an in-memory bearer", async () => {
    const responseBody = {
      items: [
        {
          display_name: "Ada Lovelace",
          email: "ada@corp.example",
          id: "10000000-0000-4000-8000-000000000001",
          is_active: true,
          must_change_password: false,
          roles: ["admin"],
        },
      ],
      next_cursor: null,
    } satisfies AdminUserListResponse;
    const requests: Request[] = [];
    const apiClient = createClient({
      baseUrl: "https://api.verboflex.test",
      fetch: async (request) => {
        requests.push(
          request instanceof Request ? request : new Request(request),
        );
        return new Response(JSON.stringify(responseBody), {
          headers: { "Content-Type": "application/json" },
          status: 200,
        });
      },
    });

    const result = await listAdminUsers({
      auth: "phase-two-memory-bearer",
      client: apiClient,
      query: { cursor: null, limit: 50 },
    });

    expectTypeOf(result.data).toEqualTypeOf<
      ListAdminUsersResponse | undefined
    >();
    expect(result.data).toEqual(responseBody);
    expect(requests).toHaveLength(1);
    expect(requests[0]?.method).toBe("GET");
    expect(requests[0]?.url).toBe(
      "https://api.verboflex.test/api/v1/admin/users?limit=50",
    );
    expect(requests[0]?.headers.get("Authorization")).toBe(
      "Bearer phase-two-memory-bearer",
    );
    expect(requests[0]?.url).not.toContain("phase-two-memory-bearer");
    expect(requests[0]?.body).toBeNull();
  });

  it("keeps list and provider-facing admin schemas free of credential material", () => {
    const guardedSchemas = [
      "AdminUserListResponse",
      ...Object.keys(openApi.components.schemas).filter((name) =>
        /^(?:AdminBitbucket|AdminBranch|AdminDiscovery|AdminRepository|AdminSource)/u.test(
          name,
        ),
      ),
    ];

    for (const schemaName of guardedSchemas) {
      const schema = openApi.components.schemas[schemaName];
      expect(schema, `${schemaName} must remain generated`).toBeDefined();
      const leaked = [...collectSchemaProperties(schema!)].filter((property) =>
        sensitiveAdminProperties.has(property),
      );
      expect(leaked, `${schemaName} leaked credential material`).toEqual([]);
    }
  });

  it("exposes metadata reads and bounded OAuth controls but no provider write surface", () => {
    const allowedProviderOperations = new Map([
      ["/api/v1/admin/bitbucket", ["get"]],
      ["/api/v1/admin/bitbucket/oauth/callback", ["get"]],
      ["/api/v1/admin/bitbucket/oauth/reconnect", ["post"]],
      ["/api/v1/admin/bitbucket/oauth/start", ["post"]],
      ["/api/v1/admin/bitbucket/revoke", ["post"]],
    ]);

    for (const [path, methods] of allowedProviderOperations) {
      const operation = openApi.paths[path];
      expect(operation, `${path} must remain canonical`).toBeDefined();
      expect(Object.keys(operation!).sort()).toEqual(methods);
      for (const method of methods) {
        expect(operation?.[method]?.requestBody).toBeUndefined();
      }
    }

    for (const [path, operation] of Object.entries(openApi.paths).filter(
      ([path]) =>
        /\/admin\/repositories\/.*\/(?:branches|sources)$/u.test(path),
    )) {
      expect(Object.keys(operation), `${path} must stay read-only`).toEqual([
        "get",
      ]);
    }
  });

  it("rejects handwritten substitutes for generated user request and response shapes", () => {
    const duplicates = Object.entries(handwrittenSources)
      .filter(
        ([file]) => !file.includes("/api/client/") && !file.includes(".test."),
      )
      .flatMap(([file, source]) =>
        findHandwrittenAdminUserWireTypes(file, source),
      );

    expect(duplicates).toEqual([]);
  });

  it("proves the duplicate-wire checker rejects known-bad handwritten types", () => {
    const knownBad = `
      interface SubstituteAdminUserList {
        items: unknown[];
        next_cursor: string | null;
      }
      type SubstituteAdminUser = {
        id: string;
        email: string;
        display_name: string;
        roles: string[];
        is_active: boolean;
        must_change_password: boolean;
      };
    `;

    expect(findHandwrittenAdminUserWireTypes("known-bad.ts", knownBad)).toEqual(
      [
        "known-bad.ts:SubstituteAdminUserList",
        "known-bad.ts:SubstituteAdminUser",
      ],
    );
  });
});
