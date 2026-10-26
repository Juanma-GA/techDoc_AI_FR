import { useEffect, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button, Input } from "@internal/ui";
import { createRow, parsePageSelection, type SplitRow } from "./splitModel";

type SplitTableProps = {
  rows: SplitRow[];
  fileNames: string[];
  pageCount: number;
  disabled: boolean;
  onRowsChange: (rows: SplitRow[]) => void;
};

export function SplitTable({ rows, fileNames, pageCount, disabled, onRowsChange }: SplitTableProps) {
  const { t } = useTranslation();
  const [clearArmed, setClearArmed] = useState(false);

  useEffect(() => {
    if (!clearArmed) return;
    const timer = window.setTimeout(() => setClearArmed(false), 3000);
    return () => window.clearTimeout(timer);
  }, [clearArmed]);

  const updateRow = (id: string, patch: Partial<SplitRow>) => {
    onRowsChange(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  };

  return (
    <div className="split-table-section">
      <div className="split-table-scroll">
        <table className="split-table">
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">{t("split.columnPages")}</th>
              <th scope="col">{t("split.columnValue")}</th>
              <th scope="col">{t("split.columnFile")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("split.columnActions")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="split-table-empty">
                  {t("split.tableEmpty")}
                </td>
              </tr>
            ) : null}
            {rows.map((row, index) => {
              const invalidPages = pageCount > 0 && parsePageSelection(row.pages, pageCount) === null;
              return (
                <tr key={row.id}>
                  <td className="split-row-index">{index + 1}</td>
                  <td>
                    <Input
                      className="page-range-input"
                      size="sm"
                      state={invalidPages ? "error" : "default"}
                      value={row.pages}
                      disabled={disabled}
                      placeholder="1-3"
                      aria-label={t("split.rowPages", { index: index + 1 })}
                      aria-invalid={invalidPages}
                      onChange={(event) => updateRow(row.id, { pages: event.currentTarget.value })}
                    />
                  </td>
                                    <td>
                    <Input
                      size="sm"
                      value={row.value}
                      disabled={disabled}
                      placeholder={t("split.valuePlaceholder")}
                      aria-label={t("split.rowValue", { index: index + 1 })}
                      onChange={(event) => updateRow(row.id, { value: event.currentTarget.value })}
                    />
                  </td>
                  <td className="split-file-name" title={fileNames[index]}>
                    {fileNames[index]}
                  </td>
                  <td>
                    <Button
                      variant="ghost"
                      className="icon-button remove-button"
                      disabled={disabled}
                      aria-label={t("split.removeRow", { index: index + 1 })}
                      onClick={() => onRowsChange(rows.filter((item) => item.id !== row.id))}
                    >
                      <X size={15} aria-hidden="true" />
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="split-table-actions">
        <Button
          variant="secondary"
          size="sm"
          disabled={disabled}
          onClick={() => onRowsChange([...rows, createRow()])}
        >
          <Plus size={15} aria-hidden="true" />
          {t("split.addRow")}
        </Button>
        <Button
          variant={clearArmed ? "danger" : "ghost"}
          size="sm"
          disabled={disabled || rows.length === 0}
          onClick={() => {
            if (clearArmed) {
              setClearArmed(false);
              onRowsChange([]);
            } else {
              setClearArmed(true);
            }
          }}
        >
          <Trash2 size={15} aria-hidden="true" />
          {clearArmed ? t("split.clearConfirm") : t("split.clearRows")}
        </Button>
      </div>
    </div>
  );
}
