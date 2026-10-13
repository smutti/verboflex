import { principalForProduct } from "../auth/productRoles";
import {
  GitPullRequest,
  Languages,
  PackageOpen,
  RefreshCw,
  Users,
} from "lucide-react";
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { Link, Outlet, useLocation, useParams } from "react-router-dom";

import {
  listProductWorkspaces,
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

function useAuthorizedProducts(accessToken: string, productId: string) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{
    token: string;
    productId: string;
    attempt: number;
    load: ProductLoad;
  }>({ token: accessToken, productId, attempt, load: { status: "loading" } });
  const load =
    result.token === accessToken &&
    result.productId === productId &&
    result.attempt === attempt
      ? result.load
      : ({ status: "loading" } satisfies ProductLoad);

  useEffect(() => {
    const controller = new AbortController();
    void listProductWorkspaces({
      query: { product_id: productId },
      auth: accessToken,
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.data) throw new Error("Products unavailable");
        setResult({
          token: accessToken,
          productId,
          attempt,
          load: { status: "ready", products: result.data.items },
        });
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setResult({
            token: accessToken,
            productId,
            attempt,
            load: { status: "error" },
          });
      });
    return () => controller.abort();
  }, [accessToken, attempt, productId]);

  return { load, retry: () => setAttempt((value) => value + 1) };
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

export { ProductWorkspaceIndex } from "./ProductWorkspaceIndex";

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
  const location = useLocation();
  const rawProductId = useParams<"productId">().productId ?? "";
  let productId = rawProductId;
  try {
    productId = decodeURIComponent(rawProductId);
  } catch {
    // A malformed route cannot match an authorized product.
  }
  const { load, retry } = useAuthorizedProducts(accessToken, productId);

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
  const changesPath = `/products/${encodeURIComponent(product.id)}/change-sets`;
  const teamPath = `/products/${encodeURIComponent(product.id)}/team`;
  const changesActive = location.pathname.startsWith(changesPath);
  const teamActive =
    location.pathname === teamPath ||
    location.pathname.startsWith(`${teamPath}/`);
  const tabClass =
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 font-semibold no-underline";
  const activeStyle = { backgroundColor: identity.accent, color: "#ffffff" };
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
          className="mt-(--space-lg) flex flex-wrap items-center gap-2"
        >
          <Link
            to={stringsPath}
            aria-current={changesActive || teamActive ? undefined : "page"}
            className={tabClass}
            style={changesActive || teamActive ? undefined : activeStyle}
          >
            <Languages className="size-4 shrink-0" aria-hidden="true" />
            Strings
          </Link>
          <Link
            to={changesPath}
            aria-current={changesActive ? "page" : undefined}
            className={tabClass}
            style={changesActive ? activeStyle : undefined}
          >
            <GitPullRequest className="size-4 shrink-0" aria-hidden="true" />
            Change sets
          </Link>
          {(principal.roles.includes("admin") ||
            principal.managed_product_ids?.includes(product.id)) && (
            <Link
              to={teamPath}
              aria-current={teamActive ? "page" : undefined}
              className={tabClass}
              style={teamActive ? activeStyle : undefined}
            >
              <Users className="size-4 shrink-0" aria-hidden="true" />
              Team
            </Link>
          )}
        </nav>
      </header>
      {changesActive || teamActive ? (
        <Outlet />
      ) : (
        <TranslationsWorkspace
          accessToken={accessToken}
          principal={principalForProduct(principal, product.id)}
          lockedProduct={product}
          detailsBasePath={stringsPath}
          searchPath={stringsPath}
        />
      )}
    </div>
  );
}
