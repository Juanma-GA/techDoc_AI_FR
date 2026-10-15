import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import catpartDiffEn from "./locales/catpart-diff.en.json";
import fr from "./locales/fr.json";
import catpartDiffFr from "./locales/catpart-diff.fr.json";

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      fr: { translation: { ...fr, catpartDiff: catpartDiffFr } },
      en: { translation: { ...en, catpartDiff: catpartDiffEn } },
    },
    fallbackLng: ["fr", "en"],
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
    },
  });

export default i18n;
