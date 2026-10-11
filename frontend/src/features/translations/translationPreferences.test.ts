import { beforeEach, describe, expect, it } from "vitest";

import type { TranslationOptionsResponse } from "../../api/client";
import {
  loadTranslationPreferences,
  saveTranslationPreferences,
  sanitizeTranslationPreferences,
  translationPreferenceKey,
  coherentTranslationSelection,
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
  it("repairs restored bilingual focus omitted from the saved selection", () => {
    const result = sanitizeTranslationPreferences(
      {
        productId: "product-alpha",
        language: "it-IT",
        viewMode: "bilingual",
        visibleLanguages: ["en-US"],
      },
      options,
    );
    expect(result.visibleLanguages).toEqual(["en-US", "it-IT"]);
  });
  it("reserves source and focus within twenty slots even outside server defaults", () => {
    const visible = Array.from({ length: 20 }, (_, i) => `l${i}`);
    const result = coherentTranslationSelection(
      {
        productId: null,
        language: "it",
        viewMode: "bilingual",
        visibleLanguages: visible,
      },
      [...visible, "en", "it"],
      visible,
      ["en"],
    );
    expect(result.visibleLanguages).toHaveLength(20);
    expect(result.visibleLanguages).toEqual(
      expect.arrayContaining(["en", "it"]),
    );
  });
  it("isolates accepted product workspace settings from global and other product choices", () => {
    saveTranslationPreferences(
      localStorage,
      "principal-a",
      options,
      {
        productId: "product-alpha",
        language: "it-IT",
        viewMode: "bilingual",
        visibleLanguages: ["it-IT"],
      },
      "product-alpha",
    );
    expect(
      loadTranslationPreferences(
        localStorage,
        "principal-a",
        options,
        "product-alpha",
      ),
    ).toMatchObject({ viewMode: "bilingual", visibleLanguages: ["it-IT"] });
    expect(
      loadTranslationPreferences(localStorage, "principal-a", options),
    ).toMatchObject({ productId: null, viewMode: "multilingual" });
    expect(
      loadTranslationPreferences(
        localStorage,
        "principal-a",
        options,
        "product-beta",
      ),
    ).toMatchObject({ productId: null, viewMode: "multilingual" });
  });
  it("keeps accepted mode and bounded authorized visible languages separate from focus", () => {
    saveTranslationPreferences(localStorage, "principal-a", options, {
      productId: "product-alpha",
      language: "it-IT",
      viewMode: "bilingual",
      visibleLanguages: ["en-US", "it-IT", "en-US", "removed"],
    });
    expect(
      loadTranslationPreferences(localStorage, "principal-a", options),
    ).toMatchObject({
      language: "it-IT",
      viewMode: "bilingual",
      visibleLanguages: ["en-US", "it-IT"],
    });
    expect(
      loadTranslationPreferences(localStorage, "principal-b", options),
    ).toMatchObject({ viewMode: "multilingual", visibleLanguages: null });
  });
  it("migrates the old preference key without carrying cached content", () => {
    localStorage.setItem(
      "verboflex.translation-search.v1.principal-a",
      JSON.stringify({
        version: 1,
        productId: "product-alpha",
        language: "it-IT",
        pages: ["private"],
      }),
    );
    expect(
      loadTranslationPreferences(localStorage, "principal-a", options),
    ).toMatchObject({
      productId: "product-alpha",
      language: "it-IT",
      viewMode: "multilingual",
      visibleLanguages: null,
    });
  });
  it("rejects over-limit selection instead of silently hiding requested rows", () => {
    const large = {
      ...options,
      languages: Array.from({ length: 21 }, (_, i) => ({
        code: "l" + i,
        label: "Language " + i,
      })),
    };
    expect(
      sanitizeTranslationPreferences(
        {
          viewMode: "wrong",
          visibleLanguages: large.languages.map((l) => l.code),
        },
        large,
      ),
    ).toMatchObject({ viewMode: "multilingual", visibleLanguages: null });
  });
  it.each([null, [], "foreign", 12])(
    "rejects non-record preference input %j",
    (candidate) => {
      expect(sanitizeTranslationPreferences(candidate, options)).toEqual({
        viewMode: "multilingual",
        visibleLanguages: null,
        productId: null,
        language: null,
      });
    },
  );
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
    ).toEqual({
      viewMode: "multilingual",
      visibleLanguages: null,
      productId: "product-alpha",
      language: "it-IT",
    });
    expect(
      JSON.parse(
        localStorage.getItem(translationPreferenceKey("principal-a")) ?? "{}",
      ),
    ).toEqual({
      viewMode: "multilingual",
      visibleLanguages: null,
      version: 2,
      productId: "product-alpha",
      language: "it-IT",
    });
  });

  it("keeps explicit All products and All languages as null values", () => {
    saveTranslationPreferences(localStorage, "principal-a", options, {
      productId: null,
      language: null,
    });

    expect(
      loadTranslationPreferences(localStorage, "principal-a", options),
    ).toEqual({
      viewMode: "multilingual",
      visibleLanguages: null,
      productId: null,
      language: null,
    });
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
    ).toEqual({
      viewMode: "multilingual",
      visibleLanguages: null,
      productId: "product-alpha",
      language: "en-US",
    });
    expect(
      loadTranslationPreferences(localStorage, "principal-b", options),
    ).toEqual({
      viewMode: "multilingual",
      visibleLanguages: null,
      productId: "product-beta",
      language: "it-IT",
    });
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
        version: 99,
        productId: "product-alpha",
        language: "it-IT",
      }),
    ],
    [
      "wrong shape",
      JSON.stringify({ version: 2, productId: 42, language: ["it-IT"] }),
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
    ).toEqual({
      viewMode: "multilingual",
      visibleLanguages: null,
      productId: null,
      language: null,
    });
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
    ).toEqual({
      viewMode: "multilingual",
      visibleLanguages: null,
      productId: null,
      language: null,
    });
    expect(
      JSON.parse(
        localStorage.getItem(translationPreferenceKey("principal-a")) ?? "{}",
      ),
    ).toEqual({
      viewMode: "multilingual",
      visibleLanguages: null,
      version: 2,
      productId: null,
      language: null,
    });
  });

  it("sanitizes each choice independently against current authority", () => {
    expect(
      sanitizeTranslationPreferences(
        { productId: "product-alpha", language: "removed-language" },
        options,
      ),
    ).toEqual({
      viewMode: "multilingual",
      visibleLanguages: null,
      productId: "product-alpha",
      language: null,
    });
    expect(
      sanitizeTranslationPreferences(
        { productId: "removed-product", language: "it-IT" },
        options,
      ),
    ).toEqual({
      viewMode: "multilingual",
      visibleLanguages: null,
      productId: null,
      language: "it-IT",
    });
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
      "viewMode",
      "visibleLanguages",
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
