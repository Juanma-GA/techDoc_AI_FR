import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  FileDropzone,
  Spinner,
} from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiClientError, documentsApi, type DocumentDto } from "../lib/api";

const ACCEPT = ".pdf,.docx,.pptx,.xlsx,.xlsm,.txt,.md";

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} kB`;
  return `${(size / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function Documents() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const docsQuery = useQuery<DocumentDto[], ApiClientError>({
    queryKey: ["documents"],
    queryFn: documentsApi.list,
  });

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => documentsApi.upload(files),
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

  const documents = docsQuery.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("documents.title")}</h1>
        <p className="text-fg-dim">{t("documents.subtitle")}</p>
      </header>

      <Card>
        <CardContent className="pt-4">
          <FileDropzone
            accept={ACCEPT}
            multiple
            label={t("documents.uploadLabel")}
            description={t("documents.uploadDescription")}
            disabled={uploadMutation.isPending}
            onFiles={(files) => uploadMutation.mutate(files)}
          />
          {uploadMutation.isPending ? (
            <p className="mt-3 flex items-center gap-2 text-sm text-fg-dim">
              <Spinner size="sm" /> {t("documents.uploading")}
            </p>
          ) : null}
          {error ? (
            <p className="mt-3 text-sm text-danger">{error}</p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("documents.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {docsQuery.isLoading ? (
            <Spinner />
          ) : documents.length === 0 ? (
            <EmptyState title={t("documents.empty")} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-md text-left text-fg-dim">
                    <th className="px-2 py-2">{t("documents.columnFilename")}</th>
                    <th className="px-2 py-2">{t("documents.columnSize")}</th>
                    <th className="px-2 py-2">{t("documents.columnChunks")}</th>
                    <th className="px-2 py-2">{t("documents.columnDate")}</th>
                    <th className="px-2 py-2 text-right">{t("documents.columnActions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.id} className="border-b border-md/40">
                      <td className="px-2 py-2 text-fg">{doc.filename}</td>
                      <td className="px-2 py-2 text-fg-dim">{formatSize(doc.size)}</td>
                      <td className="px-2 py-2 text-fg-dim">
                        {doc.index_error ? (
                          <Badge variant="warning">{t("documents.indexErrorBadge")}</Badge>
                        ) : (
                          <Badge variant="default">{doc.chunk_count}</Badge>
                        )}
                      </td>
                      <td className="px-2 py-2 text-fg-dim">
                        {formatDate(doc.uploaded_at)}
                      </td>
                      <td className="px-2 py-2 text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={t("documents.delete")}
                          onClick={() => deleteMutation.mutate(doc.id)}
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 size={14} aria-hidden="true" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
