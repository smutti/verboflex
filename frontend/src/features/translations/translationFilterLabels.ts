import { t } from "@/i18n";
export const translationFilterLabels = {
  workStatus: {
    get needs_translation() {
      return t("Needs translation");
    },
    get needs_review() {
      return t("Needs review");
    },
    get source_changed() {
      return t("Source changed");
    },
  },
  state: {
    get draft() {
      return t("Draft");
    },
    get approved() {
      return t("Approved");
    },
    get rejected() {
      return t("Rejected");
    },
  },
  violation: {
    get over_limit() {
      return t("Over limit");
    },
    get within_limit() {
      return t("Within limit");
    },
    get no_max() {
      return t("No max length");
    },
  },
  deleted: {
    get active() {
      return t("Active only");
    },
    get deleted() {
      return t("Deleted only");
    },
    get all() {
      return t("Active and deleted");
    },
  },
} as const;
