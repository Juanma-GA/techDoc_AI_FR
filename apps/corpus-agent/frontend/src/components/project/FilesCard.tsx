import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { FileDropzone } from "@internal/ui";

import { filesApi } from "../../lib/api";
import type { FileOut, UploadItemResult } from "../../lib/types";

export function FilesCard({ pid }: { pid: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [results, setResults] = useState<UploadItemResult[]>([]);

  const filesQuery = useQuery<FileOut[]>({ queryKey: ["files", pid], queryFn: () => filesApi.list(pid) });

  const upload = useMutation({
    mutationFn: (files: File[]) => filesApi.upload(pid, files),
    onSuccess: (res) => {
      setResults(res.uploaded);
      void qc.invalidateQueries({ queryKey: ["files", pid] });
    },
  });
  const remove = useMutation({
    mutationFn: (fileId: string) => filesApi.remove(pid, fileId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["files", pid] }),
  });

  const files = filesQuery.data ?? [];
  // Doublons : fichiers partageant le sha256 de leur derniere version.
  const latestSha = (f: FileOut): string => {
    const sorted = [...f.versions].sort((a, b) => (a.uploaded_at < b.uploaded_at ? -1 : 1));
    return sorted.length ? sorted[sorted.length - 1]!.sha256 : "";
  };
  const byHash = new Map<string, string[]>();
  for (const f of files) {
    const sha = latestSha(f);
    if (!sha) continue;
    const list = byHash.get(sha) ?? [];
    list.push(f.current_name);
    byHash.set(sha, list);
  }
  // Pour un fichier en doublon, retourne les noms des AUTRES fichiers identiques.
  const duplicateOthers = (f: FileOut): string[] | null => {
    const sha = latestSha(f);
    const names = sha ? byHash.get(sha) : undefined;
    if (!names || names.length <= 1) return null;
    return names.filter((n) => n !== f.current_name);
  };

  return (
    <div className="card">
      <h2 className="card-title">{t("projects.files")}</h2>
      <FileDropzone
        multiple
        onFiles={(fs) => upload.mutate(fs)}
        label={t("projects.upload")}
        accept=".docx,.pdf,.xlsx,.xlsm,.xml,.csv,.txt"
      />
      {results.length > 0 && (
        <div className="row" style={{ marginTop: 8, flexDirection: "column", alignItems: "stretch" }}>
          {results.map((r, i) => (
            <div key={i} className={r.ok ? "success" : "error"}>
              {r.ok ? "✓" : "✗"} {r.filename}
              {r.skipped ? ` — ${r.skipped}` : ""}
              {r.error ? ` — ${r.error}` : ""}
            </div>
          ))}
        </div>
      )}

      {filesQuery.isLoading ? (
        <div className="empty-state">{t("common.loading")}</div>
      ) : files.length === 0 ? (
        <div className="empty-state">—</div>
      ) : (
        <div className="file-list" style={{ marginTop: 10 }}>
          {files.map((f) => {
            const others = duplicateOthers(f);
            return (
            <div className="file-row" key={f.id}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="file-name">
                  {f.current_name}
                  {others && (
                    <span className="badge danger" style={{ marginLeft: 8 }} title={`${t("files.duplicateOf")} : ${others.join(", ")}`}>
                      {t("files.duplicate")}
                    </span>
                  )}
                </div>
                <div className="file-meta">
                  {f.versions.length} v · {f.mime_type}
                </div>
              </div>
              <button type="button" className="btn ghost small" onClick={() => remove.mutate(f.id)} aria-label={t("common.delete")}>
                ×
              </button>
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
