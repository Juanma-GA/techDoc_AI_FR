import type { TFunction } from "i18next";

import type { useExcelMapping } from "../hooks/useExcelMapping";
import type { ReplacementPair } from "./workspace-api";

function enteredPairs(pairs: ReplacementPair[]) {
  return pairs.filter((pair) => pair.enabled)
    .map(({ reference, replacement }) => ({
      reference: reference.trim(), replacement: replacement.trim(),
    })).filter(({ reference, replacement }) => reference || replacement);
}

export function hasValidManualPairs(pairs: ReplacementPair[]) {
  const selected = enteredPairs(pairs);
  return selected.length > 0 && selected.every(({ reference, replacement }) =>
    reference && replacement,
  );
}

function selectedPairs(
  pairs: ReplacementPair[],
  t: TFunction,
  skipEmptyReferences = false,
  comparisonOnly = false,
) {
  const selected = enteredPairs(pairs);
  const applicable = skipEmptyReferences || comparisonOnly
    ? selected.filter(({ reference }) => reference)
    : selected;
  if (applicable.some(({ reference, replacement }) =>
    !reference || (!comparisonOnly && !replacement),
  )) {
    throw new Error(t("image.errorPairIncomplete"));
  }
  return applicable;
}

export function imageForm(
  image: File, sourceName: string,
  excel: ReturnType<typeof useExcelMapping>, t: TFunction,
  includeExcel = true,
): FormData {
  if (includeExcel && excel.excelFile && !excel.excelSelectionReady) {
    throw new Error(t("image.errorExcelSelection"));
  }
  const form = new FormData();
  form.append("image", image, sourceName);
  if (includeExcel && excel.excelFile) {
    form.append("workbook", excel.excelFile);
    form.append("excel_sheet", excel.excelSheet);
    form.append("excel_reference_column", excel.excelReferenceColumn);
    form.append("excel_replacement_column", excel.excelReplacementColumn);
    form.append("excel_icn_column", excel.excelIcnColumn);
    form.append("excel_piece_column", excel.excelPieceColumn);
    form.append("excel_piece_row", excel.excelPieceRow);
  }
  return form;
}

export function analysisForm(
  image: File, sourceName: string, pairs: ReplacementPair[],
  excel: ReturnType<typeof useExcelMapping>, t: TFunction,
  replacementFontSize?: number | null,
  comparisonOnly = false,
): FormData {
  const includeExcel = !excel.excelFile || excel.excelSelectionReady;
  if (!includeExcel && !hasValidManualPairs(pairs)) {
    throw new Error(t("image.errorExcelSelection"));
  }
  const form = imageForm(image, sourceName, excel, t, includeExcel);
  if (replacementFontSize != null) {
    form.append("replacement_font_size", String(replacementFontSize));
  }
  form.append(
    "replacement_pairs",
    JSON.stringify(selectedPairs(pairs, t, false, comparisonOnly)),
  );
  form.append("comparison_only", String(comparisonOnly));
  if (excel.excelFile) {
    form.append(
      "excel_replacement_pairs",
      JSON.stringify(selectedPairs(excel.excelPairs, t, true, comparisonOnly)),
    );
  }
  return form;
}
