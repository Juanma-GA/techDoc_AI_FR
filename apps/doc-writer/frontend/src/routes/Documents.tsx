import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useDemoMode } from "@internal/ui";

import { PreviewDropzone } from "../components/PreviewDropzone";
import { ApiClientError, documentsApi, type DocumentDto } from "../lib/api";
import {
  createMaintenanceDemoFiles,
  createMaintenanceDemoStyles,
  createMaintenanceDemoTemplates,
} from "../lib/maintenanceDemo";

const ACCEPT = ".pdf,.docx,.pptx,.xlsx,.xlsm,.txt,.md";

function formatSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}
function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

// Page Documents, pixel-identique au preview (sources uniquement : upload +
// liste + suppression).
export function Documents() {
  const { t } = useTranslation();
  const { mode } = useDemoMode();
  const demoMode = mode === "demo";
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const docsQuery = useQuery<DocumentDto[], ApiClientError>({
    queryKey: ["documents", "source"],
    queryFn: () => documentsApi.list("source"),
    enabled: !demoMode,
  });

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => documentsApi.upload(files, "source"),
    onSuccess: () => {
      setError(null);
      void qc.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (err: ApiClientError) => setError(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  const documents = demoMode
    ? createMaintenanceDemoFiles({
        conveyor: {
          fileName: t("demo.scenarios.conveyor.fileName"),
          fileContent: t("demo.scenarios.conveyor.fileContent"),
          output: t("demo.scenarios.conveyor.output"),
        },
        pump: {
          fileName: t("demo.scenarios.pump.fileName"),
          fileContent: t("demo.scenarios.pump.fileContent"),
          output: t("demo.scenarios.pump.output"),
        },
      })
    : docsQuery.data ?? [];
  const demoTemplates = demoMode
    ? createMaintenanceDemoTemplates({
        "service-report": t("demo.templates.serviceReport.name"),
        "inspection-checklist": t("demo.templates.inspectionChecklist.name"),
      })
    : [];
  const demoStyles = demoMode
    ? createMaintenanceDemoStyles(
        t("demo.styles.documentName"),
        t("demo.styles.documentContent"),
      )
    : [];

  return (
    <>
      <div className="page-header">
        <h1>{t("documents.title")}</h1>
        <p>{t("documents.subtitle")}</p>
      </div>

      <div className="banner">
        {demoMode ? (
          <>{t("demo.documentsHint")}</>
        ) : (
          <>
            <strong>{t("documents.sourcesOnly")}</strong> {t("documents.sourcesHint")}
          </>
        )}
      </div>

      {demoMode ? null : (
        <div className="card">
          <h2 className="card-title">{t("documents.uploadLabel")}</h2>
          <PreviewDropzone
            accept={ACCEPT}
            multiple
            disabled={uploadMutation.isPending}
            title={t("documents.uploadLabel")}
            hint={t("documents.uploadDescription")}
            onFiles={(files) => uploadMutation.mutate(files)}
          />
          {uploadMutation.isPending ? (
            <div className="success">{t("documents.uploading")}</div>
          ) : null}
          {error ? <div className="error">{error}</div> : null}
        </div>
      )}

      <div className="card">
        <h2 className="card-title">{t("documents.title")}</h2>
        {documents.length === 0 ? (
          <div className="empty-state">{t("documents.empty")}</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("documents.columnFilename")}</th>
                <th>{t("documents.columnSize")}</th>
                <th>{t("documents.columnChunks")}</th>
                <th>{t("documents.columnDate")}</th>
                {!demoMode ? (
                  <th style={{ textAlign: "right" }}>
                    {t("documents.columnActions")}
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td className="file-name">{doc.filename}</td>
                  <td className="file-meta">{formatSize(doc.size)}</td>
                  <td>
                    {doc.index_error ? (
                      <span className="badge warn">
                        {t("documents.indexErrorBadge")}
                      </span>
                    ) : (
                      <span className="badge ok">{doc.chunk_count}</span>
                    )}
                  </td>
                  <td className="file-meta">{formatDate(doc.uploaded_at)}</td>
                  {!demoMode ? (
                    <td style={{ textAlign: "right" }}>
                      <button
                        type="button"
                        className="btn ghost small"
                        disabled={deleteMutation.isPending}
                        onClick={() => deleteMutation.mutate(doc.id)}
                      >
                        {t("documents.delete")}
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {demoMode ? (
        <>
          <div className="card">
            <h2 className="card-title">{t("demo.templates.title")}</h2>
            <ul className="doc-checklist">
              {demoTemplates.map((template) => (
                <li key={template.id}>{template.filename}</li>
              ))}
            </ul>
          </div>
          <div className="card">
            <h2 className="card-title">{t("demo.styles.title")}</h2>
            <ul className="doc-checklist">
              {demoStyles.map((style) => (
                <li key={style.id}>{style.filename}</li>
              ))}
            </ul>
          </div>
        </>
      ) : null}
    </>
  );
}
