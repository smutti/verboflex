import ts from "typescript";
import { describe, expect, expectTypeOf, it } from "vitest";

import openApiDocument from "../../openapi.json";
import { createClient } from "./client/client";
import {
  connectAdminBitbucketOauth,
  confirmAdminActiveRevisionRevalidation,
  confirmAdminImportRewriteBaseline,
  confirmAdminPreviewJob,
  createAdminActiveRevisionRevalidationJob,
  deleteTranslationConstraint,
  getAdminBitbucketStatus,
  getAdminActiveRevisionRevalidationJob,
  getAdminImport,
  getAdminImportRewriteComparison,
  getAdminProductReactivationEligibility,
  getAdminRepositoryBranch,
  getTranslationGroup,
  listAdminPublishedMappingImports,
  listAdminRevisionMappings,
  listTranslationOptions,
  listAdminUsers,
  putTranslationConstraint,
  reconnectAdminBitbucketOauth,
  saveTranslationProposal,
  searchTranslations,
  startAdminPublishedMappingImport,
} from "./client/sdk.gen";
import type {
  AdminActiveRevisionRevalidationConfirmationRequest,
  AdminActiveRevisionRevalidationConfirmationResponse,
  AdminActiveRevisionRevalidationJobCreateRequest,
  AdminActiveRevisionRevalidationJobResponse,
  AdminBranchListResponse,
  AdminBranchResponse,
  AdminImportRewriteConfirmationRequest,
  AdminImportRewriteComparisonResponse,
  AdminMappingListResponse,
  AdminPreviewConfirmationRequest,
  AdminPreviewConfirmationResponse,
  AdminProductResponse,
  AdminPublishedMappingImportListResponse,
  AdminPublishedMappingImportResponse,
  AdminRepositoryListResponse,
  AdminProductReactivationEligibilityResponse,
  AdminUserListResponse,
  DeleteTranslationConstraintData,
  DeleteTranslationConstraintRequest,
  DeleteTranslationConstraintResponse,
  ConfirmAdminActiveRevisionRevalidationData,
  ConfirmAdminActiveRevisionRevalidationResponse,
  ConfirmAdminImportRewriteBaselineData,
  ConfirmAdminImportRewriteBaselineResponse,
  ConfirmAdminPreviewJobData,
  ConfirmAdminPreviewJobResponse,
  CreateAdminActiveRevisionRevalidationJobData,
  CreateAdminActiveRevisionRevalidationJobResponse,
  GetAdminActiveRevisionRevalidationJobData,
  GetAdminActiveRevisionRevalidationJobResponse,
  GetAdminImportData,
  GetAdminImportResponse,
  GetAdminImportRewriteComparisonData,
  GetAdminImportRewriteComparisonResponse,
  GetAdminProductReactivationEligibilityData,
  GetAdminProductReactivationEligibilityResponse,
  GetAdminRepositoryBranchData,
  GetAdminRepositoryBranchResponse,
  GetTranslationGroupData,
  GetTranslationGroupResponse,
  ImportDatasetStatus,
  ImportParserIssue,
  ListTranslationOptionsData,
  ListTranslationOptionsResponse,
  ListAdminRevisionMappingsData,
  ListAdminRevisionMappingsResponse,
  ListAdminPublishedMappingImportsData,
  ListAdminPublishedMappingImportsResponse,
  ListAdminUsersResponse,
  PutTranslationConstraintData,
  PutTranslationConstraintRequest,
  PutTranslationConstraintResponse,
  SaveTranslationProposalData,
  SaveTranslationProposalRequest,
  SaveTranslationProposalResponse,
  SearchTranslationsData,
  SearchTranslationsResponse,
  StartAdminPublishedMappingImportData,
  StartAdminPublishedMappingImportResponse,
  TranslationConstraintMutationResponse,
  TranslationConstraintProjectionResponse,
  TranslationGroupDetailResponse,
  TranslationOptionsResponse,
  TranslationProposalResponse,
  TranslationProvenanceResponse,
  TranslationSearchPageResponse,
  TranslationValueResponse,
} from "./client/types.gen";

