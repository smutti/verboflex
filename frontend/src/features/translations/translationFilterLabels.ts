export const translationFilterLabels = {
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
