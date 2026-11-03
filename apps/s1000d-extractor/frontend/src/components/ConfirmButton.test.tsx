// @vitest-environment jsdom

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmButton } from "./ConfirmButton";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

let root: Root | undefined;
let container: HTMLDivElement | undefined;

beforeEach(() => {
  Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", {
    value: true,
    configurable: true,
  });
});

afterEach(() => {
  if (root) act(() => root?.unmount());
  container?.remove();
  root = undefined;
  container = undefined;
  vi.useRealTimers();
});

function renderButton(onConfirm: () => void): HTMLButtonElement {
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  act(() => {
    root?.render(createElement(ConfirmButton, { label: "Delete", onConfirm, size: "sm" }));
  });
  const button = container.querySelector("button");
  if (!button) throw new Error("ConfirmButton did not render a button.");
  return button;
}

describe("ConfirmButton", () => {
  it("arms on the first click and confirms on the second", () => {
    const onConfirm = vi.fn();
    const button = renderButton(onConfirm);

    act(() => button.click());
    expect(button.textContent).toBe("common.confirmAgain");
    expect(button.getAttribute("aria-live")).toBe("polite");
    expect(onConfirm).not.toHaveBeenCalled();

    act(() => button.click());
    expect(button.textContent).toBe("Delete");
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("disarms after three seconds", () => {
    vi.useFakeTimers();
    const button = renderButton(vi.fn());

    act(() => button.click());
    act(() => vi.advanceTimersByTime(2999));
    expect(button.textContent).toBe("common.confirmAgain");

    act(() => vi.advanceTimersByTime(1));
    expect(button.textContent).toBe("Delete");
  });
});
