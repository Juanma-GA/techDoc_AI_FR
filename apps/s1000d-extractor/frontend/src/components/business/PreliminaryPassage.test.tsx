// @vitest-environment jsdom

import i18next from "i18next";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider, initReactI18next } from "react-i18next";
import { describe, expect, it, vi } from "vitest";

import {
  detectorTitleFor, isReviewable, type ReviewPassage,
} from "../../lib/preliminaryTypes";
import en from "../../locales/en.json";
import fr from "../../locales/fr.json";
import { PreliminaryPassage } from "./PreliminaryPassage";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

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

async function render(language: string, changes: Partial<ReviewPassage> = {}, isTemplate = true) {
  const instance = i18next.createInstance();
  await instance.use(initReactI18next).init({
    lng: language, resources: { fr: { translation: fr }, en: { translation: en } },
    interpolation: { escapeValue: false },
  });
  const onAction = vi.fn(async () => true);
  const onEdit = vi.fn();
  const element = document.createElement("div");
  element.innerHTML = renderToStaticMarkup(createElement(
    I18nextProvider, { i18n: instance },
    createElement(PreliminaryPassage, {
      dmId: "procedure", passage: { ...passage, ...changes }, text: changes.text ?? passage.text,
      detectorTitle: detectorTitleFor({ ...passage, ...changes }), isTemplate,
      disabled: false, editDisabled: false, selected: false,
      onAction, onSelect: vi.fn(), onEdit,
    }),
  ));
  return {
    element,
    onAction,
    onEdit,
    select: element.querySelector<HTMLButtonElement>('button[aria-haspopup="listbox"]'),
  };
}

describe.each([
  {
    language: "fr", proposed: "Sécurité",
    bodyPending: "Procédure classique (corps)",
    ambiguous: "À trancher", accept: "Accepter la proposition",
  },
  {
    language: "en", proposed: "Safety",
    bodyPending: "Classic procedure (body)",
    ambiguous: "Decision needed", accept: "Accept proposal",
  },
])("explicit classification proposals ($language)", (labels) => {
  it("shows a clear category without recording a human decision", async () => {
    const { select, element, onAction } = await render(labels.language);
    expect(select?.textContent?.trim()).toBe(labels.proposed);
    expect(element.querySelector('button[aria-expanded="false"]')).not.toBeNull();
    expect(element.querySelector("article")?.className).toContain("cursor-pointer");
    expect(element.querySelector("article")?.className).toContain("hover:bg-bg-2");
    expect(element.querySelector("#preliminary-passage-p")?.hasAttribute("hidden")).toBe(true);
    expect(element.querySelector("details[data-passage-details]")).not.toBeNull();
    expect(onAction).not.toHaveBeenCalled();
  });

  it("does not label an unmatched body proposal as ambiguous", async () => {
    const { select, onAction } = await render(labels.language, { suggested: "body", rule: "unmatched" });
    expect(select?.textContent?.trim()).toBe(labels.bodyPending);
    expect(onAction).not.toHaveBeenCalled();
  });

  it("reserves the decision-needed label for ambiguous proposals", async () => {
    const { select, element } = await render(labels.language, { suggested: "review", rule: "multiple" });
    expect(select?.textContent?.trim()).toBe(labels.ambiguous);
    expect([...element.querySelectorAll("button")].some((button) => button.textContent === labels.accept)).toBe(false);
  });

  it("hides an already excluded passage", async () => {
    const { element, onAction } = await render(labels.language, { decision: "body" });
    expect(element.querySelector("article")).toBeNull();
    expect(onAction).not.toHaveBeenCalled();
  });
});

