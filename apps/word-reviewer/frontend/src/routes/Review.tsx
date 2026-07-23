import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { PdfDocView } from "../components/PdfDocView";
import {
  analyzeStream,
  documentsApi,
  suggestionsApi,
  type DocBlock,
  type DocView,
  type LayoutChecks,
  type PdfHighlight,
  type PdfView,
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

// Regroupe des items identiques (recurrence) selon une cle -> [{rep, items}].
// L'ordre de premiere apparition est conserve.
function collapseBy<T>(items: T[], keyOf: (t: T) => string): { rep: T; items: T[] }[] {
  const m = new Map<string, T[]>();
  for (const it of items) {
    const k = keyOf(it);
    const g = m.get(k);
    if (g) g.push(it);
    else m.set(k, [it]);
  }
  return [...m.values()].map((g) => ({ rep: g[0]!, items: g }));
}

// Regroupe des items par Sujet (Rule.category). "" (règles standard) -> "Sans sujet".
// Retourne les groupes triés par libellé pour un ordre stable.
function groupByCategory<T>(items: T[], catOf: (t: T) => string): [string, T[]][] {
  const g = new Map<string, T[]>();
  for (const it of items) {
    const key = (catOf(it) || "").trim() || "Sans sujet";
    if (!g.has(key)) g.set(key, []);
    g.get(key)!.push(it);
  }
  return [...g.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

// Pagination de secours quand le .docx ne porte aucun saut de page detectable.
const PAGE_SIZE = 40;

// Decoupe les blocs en pages : en-tetes/pieds (rendus sur chaque page) + pages du
// corps (par saut de page Word si dispo, sinon par paquets de PAGE_SIZE blocs).
function paginate(blocks: DocBlock[]): {
  header: DocBlock[];
  footer: DocBlock[];
  pages: DocBlock[][];
  pageOf: Record<string, number>;
} {
  const header = blocks.filter((b) => b.zone === "header");
  const footer = blocks.filter((b) => b.zone === "footer");
  const body = blocks.filter((b) => b.zone !== "header" && b.zone !== "footer");
  const distinct = new Set(body.map((b) => b.page ?? 1));

  let pages: DocBlock[][];
  if (distinct.size > 1) {
    const byPage = new Map<number, DocBlock[]>();
    for (const b of body) {
      const p = b.page ?? 1;
      let arr = byPage.get(p);
      if (!arr) {
        arr = [];
        byPage.set(p, arr);
      }
      arr.push(b);
    }
    pages = [...byPage.keys()].sort((a, b) => a - b).map((k) => byPage.get(k) ?? []);
  } else if (body.length > PAGE_SIZE) {
    pages = [];
    for (let i = 0; i < body.length; i += PAGE_SIZE) pages.push(body.slice(i, i + PAGE_SIZE));
  } else {
    pages = [body];
  }

  const pageOf: Record<string, number> = {};
  pages.forEach((pg, idx) => pg.forEach((b) => (pageOf[b.target_id] = idx)));
  return { header, footer, pages, pageOf };
}

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

  const renderBlocks = (list: DocBlock[]): string => {
    let html = "";
    let i = 0;
    while (i < list.length) {
      const b = list[i];
      if (!b) {
        i++;
        continue;
      }
      if (b.kind === "cell" && b.table_id != null) {
        const tid = b.table_id;
        const cells: DocBlock[] = [];
        for (let c = list[i]; c && c.kind === "cell" && c.table_id === tid; c = list[i]) {
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
    return html;
  };

  // En-tetes et pieds de page sont sortis dans des sections dediees et etiquetees
  // (sinon ils se fondent en fin de flux et "disparaissent" visuellement).
  const header = blocks.filter((b) => b.zone === "header");
  const footer = blocks.filter((b) => b.zone === "footer");
  const body = blocks.filter((b) => b.zone !== "header" && b.zone !== "footer");

  let out = "";
  if (header.length)
    out += `<section class="doc-zone header"><div class="doc-zone-label">En-tête</div>${renderBlocks(header)}</section>`;
  out += renderBlocks(body);
  if (footer.length)
    out += `<section class="doc-zone footer"><div class="doc-zone-label">Pied de page</div>${renderBlocks(footer)}</section>`;
  return out || '<div class="empty-state">Document vide.</div>';
}

export function Review() {
  const { docId = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const docRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [proposed, setProposed] = useState<Record<string, string>>({});
  const [reanalyzing, setReanalyzing] = useState(false);
  const [analyzeProg, setAnalyzeProg] = useState<{ done: number; total: number } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pageIdx, setPageIdx] = useState(0);

  const viewQuery = useQuery<DocView | null>({
    queryKey: ["wr-view", docId],
    queryFn: () => documentsApi.view(docId),
  });
  const sugsQuery = useQuery<Suggestion[]>({
    queryKey: ["wr-sugs", docId],
    queryFn: () => documentsApi.suggestions(docId),
  });
  const pdfQuery = useQuery<PdfView>({
    queryKey: ["wr-pdf", docId],
    queryFn: () => documentsApi.pdfView(docId),
  });
  const layoutQuery = useQuery<LayoutChecks>({
    queryKey: ["wr-layout", docId],
    queryFn: () => documentsApi.layoutChecks(docId),
  });

  const view = viewQuery.data ?? null;
  const sugs = useMemo(() => sugsQuery.data ?? [], [sugsQuery.data]);
  const pdf = pdfQuery.data ?? null;
  const pdfAvailable = pdf?.available === true;
  const [preferHtml, setPreferHtml] = useState(false);
  const usePdf = pdfAvailable && !preferHtml; // vue effective (toggle PDF <-> HTML)
  // La structure (mise en page) est une anomalie a part entiere : on l'affiche dans
  // la liste QUELLE QUE SOIT la vue (PDF ou HTML). Seul le surlignage geometrique
  // sur la page reste propre au PDF (les findings portent des coordonnees PDF).
  const layout = useMemo(() => layoutQuery.data?.findings ?? [], [layoutQuery.data]);

  // Severite par id (anomalies + controles de mise en page).
  const sevMap = useMemo(() => {
    const m: Record<string, string> = {};
    sugs.forEach((s) => (m[s.id] = s.severity));
    layout.forEach((f) => (m[f.id] = f.severity));
    return m;
  }, [sugs, layout]);
  const severityOf = (id: string) => sevMap[id] ?? "info";

  // Surlignages PDF = anomalies localisees + boites des controles geometriques.
  const pdfHighlights = useMemo<PdfHighlight[]>(
    () => [
      ...(pdf?.highlights ?? []),
      ...layout.filter((f) => f.boxes.length).map((f) => ({ id: f.id, page: f.page, boxes: f.boxes })),
    ],
    [pdf, layout],
  );

  // id (anomalie ou controle) -> page (0-indexed) pour le clic-vers-page.
  const pdfPageOf = useMemo(() => {
    const m: Record<string, number> = {};
    (pdf?.highlights ?? []).forEach((h) => (m[h.id] = h.page - 1));
    layout.forEach((f) => (m[f.id] = f.page - 1));
    return m;
  }, [pdf, layout]);

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

  const { header, footer, pages, pageOf } = useMemo(
    () => paginate(view?.blocks ?? []),
    [view],
  );
  // Nombre de pages : reel (PDF) si dispo, sinon pagination logique du HTML.
  const pageCount = usePdf ? Math.max(1, pdf?.page_count ?? 1) : Math.max(1, pages.length);
  const curPage = Math.min(pageIdx, pageCount - 1);
  const docHtml = useMemo(
    () => (usePdf ? "" : renderDocHtml([...header, ...(pages[curPage] ?? []), ...footer], sugs)),
    [usePdf, header, footer, pages, curPage, sugs],
  );

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["wr-view", docId] });
    void qc.invalidateQueries({ queryKey: ["wr-sugs", docId] });
    void qc.invalidateQueries({ queryKey: ["wr-pdf", docId] });
    void qc.invalidateQueries({ queryKey: ["wr-layout", docId] });
  };

  // Clic sur une suggestion -> bascule sur la page qui la contient.
  useEffect(() => {
    if (!selectedId) return;
    let pg: number | undefined;
    if (usePdf) {
      pg = pdfPageOf[selectedId];
    } else {
      const sug = sugs.find((s) => s.id === selectedId);
      pg = sug ? pageOf[sug.target_id] : undefined;
    }
    if (pg != null && pg !== curPage) setPageIdx(pg);
  }, [selectedId, usePdf, pdfPageOf, sugs, pageOf, curPage]);

  // Mode HTML : surbrillance + scroll dans la vue innerHTML (sans objet en mode PDF).
  useEffect(() => {
    if (usePdf) return;
    const root = docRef.current;
    if (!root) return;
    root.querySelectorAll(".selected").forEach((e) => e.classList.remove("selected"));
    if (!selectedId) return;
    const marks = root.querySelectorAll(`[data-sug="${selectedId}"]`);
    marks.forEach((m) => m.classList.add("selected"));
    const first = marks[0] as HTMLElement | undefined;
    if (first) first.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [usePdf, selectedId, docHtml]);

  // Defile le panneau de suggestions jusqu'a la carte selectionnee.
  useEffect(() => {
    const root = panelRef.current;
    if (!root || !selectedId) return;
    // `~=` : matche un id parmi la liste d'ids portee par la carte (groupes manuels).
    const card = root.querySelector<HTMLElement>(`[data-sugcard~="${selectedId}"]`);
    if (card) card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selectedId, sugs]);

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
    onSuccess: () => {
      setActionError(null);
      refresh();
    },
    onError: (e) => setActionError(e instanceof Error ? e.message : String(e)),
  });
  const rejectMut = useMutation({
    mutationFn: (id: string) => suggestionsApi.patch(id, { status: "rejected" }),
    onSuccess: refresh,
  });
  const undoMut = useMutation({
    mutationFn: (id: string) => suggestionsApi.undo(id),
    onSuccess: () => {
      setActionError(null);
      refresh();
    },
    onError: (e) => setActionError(e instanceof Error ? e.message : String(e)),
  });
  const reanalyze = async () => {
    setReanalyzing(true);
    setAnalyzeProg({ done: 0, total: 0 });
    try {
      await analyzeStream(docId, (ev, data) => {
        if (ev === "progress")
          setAnalyzeProg({ done: Number(data.done ?? 0), total: Number(data.total ?? 0) });
      });
      refresh();
    } finally {
      setReanalyzing(false);
      setAnalyzeProg(null);
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

  // Regroupe par Sujet (colonne TOPIC de la checklist) pour un affichage repliable
  // — évite d'afficher toutes les anomalies à plat. "" (règle standard) -> repli dédié.
  const autoByCat = useMemo(() => groupByCategory(auto, (s) => s.category), [auto]);
  const manualByCat = useMemo(
    () => groupByCategory(manualGroups, (g) => g[0]?.category ?? ""),
    [manualGroups],
  );

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
        {pdfAvailable ? (
          <div className="seg-toggle" role="group" aria-label="Mode d'affichage">
            <button
              type="button"
              className={`seg-btn${!preferHtml ? " active" : ""}`}
              onClick={() => setPreferHtml(false)}
            >
              PDF fidèle
            </button>
            <button
              type="button"
              className={`seg-btn${preferHtml ? " active" : ""}`}
              onClick={() => setPreferHtml(true)}
            >
              HTML
            </button>
          </div>
        ) : null}
        <span className="zone-tag">
          v{view.current_version} · {handled}/{sugs.length} traitées
        </span>
        {analyzeProg ? (
          <span className="analyze-row">
            <span className="spinner" aria-hidden="true" />
            <span className="analyze-label">
              {analyzeProg.total > 0 ? `Analyse ${analyzeProg.done}/${analyzeProg.total}` : "Analyse…"}
            </span>
          </span>
        ) : null}
        <button className="btn secondary small" type="button" disabled={reanalyzing} onClick={() => void reanalyze()}>
          {reanalyzing ? "Analyse…" : "Réanalyser"}
        </button>
        <a className="btn secondary small" href={documentsApi.exportUrl(docId)} target="_blank" rel="noreferrer">
          Export
        </a>
      </div>

      {actionError ? (
        <div className="banner warn" role="alert" onClick={() => setActionError(null)}>
          {actionError}
        </div>
      ) : null}

      <div className="review-grid">
        <div className="doc-pane">
          {pageCount > 1 ? (
            <div className="doc-pager">
              <button
                className="btn ghost small"
                type="button"
                disabled={curPage <= 0}
                onClick={() => setPageIdx(curPage - 1)}
              >
                ← Page préc.
              </button>
              <span className="analyze-label">
                Page {curPage + 1} / {pageCount}
              </span>
              <button
                className="btn ghost small"
                type="button"
                disabled={curPage >= pageCount - 1}
                onClick={() => setPageIdx(curPage + 1)}
              >
                Page suiv. →
              </button>
            </div>
          ) : null}
          {usePdf ? (
            <PdfDocView
              docId={docId}
              page={curPage + 1}
              version={view.current_version}
              highlights={pdfHighlights}
              selectedId={selectedId}
              severityOf={severityOf}
              onSelect={setSelectedId}
            />
          ) : (
            <div
              className="doc-view"
              ref={docRef}
              onClick={selectFromDoc}
              dangerouslySetInnerHTML={{ __html: docHtml }}
            />
          )}
        </div>

        <div className="sug-panel" ref={panelRef}>
          {layout.length > 0 ? (
            <details className="card" open>
              <summary className="card-title" style={{ cursor: "pointer" }}>
                Mise en page ({collapseBy(layout, (f) => f.message).length})
              </summary>
              <div className="banner">
                Contrôles géométriques (titres, pieds de page) sur le rendu PDF fidèle.
                {!usePdf ? " Le surlignage est visible en vue PDF." : ""}
              </div>
              <div>
                {collapseBy(layout, (f) => f.message).map(({ rep: f, items: grp }) => {
                  const ids = grp.map((x) => x.id);
                  const sel = selectedId != null && ids.includes(selectedId);
                  return (
                    <div
                      className={`checkline${sel ? " selected" : ""}`}
                      key={f.id}
                      data-sugcard={ids.join(" ")}
                      onClick={() => setSelectedId(f.id)}
                    >
                      <span>
                        <span className={`badge ${hlClass(f.severity)}`}>{f.severity}</span> {f.message}
                        {grp.length > 1 ? (
                          <span className="badge" title={`${grp.length} occurrences`}> ×{grp.length}</span>
                        ) : null}{" "}
                        <span className="zone-tag">{f.rule_code}</span>
                      </span>
                    </div>
                  );
                })}
              </div>
            </details>
          ) : null}
          <details className="card" open>
            <summary className="card-title" style={{ cursor: "pointer" }}>
              À corriger ({auto.length})
            </summary>
            <div className="banner">Corrections proposées : appliquer remplace le texte (versionné, annulable).</div>
            <div>
              {auto.length === 0 ? (
                <div className="empty-state">-</div>
              ) : (
                autoByCat.map(([label, items]) => (
                  <details className="cat-group" key={label} open>
                    <summary style={{ cursor: "pointer", fontWeight: 600, padding: "6px 0" }}>
                      {label} <span className="zone-tag">{items.length}</span>
                    </summary>
                    {collapseBy(
                      items,
                      (s) => `${s.rule_code}${s.original_text}${s.proposed_text}`,
                    ).map(({ rep: s, items: grp }) => {
                  const ids = grp.map((x) => x.id);
                  const applied = s.status === "applied" || s.status === "edited";
                  const prop = proposed[s.id] ?? s.proposed_text;
                  const sel = selectedId != null && ids.includes(selectedId);
                  return (
                    <div
                      className={`sug${applied ? " applied" : ""}${sel ? " selected" : ""}`}
                      key={s.id}
                      data-sugcard={ids.join(" ")}
                      onClick={(e) => {
                        if ((e.target as HTMLElement).closest("button, input")) return;
                        setSelectedId(s.id);
                      }}
                    >
                      <div className="sug-head">
                        <span className={`badge ${hlClass(s.severity)}`}>{s.severity}</span>
                        <span className="grow sug-msg">{s.message}</span>
                        {grp.length > 1 ? (
                          <span className="badge" title={`${grp.length} occurrences identiques`}>×{grp.length}</span>
                        ) : null}
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
                          (() => {
                            // Annulation LIFO : seule la correction de la version
                            // courante du document est annulable directement.
                            const undoable = s.applied_version === view.current_version;
                            return (
                              <button
                                className="btn secondary small"
                                type="button"
                                disabled={!undoable}
                                title={
                                  undoable
                                    ? "Annuler cette correction"
                                    : "Annule d'abord la correction la plus récente."
                                }
                                onClick={() => undoMut.mutate(s.id)}
                              >
                                Annuler
                              </button>
                            );
                          })()
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
                    })}
                  </details>
                ))
              )}
            </div>
          </details>

          <details className="card" open>
            <summary className="card-title" style={{ cursor: "pointer" }}>
              À vérifier <span className="zone-tag">{manual.length}</span>
            </summary>
            <div className="banner">Signalements à revue humaine.</div>
            <div>
              {manualGroups.length === 0 ? (
                <div className="empty-state">-</div>
              ) : (
                manualByCat.map(([label, groups]) => (
                  <details className="cat-group" key={label} open>
                    <summary style={{ cursor: "pointer", fontWeight: 600, padding: "6px 0" }}>
                      {label}{" "}
                      <span className="zone-tag">{groups.reduce((n, g) => n + g.length, 0)}</span>
                    </summary>
                    {groups.map((items) => {
                  const s = items[0];
                  if (!s) return null;
                  const groupSelected = items.some((x) => x.id === selectedId);
                  return (
                    <div
                      className={`checkline${groupSelected ? " selected" : ""}`}
                      key={s.id}
                      data-sugcard={items.map((x) => x.id).join(" ")}
                      onClick={() => setSelectedId(s.id)}
                    >
                      <span>
                        <span className={`badge ${hlClass(s.severity)}`}>{s.severity}</span> {s.message}
                        {items.length > 1 ? <span className="badge"> x{items.length}</span> : null}{" "}
                        <span className="zone-tag">{s.rule_code}</span>
                      </span>
                    </div>
                  );
                    })}
                  </details>
                ))
              )}
            </div>
          </details>
        </div>
      </div>
    </>
  );
}
