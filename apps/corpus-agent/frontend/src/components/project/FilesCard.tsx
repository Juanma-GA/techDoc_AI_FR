import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { FileDropzone } from "@internal/ui";

import { filesApi } from "../../lib/api";
import type { CorpusPathOut, FileOut, FolderFileOut, UploadItemResult } from "../../lib/types";

/** Taille lisible (o / Ko / Mo). */
function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

/** `skipped` du backend = code stable (jamais de prose) ; on le traduit ici
 * — un code inconnu (future valeur) retombe sur lui-meme plutot que planter. */
function skippedLabel(t: TFunction, code: string): string {
  return code === "unchanged" ? t("files.skippedUnchanged") : code;
}

export function FilesCard({ pid }: { pid: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [results, setResults] = useState<UploadItemResult[]>([]);
  const [analysisUpdated, setAnalysisUpdated] = useState(false);
  const [folderPath, setFolderPath] = useState("");
  // Aperçu du dossier (liste des fichiers) + sélection avant import.
  const [listing, setListing] = useState<FolderFileOut[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const filesQuery = useQuery<FileOut[]>({ queryKey: ["files", pid], queryFn: () => filesApi.list(pid) });
  const folderQuery = useQuery<CorpusPathOut>({
    queryKey: ["corpus-folder", pid],
    queryFn: () => filesApi.getFolder(pid),
  });

  const upload = useMutation({
    mutationFn: (files: File[]) => filesApi.upload(pid, files),
    onSuccess: (res) => {
      setResults(res.uploaded);
      setAnalysisUpdated(!!res.analysis_run_id);
      void qc.invalidateQueries({ queryKey: ["files", pid] });
      void qc.invalidateQueries({ queryKey: ["anomalies", pid] });
      void qc.invalidateQueries({ queryKey: ["kpis"] });
      void qc.invalidateQueries({ queryKey: ["analysis-runs", pid] });
    },
  });
  // Parcourir un dossier : liste ses fichiers pour sélection (sans ingérer).
  // Par défaut, tout ce qui est ingérable (non bloqué) est présélectionné.
  const browse = useMutation({
    mutationFn: (path: string) => filesApi.listFolder(pid, path),
    onSuccess: (res) => {
      setListing(res.files);
      setSelected(new Set(res.files.filter((f) => !f.blocked).map((f) => f.rel)));
    },
  });
  // Import de la sélection : même sortie que l'upload manuel (affichage `results`).
  const syncFolder = useMutation({
    mutationFn: ({ path, only }: { path: string; only?: string[] }) =>
      filesApi.syncFolder(pid, path, only),
    onSuccess: (res) => {
      setResults(res.uploaded);
      setAnalysisUpdated(!!res.analysis_run_id);
      void qc.invalidateQueries({ queryKey: ["files", pid] });
      void qc.invalidateQueries({ queryKey: ["corpus-folder", pid] });
      void qc.invalidateQueries({ queryKey: ["anomalies", pid] });
      void qc.invalidateQueries({ queryKey: ["kpis"] });
      void qc.invalidateQueries({ queryKey: ["analysis-runs", pid] });
    },
  });
  const disconnectFolder = useMutation({
    mutationFn: () => filesApi.disconnectFolder(pid),
    onSuccess: () => {
      setListing(null);
      setSelected(new Set());
      void qc.invalidateQueries({ queryKey: ["corpus-folder", pid] });
    },
  });
  const remove = useMutation({
    mutationFn: (fileId: string) => filesApi.remove(pid, fileId),
    onSuccess: () => {
      setAnalysisUpdated(true);
      void qc.invalidateQueries({ queryKey: ["files", pid] });
      void qc.invalidateQueries({ queryKey: ["anomalies", pid] });
      void qc.invalidateQueries({ queryKey: ["kpis"] });
      void qc.invalidateQueries({ queryKey: ["analysis-runs", pid] });
    },
  });

  const connectedPath = folderQuery.data?.path ?? null;
  const effectivePath = () => folderPath.trim() || connectedPath || "";
  const doBrowse = () => {
    const p = effectivePath();
    if (p) browse.mutate(p);
  };
  const selectableCount = (listing ?? []).filter((f) => !f.blocked).length;
  const toggleSel = (rel: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(rel)) next.delete(rel);
      else next.add(rel);
      return next;
    });
  const importSelection = () => {
    const p = effectivePath();
    if (p && selected.size) syncFolder.mutate({ path: p, only: [...selected] });
  };

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
      {analysisUpdated && <div className="banner">{t("files.analysisUpdated")}</div>}

      {/* Connexion d'un dossier corpus (chemin local / OneDrive synchronise) */}
      <div className="folder-connect" style={{ marginTop: 12 }}>
        <div className="label">{t("projects.folderConnect")}</div>
        <div className="label" style={{ opacity: 0.7, marginBottom: 6 }}>{t("projects.folderConnectHint")}</div>
        <div className="row" style={{ gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <input
            className="input"
            style={{ flex: 1, minWidth: 240 }}
            placeholder={connectedPath ?? "C:\\Users\\...\\OneDrive\\MonCorpus"}
            value={folderPath}
            onChange={(e) => setFolderPath(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") doBrowse(); }}
          />
          <button
            type="button"
            className="btn secondary"
            disabled={browse.isPending || (!folderPath.trim() && !connectedPath)}
            onClick={doBrowse}
          >
            {browse.isPending ? <span className="spinner" /> : null}{" "}
            {t("projects.folderBrowse")}
          </button>
          {connectedPath && (
            <button
              type="button"
              className="btn ghost small"
              disabled={disconnectFolder.isPending}
              onClick={() => disconnectFolder.mutate()}
            >
              {t("projects.folderDisconnect")}
            </button>
          )}
        </div>
        {connectedPath && (
          <div className="label" style={{ marginTop: 6 }}>
            {t("projects.folderConnected")} <code>{connectedPath}</code>
          </div>
        )}
        {browse.isError && (
          <div className="error" style={{ marginTop: 6 }}>
            {browse.error instanceof Error ? browse.error.message : String(browse.error)}
          </div>
        )}

        {listing && (
          <div className="folder-listing" style={{ marginTop: 10 }}>
            {listing.length === 0 ? (
              <div className="empty-state">{t("projects.folderEmpty")}</div>
            ) : (
              <>
                <div className="row" style={{ gap: "0.75rem", alignItems: "center", flexWrap: "wrap", marginBottom: 6 }}>
                  <span className="label">{t("projects.folderSelected", { count: selected.size, total: selectableCount })}</span>
                  <button type="button" className="btn ghost small"
                    onClick={() => setSelected(new Set(listing.filter((f) => !f.blocked).map((f) => f.rel)))}>
                    {t("projects.folderSelectAll")}
                  </button>
                  <button type="button" className="btn ghost small" onClick={() => setSelected(new Set())}>
                    {t("projects.folderSelectNone")}
                  </button>
                </div>
                <div style={{ maxHeight: 240, overflowY: "auto", display: "flex", flexDirection: "column", gap: 2 }}>
                  {listing.map((f) => (
                    <label
                      key={f.rel}
                      className="row"
                      style={{ gap: "0.5rem", alignItems: "center", opacity: f.blocked ? 0.45 : 1 }}
                      title={f.blocked ? t("projects.folderBlocked") : f.rel}
                    >
                      <input
                        type="checkbox"
                        disabled={f.blocked}
                        checked={selected.has(f.rel)}
                        onChange={() => toggleSel(f.rel)}
                      />
                      <span style={{ flex: 1, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {f.rel}
                      </span>
                      <span className="label">{fmtSize(f.size)}</span>
                      {f.blocked && <span className="badge off">{t("projects.folderBlockedTag")}</span>}
                    </label>
                  ))}
                </div>
                <button
                  type="button"
                  className="btn primary"
                  style={{ marginTop: 8 }}
                  disabled={syncFolder.isPending || selected.size === 0}
                  onClick={importSelection}
                >
                  {syncFolder.isPending ? <span className="spinner" /> : null}{" "}
                  {t("projects.folderImportSelection", { count: selected.size })}
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {results.length > 0 && (
        <div className="row" style={{ marginTop: 8, flexDirection: "column", alignItems: "stretch" }}>
          {results.map((r, i) => (
            <div key={i} className={r.ok ? "success" : "error"}>
              {r.ok ? "✓" : "✗"} {r.filename}
              {r.skipped ? ` — ${skippedLabel(t, r.skipped)}` : ""}
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
                <div className="file-name" title={f.rel_path ?? undefined}>
                  {f.rel_path ?? f.current_name}
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
