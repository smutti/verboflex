import { t } from "@/i18n";
import type {
  TranslationGroupDetailResponse,
  TranslationSourceComparisonResponse,
} from "../../api/client";

function validComparison(
  value: TranslationSourceComparisonResponse | null | undefined,
  sourceId: string | null | undefined,
  origin?: string,
) {
  if (value == null) return true;
  return (
    typeof value === "object" &&
    !!sourceId &&
    value.source_value_id === sourceId &&
    ["base_language", "embedded"].includes(value.origin) &&
    (!origin || value.origin === origin) &&
    Number.isSafeInteger(value.previous_revision_number) &&
    value.previous_revision_number > 0 &&
    Number.isSafeInteger(value.current_revision_number) &&
    value.current_revision_number > value.previous_revision_number &&
    typeof value.changed === "boolean" &&
    typeof value.previous_truncated === "boolean" &&
    typeof value.current_truncated === "boolean" &&
    [value.previous_text, value.current_text].every(
      (text) => typeof text === "string" && Array.from(text).length <= 4096,
    ) &&
    [
      value.previous_commit_hash,
      value.current_commit_hash,
      value.previous_execution_id,
      value.current_execution_id,
    ].every((id) => typeof id === "string" && id.length > 0 && id.length <= 128)
  );
}

/** Validate mandatory projection coherence without calculating Unicode lengths. */
export function completeTranslationDetail(
  data: TranslationGroupDetailResponse,
  id: string,
): boolean {
  if (
    !data ||
    data.id !== id ||
    typeof data.raw_key !== "string" ||
    !data.raw_key ||
    typeof data.language !== "string" ||
    !Array.isArray(data.values) ||
    !data.values.length ||
    data.values.length > 10000 ||
    !Number.isInteger(data.comment_count) ||
    data.comment_count < 0 ||
    typeof data.mutation_eligible !== "boolean" ||
    typeof data.review_eligible !== "boolean"
  )
    return false;
  if (
    !Array.isArray(data.states) ||
    !data.states.length ||
    !["draft", "approved", "rejected", "mixed"].includes(data.state_summary)
  )
    return false;
  if ((data.explicit_maximum === null) !== (data.constraint_version === null))
    return false;
  if (
    data.explicit_maximum !== null &&
    (!Number.isInteger(data.explicit_maximum) ||
      data.explicit_maximum < 0 ||
      data.explicit_maximum > 1048576 ||
      !Number.isInteger(data.constraint_version) ||
      data.constraint_version! < 1)
  )
    return false;
  const ids = new Set<string>();
  if (data.source_context != null) {
    const sourceIds = new Set<string>();
    if (
      !Array.isArray(data.source_context) ||
      data.source_context.length > 10000 ||
      !data.source_context.every((source) => {
        if (
          !source ||
          typeof source.source_value_id !== "string" ||
          !source.source_value_id ||
          sourceIds.has(source.source_value_id)
        )
          return false;
        sourceIds.add(source.source_value_id);
        return (
          ["embedded", "base_language"].includes(source.origin) &&
          (source.source_text === null ||
            typeof source.source_text === "string") &&
          (source.language === null || typeof source.language === "string") &&
          validComparison(
            source.source_comparison,
            source.source_value_id,
            source.origin,
          )
        );
      })
    )
      return false;
  }
  return data.values.every((value) => {
    if (!value || typeof value.id !== "string" || ids.has(value.id))
      return false;
    ids.add(value.id);
    const c = value.constraint;
    return (
      validComparison(value.source_comparison, value.source_value_id) &&
      [
        "scalar",
        "android_quantity",
        "android_array_item",
        "qt_numerus",
        "qt_length_variant",
        "json_path",
      ].includes(value.selector_kind) &&
      (value.selector_fields === null ||
        Array.isArray(value.selector_fields)) &&
      (value.source_text === null || typeof value.source_text === "string") &&
      (value.translated_text === null ||
        typeof value.translated_text === "string") &&
      typeof value.display_text === "string" &&
      Array.isArray(value.structure) &&
      ["draft", "approved", "rejected"].includes(value.review_state) &&
      data.states.includes(value.review_state) &&
      Number.isInteger(value.grapheme_count) &&
      value.grapheme_count >= 0 &&
      !!c &&
      c.actual === value.grapheme_count &&
      (c.maximum === null
        ? c.source === "none" && c.status === "no_max" && c.overage === null
        : Number.isInteger(c.maximum) &&
          c.maximum >= 0 &&
          c.maximum <= 1048576 &&
          ["base_default", "language_override"].includes(c.source) &&
          (c.status === "within_limit"
            ? c.actual <= c.maximum && c.overage === 0
            : c.status === "over_limit" &&
              c.actual > c.maximum &&
              c.overage === c.actual - c.maximum))
    );
  });
}

export const reviewStateLabel = (state: string) =>
  state === "mixed"
    ? t("Mixed states")
    : ({ draft: t("Draft"), approved: t("Approved"), rejected: t("Rejected") }[
        state
      ] ?? t("State unavailable"));
export const lengthStatusLabel = (
  constraint: TranslationGroupDetailResponse["values"][number]["constraint"],
) =>
  constraint.status === "no_max"
    ? t("No max length")
    : constraint.status === "within_limit"
      ? t("Within limit")
      : t("Over limit by {{v0}}", { v0: constraint.overage });
export function ruleSourceLabel(detail: TranslationGroupDetailResponse) {
  const source = detail.values[0].constraint.source;
  return source === "none"
    ? t("No max length")
    : source === "language_override"
      ? t("Language override")
      : detail.language === detail.base_language
        ? t("Base-language default")
        : t("Inherited from {{v0}}", {
            v0: detail.base_language ?? t("base language"),
          });
}
