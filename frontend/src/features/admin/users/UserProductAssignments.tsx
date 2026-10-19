import { useId } from "react";

import {
  listAdminProducts,
  listAdminUserProducts,
  type AdminUserProductAccess,
  type AdminUserProductChange,
  type AdminUserResponse,
} from "../../../api/client";
import { Button } from "../../../components/ui/button";
import { Label } from "../../../components/ui/label";
import { useCursorCollection } from "../useCursorCollection";

interface UserProductAssignmentsProps {
  accessToken: string;
  disabled: boolean;
  user: AdminUserResponse | null;
  value: AdminUserProductChange[];
  onChange: (value: AdminUserProductChange[]) => void;
}

export function UserProductAssignments({
  accessToken,
  disabled,
  user,
  value,
  onChange,
}: UserProductAssignmentsProps) {
  const id = useId();
  const products = useCursorCollection<AdminUserProductAccess>({
    queryKey: `${accessToken}:${user?.id ?? "new"}`,
    getItemId: (product) => product.product_id,
    loadPage: async (cursor, signal) => {
      if (user) {
        const result = await listAdminUserProducts({
          auth: accessToken,
          path: { user_id: user.id },
          query: { cursor, limit: 50 },
          signal,
        });
        if (!result.data) throw new Error("Product access unavailable");
        return result.data;
      }
      const result = await listAdminProducts({
        auth: accessToken,
        query: { cursor, limit: 50, status: "active" },
        signal,
      });
      if (!result.data) throw new Error("Products unavailable");
      return {
        ...result.data,
        items: result.data.items.map((product) => ({
          product_id: product.id,
          name: product.name,
          is_active: product.is_active,
          role: null,
          version: null,
        })),
      };
    },
  });

  function assign(product: AdminUserProductAccess, selected: string) {
    const productId = product.product_id;
    const role =
      selected === "none" ? null : (selected as AdminUserProductChange["role"]);
    const existing = value.find((item) => item.product_id === productId);
    const remaining = value.filter((item) => item.product_id !== productId);
    onChange(
      role === product.role
        ? remaining
        : [
            ...remaining,
            {
              product_id: productId,
              role,
              expected_version: existing
                ? existing.expected_version
                : product.version,
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
        {user
          ? "Manage this person's product roles. Choose No access to remove a membership. Changes apply when you save the user."
          : "Choose a role for each active product this person should access. You can also assign products later from their Team page."}
      </p>
      {user && !user.is_active && (
        <p className="text-sm text-muted-foreground">
          Reactivate this account before assigning or changing roles. You can
          still remove product access.
        </p>
      )}
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
          {user ? "No products available." : "No active products available."}
        </p>
      )}
      <div className="grid max-h-64 gap-3 overflow-y-auto">
        {products.items.map((product) => {
          const assignment = value.find(
            (item) => item.product_id === product.product_id,
          );
          return (
            <div key={product.product_id} className="grid min-w-0 gap-2">
              <Label
                htmlFor={`${id}-${product.product_id}`}
                className="[overflow-wrap:anywhere]"
              >
                {product.name}
                {!product.is_active && " (inactive)"}
              </Label>
              <select
                id={`${id}-${product.product_id}`}
                className="min-h-11 w-full min-w-0 rounded-md border bg-background px-3 text-sm"
                value={(assignment ? assignment.role : product.role) ?? "none"}
                disabled={!assignment && value.length >= 100}
                onChange={(event) => assign(product, event.target.value)}
              >
                <option value="none">No access</option>
                <option
                  value="viewer"
                  disabled={
                    user?.is_active === false && product.role !== "viewer"
                  }
                >
                  Viewer
                </option>
                <option
                  value="translator"
                  disabled={
                    user?.is_active === false && product.role !== "translator"
                  }
                >
                  Translator
                </option>
                <option
                  value="product_manager_reviewer"
                  disabled={
                    user?.is_active === false &&
                    product.role !== "product_manager_reviewer"
                  }
                >
                  Product manager / reviewer
                </option>
                <option
                  value="product_owner"
                  disabled={
                    user?.is_active === false &&
                    product.role !== "product_owner"
                  }
                >
                  Product Owner
                </option>
              </select>
            </div>
          );
        })}
      </div>
      {value.length >= 100 && (
        <p className="text-sm text-muted-foreground">
          {user
            ? "You can change up to 100 products in one save. Save these changes before editing more."
            : "You can assign up to 100 products when creating an account."}
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
