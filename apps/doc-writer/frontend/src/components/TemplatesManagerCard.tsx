import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useDemoMode } from "@internal/ui";

import { ApiClientError, documentsApi, type DocumentDto } from "../lib/api";
import { createMaintenanceDemoTemplates } from "../lib/maintenanceDemo";
import { PreviewDropzone } from "./PreviewDropzone";
import { ZonesManagerPanel } from "./ZonesManagerPanel";

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

// Gestion des templates (upload + liste + Reanalyser + Gerer les zones), skin
// preview. Le panneau de zones s'ouvre inline sous la liste.
export function TemplatesManagerCard() {
  const { t } = useTranslation();
  const { mode } = useDemoMode();
  const demoMode = mode === "demo";
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [managed, setManaged] = useState<{ id: string; filename: string } | null>(
    null,
  );

  const templatesQuery = useQuery<DocumentDto[], ApiClientError>({
    queryKey: ["documents", "template"],
    queryFn: () => documentsApi.list("template"),
    enabled: !demoMode,
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["documents", "template"] });
    void qc.invalidateQueries({ queryKey: ["documents"] });
  };

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => documentsApi.upload(files, "template"),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err: ApiClientError) => setError(err.message),
  });
  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentsApi.remove(id),
    onSuccess: (_d, id) => {
      if (managed?.id === id) setManaged(null);
      invalidate();
    },
  });
  const reanalyseMutation = useMutation({
    mutationFn: (id: string) => documentsApi.reanalyseZones(id),
    onSuccess: (data, id) => {
      setNotice(t("settings.reanalyseDone", { n: data.zones.length }));
      qc.setQueryData(["documents", id, "zones"], data);
    },
    onError: (err: ApiClientError) => setError(err.message),
  });
  // Confirmation double-clic (regle #13 : jamais de popup natif) : la
  // reanalyse touche un template deja configure (labels/consignes/corbeille),
  // meme si le backend les preserve desormais par zone inchangee — un clic
  // seul reste une action a confirmer.
  const [reanalyseArmed, setReanalyseArmed] = useState<string | null>(null);

  const demoTemplates = demoMode
    ? createMaintenanceDemoTemplates({
        "service-report": t("demo.templates.serviceReport.name"),
        "inspection-checklist": t("demo.templates.inspectionChecklist.name"),
      })
    : [];
  const templates = demoMode ? demoTemplates : templatesQuery.data ?? [];

  return (
    <div className="card">
      <h2 className="card-title">{t("settings.templateDocsTitle")}</h2>
      <p style={{ color: "var(--fg-dim)", fontSize: "0.85rem", marginBottom: 10 }}>
        {t("settings.templateDocsHint")}
      </p>

      {demoMode ? (
        <div className="banner">{t("demo.readOnlyExamples")}</div>
      ) : (
        <>
          <PreviewDropzone
            accept=".pptx,.docx,.pdf"
            multiple
            disabled={uploadMutation.isPending}
            title={t("settings.docsUploadLabel")}
            hint=".pptx, .docx, .pdf"
            onFiles={(files) => uploadMutation.mutate(files)}
          />
          {uploadMutation.isPending ? (
            <div className="success">{t("documents.uploading")}</div>
          ) : null}
          {reanalyseMutation.isPending ? (
            <div className="success">{t("settings.reanalyseRunning")}</div>
          ) : null}
        </>
      )}
      {notice ? <div className="success">{notice}</div> : null}
      {error ? <div className="error">{error}</div> : null}

      {templates.length === 0 ? (
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
            {templates.map((doc) => {
              // Reanalyser + Gerer les zones : tous les formats de template
              // exposent des zones (.pptx natif, .docx, .pdf converti -> .docx).
              const name = doc.filename.toLowerCase();
              const canManageZones =
                name.endsWith(".pptx") ||
                name.endsWith(".docx") ||
                name.endsWith(".pdf");
              return (
                <tr key={doc.id}>
                  <td className="file-name">{doc.filename}</td>
                  <td className="file-meta">{formatSize(doc.size)}</td>
                  <td className="file-meta">{formatDate(doc.uploaded_at)}</td>
                  {!demoMode ? (
                    <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      {canManageZones ? (
                      <>
                        <button
                          type="button"
                          className={`btn small ${reanalyseArmed === doc.id ? "danger" : "secondary"}`}
                          style={{ marginRight: 4 }}
                          disabled={reanalyseMutation.isPending}
                          onClick={() => {
                            if (reanalyseArmed !== doc.id) {
                              setReanalyseArmed(doc.id);
                              setTimeout(
                                () => setReanalyseArmed((c) => (c === doc.id ? null : c)),
                                3000,
                              );
                              return;
                            }
                            setReanalyseArmed(null);
                            setNotice(null);
                            setError(null);
                            reanalyseMutation.mutate(doc.id);
                          }}
                        >
                          {reanalyseArmed === doc.id ? t("data.confirmAgain") : t("settings.reanalyse")}
                        </button>
                        <button
                          type="button"
                          className="btn secondary small"
                          style={{ marginRight: 4 }}
                          onClick={() =>
                            setManaged({ id: doc.id, filename: doc.filename })
                          }
                        >
                          {t("settings.manageZones")}
                        </button>
                      </>
                      ) : null}
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
              );
            })}
          </tbody>
        </table>
      )}

      {!demoMode && managed ? (
        <div style={{ marginTop: 12 }}>
          <ZonesManagerPanel
            docId={managed.id}
            filename={managed.filename}
            onClose={() => setManaged(null)}
          />
        </div>
      ) : null}
    </div>
  );
}
