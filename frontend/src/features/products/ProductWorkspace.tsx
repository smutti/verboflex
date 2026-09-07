import { ArrowRight, Languages, PackageOpen, RefreshCw } from "lucide-react";
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import {
  listTranslationOptions,
  type CurrentUserResponse,
  type TranslationProductOptionResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Skeleton } from "../../components/ui/skeleton";
import { TranslationsWorkspace } from "../translations/TranslationsWorkspace";
import { productIdentity } from "./productIdentity";

type ProductLoad =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; products: TranslationProductOptionResponse[] };

function useAuthorizedProducts(accessToken: string) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{
    token: string;
    attempt: number;
    load: ProductLoad;
  }>({ token: accessToken, attempt, load: { status: "loading" } });
  const load =
    result.token === accessToken && result.attempt === attempt
      ? result.load
      : ({ status: "loading" } satisfies ProductLoad);

  useEffect(() => {
    const controller = new AbortController();
    void listTranslationOptions({
      auth: accessToken,
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.data) throw new Error("Products unavailable");
        setResult({
          token: accessToken,
          attempt,
          load: { status: "ready", products: result.data.products },
        });
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setResult({
            token: accessToken,
            attempt,
            load: { status: "error" },
          });
      });
    return () => controller.abort();
  }, [accessToken, attempt]);

  return { load, retry: () => setAttempt((value) => value + 1) };
}

function LoadingProducts() {
  return (
    <div className="grid gap-(--space-md) md:grid-cols-2" role="status">
      <span className="sr-only">Loading products</span>
      {Array.from({ length: 4 }, (_, index) => (
        <Skeleton key={index} className="h-40 w-full rounded-lg" />
      ))}
    </div>
  );
}

function ProductError({ retry }: { retry: () => void }) {
  return (
    <Alert>
      <AlertTitle>Products could not be loaded</AlertTitle>
      <AlertDescription className="space-y-(--space-md)">
        <p>Retry without leaving your workspace.</p>
        <Button type="button" variant="outline" onClick={retry}>
          <RefreshCw aria-hidden="true" />
          Retry loading products
        </Button>
      </AlertDescription>
    </Alert>
  );
}

function identityStyle(productId: string, productName: string) {
  const identity = productIdentity(productId, productName);
  return {
    identity,
    style: {
      "--product-accent": identity.accent,
      "--product-soft": identity.soft,
      "--product-ink": identity.ink,
    } as CSSProperties,
  };
}

