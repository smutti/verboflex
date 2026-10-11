interface SubmissionEntry {
  principalId: string;
  accessToken: string;
  productId: string;
  translationGroupId: string;
  expectedVersion: number;
}
let pending: SubmissionEntry | undefined;

/** Only call after the dirty-editor guard permits navigation. Memory only. */
export function setSubmissionEntry(entry: SubmissionEntry) {
  pending = entry;
}

export function consumeSubmissionEntry(
  scope: Pick<SubmissionEntry, "principalId" | "accessToken" | "productId">,
) {
  const entry = peekSubmissionEntry(scope);
  pending = undefined;
  return entry;
}
export function peekSubmissionEntry(
  scope: Pick<SubmissionEntry, "principalId" | "accessToken" | "productId">,
) {
  const entry = pending;
  return entry &&
    entry.principalId === scope.principalId &&
    entry.accessToken === scope.accessToken &&
    entry.productId === scope.productId
    ? entry
    : undefined;
}
