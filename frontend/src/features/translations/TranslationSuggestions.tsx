import { t, useUiLanguage } from "@/i18n";
import { GlossaryMatches } from "./GlossaryMatches";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Copy, RotateCw } from "lucide-react";
import {
  getTranslationSuggestions,
  resolveTranslationSuggestion,
  type ReuseQuery,
  type ReuseSuggestion,
} from "../../api/client";
import { Button } from "../../components/ui/button";

function SourceDifference({
  source,
  current,
}: {
  source: string;
  current: string;
}) {
  useUiLanguage();
  if (source === current) return <>{source}</>;
  // Bound linear comparison; changed spans remain readable with either script.
  const before = Array.from(source),
    after = Array.from(current);
  let start = 0,
    end = 0;
  while (
    start < Math.min(before.length, after.length) &&
    before[start] === after[start]
  )
    start++;
  while (
    end < Math.min(before.length, after.length) - start &&
    before[before.length - 1 - end] === after[after.length - 1 - end]
  )
    end++;
  return (
    <>
      {before.slice(0, start).join("")}
      <mark className="bg-amber-100 text-amber-950">
        {before.slice(start, before.length - end).join("") || "∅"}
      </mark>
      {end ? before.slice(-end).join("") : ""}
    </>
  );
}
export function TranslationSuggestions({
  accessToken,
  productId,
  query,
  disabled,
  onUse,
  currentText,
}: {
  accessToken: string;
  productId: string;
  query: ReuseQuery | null;
  disabled: boolean;
  onUse: (text: string) => void;
  currentText: string;
}) {
  useUiLanguage();
  const [loadedIdentity, setLoadedIdentity] = useState("");
  const [items, setItems] = useState<ReuseSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [applying, setApplying] = useState<string | null>(null);
  const generation = useRef(0);
  const textAtApply = useRef(currentText);
  useLayoutEffect(() => {
    textAtApply.current = currentText;
  }, [currentText]);
  const currentQuery = JSON.stringify(query);
  const identity = JSON.stringify([
    accessToken,
    productId,
    currentQuery,
    refresh,
  ]);
  useEffect(() => {
    const controller = new AbortController();
    const requestGeneration = ++generation.current;
    const parsed: ReuseQuery | null = JSON.parse(currentQuery);
    if (!parsed) return () => controller.abort();
    // Reset via a microtask so one render's prior suggestions cannot be applied.
    void Promise.resolve().then(async () => {
      if (controller.signal.aborted) return;
      setLoading(true);
      setFailure(null);
      setItems([]);
      setApplying(null);
      try {
        const response = await getTranslationSuggestions({
          auth: accessToken,
          path: { product_id: productId },
          body: parsed,
          signal: controller.signal,
        });
        if (
          controller.signal.aborted ||
          generation.current !== requestGeneration
        )
          return;
        if (!response.data)
          throw new Error(t("Suggestions could not be loaded"));
        setItems(response.data.items);
        setLoadedIdentity(identity);
      } catch {
        if (!controller.signal.aborted)
          setFailure("Suggestions could not be loaded");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    });
    return () => {
      controller.abort();
      generation.current = requestGeneration + 1;
    };
  }, [accessToken, productId, currentQuery, refresh, identity]);
  async function applySuggestion(item: ReuseSuggestion) {
    if (
      !query ||
      disabled ||
      loading ||
      applying ||
      loadedIdentity !== identity
    )
      return;
    const requestGeneration = generation.current;
    const expectedText = currentText;
    setApplying(item.digest);
    setFailure(null);
    try {
      const response = await resolveTranslationSuggestion({
        auth: accessToken,
        path: { product_id: productId },
        body: {
          query,
          source_value_id: item.source_value_id,
          target_value_id: item.target_value_id,
          expected_digest: item.digest,
        },
      });
      if (generation.current !== requestGeneration) return;
      if (!response.data) {
        setFailure("This suggestion changed. Refresh suggestions.");
        return;
      }
      if (textAtApply.current !== expectedText) {
        setFailure("Translation changed. Choose the suggestion again.");
        return;
      }
      onUse(response.data.target_text);
    } catch {
      if (generation.current === requestGeneration)
        setFailure("Could not apply this suggestion");
    } finally {
      if (generation.current === requestGeneration) setApplying(null);
    }
  }
  if (!query) return null;
  return (
    <aside
      aria-label={t("Translation suggestions")}
      className="min-w-0 self-start rounded-lg border bg-background p-3 space-y-3"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">{t("Suggestions")}</h3>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={t("Refresh suggestions")}
          disabled={loading || !!applying}
          onClick={() => setRefresh((r) => r + 1)}
        >
          <RotateCw className="size-4" />
        </Button>
      </div>
      {loading && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("Finding matches…")}
        </p>
      )}
      {failure && (
        <p role="alert" className="text-sm text-destructive">
          {t(failure)}
        </p>
      )}
      {!loading && !failure && items.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("No matches")}</p>
      )}
      <div className="max-h-[32rem] space-y-3 overflow-y-auto">
        {(loadedIdentity === identity ? items : []).map((item) => (
          <article
            key={item.digest}
            className="space-y-2 rounded-md border p-3"
          >
            <div className="flex items-center justify-between gap-2">
              <span
                className={`rounded px-2 py-0.5 text-sm font-semibold ${item.match_percent === 100 ? "bg-emerald-100 text-emerald-900" : "bg-amber-100 text-amber-950"}`}
              >
                {item.match_percent}%
              </span>
              <span className="text-xs text-muted-foreground">
                {item.origin === "approved_draft"
                  ? t("Approved draft")
                  : t("Repository")}
              </span>
            </div>
            <p
              lang={item.source_language}
              dir="auto"
              className="whitespace-pre-wrap break-words text-sm text-muted-foreground"
            >
              <SourceDifference
                source={item.source_text}
                current={query.source_text}
              />
            </p>
            <p
              lang={item.target_language}
              dir="auto"
              className="whitespace-pre-wrap break-words"
            >
              {item.target_text}
            </p>
            <details className="text-xs text-muted-foreground break-all">
              <summary className="cursor-pointer">{item.key}</summary>
              <p>
                {item.product_name} · {item.repository}
              </p>
              <p>{item.file}</p>
            </details>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={disabled || loading || !!applying}
              onClick={() => void applySuggestion(item)}
            >
              <Copy className="size-3.5" />
              {applying === item.digest ? t("Checking…") : t("Use")}
            </Button>
          </article>
        ))}
      </div>
      <GlossaryMatches
        accessToken={accessToken}
        productId={productId}
        query={query}
        currentText={currentText}
        refresh={refresh}
      />
    </aside>
  );
}
