import { Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { PdfUploadZone } from "../components/upload/PdfUploadZone";
import { StandardPicker } from "../components/upload/StandardPicker";
import { useDeleteDocument, useDocuments, useUploadDocument } from "../hooks/useDocuments";
import { useFiltersStore } from "../stores/filtersStore";
import type { Document } from "../types/domain";

export function DocumentsList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const docs = useDocuments();
  const upload = useUploadDocument();
  const remove = useDeleteDocument();
  const targetUnit = useFiltersStore((s) => s.targetUnit);
  const lastStandardId = useFiltersStore((s) => s.lastStandardId);
  const lastStandardVersionId = useFiltersStore((s) => s.lastStandardVersionId);
  const setLastStandard = useFiltersStore((s) => s.setLastStandard);

  const handleUpload = (file: File): void => {
    upload.mutate(
      { file, target: targetUnit, standardVersionId: lastStandardVersionId },
      {
        onSuccess: (doc: Document) => navigate(`/documents/${doc.id}`),
      },
    );
  };

  return (
    <div className="flex flex-col">
      <PageHeader title={t("documents.title")} subtitle={t("documents.subtitle")} />

      <section className="flex flex-col gap-6 p-6">
        <div className="flex flex-col gap-3">
          <StandardPicker
            standardId={lastStandardId}
            versionId={lastStandardVersionId}
            onChange={setLastStandard}
          />
          <PdfUploadZone onFile={handleUpload} disabled={upload.isPending} />
        </div>

        {docs.isLoading ? (
          <p className="text-fg-dim">{t("common.loading")}</p>
        ) : docs.data && docs.data.length > 0 ? (
          <ul className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {docs.data.map((doc) => (
              <li
                key={doc.id}
                className="flex flex-col gap-1 rounded-lg border bg-card p-4 hover:bg-card-hover"
              >
                <h3 className="font-mono text-fg">{doc.original_filename}</h3>
                <p className="font-mono text-xs text-fg-dim">
                  {doc.page_count} pages · v{doc.current_version} · {doc.target_unit_system}
                </p>
                <div className="mt-2 flex justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/documents/${doc.id}`)}
                    className="rounded-sm bg-brand px-3 py-1 text-xs text-fg hover:bg-brand-blue-light"
                  >
                    {t("documents.open")}
                  </button>
                  <button
                    type="button"
                    aria-label={t("documents.delete")}
                    onClick={() => remove.mutate(doc.id)}
                    className="rounded-sm border p-1 text-fg-dim hover:bg-danger/10 hover:text-danger"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-fg-dim">{t("documents.empty")}</p>
        )}
      </section>
    </div>
  );
}
