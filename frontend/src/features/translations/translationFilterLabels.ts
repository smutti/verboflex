export const translationFilterLabels = {
  workStatus: {
    needs_translation: "Needs translation",
    needs_review: "Needs review",
    source_changed: "Source changed",
  },
  state: { draft: "Draft", approved: "Approved", rejected: "Rejected" },
  violation: {
    over_limit: "Over limit",
    within_limit: "Within limit",
    no_max: "No max length",
  },
  deleted: {
    active: "Active only",
    deleted: "Deleted only",
    all: "Active and deleted",
  },
} as const;
