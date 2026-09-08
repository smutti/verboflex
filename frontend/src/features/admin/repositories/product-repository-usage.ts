import {
  listAdminRevisionMappings,
  type AdminMappingListResponse,
  type AdminMappingResponse,
} from "../../../api/client";

const MAPPING_PAGE_SIZE = 50;
const MAX_MAPPING_PAGES = 50;

export function mappedRepositoryIds(mappings: readonly AdminMappingResponse[]) {
  return Array.from(
    new Set(
      mappings.flatMap((mapping) =>
        mapping.translations_repository_id === null
          ? [mapping.primary_repository_id]
          : [mapping.primary_repository_id, mapping.translations_repository_id],
      ),
    ),
  );
}

export async function loadMappedRepositoryIds({
  accessToken,
  productId,
  revisionId,
  signal,
}: {
  accessToken: string;
  productId: string;
  revisionId: string;
  signal: AbortSignal;
}) {
  const mappings: AdminMappingResponse[] = [];
  const mappingIds = new Set<string>();
  const consumedCursors = new Set<string>();
  let cursor: string | null = null;
  let pageCount = 0;

  do {
    if (signal.aborted) {
      throw new DOMException("The operation was aborted", "AbortError");
    }
    if (pageCount >= MAX_MAPPING_PAGES) {
      throw new Error("product mappings exceeded page limit");
    }
    const result: { data?: AdminMappingListResponse } =
      await listAdminRevisionMappings({
        auth: accessToken,
        path: { product_id: productId, revision_id: revisionId },
        query: { cursor, limit: MAPPING_PAGE_SIZE },
        signal,
      });
    if (signal.aborted) {
      throw new DOMException("The operation was aborted", "AbortError");
    }
    if (result.data === undefined) {
      throw new Error("product mappings unavailable");
    }
    for (const mapping of result.data.items) {
      if (!mappingIds.has(mapping.id)) {
        mappingIds.add(mapping.id);
        mappings.push(mapping);
      }
    }
    cursor = result.data.next_cursor;
    if (signal.aborted) {
      throw new DOMException("The operation was aborted", "AbortError");
    }
    pageCount += 1;
    if (cursor !== null) {
      if (consumedCursors.has(cursor)) {
        throw new Error("product mappings repeated cursor");
      }
      consumedCursors.add(cursor);
    }
  } while (cursor !== null);

  return mappedRepositoryIds(mappings);
}
