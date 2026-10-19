// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import { FileDropzone } from "./FileDropzone";
import { MAX_FILE_SIZE } from "../files";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(cleanup);

function setup(props = {}) {
  const onFiles = vi.fn();
  const onError = vi.fn();
  const view = render(<FileDropzone onFiles={onFiles} onError={onError} {...props} />);
  return { ...view, onFiles, onError };
}

describe("shared dropzone with PDF business validation", () => {
  it("accepts a PDF and resets the input for another selection", () => {
    const view = setup();
    const file = new File(["%PDF-synthetic"], "synthetic.pdf", { type: "application/pdf" });
    const input = view.container.querySelector("input");
    if (!input) throw new Error("Missing file input");
    fireEvent.change(input, { target: { files: [file] } });
    expect(view.onFiles).toHaveBeenCalledWith([file]);
    expect(view.onError).toHaveBeenCalledWith("");
    expect(input.value).toBe("");
  });

  it("rejects a multi-file drop in single-file mode", () => {
    const view = setup();
    const file = new File(["synthetic"], "test.pdf", { type: "application/pdf" });
    fireEvent.drop(view.getByRole("button"), { dataTransfer: { files: [file, file] } });
    expect(view.onFiles).not.toHaveBeenCalled();
    expect(view.onError.mock.calls[0]?.[0]).toBe(i18n.t("files.singleOnly"));
  });

  it("rejects unsupported images and oversized PDFs", () => {
    const image = setup({ fileType: "image" });
    fireEvent.drop(image.getByRole("button"), {
      dataTransfer: { files: [new File(["synthetic"], "test.webp", { type: "image/webp" })] },
    });
    expect(image.onFiles).not.toHaveBeenCalled();
    expect(image.onError).toHaveBeenCalledWith(i18n.t("files.notImage", { name: "test.webp" }));
    cleanup();
    const pdf = setup();
    const large = new File(["synthetic"], "large.pdf", { type: "application/pdf" });
    Object.defineProperty(large, "size", { value: MAX_FILE_SIZE + 1 });
    fireEvent.drop(pdf.getByRole("button"), { dataTransfer: { files: [large] } });
    expect(pdf.onFiles).not.toHaveBeenCalled();
    expect(pdf.onError).toHaveBeenCalledWith(i18n.t("files.tooLarge", { name: "large.pdf" }));
  });

  it("ignores drops while disabled", () => {
    const view = setup({ disabled: true });
    fireEvent.drop(view.getByRole("button"), {
      dataTransfer: { files: [new File(["synthetic"], "test.pdf", { type: "application/pdf" })] },
    });
    expect(view.onFiles).not.toHaveBeenCalled();
    expect(view.getByRole("button").getAttribute("tabindex")).toBe("-1");
  });

  it("renders translated labels and accepts multiple images", async () => {
    await i18n.changeLanguage("fr");
    const view = setup({ fileType: "image", multiple: true });
    const image = new File(["synthetic"], "image.png", { type: "image/png" });
    fireEvent.drop(view.getByRole("button"), { dataTransfer: { files: [image, image] } });
    expect(view.onFiles).toHaveBeenCalledWith([image, image]);
    expect(view.getByText(i18n.t("files.dropLabel"))).toBeTruthy();
  });
});
