import i18next from "i18next";
import { describe, expect, it } from "vitest";

import en from "../locales/en.json";
import fr from "../locales/fr.json";
import { isAiGeneratedSuggestion, localizedRuleCode } from "./suggestionText";

describe("localizedRuleCode", () => {
  it("localizes AI_SCAN and humanizes other internal codes in French and English", async () => {
    const instance = i18next.createInstance();
    await instance.init({
      lng: "fr",
      fallbackLng: "fr",
      resources: {
        fr: { translation: fr },
        en: { translation: en },
      },
    });

    expect(localizedRuleCode("AI_SCAN", instance.t)).toBe("Analyse IA");
    expect(localizedRuleCode("STE_PASSIVE_VOICE", instance.t)).toBe("Ste Passive Voice");
    expect(instance.t("reviewer.source.ai")).toBe("Générée par IA");
    expect(isAiGeneratedSuggestion("ai", "CHECKLIST_1")).toBe(true);
    expect(isAiGeneratedSuggestion("norme", "AI_SCAN")).toBe(true);
    expect(isAiGeneratedSuggestion("norme", "STE_PASSIVE_VOICE", "Synthetic rewrite")).toBe(true);
    expect(isAiGeneratedSuggestion("norme", "STE_PASSIVE_VOICE", "")).toBe(false);

    await instance.changeLanguage("en");

    expect(localizedRuleCode("AI_SCAN", instance.t)).toBe("AI review");
    expect(instance.t("reviewer.source.ai")).toBe("AI-generated");
  });
});