import { TranslationSuggestions } from "./TranslationSuggestions";
import type { ReuseQuery } from "../../api/client";
import { useEffect, useRef, useState } from "react";
import { TriangleAlert } from "lucide-react";
import { cn } from "../../lib/utils";
import { toast } from "sonner";

import {
  saveTranslationProposal,
  type TranslationGroupDetailResponse,
  type TranslationProposalConflictResponse,
  type TranslationProposalResponse,
  type TranslationSelectorFieldResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";

export interface ActiveTranslationDraftValue {
  translationValueId: string;
  selectorVersion: 1;
  selectorDigest: string;
  selectorFields: TranslationSelectorFieldResponse[] | null;
  selectorKind: string;
  publishedText: string;
  text: string;
  initialText: string;
  basisRevisionNumber: number;
  basisDigest: string;
  actual: number;
  maximum: number | null;
  overage: number;
}

export interface ActiveTranslationDraft {
  principalId: string;
  productId: string;
  translationGroupId: string;
  language: string;
  expectedVersion: number;
  reconciliationRequired: boolean;
  dirty: boolean;
  detail: TranslationGroupDetailResponse;
  values: ActiveTranslationDraftValue[];
}

// eslint-disable-next-line react-refresh/only-export-components
export function countTranslationGraphemes(text: string) {
  return Array.from(
    new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text),
  ).length;
}

// eslint-disable-next-line react-refresh/only-export-components
export function writableTranslationDetail(
  detail: TranslationGroupDetailResponse,
  editField: "source_text" | "translated_text" | null,
): boolean {
  if (!editField || detail.is_deleted || !detail.mutation_eligible)
    return false;
  return detail.values.every((value) => {
    const provenance = value.provenance;
    if (
      value.is_deleted ||
      !provenance ||
      provenance.repository_side === "keys" ||
      !value.history[0] ||
      !provenance.execution_id ||
      !provenance.commit_hash
    )
      return false;
    const kinds: Record<string, string[]> = {
      android_xml: ["scalar", "android_quantity", "android_array_item"],
      json: ["scalar", "json_path"],
      ios_strings: ["scalar"],
      qt_ts: ["scalar", "qt_numerus", "qt_length_variant"],
    };
    if (!kinds[provenance.format]?.includes(value.selector_kind)) return false;
    if (
      provenance.format === "android_xml" &&
      (value.structure.some(
        (node) =>
          typeof node === "object" &&
          node !== null &&
          "kind" in node &&
          node.kind === "android_xml:inline",
      ) ||
        value.structure.filter((node) =>
          [
            "android_xml:text",
            "android_xml:tail",
            "android_xml:cdata",
          ].includes(
            typeof node === "object" &&
              node !== null &&
              "kind" in node &&
              typeof node.kind === "string"
              ? node.kind
              : "",
          ),
        ).length > 1)
    )
      return false;
    return editField === "source_text"
      ? ["direct", "translations"].includes(provenance.repository_side) &&
          provenance.format !== "qt_ts" &&
          value.translated_text === null &&
          value.source_text !== null
      : value.translated_text !== null;
  });
}

// eslint-disable-next-line react-refresh/only-export-components
export function createActiveTranslationDraft(
  detail: TranslationGroupDetailResponse,
  principalId: string,
): ActiveTranslationDraft {
  const pendingByValue = new Map(
    (detail.pending_change?.values ?? []).map((value) => [
      value.translation_value_id,
      value,
    ]),
  );
  return {
    principalId,
    productId: detail.product_id,
    translationGroupId: detail.id,
    language: detail.language,
    expectedVersion: detail.pending_change?.version ?? 0,
    reconciliationRequired:
      detail.pending_change?.reconciliation_required ?? false,
    dirty: false,
    detail,
    values: detail.values.map((value) => {
      const pending = pendingByValue.get(value.id);
      const basis = value.history[0];
      if (!pending && !basis) {
        throw new Error("Translation edit basis unavailable");
      }
      const sourceLeaf =
        value.provenance !== null &&
        ["direct", "translations"].includes(value.provenance.repository_side) &&
        ["android_xml", "json", "ios_strings"].includes(
          value.provenance.format,
        ) &&
        value.translated_text === null;
      const imported = sourceLeaf
        ? (value.source_text ?? value.display_text)
        : (value.translated_text ?? "");
      const text = pending?.text ?? imported;
      return {
        translationValueId: value.id,
        selectorVersion: value.selector_version,
        selectorDigest: value.selector_digest,
        selectorFields: value.selector_fields,
        selectorKind: value.selector_kind,
        publishedText: imported,
        text,
        initialText: text,
        basisRevisionNumber:
          pending?.basis_revision_number ?? basis.revision_number,
        basisDigest: pending?.basis_digest ?? basis.revision_digest,
        actual: pending?.grapheme_count ?? value.constraint.actual,
        maximum: pending ? pending.maximum : value.constraint.maximum,
        overage: pending
          ? pending.is_over_limit
            ? Math.max(
                1,
                (pending.grapheme_count ?? value.constraint.actual) -
                  (pending.maximum ?? 0),
              )
            : 0
          : (value.constraint.overage ?? 0),
      };
    }),
  };
}

