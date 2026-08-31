import ts from "typescript";
import { describe, expect, expectTypeOf, it } from "vitest";

import openApiDocument from "../../openapi.json";
import { createClient } from "./client/client";
import {
  confirmAdminActiveRevisionRevalidation,
  createAdminActiveRevisionRevalidationJob,
  getAdminActiveRevisionRevalidationJob,
  getAdminProductReactivationEligibility,
  getAdminRepositoryBranch,
  listAdminRevisionMappings,
  listAdminUsers,
} from "./client/sdk.gen";
import type {
  AdminActiveRevisionRevalidationConfirmationRequest,
  AdminActiveRevisionRevalidationConfirmationResponse,
  AdminActiveRevisionRevalidationJobCreateRequest,
  AdminActiveRevisionRevalidationJobResponse,
  AdminBranchListResponse,
  AdminBranchResponse,
  AdminMappingListResponse,
  AdminRepositoryListResponse,
  AdminProductReactivationEligibilityResponse,
  AdminUserListResponse,
  ConfirmAdminActiveRevisionRevalidationData,
  ConfirmAdminActiveRevisionRevalidationResponse,
  CreateAdminActiveRevisionRevalidationJobData,
  CreateAdminActiveRevisionRevalidationJobResponse,
  GetAdminActiveRevisionRevalidationJobData,
  GetAdminActiveRevisionRevalidationJobResponse,
  GetAdminProductReactivationEligibilityData,
  GetAdminProductReactivationEligibilityResponse,
  GetAdminRepositoryBranchData,
  GetAdminRepositoryBranchResponse,
  ListAdminRevisionMappingsData,
  ListAdminRevisionMappingsResponse,
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
  operationId?: string;
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
  "authorization_url",
  "client_secret",
  "credentials",
  "encryption_key",
  "next",
  "next_url",
  "provider_body",
  "provider_next",
  "provider_next_url",
  "provider_url",
  "raw_body",
  "refresh_token",
  "refresh_token_ciphertext",
  "source_bytes",
  "state_expires_in",
  "temporary_password",
  "token_ciphertext",
]);

