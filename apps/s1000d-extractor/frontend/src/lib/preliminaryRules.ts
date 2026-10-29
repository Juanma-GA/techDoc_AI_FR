import { api } from "./api";
import { requirementCategories } from "./preliminaryTypes";

export const ruleKinds = ["keyword", "heading"] as const;
export type RuleKind = (typeof ruleKinds)[number];
export type RuleCategory = (typeof requirementCategories)[number];
export type RequirementRuleGroup = {
  category: RuleCategory;
  kind: RuleKind;
  fr: string[];
  en: string[];
};
export type LanguageLists = { fr: string; en: string };
export type CategoryRuleDraft = {
  category: RuleCategory;
  keyword: LanguageLists;
  heading: LanguageLists;
};
export type RequirementRules = { revision: number; groups: RequirementRuleGroup[] };
export const preliminaryRulesQueryKey = ["preliminary-rules"];

export function createRuleDraft(groups: RequirementRuleGroup[]): CategoryRuleDraft[] {
  return requirementCategories.map((category) => {
    const list = (kind: RuleKind): LanguageLists => {
      const group = groups.find((entry) => entry.category === category && entry.kind === kind);
      return { fr: group?.fr.join("\n") ?? "", en: group?.en.join("\n") ?? "" };
    };
    return { category, keyword: list("keyword"), heading: list("heading") };
  });
}

export function parseExpressions(text: string): string[] {
  return text.split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
}

export function draftToGroups(draft: CategoryRuleDraft[]): RequirementRuleGroup[] {
  return draft.flatMap(({ category, ...lists }) => ruleKinds.flatMap((kind) => {
    const fr = parseExpressions(lists[kind].fr);
    const en = parseExpressions(lists[kind].en);
    return fr.length || en.length ? [{ category, kind, fr, en }] : [];
  }));
}

export function validRuleLists(groups: RequirementRuleGroup[]): boolean {
  return groups.every((group) => group.fr.length > 0 && group.en.length > 0
    && [...group.fr, ...group.en].every((value) =>
      value.trim().length > 0 && value.length <= 200 && !/[\r\n\t]/.test(value)))
    && (["fr", "en"] as const).every((language) =>
      groups.reduce((count, group) => count + group[language].length, 0) <= 1000);
}

export function removesExpressions(before: RequirementRuleGroup[], after: RequirementRuleGroup[]): boolean {
  return before.some((group) => {
    const next = after.find((entry) => entry.category === group.category && entry.kind === group.kind);
    return (["fr", "en"] as const).some((language) =>
      group[language].some((value) => !next?.[language].includes(value)));
  });
}

export type RuleListChange = {
  kind: RuleKind;
  language: "fr" | "en";
  text: string;
};

export const preliminaryRulesApi = {
  read: () => api<RequirementRules>("/settings/preliminary-rules"),
  write: (body: RequirementRules) => api<RequirementRules>(
    "/settings/preliminary-rules", { method: "POST", body: JSON.stringify(body) },
  ),
};
