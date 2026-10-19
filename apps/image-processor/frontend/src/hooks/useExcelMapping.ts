import type { TFunction } from "i18next";
import { useCallback, useMemo, useRef, useState } from "react";

import { imageReplaceApi } from "../lib/api";
import { MAX_UPLOAD_BYTES } from "../lib/image-processing";
import { restoreFile, type ExcelSnapshot } from "../lib/workspace-api";
import { useExcelPairs, type RestoredExcelPairs } from "./useExcelPairs";

export type ExcelMemorySnapshot = Omit<ExcelSnapshot, "workbook"> & { workbook: File | null };
type MappingState = Omit<ExcelMemorySnapshot, "pairs">;
const EMPTY: MappingState = {
  workbook: null, sheets: [], sheet: "", columns: [], referenceColumn: "",
  replacementColumn: "", icnColumn: "", pieceColumn: "", pieces: [], pieceRow: "",
};

export function useExcelMapping(t: TFunction) {
  const [state, setState] = useState<MappingState>(EMPTY);
  const [excelError, setExcelError] = useState("");
  const [excelLoading, setExcelLoading] = useState(false);
  const [restored, setRestored] = useState<RestoredExcelPairs | null>(null);
  const requestId = useRef(0);
  const selection = {
    workbook: state.workbook, sheet: state.sheet,
    referenceColumn: state.referenceColumn, replacementColumn: state.replacementColumn,
    icnColumn: state.icnColumn, pieceColumn: state.pieceColumn, pieceRow: state.pieceRow,
  };
  const preview = useExcelPairs(selection, t, setExcelError, restored);
  const persistenceState = useMemo(
    () => ({ ...state, pairs: preview.pairs }), [state, preview.pairs],
  );

  async function load(run: (currentRequest: number) => Promise<void>) {
    const currentRequest = ++requestId.current;
    setExcelError("");
    setExcelLoading(true);
    try {
      await run(currentRequest);
    } catch (error) {
      if (currentRequest === requestId.current) {
        setExcelError(error instanceof Error ? error.message : t("image.errorGeneric"));
      }
    } finally {
      if (currentRequest === requestId.current) setExcelLoading(false);
    }
  }

  async function chooseExcel(files: File[]) {
    const file = files[0];
    if (!file) return;
    if (!/\.(xlsx|xlsm)$/i.test(file.name) || file.size > MAX_UPLOAD_BYTES) {
      setExcelError(t(file.size > MAX_UPLOAD_BYTES ? "image.errorExcelSize" : "image.errorExcelType"));
      return;
    }
    setRestored(null);
    setState({ ...EMPTY, workbook: file });
    await load(async (currentRequest) => {
      const form = new FormData();
      form.append("workbook", file);
      const payload = await imageReplaceApi.excelSheets(form);
      if (payload.sheets.length === 0) throw new Error(t("image.errorExcelSheets"));
      if (currentRequest === requestId.current) {
        setState((current) => ({ ...current, sheets: payload.sheets }));
      }
    });
  }

  async function chooseExcelSheet(sheet: string) {
    setRestored(null);
    setState((current) => ({ ...EMPTY, workbook: current.workbook, sheets: current.sheets, sheet }));
    if (!sheet || !state.workbook) {
      requestId.current += 1;
      setExcelLoading(false);
      return;
    }
    await load(async (currentRequest) => {
      const form = new FormData();
      form.append("workbook", state.workbook!);
      form.append("sheet_name", sheet);
      const payload = await imageReplaceApi.excelColumns(form);
      if (currentRequest === requestId.current) {
        setState((current) => ({ ...current, columns: payload.columns }));
      }
    });
  }

  async function chooseExcelPieceColumn(
    column: string,
    referenceColumn = state.referenceColumn,
    replacementColumn = state.replacementColumn,
  ) {
    setRestored(null);
    setState((current) => ({ ...current, pieceColumn: column, pieces: [], pieceRow: "" }));
    if (!column || !referenceColumn || !replacementColumn || !state.workbook || !state.sheet) {
      requestId.current += 1;
      setExcelLoading(false);
      return;
    }
    await load(async (currentRequest) => {
      const form = new FormData();
      form.append("workbook", state.workbook!);
      form.append("sheet_name", state.sheet);
      form.append("reference_column", referenceColumn);
      form.append("replacement_column", replacementColumn);
      form.append("piece_column", column);
      const payload = await imageReplaceApi.excelPieces(form);
      if (currentRequest === requestId.current) {
        setState((current) => ({ ...current, pieces: payload.pieces }));
      }
    });
  }

  function setExcelReferenceColumn(referenceColumn: string) {
    setState((current) => ({ ...current, referenceColumn, pieceRow: "" }));
    setExcelError("");
    if (state.pieceColumn) void chooseExcelPieceColumn(state.pieceColumn, referenceColumn);
  }

  function setExcelReplacementColumn(replacementColumn: string) {
    setState((current) => ({ ...current, replacementColumn, pieces: [], pieceRow: "" }));
    setExcelError("");
    if (state.pieceColumn) {
      void chooseExcelPieceColumn(state.pieceColumn, state.referenceColumn, replacementColumn);
    }
  }

  const restoreExcel = useCallback((snapshot: ExcelSnapshot) => {
    requestId.current += 1;
    const { workbook: stored, pairs, ...mapping } = snapshot;
    const workbook = stored ? restoreFile(stored) : null;
    setRestored({ selection: { ...mapping, workbook }, pairs });
    setState({ ...mapping, workbook });
    setExcelError("");
    setExcelLoading(false);
  }, []);

  function removeExcel() {
    requestId.current += 1;
    setRestored(null);
    setState(EMPTY);
    setExcelError("");
    setExcelLoading(false);
  }

  function resetPiece() {
    setRestored(null);
    setState((current) => ({ ...current, pieceRow: "" }));
  }

  const configured = Boolean(
    state.workbook && state.sheet && state.referenceColumn && state.replacementColumn &&
    state.icnColumn && state.pieceColumn && state.pieceRow,
  );
  return {
    persistenceState, restoreExcel, resetPiece,
    excelFile: state.workbook, excelSheets: state.sheets, excelSheet: state.sheet,
    excelColumns: state.columns, excelReferenceColumn: state.referenceColumn,
    excelReplacementColumn: state.replacementColumn, excelIcnColumn: state.icnColumn,
    excelPieceColumn: state.pieceColumn, excelPieces: state.pieces, excelPieceRow: state.pieceRow,
    excelError, excelLoading, excelPairs: preview.pairs, excelPairsLoading: preview.loading,
    excelPairsReady: preview.ready, excelSelectionConfigured: configured,
    excelSelectionReady: !state.workbook || (configured && preview.ready),
    chooseExcel, chooseExcelSheet, chooseExcelPieceColumn, removeExcel, setExcelReferenceColumn,
    setExcelReplacementColumn,
    setExcelIcnColumn: (icnColumn: string) => setState((current) => ({ ...current, icnColumn })),
    setExcelPieceRow: (pieceRow: string) => {
      setRestored(null);
      setState((current) => ({ ...current, pieceRow }));
    },
    updateExcelPair: preview.updatePair, removeExcelPair: preview.removePair,
    toggleExcelPair: preview.togglePair,
  };
}
