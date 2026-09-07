import { describe, expect, it } from "vitest";

import { productIdentity } from "./productIdentity";

describe("productIdentity", () => {
  it("keeps the visual identity stable across product renames", () => {
    const before = productIdentity("product-123", "Before");
    const after = productIdentity("product-123", "After");

    expect({
      accent: before.accent,
      soft: before.soft,
      ink: before.ink,
    }).toEqual({ accent: after.accent, soft: after.soft, ink: after.ink });
  });

  it("returns a complete accessible palette and initials", () => {
    const identity = productIdentity("product-alpha", "Alpha Mobile");

    expect(identity.initials).toBe("AM");
    expect(identity.accent).toMatch(/^#[0-9a-f]{6}$/);
    expect(identity.soft).toMatch(/^#[0-9a-f]{6}$/);
    expect(identity.ink).toMatch(/^#[0-9a-f]{6}$/);
  });
});
