export function hasLivePublishedAuthority(current: string, expected: string) {
  // phase3-mutation:published-live-authority
  return current === expected;
}

export function ownsPublishedRequestToken(
  current: symbol | undefined,
  expected: symbol,
) {
  // phase3-mutation:published-request-token-ownership
  return current === expected;
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
  committed: boolean,
) {
  // phase3-mutation:rewrite-uncommitted-finalization
  return liveIdentity === expectedIdentity && !committed;
}
