import type { RoleName } from "../../api/client";

export const ROLE_LABELS: Record<RoleName, string> = {
  admin: "Administrator",
  product_manager_reviewer: "Product manager / reviewer",
  translator: "Translator",
  viewer: "Viewer",
};
