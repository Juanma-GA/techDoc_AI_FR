import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import fr from "./locales/fr.json";
import signatureEn from "./features/signature/locales/en.json";
import signatureFr from "./features/signature/locales/fr.json";

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      fr: {
        translation: {
          ...fr,
          app: { ...fr.app, ...signatureFr.app },
          tools: { ...fr.tools, ...signatureFr.tools },
          signature: signatureFr.signature,
        },
      },
      en: {
        translation: {
          ...en,
          app: { ...en.app, ...signatureEn.app },
          tools: { ...en.tools, ...signatureEn.tools },
          signature: signatureEn.signature,
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
