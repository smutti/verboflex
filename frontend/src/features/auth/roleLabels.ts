import { t } from "@/i18n";
import type { RoleName } from "../../api/client";

export const ROLE_LABELS: Record<RoleName, string> = {
  get admin() {
    return t("Administrator");
  },
  get product_manager_reviewer() {
    return t("Product manager / reviewer");
  },
  get translator() {
    return t("Translator");
  },
  get viewer() {
    return t("Viewer");
  },
};