const handwrittenSources = import.meta.glob("/src/**/*.{ts,tsx}", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

const generatedSdkSource = handwrittenSources["/src/api/client/sdk.gen.ts"];
const generatedTypesSource = handwrittenSources["/src/api/client/types.gen.ts"];

function createRecordingApiClient(responseBody: unknown) {
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

  return { apiClient, requests };
}

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

function generatedTypeAliasesWithPrefix(
  sourceText: string,
  prefix: string,
): string {
  const source = ts.createSourceFile(
    "types.gen.ts",
    sourceText,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );

  return source.statements
    .filter(
      (statement): statement is ts.TypeAliasDeclaration =>
        ts.isTypeAliasDeclaration(statement) &&
        statement.name.text.startsWith(prefix),
    )
    .map((statement) => statement.getText(source))
    .join("\n");
}

const forbiddenWireShapes = [
  ["items", "next_cursor"],
  ["display_name", "email", "id", "is_active", "must_change_password", "roles"],
].map((shape) => shape.sort().join("\u0000"));

const phaseTwoAdminOperationIds = new Map([
  ["GET /api/v1/admin/bitbucket", "get_admin_bitbucket_status"],
  ["POST /api/v1/admin/bitbucket/connect", "connect_admin_bitbucket_oauth"],
  ["POST /api/v1/admin/bitbucket/reconnect", "reconnect_admin_bitbucket_oauth"],
  [
    "POST /api/v1/admin/bitbucket/revoke",
    "revoke_admin_bitbucket_connection_locally",
  ],
  ["GET /api/v1/admin/preview-jobs/{job_id}", "get_admin_preview_job"],
  [
    "POST /api/v1/admin/preview-jobs/{job_id}/confirmation",
    "confirm_admin_preview_job",
  ],
  [
    "GET /api/v1/admin/active-revision-revalidation-jobs/{job_id}",
    "get_admin_active_revision_revalidation_job",
  ],
  [
    "POST /api/v1/admin/active-revision-revalidation-jobs/{job_id}/confirmation",
    "confirm_admin_active_revision_revalidation",
  ],
  ["GET /api/v1/admin/products", "list_admin_products"],
  ["POST /api/v1/admin/products", "create_admin_product"],
  ["GET /api/v1/admin/products/{product_id}", "get_admin_product"],
  [
    "PATCH /api/v1/admin/products/{product_id}",
    "update_admin_product_candidate",
  ],
  [
    "GET /api/v1/admin/products/{product_id}/candidate/mappings",
    "list_admin_candidate_mappings",
  ],
  [
    "POST /api/v1/admin/products/{product_id}/candidate/mappings",
    "create_admin_candidate_mapping",
  ],
  [
    "PATCH /api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}",
    "update_admin_candidate_mapping",
  ],
  [
    "POST /api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs",
    "create_admin_preview_job",
  ],
  [
    "GET /api/v1/admin/products/{product_id}/revisions/{revision_id}/mappings",
    "list_admin_revision_mappings",
  ],
  [
    "GET /api/v1/admin/products/{product_id}/revisions/{revision_id}/reactivation-eligibility",
    "get_admin_product_reactivation_eligibility",
  ],
  [
    "POST /api/v1/admin/products/{product_id}/revisions/{revision_id}/mappings/{mapping_id}/revalidation-preview-jobs",
    "create_admin_active_revision_revalidation_job",
  ],
  [
    "POST /api/v1/admin/products/{product_id}/deactivate",
    "deactivate_admin_product",
  ],
  [
    "POST /api/v1/admin/products/{product_id}/publish",
    "publish_admin_product_candidate",
  ],
  [
    "POST /api/v1/admin/products/{product_id}/reactivate",
    "reactivate_admin_product",
  ],
  ["GET /api/v1/admin/repositories", "list_admin_repositories"],
  ["POST /api/v1/admin/repositories", "create_admin_repository"],
  ["GET /api/v1/admin/repositories/{repository_id}", "get_admin_repository"],
  [
    "GET /api/v1/admin/repositories/{repository_id}/branch",
    "get_admin_repository_branch",
  ],
  [
    "GET /api/v1/admin/repositories/{repository_id}/branches",
    "list_admin_repository_branches",
  ],
  [
    "GET /api/v1/admin/repositories/{repository_id}/sources",
    "discover_admin_repository_sources",
  ],
  ["GET /api/v1/admin/users", "list_admin_users"],
  ["POST /api/v1/admin/users", "create_admin_user"],
  ["PATCH /api/v1/admin/users/{user_id}", "update_admin_user"],
  ["POST /api/v1/admin/users/{user_id}/deactivate", "deactivate_admin_user"],
  ["POST /api/v1/admin/users/{user_id}/reactivate", "reactivate_admin_user"],
  [
    "POST /api/v1/admin/users/{user_id}/reset-password",
    "reset_admin_user_password",
  ],
]);

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
  it("exposes exact active-revision recovery operations and closed generated shapes", async () => {
    const productId = "10000000-0000-4000-8000-000000000001";
    const revisionId = "20000000-0000-4000-8000-000000000002";
    const mappingId = "30000000-0000-4000-8000-000000000003";
    const jobId = "40000000-0000-4000-8000-000000000004";
    const commitHash = "a".repeat(40);
    const eligibilityBody = {
      product_id: productId,
      active_revision_id: revisionId,
      active_revision_version: 4,
      eligible: false,
      blocker_codes: ["revalidation_confirmation_required"],
      mappings: [
        {
          mapping_id: mappingId,
          is_current: false,
          blocker_codes: ["revalidation_confirmation_required"],
        },
      ],
    } satisfies AdminProductReactivationEligibilityResponse;
    const createBody = {
      expected_active_revision_version: 4,
      commits: [{ role: "direct", commit_hash: commitHash }],
    } satisfies AdminActiveRevisionRevalidationJobCreateRequest;
    const confirmationBody = {
      active_revision_id: revisionId,
      active_revision_version: 4,
      mapping_id: mappingId,
      connection_generation: 7,
      commits: [{ role: "direct", commit_hash: commitHash }],
      preview_digest: "f".repeat(64),
      layout_candidate_id: "50000000-0000-4000-8000-000000000005",
      layout_candidate_version: 1,
    } satisfies AdminActiveRevisionRevalidationConfirmationRequest;
    const { apiClient, requests } = createRecordingApiClient(eligibilityBody);

    const eligibility = await getAdminProductReactivationEligibility({
      auth: "phase-two-memory-bearer",
      client: apiClient,
      path: { product_id: productId, revision_id: revisionId },
      query: { expected_active_revision_version: 4 },
    });
    await createAdminActiveRevisionRevalidationJob({
      auth: "phase-two-memory-bearer",
      body: createBody,
      client: apiClient,
      path: {
        product_id: productId,
        revision_id: revisionId,
        mapping_id: mappingId,
      },
    });
    await getAdminActiveRevisionRevalidationJob({
      auth: "phase-two-memory-bearer",
      client: apiClient,
      path: { job_id: jobId },
    });
    await confirmAdminActiveRevisionRevalidation({
      auth: "phase-two-memory-bearer",
      body: confirmationBody,
      client: apiClient,
      path: { job_id: jobId },
    });

    expectTypeOf(eligibility.data).toEqualTypeOf<
      GetAdminProductReactivationEligibilityResponse | undefined
    >();
    expectTypeOf<
      CreateAdminActiveRevisionRevalidationJobData["body"]
    >().toEqualTypeOf<AdminActiveRevisionRevalidationJobCreateRequest>();
    expectTypeOf<
      ConfirmAdminActiveRevisionRevalidationData["body"]
    >().toEqualTypeOf<AdminActiveRevisionRevalidationConfirmationRequest>();
    expectTypeOf<
      GetAdminProductReactivationEligibilityData["path"]
    >().toEqualTypeOf<{ product_id: string; revision_id: string }>();
    expectTypeOf<
      GetAdminProductReactivationEligibilityData["query"]
    >().toEqualTypeOf<{ expected_active_revision_version: number }>();
    expectTypeOf<CreateAdminActiveRevisionRevalidationJobResponse>().toEqualTypeOf<AdminActiveRevisionRevalidationJobResponse>();
    expectTypeOf<GetAdminActiveRevisionRevalidationJobResponse>().toEqualTypeOf<AdminActiveRevisionRevalidationJobResponse>();
    expectTypeOf<ConfirmAdminActiveRevisionRevalidationResponse>().toEqualTypeOf<AdminActiveRevisionRevalidationConfirmationResponse>();
    expectTypeOf<
      GetAdminActiveRevisionRevalidationJobData["path"]
    >().toEqualTypeOf<{
      job_id: string;
    }>();

    expect(requests.map((request) => request.method)).toEqual([
      "GET",
      "POST",
      "GET",
      "POST",
    ]);
    expect(requests.map((request) => new URL(request.url).pathname)).toEqual([
      `/api/v1/admin/products/${productId}/revisions/${revisionId}/reactivation-eligibility`,
      `/api/v1/admin/products/${productId}/revisions/${revisionId}/mappings/${mappingId}/revalidation-preview-jobs`,
      `/api/v1/admin/active-revision-revalidation-jobs/${jobId}`,
      `/api/v1/admin/active-revision-revalidation-jobs/${jobId}/confirmation`,
    ]);
    expect(
      new URL(requests[0]!.url).searchParams.get(
        "expected_active_revision_version",
      ),
    ).toBe("4");
  });

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
    const { apiClient, requests } = createRecordingApiClient(responseBody);

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

  it("calls the owned revision mapping operation with exact path IDs and an opaque cursor", async () => {
    const responseBody = {
      items: [],
      next_cursor: "vf.cursor/opaque%value?with#reserved",
    } satisfies AdminMappingListResponse;
    const { apiClient, requests } = createRecordingApiClient(responseBody);
    const productId = "10000000-0000-4000-8000-000000000001";
    const revisionId = "20000000-0000-4000-8000-000000000002";
    const cursor = "vf.cursor/incoming%value?with#reserved";

    const result = await listAdminRevisionMappings({
      auth: "phase-two-memory-bearer",
      client: apiClient,
      path: { product_id: productId, revision_id: revisionId },
      query: { cursor, limit: 100 },
    });

    expectTypeOf(result.data).toEqualTypeOf<
      ListAdminRevisionMappingsResponse | undefined
    >();
    expect(result.data).toEqual(responseBody);
    expect(requests).toHaveLength(1);
    const requestUrl = new URL(requests[0]!.url);
    expect(requestUrl.pathname).toBe(
      `/api/v1/admin/products/${productId}/revisions/${revisionId}/mappings`,
    );
    expect(requestUrl.searchParams.get("cursor")).toBe(cursor);
    expect(requestUrl.searchParams.get("limit")).toBe("100");
    expect(requestUrl.searchParams.get("product_id")).toBeNull();
    expect(requestUrl.searchParams.get("revision_id")).toBeNull();
    expect(requests[0]?.headers.get("Authorization")).toBe(
      "Bearer phase-two-memory-bearer",
    );
  });

  it("round-trips reserved branch characters through the required query input", async () => {
    const branchName =
      "release/slash%2F Unicode à?hash#colon:@amp&equals=plus+$comma,semi;[]";
    const responseBody = {
      commit_hash: "f".repeat(40),
      name: branchName,
    } satisfies AdminBranchResponse;
    const { apiClient, requests } = createRecordingApiClient(responseBody);
    const repositoryId = "30000000-0000-4000-8000-000000000003";

    const result = await getAdminRepositoryBranch({
      auth: "phase-two-memory-bearer",
      client: apiClient,
      path: { repository_id: repositoryId },
      query: { branch_name: branchName },
    });

    expectTypeOf(result.data).toEqualTypeOf<
      GetAdminRepositoryBranchResponse | undefined
    >();
    expect(result.data).toEqual(responseBody);
    expect(requests).toHaveLength(1);
    const requestUrl = new URL(requests[0]!.url);
    expect(requestUrl.pathname).toBe(
      `/api/v1/admin/repositories/${repositoryId}/branch`,
    );
    expect(requestUrl.searchParams.get("branch_name")).toBe(branchName);
    expect(requestUrl.pathname).not.toContain("release");
    expect(requestUrl.hash).toBe("");
    expect(requests[0]?.headers.get("Authorization")).toBe(
      "Bearer phase-two-memory-bearer",
    );
  });

  it("keeps generated path, query, and cursor types exact", () => {
    expectTypeOf<ListAdminRevisionMappingsData["path"]>().toEqualTypeOf<{
      product_id: string;
      revision_id: string;
    }>();
    expectTypeOf<
      NonNullable<ListAdminRevisionMappingsData["query"]>
    >().toEqualTypeOf<{
      cursor?: string | null;
      limit?: number;
    }>();
    expectTypeOf<GetAdminRepositoryBranchData["path"]>().toEqualTypeOf<{
      repository_id: string;
    }>();
    expectTypeOf<GetAdminRepositoryBranchData["query"]>().toEqualTypeOf<{
      branch_name: string;
    }>();
    expectTypeOf<AdminRepositoryListResponse["next_cursor"]>().toEqualTypeOf<
      string | null
    >();
    expectTypeOf<AdminBranchListResponse["next_cursor"]>().toEqualTypeOf<
      string | null
    >();
    expectTypeOf<AdminMappingListResponse["next_cursor"]>().toEqualTypeOf<
      string | null
    >();
  });

  it("keeps list and provider-facing admin schemas free of credential material", () => {
    const guardedSchemas = [
      "AdminUserListResponse",
      ...Object.keys(openApi.components.schemas).filter((name) =>
        /^(?:AdminBitbucket|AdminBranch|AdminDiscovery|AdminMapping|AdminRepository|AdminSource)/u.test(
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

    const bitbucketStatus =
      openApi.components.schemas.AdminBitbucketStatusResponse;
    expect(bitbucketStatus).toBeDefined();
    expect(Object.keys(bitbucketStatus?.properties ?? {}).sort()).toEqual([
      "connected_at",
      "expires_at",
      "revoked_at",
      "scope_label",
      "scope_profile",
      "status",
    ]);
    expect(bitbucketStatus?.properties).not.toHaveProperty("workspace");
  });

  it("exposes direct connection controls but no callback or provider write surface", () => {
    const allowedProviderOperations = new Map([
      ["/api/v1/admin/bitbucket", ["get"]],
      ["/api/v1/admin/bitbucket/connect", ["post"]],
      ["/api/v1/admin/bitbucket/reconnect", ["post"]],
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

    expect(
      Object.keys(openApi.paths).filter((path) =>
        /(?:callback|oauth\/start)/u.test(path),
      ),
    ).toEqual([]);

    for (const [path, operation] of Object.entries(openApi.paths).filter(
      ([path]) =>
        /\/admin\/repositories\/.*\/(?:branch|branches|sources)$/u.test(path),
    )) {
      expect(Object.keys(operation), `${path} must stay read-only`).toEqual([
        "get",
      ]);
    }
  });

  it("generates direct expiry-aware operations without a credential transport type", () => {
    expect(generatedSdkSource).toContain(
      "export const connectAdminBitbucketOauth",
    );
    expect(generatedSdkSource).toContain(
      "export const reconnectAdminBitbucketOauth",
    );
    expect(generatedSdkSource).toContain(
      "export const getAdminBitbucketStatus",
    );
    expect(generatedSdkSource).not.toMatch(
      /(?:completeAdminBitbucketOauthCallback|startAdminBitbucketOauth)/u,
    );
    expect(generatedTypesSource).toContain("expires_at: string | null");
    expect(generatedTypesSource).toContain("'Reauthorization required'");

    const bitbucketGeneratedTypes = generatedTypeAliasesWithPrefix(
      generatedTypesSource,
      "AdminBitbucket",
    );
    expect(bitbucketGeneratedTypes).not.toMatch(
      /(?:authorization_url|workspace|client_secret|access_token|refresh_token|ciphertext)/u,
    );
  });

  it("freezes every Phase 2 admin operation ID", () => {
    const actual = new Map<string, string>();

    for (const [path, pathItem] of Object.entries(openApi.paths).filter(
      ([path]) => path.startsWith("/api/v1/admin/"),
    )) {
      for (const [method, operation] of Object.entries(pathItem)) {
        expect(
          operation.operationId,
          `${method.toUpperCase()} ${path}`,
        ).toBeDefined();
        actual.set(`${method.toUpperCase()} ${path}`, operation.operationId!);
      }
    }

    expect(actual).toEqual(phaseTwoAdminOperationIds);
    expect(new Set(actual.values()).size).toBe(actual.size);
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
