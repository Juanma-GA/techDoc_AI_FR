// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nextProvider } from "react-i18next";
import { createInstance } from "i18next";

import en from "../../locales/en.json";
import fr from "../../locales/fr.json";
import cropEn from "./locales/en.json";
import cropFr from "./locales/fr.json";
import { CropPagePreview } from "./CropPagePreview";

class TestPointerEvent extends MouseEvent {
  readonly pointerId: number;

  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 0;
  }
}

async function setup() {
  const i18n = createInstance();
  await i18n.init({
    lng: "fr",
    resources: {
      fr: {
        translation: {
          ...fr,
          tools: { ...fr.tools, ...cropFr.tools },
          crop: cropFr.crop,
        },
      },
      en: {
        translation: {
          ...en,
          tools: { ...en.tools, ...cropEn.tools },
          crop: cropEn.crop,
        },
      },
    },
    interpolation: { escapeValue: false },
  });
  const onRegionChange = vi.fn();
  render(
    <I18nextProvider i18n={i18n}>
      <CropPagePreview
        canvasRef={{ current: null }}
        pageSize={{ width: 612, height: 792 }}
        ready
        disabled={false}
        region={null}
        onRegionChange={onRegionChange}
      />
    </I18nextProvider>,
  );
  return { onRegionChange };
}

beforeEach(() => {
  vi.stubGlobal("PointerEvent", TestPointerEvent);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("CropPagePreview", () => {
  it("converts a drag into a normalized crop region", async () => {
    const { onRegionChange } = await setup();
    const preview = screen.getByLabelText("Aperçu de la page 1").parentElement;
    if (!preview) throw new Error("Crop preview container is missing");
    vi.spyOn(preview, "getBoundingClientRect").mockReturnValue({
      x: 0,
      y: 0,
      left: 0,
      top: 0,
      right: 100,
      bottom: 100,
      width: 100,
      height: 100,
      toJSON: () => ({}),
    } as DOMRect);

    fireEvent.pointerDown(preview, { clientX: 10, clientY: 20, button: 0, pointerId: 1 });
    fireEvent.pointerMove(preview, { clientX: 80, clientY: 70, pointerId: 1 });
    fireEvent.pointerUp(preview, { clientX: 80, clientY: 70, pointerId: 1 });

    expect(onRegionChange).toHaveBeenCalledWith({
      left: 0.1,
      top: 0.2,
      right: 0.8,
      bottom: 0.7,
    });
  });
});
