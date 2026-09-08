import { useCallback, useEffect, useRef, useState } from "react";
import { PackageOpen, Search } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import {
  listAdminProducts,
  type AdminProductResponse,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Skeleton } from "../../../components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";

export interface ProductsPageProps {
  accessToken: string;
}

type LoadState = "loading" | "ready" | "error";
type ProductStatusFilter = "all" | "active" | "inactive";

const PRODUCT_PAGE_SIZE = 50;
const SEARCH_DEBOUNCE_MS = 300;

function normalizeSearch(value: string) {
  const normalized = value.trim().replace(/\s+/g, " ");
  return normalized.length > 0 ? normalized : null;
}

function ProductStatus({ product }: { product: AdminProductResponse }) {
  return (
    <Badge variant="outline" className="rounded-md">
      {product.is_active ? "Active" : "Inactive"}
    </Badge>
  );
}

function revisionLabel(product: AdminProductResponse) {
  if (product.active_revision !== null) {
    return `Published version ${product.active_revision.version}`;
  }
  return "Not published";
}

function candidateLabel(product: AdminProductResponse) {
  if (product.candidate_revision !== null) {
    return `Draft version ${product.candidate_revision.version}`;
  }
  return "No draft";
}

function ProductFields({ product }: { product: AdminProductResponse }) {
  return (
    <>
      <div className="grid min-w-0 gap-1">
        <Link
          className="font-semibold break-words [overflow-wrap:anywhere]"
          to={`/admin/products/${encodeURIComponent(product.id)}/overview`}
        >
          {product.name}
        </Link>
        <span className="text-muted-foreground">{revisionLabel(product)}</span>
      </div>
      <span className="break-words text-muted-foreground [overflow-wrap:anywhere]">
        {candidateLabel(product)}
      </span>
      <ProductStatus product={product} />
    </>
  );
}

