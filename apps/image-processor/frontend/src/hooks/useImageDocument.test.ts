import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";
import { storeFile, type WorkspaceSnapshot } from "../lib/workspace-api";
import { emptyPreset, imageData, ocrResult } from "../test/workflow";
import { useImageDocument } from "./useImageDocument";

describe("authoritative image and per-operation undo", () => {
  beforeEach(() => {
    vi.stubGlobal("URL", class extends URL {
      static override createObjectURL() { return "blob:synthetic"; }
      static override revokeObjectURL() {}
    });
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it("chains replacement and both brush modes, then undoes each operation exactly", async () => {
    const { result } = renderHook(() => useImageDocument(i18n.t));
    const original = new File(["synthetic source"], "source.png", { type: "image/png" });
    const icnResult = { ...ocrResult, filename: "ICN-TEST.jpg", replacement_font_size: 24 };
    act(() => { result.current.chooseImage([original]); });
    expect(result.current.currentFile).toBe(original);
    act(() => result.current.applyOcr(icnResult));
    expect((await storeFile(result.current.currentFile!)).data_url).toBe(imageData);
    expect(result.current.currentFile?.name).toBe("ICN-TEST.jpg");

    const brushImage = `data:image/png;base64,${btoa("synthetic brush pixels")}`;
    act(() => result.current.applyBrush(brushImage, "lama"));
    expect((await storeFile(result.current.currentFile!)).data_url).toBe(brushImage);
    expect(result.current.result?.full_text).toBe("R-1");
    expect(result.current.result?.replacement_font_size).toBe(24);
    expect(result.current.currentFile?.name).toBe("ICN-TEST.png");
    expect(result.current.result?.filename).toBe("ICN-TEST.jpg");
    act(() => result.current.applyBrush(imageData, "color"));
    expect((await storeFile(result.current.currentFile!)).data_url).toBe(imageData);
    expect(result.current.currentFile?.name).toBe("ICN-TEST.png");
    expect(result.current.result?.filename).toBe("ICN-TEST.jpg");

    act(() => result.current.undo());
    expect(result.current.result?.replacement_font_size).toBe(24);
    expect((await storeFile(result.current.currentFile!)).data_url).toBe(brushImage);
    act(() => result.current.undo());
    expect(result.current.result).toEqual(icnResult);
    act(() => result.current.undo());
    expect(result.current.currentFile).toBe(original);
    expect(result.current.result).toBeNull();
    expect(result.current.canUndo).toBe(false);
    expect(result.current.document?.operations.map((operation) => operation.kind)).toEqual([
      "ocr", "brush-lama", "brush-color", "undo", "undo", "undo",
    ]);
  });

  it("restores a history image and its undo stack without rerunning inference", async () => {
    const { result } = renderHook(() => useImageDocument(i18n.t));
    const { edited_image, ...analysis } = ocrResult;
    const snapshot: WorkspaceSnapshot = {
      schema_version: 1, image: { name: "original.png", data_url: imageData },
      excel: { ...emptyPreset, pieceRow: "", pairs: [] }, manualPairs: [],
      revisions: [{ kind: "ocr", image: { name: "edited.png", data_url: edited_image }, analysis }],
      operations: [{ kind: "ocr", at: "2026-10-16T10:00:00Z" }],
    };
    act(() => result.current.restore("synthetic-history", snapshot));
    expect(result.current.result).toEqual(ocrResult);
    expect(result.current.canUndo).toBe(true);
    act(() => result.current.undo());
    expect(result.current.currentFile?.name).toBe("original.png");
    expect(result.current.document?.id).toBe("synthetic-history");
  });

  it("rejects invalid files without destroying the current document", () => {
    const { result } = renderHook(() => useImageDocument(i18n.t));
    const source = new File(["source"], "original.png", { type: "image/png" });
    act(() => { result.current.chooseImage([source]); });
    expect(() => result.current.chooseImage([new File(["bad"], "bad.txt", { type: "text/plain" })]))
      .toThrow();
    expect(result.current.currentFile).toBe(source);
  });
});