function selectorLabel(value: ActiveTranslationDraftValue, index: number) {
  const fields = value.selectorFields ?? [];
  const parts = fields.map((field) =>
    Array.isArray(field.value)
      ? `${field.name} ${field.value.join(" / ")}`
      : `${field.name} ${String(field.value)}`,
  );
  return parts.length > 0
    ? parts.join(", ")
    : index === 0
      ? "Proposed translation"
      : `Proposed translation ${index + 1}`;
}

function isCompleteFreshProjection(
  fresh: TranslationProposalResponse,
  draft: ActiveTranslationDraft,
) {
  if (
    fresh.translation_group_id !== draft.translationGroupId ||
    fresh.language !== draft.language ||
    fresh.state !== "draft" ||
    fresh.pending.length !== draft.values.length ||
    fresh.published.length !== draft.values.length ||
    !Number.isSafeInteger(fresh.version)
  )
    return false;
  const expected = new Map(
    draft.values.map((value) => [value.translationValueId, value]),
  );
  const seenPending = new Set<string>();
  const seenPublished = new Set<string>();
  for (const value of fresh.pending) {
    const local = expected.get(value.translation_value_id);
    if (
      !local ||
      seenPending.has(value.translation_value_id) ||
      value.selector_version !== local.selectorVersion ||
      value.selector_digest !== local.selectorDigest
    )
      return false;
    seenPending.add(value.translation_value_id);
  }
  for (const value of fresh.published) {
    const local = expected.get(value.translation_value_id);
    if (
      !local ||
      seenPublished.has(value.translation_value_id) ||
      value.selector_version !== local.selectorVersion ||
      value.selector_digest !== local.selectorDigest
    )
      return false;
    seenPublished.add(value.translation_value_id);
  }
  return true;
}

export interface TranslationEditorProps {
  accessToken: string;
  draft: ActiveTranslationDraft;
  onDraftChange: (draft: ActiveTranslationDraft) => void;
  onSaved: (projection: TranslationProposalResponse) => void;
  onStop: () => void;
  onConflict?: (
    conflict: TranslationProposalConflictResponse,
    draft: ActiveTranslationDraft,
  ) => void;
  returnFocusTo?: HTMLElement | null;
  detail?: boolean;
  bilingual?: boolean;
  compact?: boolean;
  continuing?: boolean;
}