export function ProductsPage({ accessToken }: ProductsPageProps) {
  const currentLocation = useLocation();
  const loadGeneration = useRef(0);
  const loadMoreTriggerRef = useRef<HTMLDivElement | null>(null);
  // Stryker disable next-line BooleanLiteral: append controls are absent until the first response, whose finally block resets this internal gate.
  const loadingMoreRef = useRef(false);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  // Stryker disable next-line ArrayDeclaration: rows are hidden until the first generated response replaces this seed.
  const [products, setProducts] = useState<AdminProductResponse[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ProductStatusFilter>("all");
  const [searchInput, setSearchInput] = useState("");
  const [nameFilter, setNameFilter] = useState<string | null>(null);
  // Stryker disable next-line BooleanLiteral: pagination is absent until the first response also normalizes this flag.
  const [loadingMore, setLoadingMore] = useState(false);

  const loadProducts = useCallback(
    async (
      cursor: string | null,
      append: boolean,
      status: ProductStatusFilter,
      name: string | null,
    ) => {
      if (append && loadingMoreRef.current) {
        return;
      }
      loadingMoreRef.current = append;
      const generation = ++loadGeneration.current;
      if (append) {
        setLoadingMore(true);
      } else {
        setLoadState("loading");
      }

      try {
        const result = await listAdminProducts({
          auth: accessToken,
          query: {
            cursor,
            limit: PRODUCT_PAGE_SIZE,
            name,
            status: status === "all" ? null : status,
          },
        });
        if (generation !== loadGeneration.current) {
          return;
        }
        if (result.data === undefined) {
          throw new Error();
        }
        setProducts((current) =>
          append ? [...current, ...result.data.items] : result.data.items,
        );
        setNextCursor(result.data.next_cursor);
        setLoadState("ready");
      } catch {
        if (generation === loadGeneration.current) {
          setLoadState("error");
        }
      } finally {
        // Stryker disable next-line ConditionalExpression: a stale finally can only reset append-only state while the replacement collection request hides pagination.
        if (generation === loadGeneration.current) {
          loadingMoreRef.current = false;
          setLoadingMore(false);
        }
      }
    },
    [accessToken],
  );

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setNameFilter(normalizeSearch(searchInput));
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timeout);
  }, [searchInput]);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) {
        void loadProducts(null, false, statusFilter, nameFilter);
      }
    });
    return () => {
      active = false;
      loadGeneration.current += 1;
    };
  }, [loadProducts, nameFilter, statusFilter]);

  const collectionReady = loadState === "ready";
  const filtersActive = statusFilter !== "all" || nameFilter !== null;

  useEffect(() => {
    const target = loadMoreTriggerRef.current;
    if (
      loadState !== "ready" ||
      target === null ||
      nextCursor === null ||
      loadingMore
    ) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          void loadProducts(nextCursor, true, statusFilter, nameFilter);
        }
      },
      { rootMargin: "320px 0px" },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [
    loadProducts,
    loadState,
    loadingMore,
    nameFilter,
    nextCursor,
    statusFilter,
  ]);

  return (
    <section
      className="grid min-w-0 max-w-full gap-8 overflow-x-clip"
      aria-labelledby="admin-products-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid min-w-0 gap-2">
          <h1 id="admin-products-title" className="text-display font-semibold">
            Products
          </h1>
          <p className="text-muted-foreground">
            Manage published product configuration and candidate drafts.
          </p>
        </div>
        <Button asChild className="w-full sm:w-auto">
          <Link
            to={collectionReady ? "/admin/products/new" : currentLocation}
            aria-disabled={!collectionReady}
            tabIndex={collectionReady ? undefined : -1}
          >
            Create product
          </Link>
        </Button>
      </div>

      {loadState === "loading" ? (
        <div className="grid gap-4" role="status" aria-live="polite">
          <Skeleton className="h-9 w-64 max-w-full" />
          <Skeleton className="h-48 w-full" />
          <span>Loading products</span>
        </div>
      ) : null}

      {loadState === "error" ? (
        <Alert variant="destructive">
          <AlertTitle>Products unavailable</AlertTitle>
          <AlertDescription>
            <p>
              We could not load this page. Retry without leaving the
              administration area.
            </p>
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                void loadProducts(null, false, statusFilter, nameFilter)
              }
            >
              Retry loading page
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {loadState === "ready" ? (
        <div className="grid min-w-0 max-w-full gap-6">
          <div className="grid items-end gap-4 lg:grid-cols-[minmax(16rem,1fr)_auto]">
            <div className="grid gap-2">
              <label
                htmlFor="product-name-filter"
                className="text-sm font-medium"
              >
                Search by product name
              </label>
              <div className="relative">
                <Search
                  aria-hidden="true"
                  className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
                />
                <Input
                  id="product-name-filter"
                  aria-label="Search products"
                  className="pl-9"
                  placeholder="Search products…"
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                />
              </div>
            </div>
            <div
              className="flex flex-wrap gap-2"
              role="group"
              aria-label="Product status"
            >
              {(["all", "active", "inactive"] as const).map((status) => (
                <Button
                  key={status}
                  type="button"
                  size="sm"
                  variant={statusFilter === status ? "default" : "outline"}
                  className="rounded-full px-4"
                  aria-pressed={statusFilter === status}
                  onClick={() => setStatusFilter(status)}
                >
                  {status === "all"
                    ? "All"
                    : status === "active"
                      ? "Active"
                      : "Inactive"}
                </Button>
              ))}
            </div>
          </div>

          {products.length === 0 ? (
            <section className="grid min-h-[42vh] place-items-center rounded-xl border border-dashed bg-secondary/40 p-8 text-center">
              <div className="grid max-w-md justify-items-center gap-4">
                <span className="bg-background text-muted-foreground grid size-16 place-items-center rounded-full border shadow-sm">
                  <PackageOpen
                    data-testid="products-empty-icon"
                    aria-hidden="true"
                    className="size-8"
                  />
                </span>
                <div className="grid gap-2">
                  <h2 className="text-heading font-semibold">
                    {filtersActive
                      ? "No products found"
                      : "No products configured"}
                  </h2>
                  <p className="text-muted-foreground">
                    {filtersActive
                      ? "Try a different name or status filter."
                      : "Create a product to connect repositories and validate a localization layout."}
                  </p>
                </div>
                {!filtersActive ? (
                  <Button asChild>
                    <Link to="/admin/products/new">
                      Create your first product
                    </Link>
                  </Button>
                ) : null}
              </div>
            </section>
          ) : (
            <>
              <div className="hidden min-w-0 md:block">
                <Table aria-label="Products">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Product</TableHead>
                      <TableHead>Candidate</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {products.map((product) => (
                      <TableRow key={product.id}>
                        <TableCell className="min-w-0 whitespace-normal">
                          <div className="grid min-w-0 gap-1">
                            <Link
                              className="font-semibold break-words [overflow-wrap:anywhere]"
                              to={`/admin/products/${encodeURIComponent(product.id)}/overview`}
                            >
                              {product.name}
                            </Link>
                            <span className="text-muted-foreground">
                              {revisionLabel(product)}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="whitespace-normal">
                          {candidateLabel(product)}
                        </TableCell>
                        <TableCell>
                          <ProductStatus product={product} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <div
                className="grid min-w-0 max-w-full gap-4 md:hidden"
                aria-label="Products mobile list"
              >
                {products.map((product) => (
                  <article
                    key={product.id}
                    className="grid min-w-0 max-w-full gap-3 border-b pb-4"
                  >
                    <ProductFields product={product} />
                  </article>
                ))}
              </div>
            </>
          )}

          {nextCursor !== null ? (
            <div
              ref={loadMoreTriggerRef}
              className="grid min-h-16 place-items-center"
              aria-hidden={!loadingMore}
            >
              {loadingMore ? (
                <div
                  role="status"
                  aria-live="polite"
                  className="flex items-center gap-3 text-sm text-muted-foreground"
                >
                  <span className="border-primary size-5 animate-spin rounded-full border-2 border-r-transparent" />
                  Loading more products
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
