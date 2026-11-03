import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MousePointer2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { HtmlEditorDocument } from "@/api/client";
import { t, useUiLanguage } from "@/i18n";

const policy = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">`;
const previewStyle = `<style>html,body{height:auto!important;min-height:0!important}html{overflow:hidden}body{margin:8px} [data-vf-fragment]{cursor:pointer;border-radius:2px} [data-vf-fragment]:hover{outline:1px dashed #0f766e} [data-vf-fragment][aria-pressed=true]{background:#f0fdfa!important;color:#111827!important;outline:2px solid #0f766e;box-decoration-break:clone} [data-vf-fragment]:focus-visible{outline:2px solid #0f766e;outline-offset:3px}</style>`;
const escape = (value: string) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

// eslint-disable-next-line react-refresh/only-export-components
export function hasEditableHtmlText(text: string) {
  return Boolean(
    text.replace(/\{\{\s*[A-Za-z_][A-Za-z0-9_.]*\s*\}\}/g, "").trim(),
  );
}

export function InteractiveEmailCanvas({
  document: preview,
  selectedId,
  texts,
  onSelect,
  disabled,
}: {
  document: HtmlEditorDocument;
  selectedId: string | null;
  texts: ReadonlyMap<string, string>;
  onSelect: (id: string) => void;
  disabled: boolean;
}) {
  useUiLanguage();
  const frame = useRef<HTMLIFrameElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const observer = useRef<ResizeObserver | null>(null);
  const cleanFrame = useRef<(() => void) | null>(null);
  const [size, setSize] = useState({ width: 0, height: 640, scale: 1 });
  const available = useMemo(
    () =>
      new Set(
        preview.fragments
          .filter((f) => f.element !== "title" && hasEditableHtmlText(f.text))
          .map((f) => f.group_id),
      ),
    [preview],
  );
  const selectLabel = t("Select email text");
  const srcDoc = useMemo(() => {
    let html = preview.document;
    for (const fragment of preview.fragments) {
      const value = available.has(fragment.group_id)
        ? `<span data-vf-fragment="${escape(fragment.group_id)}" role="button" tabindex="0" aria-label="${escape(selectLabel)}">${escape(fragment.text)}</span>`
        : escape(fragment.text);
      html = html.replace(fragment.marker, () => value);
    }
    return policy + previewStyle + html;
  }, [preview, available, selectLabel]);
  const measure = useCallback(() => {
    const doc = frame.current?.contentDocument;
    const width = viewport.current?.clientWidth ?? 0;
    if (!doc?.body || !width) return;
    const natural = Math.max(
      width,
      doc.body.scrollWidth,
      doc.documentElement.scrollWidth,
    );
    const height = Math.max(80, Math.min(12000, doc.body.scrollHeight + 16));
    const scale = Math.min(1, width / natural);
    setSize((old) =>
      Math.abs(old.width - natural) < 1 &&
      Math.abs(old.height - height) < 1 &&
      Math.abs(old.scale - scale) < 0.001
        ? old
        : { width: natural, height, scale },
    );
  }, []);
  const synchronize = useCallback(() => {
    const doc = frame.current?.contentDocument;
    if (!doc) return;
    doc
      .querySelectorAll<HTMLElement>("[data-vf-fragment]")
      .forEach((element) => {
        const id = element.dataset.vfFragment!;
        if (!available.has(id)) return;
        const content = texts.get(id);
        if (content !== undefined && element.textContent !== content)
          element.textContent = content;
        element.setAttribute("aria-pressed", String(id === selectedId));
        element.setAttribute("aria-disabled", String(disabled));
        element.setAttribute(
          "aria-label",
          `${selectLabel}: ${element.textContent?.slice(0, 200) ?? ""}`,
        );
      });
    measure();
  }, [available, texts, selectedId, disabled, selectLabel, measure]);
  // Listener authority is replaced on every selection/permission change, never supplied by the email.
  const connect = useCallback(() => {
    cleanFrame.current?.();
    const doc = frame.current?.contentDocument;
    if (!doc?.body) return;
    const pick = (event: Event) => {
      if (
        event.type === "keydown" &&
        !["Enter", " "].includes((event as KeyboardEvent).key)
      )
        return;
      const target = event.target as Element | null;
      const id = target
        ?.closest?.("[data-vf-fragment]")
        ?.getAttribute("data-vf-fragment");
      if (!id || !available.has(id)) return;
      event.preventDefault();
      if (!disabled) onSelect(id);
    };
    doc.addEventListener("click", pick);
    doc.addEventListener("keydown", pick);
    const resize = new ResizeObserver(measure);
    resize.observe(doc.body);
    doc
      .querySelectorAll("img")
      .forEach((img) => img.addEventListener("load", measure));
    cleanFrame.current = () => {
      doc.removeEventListener("click", pick);
      doc.removeEventListener("keydown", pick);
      doc
        .querySelectorAll("img")
        .forEach((img) => img.removeEventListener("load", measure));
      resize.disconnect();
    };
    synchronize();
  }, [available, disabled, measure, onSelect, synchronize]);
  useEffect(() => {
    connect();
    return () => cleanFrame.current?.();
  }, [connect]);
  useEffect(() => {
    observer.current = new ResizeObserver(() => {
      measure();
    });
    if (viewport.current) observer.current.observe(viewport.current);
    return () => observer.current?.disconnect();
  }, [measure]);
  return (
    <div className="min-w-0 space-y-3">
      {preview.fragments
        .filter((fragment) => fragment.element === "title")
        .map((fragment) => (
          <Button
            key={fragment.group_id}
            variant="outline"
            disabled={disabled}
            aria-pressed={selectedId === fragment.group_id}
            className={`h-auto min-h-11 w-full flex-col items-start gap-1 whitespace-normal text-left ${selectedId === fragment.group_id ? "border-primary bg-primary/5" : ""}`}
            onClick={() => onSelect(fragment.group_id)}
          >
            <span className="text-label text-muted-foreground">
              {t("Email title")}
            </span>
            <span className="wrap-anywhere">
              {texts.get(fragment.group_id) ?? fragment.text}
            </span>
          </Button>
        ))}
      <div
        ref={viewport}
        className="relative w-full overflow-hidden rounded border bg-white"
        style={{ height: Math.ceil(size.height * size.scale) }}
      >
        <iframe
          ref={frame}
          title={t("Interactive email preview")}
          sandbox="allow-same-origin"
          referrerPolicy="no-referrer"
          className="absolute top-0 left-0 origin-top-left border-0"
          style={{
            width: size.width || "100%",
            height: size.height,
            transform: `scale(${size.scale})`,
          }}
          srcDoc={srcDoc}
          onLoad={connect}
        />
      </div>
      <p className="flex items-center justify-center gap-2 text-label text-muted-foreground">
        <MousePointer2 aria-hidden="true" className="size-4" />
        {t("Click a text in the email to translate it")}
      </p>
      {preview.missing_images > 0 && (
        <p role="status" className="text-label text-muted-foreground">
          {t(
            "Some repository images are unavailable. Refresh the project source or check their paths.",
          )}
        </p>
      )}
    </div>
  );
}
