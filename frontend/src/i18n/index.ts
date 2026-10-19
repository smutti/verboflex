import { useSyncExternalStore } from "react";
import { createInstance } from "i18next";
import en from "./locales/en.json";
import it from "./locales/it.json";
import de from "./locales/de.json";
import es from "./locales/es.json";
import fr from "./locales/fr.json";
import nl from "./locales/nl.json";

export const UI_LANGUAGES = [
  { code: "it", name: "Italiano", flag: "🇮🇹" },
  { code: "en", name: "English", flag: "🇬🇧" },
  { code: "de", name: "Deutsch", flag: "🇩🇪" },
  { code: "es", name: "Español", flag: "🇪🇸" },
  { code: "fr", name: "Français", flag: "🇫🇷" },
  { code: "nl", name: "Nederlands", flag: "🇳🇱" },
] as const;
export type UiLanguage = (typeof UI_LANGUAGES)[number]["code"];
export const UI_LANGUAGE_STORAGE_KEY = "verboflex.ui-language";
const i18n = createInstance();
void i18n.init({
  lng: "en",
  fallbackLng: "en",
  supportedLngs: UI_LANGUAGES.map(({ code }) => code),
  resources: Object.fromEntries(
    Object.entries({ en, it, de, es, fr, nl }).map(
      ([language, translation]) => [language, { translation }],
    ),
  ),
  initAsync: false,
  keySeparator: false,
  nsSeparator: false,
  interpolation: { escapeValue: false }, // React escapes text; never render these as HTML.
});

export function isUiLanguage(value: unknown): value is UiLanguage {
  return UI_LANGUAGES.some(({ code }) => code === value);
}
export function resolveUiLanguage(
  saved: string | null,
  preferred: readonly string[],
): UiLanguage {
  if (isUiLanguage(saved)) return saved;
  for (const candidate of preferred) {
    const language = candidate.toLowerCase().split(/[-_]/)[0];
    if (isUiLanguage(language)) return language;
  }
  return "en";
}
export function getUiLanguage(): UiLanguage {
  return isUiLanguage(i18n.language) ? i18n.language : "en";
}
function applyLanguage(language: UiLanguage) {
  if (language !== getUiLanguage()) void i18n.changeLanguage(language);
  document.documentElement.lang = language;
}
function browserLanguages(): readonly string[] {
  return navigator.languages?.length
    ? navigator.languages
    : [navigator.language];
}
export function initializeUiLanguage() {
  let saved: string | null = null;
  try {
    saved = window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY);
  } catch {
    /* Storage can be blocked. */
  }
  applyLanguage(resolveUiLanguage(saved, browserLanguages()));
}
export function setUiLanguage(language: UiLanguage) {
  if (!isUiLanguage(language)) return;
  try {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, language);
  } catch {
    /* The current tab still changes language. */
  }
  applyLanguage(language);
}
function onStorage(event: StorageEvent) {
  if (event.key !== UI_LANGUAGE_STORAGE_KEY && event.key !== null) return;
  try {
    if (event.storageArea && event.storageArea !== window.localStorage) return;
  } catch {
    return;
  }
  applyLanguage(resolveUiLanguage(event.newValue, browserLanguages()));
}
let subscribers = 0;
function subscribe(callback: () => void) {
  i18n.on("languageChanged", callback);
  if (subscribers++ === 0) window.addEventListener("storage", onStorage);
  return () => {
    i18n.off("languageChanged", callback);
    if (--subscribers === 0) window.removeEventListener("storage", onStorage);
  };
}
export function useUiLanguage() {
  return useSyncExternalStore(subscribe, getUiLanguage, () => "en" as const);
}
export function displayLanguage(code: string, fallback = code): string {
  try {
    return (
      new Intl.DisplayNames([getUiLanguage()], { type: "language" }).of(code) ??
      fallback
    );
  } catch {
    return fallback;
  }
}
// Call only for application-owned copy, never repository or user content.
export function t(
  message: string | null | undefined,
  values?: Record<string, unknown>,
): string {
  if (!message) return "";
  const key = message.trim();
  if (!key) return message;
  const leading = message.match(/^\s*/)?.[0] ?? "";
  const trailing = message.match(/\s*$/)?.[0] ?? "";
  return (
    leading + String(i18n.t(key, { ...values, defaultValue: key })) + trailing
  );
}
