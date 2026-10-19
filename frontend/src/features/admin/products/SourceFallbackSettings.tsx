import { t, useUiLanguage } from "@/i18n";
import { useEffect, useRef, useState } from "react";

import {
  getAdminSourceFallback,
  updateAdminSourceFallback,
  searchTranslationKeys,
  type SourceFallbackResponse,
} from "../../../api/client";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";

type Props = { accessToken: string; productId: string };

export function SourceFallbackSettings(props: Props) {
  useUiLanguage();
  const [opened, setOpened] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{
    data?: SourceFallbackResponse;
    failed?: boolean;
  }>({});
  useEffect(() => {
    if (!opened) return;
    const controller = new AbortController();
    void getAdminSourceFallback({
      auth: props.accessToken,
      path: { product_id: props.productId },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.data || result.data.product_id !== props.productId)
          throw new Error();
        setState({ data: result.data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ failed: true });
      });
    return () => controller.abort();
  }, [opened, attempt, props.accessToken, props.productId]);
  return (
    <details
      className="rounded-lg border bg-card p-4"
      onToggle={(event) => {
        if (event.currentTarget.open) setOpened(true);
      }}
    >
      <summary className="cursor-pointer font-semibold">
        {t("Source language settings")}
      </summary>
      {opened && (
        <div className="mt-4">
          {state.data ? (
            <SourceFallbackForm key={attempt} {...props} initial={state.data} />
          ) : state.failed ? (
            <div role="alert">
              <p>{t("Source language settings could not be loaded.")}</p>
              <Button variant="outline" onClick={() => setAttempt(attempt + 1)}>
                {t("Retry settings")}
              </Button>
            </div>
          ) : (
            <p role="status">{t("Loading source language settings…")}</p>
          )}
        </div>
      )}
    </details>
  );
}

function SourceFallbackForm({
  accessToken,
  productId,
  initial,
}: Props & { initial: SourceFallbackResponse }) {
  useUiLanguage();
  const [policy, setPolicy] = useState(initial);
  const [enabled, setEnabled] = useState(initial.enabled);
  const [language, setLanguage] = useState(
    initial.language ?? initial.available_languages[0] ?? "",
  );
  const [selected, setSelected] = useState(new Set(initial.source_texts));
  const [query, setQuery] = useState("");
  const [page, setPage] = useState<{
    texts: string[];
    cursor: string | null;
    failed?: boolean;
  }>({ texts: [], cursor: null });
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const saveController = useRef<AbortController | null>(null);
  useEffect(() => () => saveController.current?.abort(), []);
  useEffect(() => {
    if (!language) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      void searchTranslationKeys({
        auth: accessToken,
        signal: controller.signal,
        query: {
          product_id: productId,
          language,
          visible_languages: [language],
          ...(query ? { q: query } : {}),
          ...(cursor ? { cursor } : {}),
        },
      })
        .then((result) => {
          if (controller.signal.aborted) return;
          if (!result.data) throw new Error();
          const texts = result.data.items.flatMap((item) =>
            item.base_language === language &&
            item.source_text &&
            !item.source_truncated &&
            item.slots.some(
              (slot) =>
                slot.language === language &&
                slot.provenance?.format === "qt_ts" &&
                slot.selector_kinds.every((kind) => kind === "scalar"),
            )
              ? [item.source_text]
              : [],
          );
          setPage((old) => ({
            texts: [...new Set([...(cursor ? old.texts : []), ...texts])],
            cursor: result.data!.next_cursor,
          }));
        })
        .catch(() => {
          if (!controller.signal.aborted)
            setPage((old) => ({ ...old, failed: true }));
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [accessToken, productId, language, query, cursor]);
  async function save() {
    if (saving) return;
    setSaving(true);
    setMessage("");
    setFailed(false);
    const controller = new AbortController();
    saveController.current = controller;
    try {
      const result = await updateAdminSourceFallback({
        auth: accessToken,
        path: { product_id: productId },
        signal: controller.signal,
        body: {
          expected_version: policy.version,
          enabled,
          language: language || null,
          source_texts: [...selected],
        },
      });
      if (!result.data || result.data.product_id !== productId)
        throw new Error();
      if (controller.signal.aborted) return;
      setPolicy(result.data);
      setMessage("Source language settings saved.");
    } catch {
      if (!controller.signal.aborted) {
        setFailed(true);
        setMessage(
          "Settings were not saved. Reload the page if another administrator changed them.",
        );
      }
    } finally {
      if (!controller.signal.aborted) setSaving(false);
    }
  }
  return (
    <div className="max-w-4xl space-y-4">
      <p className="text-sm text-muted-foreground">
        {t(
          "Confirm which source phrases are already in the base language. Empty Qt translations will use the selected text and leave Needs translation. New or changed phrases still need translation until confirmed here. Repository files and approvals are unchanged.",
        )}
      </p>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={enabled}
          disabled={saving}
          onChange={(event) => setEnabled(event.target.checked)}
        />
        {t("Use confirmed source text for the base language")}
      </label>
      <label className="flex flex-wrap items-center gap-3">
        {t("Base language")}
        <select
          aria-label={t("Source fallback base language")}
          value={language}
          disabled={saving}
          className="rounded-md border p-2"
          onChange={(event) => {
            setLanguage(event.target.value);
            setSelected(new Set());
            setCursor(null);
            setPage({ texts: [], cursor: null });
          }}
        >
          {!language && <option value="">{t("Select a base language")}</option>}
          {initial.available_languages.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </label>
      <p className="text-sm">
        {selected.size} {t(" source phrases confirmed")}
      </p>
      <Input
        aria-label={t("Find source phrases")}
        placeholder={t("Find source phrases…")}
        maxLength={256}
        value={query}
        disabled={saving}
        onChange={(event) => {
          setQuery(event.target.value);
          setCursor(null);
          setPage({ texts: [], cursor: null });
        }}
      />
      <div
        className="max-h-80 space-y-2 overflow-y-auto rounded-md border p-3"
        aria-label={t("Source phrases")}
      >
        {page.texts.map((text) => (
          <label key={text} className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              checked={selected.has(text)}
              disabled={
                saving || (!selected.has(text) && selected.size >= 2000)
              }
              onChange={(event) =>
                setSelected((old) => {
                  const next = new Set(old);
                  if (event.target.checked) next.add(text);
                  else next.delete(text);
                  return next;
                })
              }
            />
            <span
              className="min-w-0 whitespace-pre-wrap wrap-anywhere"
              dir="auto"
            >
              {text}
            </span>
          </label>
        ))}
        {loading && <p role="status">{t("Loading source phrases…")}</p>}
        {page.failed && (
          <p role="alert">
            {t("Source phrases could not be loaded. Search again to retry.")}
          </p>
        )}
        {!loading && !page.failed && page.texts.length === 0 && (
          <p>{t("No matching Qt source phrases.")}</p>
        )}
      </div>
      {page.cursor && (
        <Button
          variant="outline"
          disabled={loading || saving}
          onClick={() => setCursor(page.cursor)}
        >
          {t("Load more source phrases")}
        </Button>
      )}
      <div>
        <Button
          disabled={saving || (enabled && !language)}
          onClick={() => void save()}
        >
          {saving ? t("Saving…") : t("Save source language settings")}
        </Button>
      </div>
      {message && <p role={failed ? "alert" : "status"}>{t(message)}</p>}
    </div>
  );
}
