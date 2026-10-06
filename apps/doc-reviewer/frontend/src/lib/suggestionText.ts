import type { TFunction } from "i18next";

import type { Suggestion } from "../types/domain";

function translation(
  t: TFunction,
  key: string,
  options: Record<string, unknown> = {},
): string | null {
  const value = t(key, { ...options, defaultValue: "__missing_translation__" });
  return value === "__missing_translation__" || value === key ? null : value;
}

export function localizedRuleCode(ruleCode: string, t: TFunction): string {
  const translated = translation(t, `rules.codes.${ruleCode}`);
  if (translated) return translated;
  return ruleCode
    .replace(/[_-]+/g, " ")
    .trim()
    .toLocaleLowerCase()
    .replace(/(^|\s)([a-z0-9])/g, (_match, prefix: string, character: string) =>
      `${prefix}${character.toLocaleUpperCase()}`,
    );
}

const AI_REWRITTEN_RULE_CODES = new Set([
  "STE_PASSIVE_VOICE",
  "STE_FIRST_PERSON",
  "STE_PROCEDURAL_GERUND",
  "STE_LONG_SENTENCE",
]);

export function isAiGeneratedSuggestion(
  sourceKind: string,
  ruleCode: string,
  proposedText?: string,
): boolean {
  return (
    sourceKind === "ai" ||
    ruleCode === "AI_SCAN" ||
    ruleCode === "FIGURE_COHERENCE" ||
    (AI_REWRITTEN_RULE_CODES.has(ruleCode) && Boolean(proposedText))
  );
}

function detailText(message: string, t: TFunction): string {
  const sizeMatch = message.match(
    /Taille detectee\s*:\s*(.+?)\.\s*Taille attendue\s*:\s*(.+?)\.?$/,
  );
  if (sizeMatch) {
    return ` ${t("rules.suggestionDetails.detectedSize")}: ${sizeMatch[1]}. ` +
      `${t("rules.suggestionDetails.expectedSize")}: ${sizeMatch[2]}.`;
  }

  const details: Array<[string, string, boolean]> = [
    [" Element attendu absent de la page", "rules.suggestionDetails.expectedMissing", false],
    [" Element attendu :", "rules.suggestionDetails.expectedElement", true],
    [" Texte attendu absent :", "rules.suggestionDetails.expectedTextMissing", true],
    ["Texte manquant :", "rules.suggestionDetails.missingText", true],
    ["Texte attendu :", "rules.suggestionDetails.expectedText", true],
    ["Texte en trop :", "rules.suggestionDetails.extraText", true],
    ["Texte attendu pour ", "rules.suggestionDetails.expectedTextFor", true],
    [" Le contenu doit commencer par ", "rules.suggestionDetails.contentMustStart", true],
  ];
  for (const [marker, key, hasValue] of details) {
    const index = message.indexOf(marker);
    if (index < 0) continue;
    const suffix = message.slice(index + marker.length).trim();
    if (!hasValue) return ` ${t(key)}`;
    if (key === "rules.suggestionDetails.expectedTextFor") {
      return ` ${t(key)}${suffix}`;
    }
    return ` ${t(key)}${suffix ? `: ${suffix}` : ""}`;
  }
  return "";
}

function translatedFallback(message: string, t: TFunction): string {
  return message
    .replace("Règle non satisfaite : ", t("rules.suggestionPrefix.failed"))
    .replace("Vérification manuelle requise : ", t("rules.suggestionPrefix.manual"))
    .replace("Détection · pas de correction automatique", t("rules.suggestionDetails.detectionOnly"));
}

export function localizedSuggestionMessage(
  suggestion: Suggestion,
  t: TFunction,
): string {
  const messageKey = `rules.messages.${suggestion.rule_code}`;
  let translated = translation(t, messageKey);
  if (suggestion.rule_code === "UNITS_CONVERT") {
    const system = suggestion.message.match(/système\s+([^.]+)|the\s+(\w+)\s+system/i);
    translated = translation(t, messageKey, { system: system?.[1] ?? system?.[2] ?? "target unit" });
  } else if (suggestion.rule_code === "FIGURE_NO_CAPTION" || suggestion.rule_code === "FIGURE_COHERENCE") {
    const index = suggestion.message.match(/Figure\s+(\d+)/i)?.[1] ?? "";
    translated = translation(t, messageKey, { index });
  } else if (suggestion.rule_code.startsWith("LAYOUT_")) {
    const detail = suggestion.message.match(/\(([^)]*)\)/)?.[1] ?? "";
    translated = translation(t, messageKey, { detail });
  }
  if (!translated) return translatedFallback(suggestion.message, t);

  const isCompiled =
    suggestion.rule_kind === "compiled_standard" || suggestion.rule_kind === "compiled_checklist";
  const isManual = suggestion.message.startsWith("Vérification manuelle requise : ");
  const prefix = isCompiled
    ? t(isManual ? "rules.suggestionPrefix.manual" : "rules.suggestionPrefix.failed")
    : "";
  return `${prefix}${translated}${detailText(suggestion.message, t)}`;
}