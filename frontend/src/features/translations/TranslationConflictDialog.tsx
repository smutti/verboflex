import { t, useUiLanguage } from "@/i18n";
import type { TranslationProposalResponse } from "../../api/client";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import {
  countTranslationGraphemes,
  type ActiveTranslationDraft,
} from "./TranslationEditor";

function selectorLabel(
  value: ActiveTranslationDraft["values"][number],
  index: number,
) {
  const fields = value.selectorFields ?? [];
  const label = fields
    .map((field) =>
      Array.isArray(field.value)
        ? `${field.name} ${field.value.join(" / ")}`
        : `${field.name} ${String(field.value)}`,
    )
    .join(", ");
  return label || t("Translation {{v0}}", { v0: index + 1 });
}

// eslint-disable-next-line react-refresh/only-export-components
export function reconcileTranslationDraft(
  draft: ActiveTranslationDraft,
  latest: TranslationProposalResponse,
): ActiveTranslationDraft {
  const latestPending = new Map(
    latest.pending.map((value) => [value.translation_value_id, value]),
  );
  const latestPublished = new Map(
    latest.published.map((value) => [value.translation_value_id, value]),
  );
  return {
    ...draft,
    expectedVersion: latest.version,
    reconciliationRequired: true,
    dirty: true,
    values: draft.values.map((value) => {
      const server = latestPending.get(value.translationValueId);
      const published = latestPublished.get(value.translationValueId);
      return server && published
        ? {
            ...value,
            // A saved proposal can still refer to the pre-import revision.
            // Reconcile against the current repository value explicitly.
            basisRevisionNumber: published.revision_number,
            basisDigest: published.revision_digest,
            publishedText: published.text ?? "",
            actual: countTranslationGraphemes(value.text),
            maximum: server.maximum,
            overage:
              server.maximum === null
                ? 0
                : Math.max(
                    0,
                    countTranslationGraphemes(value.text) - server.maximum,
                  ),
          }
        : value;
    }),
  };
}

export function TranslationConflictDialog({
  open,
  draft,
  latest,
  onKeepEditing,
  onReconcile,
}: {
  open: boolean;
  draft: ActiveTranslationDraft;
  latest: TranslationProposalResponse;
  onKeepEditing: () => void;
  onReconcile: (draft: ActiveTranslationDraft) => void;
}) {
  useUiLanguage();
  const serverById = new Map(
    latest.pending.map((value) => [value.translation_value_id, value]),
  );
  const publishedById = new Map(
    latest.published.map((value) => [value.translation_value_id, value]),
  );
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onKeepEditing()}>
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>
            {latest.reconciliation_required
              ? t("Translation source changed")
              : t("Translation changed in another session")}
          </DialogTitle>
          <DialogDescription>
            {latest.reconciliation_required
              ? t("Review the repository changes before saving your draft.")
              : t("Compare your changes with the latest saved version.")}
          </DialogDescription>
        </DialogHeader>
        <div className="grid max-h-[60vh] gap-(--space-lg) overflow-y-auto md:grid-cols-2">
          <section
            aria-label={t("Your unsaved version")}
            className="space-y-(--space-md)"
          >
            <h3 className="text-heading font-semibold">
              {t("Your unsaved version")}
            </h3>
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
                  {value.text || t("Empty pending translation")}
                </p>
              </div>
            ))}
          </section>
          <section
            aria-label={t("Latest saved version")}
            className="space-y-(--space-md)"
          >
            <h3 className="text-heading font-semibold">
              {t("Latest saved version")}
            </h3>
            {draft.values.map((value, index) => {
              const server = serverById.get(value.translationValueId);
              return (
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
                    {server?.text || t("Empty pending translation")}
                  </p>
                </div>
              );
            })}
          </section>
          {latest.reconciliation_required && (
            <section
              aria-label={t("Current repository version")}
              className="space-y-(--space-md) md:col-span-2"
            >
              <h3 className="text-heading font-semibold">
                {t("Current repository version")}
              </h3>
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
                    {publishedById.get(value.translationValueId)?.text ||
                      t("Empty translation")}
                  </p>
                </div>
              ))}
            </section>
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onKeepEditing}>
            {t("Keep editing")}
          </Button>
          <Button
            type="button"
            onClick={() =>
              onReconcile(reconcileTranslationDraft(draft, latest))
            }
          >
            {t("Reconcile with latest")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
