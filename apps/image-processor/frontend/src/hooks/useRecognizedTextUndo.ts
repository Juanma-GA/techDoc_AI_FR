import { useCallback } from "react";

import {
  imageReplaceApi,
  type OcrReferenceDto,
  type OcrReferenceUndoDto,
  type OcrResultDto,
} from "../lib/api";
import { requestError } from "../lib/workspace-api";
import type { RecognizedTextOperationOptions } from "./useRecognizedTextReplacement";

export function referenceKey(value: string) {
  return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toUpperCase().replace(/[^A-Z0-9]/g, "");
}

export function updateReferenceResults(
  result: OcrResultDto,
  referenceIndex: number | null,
  lineIndex: number,
  reference: string,
  replacement: string,
  replacementCount: number,
  undo: OcrReferenceUndoDto,
): OcrReferenceDto[] {
  const selected = referenceIndex === null ? undefined : result.references[referenceIndex];
  if (!selected || !selected.line_indices.includes(lineIndex)) {
    return [
      ...result.references,
      {
        reference, found: true, line_indices: [lineIndex], replacement,
        replacement_count: replacementCount, undo,
      },
    ];
  }

  const remainingLines = selected.line_indices.filter((index) => index !== lineIndex);
  const previouslyReplaced = selected.line_indices
    .slice(0, selected.replacement_count ?? 0)
    .includes(lineIndex);
  const remainingReplacementCount = Math.max(
    0,
    (selected.replacement_count ?? 0) - Number(previouslyReplaced),
  );
  return result.references.flatMap((item, index) => {
    if (index !== referenceIndex) return [item];
    return [
      ...(remainingLines.length > 0
        ? [{
            ...selected,
            found: true,
            line_indices: remainingLines,
            replacement_count: remainingReplacementCount,
          }]
        : []),
      {
        ...selected,
        found: true,
        line_indices: [lineIndex],
        replacement,
        replacement_count: replacementCount,
        undo,
      },
    ];
  });
}

function sameIndices(left: number[], right: number[]) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function restoreReferenceResults(
  result: OcrResultDto,
  referenceIndex: number,
  lineIndex: number,
  current: OcrReferenceDto,
): OcrReferenceDto[] {
  const undo = current.undo;
  if (!undo) return result.references;
  if (!undo.previous_reference) {
    return result.references.filter((_, index) => index !== referenceIndex);
  }

  const previous = undo.previous_reference;
  const remainingLines = previous.line_indices.filter((index) => index !== lineIndex);
  const remainderIndex = remainingLines.length > 0
    ? result.references.findIndex((item, index) =>
        index !== referenceIndex &&
        item.reference === previous.reference &&
        sameIndices(item.line_indices, remainingLines) &&
        (item.replacement ?? "") === (previous.replacement ?? ""),
      )
    : -1;
  const restored = result.references.filter(
    (_, index) => index !== referenceIndex && index !== remainderIndex,
  );
  const insertionIndex = Math.min(undo.previous_reference_index ?? restored.length, restored.length);
  restored.splice(insertionIndex, 0, previous);
  return restored;
}

export function useRecognizedTextUndo({
  image,
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
    referenceIndex: number,
  ): Promise<boolean> => {
    const result = image.result;
    const line = result?.lines[lineIndex];
    const current = result?.references[referenceIndex];
    const undo = current?.undo;
    if (
      !image.currentFile || !result || !line || !current || !undo ||
      loading || restoring || downloading || retouching
    ) {
      setError(t("image.errorUndoLineReplacement"));
      return false;
    }

    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("image", image.currentFile, image.currentFile.name);
      form.append("line_json", JSON.stringify({ text: line.text, box: line.box }));
      form.append("reference", current.reference);
      form.append("replacement", undo.previous_image_value);
      if (result.replacement_font_size != null) {
        form.append("replacement_font_size", String(result.replacement_font_size));
      }
      const rendered = await imageReplaceApi.replaceLine(form);
      const restoredLine = {
        ...line,
        matched_references: undo.previous_matched_references,
      };
      const restoredResult: OcrResultDto = {
        ...result,
        edited_image: rendered.edited_image,
        lines: result.lines.map((item, index) => index === lineIndex ? restoredLine : item),
        references: restoreReferenceResults(result, referenceIndex, lineIndex, current),
        replacement_font_size: rendered.replacement_font_size,
      };
      image.applyTextReplacement(restoredResult);

      const reference = referenceKey(current.reference);
      if (undo.previous_pair_source === "created") {
        setManualPairs((pairs) => pairs.filter((pair) =>
          pair.id !== undo.previous_pair_id ||
          referenceKey(pair.reference) !== reference ||
          pair.replacement.trim() !== (current.replacement ?? "").trim(),
        ));
      } else if (undo.previous_pair_source === "manual") {
        setManualPairs((pairs) => pairs.map((pair) =>
          pair.id === undo.previous_pair_id &&
          pair.replacement.trim() === (current.replacement ?? "").trim()
            ? {
                ...pair,
                replacement: undo.previous_pair_replacement,
                enabled: undo.previous_pair_enabled,
              }
            : pair,
        ));
      } else {
        const pair = excel.excelPairs.find((item) => item.id === undo.previous_pair_id);
        if (pair && pair.replacement.trim() === (current.replacement ?? "").trim()) {
          excel.updateExcelPair(pair.id, "replacement", undo.previous_pair_replacement);
          if (pair.enabled !== undo.previous_pair_enabled) excel.toggleExcelPair(pair.id);
        }
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
    restoring,
    retouching,
    setError,
    setLoading,
    setManualPairs,
    t,
  ]);
}
