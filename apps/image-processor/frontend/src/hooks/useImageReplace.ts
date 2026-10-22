import type { TFunction } from "i18next";
import { useState, type FormEvent } from "react";

import { imageReplaceApi, type OcrResultDto } from "../lib/api";
import { analysisForm } from "../lib/analysis-form";
import { requestError, workspaceApi, type ReplacementPair } from "../lib/workspace-api";
import { useExcelMapping } from "./useExcelMapping";
import { useImageDocument } from "./useImageDocument";
import { useImageDownload } from "./useImageDownload";
import { useRecognizedTextReplacement } from "./useRecognizedTextReplacement";
import { useRecognizedTextUndo } from "./useRecognizedTextUndo";
import { useWorkspaceStorage } from "./useWorkspaceStorage";

export type { ReplacementPair } from "../lib/workspace-api";

export function useImageReplace(t: TFunction) {
  const [replacementPairs, setReplacementPairs] = useState<ReplacementPair[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [retouching, setRetouching] = useState(false);
  const excel = useExcelMapping(t);
  const image = useImageDocument(t);
  const download = useImageDownload({ image, excel, setError, t });
  const storage = useWorkspaceStorage({
    excel: excel.persistenceState, restoreExcel: excel.restoreExcel,
    excelPending: excel.excelLoading || (excel.excelSelectionConfigured && !excel.excelPairsReady),
    document: image.document, manualPairs: replacementPairs,
  });
  const recognizedTextOptions = {
    image, manualPairs: replacementPairs, setManualPairs: setReplacementPairs,
    excel, loading, restoring, downloading: download.downloading, retouching, setLoading, setError, t,
  };
  const replaceRecognizedLine = useRecognizedTextReplacement(recognizedTextOptions);
  const undoRecognizedLine = useRecognizedTextUndo(recognizedTextOptions);

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

  async function reapplyReplacements(resultOverride?: OcrResultDto): Promise<boolean> {
    const result = resultOverride ?? image.result;
    if (!image.imageFile || !result || loading || restoring || retouching) return false;

    const references = result.references
      .map((reference, index) => ({ reference, index }))
      .filter(({ reference }) => reference.replacement);
    if (references.length === 0) return false;

    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("image", image.imageFile, image.imageFile.name);
      form.append(
        "lines_json",
        JSON.stringify(result.lines.map(({ text, box }) => ({ text, box }))),
      );
      form.append(
        "replacement_pairs_json",
        JSON.stringify(references.map(({ reference }) => ({
          reference: reference.reference,
          replacement: reference.replacement,
        }))),
      );
      form.append(
        "broadcast_references_json",
        JSON.stringify(references
          .filter(({ reference }) => (reference.replacement_count ?? 0) > 1)
          .map(({ reference }) => reference.reference)),
      );
      if (result.replacement_font_size != null) {
        form.append("replacement_font_size", String(result.replacement_font_size));
      }
      const rendered = await imageReplaceApi.reapplyReplacements(form);
      const referencesWithCounts = result.references.map((reference, index) => {
        const renderedIndex = references.findIndex((item) => item.index === index);
        const replacementCount = renderedIndex < 0
          ? reference.replacement_count
          : rendered.replacement_counts[renderedIndex];
        return {
          ...reference,
          ...(replacementCount === undefined ? {} : { replacement_count: replacementCount }),
        };
      });
      image.applyTextReplacement({
        ...result,
        edited_image: rendered.edited_image,
        references: referencesWithCounts,
        replacement_font_size: rendered.replacement_font_size,
      });
      return true;
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("image.errorGeneric")));
      return false;
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

  async function retrySave() {
    setError("");
    try {
      await storage.flush();
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("history.saveError")));
    }
  }

  return {
    ...excel, ...image, storage, replacementPairs, error, loading,
    downloading: download.downloading, savingAs: download.savingAs, restoring, retouching,
    setRetouching,
    chooseImage, newImage, updatePair, togglePair, addPair, removePair, submit,
    replaceRecognizedLine, undoRecognizedLine, reapplyReplacements, openHistory,
    downloadImage: download.downloadImage,
    downloadImageAs: download.downloadImageAs,
    retrySave,
  };
}
