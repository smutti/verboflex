import { t, useUiLanguage } from "@/i18n";
import type { ReactNode } from "react";
import { Link, Outlet, useLocation, useParams } from "react-router-dom";

import { cn } from "../../../lib/utils";

export interface ProductDetailLayoutProps {
  children?: ReactNode;
  hideTitle?: boolean;
  productId?: string;
  productName?: string;
}

const PRODUCT_SECTIONS = [
  {
    get label() {
      return t("Overview");
    },
    slug: "overview",
  },
  {
    get label() {
      return t("Team");
    },
    slug: "team",
  },
  {
    get label() {
      return t("Repositories");
    },
    slug: "repositories",
  },
  {
    get label() {
      return t("Translation sources");
    },
    slug: "mappings",
  },
  {
    get label() {
      return t("Approval branches");
    },
    slug: "branches",
  },
  {
    get label() {
      return t("Preview and import");
    },
    slug: "preview",
  },
] as const;

type ProductSection = (typeof PRODUCT_SECTIONS)[number]["slug"];

function resolveProductSection(pathname: string): ProductSection {
  const pathSegments = pathname.split("/").filter(Boolean);
  const requestedSection = pathSegments.at(-1);
  return (
    PRODUCT_SECTIONS.find(({ slug }) => slug === requestedSection)?.slug ??
    "overview"
  );
}

export function ProductDetailLayout({
  children,
  hideTitle = false,
  productId: productIdProp,
  productName = t("Product configuration"),
}: ProductDetailLayoutProps) {
  useUiLanguage();
  const location = useLocation();
  const routeProductId = useParams<"productId">().productId;
  const productId = productIdProp ?? routeProductId ?? "";
  const currentSection = resolveProductSection(location.pathname);
  const productBase = `/admin/products/${encodeURIComponent(productId)}`;

  return (
    <section
      data-testid="product-detail-layout"
      className="grid min-w-0 max-w-full gap-8 overflow-x-clip"
      aria-label={hideTitle ? t("Product configuration") : undefined}
      aria-labelledby={hideTitle ? undefined : "product-detail-title"}
    >
      {hideTitle ? null : (
        <h1
          id="product-detail-title"
          className="break-words text-display font-semibold [overflow-wrap:anywhere]"
        >
          {productName}
        </h1>
      )}
      <nav
        aria-label={t("Product configuration")}
        className="min-w-0 max-w-full"
      >
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
