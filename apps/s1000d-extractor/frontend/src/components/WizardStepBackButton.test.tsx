import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { WizardStep } from "../lib/api";
import { WizardStepBackButton } from "./WizardStepBackButton";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

function renderButton(step: WizardStep, steps: WizardStep[], disabled = false) {
  return renderToStaticMarkup(
    createElement(WizardStepBackButton, {
      step,
      steps,
      disabled,
      onBack: vi.fn(),
    }),
  );
}

describe("wizard step back button", () => {
  it("does not show a back action on the first step", () => {
    expect(renderButton("split", ["split", "type", "structure", "generate"])).toBe("");
  });

  it("shows a disabled back action while the wizard is busy", () => {
    const markup = renderButton(
      "split",
      ["dmrl", "split", "type", "structure", "generate"],
      true,
    );

    expect(markup).toContain("common.back");
    expect(markup).toContain("disabled");
  });
});
