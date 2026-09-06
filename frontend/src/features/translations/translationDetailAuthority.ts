import type { TranslationGroupDetailResponse } from "../../api/client";

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
    data.pending_change !== null ||
    !Array.isArray(data.comments) ||
    data.comments.length !== 0
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
  return data.values.every((value) => {
    if (!value || typeof value.id !== "string" || ids.has(value.id))
      return false;
    ids.add(value.id);
    const c = value.constraint;
    return (
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
    ? "Mixed states"
    : ({ draft: "Draft", approved: "Approved", rejected: "Rejected" }[state] ??
      "State unavailable");
export const lengthStatusLabel = (
  constraint: TranslationGroupDetailResponse["values"][number]["constraint"],
) =>
  constraint.status === "no_max"
    ? "No max length"
    : constraint.status === "within_limit"
      ? "Within limit"
      : `Over limit by ${constraint.overage}`;
export function ruleSourceLabel(detail: TranslationGroupDetailResponse) {
  const source = detail.values[0].constraint.source;
  return source === "none"
    ? "No max length"
    : source === "language_override"
      ? "Language override"
      : detail.language === detail.base_language
        ? "Base-language default"
        : `Inherited from ${detail.base_language ?? "base language"}`;
}
