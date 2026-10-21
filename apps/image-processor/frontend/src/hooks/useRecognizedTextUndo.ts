import { useCallback } from "react";

import {
  imageReplaceApi,
  type OcrReferenceDto,
  type OcrReferenceUndoDto,
  type OcrResultDto,
} from "../lib/api";
import { requestError } from "../lib/workspace-api";
import { restoreOcrReferenceResults } from "./useImageDocument";
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

function replacementAppliedAtLine(reference: OcrReferenceDto, lineIndex: number) {
  return reference.line_indices
    .slice(0, reference.replacement_count ?? 0)
    .includes(lineIndex);
}

function undoAutomaticLineReplacements(result: OcrResultDto, lineIndex: number): OcrReferenceDto[] {
  return result.references.map((reference) => {
    if (!replacementAppliedAtLine(reference, lineIndex)) return reference;
    return {
      ...reference,
      line_indices: reference.line_indices.filter((index) => index !== lineIndex),
      replacement_count: Math.max(0, (reference.replacement_count ?? 0) - 1),
    };
  });
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
  ): Promise<boolean> => {
    const result = image.result;
    const line = result?.lines[lineIndex];
    let referenceIndex = -1;
    if (result) {
      for (let index = result.references.length - 1; index >= 0; index -= 1) {
        const reference = result.references[index];
        if (reference?.undo && reference.line_indices.includes(lineIndex)) {
          referenceIndex = index;
          break;
        }
      }
    }
    const current = referenceIndex >= 0 ? result?.references[referenceIndex] : undefined;
    const undo = current?.undo;
    if (
      !image.currentFile || !result || !line || !referenceKey(line.text) ||
      (!undo && !result.references.some((reference) => replacementAppliedAtLine(reference, lineIndex))) ||
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
      form.append("reference", undo ? current.reference : line.text);
      form.append("replacement", undo ? undo.previous_image_value : line.text);
      if (result.replacement_font_size != null) {
        form.append("replacement_font_size", String(result.replacement_font_size));
      }
      const rendered = await imageReplaceApi.replaceLine(form);
      const restoredLine = {
        ...line,
        ...(undo ? { matched_references: undo.previous_matched_references } : {}),
      };
      const restoredResult: OcrResultDto = {
        ...result,
        edited_image: rendered.edited_image,
        lines: result.lines.map((item, index) => index === lineIndex ? restoredLine : item),
        references: undo && current
          ? restoreOcrReferenceResults(result, referenceIndex, lineIndex, current)
          : undoAutomaticLineReplacements(result, lineIndex),
        replacement_font_size: rendered.replacement_font_size,
      };
      image.applyTextReplacement(restoredResult);

      if (undo && current) {
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
