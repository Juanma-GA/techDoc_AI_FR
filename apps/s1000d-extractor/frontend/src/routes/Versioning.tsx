import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { documentsApi, versioningApi, type DmVersion } from "../lib/api";

export function humanizeStatus(status: string): string {
  return status.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function Versioning() {
  const qc = useQueryClient();
  const [docId, setDocId] = useState("");
  const [selected, setSelected] = useState<DmVersion | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const docsQuery = useQuery({ queryKey: ["s1000d-docs"], queryFn: documentsApi.list });
  const versionsQuery = useQuery({
    queryKey: ["dm-versions", docId],
    queryFn: () => versioningApi.list(docId),
    enabled: Boolean(docId),
  });
  const contentQuery = useQuery({
    queryKey: ["dm-version", docId, selected?.id],
    queryFn: () => versioningApi.get(docId, selected?.id ?? ""),
    enabled: Boolean(docId && selected),
  });

  const restore = async () => {
    if (!selected) return;
    try {
      await versioningApi.restore(docId, selected.id);
      setMessage("Version restaurée comme nouveau snapshot.");
      void qc.invalidateQueries({ queryKey: ["dm-versions", docId] });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Versioning</h1>
        <p>Historique des Data Modules et restauration non destructive.</p>
      </div>
      <div className="card">
        <label className="label" htmlFor="version-doc">Document</label>
        <select id="version-doc" className="input" value={docId} onChange={(event) => { setDocId(event.target.value); setSelected(null); setMessage(null); }}>
          <option value="">Sélectionner un document</option>
          {(docsQuery.data ?? []).map((doc) => <option key={doc.id} value={doc.id}>{doc.filename}</option>)}
        </select>
      </div>
      {docId ? (
        <div className="version-layout">
          <div className="card">
            <h2 className="card-title">Snapshots</h2>
            {versionsQuery.isLoading ? <div className="empty-state">Chargement...</div> : null}
            {(versionsQuery.data ?? []).map((version) => (
              <button key={version.id} type="button" className={`version-row ${selected?.id === version.id ? "active" : ""}`} onClick={() => setSelected(version)}>
                <strong>{version.dm_code}</strong>
                <span>{humanizeStatus(version.status)} · {new Date(version.created_at).toLocaleString()}</span>
                <small>{version.content_length} caractères · {version.author}</small>
              </button>
            ))}
            {!versionsQuery.isLoading && !(versionsQuery.data ?? []).length ? <div className="empty-state">Aucune version enregistrée.</div> : null}
          </div>
          <div className="card">
            <h2 className="card-title">Aperçu</h2>
            {contentQuery.data ? <pre className="code-preview">{contentQuery.data.content}</pre> : <div className="empty-state">Sélectionnez un snapshot.</div>}
            {selected ? <button type="button" className="btn secondary" onClick={() => void restore()}>Restaurer ce snapshot</button> : null}
            {message ? <div className="success">{message}</div> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
