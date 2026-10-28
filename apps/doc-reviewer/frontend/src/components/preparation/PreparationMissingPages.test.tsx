import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

import { PreparationMissingPages } from "./PreparationMissingPages";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("PreparationMissingPages", () => {
  let container: HTMLDivElement;
  let root: Root;
  const onProvide = vi.fn();
  const onAbsent = vi.fn();

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    onProvide.mockReset();
    onAbsent.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("renders nothing when every required type was found", () => {
    act(() => {
      root.render(
        <PreparationMissingPages
          groups={[]}
          pageCount={5}
          saving={false}
          onProvide={onProvide}
          onAbsent={onAbsent}
        />,
      );
    });

    expect(container.textContent).toBe("");
  });

  it("lets the user mark a missing type as absent and undo it", () => {
    act(() => {
      root.render(
        <PreparationMissingPages
          groups={[["TP1"]]}
          absentGroups={[["ROR"]]}
          pageCount={5}
          saving={false}
          onProvide={onProvide}
          onAbsent={onAbsent}
        />,
      );
    });
    const buttons = Array.from(container.querySelectorAll<HTMLButtonElement>("button"));
    const notPresent = buttons.find((item) => item.textContent === "preparationUi.missing.notPresent");
    const undo = buttons.find((item) => item.textContent === "preparationUi.missing.undo");

    act(() => notPresent?.click());
    act(() => undo?.click());

    expect(onAbsent).toHaveBeenNthCalledWith(1, ["TP1"], true);
    expect(onAbsent).toHaveBeenNthCalledWith(2, ["ROR"], false);
  });

  it("asks for a page per missing type and validates the page range", () => {
    act(() => {
      root.render(
        <PreparationMissingPages
          groups={[["TP1"], ["HIGHLIGHTS", "HIGHLIGHTS_PAGE_1"]]}
          pageCount={5}
          saving={false}
          onProvide={onProvide}
          onAbsent={onAbsent}
        />,
      );
    });
    const inputs = container.querySelectorAll<HTMLInputElement>('input[type="number"]');
    expect(container.querySelectorAll("input")).toHaveLength(2);
    const buttons = container.querySelectorAll<HTMLButtonElement>("button");
    const input = inputs[0] as HTMLInputElement;
    const button = buttons[0] as HTMLButtonElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    expect(button.disabled).toBe(true);

    act(() => {
      setter?.call(input, "9");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(button.disabled).toBe(true);

    act(() => {
      setter?.call(input, "3");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    act(() => button.click());

    expect(container.textContent).toContain("HIGHLIGHTS / HIGHLIGHTS_PAGE_1");
    expect(onProvide).toHaveBeenCalledWith(3, "TP1");
  });
});