type OpenApiSchema = {
  additionalProperties?: boolean;
  const?: unknown;
  enum?: unknown[];
  required?: string[];
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
  "attempt_history",
  "attempts",
  "authorization_url",
  "client_secret",
  "correlation_id",
  "credentials",
  "database_query",
  "encryption_key",
  "exception",
  "exception_message",
  "next",
  "next_url",
  "provider_body",
  "provider_response",
  "provider_status_text",
  "provider_next",
  "provider_next_url",
  "provider_url",
  "queue_name",
  "raw_authority",
  "raw_body",
  "raw_source",
  "refresh_token",
  "refresh_token_ciphertext",
  "source_bytes",
  "source_file_content",
  "sql",
  "stack",
  "stack_trace",
  "state_expires_in",
  "temporary_password",
  "token",
  "token_ciphertext",
  "token_type",
  "task_id",
  "staging_path",
  "effective_authority",
  "generation",
  "scope",
]);

const handwrittenSources = import.meta.glob("/src/**/*.{ts,tsx}", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

const generatedSdkSource = handwrittenSources["/src/api/client/sdk.gen.ts"];
const generatedTypesSource = handwrittenSources["/src/api/client/types.gen.ts"];
const generatedIndexSource = handwrittenSources["/src/api/client/index.ts"];

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

function generatedTypeAliases(
  sourceText: string,
  names: readonly string[] | string,
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
        (typeof names === "string"
          ? statement.name.text.startsWith(names)
          : names.includes(statement.name.text)),
    )
    .map((statement) => statement.getText(source))
    .join("\n");
}

const forbiddenWireShapes = [
  ["items", "next_cursor"],
  ["display_name", "email", "id", "is_active", "must_change_password", "roles"],
].map((shape) => shape.sort().join("\u0000"));

const phaseThreeAdminOperationIds = new Map([
  [
    "GET /api/v1/admin/products/{product_id}/source-fallback",
    "get_admin_source_fallback",
  ],
  [
    "PUT /api/v1/admin/products/{product_id}/source-fallback",
    "update_admin_source_fallback",
  ],
  [
    "GET /api/v1/admin/bitbucket/repositories",
    "list_admin_bitbucket_repositories",
  ],
  [
    "PUT /api/v1/admin/bitbucket/repositories/{repository_slug}",
    "select_admin_bitbucket_repository",
  ],
  ["GET /api/v1/admin/bitbucket/workspace", "get_admin_bitbucket_workspace"],
  ["PUT /api/v1/admin/bitbucket/workspace", "update_admin_bitbucket_workspace"],
  ["POST /api/v1/admin/github/repositories", "connect_admin_github_repository"],
  [
    "GET /api/v1/admin/products/{product_id}/summary",
    "get_admin_product_summary",
  ],
  ["GET /api/v1/admin/bitbucket", "get_admin_bitbucket_status"],
  ["POST /api/v1/admin/bitbucket/connect", "connect_admin_bitbucket_oauth"],
  ["POST /api/v1/admin/bitbucket/reconnect", "reconnect_admin_bitbucket_oauth"],
  [
    "POST /api/v1/admin/bitbucket/revoke",
    "revoke_admin_bitbucket_connection_locally",
  ],
  ["GET /api/v1/admin/preview-jobs/{job_id}", "get_admin_preview_job"],
  [
    "GET /api/v1/admin/preview-jobs/{job_id}/duplicates",
    "get_admin_preview_duplicates",
  ],
  [
    "GET /api/v1/admin/products/{product_id}/imports/{import_id}/duplicates",
    "get_admin_import_duplicates",
  ],
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
  ["DELETE /api/v1/admin/products/{product_id}", "delete_admin_product"],
  [
    "GET /api/v1/admin/products/{product_id}/imports/{import_id}",
    "get_admin_import",
  ],
  [
    "GET /api/v1/admin/products/{product_id}/published/mapping-imports",
    "list_admin_published_mapping_imports",
  ],
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
    "GET /api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs/latest",
    "get_admin_latest_candidate_preview_job",
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
    "GET /api/v1/admin/products/{product_id}/revisions/{revision_id}/mappings/{mapping_id}/revalidation-preview-jobs/latest",
    "get_admin_latest_active_revision_revalidation_job",
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
    "POST /api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports",
    "start_admin_published_mapping_import",
  ],
  [
    "GET /api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports/{import_id}/rewrite-comparison",
    "get_admin_import_rewrite_comparison",
  ],
  [
    "POST /api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports/{import_id}/rewrite-confirmation",
    "confirm_admin_import_rewrite_baseline",
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
  ["GET /api/v1/admin/users/{user_id}/products", "list_admin_user_products"],
  ["POST /api/v1/admin/users", "create_admin_user"],
  ["PATCH /api/v1/admin/users/{user_id}", "update_admin_user"],
  ["POST /api/v1/admin/users/{user_id}/deactivate", "deactivate_admin_user"],
  ["POST /api/v1/admin/users/{user_id}/reactivate", "reactivate_admin_user"],
  [
    "POST /api/v1/admin/users/{user_id}/reset-password",
    "reset_admin_user_password",
  ],
]);

