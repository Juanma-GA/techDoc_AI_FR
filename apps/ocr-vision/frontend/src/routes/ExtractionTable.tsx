import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  extractApi,
  imagesApi,
  projectTablesApi,
  rowsApi,
  type ColumnSpec,
  type ExportFormat,
  type ImageDto,
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
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const rowsQuery = useQuery<RowDto[]>({
    queryKey: ["rows", tableId],
    queryFn: () => projectTablesApi.rows(tableId),
  });

  const imagesQuery = useQuery<ImageDto[]>({
    queryKey: ["images", tableId],
    queryFn: () => imagesApi.list(tableId),
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["rows", tableId] });
    void qc.invalidateQueries({ queryKey: ["images", tableId] });
    void qc.invalidateQueries({ queryKey: ["project-tables"] });
    void qc.invalidateQueries({ queryKey: ["admin", "stats"] });
  };

  const extractMutation = useMutation({
    mutationFn: () => extractApi.run(tableId, file as File),
    onSuccess: (r) => {
      const imgPart = r.images_added
        ? " " + t("extraction.extractImages", { n: r.images_added })
        : "";
      setFeedback(
        r.rows_added
          ? { kind: "ok", text: t("extraction.extractOk", { n: r.rows_added }) + imgPart }
          : { kind: "error", text: (r.warning || t("extraction.extractEmpty")) + imgPart },
      );
      setFile(null);
      invalidate();
    },
    onError: (e: Error) => setFeedback({ kind: "error", text: e.message }),
  });

  const deleteImage = useMutation({
    mutationFn: (id: string) => imagesApi.remove(id),
    onSuccess: invalidate,
  });

  const exportMutation = useMutation({
    mutationFn: () => extractApi.export(tableId, targetDir.trim(), format),
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
  const images = imagesQuery.data ?? [];

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
        <h2 className="card-title">
          {t("extraction.imagesTitle")} ({images.length})
        </h2>
        {images.length ? (
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            {images.map((img) => (
              <figure
                key={img.id}
                style={{
                  margin: 0,
                  width: 150,
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  overflow: "hidden",
                }}
              >
                <a href={imagesApi.fileUrl(img)} target="_blank" rel="noreferrer">
                  <img
                    src={imagesApi.fileUrl(img)}
                    alt={img.filename}
                    style={{ width: "100%", height: 110, objectFit: "cover", display: "block" }}
                  />
                </a>
                <figcaption
                  className="file-meta"
                  style={{ padding: "4px 6px", display: "flex", justifyContent: "space-between" }}
                >
                  <span>{img.page ? `p.${img.page}` : ""}</span>
                  <button
                    type="button"
                    className="btn ghost"
                    style={{ padding: "0 6px" }}
                    onClick={() => deleteImage.mutate(img.id)}
                  >
                    {t("extraction.deleteRow")}
                  </button>
                </figcaption>
              </figure>
            ))}
          </div>
        ) : (
          <div className="empty-state">{t("extraction.noImages")}</div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">{t("extraction.exportTitle")}</h2>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="grow">
            <div className="label">{t("extraction.targetDir")}</div>
            <input
              className="input"
              value={targetDir}
              placeholder={t("extraction.targetPlaceholder")}
              onChange={(e) => setTargetDir(e.target.value)}
            />
          </label>
          <label>
            <div className="label">{t("extraction.format")}</div>
            <select
              className="input"
              style={{ maxWidth: 140 }}
              value={format}
              onChange={(e) => setFormat(e.target.value as ExportFormat)}
            >
              <option value="csv">CSV</option>
              <option value="xlsx">Excel (.xlsx)</option>
            </select>
          </label>
        </div>
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
