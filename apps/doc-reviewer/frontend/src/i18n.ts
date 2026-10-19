import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import clientRulesEn from "./locales/client-rules.en.json";
import clientRulesFr from "./locales/client-rules.fr.json";
import en from "./locales/en.json";
import fr from "./locales/fr.json";

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      fr: { translation: { ...fr, clientRuleCatalog: clientRulesFr } },
      en: { translation: { ...en, clientRuleCatalog: clientRulesEn } },
    },
    fallbackLng: "fr",
    supportedLngs: ["fr", "en"],
    interpolation: { escapeValue: false },
    returnEmptyString: false,
  });

export default i18n;
