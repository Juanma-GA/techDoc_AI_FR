import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useDemoMode } from "@internal/ui";

import {
  ApiClientError,
  documentsApi,
  type DocumentDto,
  type DocumentKind,
} from "../lib/api";
import { createMaintenanceDemoStyles } from "../lib/maintenanceDemo";
import { PreviewDropzone } from "./PreviewDropzone";

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

type Props = {
  kind: Exclude<DocumentKind, "source">;
  title: string;
  hint: string;
  accept: string;
};

// Gestion (upload + liste + suppression) d'un kind non-source, skin preview.
export function DocsManagerCard({ kind, title, hint, accept }: Props) {
  const { t } = useTranslation();
  const { mode } = useDemoMode();
  const demoMode = mode === "demo";
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const docsQuery = useQuery<DocumentDto[], ApiClientError>({
    queryKey: ["documents", kind],
    queryFn: () => documentsApi.list(kind),
    enabled: !demoMode,
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["documents", kind] });
    void qc.invalidateQueries({ queryKey: ["documents"] });
  };

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => documentsApi.upload(files, kind),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err: ApiClientError) => setError(err.message),
  });
  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentsApi.remove(id),
    onSuccess: invalidate,
  });

  const demoStyles =
    demoMode && kind === "style"
      ? createMaintenanceDemoStyles(
          t("demo.styles.documentName"),
          t("demo.styles.documentContent"),
        )
      : [];
  const docs = demoMode ? demoStyles : docsQuery.data ?? [];

  return (
    <div className="card">
      <h2 className="card-title">{title}</h2>
      <p style={{ color: "var(--fg-dim)", fontSize: "0.85rem", marginBottom: 10 }}>
        {hint}
      </p>

      {demoMode ? (
        <div className="banner">{t("demo.readOnlyExamples")}</div>
      ) : (
        <>
          <PreviewDropzone
            accept={accept}
            multiple
            disabled={uploadMutation.isPending}
            title={t("settings.docsUploadLabel")}
            hint={accept}
            onFiles={(files) => uploadMutation.mutate(files)}
          />
          {uploadMutation.isPending ? (
            <div className="success">{t("documents.uploading")}</div>
          ) : null}
        </>
      )}
      {error ? <div className="error">{error}</div> : null}

      {docs.length === 0 ? (
        <div className="empty-state">{t("documents.empty")}</div>
      ) : (
        <table className="data-table" style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>{t("documents.columnFilename")}</th>
              <th>{t("documents.columnSize")}</th>
              <th>{t("documents.columnDate")}</th>
              {!demoMode ? (
                <th style={{ textAlign: "right" }}>{t("documents.columnActions")}</th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {docs.map((doc) => (
              <tr key={doc.id}>
                <td className="file-name">{doc.filename}</td>
                <td className="file-meta">{formatSize(doc.size)}</td>
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
  );
}
