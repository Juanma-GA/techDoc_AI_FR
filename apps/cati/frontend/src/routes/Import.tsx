import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Badge, Card, CardContent, CardHeader, CardTitle, EmptyState, FileDropzone, Select, Spinner } from "@internal/ui";

import { ConfirmButton } from "../components/ConfirmButton";
import { useDeleteDocument, useDocuments, useUploadDocuments } from "../hooks/useDocuments";
import { useProfiles } from "../hooks/useProfiles";
import { useCatiStore } from "../stores/useCatiStore";
import type { DocumentDto } from "../lib/api";

function StatusBadge({ doc }: { doc: DocumentDto }) {
  const { t } = useTranslation();
  if (doc.status === "error") return <Badge variant="danger">{t("import.statusError")}</Badge>;
  const method = doc.extraction_method === "llm" ? t("import.methodLlm") : t("import.methodDeterministic");
  return <Badge variant="info">{method}</Badge>;
}

export function Import() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: documents, isLoading } = useDocuments();
  const { data: profiles } = useProfiles();
  const upload = useUploadDocuments();
  const del = useDeleteDocument();
  const setSelectedDocId = useCatiStore((s) => s.setSelectedDocId);

  const [profileId, setProfileId] = useState("");
  useEffect(() => {
    const def = profiles?.find((p) => p.is_default);
    if (def) setProfileId((cur) => cur || def.id);
  }, [profiles]);

  const openInTable = (id: string) => {
    setSelectedDocId(id);
    navigate("/table");
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("import.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {profiles && profiles.length > 0 && (
            <label className="flex flex-col gap-1">
              <span className="label">{t("import.profile")}</span>
              <Select
                options={profiles.map((p) => ({ value: p.id, label: p.is_default ? `${p.name} ★` : p.name }))}
                value={profileId}
                onChange={(e) => setProfileId(e.target.value)}
              />
            </label>
          )}
          <FileDropzone
            accept="application/pdf,.pdf"
            onFiles={(files) => upload.mutate({ files, profileId: profileId || undefined })}
            disabled={upload.isPending}
            label={t("import.dropLabel")}
            description={t("import.dropDescription")}
          />
          {upload.isPending && (
            <div className="flex items-center gap-2 text-sm text-fg-dim">
              <Spinner /> {t("import.uploading")}
            </div>
          )}
          {upload.isError && <p className="text-sm text-danger">{t("import.uploadError")}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("import.listTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Spinner />
          ) : !documents || documents.length === 0 ? (
            <EmptyState title={t("import.emptyTitle")} description={t("import.emptyDescription")} />
          ) : (
            <ul className="divide-y divide-md">
              {documents.map((doc) => (
                <li key={doc.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-fg">{doc.filename}</p>
                    <p className="text-sm text-fg-dim">
                      {t("import.itemCount", { count: doc.item_count })} · {doc.page_count} p.
                      {doc.warnings.length > 0 && (
                        <span className="text-warning"> · {t("import.warnings", { count: doc.warnings.length })}</span>
                      )}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <StatusBadge doc={doc} />
                    <button
                      type="button"
                      className="rounded-sm border border-md bg-card px-3 py-1.5 text-sm text-fg hover:bg-card-hover"
                      onClick={() => openInTable(doc.id)}
                    >
                      {t("import.open")}
                    </button>
                    <ConfirmButton
                      label={t("common.delete")}
                      onConfirm={() => del.mutate(doc.id)}
                      disabled={del.isPending}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
