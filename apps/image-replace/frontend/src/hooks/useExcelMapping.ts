import type { TFunction } from "i18next";
import { useRef, useState } from "react";

import {
  imageReplaceApi,
  type ExcelColumnDto,
  type ExcelPieceDto,
} from "../lib/api";
import { MAX_UPLOAD_BYTES } from "../lib/image-processing";

export function useExcelMapping(t: TFunction) {
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [excelSheets, setExcelSheets] = useState<string[]>([]);
  const [excelSheet, setExcelSheet] = useState("");
  const [excelColumns, setExcelColumns] = useState<ExcelColumnDto[]>([]);
  const [excelReferenceColumn, setExcelReferenceColumn] = useState("");
  const [excelReplacementColumn, setExcelReplacementColumn] = useState("");
  const [excelIcnColumn, setExcelIcnColumn] = useState("");
  const [excelPieceColumn, setExcelPieceColumn] = useState("");
  const [excelPieces, setExcelPieces] = useState<ExcelPieceDto[]>([]);
  const [excelPieceRow, setExcelPieceRow] = useState("");
  const [excelError, setExcelError] = useState("");
  const [excelLoading, setExcelLoading] = useState(false);
  const excelRequestId = useRef(0);

  async function chooseExcel(files: File[]) {
    const nextFile = files[0];
    if (!nextFile) return;
    const requestId = ++excelRequestId.current;
    if (!/\.(xlsx|xlsm)$/i.test(nextFile.name)) {
      setExcelLoading(false);
      setExcelError(t("image.errorExcelType"));
      return;
    }
    if (nextFile.size > MAX_UPLOAD_BYTES) {
      setExcelLoading(false);
      setExcelError(t("image.errorExcelSize"));
      return;
    }

    setExcelFile(nextFile);
    setExcelSheets([]);
    setExcelSheet("");
    setExcelColumns([]);
    setExcelReferenceColumn("");
    setExcelReplacementColumn("");
    setExcelIcnColumn("");
    setExcelPieceColumn("");
    setExcelPieces([]);
    setExcelPieceRow("");
    setExcelError("");
    setExcelLoading(true);

    const formData = new FormData();
    formData.append("workbook", nextFile);
    try {
      const payload = await imageReplaceApi.excelSheets(formData);
      if (requestId !== excelRequestId.current) return;
      if (payload.sheets.length === 0) throw new Error("The workbook contains no sheets.");
      setExcelSheets(payload.sheets);
    } catch (requestError) {
      if (requestId === excelRequestId.current) {
        setExcelError(requestError instanceof Error ? requestError.message : t("image.errorGeneric"));
      }
    } finally {
      if (requestId === excelRequestId.current) setExcelLoading(false);
    }
  }

  async function chooseExcelSheet(sheetName: string) {
    const requestId = ++excelRequestId.current;
    setExcelSheet(sheetName);
    setExcelColumns([]);
    setExcelReferenceColumn("");
    setExcelReplacementColumn("");
    setExcelIcnColumn("");
    setExcelPieceColumn("");
    setExcelPieces([]);
    setExcelPieceRow("");
    setExcelError("");
    if (!sheetName || !excelFile) {
      setExcelLoading(false);
      return;
    }

    setExcelLoading(true);
    const formData = new FormData();
    formData.append("workbook", excelFile);
    formData.append("sheet_name", sheetName);
    try {
      const payload = await imageReplaceApi.excelColumns(formData);
      if (requestId === excelRequestId.current) setExcelColumns(payload.columns);
    } catch (requestError) {
      if (requestId === excelRequestId.current) {
        setExcelError(requestError instanceof Error ? requestError.message : t("image.errorGeneric"));
      }
    } finally {
      if (requestId === excelRequestId.current) setExcelLoading(false);
    }
  }

  async function chooseExcelPieceColumn(column: string) {
    const requestId = ++excelRequestId.current;
    setExcelPieceColumn(column);
    setExcelPieces([]);
    setExcelPieceRow("");
    setExcelError("");
    if (!column || !excelFile || !excelSheet) {
      setExcelLoading(false);
      return;
    }

    setExcelLoading(true);
    const formData = new FormData();
    formData.append("workbook", excelFile);
    formData.append("sheet_name", excelSheet);
    formData.append("piece_column", column);
    try {
      const payload = await imageReplaceApi.excelPieces(formData);
      if (requestId === excelRequestId.current) setExcelPieces(payload.pieces);
    } catch (requestError) {
      if (requestId === excelRequestId.current) {
        setExcelError(requestError instanceof Error ? requestError.message : t("image.errorGeneric"));
      }
    } finally {
      if (requestId === excelRequestId.current) setExcelLoading(false);
    }
  }

  function removeExcel() {
    excelRequestId.current += 1;
    setExcelFile(null);
    setExcelSheets([]);
    setExcelSheet("");
    setExcelColumns([]);
    setExcelReferenceColumn("");
    setExcelReplacementColumn("");
    setExcelIcnColumn("");
    setExcelPieceColumn("");
    setExcelPieces([]);
    setExcelPieceRow("");
    setExcelLoading(false);
    setExcelError("");
  }

  const excelSelectionReady =
    !excelFile ||
    Boolean(
      excelSheet &&
        excelReferenceColumn &&
        excelReplacementColumn &&
        excelIcnColumn &&
        excelPieceColumn &&
        excelPieceRow,
    );

  return {
    excelFile,
    excelSheets,
    excelSheet,
    excelColumns,
    excelReferenceColumn,
    excelReplacementColumn,
    excelIcnColumn,
    excelPieceColumn,
    excelPieces,
    excelPieceRow,
    excelError,
    excelLoading,
    excelSelectionReady,
    chooseExcel,
    chooseExcelSheet,
    chooseExcelPieceColumn,
    removeExcel,
    setExcelReferenceColumn,
    setExcelReplacementColumn,
    setExcelIcnColumn,
    setExcelPieceRow,
  };
}
