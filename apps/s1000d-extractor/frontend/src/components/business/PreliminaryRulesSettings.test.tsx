// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18next from "i18next";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider, initReactI18next } from "react-i18next";
import { describe, expect, it } from "vitest";

import {
  createRuleDraft, draftToGroups, parseExpressions, preliminaryRulesQueryKey, removesExpressions, validRuleLists,
  type RequirementRuleGroup,
} from "../../lib/preliminaryRules";
import en from "../../locales/en.json";
import fr from "../../locales/fr.json";
import { PreliminaryRulesSettings } from "./PreliminaryRulesSettings";

const group: RequirementRuleGroup = {
  category: "conditions", kind: "keyword", fr: ["banc isolé"], en: ["isolated bench", "clear bench"],
};

describe("independent bilingual lists", () => {
  it("accepts different synonym counts and intentional empty configurations", () => {
    expect(validRuleLists([])).toBe(true);
    expect(validRuleLists([group])).toBe(true);
    expect(validRuleLists([{ ...group, fr: ["clé C++"], en: ["C++ wrench"] }])).toBe(true);
  });
  it.each([
    { fr: [] }, { en: [] }, { fr: [""] }, { en: ["   "] }, { fr: ["a\tb"] },
    { fr: ["a\nb"] }, { en: ["x".repeat(201)] },
  ])("rejects incomplete or invalid lists: %j", (changes) => {
    expect(validRuleLists([{ ...group, ...changes }])).toBe(false);
  });
  it("limits expressions per language across all categories, not just each textarea", () => {
    const values = Array.from({ length: 501 }, (_, index) => `Term ${index}`);
    expect(validRuleLists([
      { ...group, fr: values }, { ...group, category: "support", fr: values },
    ])).toBe(false);
  });
  it("trims lines, ignores blank lines and preserves independent language order", () => {
    expect(parseExpressions("  étau  \r\n\r\n fixture\n \n")).toEqual(["étau", "fixture"]);
    const draft = createRuleDraft([group]);
    expect(draft).toHaveLength(6);
    expect(draftToGroups(draft)).toEqual([group]);
    draft[0]!.keyword.fr = "  banc isolé\n\nétau \n";
    expect(draftToGroups(draft)[0]).toEqual({ ...group, fr: ["banc isolé", "étau"] });
  });
  it("does not restore defaults when both lists are cleared", () => {
    expect(draftToGroups(createRuleDraft([]))).toEqual([]);
    const draft = createRuleDraft([group]);
    draft[0]!.keyword = { fr: " \n ", en: "" };
    expect(draftToGroups(draft)).toEqual([]);
  });
  it("preserves category and heading/keyword separation", () => {
    const groups: RequirementRuleGroup[] = [
      group, { category: "support", kind: "heading", fr: ["Équipements"], en: ["Bench resources"] },
    ];
    expect(draftToGroups(createRuleDraft(groups))).toEqual(groups);
  });
  it("requires destructive confirmation for removals and replacements, but not additions or reordering", () => {
    expect(removesExpressions([group], [group])).toBe(false);
    expect(removesExpressions([group], [{ ...group, en: [...group.en].reverse(), fr: [...group.fr, "étau"] }])).toBe(false);
    expect(removesExpressions([group], [{ ...group, en: ["isolated bench"] }])).toBe(true);
    expect(removesExpressions([group], [{ ...group, fr: ["autre"] }])).toBe(true);
    expect(removesExpressions([group], [])).toBe(true);
    expect(removesExpressions([group], [{ ...group, category: "support" }])).toBe(true);
  });
});

describe.each([
  {
    language: "fr", title: "Règles de préremplissage des exigences",
    french: "Liste française (FR)", english: "Liste anglaise (EN)",
    empty: "Aucun mot-clé renseigné", expand: "Afficher les règles",
  },
  {
    language: "en", title: "Requirement prefill rules",
    french: "French list (FR)", english: "English list (EN)",
    empty: "No keywords yet", expand: "Show rules",
  },
])("localized grouped settings ($language)", (labels) => {
  async function render(groups: RequirementRuleGroup[]) {
    const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
    client.setQueryData(preliminaryRulesQueryKey, { revision: 1, groups });
    const instance = i18next.createInstance();
    await instance.use(initReactI18next).init({
      lng: labels.language, resources: { fr: { translation: fr }, en: { translation: en } },
      interpolation: { escapeValue: false },
    });
    const element = document.createElement("div");
    element.innerHTML = renderToStaticMarkup(createElement(
      QueryClientProvider, { client },
      createElement(I18nextProvider, { i18n: instance }, createElement(PreliminaryRulesSettings)),
    ));
    client.clear();
    return element;
  }
  it("renders six compact categories with multiline FR/EN lists instead of per-rule controls", async () => {
    const element = await render([group]);
    expect(element.querySelector("form")?.getAttribute("aria-label")).toBe(labels.title);
    expect(element.textContent).toContain(labels.french);
    expect(element.textContent).toContain(labels.english);
    expect(element.querySelectorAll('[data-testid^="rule-category-"]')).toHaveLength(6);
    expect(element.querySelectorAll("input, select, [data-rule-index]")).toHaveLength(0);
    const lists = element.querySelectorAll("textarea");
    expect(lists).toHaveLength(24);
    expect(lists[0]?.value).toBe(group.fr.join("\n"));
    expect(lists[1]?.value).toBe(group.en.join("\n"));
    expect([...lists].filter((list) => list.required)).toHaveLength(2);
    expect([...lists].every((list) => list.rows === 5)).toBe(true);
    expect(element.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(true);
  });
  it("starts collapsed with an accessible toggle while keeping all category drafts mounted", async () => {
    const element = await render([group]);
    const toggle = element.querySelector<HTMLButtonElement>('button[aria-expanded="false"]');
    expect(toggle?.textContent).toContain(labels.expand);
    const panel = element.querySelector(`[id="${toggle?.getAttribute("aria-controls")}"]`);
    expect(panel?.hasAttribute("hidden")).toBe(true);
    expect(panel?.querySelector("form")).not.toBeNull();
    expect(element.querySelector("details[open]")).toBeNull();
  });
  it("keeps all six categories editable when configuration is empty, without inserting defaults", async () => {
    const element = await render([]);
    expect(element.textContent).toContain(labels.empty);
    expect(element.querySelectorAll('[data-testid^="rule-category-"]')).toHaveLength(6);
    expect([...element.querySelectorAll("textarea")].every((list) => !list.value && !list.required)).toBe(true);
  });
});
