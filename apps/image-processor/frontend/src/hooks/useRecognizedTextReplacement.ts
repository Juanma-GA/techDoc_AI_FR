import { useCallback, type Dispatch, type SetStateAction } from "react";
import type { TFunction } from "i18next";

import { imageReplaceApi, type OcrReferenceDto, type OcrResultDto } from "../lib/api";
import { requestError, type ReplacementPair } from "../lib/workspace-api";
import type { useExcelMapping } from "./useExcelMapping";
import type { useImageDocument } from "./useImageDocument";

type Options = {
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

function referenceKey(value: string) {
  return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toUpperCase().replace(/[^A-Z0-9]/g, "");
}

function updateReferenceResults(
  result: OcrResultDto,
  referenceIndex: number | null,
  lineIndex: number,
  reference: string,
  replacement: string,
  replacementCount: number,
): OcrReferenceDto[] {
  const selected = referenceIndex === null ? undefined : result.references[referenceIndex];
  if (!selected || !selected.line_indices.includes(lineIndex)) {
    return [
      ...result.references,
      { reference, found: true, line_indices: [lineIndex], replacement, replacement_count: replacementCount },
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
      },
    ];
  });
}

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
}: Options) {
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
        ),
        replacement_font_size: rendered.replacement_font_size,
      };
      image.applyTextReplacement(updatedResult);

      const key = referenceKey(reference);
      const candidates = [
        ...manualPairs.map((pair) => ({ source: "manual" as const, pair })),
        ...excel.excelPairs.map((pair) => ({ source: "excel" as const, pair })),
      ].filter(({ pair }) => referenceKey(pair.reference) === key);
      const previousReplacement = referenceIndex === null
        ? ""
        : result.references[referenceIndex]?.replacement ?? "";
      const target = candidates.find(({ pair }) =>
        previousReplacement && pair.replacement.trim() === previousReplacement.trim(),
      ) ?? candidates[0];

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
            id: Math.max(-1, ...current.map((pair) => pair.id)) + 1,
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