export function ProductWorkspaceIndex({
  accessToken,
}: {
  accessToken: string;
}) {
  const { load, retry } = useAuthorizedProducts(accessToken);

  return (
    <div className="grid min-w-0 gap-(--space-xl)">
      <header className="space-y-(--space-sm)">
        <p className="text-label font-semibold tracking-[0.16em] text-primary uppercase">
          Product workspace
        </p>
        <h1 className="text-display font-semibold">Choose a product</h1>
        <p className="max-w-3xl text-muted-foreground">
          Enter a dedicated workspace to search and work on one product without
          losing context.
        </p>
      </header>
      {load.status === "loading" ? (
        <LoadingProducts />
      ) : load.status === "error" ? (
        <ProductError retry={retry} />
      ) : load.products.length === 0 ? (
        <div className="rounded-lg border bg-secondary p-(--space-lg)">
          <h2 className="text-heading font-semibold">No products available</h2>
          <p className="mt-(--space-sm) text-muted-foreground">
            There are no active products available to your account yet.
          </p>
        </div>
      ) : (
        <div className="grid gap-(--space-md) md:grid-cols-2 xl:grid-cols-3">
          {load.products.map((product) => {
            const { identity, style } = identityStyle(product.id, product.name);
            return (
              <Link
                key={product.id}
                to={`/products/${encodeURIComponent(product.id)}/strings`}
                aria-label={`Open ${product.name} workspace`}
                className="group relative min-h-44 overflow-hidden rounded-lg border bg-secondary p-(--space-lg) text-foreground shadow-sm transition-[transform,box-shadow,border-color] hover:-translate-y-1 hover:shadow-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 motion-reduce:transform-none motion-reduce:transition-none"
                style={{ ...style, borderColor: identity.accent }}
              >
                <span
                  className="absolute inset-x-0 top-0 h-2"
                  style={{ backgroundColor: identity.accent }}
                  aria-hidden="true"
                />
                <span className="flex items-start justify-between gap-(--space-md)">
                  <span
                    className="grid size-14 shrink-0 place-items-center rounded-lg text-heading font-semibold"
                    style={{
                      backgroundColor: identity.soft,
                      color: identity.ink,
                    }}
                    aria-hidden="true"
                  >
                    {identity.initials}
                  </span>
                  <ArrowRight
                    aria-hidden="true"
                    className="transition-transform group-hover:translate-x-1 motion-reduce:transition-none"
                    style={{ color: identity.accent }}
                  />
                </span>
                <span className="mt-(--space-lg) block text-heading font-semibold wrap-anywhere">
                  {product.name}
                </span>
                <span className="mt-(--space-xs) block text-muted-foreground">
                  Open strings workspace
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

function FocusUnavailable({ children }: { children: ReactNode }) {
  return (
    <div className="grid gap-(--space-lg)">
      {children}
      <Button asChild variant="outline" className="w-fit">
        <Link to="/products">Choose another product</Link>
      </Button>
    </div>
  );
}

export function ProductFocusWorkspace({
  accessToken,
  principal,
}: {
  accessToken: string;
  principal: CurrentUserResponse;
}) {
  const rawProductId = useParams<"productId">().productId ?? "";
  let productId = rawProductId;
  try {
    productId = decodeURIComponent(rawProductId);
  } catch {
    // A malformed route cannot match an authorized product.
  }
  const { load, retry } = useAuthorizedProducts(accessToken);

  if (load.status === "loading") {
    return (
      <div className="grid gap-(--space-md)" role="status">
        <span>Loading product workspace</span>
        <Skeleton className="h-52 w-full rounded-lg" />
        <Skeleton className="h-80 w-full rounded-lg" />
      </div>
    );
  }
  if (load.status === "error") return <ProductError retry={retry} />;

  const product = load.products.find((candidate) => candidate.id === productId);
  if (!product) {
    return (
      <FocusUnavailable>
        <Alert>
          <AlertTitle>Product workspace unavailable</AlertTitle>
          <AlertDescription>
            This product is inactive or outside your authorized products.
          </AlertDescription>
        </Alert>
      </FocusUnavailable>
    );
  }

  const { identity, style } = identityStyle(product.id, product.name);
  const stringsPath = `/products/${encodeURIComponent(product.id)}/strings`;
  return (
    <div
      data-testid="product-focus"
      data-product-id={product.id}
      className="grid min-w-0 gap-(--space-xl)"
      style={style}
    >
      <header
        className="relative overflow-hidden rounded-lg border p-(--space-lg) shadow-sm md:p-(--space-xl)"
        style={{
          background: `linear-gradient(125deg, ${identity.soft} 0%, #ffffff 72%)`,
          borderColor: identity.accent,
          borderLeftWidth: 8,
        }}
      >
        <div className="flex flex-col gap-(--space-lg) sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-(--space-md)">
            <span
              className="grid size-16 shrink-0 place-items-center rounded-lg text-heading font-semibold shadow-sm"
              style={{ backgroundColor: identity.accent, color: "#ffffff" }}
              aria-hidden="true"
            >
              {identity.initials}
            </span>
            <div className="min-w-0">
              <p
                className="text-label font-semibold tracking-[0.16em] uppercase"
                style={{ color: identity.ink }}
              >
                Product in focus
              </p>
              <h1 className="mt-(--space-xs) text-display font-semibold wrap-anywhere">
                {product.name}
              </h1>
              <p className="mt-(--space-xs) text-muted-foreground">
                Every search and action below stays within this product.
              </p>
            </div>
          </div>
          <Button asChild variant="outline" className="shrink-0 bg-white/80">
            <Link to="/products">
              <PackageOpen aria-hidden="true" />
              Change product
            </Link>
          </Button>
        </div>
        <nav
          aria-label={`${product.name} workspace`}
          className="mt-(--space-lg)"
        >
          <Link
            to={stringsPath}
            aria-current="page"
            className="inline-flex min-h-[44px] items-center gap-(--space-sm) rounded-md px-(--space-md) font-semibold no-underline"
            style={{ backgroundColor: identity.accent, color: "#ffffff" }}
          >
            <Languages aria-hidden="true" />
            Strings
          </Link>
        </nav>
      </header>
      <TranslationsWorkspace
        accessToken={accessToken}
        principal={principal}
        lockedProduct={product}
        detailsBasePath={stringsPath}
        searchPath={stringsPath}
      />
    </div>
  );
}
