import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: "fr" } }),
}));

import { AnalysisPageRange } from "./AnalysisPageRange";

describe("AnalysisPageRange", () => {
  let container: HTMLDivElement;
  let root: Root;
  const onStart = vi.fn();

  beforeEach(() => {
    Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", {
      value: true,
      configurable: true,
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  const render = (trackModifiedPages: boolean) =>
    act(() =>
      root.render(
        <AnalysisPageRange
          pageCount={10}
          running={false}
          onStart={onStart}
          trackModifiedPages={trackModifiedPages}
        />,
      ),
    );
  const options = () =>
    Array.from(container.querySelectorAll("option")).map((option) => option.value);
  const start = () =>
    act(() => container.querySelector("button")!.dispatchEvent(new MouseEvent("click", { bubbles: true })));

  it("offers the modified pages by default", () => {
    render(true);

    expect(options()).toEqual(["modified", "all", "range"]);
    start();
    expect(onStart).toHaveBeenCalledWith({ modifiedOnly: true });
  });

  it("analyses the whole document when the norm does not follow modified pages", () => {
    render(false);

    expect(options()).toEqual(["all", "range"]);
    expect(container.querySelector("select")!.value).toBe("all");
    start();
    expect(onStart).toHaveBeenCalledWith({ modifiedOnly: false });
  });
});
