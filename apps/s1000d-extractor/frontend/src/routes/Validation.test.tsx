// @vitest-environment jsdom

import { createInstance } from "i18next";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { validationApi, wizardApi } from "../lib/api";
import fr from "../locales/fr.json";
import { Validation } from "./Validation";

it("validates generated DMs on the server and downloads only for an issue override", async () => {
  Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", { value: true, configurable: true });
  const result = {
    dm_id: "dm-1", filename: "synthetic.xml", dmc: "", issue: null, schema: null,
    status: "needs_issue" as const, error_count: 0, violations: [],
  };
  const server = vi.spyOn(wizardApi, "validate").mockResolvedValue({ results: [result] });
  const file = new File(["<dmodule/>"], "synthetic.xml", { type: "application/xml" });
  const download = vi.spyOn(wizardApi, "downloadDmFile").mockResolvedValue(file);
  const upload = vi.spyOn(validationApi, "validate").mockResolvedValue({
    results: [{ ...result, status: "valid", issue: "4.1" }],
  });
  const i18n = createInstance();
  await i18n.init({ lng: "fr", resources: { fr: { translation: fr } } });
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  try {
    await act(async () => {
      root.render(
        <I18nextProvider i18n={i18n}>
          <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={[{
            pathname: "/validation",
            state: { generated: { documentId: "synthetic", dmIds: ["dm-1"] } },
          }]}>
            <Validation />
          </MemoryRouter>
        </I18nextProvider>,
      );
    });
    expect(server).toHaveBeenCalledWith("synthetic", ["dm-1"]);
    expect(download).not.toHaveBeenCalled();
    expect(upload).not.toHaveBeenCalled();
    const select = container.querySelector("select");
    expect(select).not.toBeNull();
    await act(async () => {
      if (!select) throw new Error("Missing issue selector.");
      select.value = "4.1";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(download).toHaveBeenCalledWith("synthetic", "dm-1");
    expect(upload).toHaveBeenCalledWith([file], ["4.1"], ["synthetic.xml"]);
  } finally {
    await act(async () => root.unmount());
    container.remove();
    vi.restoreAllMocks();
  }
});
