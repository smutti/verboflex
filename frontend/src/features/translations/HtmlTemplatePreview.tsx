import { useEffect, useState } from "react";
import {
  getHtmlTemplatePreview,
  type HtmlTemplatePreviewResponse,
} from "@/api/client";
import { t, useUiLanguage } from "@/i18n";

const policy = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; base-uri 'none'; form-action 'none'">`;

export function HtmlTemplatePreview({
  accessToken,
  groupId,
  text,
}: {
  accessToken: string;
  groupId: string;
  text: string;
}) {
  useUiLanguage();
  const [loaded, setPreview] = useState<{
    groupId: string;
    data: HtmlTemplatePreviewResponse;
  } | null>(null);
  const preview = loaded?.groupId === groupId ? loaded.data : null;
  useEffect(() => {
    const controller = new AbortController();
    void getHtmlTemplatePreview({
      auth: accessToken,
      path: { translation_group_id: groupId },
      signal: controller.signal,
    })
      .then((result) => {
        if (!controller.signal.aborted && result.data)
          setPreview({ groupId, data: result.data });
      })
      .catch(() => {
        /* The text editor remains available when preview is unavailable. */
      });
    return () => controller.abort();
  }, [accessToken, groupId]);
  const escaped = text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  return (
    <section className="space-y-2">
      <p className="text-sm text-muted-foreground">
        {t(
          "Edit text only. HTML tags, links and template variables are protected.",
        )}
      </p>
      {preview && (
        <details>
          <summary className="cursor-pointer text-sm font-medium">
            {t("HTML template preview")}
          </summary>
          <p className="break-all text-xs text-muted-foreground">
            {preview.path}
          </p>
          <iframe
            title={t("HTML template preview")}
            sandbox=""
            referrerPolicy="no-referrer"
            className="h-96 w-full rounded border bg-white"
            srcDoc={
              policy + preview.document.replace(preview.marker, () => escaped)
            }
          />
          <p className="text-xs text-muted-foreground">
            {t(
              "Preview shows imported content with your current edit. External images are disabled.",
            )}
          </p>
        </details>
      )}
    </section>
  );
}
