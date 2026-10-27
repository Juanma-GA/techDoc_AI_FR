// @vitest-environment jsdom

import i18next from "i18next";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider, initReactI18next } from "react-i18next";
import { describe, expect, it, vi } from "vitest";

import { isReviewable, type ReviewPassage } from "../../lib/preliminaryTypes";
import en from "../../locales/en.json";
import fr from "../../locales/fr.json";
import { PreliminaryPassage } from "./PreliminaryPassage";

const passage: ReviewPassage = {
  id: "p", node_id: "node", row: null, start: 0, end: 15,
  source_text: "Synthetic text.", text: "Synthetic text.", page: 1, kind: "paragraph",
  suggested: "safety", rule: "keywords", decision: null,
};

describe("source roles", () => {
  it("keeps ordinary and older content passages reviewable", () => {
    expect(isReviewable(passage)).toBe(true);
    expect(isReviewable({ ...passage, role: "content" })).toBe(true);
  });
  it.each(["heading", "marker", "table-header", "layout", "caption"] as const)(
    "keeps %s in the source without creating a requirement decision", (role) => {
      expect(isReviewable({ ...passage, role })).toBe(false);
    },
  );
});

async function render(language: string, changes: Partial<ReviewPassage> = {}) {
  const instance = i18next.createInstance();
  await instance.use(initReactI18next).init({
    lng: language, resources: { fr: { translation: fr }, en: { translation: en } },
    interpolation: { escapeValue: false },
  });
  const onAction = vi.fn(async () => true);
  const element = document.createElement("div");
  element.innerHTML = renderToStaticMarkup(createElement(
    I18nextProvider, { i18n: instance },
    createElement(PreliminaryPassage, {
      dmId: "procedure", passage: { ...passage, ...changes }, text: passage.text,
      disabled: false, editDisabled: false, selected: false,
      onAction, onSelect: vi.fn(), onEdit: vi.fn(),
    }),
  ));
  return { element, onAction, select: element.querySelector("select") };
}

describe.each([
  {
    language: "fr", proposed: "Sécurité — à confirmer",
    bodyPending: "Reste dans la procédure — à confirmer",
    ambiguous: "À trancher", body: "Reste dans la procédure", accept: "Accepter la proposition",
  },
  {
    language: "en", proposed: "Safety — awaiting confirmation",
    bodyPending: "Keep in procedure — awaiting confirmation",
    ambiguous: "Decision needed", body: "Keep in procedure", accept: "Accept proposal",
  },
])("explicit classification proposals ($language)", (labels) => {
  it("shows a clear category without recording a human decision", async () => {
    const { select, onAction } = await render(labels.language);
    expect(select?.value).toBe("");
    expect(select?.selectedOptions[0]?.textContent).toBe(labels.proposed);
    expect(onAction).not.toHaveBeenCalled();
  });

  it("does not label an unmatched body proposal as ambiguous", async () => {
    const { select, onAction } = await render(labels.language, { suggested: "body", rule: "unmatched" });
    expect(select?.value).toBe("");
    expect(select?.selectedOptions[0]?.textContent).toBe(labels.bodyPending);
    expect(onAction).not.toHaveBeenCalled();
  });

  it("reserves the decision-needed label for ambiguous proposals", async () => {
    const { select, element } = await render(labels.language, { suggested: "review", rule: "multiple" });
    expect(select?.selectedOptions[0]?.textContent).toBe(labels.ambiguous);
    expect([...element.querySelectorAll("button")].some((button) => button.textContent === labels.accept)).toBe(false);
  });

  it("keeps a confirmed category distinct from the pending proposal", async () => {
    const { select, onAction } = await render(labels.language, { decision: "body" });
    expect(select?.value).toBe("body");
    expect(select?.selectedOptions[0]?.textContent).toBe(labels.body);
    expect(onAction).not.toHaveBeenCalled();
  });
});
