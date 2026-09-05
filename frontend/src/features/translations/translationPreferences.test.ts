import { beforeEach, describe, expect, it } from "vitest";

import type { TranslationOptionsResponse } from "../../api/client";
import {
  loadTranslationPreferences,
  saveTranslationPreferences,
  sanitizeTranslationPreferences,
  translationPreferenceKey,
} from "./translationPreferences";

const options: TranslationOptionsResponse = {
  products: [
    { id: "product-alpha", name: "Alpha" },
    { id: "product-beta", name: "Beta" },
  ],
  languages: [
    { code: "en-US", label: "English" },
    { code: "it-IT", label: "Italian" },
  ],
};

describe("translation search preferences", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("round-trips authorized product and language choices for one principal", () => {
    saveTranslationPreferences(localStorage, "principal-a", options, {
      productId: "product-alpha",
      language: "it-IT",
    });

    expect(
      loadTranslationPreferences(localStorage, "principal-a", options),
    ).toEqual({ productId: "product-alpha", language: "it-IT" });
    expect(
      JSON.parse(
        localStorage.getItem(translationPreferenceKey("principal-a")) ?? "{}",
      ),
    ).toEqual({ version: 1, productId: "product-alpha", language: "it-IT" });
  });

  it("keeps explicit All products and All languages as null values", () => {
    saveTranslationPreferences(localStorage, "principal-a", options, {
      productId: null,
      language: null,
    });

    expect(
      loadTranslationPreferences(localStorage, "principal-a", options),
    ).toEqual({ productId: null, language: null });
  });

  it("isolates preferences between authenticated principals", () => {
    saveTranslationPreferences(localStorage, "principal-a", options, {
      productId: "product-alpha",
      language: "en-US",
    });
    saveTranslationPreferences(localStorage, "principal-b", options, {
      productId: "product-beta",
      language: "it-IT",
    });

    expect(
      loadTranslationPreferences(localStorage, "principal-a", options),
    ).toEqual({ productId: "product-alpha", language: "en-US" });
    expect(
      loadTranslationPreferences(localStorage, "principal-b", options),
    ).toEqual({ productId: "product-beta", language: "it-IT" });
    expect(translationPreferenceKey("principal-a")).not.toBe(
      translationPreferenceKey("principal-b"),
    );
  });

  it.each([
    ["missing", null],
    ["malformed", "{definitely-not-json"],
    [
      "unknown version",
      JSON.stringify({
        version: 2,
        productId: "product-alpha",
        language: "it-IT",
      }),
    ],
    [
      "wrong shape",
      JSON.stringify({ version: 1, productId: 42, language: ["it-IT"] }),
    ],
  ])("returns explicit All values for %s storage", (_case, storedValue) => {
    if (storedValue !== null) {
      localStorage.setItem(
        translationPreferenceKey("principal-a"),
        storedValue,
      );
    }

    expect(
      loadTranslationPreferences(localStorage, "principal-a", options),
    ).toEqual({ productId: null, language: null });
  });

  it("clears choices that are no longer in the live authorized options", () => {
    localStorage.setItem(
      translationPreferenceKey("principal-a"),
      JSON.stringify({
        version: 1,
        productId: "removed-product",
        language: "removed-language",
      }),
    );

    expect(
      loadTranslationPreferences(localStorage, "principal-a", options),
    ).toEqual({ productId: null, language: null });
    expect(
      JSON.parse(
        localStorage.getItem(translationPreferenceKey("principal-a")) ?? "{}",
      ),
    ).toEqual({ version: 1, productId: null, language: null });
  });

  it("sanitizes each choice independently against current authority", () => {
    expect(
      sanitizeTranslationPreferences(
        { productId: "product-alpha", language: "removed-language" },
        options,
      ),
    ).toEqual({ productId: "product-alpha", language: null });
    expect(
      sanitizeTranslationPreferences(
        { productId: "removed-product", language: "it-IT" },
        options,
      ),
    ).toEqual({ productId: null, language: "it-IT" });
  });

  it("serializes only version, productId, and language", () => {
    saveTranslationPreferences(localStorage, "principal-a", options, {
      productId: "product-alpha",
      language: "it-IT",
      query: "secret translation text",
      rawKey: "repository.key",
      sourceText: "source content",
      translatedText: "translated content",
      path: "locales/it.json",
      commit: "deadbeef",
      cursor: "opaque-cursor",
      roles: ["admin"],
      token: "bearer-secret",
      state: "approved",
      violation: "over_limit",
      deleted: "all",
      constraint: { maximum: 12 },
    });

    const serialized =
      localStorage.getItem(translationPreferenceKey("principal-a")) ?? "";
    expect(Object.keys(JSON.parse(serialized))).toEqual([
      "version",
      "productId",
      "language",
    ]);
    for (const forbidden of [
      "secret translation text",
      "repository.key",
      "source content",
      "translated content",
      "locales/it.json",
      "deadbeef",
      "opaque-cursor",
      "admin",
      "bearer-secret",
      "approved",
      "over_limit",
      "maximum",
    ]) {
      expect(serialized).not.toContain(forbidden);
    }
  });
});
