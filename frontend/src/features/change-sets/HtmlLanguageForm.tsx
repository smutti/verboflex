import { useState } from "react";
import { createHtmlLanguage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { t, useUiLanguage } from "@/i18n";

export function HtmlLanguageForm({
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
          const result = await createHtmlLanguage({
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
        {t("New HTML language")}
        <input
          className="ml-2 min-h-11 rounded border bg-background px-3"
          value={language}
          placeholder="fr-BE"
          required
          maxLength={32}
          pattern="[a-z]{2,3}(-[A-Z]{2})?"
          disabled={busy}
          onChange={(event) => setLanguage(event.target.value)}
        />
      </label>
      <p className="text-sm text-muted-foreground">
        {t(
          "Creates files with the language suffix on the working branch, copying the source text. Translate and review them before opening the PR.",
        )}
      </p>
      <Button type="submit" disabled={busy || !language.trim()}>
        {t("Add language files")}
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
