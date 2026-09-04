import { describe, expect, it } from "vitest";

import {
  hasLivePublishedAuthority,
  isLiveRewriteConfirmationRequest,
  ownsLiveMutationController,
  ownsPublishedRequestToken,
  shouldClearUncommittedConfirmation,
} from "./mutationAuthority";

describe("published import mutation authority predicates", () => {
  it("accepts only the live authority identity", () => {
    expect(hasLivePublishedAuthority("product-1", "product-1", true)).toBe(
      true,
    );
    expect(hasLivePublishedAuthority("product-1", "product-1", false)).toBe(
      false,
    );
    expect(hasLivePublishedAuthority("product-2", "product-1", true)).toBe(
      false,
    );
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

describe("shared mutation controller authority", () => {
  it("accepts only the exact live non-aborted controller", () => {
    const ownedController = new AbortController();

    expect(ownsLiveMutationController(ownedController, ownedController)).toBe(
      true,
    );
    expect(
      ownsLiveMutationController(new AbortController(), ownedController),
    ).toBe(false);
    expect(ownsLiveMutationController(null, ownedController)).toBe(false);
    ownedController.abort();
    expect(ownsLiveMutationController(ownedController, ownedController)).toBe(
      false,
    );
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
      shouldClearUncommittedConfirmation(
        "identity-1",
        "identity-1",
        true,
        false,
      ),
    ).toBe(true);
    expect(
      shouldClearUncommittedConfirmation(
        "identity-1",
        "identity-1",
        true,
        true,
      ),
    ).toBe(false);
    expect(
      shouldClearUncommittedConfirmation(
        "identity-2",
        "identity-1",
        true,
        false,
      ),
    ).toBe(false);
    expect(
      shouldClearUncommittedConfirmation(
        "identity-1",
        "identity-1",
        false,
        false,
      ),
    ).toBe(false);
    expect(
      shouldClearUncommittedConfirmation(
        "identity-2",
        "identity-1",
        false,
        true,
      ),
    ).toBe(false);
  });
});