it.each([
  {
    language: "fr", detectorLabel: "Intitulé détecteur", contentLabel: "Contenu à classer",
  },
  {
    language: "en", detectorLabel: "Detector title", contentLabel: "Content to classify",
  },
])("shows detector and cell content separately ($language)", async ({
  language, detectorLabel, contentLabel,
}) => {
  const { element } = await render(language, {
    source_marker: "REQUIRED PERSON(S)",
    detector_title: "REQUIRED PERSON(S)",
    source_text: "1 OPER",
    text: "1 OPER",
    marker_key: "required person s",
  });

  expect(element.querySelector<HTMLInputElement>("input")?.value).toBe("REQUIRED PERSON(S)");
  expect(element.querySelector<HTMLTextAreaElement>("textarea")?.value).toBe("1 OPER");
  expect(element.textContent).toContain(detectorLabel);
  expect(element.textContent).toContain(contentLabel);
  expect(element.querySelector("details[data-passage-details]")).toBeNull();
  expect(element.querySelector('[aria-controls="preliminary-passage-p"]')).toBeNull();
});

it("shows and edits only the selected source-table cell", async () => {
  const { element } = await render("fr", {
    row: 1,
    column: 1,
    kind: "table",
    source_text: "Right cell",
    text: "Right cell",
    source_cells: ["Left cell", "Right cell"],
    source_labels: ["Left heading", "Right heading"],
  });

  expect(element.querySelector<HTMLInputElement>("input")?.value).toBe("Right heading");
  expect(element.querySelector<HTMLTextAreaElement>("textarea")?.value).toBe("Right cell");
  expect(element.textContent).not.toContain("Left heading");
  expect(element.querySelector("textarea")?.disabled).toBe(false);
  expect(element.querySelector("input")?.readOnly).toBe(false);
});

it("keeps a later procedure's detector visible but read-only", async () => {
  const { element } = await render("fr", {
    source_marker: "REQUIRED PERSON(S)",
    detector_title: "REQUIRED PERSON(S)",
    source_text: "1 OPER",
    text: "1 OPER",
  }, false);

  expect(element.querySelector<HTMLInputElement>("input")?.value).toBe("REQUIRED PERSON(S)");
  expect(element.querySelector<HTMLInputElement>("input")?.readOnly).toBe(true);
  expect(element.querySelector<HTMLTextAreaElement>("textarea")?.readOnly).toBe(false);
});

it("emits a detector-title edit separately from the cell content", async () => {
  const instance = i18next.createInstance();
  await instance.use(initReactI18next).init({
    lng: "fr", resources: { fr: { translation: fr } },
    interpolation: { escapeValue: false },
  });
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const onEdit = vi.fn();
  const anchoredPassage: ReviewPassage = {
    ...passage, source_marker: "REQUIRED PERSON(S)", detector_title: "REQUIRED PERSON(S)",
    source_text: "1 OPER", text: "1 OPER",
  };
  try {
    await act(async () => {
      root.render(createElement(
        I18nextProvider, { i18n: instance },
        createElement(PreliminaryPassage, {
          dmId: "procedure", passage: anchoredPassage, text: "1 OPER",
          detectorTitle: "REQUIRED PERSON(S)", isTemplate: true, disabled: false,
          editDisabled: false, selected: false, onAction: vi.fn(async () => true),
          onSelect: vi.fn(), onEdit,
        }),
      ));
    });

    const detector = host.querySelector<HTMLInputElement>('input[aria-label="Intitulé détecteur"]');
    const setValue = (element: HTMLInputElement | HTMLTextAreaElement, value: string) => {
      Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), "value")?.set?.call(element, value);
      element.dispatchEvent(new Event("input", { bubbles: true }));
    };
    await act(async () => {
      if (detector) setValue(detector, "REQUIRED PERSONS");
    });

    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({
      op: "decide", detector_title: "REQUIRED PERSONS",
    }));
  } finally {
    await act(async () => root.unmount());
    host.remove();
  }
});

