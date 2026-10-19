import { t } from "@/i18n";
import type { RoleName } from "../../../api/client";

export const USER_ROLE_OPTIONS: ReadonlyArray<{
  label: string;
  value: RoleName;
}> = [
  {
    value: "admin",
    get label() {
      return t("Administrator");
    },
  },
  {
    value: "product_manager_reviewer",
    get label() {
      return t("Product manager / reviewer");
    },
  },
  {
    value: "translator",
    get label() {
      return t("Translator");
    },
  },
  {
    value: "viewer",
    get label() {
      return t("Viewer");
    },
  },
];

export const CREATE_DEFAULT_ROLES: RoleName[] = ["viewer"];
