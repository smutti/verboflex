import { t, useUiLanguage, displayLanguage } from "@/i18n";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  deactivateAdminProduct,
  getAdminProduct,
  getAdminProductSummary,
  type AdminProductResponse,
  type AdminProductSummaryResponse,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../../../components/ui/alert-dialog";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Skeleton } from "../../../components/ui/skeleton";
import { ProductDetailLayout } from "./ProductDetailLayout";
import { ProductDeleteDialog } from "./ProductDeleteDialog";
import { SourceFallbackSettings } from "./SourceFallbackSettings";

export interface ProductOverviewPageProps {
  accessToken: string;
  productId?: string;
}

type ProductLoadState =
  | { status: "loading" }
  | { status: "error" }
  | {
      status: "ready";
      product: AdminProductResponse;
      productId: string;
      accessToken: string;
    };

type ReadyProductLoadState = Extract<ProductLoadState, { status: "ready" }>;

function CoverageBar({ value, label }: { value: number; label: string }) {
  useUiLanguage();
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
      className="h-2 overflow-hidden rounded-full bg-muted"
    >
      <div
        className="h-full rounded-full bg-primary"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

function languageName(code: string) {
  try {
    return displayLanguage(code);
  } catch {
    return code;
  }
}

function LocalizationSummary({
  accessToken,
  productId,
  isActive,
}: {
  accessToken: string;
  productId: string;
  isActive: boolean;
}) {
  const language = useUiLanguage();
  const countFormat = new Intl.NumberFormat(language);
  const percentFormat = new Intl.NumberFormat(language, {
    maximumFractionDigits: 1,
  });
  const [request, setRequest] = useState(0);
  const [load, setLoad] = useState<{
    request: number;
    data?: AdminProductSummaryResponse;
    failed?: boolean;
  }>({ request: 0 });
  useEffect(() => {
    const controller = new AbortController();
    void getAdminProductSummary({
      auth: accessToken,
      path: { product_id: productId },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.data || result.data.product_id !== productId)
          throw new Error("Summary unavailable");
        setLoad({ request, data: result.data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setLoad({ request, failed: true });
      });
    return () => controller.abort();
  }, [accessToken, productId, request]);
  const current = load.request === request ? load : undefined;
  if (current?.failed)
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("Translation summary unavailable")}</AlertTitle>
        <AlertDescription className="grid gap-3">
          <p>
            {t(
              "We could not load translation coverage. Product settings are still available.",
            )}
          </p>
          <Button
            variant="outline"
            className="w-fit"
            onClick={() => setRequest((value) => value + 1)}
          >
            {t("Retry summary")}
          </Button>
        </AlertDescription>
      </Alert>
    );
  if (!current?.data)
    return (
      <section role="status" aria-live="polite" className="grid gap-4">
        <span>{t("Loading translation summary")}</span>
        <Skeleton className="h-40 w-full" />
      </section>
    );
  const summary = current.data;
  const stats = [
    {
      label: t("Source strings"),
      value: summary.source_string_count,
    },
    {
      label: t("Translated"),
      value: summary.translated_count,
      detail: t("of {{v0}} target strings", {
        v0: countFormat.format(summary.expected_translation_count),
      }),
    },
    {
      label: t("Missing or unfinished"),
      value: summary.missing_count,
    },
    {
      label: t("Target languages"),
      value: summary.target_language_count,
    },
  ];
  return (
    <div className="grid min-w-0 gap-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map(({ label, value, detail }) => (
          <section
            key={label}
            aria-label={label}
            className="grid content-start gap-2 rounded-lg border bg-secondary p-5"
          >
            <h2 className="text-sm font-medium text-muted-foreground">
              {label}
            </h2>
            <p className="text-3xl font-semibold tracking-tight tabular-nums">
              {countFormat.format(value)}
            </p>
            {detail && (
              <p className="text-sm text-muted-foreground">{detail}</p>
            )}
          </section>
        ))}
      </div>
      <section
        aria-label={t("Translation coverage")}
        className="grid gap-5 rounded-lg border bg-secondary p-5 sm:p-6"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="grid gap-1">
            <h2 className="text-heading font-semibold">
              {t("Translation coverage")}
            </h2>
            <p className="text-sm text-muted-foreground">
              {t("Target languages only")}
            </p>
          </div>
          <p className="text-3xl font-semibold tracking-tight tabular-nums">
            {summary.coverage_percent === null
              ? "—"
              : `${percentFormat.format(summary.coverage_percent)}%`}
          </p>
        </div>
        {summary.coverage_percent !== null && (
          <CoverageBar
            value={summary.coverage_percent}
            label={t("Overall translation coverage")}
          />
        )}
        {summary.imported_scope_count === 0 ? (
          <p>{t("Import translations to see coverage.")}</p>
        ) : summary.source_string_count === 0 ? (
          <p>{t("No source strings imported.")}</p>
        ) : summary.target_language_count === 0 ? (
          <p>{t("Only source strings imported; no target languages yet.")}</p>
        ) : null}
        {summary.unimported_scope_count > 0 ? (
          <p className="text-sm text-warning">
            {summary.unimported_scope_count}{" "}
            {summary.unimported_scope_count === 1
              ? t("translation source has")
              : t("translation sources have")}{" "}
            {t("not been imported yet; excluded from totals.")}
          </p>
        ) : null}
        {summary.last_imported_at ? (
          <p className="text-sm text-muted-foreground">
            {t("Last successful import:")}{" "}
            <time dateTime={summary.last_imported_at}>
              {new Intl.DateTimeFormat(language, {
                dateStyle: "medium",
                timeStyle: "short",
              }).format(new Date(summary.last_imported_at))}
            </time>
          </p>
        ) : null}
      </section>
      {summary.languages.length > 0 ? (
        <section
          aria-labelledby="language-coverage-heading"
          className="grid min-w-0 gap-4"
        >
          <div>
            <h2
              id="language-coverage-heading"
              className="text-heading font-semibold"
            >
              {t("Languages needing attention")}
            </h2>
          </div>
          <div className="relative max-w-full overflow-x-auto rounded-lg border bg-secondary">
            <table
              aria-label={t("Translation coverage by language")}
              className="w-full text-left text-sm"
            >
              <thead className="border-b bg-muted/40">
                <tr>
                  <th scope="col" className="p-4">
                    {t("Language")}
                  </th>
                  <th scope="col" className="p-4">
                    {t("Translated")}
                  </th>
                  <th scope="col" className="p-4">
                    {t("Missing or unfinished")}
                  </th>
                  <th scope="col" className="min-w-32 p-4">
                    {t("Coverage")}
                  </th>
                  <th scope="col" className="p-4">
                    <span className="sr-only">{t("Actions")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {summary.languages.map((row) => (
                  <tr key={row.language} className="border-b last:border-0">
                    <th scope="row" className="p-4 font-medium">
                      <span className="block">
                        {languageName(row.language)}
                      </span>
                      <span className="text-xs font-normal text-muted-foreground">
                        {row.language}
                      </span>
                    </th>
                    <td className="p-4 tabular-nums whitespace-nowrap">
                      {countFormat.format(row.translated_count)}{" "}
                      <span className="text-muted-foreground">
                        / {countFormat.format(row.expected_count)}
                      </span>
                    </td>
                    <td className="p-4 font-medium tabular-nums">
                      {countFormat.format(row.missing_count)}
                    </td>
                    <td className="p-4">
                      <div className="grid gap-2">
                        <span className="tabular-nums">
                          {row.coverage_percent === null
                            ? "—"
                            : `${percentFormat.format(row.coverage_percent)}%`}
                        </span>
                        {row.coverage_percent !== null ? (
                          <CoverageBar
                            value={row.coverage_percent}
                            label={t("{{v0}} translation coverage", {
                              v0: row.language,
                            })}
                          />
                        ) : null}
                      </div>
                    </td>
                    <td className="p-4">
                      {isActive ? (
                        <Button asChild variant="outline" size="sm">
                          <Link
                            to={`/products/${encodeURIComponent(productId)}/strings?language=${encodeURIComponent(row.language)}`}
                          >
                            {t("Open language")}
                          </Link>
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!isActive ? (
            <p className="text-sm text-muted-foreground">
              {t("Activate the product to access its strings.")}
            </p>
          ) : null}
          {summary.languages_has_more ? (
            <p className="text-sm text-muted-foreground">
              {t("Top ")}
              {countFormat.format(summary.languages.length)}{" "}
              {t(" languages by missing strings. Totals cover all")}{" "}
              {countFormat.format(summary.target_language_count)}{" "}
              {t(" languages.")}
            </p>
          ) : null}
        </section>
      ) : null}
      <details className="max-w-3xl text-sm text-muted-foreground">
        <summary className="cursor-pointer">{t("About coverage")}</summary>
        <p className="mt-2">
          {t(
            "Imported languages only. A translation is complete when every form has finished text. Missing or unfinished forms count as missing. Draft edits and review status are excluded.",
          )}
        </p>
      </details>
    </div>
  );
}

export function ProductOverviewPage({
  accessToken,
  productId,
}: ProductOverviewPageProps) {
  useUiLanguage();
  const routeProductId = useParams<"productId">().productId;
  const navigate = useNavigate();
  const resolvedProductId = productId ?? routeProductId;
  const loadGeneration = useRef(0);
  const deactivateTriggerRef = useRef<HTMLButtonElement>(null);
  const deactivateErrorRef = useRef<HTMLDivElement>(null);
  const deactivatePendingRef = useRef(false);
  const [loadState, setLoadState] = useState<ProductLoadState>({
    status: "loading",
  });
  const [deactivateOpen, setDeactivateOpen] = useState(false);
  const [deactivatePending, setDeactivatePending] = useState(false);
  const [deactivateError, setDeactivateError] = useState(false);

  const loadProduct = useCallback(async () => {
    const generation = ++loadGeneration.current;
    setLoadState({ status: "loading" });
    if (resolvedProductId === undefined) {
      setLoadState({ status: "error" });
      return;
    }

    try {
      const result = await getAdminProduct({
        auth: accessToken,
        path: { product_id: resolvedProductId },
      });
      if (generation !== loadGeneration.current) {
        return;
      }
      if (result.data === undefined) {
        throw new Error();
      }
      setLoadState({
        // Stryker disable next-line StringLiteral: a validated response transitions this non-ready branch into the erased TypeScript ready discriminant.
        status: "ready",
        product: result.data,
        productId: resolvedProductId,
        accessToken,
      });
    } catch {
      if (generation === loadGeneration.current) {
        setLoadState({ status: "error" });
      }
    }
  }, [accessToken, resolvedProductId]);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) {
        void loadProduct();
      }
    });
    return () => {
      active = false;
      loadGeneration.current += 1;
    };
  }, [loadProduct]);

  useEffect(() => {
    if (deactivateError) {
      deactivateErrorRef.current!.focus();
    }
  }, [deactivateError]);

  function closeDeactivate(open: boolean) {
    if (deactivatePending) {
      return;
    }
    setDeactivateOpen(open);
    // Stryker disable next-line ConditionalExpression: this controlled dialog can request only closure after it has mounted open.
    if (!open) {
      setDeactivateError(false);
      queueMicrotask(() => deactivateTriggerRef.current!.focus());
    }
  }

  async function submitDeactivate(readyState: ReadyProductLoadState) {
    if (deactivatePendingRef.current) {
      return;
    }
    deactivatePendingRef.current = true;
    setDeactivatePending(true);
    setDeactivateError(false);
    try {
      const result = await deactivateAdminProduct({
        auth: accessToken,
        path: { product_id: readyState.productId },
      });
      if (result.data === undefined) {
        setDeactivateError(true);
        return;
      }
      setLoadState({
        // Stryker disable next-line StringLiteral: a validated response keeps this already-ready branch ready; the literal is the erased TypeScript discriminant.
        status: "ready",
        product: result.data,
        productId: readyState.productId,
        accessToken,
      });
      setDeactivateOpen(false);
    } catch {
      setDeactivateError(true);
    } finally {
      deactivatePendingRef.current = false;
      setDeactivatePending(false);
    }
  }

  if (
    loadState.status === "loading" ||
    (loadState.status === "ready" &&
      (loadState.productId !== resolvedProductId ||
        loadState.accessToken !== accessToken))
  ) {
    return (
      <section className="grid gap-4" role="status" aria-live="polite">
        <Skeleton className="h-9 w-64 max-w-full" />
        <Skeleton className="h-48 w-full" />
        <span>{t("Loading product overview")}</span>
      </section>
    );
  }

  if (loadState.status === "error") {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("Product unavailable")}</AlertTitle>
        <AlertDescription>
          <Button
            type="button"
            variant="outline"
            onClick={() => void loadProduct()}
          >
            {t("Retry loading page")}
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const product = loadState.product;

  return (
    <ProductDetailLayout
      productId={loadState.productId}
      productName={product.name}
    >
      <section
        className="grid min-w-0 max-w-full gap-8 overflow-x-clip"
        aria-label={t("Product overview")}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="grid min-w-0 gap-2">
            <Badge
              variant={product.is_active ? "success" : "warning"}
              className="w-fit rounded-md"
            >
              {product.is_active ? t("Active") : t("Inactive")}
            </Badge>
            {(product.active_revision ?? product.candidate_revision)
              ?.description ? (
              <p className="max-w-2xl text-muted-foreground [overflow-wrap:anywhere]">
                {
                  (product.active_revision ?? product.candidate_revision)
                    ?.description
                }
              </p>
            ) : null}
          </div>
          <div className="flex w-full flex-wrap gap-3 sm:w-auto">
            {product.active_revision !== null ||
            product.candidate_revision !== null ? (
              <Button asChild variant="outline" className="w-full sm:w-auto">
                <Link
                  to={`/admin/products/${encodeURIComponent(loadState.productId)}/edit`}
                >
                  {t("Configure product")}
                </Link>
              </Button>
            ) : null}
            {product.is_active ? (
              <Button
                ref={deactivateTriggerRef}
                type="button"
                variant="destructive"
                className="w-full sm:w-auto"
                onClick={() => setDeactivateOpen(true)}
              >
                {t("Deactivate product")}
              </Button>
            ) : null}
            <ProductDeleteDialog
              accessToken={accessToken}
              product={product}
              onDeleted={() => navigate("/admin/products", { replace: true })}
            />
          </div>
        </div>

        {product.affected_mapping_count > 0 ? (
          <section
            aria-label={t("Product freshness")}
            className="flex min-w-0 flex-wrap items-center gap-2"
          >
            <Badge
              variant="outline"
              className="border-warning text-warning rounded-md"
            >
              {product.affected_mapping_count}{" "}
              {product.affected_mapping_count === 1
                ? t("mapping may be stale")
                : t("mappings may be stale")}
            </Badge>
            <p className="min-w-0 text-sm text-muted-foreground [overflow-wrap:anywhere]">
              {t("Import failed. Showing the last successful import.")}
            </p>
          </section>
        ) : null}

        {product.is_active && product.candidate_revision !== null ? (
          <p className="text-sm text-muted-foreground">
            <Link
              className="font-medium text-primary underline underline-offset-4"
              to={`/admin/products/${encodeURIComponent(loadState.productId)}/edit`}
            >
              {t("Unpublished configuration changes")}
            </Link>
            {t(" — your current configuration is still active.")}
          </p>
        ) : null}

        <SourceFallbackSettings
          key={`source-${accessToken}-${loadState.productId}`}
          accessToken={accessToken}
          productId={loadState.productId}
        />
        <LocalizationSummary
          key={JSON.stringify([accessToken, loadState.productId])}
          accessToken={accessToken}
          productId={loadState.productId}
          isActive={product.is_active}
        />

        {deactivateOpen ? (
          <AlertDialog open onOpenChange={closeDeactivate}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>
                  {t("Deactivate ")}
                  {product.name}?
                </AlertDialogTitle>
                <AlertDialogDescription>
                  {t(
                    "Its mappings will stop operating, but its published configuration will be kept.",
                  )}
                </AlertDialogDescription>
              </AlertDialogHeader>

              {deactivateError ? (
                <Alert
                  ref={deactivateErrorRef}
                  tabIndex={-1}
                  variant="destructive"
                >
                  <AlertTitle>{t("Product not deactivated")}</AlertTitle>
                  <AlertDescription>
                    {t(
                      "We could not deactivate this product. Its active state is unchanged.",
                    )}
                  </AlertDescription>
                </Alert>
              ) : null}

              <AlertDialogFooter>
                <AlertDialogCancel disabled={deactivatePending}>
                  {t("Cancel")}
                </AlertDialogCancel>
                <Button
                  type="button"
                  variant="destructive"
                  disabled={deactivatePending}
                  aria-busy={deactivatePending}
                  onClick={() => void submitDeactivate(loadState)}
                >
                  {t("Deactivate product")}
                </Button>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        ) : null}
      </section>
    </ProductDetailLayout>
  );
}
