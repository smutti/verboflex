import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../../components/ui/select";
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
type ProductPageSize = 50 | 100;

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
  const loadGeneration = useRef(0);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  // Stryker disable next-line ArrayDeclaration: rows are hidden until the first generated response replaces this seed.
  const [products, setProducts] = useState<AdminProductResponse[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ProductStatusFilter>("all");
  const [pageSize, setPageSize] = useState<ProductPageSize>(50);
  // Stryker disable next-line BooleanLiteral: pagination is absent until the first response also normalizes this flag.
  const [loadingMore, setLoadingMore] = useState(false);

  const loadProducts = useCallback(
    async (
      cursor: string | null,
      append: boolean,
      status: ProductStatusFilter,
      limit: ProductPageSize,
    ) => {
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
            limit,
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
        if (generation === loadGeneration.current) {
          setLoadingMore(false);
        }
      }
    },
    [accessToken],
  );

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) {
        void loadProducts(null, false, statusFilter, pageSize);
      }
    });
    return () => {
      active = false;
      loadGeneration.current += 1;
    };
  }, [loadProducts, pageSize, statusFilter]);

  const collectionReady = loadState === "ready";

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
            to={collectionReady ? "/admin/products/new" : "."}
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
                void loadProducts(null, false, statusFilter, pageSize)
              }
            >
              Retry loading page
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {loadState === "ready" ? (
        <div className="grid min-w-0 max-w-full gap-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <label
                htmlFor="product-status-filter"
                className="text-sm font-medium"
              >
                Product status
              </label>
              <Select
                value={statusFilter}
                onValueChange={(value) =>
                  setStatusFilter(value as ProductStatusFilter)
                }
              >
                <SelectTrigger id="product-status-filter" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <label
                htmlFor="products-page-size"
                className="text-sm font-medium"
              >
                Products per page
              </label>
              <Select
                value={String(pageSize)}
                onValueChange={(value) =>
                  setPageSize(Number(value) as ProductPageSize)
                }
              >
                <SelectTrigger id="products-page-size" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {products.length === 0 ? (
            <section className="grid gap-2 rounded-lg border bg-secondary p-6">
              <h2 className="text-heading font-semibold">
                No products configured
              </h2>
              <p className="text-muted-foreground">
                Create a product to connect repositories and validate a
                localization layout.
              </p>
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
                    {products.map((product, index) => (
                      <TableRow key={index}>
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
                {products.map((product, index) => (
                  <article
                    key={index}
                    className="grid min-w-0 max-w-full gap-3 border-b pb-4"
                  >
                    <ProductFields product={product} />
                  </article>
                ))}
              </div>
            </>
          )}

          {nextCursor !== null ? (
            <Button
              type="button"
              variant="outline"
              className="justify-self-start"
              disabled={loadingMore}
              aria-busy={loadingMore}
              onClick={() =>
                void loadProducts(nextCursor, true, statusFilter, pageSize)
              }
            >
              Load more products
            </Button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
