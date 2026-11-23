import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { AdminPublishedMappingImportResponse } from "../../../api/client";
import { t, useUiLanguage } from "../../../i18n";

function updateStatus(item: AdminPublishedMappingImportResponse) {
  switch (item.state) {
    case "current":
      return t("Catalog updated");
    case "queued":
      return t("Update queued");
    case "running":
      return t("Reading the latest strings…");
    case "review_required":
      return t("Review the source changes before updating");
    case "not_imported":
      return t("Ready for the first update");
    case "import_failed":
    case "may_be_stale":
      return t("Catalog update unsuccessful");
  }
}

function updateAdvice(item: AdminPublishedMappingImportResponse) {
  switch (item.error_category) {
    case "timeout":
      return t(
        "The source did not respond in time. Try again in a few minutes.",
      );
    case "provider_unavailable":
    case "rate_limited":
      return t(
        "The source is temporarily unavailable. Try again in a few minutes.",
      );
    case "confirmation_required":
      return t(
        "Confirm the source in product settings, then update the catalog again.",
      );
    case "source_not_found":
    case "connection_required":
    case "permission_denied":
      return t(
        "Check the source and its access in product settings before trying again.",
      );
    default:
      return t("Check the source details below before trying again.");
  }
}

export function CatalogUpdateCard({
  item,
  names,
  productId,
  action,
  details,
  error,
}: {
  item: AdminPublishedMappingImportResponse;
  names: string[];
  productId: string;
  action: ReactNode;
  details: ReactNode;
  error: ReactNode;
}) {
  const language = useUiLanguage();
  const format = new Intl.DateTimeFormat(language, {
    dateStyle: "medium",
    timeStyle: "short",
  });
  const catalog = item.active_baseline;
  const strings = `/products/${encodeURIComponent(productId)}/strings`;
  const failed =
    item.state === "import_failed" || item.state === "may_be_stale";
  const warnings = Boolean(
    item.duplicate_report_summary?.group_count ||
    item.parser_issues.length ||
    item.parser_issue_remaining_count,
  );
  return (
    <article
      className="grid min-w-0 gap-3 rounded-lg border bg-card p-4"
      aria-label={names.join(" · ")}
    >
      <h3 className="font-semibold wrap-anywhere">{names.join(" · ")}</h3>
      <div aria-live="polite" className="grid gap-1">
        <strong>{updateStatus(item)}</strong>
        {failed && <p>{updateAdvice(item)}</p>}
        {failed && item.latest_execution_at && (
          <p>
            {t("Last attempt on {{date}}", {
              date: format.format(new Date(item.latest_execution_at)),
            })}
          </p>
        )}
        {catalog ? (
          <p>
            {t("You are viewing the strings from {{date}}.", {
              date: format.format(new Date(catalog.imported_at)),
            })}
          </p>
        ) : (
          <p>
            {t("Strings will appear here after the first successful update.")}
          </p>
        )}
      </div>
      {error}
      <div className="flex flex-wrap items-center gap-4">
        {action}
        {catalog && (
          <Link className="text-primary underline" to={strings}>
            {t("Open translation catalog")}
          </Link>
        )}
        {catalog && item.state === "current" && (
          <Link
            className="text-primary underline"
            to={strings + "?work_status=source_changed"}
          >
            {t("Review translations with changed source text")}
          </Link>
        )}
      </div>
      <details className="min-w-0 text-sm">
        <summary className="cursor-pointer">
          {warnings ? t("Source details and warnings") : t("Source details")}
        </summary>
        <div className="mt-3 grid gap-3">{details}</div>
      </details>
    </article>
  );
}
