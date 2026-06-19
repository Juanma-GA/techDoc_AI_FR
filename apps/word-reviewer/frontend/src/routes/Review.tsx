import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  analyzeStream,
  documentsApi,
  suggestionsApi,
  type DocBlock,
  type DocView,
  type Suggestion,
} from "../lib/api";

function escapeHtml(s: string): string {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const hlClass = (sev: string) =>
  sev === "error" ? "error" : sev === "warning" ? "warn" : "info";

type Span = { start: number; end: number; id: string; severity: string; status: string };

function injectHighlights(text: string, spans: Span[]): string {
  if (!spans.length) return escapeHtml(text || "");
  const sorted = spans.slice().sort((a, b) => a.start - b.start);
  let out = "";
  let cur = 0;
  for (const sp of sorted) {
    if (sp.start < cur || sp.start > text.length || sp.end > text.length) continue;
    out += escapeHtml(text.slice(cur, sp.start));
    const cls = sp.status === "applied" || sp.status === "edited" ? "applied" : hlClass(sp.severity);
    out += `<mark class="hl ${cls}" data-sug="${sp.id}">${escapeHtml(text.slice(sp.start, sp.end))}</mark>`;
    cur = sp.end;
  }
  out += escapeHtml(text.slice(cur));
  return out;
}

function renderDocHtml(blocks: DocBlock[], sugs: Suggestion[]): string {
  const inline: Record<string, Span[]> = {};
  const blk: Record<string, Suggestion[]> = {};
  for (const s of sugs) {
    if (!s.target_id) continue;
    if (s.char_end > s.char_start && s.original_text) {
      (inline[s.target_id] = inline[s.target_id] || []).push({
        start: s.char_start,
        end: s.char_end,
        id: s.id,
        severity: s.severity,
        status: s.status,
      });
    } else {
      (blk[s.target_id] = blk[s.target_id] || []).push(s);
    }
  }
  const cellInner = (b: DocBlock) =>
    b.text ? injectHighlights(b.text, inline[b.target_id] || []) : '<span class="blk-empty">·</span>';
  const flagAttrs = (b: DocBlock) => {
    const first = blk[b.target_id]?.[0];
    return first ? ` blockflag" data-sug="${first.id}"` : '"';
  };

  let html = "";
  let i = 0;
  while (i < blocks.length) {
    const b = blocks[i];
    if (!b) {
      i++;
      continue;
    }
    if (b.kind === "cell" && b.table_id != null) {
      const tid = b.table_id;
      const cells: DocBlock[] = [];
      for (let c = blocks[i]; c && c.kind === "cell" && c.table_id === tid; c = blocks[i]) {
        cells.push(c);
        i++;
      }
      const rows: Record<number, DocBlock[]> = {};
      cells.forEach((c) => {
        (rows[c.row ?? 0] = rows[c.row ?? 0] || []).push(c);
      });
      html += '<table class="docx"><tbody>';
      Object.keys(rows)
        .map(Number)
        .sort((a, b2) => a - b2)
        .forEach((r) => {
          html += "<tr>";
          (rows[r] ?? [])
            .sort((a, b2) => (a.col ?? 0) - (b2.col ?? 0))
            .forEach((c) => {
              html += `<td class="blk${flagAttrs(c)} id="blk-${c.target_id}">${cellInner(c)}</td>`;
            });
          html += "</tr>";
        });
      html += "</tbody></table>";
      continue;
    }
    const tag = b.kind === "heading" ? ((b.heading_level || 1) >= 2 ? "h4" : "h3") : "p";
    html += `<${tag} class="blk${flagAttrs(b)} id="blk-${b.target_id}">${cellInner(b)}</${tag}>`;
    i++;
  }
  return html || '<div class="empty-state">Aucune anomalie.</div>';
}

export function Review() {
  const { docId = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const docRef = useRef<HTMLDivElement>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [proposed, setProposed] = useState<Record<string, string>>({});
  const [reanalyzing, setReanalyzing] = useState(false);

  const viewQuery = useQuery<DocView | null>({
    queryKey: ["wr-view", docId],
    queryFn: () => documentsApi.view(docId),
  });
  const sugsQuery = useQuery<Suggestion[]>({
    queryKey: ["wr-sugs", docId],
    queryFn: () => documentsApi.suggestions(docId),
  });

  const view = viewQuery.data ?? null;
  const sugs = useMemo(() => sugsQuery.data ?? [], [sugsQuery.data]);

  const isCorrective = (s: Suggestion) =>
    s.char_end > s.char_start &&
    !!s.original_text &&
    !!s.proposed_text &&
    s.proposed_text !== s.original_text;
  const auto = sugs.filter(isCorrective);
  const manual = sugs.filter((s) => !isCorrective(s));
  const handled = sugs.filter((s) =>
    ["applied", "edited", "rejected", "checked"].includes(s.status),
  ).length;

  const docHtml = useMemo(
    () => (view ? renderDocHtml(view.blocks, sugs) : ""),
    [view, sugs],
  );

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["wr-view", docId] });
    void qc.invalidateQueries({ queryKey: ["wr-sugs", docId] });
  };

  // Surbrillance de la sélection dans la vue document (innerHTML) + scroll.
  useEffect(() => {
    const root = docRef.current;
    if (!root) return;
    root.querySelectorAll(".selected").forEach((e) => e.classList.remove("selected"));
    if (!selectedId) return;
    const marks = root.querySelectorAll(`[data-sug="${selectedId}"]`);
    marks.forEach((m) => m.classList.add("selected"));
  }, [selectedId, docHtml]);

  const selectFromDoc = (e: React.MouseEvent) => {
    const m = (e.target as HTMLElement).closest("[data-sug]");
    if (m) setSelectedId((m as HTMLElement).dataset.sug ?? null);
  };

  const applyMut = useMutation({
    mutationFn: async (v: { id: string; group: boolean; prop: string }) => {
      await suggestionsApi.patch(v.id, { proposed_text: v.prop });
      if (v.group) await suggestionsApi.applyGroup(v.id);
      else await suggestionsApi.apply(v.id);
    },
    onSuccess: refresh,
  });
  const rejectMut = useMutation({
    mutationFn: (id: string) => suggestionsApi.patch(id, { status: "rejected" }),
    onSuccess: refresh,
  });
  const undoMut = useMutation({
    mutationFn: (id: string) => suggestionsApi.undo(id),
    onSuccess: refresh,
  });
  const checkMut = useMutation({
    mutationFn: (v: { ids: string[]; status: string }) =>
      Promise.all(v.ids.map((id) => suggestionsApi.patch(id, { status: v.status }))),
    onSuccess: refresh,
  });

  const reanalyze = async () => {
    setReanalyzing(true);
    try {
      await analyzeStream(docId, () => {});
      refresh();
    } finally {
      setReanalyzing(false);
    }
  };

  // Regroupe les signalements manuels identiques (règle + message).
  const manualGroups = useMemo(() => {
    const g = new Map<string, Suggestion[]>();
    for (const s of manual) {
      const k = s.rule_code + "" + s.message;
      if (!g.has(k)) g.set(k, []);
      g.get(k)!.push(s);
    }
    return [...g.values()];
  }, [manual]);
  const manualChecked = manual.filter((s) => s.status === "checked").length;

  if (viewQuery.isLoading || sugsQuery.isLoading)
    return (
      <div className="card">
        <div className="empty-state">Chargement…</div>
      </div>
    );
  if (!view)
    return (
      <div className="card">
        <div className="empty-state">Document introuvable.</div>
        <button className="btn secondary" type="button" onClick={() => navigate("/documents")}>
          ← Retour
        </button>
      </div>
    );

  return (
    <>
      <div className="review-bar">
        <button className="btn ghost small" type="button" onClick={() => navigate("/documents")}>
          ← Retour
        </button>
        <strong className="grow">{view.original_filename}</strong>
        <span className="zone-tag">
          v{view.current_version} · {handled}/{sugs.length} traitées
        </span>
        <button className="btn secondary small" type="button" disabled={reanalyzing} onClick={() => void reanalyze()}>
          {reanalyzing ? "Analyse…" : "Réanalyser"}
        </button>
        <a className="btn secondary small" href={documentsApi.exportUrl(docId)} target="_blank" rel="noreferrer">
          Export
        </a>
      </div>

      <div className="review-grid">
        <div
          className="doc-view"
          ref={docRef}
          onClick={selectFromDoc}
          dangerouslySetInnerHTML={{ __html: docHtml }}
        />

        <div className="sug-panel">
          <div className="card">
            <div className="banner">Corrections proposées : appliquer remplace le texte (versionné, annulable).</div>
            <h2 className="card-title">À corriger ({auto.length})</h2>
            <div>
              {auto.length === 0 ? (
                <div className="empty-state">-</div>
              ) : (
                auto.map((s) => {
                  const applied = s.status === "applied" || s.status === "edited";
                  const prop = proposed[s.id] ?? s.proposed_text;
                  return (
                    <div
                      className={`sug${applied ? " applied" : ""}${selectedId === s.id ? " selected" : ""}`}
                      key={s.id}
                      onClick={(e) => {
                        if ((e.target as HTMLElement).closest("button, input")) return;
                        setSelectedId(s.id);
                      }}
                    >
                      <div className="sug-head">
                        <span className={`badge ${hlClass(s.severity)}`}>{s.severity}</span>
                        <span className="grow sug-msg">{s.message}</span>
                        <span className="zone-tag">{s.rule_code}</span>
                        <span className="badge">{s.status}</span>
                      </div>
                      <div className="diff">
                        <span className="old">{s.original_text}</span> →{" "}
                        <input
                          className="input prop"
                          style={{ display: "inline-block", width: "auto", minWidth: 150 }}
                          value={prop}
                          disabled={s.status === "applied"}
                          onChange={(e) => setProposed((p) => ({ ...p, [s.id]: e.target.value }))}
                        />
                      </div>
                      <div className="sug-actions">
                        {s.status === "applied" ? (
                          <button className="btn secondary small" type="button" onClick={() => undoMut.mutate(s.id)}>
                            Annuler
                          </button>
                        ) : (
                          <>
                            <button
                              className="btn primary small"
                              type="button"
                              onClick={() => applyMut.mutate({ id: s.id, group: false, prop })}
                            >
                              Appliquer
                            </button>
                            <button
                              className="btn secondary small"
                              type="button"
                              onClick={() => applyMut.mutate({ id: s.id, group: true, prop })}
                            >
                              Appliquer au groupe
                            </button>
                            <button className="btn ghost small" type="button" onClick={() => rejectMut.mutate(s.id)}>
                              Rejeter
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div className="card">
            <h2 className="card-title">
              À vérifier <span className="zone-tag">{manualChecked}/{manual.length} cochés</span>
            </h2>
            <div className="banner">Signalements à revue humaine : coche ceux qui sont traités.</div>
            <div>
              {manualGroups.length === 0 ? (
                <div className="empty-state">-</div>
              ) : (
                manualGroups.map((items) => {
                  const s = items[0];
                  if (!s) return null;
                  const allChecked = items.every((x) => x.status === "checked");
                  return (
                    <label className="checkline" key={s.id}>
                      <input
                        type="checkbox"
                        checked={allChecked}
                        onChange={(e) =>
                          checkMut.mutate({
                            ids: items.map((x) => x.id),
                            status: e.target.checked ? "checked" : "open",
                          })
                        }
                      />
                      <span onClick={() => setSelectedId(s.id)}>
                        <span className={`badge ${hlClass(s.severity)}`}>{s.severity}</span> {s.message}
                        {items.length > 1 ? <span className="badge"> x{items.length}</span> : null}{" "}
                        <span className="zone-tag">{s.rule_code}</span>
                      </span>
                    </label>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
