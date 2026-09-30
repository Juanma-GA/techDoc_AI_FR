import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useState } from "react";

import { documentsApi, versioningApi, type DmVersion } from "../lib/api";

export function humanizeStatus(status: string): string {
  return status.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function Versioning() {
  const { t, i18n } = useTranslation();
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
      setMessage(t("versioning.restored"));
      void qc.invalidateQueries({ queryKey: ["dm-versions", docId] });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setMessage(t("versioning.restoreError", { message }));
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("versioning.title")}</h1>
        <p>{t("versioning.subtitle")}</p>
      </div>
      <div className="card">
        <label className="label" htmlFor="version-doc">{t("versioning.document")}</label>
        <select id="version-doc" className="input" value={docId} onChange={(event) => { setDocId(event.target.value); setSelected(null); setMessage(null); }}>
          <option value="">{t("versioning.selectDocument")}</option>
          {(docsQuery.data ?? []).map((doc) => <option key={doc.id} value={doc.id}>{doc.filename}</option>)}
        </select>
      </div>
      {docId ? (
        <div className="version-layout">
          <div className="card">
            <h2 className="card-title">{t("versioning.snapshots")}</h2>
            {versionsQuery.isLoading ? <div className="empty-state">{t("versioning.loading")}</div> : null}
            {(versionsQuery.data ?? []).map((version) => (
              <button key={version.id} type="button" className={`version-row ${selected?.id === version.id ? "active" : ""}`} onClick={() => setSelected(version)}>
                <strong>{version.dm_code}</strong>
                <span>{t(`versioning.status.${version.status}`, { defaultValue: humanizeStatus(version.status) })} · {new Date(version.created_at).toLocaleString(i18n.language)}</span>
                <small>{t("versioning.characters", { count: version.content_length })} · {version.author}</small>
              </button>
            ))}
            {!versionsQuery.isLoading && !(versionsQuery.data ?? []).length ? <div className="empty-state">{t("versioning.noVersions")}</div> : null}
          </div>
          <div className="card">
            <h2 className="card-title">{t("versioning.preview")}</h2>
            {contentQuery.data ? <pre className="code-preview">{contentQuery.data.content}</pre> : <div className="empty-state">{t("versioning.selectSnapshot")}</div>}
            {selected ? <button type="button" className="btn secondary" onClick={() => void restore()}>{t("versioning.restore")}</button> : null}
            {message ? <div className="success">{message}</div> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
