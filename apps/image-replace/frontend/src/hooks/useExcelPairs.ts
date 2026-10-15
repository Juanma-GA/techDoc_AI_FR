import type { TFunction } from "i18next";
import { useEffect, useRef, useState } from "react";

import { imageReplaceApi, type ExcelReplacementPairDto } from "../lib/api";

export type EditableExcelPair = ExcelReplacementPairDto & { id: number };

export type ExcelPairSelection = {
  workbook: File | null;
  sheet: string;
  referenceColumn: string;
  replacementColumn: string;
  icnColumn: string;
  pieceColumn: string;
  pieceRow: string;
};

function matchesSelection(
  loaded: ExcelPairSelection | null,
  current: ExcelPairSelection,
): boolean {
  return Boolean(
    loaded &&
      loaded.workbook === current.workbook &&
      loaded.sheet === current.sheet &&
      loaded.referenceColumn === current.referenceColumn &&
      loaded.replacementColumn === current.replacementColumn &&
      loaded.icnColumn === current.icnColumn &&
      loaded.pieceColumn === current.pieceColumn &&
      loaded.pieceRow === current.pieceRow,
  );
}

export function useExcelPairs(
  selection: ExcelPairSelection,
  t: TFunction,
  setError: (message: string) => void,
) {
  const [pairs, setPairs] = useState<EditableExcelPair[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadedSelection, setLoadedSelection] = useState<ExcelPairSelection | null>(null);
  const requestId = useRef(0);
  const nextPairId = useRef(0);

  const {
    workbook,
    sheet,
    referenceColumn,
    replacementColumn,
    icnColumn,
    pieceColumn,
    pieceRow,
  } = selection;
  const selectionComplete = Boolean(
    workbook && sheet && referenceColumn && replacementColumn && icnColumn && pieceColumn && pieceRow,
  );
  const loadedForCurrentSelection = selectionComplete && matchesSelection(loadedSelection, selection);

  useEffect(() => {
    const currentRequestId = ++requestId.current;
    if (!selectionComplete || !workbook) {
      setPairs([]);
      setLoadedSelection(null);
      setLoading(false);
      setError("");
      return undefined;
    }

    const currentSelection = {
      workbook,
      sheet,
      referenceColumn,
      replacementColumn,
      icnColumn,
      pieceColumn,
      pieceRow,
    };
    setPairs([]);
    setLoadedSelection(null);
    setLoading(true);
    setError("");

    const formData = new FormData();
    formData.append("workbook", workbook);
    formData.append("excel_sheet", sheet);
    formData.append("excel_reference_column", referenceColumn);
    formData.append("excel_replacement_column", replacementColumn);
    formData.append("excel_icn_column", icnColumn);
    formData.append("excel_piece_column", pieceColumn);
    formData.append("excel_piece_row", pieceRow);

    void imageReplaceApi
      .excelPairs(formData)
      .then((payload) => {
        if (currentRequestId !== requestId.current) return;
        setPairs(
          payload.pairs.map((pair) => ({
            ...pair,
            id: nextPairId.current++,
          })),
        );
        setLoadedSelection(currentSelection);
      })
      .catch((requestError: unknown) => {
        if (currentRequestId === requestId.current) {
          setError(
            requestError instanceof Error ? requestError.message : t("image.errorGeneric"),
          );
        }
      })
      .finally(() => {
        if (currentRequestId === requestId.current) setLoading(false);
      });

    return () => {
      if (currentRequestId === requestId.current) requestId.current += 1;
    };
  }, [
    workbook,
    sheet,
    referenceColumn,
    replacementColumn,
    icnColumn,
    pieceColumn,
    pieceRow,
    selectionComplete,
    setError,
    t,
  ]);

  function updatePair(id: number, field: "reference" | "replacement", value: string) {
    setPairs((current) =>
      current.map((pair) => (pair.id === id ? { ...pair, [field]: value } : pair)),
    );
  }

  function removePair(id: number) {
    setPairs((current) => current.filter((pair) => pair.id !== id));
  }

  return {
    pairs: loadedForCurrentSelection ? pairs : [],
    loading: selectionComplete && loading,
    ready: !workbook || loadedForCurrentSelection,
    updatePair,
    removePair,
  };
}
