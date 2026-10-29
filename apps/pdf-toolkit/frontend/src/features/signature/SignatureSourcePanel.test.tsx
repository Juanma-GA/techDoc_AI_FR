// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { SignatureSourcePanel } from "./SignatureSourcePanel";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("SignatureSourcePanel", () => {
  it("disables signature input until a PDF is selected", () => {
    const onSaveSignature = vi.fn();
    const view = render(
      <SignatureSourcePanel
        pdfFile={null}
        signatureFile={null}
        firstName=""
        lastName=""
        dateValue=""
        language="en"
        disabled={false}
        onPdfFiles={vi.fn()}
        onError={vi.fn()}
        onRemovePdf={vi.fn()}
        onFirstNameChange={vi.fn()}
        onLastNameChange={vi.fn()}
        onDateChange={vi.fn()}
        onSaveSignature={onSaveSignature}
        onClearSignature={vi.fn()}
      />,
    );
    const canvas = view.getByLabelText(i18n.t("signature.canvasLabel"));

    expect(canvas.getAttribute("aria-disabled")).toBe("true");
    const importButton = view.getByRole("button", { name: i18n.t("signature.import") });
    expect(importButton.hasAttribute("disabled")).toBe(true);

    fireEvent.pointerDown(canvas, { pointerId: 1, clientX: 8, clientY: 8 });

    expect(onSaveSignature).not.toHaveBeenCalled();
  });
});