it("opens the whole passage and its edit details when clicking the passage box", async () => {
  const instance = i18next.createInstance();
  await instance.use(initReactI18next).init({
    lng: "fr", resources: { fr: { translation: fr } },
    interpolation: { escapeValue: false },
  });
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  try {
    await act(async () => {
      root.render(createElement(
        I18nextProvider, { i18n: instance },
        createElement(PreliminaryPassage, {
          dmId: "procedure", passage, text: passage.text, detectorTitle: "", isTemplate: true, disabled: false,
          editDisabled: false, selected: false, onAction: vi.fn(async () => true),
          onSelect: vi.fn(), onEdit: vi.fn(),
        }),
      ));
    });

    const passageCard = host.querySelector("article");
    const details = host.querySelector("details");
    expect(details?.open).toBe(false);
    await act(async () => passageCard?.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(host.querySelector("#preliminary-passage-p")?.hasAttribute("hidden")).toBe(false);
    expect(details?.open).toBe(true);

    await act(async () => passageCard?.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(host.querySelector("#preliminary-passage-p")?.hasAttribute("hidden")).toBe(true);
    expect(details?.open).toBe(false);

    await act(async () => passageCard?.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(host.querySelector("#preliminary-passage-p")?.hasAttribute("hidden")).toBe(false);
    expect(details?.open).toBe(true);

    const collapse = host.querySelector<HTMLButtonElement>('button[aria-expanded="true"]');
    await act(async () => collapse?.click());
    expect(host.querySelector("#preliminary-passage-p")?.hasAttribute("hidden")).toBe(true);
    expect(details?.open).toBe(false);
  } finally {
    await act(async () => root.unmount());
    host.remove();
  }
});

it("saves the selected S1000D tag for the current category", async () => {
  const instance = i18next.createInstance();
  await instance.use(initReactI18next).init({
    lng: "fr", resources: { fr: { translation: fr } },
    interpolation: { escapeValue: false },
  });
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const onAction = vi.fn(async () => true);
  try {
    await act(async () => {
      root.render(createElement(
        I18nextProvider, { i18n: instance },
        createElement(PreliminaryPassage, {
          dmId: "procedure",
          detectorTitle: "",
          isTemplate: true,
          passage: {
            ...passage, decision: "support", target_tag: "name",
            tag_options: { support: ["name", "partNumber"] },
          },
          text: passage.text, disabled: false, editDisabled: false, selected: false,
          onAction, onSelect: vi.fn(), onEdit: vi.fn(),
        }),
      ));
    });

    const tagSelector = host.querySelector<HTMLButtonElement>('button[aria-label="Balise S1000D"]');
    await act(async () => { tagSelector?.click(); });
    const partNumber = [...document.querySelectorAll<HTMLButtonElement>('[role="option"]')]
      .find((option) => option.textContent?.startsWith("partNumber"));
    await act(async () => { partNumber?.click(); });

    expect(onAction).toHaveBeenCalledWith({
      dm_id: "procedure", passage_id: "p", op: "decide",
      destination: "support", target_tag: "partNumber",
    });
  } finally {
    await act(async () => root.unmount());
    host.remove();
  }
});

it.each([
  {
    language: "fr",
    label: "Exclure des préliminaires/sécurité et garder dans la procédure classique",
  },
  {
    language: "en",
    label: "Exclude from preliminaries/safety and keep in the classic procedure",
  },
])("moves an excluded zone to the procedure body ($language)", async ({ language, label }) => {
  const instance = i18next.createInstance();
  await instance.use(initReactI18next).init({
    lng: language, resources: { fr: { translation: fr }, en: { translation: en } },
    interpolation: { escapeValue: false },
  });
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const onAction = vi.fn(async () => true);
  try {
    await act(async () => {
      root.render(createElement(
        I18nextProvider, { i18n: instance },
        createElement(PreliminaryPassage, {
          dmId: "procedure",
          detectorTitle: "",
          isTemplate: true,
          passage: {
            ...passage, decision: "safety", target_tag: "warning",
            tag_options: { safety: ["warning"], body: ["proceduralStep"] },
          },
          text: passage.text, disabled: false, editDisabled: false, selected: false,
          onAction, onSelect: vi.fn(), onEdit: vi.fn(),
        }),
      ));
    });

    const excludeButton = host.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`);
    expect(excludeButton?.textContent?.trim()).toBe("");
    expect(excludeButton?.querySelector("svg")).toBeTruthy();
    await act(async () => { excludeButton?.click(); });

    expect(onAction).toHaveBeenCalledWith({
      dm_id: "procedure", passage_id: "p", op: "decide",
      destination: "body", target_tag: "proceduralStep",
    });
    expect(host.querySelector("article")).toBeNull();
  } finally {
    await act(async () => root.unmount());
    host.remove();
  }
});
