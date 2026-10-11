import {
  ArrowRight,
  Languages,
  PackageOpen,
  Search,
  RefreshCw,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  listProductWorkspaces,
  type ProductWorkspaceCard,
  type ProductWorkspacePage,
} from "../../api/client";
import { Alert, AlertTitle } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Skeleton } from "../../components/ui/skeleton";
import { productIdentity } from "./productIdentity";

const numbers = new Intl.NumberFormat("en");
const languageNames = new Intl.DisplayNames(["en"], { type: "language" });
function languageName(code: string) {
  try {
    return languageNames.of(code) ?? code;
  } catch {
    return code;
  }
}

function ProductCard({ product }: { product: ProductWorkspaceCard }) {
  const identity = productIdentity(product.id, product.name);
  const coverage = product.coverage;
  return (
    <Link
      to={`/products/${encodeURIComponent(product.id)}/strings`}
      aria-label={`Open ${product.name} workspace`}
      className="group relative flex min-w-0 flex-col gap-5 overflow-hidden rounded-xl border bg-card p-6 text-foreground shadow-xs transition-[border-color,box-shadow] hover:border-slate-400 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-4 motion-reduce:transition-none"
    >
      <span
        className="absolute inset-x-0 top-0 h-1"
        style={{ background: identity.accent }}
        aria-hidden="true"
      />
      <div className="flex min-w-0 items-start gap-3">
        <span
          className="grid size-11 shrink-0 place-items-center rounded-lg"
          style={{ background: identity.soft, color: identity.ink }}
        >
          <PackageOpen className="size-5" aria-hidden="true" />
        </span>
        <h2 className="min-h-12 min-w-0 flex-1 text-[18px] leading-snug font-semibold wrap-anywhere">
          {product.name}
        </h2>
        <ArrowRight
          className="mt-1 size-5 shrink-0 text-muted-foreground group-hover:text-primary"
          aria-hidden="true"
        />
      </div>
      {coverage ? (
        <>
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-label text-muted-foreground">
                Source strings
              </dt>
              <dd className="mt-1 text-[24px] font-semibold tabular-nums">
                {numbers.format(coverage.source_string_count)}
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-1 text-label text-muted-foreground">
                <Languages className="size-3.5" aria-hidden="true" />
                Languages
              </dt>
              <dd className="mt-1 text-[24px] font-semibold tabular-nums">
                {numbers.format(coverage.language_count)}
              </dd>
            </div>
          </dl>
          <div
            className="flex min-h-6 flex-wrap gap-1.5"
            aria-label="Supported languages"
          >
            {coverage.languages.map((code) => (
              <span
                key={code}
                title={languageName(code)}
                className="rounded-md border bg-slate-50 px-2 py-0.5 text-label font-medium text-slate-600"
              >
                {code}
              </span>
            ))}
            {coverage.language_count > coverage.languages.length && (
              <span
                className="px-1 py-0.5 text-label text-muted-foreground"
                title="More supported languages"
              >
                +{coverage.language_count - coverage.languages.length}
              </span>
            )}
          </div>
          <div className="mt-auto border-t pt-4">
            {coverage.coverage_percent !== null ? (
              <>
                <div className="mb-2 flex items-baseline justify-between gap-2">
                  <span
                    className="font-semibold tabular-nums"
                    style={{ color: identity.ink }}
                  >
                    {numbers.format(coverage.coverage_percent)}%{" "}
                    <span className="font-normal text-muted-foreground">
                      translated
                    </span>
                  </span>
                  <span className="text-label text-muted-foreground tabular-nums">
                    {numbers.format(coverage.translated_count)} /{" "}
                    {numbers.format(coverage.expected_translation_count)}
                  </span>
                </div>
                <div
                  className="h-2 overflow-hidden rounded-full bg-slate-100"
                  role="progressbar"
                  aria-label={`${product.name} translated`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={coverage.coverage_percent}
                >
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${coverage.coverage_percent}%`,
                      background: identity.accent,
                    }}
                  />
                </div>
                <p className="mt-2 text-label text-muted-foreground">
                  {coverage.missing_count
                    ? `${numbers.format(coverage.missing_count)} missing`
                    : "All translations complete"}
                </p>
              </>
            ) : (
              <p className="text-label text-muted-foreground">
                {coverage.source_string_count
                  ? "No target translations imported"
                  : "No source strings imported"}
              </p>
            )}
          </div>
        </>
      ) : (
        <div className="flex min-h-40 flex-1 items-center justify-center rounded-lg bg-slate-50 text-muted-foreground">
          {product.imported_scope_count
            ? "Statistics unavailable"
            : "Not imported yet"}
        </div>
      )}
      {product.unimported_scope_count > 0 &&
        product.imported_scope_count > 0 && (
          <p className="text-label font-medium text-amber-800">
            Partial import
          </p>
        )}
    </Link>
  );
}

export function ProductWorkspaceIndex({
  accessToken,
}: {
  accessToken: string;
}) {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [attempt, setAttempt] = useState(0);
  const identity = JSON.stringify([accessToken, query, page, attempt]);
  const [result, setResult] = useState<{
    identity: string;
    data?: ProductWorkspacePage;
    error?: boolean;
  } | null>(null);
  const data = result?.identity === identity ? result.data : undefined;
  const error = result?.identity === identity && result.error;
  useEffect(() => {
    if (input.trim() === query) return;
    const timer = window.setTimeout(() => {
      setQuery(input.trim());
      setPage(1);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [input, query]);
  useEffect(() => {
    const controller = new AbortController();
    void listProductWorkspaces({
      auth: accessToken,
      signal: controller.signal,
      query: { q: query, page },
    })
      .then((response) => {
        if (controller.signal.aborted) return;
        if (!response.data) throw new Error("Products unavailable");
        setResult({ identity, data: response.data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ identity, error: true });
      });
    return () => controller.abort();
  }, [accessToken, query, page, identity]);
  const clear = () => {
    setInput("");
    setQuery("");
    setPage(1);
  };
  return (
    <div className="grid min-w-0 gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-display font-semibold">Products</h1>
          <p
            className="mt-2 text-label text-muted-foreground"
            title="Based on the latest repository import. Local pending proposals are excluded."
          >
            Repository coverage
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => setAttempt((value) => value + 1)}
          aria-label="Refresh products"
        >
          <RefreshCw className="size-4" aria-hidden="true" />
          Refresh
        </Button>
      </header>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative w-full sm:max-w-md">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            aria-label="Search products"
            placeholder="Search products…"
            maxLength={120}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            className="min-h-[44px] bg-card pr-10 pl-10"
          />
          {input && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-0 right-0 size-11"
              aria-label="Clear product search"
              onClick={clear}
            >
              <X className="size-4" />
            </Button>
          )}
        </div>
        <p role="status" className="text-label text-muted-foreground">
          {data
            ? `${numbers.format(data.total)} ${data.total === 1 ? "product" : "products"}`
            : error
              ? ""
              : "Loading products…"}
        </p>
      </div>
      {error ? (
        <Alert>
          <AlertTitle>Products could not be loaded</AlertTitle>
          <Button
            className="mt-3"
            variant="outline"
            onClick={() => setAttempt((value) => value + 1)}
          >
            Retry loading products
          </Button>
        </Alert>
      ) : !data ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-72 rounded-xl" />
          ))}
        </div>
      ) : data.items.length === 0 ? (
        <div className="grid justify-items-center gap-3 rounded-xl border border-dashed bg-card px-6 py-12 text-center">
          <PackageOpen
            className="size-8 text-muted-foreground"
            aria-hidden="true"
          />
          <h2 className="text-heading font-semibold">
            {query ? "No products found" : "No products available"}
          </h2>
          {query && (
            <Button variant="outline" onClick={clear}>
              Clear search
            </Button>
          )}
          {page > 1 && (
            <Button variant="outline" onClick={() => setPage(1)}>
              First page
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {data.items.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}
      {data && (page > 1 || data.has_more) && (
        <nav
          aria-label="Product pages"
          className="flex items-center justify-center gap-4"
        >
          <Button
            variant="outline"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-label text-muted-foreground">Page {page}</span>
          <Button
            variant="outline"
            disabled={!data.has_more}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </nav>
      )}
    </div>
  );
}
