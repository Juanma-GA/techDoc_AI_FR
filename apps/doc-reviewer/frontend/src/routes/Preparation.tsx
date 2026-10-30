import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { DocumentDeleteButton } from "../components/DocumentDeleteButton";
import { PageHeader } from "../components/PageHeader";
import { PdfUploadZone } from "../components/upload/PdfUploadZone";
import {
  useDeleteDocument,
  useDocuments,
  useUploadDocument,
} from "../hooks/useDocuments";
import { effectiveTarget, useFiltersStore } from "../stores/filtersStore";
import type { Document } from "../types/domain";

export function Preparation() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const documents = useDocuments();
  const upload = useUploadDocument();
  const remove = useDeleteDocument();
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
        {remove.isError ? (
          <p className="error" role="alert">
            {t("documents.deleteFailed", {
              message: remove.error instanceof Error ? remove.error.message : "",
            })}
          </p>
        ) : null}
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
                <div
                  className="item-row clickable prep-document-row"
                  key={document.id}
                  role="link"
                  tabIndex={0}
                  aria-label={`${t("documents.open")}: ${document.original_filename}`}
                  onClick={(event) => {
                    if (event.target instanceof Element && event.target.closest("button")) return;
                    navigate(`/preparation/${document.id}`);
                  }}
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !(event.target instanceof Element && event.target.closest("button"))
                    ) {
                      event.preventDefault();
                      navigate(`/preparation/${document.id}`);
                    }
                  }}
                >
                  <div className="item-main">
                    <p className="item-name">{document.original_filename}</p>
                    <p className="item-meta">
                      {document.page_count} {t("documents.detail.meta.pages")}
                    </p>
                  </div>
                  <div className="item-actions">
                    <button
                      type="button"
                      className="btn primary small"
                      onClick={() => navigate(`/preparation/${document.id}`)}
                    >
                      {t("documents.open")}
                    </button>
                    <DocumentDeleteButton
                      label={t("common.delete")}
                      ariaLabel={t("documents.delete")}
                      confirmLabel={t("documents.deleteConfirmAgain")}
                      onConfirm={() => remove.mutate(document.id)}
                      disabled={remove.isPending}
                    />
                  </div>
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
