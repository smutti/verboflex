import type { TranslationOptionsResponse } from "../../api/client";

const TRANSLATION_PREFERENCE_VERSION = 2 as const;
const TRANSLATION_PREFERENCE_PREFIX = "verboflex.translation-search";

type TranslationPreferenceStorage = Pick<Storage, "getItem" | "setItem">;

export interface TranslationSearchPreferences {
  productId: string | null;
  language: string | null;
  viewMode?: "multilingual" | "bilingual";
  visibleLanguages?: string[] | null;
}

export function coherentTranslationSelection<
  T extends TranslationSearchPreferences,
>(
  preferences: T,
  availableLanguages: readonly string[],
  visibleLanguages: readonly string[] = preferences.visibleLanguages ?? [],
  baseLanguages: readonly string[] = [],
): T {
  if (preferences.viewMode !== "bilingual") return preferences;
  if (!preferences.language && baseLanguages.length === 0) return preferences;
  const available = new Set(availableLanguages);
  const bases = baseLanguages.filter((code) => available.has(code));
  const visible = visibleLanguages.filter((code) => available.has(code));
  const language =
    (preferences.language && available.has(preferences.language)
      ? preferences.language
      : null) ??
    visible.find((code) => !bases.includes(code)) ??
    availableLanguages.find((code) => !bases.includes(code)) ??
    bases[0] ??
    null;
  // Keep the focus and source before optional siblings when the selection is full.
  const required = [...new Set([...(language ? [language] : []), ...bases])];
  return {
    ...preferences,
    language,
    visibleLanguages: preferences.visibleLanguages
      ? [...new Set([...required, ...visible])].slice(0, 20).sort()
      : null,
  };
}

const ALL_TRANSLATIONS: TranslationSearchPreferences = {
  productId: null,
  language: null,
  viewMode: "multilingual",
  visibleLanguages: null,
};

function serializePreferences(
  preferences: TranslationSearchPreferences,
): string {
  return JSON.stringify({
    version: TRANSLATION_PREFERENCE_VERSION,
    productId: preferences.productId,
    language: preferences.language,
    viewMode: preferences.viewMode,
    visibleLanguages: preferences.visibleLanguages,
  });
}

function persistPreferences(
  storage: TranslationPreferenceStorage,
  principalId: string,
  preferences: TranslationSearchPreferences,
  productScope?: string,
): void {
  storage.setItem(
    translationPreferenceKey(principalId, productScope),
    serializePreferences(preferences),
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function authorizedChoice(
  value: unknown,
  authorizedValues: ReadonlySet<string>,
): string | null {
  return typeof value === "string" && authorizedValues.has(value)
    ? value
    : null;
}

export function translationPreferenceKey(
  principalId: string,
  productScope?: string,
): string {
  return `${TRANSLATION_PREFERENCE_PREFIX}.v${TRANSLATION_PREFERENCE_VERSION}.${encodeURIComponent(principalId)}${productScope ? `.product.${encodeURIComponent(productScope)}` : ""}`;
}

export function sanitizeTranslationPreferences(
  candidate: unknown,
  options: TranslationOptionsResponse,
): TranslationSearchPreferences {
  if (!isRecord(candidate)) {
    return { ...ALL_TRANSLATIONS };
  }

  const languages = new Set(options.languages.map(({ code }) => code));
  const visible = Array.isArray(candidate.visibleLanguages)
    ? [
        ...new Set(
          candidate.visibleLanguages.filter(
            (code): code is string =>
              typeof code === "string" && languages.has(code),
          ),
        ),
      ].sort()
    : [];
  return coherentTranslationSelection(
    {
      viewMode:
        candidate.viewMode === "bilingual" &&
        (!candidate.language || languages.has(String(candidate.language)))
          ? "bilingual"
          : "multilingual",
      visibleLanguages:
        visible.length > 0 && visible.length <= 20 ? visible : null,
      productId: authorizedChoice(
        candidate.productId,
        new Set(options.products.map(({ id }) => id)),
      ),
      language: authorizedChoice(
        candidate.language,
        new Set(options.languages.map(({ code }) => code)),
      ),
    },
    [...languages],
  );
}

export function loadTranslationPreferences(
  storage: TranslationPreferenceStorage,
  principalId: string,
  options: TranslationOptionsResponse,
  productScope?: string,
): TranslationSearchPreferences {
  const serialized =
    storage.getItem(translationPreferenceKey(principalId, productScope)) ??
    (!productScope
      ? storage.getItem(
          `${TRANSLATION_PREFERENCE_PREFIX}.v1.${encodeURIComponent(principalId)}`,
        )
      : null);
  if (serialized === null) {
    return { ...ALL_TRANSLATIONS };
  }

  let candidate: unknown;
  try {
    candidate = JSON.parse(serialized);
  } catch {
    return { ...ALL_TRANSLATIONS };
  }
  if (
    !isRecord(candidate) ||
    (candidate.version !== TRANSLATION_PREFERENCE_VERSION &&
      candidate.version !== 1)
  ) {
    return { ...ALL_TRANSLATIONS };
  }

  const preferences = sanitizeTranslationPreferences(candidate, options);
  persistPreferences(storage, principalId, preferences, productScope);
  return preferences;
}

export function saveTranslationPreferences(
  storage: TranslationPreferenceStorage,
  principalId: string,
  options: TranslationOptionsResponse,
  candidate: unknown,
  productScope?: string,
): TranslationSearchPreferences {
  const preferences = sanitizeTranslationPreferences(candidate, options);
  persistPreferences(storage, principalId, preferences, productScope);
  return preferences;
}
