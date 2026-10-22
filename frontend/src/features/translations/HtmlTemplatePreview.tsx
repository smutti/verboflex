import { useEffect, useRef, useState } from "react";
import {
  getHtmlTemplatePreview,
  type HtmlTemplatePreviewResponse,
  type TranslationGroupDetailResponse,
  type TranslationProposalResponse,
} from "@/api/client";
import { t, useUiLanguage } from "@/i18n";
import { Button } from "@/components/ui/button";

const policy = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">`;

// HTML groups contain one text fragment. A current edit wins over the latest
// saved proposal, which wins over the imported text (including an empty edit).
export function HtmlTranslationPreview({
  detail,
  accessToken,
  draftText,
  proposal,
}: {
  detail: TranslationGroupDetailResponse;
  accessToken: string;
  draftText?: string;
  proposal?: TranslationProposalResponse | null;
}) {
  const value = detail.values[0];
  const pending =
    proposal && proposal.version >= (detail.pending_change?.version ?? 0)
      ? proposal.pending
      : detail.pending_change?.values;
  return (
    <HtmlTemplatePreview
      key={JSON.stringify([
        detail.id,
        accessToken,
        value?.provenance?.execution_id,
        value?.provenance?.commit_hash,
      ])}
      accessToken={accessToken}
      groupId={detail.id}
      text={
        draftText ??
        pending?.find((item) => item.translation_value_id === value?.id)
          ?.text ??
        value?.translated_text ??
        value?.source_text ??
        value?.display_text ??
        ""
      }
    />
  );
}

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
  const [attempt, setAttempt] = useState(0);
  const identity = JSON.stringify([accessToken, groupId, attempt]);
  const [loaded, setLoaded] = useState<{
    identity: string;
    data?: HtmlTemplatePreviewResponse;
    failed?: boolean;
  } | null>(null);
  const preview = loaded?.identity === identity ? loaded.data : undefined;
  const failed = loaded?.identity === identity && loaded.failed;
  const viewport = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) =>
      setWidth(entry.contentRect.width),
    );
    if (viewport.current) observer.observe(viewport.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void getHtmlTemplatePreview({
      auth: accessToken,
      path: { translation_group_id: groupId },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (
          !result.data ||
          !result.data.marker ||
          !result.data.document.includes(result.data.marker)
        )
          throw new Error("Preview unavailable");
        setLoaded({ identity, data: result.data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setLoaded({ identity, failed: true });
      });
    return () => controller.abort();
  }, [accessToken, groupId, identity]);
  const escaped = text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  const beforeMarker =
    preview?.document.split(preview.marker)[0].toLowerCase() ?? "";
  const titleSelected =
    beforeMarker.lastIndexOf("<title") > beforeMarker.lastIndexOf("</title");
  const highlighted = `<mark data-verboflex-selected style="background:#fef08a;color:#111827;outline:2px solid #d97706;border-radius:2px;box-decoration-break:clone">${escaped}</mark>`;
  // Email templates commonly use fixed-width tables. Scale their 640px canvas
  // to fit the context column; scrolling stays inside the isolated document.
  const scale = Math.min(1, Math.max(width, 1) / 640);
  return (
    <div className="min-w-0 space-y-3">
      {preview && (
        <>
          <p className="break-all text-xs text-muted-foreground">
            {preview.path}
          </p>
          {titleSelected ? (
            <p className="text-sm wrap-anywhere">
              <strong>{t("Email title")}: </strong>
              {text}
            </p>
          ) : (
            <p className="text-sm">
              <span className="rounded bg-yellow-200 px-1 text-slate-900">
                {t("Selected text")}
              </span>
            </p>
          )}
        </>
      )}
      <div
        ref={viewport}
        className="relative h-[65vh] max-h-[48rem] min-h-80 overflow-hidden rounded-md border bg-white"
      >
        {preview ? (
          <iframe
            title={t("HTML template preview")}
            sandbox=""
            referrerPolicy="no-referrer"
            className="absolute top-0 left-0 origin-top-left border-0"
            style={{
              width: scale < 1 ? 640 : "100%",
              height: `${100 / scale}%`,
              transform: `scale(${scale})`,
            }}
            srcDoc={
              policy +
              preview.document.replace(preview.marker, () =>
                titleSelected ? escaped : highlighted,
              )
            }
          />
        ) : failed ? (
          <div role="alert" className="space-y-3 p-4 text-slate-900">
            <p>{t("HTML preview could not be loaded")}</p>
            <Button
              type="button"
              variant="outline"
              onClick={() => setAttempt((value) => value + 1)}
            >
              {t("Retry")}
            </Button>
          </div>
        ) : (
          <p role="status" className="p-4 text-slate-600">
            {t("Loading HTML template…")}
          </p>
        )}
      </div>
      {(preview?.missing_images ?? 0) > 0 && (
        <p role="status" className="text-sm text-muted-foreground">
          {t(
            "Some repository images are unavailable. Refresh the project source or check their paths.",
          )}
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        {t(
          "Preview shows imported content with your current edit and repository images. External images are disabled.",
        )}
      </p>
    </div>
  );
}
