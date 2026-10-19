import { useId } from "react";

import {
  listAdminProducts,
  type AdminProductResponse,
  type AdminUserProductAssignment,
} from "../../../api/client";
import { Button } from "../../../components/ui/button";
import { Label } from "../../../components/ui/label";
import { useCursorCollection } from "../useCursorCollection";

interface UserProductAssignmentsProps {
  accessToken: string;
  disabled: boolean;
  value: AdminUserProductAssignment[];
  onChange: (value: AdminUserProductAssignment[]) => void;
}

export function UserProductAssignments({
  accessToken,
  disabled,
  value,
  onChange,
}: UserProductAssignmentsProps) {
  const id = useId();
  const products = useCursorCollection<AdminProductResponse>({
    queryKey: accessToken,
    getItemId: (product) => product.id,
    loadPage: async (cursor, signal) => {
      const result = await listAdminProducts({
        auth: accessToken,
        query: { cursor, limit: 50, status: "active" },
        signal,
      });
      if (!result.data) throw new Error("Products unavailable");
      return result.data;
    },
  });

  function assign(productId: string, role: string) {
    const remaining = value.filter((item) => item.product_id !== productId);
    onChange(
      role === "none"
        ? remaining
        : [
            ...remaining,
            {
              product_id: productId,
              role: role as AdminUserProductAssignment["role"],
            },
          ],
    );
  }

  return (
    <fieldset
      disabled={disabled}
      className="grid min-w-0 gap-3 rounded-lg border p-4"
    >
      <legend className="px-1 text-sm font-medium">Product access</legend>
      <p className="text-sm text-muted-foreground">
        Choose a role for each active product this person should access. You can
        also assign products later from their Team page.
      </p>
      {products.status === "loading" && <p role="status">Loading products…</p>}
      {products.status === "error" && (
        <div className="grid justify-items-start gap-2">
          <p role="alert">
            Products unavailable. Retry to assign product access.
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={() => void products.reload()}
          >
            Retry loading products
          </Button>
        </div>
      )}
      {products.isEmpty && (
        <p className="text-sm text-muted-foreground">
          No active products available.
        </p>
      )}
      <div className="grid max-h-64 gap-3 overflow-y-auto">
        {products.items.map((product) => {
          const assignment = value.find(
            (item) => item.product_id === product.id,
          );
          return (
            <div key={product.id} className="grid min-w-0 gap-2">
              <Label
                htmlFor={`${id}-${product.id}`}
                className="break-words [overflow-wrap:anywhere]"
              >
                {product.name}
              </Label>
              <select
                id={`${id}-${product.id}`}
                className="min-h-11 w-full min-w-0 rounded-md border bg-background px-3 text-sm"
                value={assignment?.role ?? "none"}
                disabled={!assignment && value.length >= 100}
                onChange={(event) => assign(product.id, event.target.value)}
              >
                <option value="none">No access</option>
                <option value="viewer">Viewer</option>
                <option value="translator">Translator</option>
                <option value="product_manager_reviewer">
                  Product manager / reviewer
                </option>
                <option value="product_owner">Product Owner</option>
              </select>
            </div>
          );
        })}
      </div>
      {value.length >= 100 && (
        <p className="text-sm text-muted-foreground">
          You can assign up to 100 products when creating an account.
        </p>
      )}
      {products.loadMoreError && (
        <p role="alert">
          More products could not be loaded. Your selections are still here.
        </p>
      )}
      {products.isPartial && (
        <Button
          type="button"
          variant="outline"
          disabled={products.loadingMore}
          onClick={() => void products.loadMore()}
        >
          {products.loadMoreError
            ? "Retry loading more products"
            : "Load more products"}
        </Button>
      )}
    </fieldset>
  );
}
