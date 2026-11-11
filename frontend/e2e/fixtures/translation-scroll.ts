import type {
  TranslationGroupSummaryResponse,
  TranslationKeySummary,
  TranslationKeyPageResponse,
  TranslationGroupDetailResponse,
} from "../../src/api/client";

const options = {
  products: [
    { id: "alpha", name: "Alpha" },
    { id: "beta", name: "Beta" },
  ],
  languages: [
    { code: "en", label: "English" },
    { code: "it", label: "Italian" },
  ],
};
export function group(
  id: string,
  changes: Partial<TranslationGroupSummaryResponse> = {},
): TranslationGroupSummaryResponse {
  return {
    id,
    product_id: "alpha",
    product_name: "Alpha",
    raw_key: id,
    language: "it",
    language_label: "Italian",
    source_language: "en",
    source_text: "Source",
    translated_text: "Translated",
    selector_kinds: ["scalar"],
    provenance: null,
    value_count: 1,
    no_max_count: 1,
    over_limit_count: 0,
    within_limit_count: 0,
    has_no_max: true,
    has_over_limit: false,
    is_deleted: false,
    rank: 3,
    states: ["draft"],
    state_summary: "draft",
    comment_count: 0,
    pending_change: null,
    ...changes,
  };
}
export function keyPage(data: {
  items: TranslationGroupSummaryResponse[] | TranslationKeySummary[];
  next_cursor?: string | null;
}): TranslationKeyPageResponse {
  const items = data.items.map((item) =>
    "slots" in item
      ? item
      : {
          translation_key_id: item.id,
          scope_id: "scope",
          product_id: item.product_id,
          product_name: item.product_name,
          raw_key: item.raw_key,
          base_language: item.source_language ?? "en",
          rank: item.rank,
          key_truncated: false,
          source_text: item.source_text,
          source_truncated: false,
          slots: [
            {
              language: item.language,
              language_label: item.language_label,
              group_id: item.id,
              kind: "imported" as const,
              editable: !item.is_deleted,
              edit_field: "translated_text" as const,
              effective_text: item.translated_text,
              is_deleted: item.is_deleted,
              matches_filters: true,
              no_max_count: item.no_max_count,
              over_limit_count: item.over_limit_count,
              within_limit_count: item.within_limit_count,
              pending_change: item.pending_change ?? null,
              preview_kind: "scalar" as const,
              provenance: null,
              read_only_reason: null,
              selector_kinds: item.selector_kinds,
              source_changed: false,
              states: item.states,
              text_truncated: false,
              value_count: item.value_count,
              comment_count: item.comment_count,
            },
          ],
        },
  );
  return {
    items,
    next_cursor: data.next_cursor ?? null,
    visible_languages: items[0]?.slots.map((slot) => slot.language) ?? ["it"],
    available_languages: options.languages,
    available_languages_truncated: false,
    default_selection_capped: false,
  };
}
export function editable(id: string): TranslationGroupDetailResponse {
  return {
    id,
    product_id: "alpha",
    product_name: "Alpha",
    raw_key: id,
    language: "it",
    language_label: "Italian",
    base_language: "en",
    base_maximum: null,
    explicit_maximum: null,
    constraint_version: null,
    is_deleted: false,
    mutation_eligible: true,
    review_eligible: true,
    comment_count: 0,
    states: ["draft"],
    state_summary: "draft",
    pending_change: null,
    values: [
      {
        id,
        source_text: "Source",
        translated_text: "Old",
        display_text: "Old",
        structure: [],
        selector_kind: "scalar",
        selector_version: 1,
        selector_digest: "a".repeat(64),
        selector_fields: null,
        is_deleted: false,
        deleted_at: null,
        review_state: "draft",
        grapheme_count: 3,
        constraint: {
          actual: 3,
          maximum: null,
          source: "none",
          status: "no_max",
          overage: null,
        },
        provenance: {
          repository_id: "repo",
          repository_name: "Repo",
          repository_side: "translations",
          branch: "main",
          path: "it.json",
          format: "json",
          commit_hash: "a".repeat(40),
          execution_id: "execution",
          line: null,
          column: null,
        },
        history_has_more: false,
        history: [
          {
            revision_number: 1,
            revision_digest: "b".repeat(64),
            review_state: "draft",
            is_deleted: false,
            created_at: "2026-10-01T00:00:00Z",
            commit_hash: "a".repeat(40),
            execution_id: "execution",
          },
        ],
      },
    ],
  };
}
