// @vitest-environment jsdom

import { createInstance } from "i18next";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { I18nextProvider } from "react-i18next";
import { expect, it, vi } from "vitest";

import type { TreeNode, WizardState } from "../../../lib/api";
import fr from "../../../locales/fr.json";
import * as flags from "../../../components/zoneFlags";
import { StructureStep } from "./StructureStep";

vi.mock("../../../components/zoneFlags", () => ({
  PageFlag: vi.fn(() => null), ZoneFlag: () => null, ReviewFlag: () => null,
  TableFlag: () => null, RefFlag: () => null,
}));

it("collapses large trees and re-renders only the overridden node", async () => {
  Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", { value: true, configurable: true });
  const children: TreeNode[] = Array.from({ length: 550 }, (_, index) => ({
    id: `n${index}`, kind: "paragraph", text: `Synthetic paragraph ${index}`,
    context: "unknown", confidence: 1, children: [],
    candidates: index ? [{ element: "para" }] : [{ element: "para" }, { element: "proceduralStep" }],
  }));
  const section: TreeNode = {
    id: "section", kind: "section", text: "Synthetic section", context: "unknown",
    confidence: 1, candidates: [], children,
  };
  const state: WizardState = {
    step: "structure", split_level: "section", dms: [{
      dm_id: "dm", title: "Synthetic DM", dm_type: "descriptive", node_count: 551,
      tree: { ...section, id: "root", children: [section] },
    }],
  };
  const i18n = createInstance();
  await i18n.init({ lng: "fr", resources: { fr: { translation: fr } } });
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  try {
    await act(async () => root.render(<I18nextProvider i18n={i18n}>
      <StructureStep state={state} wizard={{ busy: false, action: async () => true }} />
    </I18nextProvider>));
    expect(container.querySelectorAll("[data-wiz-node]")).toHaveLength(1);
    const expand = Array.from(container.querySelectorAll("button")).find((button) => button.textContent === "Tout déplier");
    await act(async () => expand?.click());
    expect(container.querySelectorAll("[data-wiz-node]")).toHaveLength(551);
    vi.mocked(flags.PageFlag).mockClear();
    const choice = container.querySelector('[data-wiz-node="n0"] button:last-child');
    await act(async () => choice?.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(flags.PageFlag).toHaveBeenCalledTimes(1);
    expect(container.querySelector('[data-wiz-node="n0"] button[aria-pressed="true"]')?.textContent)
      .toContain("proceduralStep");
  } finally {
    await act(async () => root.unmount());
    container.remove();
  }
});
