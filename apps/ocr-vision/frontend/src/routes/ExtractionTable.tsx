import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  extractApi,
  projectTablesApi,
  rowsApi,
  type ColumnSpec,
  type RowDto,
} from "../lib/api";

// Plan de travail d'une table : OCR d'un document -> lignes -> export CSV.
export function ExtractionTable({
  tableId,
  columns,
}: {
  tableId: string;
  columns: ColumnSpec[];
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [targetDir, setTargetDir] = useState("");
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const rowsQuery = useQuery<RowDto[]>({
    queryKey: ["rows", tableId],
    queryFn: () => projectTablesApi.rows(tableId),
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["rows", tableId] });
    void qc.invalidateQueries({ queryKey: ["project-tables"] });
    void qc.invalidateQueries({ queryKey: ["admin", "stats"] });
  };

  const extractMutation = useMutation({
    mutationFn: () => extractApi.run(tableId, file as File),
    onSuccess: (r) => {
      setFeedback(
        r.rows_added
          ? { kind: "ok", text: t("extraction.extractOk", { n: r.rows_added }) }
          : { kind: "error", text: r.warning || t("extraction.extractEmpty") },
      );
      setFile(null);
      invalidate();
    },
    onError: (e: Error) => setFeedback({ kind: "error", text: e.message }),
  });

  const exportMutation = useMutation({
    mutationFn: () => extractApi.export(tableId, targetDir.trim()),
    onSuccess: (r) =>
      setFeedback({ kind: "ok", text: t("extraction.exportOk", { path: r.path, n: r.rows }) }),
    onError: (e: Error) => setFeedback({ kind: "error", text: e.message }),
  });

  const deleteRow = useMutation({
    mutationFn: (id: string) => rowsApi.remove(id),
    onSuccess: invalidate,
  });

  const runExtract = () => {
    setFeedback(null);
    if (!file) {
      setFeedback({ kind: "error", text: t("extraction.noFile") });
      return;
    }
    extractMutation.mutate();
  };

  const runExport = () => {
    setFeedback(null);
    if (!targetDir.trim()) {
      setFeedback({ kind: "error", text: t("extraction.needTarget") });
      return;
    }
    exportMutation.mutate();
  };

  const rows = rowsQuery.data ?? [];

  return (
    <>
      <div className="card">
        <h2 className="card-title">{t("extraction.extractTitle")}</h2>
        <input
          type="file"
          className="input"
          accept="image/*,.pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <div className="row" style={{ marginTop: 10 }}>
          <button
            type="button"
            className="btn primary"
            disabled={extractMutation.isPending}
            onClick={runExtract}
          >
            {extractMutation.isPending ? t("extraction.running") : t("extraction.run")}
          </button>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">
          {t("extraction.rowsTitle")} ({rows.length})
        </h2>
        {rows.length ? (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  {columns.map((c) => (
                    <th key={c.key}>{c.label || c.key}</th>
                  ))}
                  <th>{t("extraction.source")}</th>
                  <th aria-label="actions" />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    {columns.map((c) => (
                      <td key={c.key}>{String(r.values?.[c.key] ?? "")}</td>
                    ))}
                    <td className="file-meta">{r.source_filename}</td>
                    <td>
                      <button
                        type="button"
                        className="btn ghost"
                        onClick={() => deleteRow.mutate(r.id)}
                      >
                        {t("extraction.deleteRow")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">{t("extraction.noRows")}</div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">{t("extraction.exportTitle")}</h2>
        <label>
          <div className="label">{t("extraction.targetDir")}</div>
          <input
            className="input"
            value={targetDir}
            placeholder={t("extraction.targetPlaceholder")}
            onChange={(e) => setTargetDir(e.target.value)}
          />
        </label>
        <div className="row" style={{ marginTop: 10 }}>
          <button
            type="button"
            className="btn secondary"
            disabled={exportMutation.isPending || !rows.length}
            onClick={runExport}
          >
            {t("extraction.export")}
          </button>
        </div>
      </div>

      {feedback ? (
        <div className={feedback.kind === "ok" ? "success" : "error"}>{feedback.text}</div>
      ) : null}
    </>
  );
}
