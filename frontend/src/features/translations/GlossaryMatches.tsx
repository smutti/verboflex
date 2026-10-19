import { t, useUiLanguage } from "@/i18n";
import { useEffect, useState } from "react";
import {
  matchGlossaryTerms,
  type GlossaryMatches as Matches,
  type ReuseQuery,
} from "../../api/client";
function containsTerm(text: string, term: string, sensitive: boolean) {
  if (!sensitive) {
    text = text.toLocaleLowerCase().replaceAll("ß", "ss");
    term = term.toLocaleLowerCase().replaceAll("ß", "ss");
  }
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const word = Array.from(term).every((c) => c.codePointAt(0)! < 0x2e80);
  const alnum = /[\p{L}\p{N}]/u;
  return new RegExp(
    (word && alnum.test(term[0]) ? "(?<![\\p{L}\\p{N}_])" : "") +
      escaped +
      (word && alnum.test(term.at(-1)!) ? "(?![\\p{L}\\p{N}_])" : ""),
    "u",
  ).test(text);
}
export function GlossaryMatches({
  accessToken,
  productId,
  query,
  currentText,
  refresh,
}: {
  accessToken: string;
  productId: string;
  query: ReuseQuery;
  currentText: string;
  refresh: number;
}) {
  useUiLanguage();
  const identity = JSON.stringify([
    productId,
    query.source_language,
    query.target_language,
    query.source_text,
  ]);
  const [result, setResult] = useState<{
    identity: string;
    data?: Matches;
    error?: boolean;
  } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const [product, source_language, target_language, source_text] = JSON.parse(
      identity,
    ) as string[];
    void matchGlossaryTerms({
      auth: accessToken,
      path: { product_id: product },
      body: { source_language, target_language, source_text },
      signal: controller.signal,
    })
      .then((r) => {
        if (!controller.signal.aborted)
          setResult({
            identity,
            ...(r.data ? { data: r.data } : { error: true }),
          });
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ identity, error: true });
      });
    return () => controller.abort();
  }, [accessToken, identity, refresh]);
  if (!result || result.identity !== identity)
    return (
      <p className="text-xs text-muted-foreground">{t("Checking terms…")}</p>
    );
  if (result.error)
    return (
      <p role="status" className="text-sm text-destructive">
        {t("Terms could not be loaded")}
      </p>
    );
  if (!result.data?.items.length) return null;
  return (
    <section
      aria-label={t("Glossary terms")}
      className="space-y-2 border-t pt-3"
    >
      <h4 className="font-semibold text-sm">{t("Terms")}</h4>
      {result.data.items.map((term) => {
        const present = containsTerm(
          currentText,
          term.target_term,
          term.case_sensitive ?? false,
        );
        const violation = term.forbidden && present;
        return (
          <div
            key={term.id}
            className={`rounded border p-2 text-sm ${violation ? "border-red-500 bg-red-50 text-red-800" : ""}`}
          >
            <p>
              {term.source_term} →{" "}
              <strong className={term.forbidden ? "line-through" : ""}>
                {term.target_term}
              </strong>
            </p>
            <p className="text-xs">
              {term.forbidden
                ? violation
                  ? t("Forbidden term in translation")
                  : t("Forbidden")
                : present
                  ? t("Preferred term used")
                  : t("Preferred term")}
            </p>
            {term.note && <p className="text-xs mt-1">{term.note}</p>}
          </div>
        );
      })}
      {result.data.truncated && (
        <p className="text-xs text-muted-foreground">
          {t("First 50 matching terms")}
        </p>
      )}
    </section>
  );
}
