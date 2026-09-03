import { describe, expect, it } from "vitest";

import {
  hasLivePublishedAuthority,
  isLiveRewriteConfirmationRequest,
  ownsPublishedRequestToken,
  shouldClearUncommittedConfirmation,
} from "./mutationAuthority";

describe("published import mutation authority predicates", () => {
  it("accepts only the live authority identity", () => {
    expect(hasLivePublishedAuthority("product-1", "product-1")).toBe(true);
    expect(hasLivePublishedAuthority("product-2", "product-1")).toBe(false);
  });

  it("accepts only the currently owned request token", () => {
    const ownedToken = Symbol("owned");

    expect(ownsPublishedRequestToken(ownedToken, ownedToken)).toBe(true);
    expect(ownsPublishedRequestToken(Symbol("obsolete"), ownedToken)).toBe(
      false,
    );
    expect(ownsPublishedRequestToken(undefined, ownedToken)).toBe(false);
  });
});

describe("rewrite confirmation authority predicates", () => {
  it("accepts only the matching live identity and request token", () => {
    const ownedToken = Symbol("owned");
    const obsoleteToken = Symbol("obsolete");

    expect(
      isLiveRewriteConfirmationRequest(
        "identity-1",
        "identity-1",
        ownedToken,
        ownedToken,
      ),
    ).toBe(true);
    expect(
      isLiveRewriteConfirmationRequest(
        "identity-2",
        "identity-1",
        ownedToken,
        ownedToken,
      ),
    ).toBe(false);
    expect(
      isLiveRewriteConfirmationRequest(
        "identity-1",
        "identity-1",
        obsoleteToken,
        ownedToken,
      ),
    ).toBe(false);
    expect(
      isLiveRewriteConfirmationRequest(
        "identity-2",
        "identity-1",
        obsoleteToken,
        ownedToken,
      ),
    ).toBe(false);
    expect(
      isLiveRewriteConfirmationRequest(
        "identity-1",
        "identity-1",
        undefined,
        ownedToken,
      ),
    ).toBe(false);
  });

  it("clears only a matching authority's uncommitted request", () => {
    expect(
      shouldClearUncommittedConfirmation("identity-1", "identity-1", false),
    ).toBe(true);
    expect(
      shouldClearUncommittedConfirmation("identity-1", "identity-1", true),
    ).toBe(false);
    expect(
      shouldClearUncommittedConfirmation("identity-2", "identity-1", false),
    ).toBe(false);
    expect(
      shouldClearUncommittedConfirmation("identity-2", "identity-1", true),
    ).toBe(false);
  });
});
