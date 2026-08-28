import type { ReactNode } from "react";
import { Link, Outlet, useLocation, useParams } from "react-router-dom";

import { cn } from "../../../lib/utils";

export interface ProductDetailLayoutProps {
  children?: ReactNode;
  productName?: string;
}

const PRODUCT_SECTIONS = [
  { label: "Overview", slug: "overview" },
  { label: "Repositories", slug: "repositories" },
  { label: "Mappings", slug: "mappings" },
  { label: "Preview", slug: "preview" },
] as const;

type ProductSection = (typeof PRODUCT_SECTIONS)[number]["slug"];

function resolveProductLocation(pathname: string, routeProductId?: string) {
  const pathSegments = pathname.split("/").filter(Boolean);
  const productsIndex = pathSegments.indexOf("products");
  const productId =
    routeProductId ??
    (productsIndex >= 0 ? pathSegments[productsIndex + 1] : undefined) ??
    "";
  const requestedSection = pathSegments.at(-1);
  const currentSection: ProductSection =
    PRODUCT_SECTIONS.find(({ slug }) => slug === requestedSection)?.slug ??
    "overview";

  return { currentSection, productId };
}

export function ProductDetailLayout({
  children,
  productName = "Product configuration",
}: ProductDetailLayoutProps) {
  const location = useLocation();
  const params = useParams();
  const { currentSection, productId } = resolveProductLocation(
    location.pathname,
    params.productId,
  );
  const productBase = `/admin/products/${encodeURIComponent(productId)}`;

  return (
    <section
      data-testid="product-detail-layout"
      className="grid min-w-0 max-w-full gap-8 overflow-x-clip"
      aria-labelledby="product-detail-title"
    >
      <h1
        id="product-detail-title"
        className="break-words text-display font-semibold [overflow-wrap:anywhere]"
      >
        {productName}
      </h1>
      <nav aria-label="Product configuration" className="min-w-0 max-w-full">
        <ul className="flex min-w-0 max-w-full flex-wrap gap-2 border-b">
          {PRODUCT_SECTIONS.map(({ label, slug }) => {
            const isCurrent = currentSection === slug;
            return (
              <li key={slug} className="min-w-0 max-w-full">
                <Link
                  to={`${productBase}/${slug}`}
                  aria-current={isCurrent ? "page" : undefined}
                  className={cn(
                    "block min-h-11 max-w-full border-b-2 border-transparent px-3 py-3 font-semibold text-foreground no-underline break-words [overflow-wrap:anywhere]",
                    isCurrent && "border-primary text-primary",
                  )}
                >
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="min-w-0 max-w-full">
        {children === undefined ? <Outlet /> : children}
      </div>
    </section>
  );
}
