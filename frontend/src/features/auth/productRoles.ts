import type { CurrentUserResponse, RoleName } from "../../api/client";

export function rolesForProduct(
  principal: {
    roles: readonly RoleName[];
    product_roles?: CurrentUserResponse["product_roles"];
  },
  productId: string | null | undefined,
): RoleName[] {
  if (principal.roles.includes("admin")) return ["admin"];
  // Older sessions need a fresh /me response; the API always enforces current membership.
  if (principal.product_roles === undefined) return [...principal.roles];
  return productId ? (principal.product_roles[productId] ?? []) : [];
}

export function principalForProduct(
  principal: CurrentUserResponse,
  productId: string,
): CurrentUserResponse {
  return { ...principal, roles: rolesForProduct(principal, productId) };
}
