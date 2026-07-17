import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { analyzeStream, documentsApi, type WordDoc } from "../lib/api";

async function runPool<T>(items: T[], fn: (it: T) => Promise<void>, limit: number) {
  const queue = items.slice();
  const workers = Array.from({ length: Math.min(limit, queue.length) }, async () => {
    while (queue.length) await fn(queue.shift() as T);
  });
  await Promise.all(workers);
}

function DocStatus({ d }: { d: WordDoc }) {
  if (d.status !== "analyzed")
    return <span className="badge warn">À analyser</span>;
  if (!d.findings_total)
    return (
      <>
        <span className="badge ok">Analysé</span>{" "}
        <span className="doc-status">aucune anomalie</span>
      </>
    );
  return (
    <>
      <span className="badge ok">Analysé</span>{" "}
      <span className="doc-status">{d.findings_total} anomalies</span>{" "}
      {d.findings_open ? (
        <span className="badge warn">{d.findings_open} à traiter</span>
      ) : (
        <span className="badge ok">tout traité</span>
      )}
    </>
  );
}

function AnalyzeProgress({ p }: { p: { done: number; total: number; label: string; error?: boolean } }) {
  if (p.error)
    return (
      <span className="grow analyze-label" style={{ color: "var(--danger)" }}>
        {p.label}
      </span>
    );
  return (
    <span className="grow analyze-row">
      <span className="spinner" aria-hidden="true" />
      <span className="analyze-label">{p.label}</span>
    </span>
  );
}

export function Documents() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(
    null,
  );
  type Prog = { done: number; total: number; label: string; error?: boolean };
  const [analyzing, setAnalyzing] = useState<Record<string, Prog | undefined>>({});
  // Lignes optimistes affichees des le clic (le temps de l'upload + conversion .doc).
  const [pending, setPending] = useState<string[]>([]);

  const docsQuery = useQuery<WordDoc[]>({
    queryKey: ["word-docs"],
    queryFn: documentsApi.list,
  });
  const docs = docsQuery.data ?? [];
  const refresh = () => void qc.invalidateQueries({ queryKey: ["word-docs"] });

  const setProg = (id: string, prog: Prog | undefined) =>
    setAnalyzing((p) => ({ ...p, [id]: prog }));

  const analyzeDoc = async (id: string) => {
    setProg(id, { done: 0, total: 0, label: "Analyse…" });
    let count = 0;
    try {
      await analyzeStream(id, (ev, data) => {
        if (ev === "progress") {
          const done = Number(data.done ?? 0);
          const total = Number(data.total ?? 0);
          setProg(id, { done, total, label: `Analyse ${done}/${total}` });
        } else if (ev === "suggestion") {
          count++;
          setProg(id, { done: 1, total: 1, label: `${count} anomalies` });
        } else if (ev === "error") throw new Error((data.message as string) || "erreur");
      });
      setProg(id, undefined);
      refresh();
    } catch (e) {
      setProg(id, { done: 0, total: 0, label: e instanceof Error ? e.message : String(e), error: true });
    }
  };

  const upload = async () => {
    const files = fileRef.current?.files;
    if (!files || !files.length) {
      setFeedback({ kind: "error", text: "Sélectionne au moins un fichier." });
      return;
    }
    // Feedback immediat : les fichiers apparaissent en tete de liste (Import en cours).
    setPending(Array.from(files).map((f) => f.name));
    setFeedback(null);
    try {
      const r = await documentsApi.upload(Array.from(files));
      let msg = `${r.documents.length} document(s) importé(s).`;
      if (r.ignored?.length) msg += ` Ignorés : ${r.ignored.join(", ")}`;
      setFeedback({ kind: "ok", text: msg });
      setPending([]);
      refresh();
      // Analyse automatique (concurrence bornée).
      await runPool(r.documents.map((d) => d.id), (id) => analyzeDoc(id), 3);
      refresh();
    } catch (e) {
      setPending([]);
      setFeedback({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>Documents</h1>
        <p>Importe des .docx / .zip ; l'analyse démarre automatiquement.</p>
      </div>

      <div className="card">
        <h2 className="card-title">Importer</h2>
        <div className="row">
          <input className="input grow" type="file" ref={fileRef} accept=".docx,.doc,.zip" multiple />
          <button className="btn primary" type="button" onClick={() => void upload()}>
            Importer
          </button>
        </div>
        {feedback ? (
          <div className={feedback.kind === "ok" ? "success" : "error"}>{feedback.text}</div>
        ) : null}
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 className="card-title" style={{ margin: 0 }}>
            Documents
          </h2>
          <button
            className="btn secondary small"
            type="button"
            onClick={() => void documentsApi.exportZip(docs.map((d) => d.id))}
          >
            Exporter (ZIP)
          </button>
        </div>
        <div style={{ marginTop: 12 }}>
          {pending.map((name, i) => (
            <div className="sug" key={`pending-${i}`}>
              <div className="sug-head">
                <strong className="grow">{name}</strong>
                <span className="badge warn">Uploadé</span>
                <span className="analyze-row">
                  <span className="spinner" aria-hidden="true" />
                  <span className="analyze-label">Import en cours…</span>
                </span>
              </div>
            </div>
          ))}
          {docs.length === 0 && pending.length === 0 ? (
            <div className="empty-state">Aucun document.</div>
          ) : (
            docs.map((d) => (
              <div className="sug" key={d.id}>
                <div className="sug-head">
                  <strong className="grow">{d.original_filename}</strong>
                  <span>
                    <DocStatus d={d} />
                  </span>
                  <span className="zone-tag">
                    {d.block_count} blocs · v{d.current_version}
                  </span>
                </div>
                <div className="sug-actions">
                  <button
                    className="btn primary small"
                    type="button"
                    onClick={() => void analyzeDoc(d.id)}
                  >
                    Analyser
                  </button>
                  <button
                    className="btn secondary small"
                    type="button"
                    onClick={() => navigate(`/review/${d.id}`)}
                  >
                    Revue
                  </button>
                  <a
                    className="btn ghost small"
                    href={documentsApi.exportUrl(d.id)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Export
                  </a>
                  {analyzing[d.id] ? (
                    <AnalyzeProgress p={analyzing[d.id]!} />
                  ) : (
                    <span className="grow" />
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
