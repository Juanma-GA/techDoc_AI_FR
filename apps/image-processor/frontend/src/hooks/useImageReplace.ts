import type { TFunction } from "i18next";
import { useState, type FormEvent } from "react";

import { imageReplaceApi } from "../lib/api";
import { analysisForm, imageForm } from "../lib/analysis-form";
import { requestError, workspaceApi, type ReplacementPair } from "../lib/workspace-api";
import { useExcelMapping } from "./useExcelMapping";
import { useImageDocument } from "./useImageDocument";
import { useRecognizedTextReplacement } from "./useRecognizedTextReplacement";
import { useWorkspaceStorage } from "./useWorkspaceStorage";

export type { ReplacementPair } from "../lib/workspace-api";

type SavePickerWindow = Window & {
  showSaveFilePicker?: (options: {
    id: string;
    suggestedName: string;
    types: { description: string; accept: Record<string, string[]> }[];
  }) => Promise<{
    createWritable: () => Promise<{
      write: (data: Blob) => Promise<void>;
      close: () => Promise<void>;
    }>;
  }>;
};

function isSavePickerCancellation(error: unknown) {
  return typeof error === "object" && error !== null &&
    "name" in error && error.name === "AbortError";
}

export function useImageReplace(t: TFunction) {
  const [replacementPairs, setReplacementPairs] = useState<ReplacementPair[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [saveMode, setSaveMode] = useState<"download" | "saveAs" | null>(null);
  const downloading = saveMode !== null;
  const savingAs = saveMode === "saveAs";
  const [restoring, setRestoring] = useState(false);
  const [retouching, setRetouching] = useState(false);
  const excel = useExcelMapping(t);
  const image = useImageDocument(t);
  const storage = useWorkspaceStorage({
    excel: excel.persistenceState, restoreExcel: excel.restoreExcel,
    excelPending: excel.excelLoading || (excel.excelSelectionConfigured && !excel.excelPairsReady),
    document: image.document, manualPairs: replacementPairs,
  });
  const replaceRecognizedLine = useRecognizedTextReplacement({
    image, manualPairs: replacementPairs, setManualPairs: setReplacementPairs,
    excel, loading, restoring, downloading, retouching, setLoading, setError, t,
  });

  async function chooseImage(files: File[]) {
    setRestoring(true);
    setError("");
    try {
      await storage.flush();
      if (image.chooseImage(files)) {
        setReplacementPairs([]);
        excel.resetPiece();
        return true;
      }
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("image.errorGeneric")));
      return false;
    } finally {
      setRestoring(false);
    }
  }

  async function newImage() {
    setRestoring(true);
    setError("");
    try {
      await storage.flush();
      image.clear();
      setReplacementPairs([]);
      excel.resetPiece();
      return true;
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("image.errorGeneric")));
      return false;
    } finally {
      setRestoring(false);
    }
  }

  function updatePair(id: number, field: "reference" | "replacement", value: string) {
    setReplacementPairs((current) =>
      current.map((pair) => pair.id === id ? { ...pair, [field]: value } : pair),
    );
  }
  function togglePair(id: number) {
    setReplacementPairs((current) =>
      current.map((pair) => pair.id === id ? { ...pair, enabled: !pair.enabled } : pair),
    );
  }
  function addPair() {
    setReplacementPairs((current) => [
      ...current, {
        id: Math.max(-1, ...current.map((pair) => pair.id)) + 1,
        reference: "", replacement: "", enabled: true,
      },
    ]);
  }
  function removePair(id: number) {
    setReplacementPairs((current) => current.filter((pair) => pair.id !== id));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!image.currentFile || !image.imageFile || loading || restoring) return;
    setLoading(true);
    setError("");
    try {
      const form = analysisForm(
        image.currentFile, image.imageFile.name, replacementPairs, excel, t,
        image.result?.replacement_font_size,
      );
      image.applyOcr(await imageReplaceApi.runOcr(form));
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("image.errorGeneric")));
    } finally {
      setLoading(false);
    }
  }

  async function openHistory(id: string) {
    setRestoring(true);
    setError("");
    try {
      await storage.flush();
      const entry = await workspaceApi.read(id);
      excel.restoreExcel(entry.state.excel);
      setReplacementPairs(entry.state.manualPairs);
      image.restore(id, entry.state);
      return true;
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("history.loadError")));
      return false;
    } finally {
      setRestoring(false);
    }
  }

  async function downloadImage() {
    if (!image.currentFile || !image.imageFile || downloading) return;
    setSaveMode("download");
    setError("");
    try {
      const form = imageForm(image.currentFile, image.imageFile.name, excel, t);
      if (image.result) form.append("filename", image.result.filename);
      const exported = await imageReplaceApi.exportImage(form);
      const url = URL.createObjectURL(exported.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = exported.filename;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("image.errorGeneric")));
    } finally {
      setSaveMode(null);
    }
  }

  async function downloadImageAs() {
    if (!image.currentFile || !image.imageFile || downloading) return;
    const pickerWindow = window as SavePickerWindow;
    if (!pickerWindow.showSaveFilePicker) {
      setError(t("image.errorSaveAsUnsupported"));
      return;
    }

    setSaveMode("saveAs");
    setError("");
    try {
      const form = imageForm(image.currentFile, image.imageFile.name, excel, t);
      if (image.result) form.append("filename", image.result.filename);
      const suggestedName = image.result?.filename ??
        `${image.imageFile.name.replace(/\.[^.]+$/, "")}.jpg`;
      const handle = await pickerWindow.showSaveFilePicker({
        id: "image-processor-export",
        suggestedName,
        types: [{ description: t("image.jpegFileType"), accept: { "image/jpeg": [".jpg"] } }],
      });
      const exported = await imageReplaceApi.exportImage(form);
      const writable = await handle.createWritable();
      await writable.write(exported.blob);
      await writable.close();
    } catch (requestFailure) {
      if (!isSavePickerCancellation(requestFailure)) {
        setError(requestError(requestFailure, t("image.errorGeneric")));
      }
    } finally {
      setSaveMode(null);
    }
  }

  async function retrySave() {
    setError("");
    try {
      await storage.flush();
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("history.saveError")));
    }
  }

  return {
    ...excel, ...image, storage, replacementPairs, error, loading, downloading, savingAs, restoring, retouching,
    setRetouching,
    chooseImage, newImage, updatePair, togglePair, addPair, removePair, submit,
    replaceRecognizedLine, openHistory, downloadImage, downloadImageAs, retrySave,
  };
}
