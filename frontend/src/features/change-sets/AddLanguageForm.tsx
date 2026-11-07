import { useState } from "react";
import { createProjectLanguage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { t, useUiLanguage } from "@/i18n";

export function AddLanguageForm({
  accessToken,
  productId,
  workflowId,
  onCreated,
}: {
  accessToken: string;
  productId: string;
  workflowId: string;
  onCreated: () => void;
}) {
  useUiLanguage();
  const [language, setLanguage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [created, setCreated] = useState(false);
  return (
    <form
      className="space-y-2 rounded border p-3"
      onSubmit={async (event) => {
        event.preventDefault();
        if (busy) return;
        setBusy(true);
        setError(false);
        setCreated(false);
        try {
          const result = await createProjectLanguage({
            auth: accessToken,
            path: { product_id: productId },
            body: { workflow_id: workflowId, language: language.trim() },
          });
          if (!result.data) throw new Error("unavailable");
          setCreated(true);
          setLanguage("");
          onCreated();
        } catch {
          setError(true);
        } finally {
          setBusy(false);
        }
      }}
    >
      <label className="block text-sm font-medium">
        {t("New language")}
        <input
          className="mt-2 block min-h-11 w-full max-w-sm rounded border bg-background px-3"
          value={language}
          placeholder="fr-BE"
          required
          maxLength={64}
          pattern="[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?"
          disabled={busy}
          onChange={(event) => setLanguage(event.target.value)}
        />
      </label>
      <p className="text-sm text-muted-foreground">
        {t(
          "Copies the source catalog to the new language on the working branch, preserving keys, structure and placeholders. Translate and review the copied text before opening the PR.",
        )}
      </p>
      <p className="text-sm text-muted-foreground">
        {t(
          "After refreshing the source, the new language can use the project's configured screenshot scenarios.",
        )}
      </p>
      <Button type="submit" disabled={busy || !language.trim()}>
        {t("Add language")}
      </Button>
      {created && (
        <p role="status">
          {t(
            "Language creation queued. When the commit completes, refresh the source to import the new files.",
          )}
        </p>
      )}
      {error && (
        <p role="alert">
          {t(
            "Could not add this language. Check that it is new, refresh the source and finish pending branch operations.",
          )}
        </p>
      )}
    </form>
  );
}
