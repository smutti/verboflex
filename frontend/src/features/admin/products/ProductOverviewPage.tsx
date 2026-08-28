import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import {
  deactivateAdminProduct,
  getAdminProduct,
  type AdminProductResponse,
  type AdminProductRevisionSummary,
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
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../../components/ui/tabs";
import { ProductDetailLayout } from "./ProductDetailLayout";

export interface ProductOverviewPageProps {
  accessToken: string;
  productId?: string;
}

type ProductLoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; product: AdminProductResponse; productId: string };

function RevisionSummary({
  label,
  revision,
}: {
  label: string;
  revision: AdminProductRevisionSummary | null;
}) {
  return (
    <section
      aria-label={label}
      className="grid gap-3 rounded-lg border bg-secondary p-6"
    >
      <h2 className="text-heading font-semibold">{label}</h2>
      {revision === null ? (
        <p className="text-muted-foreground">Not configured</p>
      ) : (
        <>
          <Badge variant="outline" className="w-fit rounded-md">
            Version {revision.version}
          </Badge>
          <p className="break-words [overflow-wrap:anywhere]">
            {revision.description ?? "No description"}
          </p>
        </>
      )}
    </section>
  );
}

export function ProductOverviewPage({
  accessToken,
  productId,
}: ProductOverviewPageProps) {
  const routeProductId = useParams<"productId">().productId;
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
        status: "ready",
        product: result.data,
        productId: resolvedProductId,
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
    if (!open) {
      setDeactivateError(false);
      queueMicrotask(() => deactivateTriggerRef.current!.focus());
    }
  }

  async function submitDeactivate() {
    if (deactivatePendingRef.current || loadState.status !== "ready") {
      return;
    }
    deactivatePendingRef.current = true;
    setDeactivatePending(true);
    setDeactivateError(false);
    try {
      const result = await deactivateAdminProduct({
        auth: accessToken,
        path: { product_id: loadState.productId },
      });
      if (result.data === undefined) {
        setDeactivateError(true);
        return;
      }
      setLoadState({
        status: "ready",
        product: result.data,
        productId: loadState.productId,
      });
      setDeactivateOpen(false);
    } catch {
      setDeactivateError(true);
    } finally {
      deactivatePendingRef.current = false;
      setDeactivatePending(false);
    }
  }

  if (loadState.status === "loading") {
    return (
      <section className="grid gap-4" role="status" aria-live="polite">
        <Skeleton className="h-9 w-64 max-w-full" />
        <Skeleton className="h-48 w-full" />
        <span>Loading product overview</span>
      </section>
    );
  }

  if (loadState.status !== "ready") {
    return (
      <Alert variant="destructive">
        <AlertTitle>Product unavailable</AlertTitle>
        <AlertDescription>
          <p>
            We could not load this page. Retry without leaving the
            administration area.
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={() => void loadProduct()}
          >
            Retry loading page
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
        aria-label="Product overview"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="grid min-w-0 gap-2">
            <span className="text-heading font-semibold">Lifecycle status</span>
            <Badge variant="outline" className="w-fit rounded-md">
              {product.is_active ? "Active" : "Inactive"}
            </Badge>
          </div>
          {product.is_active ? (
            <Button
              ref={deactivateTriggerRef}
              type="button"
              variant="destructive"
              className="w-full sm:w-auto"
              onClick={() => setDeactivateOpen(true)}
            >
              Deactivate product
            </Button>
          ) : null}
        </div>

        {product.is_active && product.candidate_revision !== null ? (
          <Alert>
            <AlertTitle>Draft in progress</AlertTitle>
            <AlertDescription>
              Published configuration remains active while you edit this draft.
            </AlertDescription>
          </Alert>
        ) : null}

        <Tabs defaultValue="published" className="min-w-0 max-w-full">
          <TabsList aria-label="Configuration revisions">
            <TabsTrigger value="published">Published</TabsTrigger>
            <TabsTrigger value="draft">Draft</TabsTrigger>
          </TabsList>
          <TabsContent value="published" forceMount>
            <RevisionSummary
              label="Published configuration"
              revision={product.active_revision}
            />
          </TabsContent>
          <TabsContent value="draft" forceMount>
            <RevisionSummary
              label="Draft configuration"
              revision={product.candidate_revision}
            />
          </TabsContent>
        </Tabs>

        {deactivateOpen ? (
          <AlertDialog open onOpenChange={closeDeactivate}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Deactivate {product.name}?</AlertDialogTitle>
                <AlertDialogDescription>
                  Its mappings will stop operating, but its published
                  configuration will be kept.
                </AlertDialogDescription>
              </AlertDialogHeader>

              {deactivateError ? (
                <Alert
                  ref={deactivateErrorRef}
                  tabIndex={-1}
                  variant="destructive"
                >
                  <AlertTitle>Product not deactivated</AlertTitle>
                  <AlertDescription>
                    We could not deactivate this product. Its active state is
                    unchanged.
                  </AlertDescription>
                </Alert>
              ) : null}

              <AlertDialogFooter>
                <AlertDialogCancel disabled={deactivatePending}>
                  Cancel
                </AlertDialogCancel>
                <Button
                  type="button"
                  variant="destructive"
                  disabled={deactivatePending}
                  aria-busy={deactivatePending}
                  onClick={() => void submitDeactivate()}
                >
                  Deactivate product
                </Button>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        ) : null}
      </section>
    </ProductDetailLayout>
  );
}
