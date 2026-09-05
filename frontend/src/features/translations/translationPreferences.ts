import type { TranslationOptionsResponse } from "../../api/client";

const TRANSLATION_PREFERENCE_VERSION = 1 as const;
const TRANSLATION_PREFERENCE_PREFIX = "verboflex.translation-search";

type TranslationPreferenceStorage = Pick<Storage, "getItem" | "setItem">;

export interface TranslationSearchPreferences {
  productId: string | null;
  language: string | null;
}

const ALL_TRANSLATIONS: TranslationSearchPreferences = {
  productId: null,
  language: null,
};

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

export function translationPreferenceKey(principalId: string): string {
  return `${TRANSLATION_PREFERENCE_PREFIX}.v${TRANSLATION_PREFERENCE_VERSION}.${encodeURIComponent(principalId)}`;
}

export function sanitizeTranslationPreferences(
  candidate: unknown,
  options: TranslationOptionsResponse,
): TranslationSearchPreferences {
  if (!isRecord(candidate)) {
    return { ...ALL_TRANSLATIONS };
  }

  return {
    productId: authorizedChoice(
      candidate.productId,
      new Set(options.products.map(({ id }) => id)),
    ),
    language: authorizedChoice(
      candidate.language,
      new Set(options.languages.map(({ code }) => code)),
    ),
  };
}

export function loadTranslationPreferences(
  storage: TranslationPreferenceStorage,
  principalId: string,
  options: TranslationOptionsResponse,
): TranslationSearchPreferences {
  const serialized = storage.getItem(translationPreferenceKey(principalId));
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
    candidate.version !== TRANSLATION_PREFERENCE_VERSION
  ) {
    return { ...ALL_TRANSLATIONS };
  }

  const preferences = sanitizeTranslationPreferences(candidate, options);
  storage.setItem(
    translationPreferenceKey(principalId),
    JSON.stringify({
      version: TRANSLATION_PREFERENCE_VERSION,
      productId: preferences.productId,
      language: preferences.language,
    }),
  );
  return preferences;
}

export function saveTranslationPreferences(
  storage: TranslationPreferenceStorage,
  principalId: string,
  options: TranslationOptionsResponse,
  candidate: unknown,
): TranslationSearchPreferences {
  const preferences = sanitizeTranslationPreferences(candidate, options);
  storage.setItem(
    translationPreferenceKey(principalId),
    JSON.stringify({
      version: TRANSLATION_PREFERENCE_VERSION,
      productId: preferences.productId,
      language: preferences.language,
    }),
  );
  return preferences;
}
