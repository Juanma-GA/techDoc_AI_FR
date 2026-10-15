import type { TFunction } from "i18next";
import { Button, Select } from "@internal/ui";

import type { useExcelMapping } from "../hooks/useExcelMapping";

type ExcelMappingProps = {
  mapping: ReturnType<typeof useExcelMapping>;
  disabled: boolean;
  t: TFunction;
};

export function ExcelMapping({ mapping, disabled, t }: ExcelMappingProps) {
  if (!mapping.excelFile) return null;

  const columnOptions = [
    { value: "", label: t("image.chooseColumn") },
    ...mapping.excelColumns.map((column) => ({
      value: String(column.index),
      label: column.label,
    })),
  ];
  const pieceCounts = new Map<string, number>();
  for (const piece of mapping.excelPieces) {
    pieceCounts.set(piece.name, (pieceCounts.get(piece.name) ?? 0) + 1);
  }

  return (
    <div className="space-y-3 rounded-md border border-md bg-bg-2 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-fg-dim">{t("image.excelMergeHint")}</p>
        <Button
          variant="ghost"
          size="sm"
          disabled={disabled}
          onClick={mapping.removeExcel}
        >
          {t("image.removeExcel")}
        </Button>
      </div>

      <label className="block space-y-1">
        <span className="text-xs text-fg-dim">{t("image.sheet")}</span>
        <Select
          value={mapping.excelSheet}
          disabled={disabled || mapping.excelSheets.length === 0}
          options={[
            { value: "", label: t("image.chooseSheet") },
            ...mapping.excelSheets.map((sheet) => ({ value: sheet, label: sheet })),
          ]}
          onChange={(event) => void mapping.chooseExcelSheet(event.target.value)}
        />
      </label>

      {mapping.excelSheet && mapping.excelColumns.length > 0 ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="space-y-1">
            <span className="text-xs text-fg-dim">{t("image.referenceColumn")}</span>
            <Select
              value={mapping.excelReferenceColumn}
              disabled={disabled}
              options={columnOptions}
              onChange={(event) => mapping.setExcelReferenceColumn(event.target.value)}
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-fg-dim">{t("image.replacementColumn")}</span>
            <Select
              value={mapping.excelReplacementColumn}
              disabled={disabled}
              options={columnOptions}
              onChange={(event) => mapping.setExcelReplacementColumn(event.target.value)}
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-fg-dim">{t("image.icnColumn")}</span>
            <Select
              value={mapping.excelIcnColumn}
              disabled={disabled}
              options={columnOptions}
              onChange={(event) => mapping.setExcelIcnColumn(event.target.value)}
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-fg-dim">{t("image.pieceColumn")}</span>
            <Select
              value={mapping.excelPieceColumn}
              disabled={disabled}
              options={columnOptions}
              onChange={(event) => void mapping.chooseExcelPieceColumn(event.target.value)}
            />
          </label>
          <label className="space-y-1 sm:col-span-2">
            <span className="text-xs text-fg-dim">{t("image.piece")}</span>
            <Select
              value={mapping.excelPieceRow}
              disabled={disabled || !mapping.excelPieceColumn || mapping.excelPieces.length === 0}
              options={[
                { value: "", label: t("image.choosePiece") },
                ...mapping.excelPieces.map((piece) => ({
                  value: String(piece.row),
                  label:
                    (pieceCounts.get(piece.name) ?? 0) > 1
                      ? `${piece.name} — ${piece.row}`
                      : piece.name,
                })),
              ]}
              onChange={(event) => mapping.setExcelPieceRow(event.target.value)}
            />
          </label>
        </div>
      ) : null}

      {mapping.excelLoading ? (
        <p role="status" className="text-sm text-fg-dim">
          {t("image.readingWorkbook")}
        </p>
      ) : null}
      {mapping.excelPieceColumn && !mapping.excelLoading && mapping.excelPieces.length === 0 ? (
        <p className="text-sm text-fg-dim">{t("image.noPieces")}</p>
      ) : null}
      <p className="text-xs leading-relaxed text-fg-dim">{t("image.pieceRule")}</p>
      {mapping.excelError ? (
        <p role="alert" className="rounded-sm border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
          {mapping.excelError}
        </p>
      ) : null}
    </div>
  );
}
