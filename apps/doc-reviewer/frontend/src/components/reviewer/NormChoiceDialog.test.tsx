import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DocumentNorm } from "../../hooks/useDocumentNorm";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, values?: Record<string, unknown>) =>
      values ? `${key}:${JSON.stringify(values)}` : key,
    i18n: { language: "fr" },
  }),
}));
vi.mock("../ConfirmDialog", () => ({
  ConfirmDialog: (props: {
    title: string;
    description?: string;
    confirmLabel: string;
    cancelLabel: string;
    onConfirm: () => void;
    onOpenChange: (open: boolean) => void;
    children?: React.ReactNode;
  }) => (
    <div>
      <p>{props.description}</p>
      {props.children}
      <button type="button" onClick={() => props.onOpenChange(false)}>
        {props.cancelLabel}
      </button>
      <button
        type="button"
        onClick={() => {
          props.onConfirm();
          props.onOpenChange(false);
        }}
      >
        {props.confirmLabel}
      </button>
    </div>
  ),
}));

import { NormChoiceDialog } from "./NormChoiceDialog";

const detection: DocumentNorm = {
  detected_norm: "s1000d",
  default_norm: "ata100",
  norms: [
    { code: "ata100", label: "ATA100" },
    { code: "s1000d", label: "S1000D" },
  ],
  page_revision_tracking: false,
};

describe("NormChoiceDialog", () => {
  let container: HTMLDivElement;
  let root: Root;
  const onConfirm = vi.fn();
  const onCancel = vi.fn();

  beforeEach(() => {
    Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", {
      value: true,
      configurable: true,
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() =>
      root.render(
        <NormChoiceDialog
          detection={detection}
          activeCounts={{ ata100: 85, s1000d: 0 }}
          onCancel={onCancel}
          onConfirm={onConfirm}
        />,
      ),
    );
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  const radio = (code: string) =>
    container.querySelector<HTMLInputElement>(`input[type="radio"][value="${code}"]`)!;
  const click = (element: Element) => act(() => element.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  const button = (label: string) =>
    Array.from(container.querySelectorAll("button")).find((item) => item.textContent === label)!;

  it("proposes the detected norm and its number of active rules", () => {
    expect(radio("s1000d").checked).toBe(true);
    expect(radio("ata100").checked).toBe(false);
    expect(container.textContent).toContain('"count":85');
    expect(container.textContent).toContain('"count":0');
  });

  it("runs the analysis with the detected norm and leaves the Rules tab alone by default", () => {
    click(button("reviewer.norm.run"));

    expect(onConfirm).toHaveBeenCalledWith({ norm: "s1000d", persist: false });
  });

  it("can run another norm and update the Rules tab", () => {
    click(radio("ata100"));
    click(container.querySelector('input[type="checkbox"]')!);
    click(button("reviewer.norm.run"));

    expect(onConfirm).toHaveBeenCalledWith({ norm: "ata100", persist: true });
  });

  it("cancels without running", () => {
    click(button("common.cancel"));

    expect(onConfirm).not.toHaveBeenCalled();
    expect(onCancel).toHaveBeenCalled();
  });
});
