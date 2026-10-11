import { useEffect, useRef, useState } from "react";

import {
  deleteAdminProduct,
  type AdminProductResponse,
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
import { Button } from "../../../components/ui/button";

export interface ProductDeleteDialogProps {
  accessToken: string;
  product: AdminProductResponse;
  onDeleted: (productId: string) => void;
}

type DeleteError = "blocked" | "failed" | null;

export function ProductDeleteDialog({
  accessToken,
  product,
  onDeleted,
}: ProductDeleteDialogProps) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const pendingRef = useRef(false);
  const generationRef = useRef(0);
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<DeleteError>(null);

  useEffect(() => {
    return () => {
      generationRef.current += 1;
    };
  }, [accessToken, product.id]);

  useEffect(() => {
    if (error !== null) {
      errorRef.current?.focus();
    }
  }, [error]);

  function changeOpen(nextOpen: boolean) {
    if (pendingRef.current) {
      return;
    }
    setOpen(nextOpen);
    if (!nextOpen) {
      setError(null);
      queueMicrotask(() => triggerRef.current?.focus());
    }
  }

  async function submitDelete() {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    setError(null);
    const generation = ++generationRef.current;
    const productId = product.id;
    try {
      const result = await deleteAdminProduct({
        auth: accessToken,
        path: { product_id: productId },
      });
      if (generation !== generationRef.current) {
        return;
      }
      const responseStatus = result.response?.status;
      if (result.error === undefined && responseStatus === 204) {
        setOpen(false);
        onDeleted(productId);
        return;
      }
      setError(responseStatus === 409 ? "blocked" : "failed");
    } catch {
      if (generation === generationRef.current) {
        setError("failed");
      }
    } finally {
      if (generation === generationRef.current) {
        pendingRef.current = false;
        setPending(false);
      }
    }
  }

  return (
    <>
      <Button
        ref={triggerRef}
        type="button"
        variant="destructive"
        className="w-full sm:w-auto"
        onClick={() => setOpen(true)}
      >
        Delete product
      </Button>

      {open ? (
        <AlertDialog open onOpenChange={changeOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete {product.name}?</AlertDialogTitle>
              <AlertDialogDescription>
                VerboFlex will hide this product. Its retained data may be
                permanently removed under the configured maintenance policy.
                Bitbucket will not be changed. You can later reuse the
                product name, but the new product will have a different
                identity.
              </AlertDialogDescription>
            </AlertDialogHeader>

            {error !== null ? (
              <Alert ref={errorRef} tabIndex={-1} variant="destructive">
                <AlertTitle>
                  {error === "blocked"
                    ? "Product deletion is temporarily blocked"
                    : "Product not deleted"}
                </AlertTitle>
                <AlertDescription>
                  {error === "blocked"
                    ? "Wait for the running import or preview to finish, then try again."
                    : "We could not delete this product. It remains unchanged. Try again."}
                </AlertDescription>
              </Alert>
            ) : null}

            <AlertDialogFooter>
              <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
              <Button
                type="button"
                variant="destructive"
                disabled={pending}
                aria-busy={pending}
                onClick={() => void submitDelete()}
              >
                Delete product
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ) : null}
    </>
  );
}
