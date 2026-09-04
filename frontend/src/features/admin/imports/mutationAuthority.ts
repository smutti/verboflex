export function hasLivePublishedAuthority(
  current: string,
  expected: string,
  ownsCurrentRequest: boolean,
) {
  // phase3-mutation:published-live-authority
  return current === expected && ownsCurrentRequest;
}

export function ownsPublishedRequestToken(
  current: symbol | undefined,
  expected: symbol,
) {
  // phase3-mutation:published-request-token-ownership
  return current === expected;
}

export function ownsLiveMutationController(
  current: AbortController | null,
  expected: AbortController,
) {
  // phase3-mutation:live-mutation-controller-ownership
  return current === expected && !expected.signal.aborted;
}

export function isLiveRewriteConfirmationRequest(
  liveIdentity: string,
  expectedIdentity: string,
  liveToken: symbol | undefined,
  expectedToken: symbol,
) {
  // phase3-mutation:rewrite-live-authority-request-token
  return liveIdentity === expectedIdentity && liveToken === expectedToken;
}

export function shouldClearUncommittedConfirmation(
  liveIdentity: string,
  expectedIdentity: string,
  ownsCurrentRequest: boolean,
  committed: boolean,
) {
  // phase3-mutation:rewrite-uncommitted-finalization
  return liveIdentity === expectedIdentity && ownsCurrentRequest && !committed;
}
