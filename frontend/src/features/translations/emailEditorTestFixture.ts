import type {
  HtmlEditorDocument,
  HtmlTemplateOption,
  TranslationGroupDetailResponse,
  TranslationProposalResponse,
} from "@/api/client";

export const emailTemplates: HtmlTemplateOption[] = ["en", "it", "fr"].map(
  (language) => ({
    group_id: `${language}-body`,
    scope_id: "scope",
    name: "welcome",
    language,
    base_language: "en",
    path: `mail/Welcome-${language.toUpperCase()}.html`,
  }),
);

export function emailDocument(language = "it"): HtmlEditorDocument {
  const texts =
    language === "it"
      ? ["Ciao {{name}}", "Apri account"]
      : ["Hello {{name}}", "Open account"];
  return {
    product_id: "product",
    language,
    path: `mail/Welcome-${language.toUpperCase()}.html`,
    execution_id: "execution",
    missing_images: 0,
    document: "<html><body><p><!--BODY--></p><a><!--CTA--></a></body></html>",
    fragments: [
      {
        group_id: `${language}-body`,
        marker: "<!--BODY-->",
        position: 0,
        element: "p",
        text: texts[0],
      },
      {
        group_id: `${language}-cta`,
        marker: "<!--CTA-->",
        position: 1,
        element: "a",
        text: texts[1],
      },
    ],
  };
}

export function emailDetail(id = "it-body"): TranslationGroupDetailResponse {
  const language = id.split("-")[0];
  const part = id.endsWith("body") ? 0 : 1;
  const text = emailDocument(language).fragments[part].text;
  return {
    id,
    product_id: "product",
    product_name: "Synthetic emails",
    raw_key: `welcome::/html/body/${part}`,
    language,
    language_label: language,
    base_language: "en",
    base_maximum: null,
    explicit_maximum: null,
    constraint_version: null,
    states: ["draft"],
    state_summary: "draft",
    is_deleted: false,
    pending_change: null,
    comment_count: 0,
    mutation_eligible: true,
    review_eligible: true,
    values: [
      {
        id,
        selector_version: 1,
        selector_kind: "scalar",
        selector_fields: [],
        selector_digest: "a".repeat(64),
        source_text: emailDocument("en").fragments[part].text,
        translated_text: language === "en" ? null : text,
        display_text: text,
        structure: [],
        grapheme_count: text.length,
        constraint: {
          actual: text.length,
          maximum: null,
          source: "none",
          status: "no_max",
          overage: null,
        },
        review_state: "draft",
        is_deleted: false,
        deleted_at: null,
        history_has_more: false,
        provenance: {
          format: "html",
          repository_side: "direct",
          repository_id: "repo",
          repository_name: "Emails",
          branch: "working",
          path: `mail/Welcome-${language.toUpperCase()}.html`,
          execution_id: "execution",
          commit_hash: "b".repeat(40),
          line: null,
          column: null,
        },
        history: [
          {
            revision_number: 1,
            revision_digest: "c".repeat(64),
            review_state: "draft",
            is_deleted: false,
            created_at: "2026-10-22T00:00:00Z",
            commit_hash: "b".repeat(40),
            execution_id: "execution",
          },
        ],
      },
    ],
  };
}

export function emailProjection(
  id: string,
  text: string,
  version = 1,
): TranslationProposalResponse {
  const detail = emailDetail(id),
    value = detail.values[0];
  return {
    translation_group_id: id,
    language: detail.language,
    version,
    state: "draft",
    reconciliation_required: false,
    updated_at: "2026-10-22T01:00:00Z",
    updated_by: "editor",
    activity: null,
    published: [
      {
        translation_value_id: id,
        selector_version: 1,
        selector_digest: value.selector_digest,
        text: value.translated_text ?? value.source_text,
        review_state: "draft",
        revision_number: 1,
        revision_digest: "c".repeat(64),
      },
    ],
    pending: [
      {
        translation_value_id: id,
        selector_version: 1,
        selector_digest: value.selector_digest,
        text,
        basis_revision_number: 1,
        basis_digest: "c".repeat(64),
        grapheme_count: text.length,
        maximum: null,
        is_over_limit: false,
        approval_eligible: true,
        submission_eligible: true,
      },
    ],
  };
}