export function TranslationEditor({
  accessToken,
  draft,
  onDraftChange,
  onSaved,
  onStop,
  onConflict,
  returnFocusTo,
  detail = false,
  bilingual = false,
  compact = false,
  continuing = false,
}: TranslationEditorProps) {
  const [saving, setSaving] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [failure, setFailure] = useState<"general" | "conflict" | null>(null);
  const active = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const mounted = useRef(true);
  const firstField = useRef<HTMLTextAreaElement>(null);
  const alert = useRef<HTMLDivElement>(null);

  useEffect(() => {
    mounted.current = true;
    firstField.current?.focus();
    return () => {
      mounted.current = false;
      active.current?.abort();
    };
  }, [accessToken, draft.principalId, draft.translationGroupId]);
  useEffect(() => {
    if (failure) alert.current?.focus();
  }, [failure]);

  function changeValue(index: number, text: string) {
    const values = draft.values.map((value, current) =>
      current === index
        ? {
            ...value,
            text,
            actual: countTranslationGraphemes(text),
            overage:
              value.maximum === null
                ? 0
                : Math.max(0, countTranslationGraphemes(text) - value.maximum),
          }
        : value,
    );
    onDraftChange({
      ...draft,
      values,
      dirty: values.some((value) => value.text !== value.initialText),
    });
    setFailure(null);
  }

  async function save() {
    if (
      active.current ||
      continuing ||
      !draft.detail.mutation_eligible ||
      draft.detail.is_deleted
    )
      return;
    const controller = new AbortController();
    const requestGeneration = ++generation.current;
    active.current = controller;
    setSaving(true);
    setFailure(null);
    try {
      const result = await saveTranslationProposal({
        auth: accessToken,
        path: { translation_group_id: draft.translationGroupId },
        body: {
          expected_version: draft.expectedVersion,
          values: draft.values.map((value) => ({
            translation_value_id: value.translationValueId,
            selector_version: value.selectorVersion,
            selector_digest: value.selectorDigest,
            basis_revision_number: value.basisRevisionNumber,
            basis_digest: value.basisDigest,
            proposed_text: value.text,
          })),
        },
        signal: controller.signal,
      });
      if (
        !mounted.current ||
        controller.signal.aborted ||
        generation.current !== requestGeneration
      )
        return;
      if (result.response?.status === 409 && result.error) {
        setFailure("conflict");
        onConflict?.(
          result.error as TranslationProposalConflictResponse,
          draft,
        );
        return;
      }
      if (!result.data || !isCompleteFreshProjection(result.data, draft))
        throw new Error("Incomplete proposal projection");
      onSaved(result.data);
      toast.success("Translation saved as Draft");
      if (!bilingual && !compact)
        queueMicrotask(() => returnFocusTo?.focus({ preventScroll: true }));
    } catch {
      if (mounted.current && !controller.signal.aborted) setFailure("general");
    } finally {
      if (mounted.current && generation.current === requestGeneration) {
        active.current = null;
        setSaving(false);
      }
    }
  }

  const focused = draft.detail.values[focusedIndex];
  const format = focused?.provenance?.format;
  const sourceLanguage = draft.detail.base_language;
  const sourceText = focused?.source_text;
  const reuseQuery: ReuseQuery | null =
    focused &&
    sourceLanguage &&
    sourceLanguage !== draft.language &&
    sourceText &&
    sourceText.length <= 4096 &&
    format &&
    ["android_xml", "qt_ts", "json", "ios_strings"].includes(format) &&
    focused.selector_kind !== "qt_length_variant" &&
    focused.source_resolution !== "ambiguous" &&
    focused.source_resolution !== "unmatched"
      ? {
          source_text: sourceText,
          source_language: sourceLanguage,
          target_language: draft.language,
          format: format as ReuseQuery["format"],
          selector_kind: focused.selector_kind,
          selector_form:
            focused.selector_fields
              ?.find((f) => f.name === "quantity" || f.name === "form_index")
              ?.value?.toString() ?? null,
          exclude_value_id: focused.id,
          fuzzy: true,
        }
      : null;
  return (
    <form
      className="min-w-0 space-y-(--space-md)"
      aria-busy={saving}
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      {!bilingual && !compact && (
        <section
          aria-label="Published translation"
          className="space-y-(--space-sm)"
        >
          <h3 className="text-heading font-semibold">Published translation</h3>
          {draft.values.map((value, index) => (
            <div
              key={value.translationValueId}
              className="space-y-(--space-xs)"
            >
              <p className="text-label font-semibold">
                {selectorLabel(value, index)}
              </p>
              <p
                className="whitespace-pre-wrap wrap-anywhere"
                lang={draft.language}
                dir="auto"
              >
                {value.publishedText || "Empty translation"}
              </p>
            </div>
          ))}
        </section>
      )}
      {bilingual &&
        !compact &&
        draft.detail.source_context &&
        draft.detail.values.some(
          (value) =>
            value.source_resolution === "unmatched" ||
            value.source_resolution === "ambiguous",
        ) && (
          <section
            aria-label={`Source variants (${draft.detail.base_language ?? "unknown"})`}
            className="space-y-2 rounded-md bg-secondary p-3"
          >
            <h3 className="text-label font-semibold">
              Source variants ({draft.detail.base_language ?? "unknown"})
            </h3>
            <p className="text-label text-muted-foreground">
              Source and target variants do not have a unique one-to-one match.
            </p>
            {draft.detail.source_context.map((source) => (
              <div key={source.source_value_id}>
                <p className="text-label font-semibold">
                  {source.selector_fields
                    ?.map((field) => `${field.name}: ${String(field.value)}`)
                    .join(", ") || source.selector_kind}
                </p>
                <p
                  lang={source.language ?? undefined}
                  dir="auto"
                  className="whitespace-pre-wrap wrap-anywhere"
                >
                  {source.source_text ?? "Source text unavailable"}
                </p>
              </div>
            ))}
          </section>
        )}
      <div
        className={
          reuseQuery
            ? "grid min-w-0 gap-4 2xl:grid-cols-[minmax(0,1fr)_19rem]"
            : ""
        }
      >
        <section aria-label="Pending proposal" className="space-y-(--space-md)">
          {!compact && (
            <h3 className="text-heading font-semibold">
              {bilingual
                ? `Translation · ${draft.language}`
                : "Pending proposal"}
            </h3>
          )}
          {draft.reconciliationRequired && (
            <p className="text-label font-semibold text-warning">
              Needs reconciliation
            </p>
          )}
          {draft.values.map((value, index) => {
            const id = `translation-proposal-${draft.translationGroupId}-${index}`;
            const label = selectorLabel(value, index);
            const member = draft.detail.values.find(
              (entry) => entry.id === value.translationValueId,
            );
            const source = draft.detail.source_context?.find(
              (entry) => entry.source_value_id === member?.source_value_id,
            );
            return (
              <div
                key={value.translationValueId}
                className={
                  bilingual && !compact
                    ? "grid min-w-0 gap-4 md:grid-cols-2"
                    : "space-y-(--space-sm)"
                }
              >
                {bilingual && !compact && (
                  <div className="min-w-0 space-y-2 rounded-md bg-secondary p-3">
                    <p className="text-label font-semibold">
                      Source ·{" "}
                      {source?.language ??
                        draft.detail.base_language ??
                        "Unknown"}
                    </p>
                    <p
                      dir="auto"
                      lang={
                        source?.language ??
                        draft.detail.base_language ??
                        undefined
                      }
                      className="whitespace-pre-wrap wrap-anywhere"
                    >
                      {member?.source_text ??
                        (member?.source_resolution === "ambiguous"
                          ? "Ambiguous source variant"
                          : member?.source_resolution === "unmatched"
                            ? "No matching source variant"
                            : "Source text unavailable")}
                    </p>
                    {source?.provenance && (
                      <p className="text-label text-muted-foreground wrap-anywhere">
                        {source.provenance.path}
                      </p>
                    )}
                  </div>
                )}
                <div className="min-w-0 space-y-2">
                  <Label htmlFor={id}>{label}</Label>
                  <Textarea
                    ref={index === 0 ? firstField : undefined}
                    id={id}
                    value={value.text}
                    onFocus={() => setFocusedIndex(index)}
                    disabled={
                      saving || continuing || !draft.detail.mutation_eligible
                    }
                    lang={draft.language}
                    dir="auto"
                    aria-invalid={value.overage > 0}
                    aria-describedby={`${id}-length`}
                    className={cn(
                      "whitespace-pre-wrap",
                      detail ? "min-h-36" : "min-h-24",
                      value.overage > 0 &&
                        "border-destructive bg-red-50 focus-visible:border-destructive focus-visible:ring-destructive/30 dark:bg-red-950/30",
                    )}
                    onChange={(event) =>
                      changeValue(index, event.currentTarget.value)
                    }
                  />
                  {value.text === "" && <p>Empty pending translation</p>}
                  <p
                    id={`${id}-length`}
                    className={cn(
                      "flex flex-wrap items-center gap-1 text-label",
                      value.overage > 0 && "font-semibold text-destructive",
                    )}
                  >
                    {value.overage > 0 && (
                      <TriangleAlert
                        aria-hidden="true"
                        className="size-4 shrink-0"
                      />
                    )}
                    Actual: {value.actual} · Maximum: {value.maximum ?? "None"}
                    {value.overage > 0
                      ? ` · Over limit by ${value.overage}`
                      : ""}
                  </p>
                  {bilingual && !compact && (
                    <p className="text-label text-muted-foreground whitespace-pre-wrap wrap-anywhere">
                      Imported: {value.publishedText || "Empty translation"}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </section>
        <TranslationSuggestions
          key={`${draft.translationGroupId}:${focusedIndex}`}
          accessToken={accessToken}
          productId={draft.productId}
          query={reuseQuery}
          currentText={draft.values[focusedIndex]?.text ?? ""}
          disabled={saving || continuing || !draft.detail.mutation_eligible}
          onUse={(text) => changeValue(focusedIndex, text)}
        />
      </div>
      {bilingual && !compact && (
        <p className="text-label text-muted-foreground">
          Saved as a draft; publishing requires a pull request.
        </p>
      )}
      {failure && (
        <Alert ref={alert} tabIndex={-1} role="alert">
          <AlertTitle>
            {failure === "conflict"
              ? "Translation changed in another session"
              : "Translation was not saved"}
          </AlertTitle>
          <AlertDescription>
            {failure === "conflict"
              ? "Compare your version with the latest saved version, reconcile the differences, then save again."
              : "Your changes are still in this editor. Review them and save again."}
          </AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap gap-(--space-sm)">
        <Button
          type="button"
          variant="outline"
          className="min-h-[44px] whitespace-normal"
          disabled={saving || continuing}
          onClick={onStop}
        >
          {compact ? "Cancel" : "Stop editing translation"}
        </Button>
        <Button
          type="submit"
          className="min-h-[44px] whitespace-normal"
          disabled={saving || continuing || !draft.detail.mutation_eligible}
          aria-busy={saving}
        >
          {compact ? "Save" : "Save translation"}
        </Button>
      </div>
    </form>
  );
}
