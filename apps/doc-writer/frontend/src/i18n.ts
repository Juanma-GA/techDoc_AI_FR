import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import es from "./locales/es.json";
import fr from "./locales/fr.json";
import demoEn from "./locales/demo-en.json";
import demoEs from "./locales/demo-es.json";
import demoFr from "./locales/demo-fr.json";

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      fr: {
        translation: {
          ...fr,
          ...demoFr,
          settings: { ...fr.settings, ...demoFr.settings },
        },
      },
      en: {
        translation: {
          ...en,
          ...demoEn,
          settings: { ...en.settings, ...demoEn.settings },
        },
      },
      es: {
        translation: {
          ...es,
          ...demoEs,
          settings: { ...es.settings, ...demoEs.settings },
        },
      },
    },
    fallbackLng: ["fr", "en"],
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
    },
  });

export default i18n;
