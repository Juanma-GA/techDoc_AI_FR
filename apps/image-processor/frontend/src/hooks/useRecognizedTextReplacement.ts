import { useCallback, type Dispatch, type SetStateAction } from "react";
import type { TFunction } from "i18next";

import {
  imageReplaceApi,
  type OcrReferenceUndoDto,
  type OcrResultDto,
} from "../lib/api";
import { requestError, type ReplacementPair } from "../lib/workspace-api";
import type { useExcelMapping } from "./useExcelMapping";
import type { useImageDocument } from "./useImageDocument";
import { referenceKey, updateReferenceResults } from "./useRecognizedTextUndo";

export type RecognizedTextOperationOptions = {
  image: ReturnType<typeof useImageDocument>;
  manualPairs: ReplacementPair[];
  setManualPairs: Dispatch<SetStateAction<ReplacementPair[]>>;
  excel: ReturnType<typeof useExcelMapping>;
  loading: boolean;
  restoring: boolean;
  downloading: boolean;
  retouching: boolean;
  setLoading: Dispatch<SetStateAction<boolean>>;
  setError: Dispatch<SetStateAction<string>>;
  t: TFunction;
};

export function useRecognizedTextReplacement({
  image,
  manualPairs,
  setManualPairs,
  excel,
  loading,
  restoring,
  downloading,
  retouching,
  setLoading,
  setError,
  t,
}: RecognizedTextOperationOptions) {
  return useCallback(async (
    lineIndex: number,
    reference: string,
    value: string,
    referenceIndex: number | null,
  ): Promise<boolean> => {
    const result = image.result;
    const line = result?.lines[lineIndex];
    const replacement = value.trim();
    if (
      !image.currentFile || !result || !line || !referenceKey(reference) || !replacement ||
      loading || restoring || downloading || retouching
    ) {
      setError(t("image.errorLineReplacement"));
      return false;
    }

    const selectedReference = referenceIndex === null
      ? undefined
      : result.references[referenceIndex];
    const previousReference = selectedReference?.line_indices.includes(lineIndex)
      ? selectedReference
      : null;
    const previousImageValue = previousReference &&
      previousReference.line_indices.slice(0, previousReference.replacement_count ?? 0)
        .includes(lineIndex)
      ? previousReference.replacement ?? reference
      : reference;
    const previousReplacement = previousReference?.replacement ?? "";
    const key = referenceKey(reference);
    const candidates = [
      ...manualPairs.map((pair) => ({ source: "manual" as const, pair })),
      ...excel.excelPairs.map((pair) => ({ source: "excel" as const, pair })),
    ].filter(({ pair }) => referenceKey(pair.reference) === key);
    const target = candidates.find(({ pair }) =>
      previousReplacement && pair.replacement.trim() === previousReplacement.trim(),
    ) ?? candidates[0];
    const undo: OcrReferenceUndoDto = {
      previous_image_value: previousImageValue,
      previous_reference_index: previousReference ? referenceIndex : null,
      previous_reference: previousReference ? {
        reference: previousReference.reference,
        found: previousReference.found,
        line_indices: previousReference.line_indices,
        replacement: previousReference.replacement,
        replacement_count: previousReference.replacement_count,
      } : null,
      previous_matched_references: line.matched_references,
      previous_pair_source: target?.source ?? "created",
      previous_pair_id: target?.pair.id ??
        Math.max(-1, ...manualPairs.map((pair) => pair.id)) + 1,
      previous_pair_replacement: target?.pair.replacement ?? "",
      previous_pair_enabled: target?.pair.enabled ?? false,
    };

    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("image", image.currentFile, image.currentFile.name);
      form.append("line_json", JSON.stringify({ text: line.text, box: line.box }));
      form.append("reference", reference);
      form.append("replacement", replacement);
      if (result.replacement_font_size != null) {
        form.append("replacement_font_size", String(result.replacement_font_size));
      }
      const rendered = await imageReplaceApi.replaceLine(form);
      const updatedLine = {
        ...line,
        matched_references: line.matched_references.includes(reference)
          ? line.matched_references
          : [...line.matched_references, reference],
      };
      const updatedResult: OcrResultDto = {
        ...result,
        edited_image: rendered.edited_image,
        lines: result.lines.map((item, index) => index === lineIndex ? updatedLine : item),
        references: updateReferenceResults(
          result,
          referenceIndex,
          lineIndex,
          reference,
          replacement,
          rendered.replacement_count,
          undo,
        ),
        replacement_font_size: rendered.replacement_font_size,
      };
      image.applyTextReplacement(updatedResult);

      if (target?.source === "manual") {
        setManualPairs((current) => current.map((pair) => pair.id === target.pair.id
          ? { ...pair, replacement, enabled: true }
          : pair));
      } else if (target?.source === "excel") {
        excel.updateExcelPair(target.pair.id, "replacement", replacement);
        if (!target.pair.enabled) excel.toggleExcelPair(target.pair.id);
      } else {
        setManualPairs((current) => [
          ...current,
          {
            id: undo.previous_pair_id,
            reference,
            replacement,
            enabled: true,
          },
        ]);
      }
      return true;
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("image.errorGeneric")));
      return false;
    } finally {
      setLoading(false);
    }
  }, [
    downloading,
    excel,
    image,
    loading,
    manualPairs,
    restoring,
    retouching,
    setError,
    setLoading,
    setManualPairs,
    t,
  ]);
}