const phaseFiveTranslationOperationIds = new Map([
  [
    "GET /api/v1/translations/{group_id}/code-context",
    "getTranslationCodeContext",
  ],
  [
    "GET /api/v1/translations/{group_id}/screenshots",
    "listTranslationScreenshots",
  ],
  [
    "GET /api/v1/translations/{group_id}/screenshots/{job_id}",
    "getTranslationScreenshot",
  ],
  [
    "GET /api/v1/translations/{group_id}/screenshots/{job_id}/image",
    "getTranslationScreenshotImage",
  ],
  [
    "PUT /api/v1/translations/{group_id}/screenshots/{job_id}",
    "requestTranslationScreenshot",
  ],
  [
    "DELETE /api/v1/translations/{group_id}/screenshots/{job_id}",
    "cancelTranslationScreenshot",
  ],
  ["GET /api/v1/translations/keys", "searchTranslationKeys"],
  ["GET /api/v1/translations/options", "listTranslationOptions"],
  ["GET /api/v1/translations", "searchTranslations"],
  ["GET /api/v1/translations/{translation_group_id}", "getTranslationGroup"],
  [
    "PUT /api/v1/translations/{translation_group_id}/constraints/{language}",
    "putTranslationConstraint",
  ],
  [
    "DELETE /api/v1/translations/{translation_group_id}/constraints/{language}",
    "deleteTranslationConstraint",
  ],
  [
    "PUT /api/v1/translations/{translation_group_id}/proposal",
    "saveTranslationProposal",
  ],
  [
    "POST /api/v1/translations/{translation_group_id}/proposal/state",
    "transitionTranslationProposal",
  ],
  [
    "GET /api/v1/translations/{translation_group_id}/activity",
    "listTranslationReviewActivity",
  ],
  [
    "GET /api/v1/translations/{translation_group_id}/comments",
    "listTranslationComments",
  ],
  [
    "POST /api/v1/translations/{translation_group_id}/comments",
    "createTranslationComment",
  ],
  [
    "GET /api/v1/translations/{translation_group_id}/comments/anchor",
    "getTranslationCommentAnchor",
  ],
  [
    "PUT /api/v1/translations/{translation_group_id}/comments/{comment_id}",
    "updateTranslationComment",
  ],
  [
    "DELETE /api/v1/translations/{translation_group_id}/comments/{comment_id}",
    "deleteTranslationComment",
  ],
  [
    "GET /api/v1/translations/{translation_group_id}/comments/{comment_id}/versions",
    "listTranslationCommentVersions",
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

describe("canonical generated API client", () => {
  it("calls exactly six generated translation operations with encoded inputs and bearer authority", async () => {
    const groupId = "10000000-0000-4000-8000-000000000001";
    const productId = "20000000-0000-4000-8000-000000000002";
    const query = "menu/key?contains=# +% & Unicode à";
    const cursor = "vf.translation/cursor?opaque=# +% & next";
    const language = "zh-Hant-TW";
    const putBody = {
      max_chars: 0,
      expected_version: 7,
    } satisfies PutTranslationConstraintRequest;
    const deleteBody = {
      expected_version: 8,
    } satisfies DeleteTranslationConstraintRequest;
    const proposalBody = {
      expected_version: 0,
      values: [
        {
          translation_value_id: groupId,
          selector_version: 1,
          selector_digest: "a".repeat(64),
          basis_revision_number: 3,
          basis_digest: "b".repeat(64),
          proposed_text: "",
        },
      ],
    } satisfies SaveTranslationProposalRequest;
    const { apiClient, requests } = createRecordingApiClient({});
    const authority = "phase-four-memory-bearer";

    await listTranslationOptions({ auth: authority, client: apiClient });
    await searchTranslations({
      auth: authority,
      client: apiClient,
      query: {
        q: query,
        product_id: productId,
        language,
        state: "approved",
        violation: "over_limit",
        deleted: "all",
        page_size: 50,
        cursor,
      },
    });
    await getTranslationGroup({
      auth: authority,
      client: apiClient,
      path: { translation_group_id: groupId },
    });
    await putTranslationConstraint({
      auth: authority,
      body: putBody,
      client: apiClient,
      path: { translation_group_id: groupId, language },
    });
    await deleteTranslationConstraint({
      auth: authority,
      body: deleteBody,
      client: apiClient,
      path: { translation_group_id: groupId, language },
    });
    await saveTranslationProposal({
      auth: authority,
      body: proposalBody,
      client: apiClient,
      path: { translation_group_id: groupId },
    });

    expect(requests.map((request) => request.method)).toEqual([
      "GET",
      "GET",
      "GET",
      "PUT",
      "DELETE",
      "PUT",
    ]);
    expect(requests.map((request) => new URL(request.url).pathname)).toEqual([
      "/api/v1/translations/options",
      "/api/v1/translations",
      `/api/v1/translations/${groupId}`,
      `/api/v1/translations/${groupId}/constraints/${language}`,
      `/api/v1/translations/${groupId}/constraints/${language}`,
      `/api/v1/translations/${groupId}/proposal`,
    ]);
    const searchUrl = new URL(requests[1]!.url);
    expect(searchUrl.searchParams.get("q")).toBe(query);
    expect(searchUrl.searchParams.get("product_id")).toBe(productId);
    expect(searchUrl.searchParams.get("language")).toBe(language);
    expect(searchUrl.searchParams.get("state")).toBe("approved");
    expect(searchUrl.searchParams.get("violation")).toBe("over_limit");
    expect(searchUrl.searchParams.get("deleted")).toBe("all");
    expect(searchUrl.searchParams.get("page_size")).toBe("50");
    expect(searchUrl.searchParams.get("cursor")).toBe(cursor);
    expect(searchUrl.hash).toBe("");
    expect(requests.slice(0, 3).every((request) => request.body === null)).toBe(
      true,
    );
    expect(await requests[3]!.clone().json()).toEqual(putBody);
    expect(await requests[4]!.clone().json()).toEqual(deleteBody);
    expect(await requests[5]!.clone().json()).toEqual(proposalBody);
    expect(
      requests.every(
        (request) =>
          request.headers.get("Authorization") === `Bearer ${authority}`,
      ),
    ).toBe(true);
    expect(requests.every((request) => !request.url.includes(authority))).toBe(
      true,
    );
  });

  it("exports exact translation and parser outcome types without handwritten transport", () => {
    expectTypeOf<
      ListTranslationOptionsData["url"]
    >().toEqualTypeOf<"/api/v1/translations/options">();
    expectTypeOf<ListTranslationOptionsResponse>().toEqualTypeOf<TranslationOptionsResponse>();
    expectTypeOf<NonNullable<SearchTranslationsData["query"]>>().toEqualTypeOf<{
      q?: string | null;
      product_id?: string | null;
      language?: string | null;
      state?: "draft" | "approved" | "rejected" | null;
      violation?: "over_limit" | "within_limit" | "no_max" | null;
      work_status?:
        "needs_translation" | "needs_review" | "source_changed" | null;
      deleted?: "active" | "deleted" | "all";
      page_size?: 50;
      cursor?: string | null;
    }>();
    expectTypeOf<SearchTranslationsResponse>().toEqualTypeOf<TranslationSearchPageResponse>();
    expectTypeOf<GetTranslationGroupData["path"]>().toEqualTypeOf<{
      translation_group_id: string;
    }>();
    expectTypeOf<GetTranslationGroupResponse>().toEqualTypeOf<TranslationGroupDetailResponse>();
    expectTypeOf<PutTranslationConstraintData["path"]>().toEqualTypeOf<{
      translation_group_id: string;
      language: string;
    }>();
    expectTypeOf<
      PutTranslationConstraintData["body"]
    >().toEqualTypeOf<PutTranslationConstraintRequest>();
    expectTypeOf<PutTranslationConstraintResponse>().toEqualTypeOf<TranslationConstraintMutationResponse>();
    expectTypeOf<
      DeleteTranslationConstraintData["body"]
    >().toEqualTypeOf<DeleteTranslationConstraintRequest>();
    expectTypeOf<DeleteTranslationConstraintResponse>().toEqualTypeOf<TranslationConstraintMutationResponse>();
    expectTypeOf<SaveTranslationProposalData["path"]>().toEqualTypeOf<{
      translation_group_id: string;
    }>();
    expectTypeOf<
      SaveTranslationProposalData["body"]
    >().toEqualTypeOf<SaveTranslationProposalRequest>();
    expectTypeOf<SaveTranslationProposalResponse>().toEqualTypeOf<TranslationProposalResponse>();

    expectTypeOf<
      TranslationValueResponse["selector_version"]
    >().toEqualTypeOf<1>();
    expectTypeOf<TranslationValueResponse["selector_kind"]>().toEqualTypeOf<
      | "scalar"
      | "android_quantity"
      | "android_array_item"
      | "qt_numerus"
      | "qt_length_variant"
      | "json_path"
    >();
    expectTypeOf<TranslationValueResponse["structure"]>().toEqualTypeOf<
      Array<unknown>
    >();
    expectTypeOf<TranslationValueResponse["source_text"]>().toEqualTypeOf<
      string | null
    >();
    expectTypeOf<TranslationValueResponse["translated_text"]>().toEqualTypeOf<
      string | null
    >();
    expectTypeOf<TranslationValueResponse["deleted_at"]>().toEqualTypeOf<
      string | null
    >();
    expectTypeOf<
      TranslationValueResponse["provenance"]
    >().toEqualTypeOf<TranslationProvenanceResponse | null>();
    expectTypeOf<
      TranslationConstraintProjectionResponse["maximum"]
    >().toEqualTypeOf<number | null>();
    expectTypeOf<
      TranslationConstraintProjectionResponse["source"]
    >().toEqualTypeOf<"none" | "base_default" | "language_override">();
    expectTypeOf<
      TranslationConstraintProjectionResponse["status"]
    >().toEqualTypeOf<"no_max" | "within_limit" | "over_limit">();
    expectTypeOf<
      TranslationConstraintMutationResponse["version"]
    >().toEqualTypeOf<number | null>();
    expectTypeOf<
      AdminPublishedMappingImportResponse["dataset_status"]
    >().toEqualTypeOf<ImportDatasetStatus>();
    expectTypeOf<
      AdminPublishedMappingImportResponse["parser_issues"]
    >().toEqualTypeOf<Array<ImportParserIssue>>();
    expectTypeOf<
      AdminPublishedMappingImportResponse["parser_issue_remaining_count"]
    >().toEqualTypeOf<number>();

    const actualOperations = new Map<string, string>();
    for (const [path, pathItem] of Object.entries(openApi.paths).filter(
      ([path]) => path.startsWith("/api/v1/translations"),
    )) {
      for (const [method, operation] of Object.entries(pathItem)) {
        actualOperations.set(
          `${method.toUpperCase()} ${path}`,
          operation.operationId!,
        );
      }
    }
    expect(actualOperations).toEqual(phaseFiveTranslationOperationIds);
    expect(new Set(actualOperations.values()).size).toBe(21);

    for (const operation of phaseFiveTranslationOperationIds.values()) {
      expect(
        generatedSdkSource.match(
          new RegExp(`export const ${operation}\\b`, "gu"),
        ),
      ).toHaveLength(1);
      expect(
        generatedIndexSource.match(new RegExp(`\\b${operation}\\b`, "gu")),
      ).toHaveLength(1);
    }

    const guardedSchemas = Object.keys(openApi.components.schemas).filter(
      (name) =>
        /^(?:Translation|PutTranslationConstraint|DeleteTranslationConstraint|ImportParserIssue$|ImportDatasetStatus$)/u.test(
          name,
        ),
    );
    for (const schemaName of guardedSchemas) {
      const schema = openApi.components.schemas[schemaName];
      expect(schema, `${schemaName} must remain canonical`).toBeDefined();
      const leaked = [...collectSchemaProperties(schema!)].filter((property) =>
        sensitiveAdminProperties.has(property),
      );
      expect(leaked, `${schemaName} leaked internal material`).toEqual([]);
    }

    const handwrittenTranslationTransports = Object.entries(handwrittenSources)
      .filter(
        ([file]) => !file.includes("/api/client/") && !file.includes(".test."),
      )
      .filter(([, source]) => source.includes("/api/v1/translations"))
      .map(([file]) => file);
    expect(handwrittenTranslationTransports).toEqual([]);
    expect(generatedSdkSource).not.toMatch(
      /(?:localStorage|sessionStorage|indexedDB)/u,
    );
  });

  it("calls exactly five generated import operations through VerboFlex bearer routes", async () => {
    const productId = "10000000-0000-4000-8000-000000000001";
    const mappingId = "20000000-0000-4000-8000-000000000002";
    const importId = "30000000-0000-4000-8000-000000000003";
    const proposalId = "40000000-0000-4000-8000-000000000004";
    const proposedExecutionId = "50000000-0000-4000-8000-000000000005";
    const proposalDigest = "a".repeat(64);
    const cursor = "vf.import/cursor?opaque#value%2F";
    const confirmationBody = {
      proposal_id: proposalId,
      proposed_execution_id: proposedExecutionId,
      proposal_digest: proposalDigest,
    } satisfies AdminImportRewriteConfirmationRequest;
    const { apiClient, requests } = createRecordingApiClient({});
    const authority = "phase-three-memory-bearer";

    await listAdminPublishedMappingImports({
      auth: authority,
      client: apiClient,
      path: { product_id: productId },
      query: { cursor, limit: 100, status: "attention" },
    });
    await startAdminPublishedMappingImport({
      auth: authority,
      client: apiClient,
      path: { product_id: productId, mapping_id: mappingId },
    });
    await getAdminImport({
      auth: authority,
      client: apiClient,
      path: { product_id: productId, import_id: importId },
    });
    await getAdminImportRewriteComparison({
      auth: authority,
      client: apiClient,
      path: {
        product_id: productId,
        mapping_id: mappingId,
        import_id: importId,
      },
    });
    await confirmAdminImportRewriteBaseline({
      auth: authority,
      body: confirmationBody,
      client: apiClient,
      path: {
        product_id: productId,
        mapping_id: mappingId,
        import_id: importId,
      },
    });

    expect(requests.map((request) => request.method)).toEqual([
      "GET",
      "POST",
      "GET",
      "GET",
      "POST",
    ]);
    expect(requests.map((request) => new URL(request.url).pathname)).toEqual([
      `/api/v1/admin/products/${productId}/published/mapping-imports`,
      `/api/v1/admin/products/${productId}/published/mappings/${mappingId}/imports`,
      `/api/v1/admin/products/${productId}/imports/${importId}`,
      `/api/v1/admin/products/${productId}/published/mappings/${mappingId}/imports/${importId}/rewrite-comparison`,
      `/api/v1/admin/products/${productId}/published/mappings/${mappingId}/imports/${importId}/rewrite-confirmation`,
    ]);
    expect(
      requests.every(
        (request) =>
          new URL(request.url).origin === "https://api.verboflex.test",
      ),
    ).toBe(true);
    expect(
      requests.every(
        (request) =>
          request.headers.get("Authorization") === `Bearer ${authority}`,
      ),
    ).toBe(true);

    const listUrl = new URL(requests[0]!.url);
    expect(listUrl.searchParams.get("cursor")).toBe(cursor);
    expect(listUrl.searchParams.get("limit")).toBe("100");
    expect(listUrl.searchParams.get("status")).toBe("attention");
    expect(listUrl.searchParams.get("product_id")).toBeNull();
    expect(await requests[4]!.clone().json()).toEqual(confirmationBody);
    expect(requests.slice(0, 4).every((request) => request.body === null)).toBe(
      true,
    );
  });

  it("generates closed import and product types without provider mutation surface", () => {
    expectTypeOf<
      NonNullable<ListAdminPublishedMappingImportsData["query"]>
    >().toEqualTypeOf<{
      cursor?: string | null;
      limit?: number;
      status?: "all" | "attention";
    }>();
    expectTypeOf<ListAdminPublishedMappingImportsData["path"]>().toEqualTypeOf<{
      product_id: string;
    }>();
    expectTypeOf<StartAdminPublishedMappingImportData["path"]>().toEqualTypeOf<{
      product_id: string;
      mapping_id: string;
    }>();
    expectTypeOf<GetAdminImportData["path"]>().toEqualTypeOf<{
      product_id: string;
      import_id: string;
    }>();
    expectTypeOf<GetAdminImportRewriteComparisonData["path"]>().toEqualTypeOf<{
      product_id: string;
      mapping_id: string;
      import_id: string;
    }>();
    expectTypeOf<
      ConfirmAdminImportRewriteBaselineData["body"]
    >().toEqualTypeOf<AdminImportRewriteConfirmationRequest>();
    expectTypeOf<
      ConfirmAdminImportRewriteBaselineData["path"]
    >().toEqualTypeOf<{
      product_id: string;
      mapping_id: string;
      import_id: string;
    }>();
    expectTypeOf<ListAdminPublishedMappingImportsResponse>().toEqualTypeOf<AdminPublishedMappingImportListResponse>();
    expectTypeOf<StartAdminPublishedMappingImportResponse>().toEqualTypeOf<AdminPublishedMappingImportResponse>();
    expectTypeOf<GetAdminImportResponse>().toEqualTypeOf<AdminPublishedMappingImportResponse>();
    expectTypeOf<GetAdminImportRewriteComparisonResponse>().toEqualTypeOf<AdminImportRewriteComparisonResponse>();
    expectTypeOf<ConfirmAdminImportRewriteBaselineResponse>().toEqualTypeOf<AdminPublishedMappingImportResponse>();
    expectTypeOf<
      AdminProductResponse["affected_mapping_count"]
    >().toEqualTypeOf<number>();
    expectTypeOf<AdminPublishedMappingImportResponse["state"]>().toEqualTypeOf<
      | "not_imported"
      | "queued"
      | "running"
      | "current"
      | "may_be_stale"
      | "review_required"
      | "import_failed"
    >();
    expectTypeOf<AdminPublishedMappingImportResponse["action"]>().toEqualTypeOf<
      | "run_import"
      | "refresh_import"
      | "retry_import"
      | "import_in_progress"
      | "review_baseline_change"
    >();

    const guardedSchemas = Object.keys(openApi.components.schemas).filter(
      (name) =>
        /^(?:AdminImport|AdminPublishedMappingImport|AdminProductResponse$)/u.test(
          name,
        ),
    );
    for (const schemaName of guardedSchemas) {
      const schema = openApi.components.schemas[schemaName];
      expect(schema, `${schemaName} must remain generated`).toBeDefined();
      const leaked = [...collectSchemaProperties(schema!)].filter((property) =>
        sensitiveAdminProperties.has(property),
      );
      expect(leaked, `${schemaName} leaked internal/provider material`).toEqual(
        [],
      );
    }

    for (const operation of [
      "listAdminPublishedMappingImports",
      "startAdminPublishedMappingImport",
      "getAdminImport",
      "getAdminImportRewriteComparison",
      "confirmAdminImportRewriteBaseline",
      "createBranchPullRequest",
    ]) {
      expect(
        generatedSdkSource.match(
          new RegExp(`export const ${operation}\\b`, "gu"),
        ),
      ).toHaveLength(1);
    }
    expect(generatedSdkSource).not.toMatch(
      /(?:cancel(?!TranslationScreenshot)|schedule|bulk|attemptHistory|createBranch(?!PullRequest\b)|createCommit|createPullRequest|mergePullRequest|approvePullRequest|declinePullRequest)/u,
    );
    expect(generatedTypesSource).not.toMatch(
      /(?:provider_body|provider_status_text|raw_authority|raw_source|source_bytes|stack_trace|task_id|attempt_history)/u,
    );
  });

  it("confirms one exact base language through the generated bearer client", async () => {
    const jobId = "40000000-0000-4000-8000-000000000004";
    const body = {
      preview_digest: "f".repeat(64),
      layout_candidate_id: "50000000-0000-4000-8000-000000000005",
      layout_candidate_version: 1,
      base_language: "it-IT",
    } satisfies AdminPreviewConfirmationRequest;
    const responseBody = {
      job_id: jobId,
      mapping_id: "30000000-0000-4000-8000-000000000003",
      preview_digest: body.preview_digest,
      layout_candidate_id: body.layout_candidate_id,
      layout_candidate_version: 1,
      base_language: body.base_language,
      confirmed_by: "60000000-0000-4000-8000-000000000006",
      confirmed_at: "2026-09-05T10:00:00Z",
    } satisfies AdminPreviewConfirmationResponse;
    const { apiClient, requests } = createRecordingApiClient(responseBody);
    const authority = "phase-four-memory-bearer";

    const result = await confirmAdminPreviewJob({
      auth: authority,
      body,
      client: apiClient,
      path: { job_id: jobId },
    });

    expectTypeOf<
      ConfirmAdminPreviewJobData["body"]
    >().toEqualTypeOf<AdminPreviewConfirmationRequest>();
    expectTypeOf<ConfirmAdminPreviewJobResponse>().toEqualTypeOf<AdminPreviewConfirmationResponse>();
    expect(result.data).toEqual(responseBody);
    expect(requests).toHaveLength(1);
    expect(requests[0]!.method).toBe("POST");
    expect(new URL(requests[0]!.url).pathname).toBe(
      `/api/v1/admin/preview-jobs/${jobId}/confirmation`,
    );
    expect(requests[0]!.headers.get("Authorization")).toBe(
      `Bearer ${authority}`,
    );
    const serializedBody = await requests[0]!.clone().text();
    expect(serializedBody.match(/"base_language"/gu)).toHaveLength(1);
    expect(JSON.parse(serializedBody)).toEqual(body);

    const generatedPreviewTypes = generatedTypeAliases(
      generatedTypesSource,
      "AdminPreview",
    );
    expect(generatedPreviewTypes).toContain("base_language: string | null;");
    expect(generatedPreviewTypes).toContain("base_language: string;");
    expect(generatedPreviewTypes).not.toMatch(
      /(?:access_token|client_secret|credentials|provider_body|provider_diagnostics|raw_body|refresh_token|source_bytes|source_file_content)/u,
    );
  });

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
      base_language: "it-IT",
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
      "capability_profile",
      "connected_at",
      "expires_at",
      "revoked_at",
      "scope_label",
      "scope_profile",
      "status",
    ]);
    expect(bitbucketStatus?.properties).not.toHaveProperty("workspace");
  });

  it("exposes the closed Bitbucket capability profile without provider authority", () => {
    const statusSchema =
      openApi.components.schemas.AdminBitbucketStatusResponse;
    const capabilitySchema =
      openApi.components.schemas.AdminBitbucketCapabilityProfile;

    expect(statusSchema?.additionalProperties).toBe(false);
    expect(statusSchema?.properties?.scope_profile).toMatchObject({
      const: "repository_and_pull_request",
    });
    expect(statusSchema?.properties?.scope_label).toMatchObject({
      const: "Repository and pull-request access",
    });
    expect(statusSchema?.properties?.capability_profile).toEqual({
      $ref: "#/components/schemas/AdminBitbucketCapabilityProfile",
    });

    expect(capabilitySchema?.additionalProperties).toBe(false);
    expect(Object.keys(capabilitySchema?.properties ?? {}).sort()).toEqual([
      "evaluated_at",
      "pull_request",
      "source_read",
      "source_write",
    ]);
    expect(capabilitySchema?.required?.sort()).toEqual([
      "evaluated_at",
      "pull_request",
      "source_read",
      "source_write",
    ]);

    const readiness = [
      "disconnected",
      "ready",
      "ready_for_later_phase",
      "reauthorization_required",
      "unavailable",
    ];
    for (const field of ["source_read", "source_write", "pull_request"]) {
      expect(
        (capabilitySchema?.properties?.[field] as OpenApiSchema | undefined)
          ?.enum,
      ).toEqual(readiness);
    }

    const generatedCapabilityTypes = generatedTypeAliases(
      generatedTypesSource,
      [
        "AdminBitbucketCapabilityProfile",
        "AdminBitbucketStatusResponse",
        "AdminBitbucketErrorResponse",
      ],
    );
    expect(generatedCapabilityTypes).toContain(
      "export type AdminBitbucketCapabilityProfile",
    );
    expect(generatedCapabilityTypes).toContain(
      "source_read: 'disconnected' | 'ready' | 'ready_for_later_phase' | 'reauthorization_required' | 'unavailable'",
    );
    expect(generatedCapabilityTypes).not.toMatch(
      /(?:raw_authority|effective_authority|generation|token|provider_body|workspace|scope:)/u,
    );
  });

  it("calls only the generated VerboFlex capability endpoints with bearer authority", async () => {
    const responseBody = {
      status: "Connected",
      scope_profile: "repository_and_pull_request",
      scope_label: "Repository and pull-request access",
      capability_profile: {
        source_read: "ready",
        source_write: "ready_for_later_phase",
        pull_request: "ready_for_later_phase",
        evaluated_at: "2026-09-02T21:00:00Z",
      },
      connected_at: "2026-09-02T21:00:00Z",
      expires_at: "2026-09-02T22:00:00Z",
      revoked_at: null,
    };
    const { apiClient, requests } = createRecordingApiClient(responseBody);
    const authority = "phase-three-memory-bearer";

    await getAdminBitbucketStatus({ client: apiClient, auth: authority });
    await connectAdminBitbucketOauth({ client: apiClient, auth: authority });
    await reconnectAdminBitbucketOauth({ client: apiClient, auth: authority });

    expect(
      requests.map((request) => [
        request.method,
        new URL(request.url).pathname,
        request.headers.get("Authorization"),
      ]),
    ).toEqual([
      ["GET", "/api/v1/admin/bitbucket", `Bearer ${authority}`],
      ["POST", "/api/v1/admin/bitbucket/connect", `Bearer ${authority}`],
      ["POST", "/api/v1/admin/bitbucket/reconnect", `Bearer ${authority}`],
    ]);
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

    const bitbucketGeneratedTypes = generatedTypeAliases(generatedTypesSource, [
      "AdminBitbucketCapabilityProfile",
      "AdminBitbucketStatusResponse",
      "AdminBitbucketErrorResponse",
    ]);
    expect(bitbucketGeneratedTypes).not.toMatch(
      /(?:authorization_url|workspace|client_secret|access_token|refresh_token|ciphertext)/u,
    );
  });

  it("freezes every current admin operation ID", () => {
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

    expect(actual).toEqual(phaseThreeAdminOperationIds);
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
