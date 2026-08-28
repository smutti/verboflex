import type { RoleName } from "../../../api/client";

export const USER_ROLE_OPTIONS: ReadonlyArray<{
  label: string;
  value: RoleName;
}> = [
  { value: "admin", label: "Administrator" },
  {
    value: "product_manager_reviewer",
    label: "Product manager / reviewer",
  },
  { value: "translator", label: "Translator" },
  { value: "viewer", label: "Viewer" },
];

export const CREATE_DEFAULT_ROLES: RoleName[] = ["viewer"];
