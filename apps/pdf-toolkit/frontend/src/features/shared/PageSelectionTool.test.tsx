// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import i18n from "../../i18n";
import { PageSelectionTool } from "./PageSelectionTool";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

afterEach(cleanup);

describe("PageSelectionTool rotation control", () => {
  it("advances clockwise by 90 degrees and cycles through supported angles", () => {
    const view = render(<PageSelectionTool mode="rotate" />);
    const advanceButton = view.getByRole("button", {
      name: i18n.t("rotate.advanceRotation", { angle: 90 }),
    });

    expect(view.getByText(i18n.t("rotate.currentAngle", { angle: 90 }))).toBeTruthy();
    fireEvent.click(advanceButton);
    expect(view.getByText(i18n.t("rotate.currentAngle", { angle: 180 }))).toBeTruthy();
    fireEvent.click(advanceButton);
    expect(view.getByText(i18n.t("rotate.currentAngle", { angle: 270 }))).toBeTruthy();
    fireEvent.click(advanceButton);
    expect(view.getByText(i18n.t("rotate.currentAngle", { angle: 90 }))).toBeTruthy();

    fireEvent.change(view.getByRole("textbox", { name: i18n.t("rotate.pagesFieldLabel") }), {
      target: { value: "2-4, 6" },
    });
    expect(view.getByText(i18n.t("rotate.previewPage", { page: 2 }))).toBeTruthy();
  });
});
