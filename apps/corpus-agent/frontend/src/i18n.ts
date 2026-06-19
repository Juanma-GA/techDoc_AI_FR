/**
 * i18n piloté par le backend : les traductions sont la même source que le
 * preview.html (GET /api/v1/i18n/{lang}, ~442 clés à plat « nav.manager »).
 * Les locales locales (src/locales/*.json) ne servent que de fallback offline
 * minimal pour le tout premier rendu. keySeparator/nsSeparator désactivés car
 * les clés sont pointées.
 */
import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import { i18nApi } from "./lib/api";
import en from "./locales/en.json";
import fr from "./locales/fr.json";

const STORE_KEY = "corpus-agent-lang";

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      fr: { translation: fr as Record<string, string> },
      en: { translation: en as Record<string, string> },
    },
    fallbackLng: "fr",
    supportedLngs: ["fr", "en", "es"],
    nonExplicitSupportedLngs: true,
    keySeparator: false,
    nsSeparator: false,
    interpolation: { escapeValue: false },
    returnEmptyString: false,
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: STORE_KEY,
      caches: ["localStorage"],
    },
  });

const loaded = new Set<string>();

/** Charge (une fois) le bundle backend pour une langue et l'injecte. */
export async function loadLanguage(lng: string): Promise<void> {
  const base = (lng || "fr").slice(0, 2);
  if (loaded.has(base)) return;
  try {
    const data = await i18nApi.lang(base);
    i18n.addResourceBundle(base, "translation", data.translations, true, true);
    loaded.add(base);
  } catch {
    /* backend indisponible → on garde le fallback local */
  }
}

/** Change la langue de l'app après avoir chargé son bundle backend. */
export async function setAppLanguage(lng: string): Promise<void> {
  await loadLanguage(lng);
  await i18n.changeLanguage(lng);
}

/** Bootstrap appelé par main.tsx avant le render (FR + langue courante). */
export async function bootstrapI18n(): Promise<void> {
  const current = (i18n.language || "fr").slice(0, 2);
  await Promise.all([loadLanguage("fr"), loadLanguage(current)]);
}

export default i18n;
