import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { PdfUploadZone } from "../components/upload/PdfUploadZone";
import { useDocuments, useUploadDocument } from "../hooks/useDocuments";
import { effectiveTarget, useFiltersStore } from "../stores/filtersStore";
import type { Document } from "../types/domain";

export function Preparation() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const documents = useDocuments();
  const upload = useUploadDocument();
  const targetUnits = useFiltersStore((state) => state.targetUnits);

  const handleUpload = (file: File): void => {
    upload.mutate(
      { file, target: effectiveTarget(targetUnits) },
      {
        onSuccess: (result) => {
          if ("id" in result) {
            navigate(`/preparation/${(result as Document).id}`);
          }
        },
      },
    );
  };

  return (
    <div>
      <PageHeader title={t("preparation.title")} subtitle={t("preparation.subtitle")} />
      <section className="card">
        <h2 className="card-title">{t("preparation.importTitle")}</h2>
        <p className="card-sub">{t("preparation.importHint")}</p>
        <PdfUploadZone onFile={handleUpload} uploading={upload.isPending} allowBatch={false} />
        {upload.isError ? (
          <p className="error" role="alert">
            {t("documents.upload.failed", {
              message: upload.error instanceof Error ? upload.error.message : "",
            })}
          </p>
        ) : null}
      </section>
      <section className="card">
        <h2 className="card-title">{t("preparation.resumeTitle")}</h2>
        {documents.isLoading ? (
          <p className="empty-state">{t("common.loading")}</p>
        ) : documents.isError ? (
          <p className="banner warn" role="alert">
            {documents.error instanceof Error ? documents.error.message : t("common.retry")}
          </p>
        ) : (documents.data ?? []).filter((document) => document.working_format === "pdf").length > 0 ? (
          <div className="item-list">
            {(documents.data ?? [])
              .filter((document) => document.working_format === "pdf")
              .map((document) => (
                <div className="item-row" key={document.id}>
                  <div className="item-main">
                    <p className="item-name">{document.original_filename}</p>
                    <p className="item-meta">
                      {document.page_count} {t("documents.detail.meta.pages")}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn primary small"
                    onClick={() => navigate(`/preparation/${document.id}`)}
                  >
                    {t("preparation.resume")}
                  </button>
                </div>
              ))}
          </div>
        ) : (
          <p className="empty-state">{t("preparation.empty")}</p>
        )}
      </section>
    </div>
  );
}
