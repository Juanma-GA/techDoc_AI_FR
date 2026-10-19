import { cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "../i18n";
import { useImageBrush } from "./useImageBrush";

afterEach(cleanup);

describe("image brush defaults", () => {
  it("selects local color by default", () => {
    const { result } = renderHook(() =>
      useImageBrush({
        imageFile: null,
        onImageEdited: () => {},
        onBusyChange: () => {},
        t: i18n.t,
      }),
    );

    expect(result.current.eraseMode).toBe("color");
  });

  it("labels the AI reconstruction option in French and English", () => {
    expect(i18n.t("image.lamaMode", { lng: "fr" })).toBe("Reconstruction IA");
    expect(i18n.t("image.lamaMode", { lng: "en" })).toBe("AI reconstruction");
  });
});
