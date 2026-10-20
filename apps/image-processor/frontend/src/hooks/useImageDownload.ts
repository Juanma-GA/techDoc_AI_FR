import { useState, type Dispatch, type SetStateAction } from "react";
import type { TFunction } from "i18next";

import { imageReplaceApi } from "../lib/api";
import { imageForm } from "../lib/analysis-form";
import { requestError } from "../lib/workspace-api";
import type { useExcelMapping } from "./useExcelMapping";
import type { useImageDocument } from "./useImageDocument";

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

type Options = {
  image: ReturnType<typeof useImageDocument>;
  excel: ReturnType<typeof useExcelMapping>;
  setError: Dispatch<SetStateAction<string>>;
  t: TFunction;
};

function isSavePickerCancellation(error: unknown) {
  return typeof error === "object" && error !== null &&
    "name" in error && error.name === "AbortError";
}

function createExportForm(
  image: Options["image"],
  excel: Options["excel"],
  t: TFunction,
): FormData {
  if (!image.currentFile || !image.imageFile) {
    throw new Error(t("image.errorGeneric"));
  }
  const form = imageForm(image.currentFile, image.imageFile.name, excel, t);
  if (image.result) form.append("filename", image.result.filename);
  return form;
}

export function useImageDownload({ image, excel, setError, t }: Options) {
  const [saveMode, setSaveMode] = useState<"download" | "saveAs" | null>(null);
  const downloading = saveMode !== null;
  const savingAs = saveMode === "saveAs";

  async function downloadImage() {
    if (!image.currentFile || !image.imageFile || downloading) return;
    setSaveMode("download");
    setError("");
    try {
      const exported = await imageReplaceApi.exportImage(createExportForm(image, excel, t));
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
      const form = createExportForm(image, excel, t);
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

  return { downloading, savingAs, downloadImage, downloadImageAs };
}
