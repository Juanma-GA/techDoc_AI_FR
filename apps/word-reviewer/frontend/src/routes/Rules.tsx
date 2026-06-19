import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";

import {
  rulesApi,
  standardsApi,
  type CustomRule,
  type Standard,
  type StandardDetail,
} from "../lib/api";

const KINDS = [
  "regex_flag", "regex_replace", "term_replace", "case_capitalize", "accent_fix",
  "field_required", "section_required", "enum_value", "step_pattern", "style_check",
  "zone_field", "revision_check", "manual", "llm_nl",
];
const SEVS = ["info", "warning", "error"];

// Lecture d'un input par classe dans la carte (inputs non-contrôlés, comme le preview).
const v = (root: HTMLElement | null, cls: string): string => {
  const el = root?.querySelector<HTMLInputElement | HTMLSelectElement>(`.${cls}`);
  return el ? el.value : "";
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "block", margin: "4px 0" }}>
      <span className="label">{label}</span>
      {children}
    </label>
  );
}

function Sel({ cls, val, opts }: { cls: string; val: string; opts: string[] }) {
  return (
    <select className={`input ${cls}`} style={{ padding: "3px 6px" }} defaultValue={val}>
      {opts.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}
function Inp({ cls, val, ph }: { cls: string; val?: string; ph?: string }) {
  return <input className={`input ${cls}`} placeholder={ph} defaultValue={val ?? ""} />;
}

function ConfirmGhost({ label, onConfirm }: { label: string; onConfirm: () => void }) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  return (
    <button
      type="button"
      className="btn ghost small"
      onClick={() => {
        if (!armed) {
          setArmed(true);
          timer.current = setTimeout(() => setArmed(false), 3000);
          return;
        }
        if (timer.current) clearTimeout(timer.current);
        setArmed(false);
        onConfirm();
      }}
    >
      {armed ? "Confirmer ?" : label}
    </button>
  );
}

export function Rules() {
  const qc = useQueryClient();
  const standardsQuery = useQuery<Standard[]>({ queryKey: ["standards"], queryFn: standardsApi.list });
  const standards = standardsQuery.data ?? [];
  const ata = standards.find((s) => s.code === "ATA100") ?? standards[0];
  const sid = ata?.id ?? "";
  const vid = ata?.versions?.[0]?.id ?? "";

  const detailQuery = useQuery<StandardDetail>({
    queryKey: ["standard-detail", sid, vid],
    queryFn: () => standardsApi.detail(sid, vid),
    enabled: !!sid && !!vid,
  });
  const customQuery = useQuery<CustomRule[]>({ queryKey: ["rules"], queryFn: rulesApi.list });

  const detail = detailQuery.data ?? { catalog: [], disabled_rule_codes: [] };
  const custom = customQuery.data ?? [];

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["standard-detail", sid, vid] });
    void qc.invalidateQueries({ queryKey: ["rules"] });
  };

  // ---- Import Excel state ----
  const [xlsxFile, setXlsxFile] = useState<File | null>(null);
  const [sheets, setSheets] = useState<{ name: string; rows: string[][]; header_row: number }[]>([]);
  const [sheetIdx, setSheetIdx] = useState(0);
  const [headerRow, setHeaderRow] = useState(0);
  const [topicCol, setTopicCol] = useState<string>("");
  const [checkCol, setCheckCol] = useState<string>("0");
  const [ctxCols, setCtxCols] = useState<Set<number>>(new Set());
  const [importMsg, setImportMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const onInspect = async (file: File) => {
    setXlsxFile(file);
    setImportMsg(null);
    try {
      const r = await rulesApi.inspect(file);
      const sh = r.sheets ?? [];
      setSheets(sh);
      setSheetIdx(0);
      setHeaderRow(sh[0]?.header_row ?? 0);
      setTopicCol("");
      setCheckCol("0");
      setCtxCols(new Set());
    } catch (e) {
      setImportMsg({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  const doImport = async () => {
    if (!xlsxFile) return;
    setImportMsg(null);
    try {
      const r = await rulesApi.importChecklist(xlsxFile, {
        sheet: sheets[sheetIdx]?.name,
        header_row: headerRow,
        topic_col: topicCol,
        check_col: checkCol,
        context_cols: [...ctxCols],
      });
      const dist = Object.entries(r.by_kind).map(([k, val]) => `${k}: ${val}`).join(", ");
      setImportMsg({
        kind: "ok",
        text: `${r.imported} règles (${r.llm_used ? "via LLM" : "heuristique"}, remplace ${r.replaced_count}). ${dist}`,
      });
      refresh();
    } catch (e) {
      setImportMsg({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  // ---- Catalog grouping ----
  const catGroups = useMemo(() => {
    const g: Record<string, typeof detail.catalog> = {};
    for (const r of detail.catalog) {
      const s = r.source || "Autre";
      (g[s] = g[s] || []).push(r);
    }
    return g;
  }, [detail]);
  const disabled = new Set(detail.disabled_rule_codes);

  const pending = custom.filter((r) => !r.validated);
  const validated = custom.filter((r) => r.validated);

  const sheet = sheets[sheetIdx];
  const header = sheet?.rows[headerRow] ?? [];
  const ncols = Math.max(header.length, ...(sheet?.rows.map((r) => r.length) ?? [0]), 0);
  const colLabel = (c: number) => {
    let s = "", n = c + 1;
    while (n > 0) { s = String.fromCharCode(65 + ((n - 1) % 26)) + s; n = Math.floor((n - 1) / 26); }
    return s + (header[c] ? ` · ${header[c]}` : "");
  };

  return (
    <>
      <div className="page-header">
        <h1>Standards &amp; Règles</h1>
        <p>Catalogue ATA, règles personnalisées, import de checklist.</p>
      </div>

      {/* Catalogue */}
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 className="card-title" style={{ margin: 0 }}>
            {ata ? ata.code : "ATA100"} · Règles du catalogue ({detail.catalog.length})
          </h2>
          <ConfirmGhost
            label="Restaurer"
            onConfirm={() => sid && vid && standardsApi.reset(sid, vid).then(refresh)}
          />
        </div>
        <div style={{ marginTop: 12 }}>
          {Object.keys(catGroups).sort().map((src) => (catGroups[src] ?? []).length === 0 ? null : (
            <div className="src-group" key={src}>
              <h3>{src} ({(catGroups[src] ?? []).length})</h3>
              {(catGroups[src] ?? []).map((r) => (
                <details className="sug" key={r.code}>
                  <summary>
                    <span style={{ fontFamily: "'JetBrains Mono',monospace" }}>{r.code}</span>
                    <span className="grow">{r.title || ""}</span>
                    <span className="badge">{r.kind}</span>
                    <span className={`badge ${r.severity === "error" ? "danger" : r.severity === "warning" ? "warn" : "info"}`}>
                      {r.severity}
                    </span>
                    {disabled.has(r.code) ? <span className="badge danger">OFF</span> : null}
                  </summary>
                  <label style={{ display: "flex", alignItems: "center", gap: 6, margin: "6px 0" }}>
                    <input
                      type="checkbox"
                      defaultChecked={!disabled.has(r.code)}
                      onChange={(e) => void standardsApi.toggle(sid, vid, r.code, e.target.checked)}
                    />
                    <span className="label">activée</span>
                  </label>
                  <div className="row">
                    <Field label="title"><Inp cls="f-title" val={r.title} /></Field>
                    <Field label="kind"><Sel cls="f-kind" val={r.kind} opts={KINDS} /></Field>
                    <Field label="severity"><Sel cls="f-sev" val={r.severity} opts={SEVS} /></Field>
                    <Field label="zone"><Inp cls="f-zone" val={r.metadata?.zone ?? ""} /></Field>
                  </div>
                  <div className="row">
                    <Field label="pattern"><Inp cls="f-pattern grow" val={r.pattern} /></Field>
                    <Field label="replacement"><Inp cls="f-repl" val={r.replacement} /></Field>
                  </div>
                  <Field label="message"><Inp cls="f-msg" val={r.message} /></Field>
                  <div className="sug-actions">
                    <button
                      type="button"
                      className="btn primary small"
                      onClick={(e) => {
                        const card = (e.currentTarget.closest("details") as HTMLElement) || null;
                        standardsApi
                          .saveRule(sid, vid, r.code, {
                            title: v(card, "f-title"), kind: v(card, "f-kind"), severity: v(card, "f-sev"),
                            pattern: v(card, "f-pattern"), replacement: v(card, "f-repl"), message: v(card, "f-msg"),
                            metadata: v(card, "f-zone") ? { zone: v(card, "f-zone") } : {},
                          })
                          .then(refresh);
                      }}
                    >
                      Enregistrer
                    </button>
                    <ConfirmGhost label="Supprimer" onConfirm={() => standardsApi.deleteRule(sid, vid, r.code).then(refresh)} />
                  </div>
                </details>
              ))}
            </div>
          ))}
          {detail.catalog.length === 0 ? <div className="empty-state">-</div> : null}
        </div>

        <div className="card" style={{ marginTop: 12, background: "var(--bg-2)" }}>
          <div className="row">
            <Inp cls="nc-code" ph="CODE" />
            <Sel cls="nc-kind" val="regex_flag" opts={KINDS} />
            <Sel cls="nc-sev" val="warning" opts={SEVS} />
            <Inp cls="nc-zone" ph="zone" />
          </div>
          <div className="row" style={{ marginTop: 6 }}>
            <Inp cls="nc-pattern grow" ph="pattern" />
            <Inp cls="nc-msg grow" ph="message" />
            <button
              type="button"
              className="btn primary small"
              onClick={(e) => {
                const c = (e.currentTarget.closest(".card") as HTMLElement) || null;
                standardsApi
                  .addRule(sid, vid, {
                    code: v(c, "nc-code"), kind: v(c, "nc-kind"), severity: v(c, "nc-sev"),
                    pattern: v(c, "nc-pattern"), message: v(c, "nc-msg"), title: v(c, "nc-msg"),
                    metadata: v(c, "nc-zone") ? { zone: v(c, "nc-zone") } : {},
                  })
                  .then(refresh);
              }}
            >
              + Ajouter
            </button>
          </div>
        </div>
      </div>

      {/* Import checklist */}
      <div className="card">
        <h2 className="card-title">Import de checklist</h2>
        <div className="banner warn">Remplace les règles importées existantes.</div>
        <input
          className="input"
          type="file"
          accept=".xlsx,.xlsm"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void onInspect(f);
          }}
        />
        {sheet ? (
          <div style={{ marginTop: 10 }}>
            <div className="row">
              <Field label="Feuille">
                <select value={sheetIdx} onChange={(e) => {
                  const i = parseInt(e.target.value, 10);
                  setSheetIdx(i);
                  setHeaderRow(sheets[i]?.header_row ?? 0);
                  setTopicCol(""); setCheckCol("0");
                }}>
                  {sheets.map((s, i) => <option key={s.name} value={i}>{s.name}</option>)}
                </select>
              </Field>
              <Field label="Colonne Topic">
                <select value={topicCol} onChange={(e) => setTopicCol(e.target.value)}>
                  <option value="">-</option>
                  {Array.from({ length: ncols }, (_, c) => <option key={c} value={c}>{colLabel(c)}</option>)}
                </select>
              </Field>
              <Field label="Colonne Check">
                <select value={checkCol} onChange={(e) => setCheckCol(e.target.value)}>
                  {Array.from({ length: ncols }, (_, c) => <option key={c} value={c}>{colLabel(c)}</option>)}
                </select>
              </Field>
            </div>
            <div className="label" style={{ margin: "6px 0" }}>
              Clique une ligne pour définir l'en-tête{" "}
              <span className="badge ok">Ligne d'en-tête {headerRow + 1}</span>
            </div>
            <div style={{ overflow: "auto", maxHeight: 240 }}>
              <table className="hdr-preview">
                <tbody>
                  {sheet.rows.map((cells, ri) => (
                    <tr
                      key={ri}
                      className={`hdr-row${ri === headerRow ? " active" : ""}`}
                      onClick={() => setHeaderRow(ri)}
                    >
                      <td className="hdr-rownum">{ri + 1}</td>
                      {Array.from({ length: ncols }, (_, ci) => (
                        <td
                          key={ci}
                          className={ci === parseInt(checkCol, 10) ? "col-check" : topicCol !== "" && ci === parseInt(topicCol, 10) ? "col-topic" : undefined}
                        >
                          {(cells[ci] || "").slice(0, 40)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Field label="Colonnes de contexte">
              <div>
                {Array.from({ length: ncols }, (_, c) => (
                  <label key={c} style={{ marginRight: 10, fontSize: "0.8rem" }}>
                    <input
                      type="checkbox"
                      checked={ctxCols.has(c)}
                      onChange={(e) =>
                        setCtxCols((p) => {
                          const n = new Set(p);
                          if (e.target.checked) n.add(c);
                          else n.delete(c);
                          return n;
                        })
                      }
                    />{" "}
                    {colLabel(c)}
                  </label>
                ))}
              </div>
            </Field>
            <button className="btn primary" type="button" style={{ marginTop: 8 }} onClick={() => void doImport()}>
              Importer
            </button>
          </div>
        ) : null}
        {importMsg ? <div className={importMsg.kind === "ok" ? "success" : "error"}>{importMsg.text}</div> : null}
      </div>

      {/* File de validation */}
      {pending.length ? (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2 className="card-title" style={{ margin: 0 }}>À valider ({pending.length})</h2>
            <button className="btn primary small" type="button" onClick={() => rulesApi.validateAll().then(refresh)}>
              Tout valider
            </button>
          </div>
          <div className="banner">Règles importées en attente de validation.</div>
          <div style={{ marginTop: 8 }}>
            {pending.map((r) => (
              <CustomEditor key={r.id} r={r} mode="pending" onChanged={refresh} />
            ))}
          </div>
        </div>
      ) : null}

      {/* Règles validées */}
      <div className="card">
        <h2 className="card-title">Règles validées ({validated.length})</h2>
        <div>
          {validated.length === 0 ? (
            <div className="empty-state">Aucune règle.</div>
          ) : (
            validated.map((r) => <CustomEditor key={r.id} r={r} mode="validated" onChanged={refresh} />)
          )}
        </div>
        <div className="card" style={{ marginTop: 12, background: "var(--bg-2)" }}>
          <div className="row">
            <Inp cls="ncu-name grow" ph="name / check" />
            <Inp cls="ncu-cat" ph="category" />
            <Sel cls="ncu-kind" val="llm_nl" opts={KINDS} />
            <button
              type="button"
              className="btn primary small"
              onClick={(e) => {
                const c = (e.currentTarget.closest(".card") as HTMLElement) || null;
                const name = v(c, "ncu-name");
                if (!name) return;
                rulesApi
                  .create({ name, category: v(c, "ncu-cat"), kind: v(c, "ncu-kind"), message: name })
                  .then(refresh);
              }}
            >
              + Ajouter
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

// Éditeur d'une règle custom (file de validation ou validée).
function CustomEditor({
  r,
  mode,
  onChanged,
}: {
  r: CustomRule;
  mode: "pending" | "validated";
  onChanged: () => void;
}) {
  const collect = (card: HTMLElement | null) => ({
    name: v(card, "g-name"), category: v(card, "g-cat"), kind: v(card, "g-kind"),
    severity: v(card, "g-sev"), pattern: v(card, "g-pattern"), replacement: v(card, "g-repl"),
    target_zone: v(card, "g-zone"), message: v(card, "g-msg"),
    enabled: (card?.querySelector<HTMLInputElement>(".cu-en")?.checked) ?? true,
  });
  const tier =
    r.kind === "manual" ? ["MANUEL", "warn"] : r.kind === "llm_nl" ? ["LLM", "info"] : ["DÉTERMINISTE", "ok"];
  return (
    <details className="sug">
      <summary>
        <span className={`badge ${tier[1]}`}>{tier[0]}</span>
        <span className={`badge ${r.severity === "error" ? "danger" : r.severity === "warning" ? "warn" : "info"}`}>
          {r.severity}
        </span>
        <span className="grow">{r.name}</span>
        {mode === "validated" && !r.enabled ? <span className="badge danger">OFF</span> : null}
      </summary>
      {mode === "validated" ? (
        <label style={{ display: "flex", alignItems: "center", gap: 6, margin: "6px 0" }}>
          <input type="checkbox" className="cu-en" defaultChecked={r.enabled} />
          <span className="label">activée</span>
        </label>
      ) : null}
      <Field label="name / check"><Inp cls="g-name" val={r.name} /></Field>
      <div className="row">
        <Field label="category"><Inp cls="g-cat" val={r.category} /></Field>
        <Field label="kind"><Sel cls="g-kind" val={r.kind} opts={KINDS} /></Field>
        <Field label="severity"><Sel cls="g-sev" val={r.severity} opts={SEVS} /></Field>
        <Field label="zone"><Inp cls="g-zone" val={r.target_zone} /></Field>
      </div>
      <div className="row">
        <Field label="pattern"><Inp cls="g-pattern grow" val={r.pattern} /></Field>
        <Field label="replacement"><Inp cls="g-repl" val={r.replacement} /></Field>
      </div>
      <Field label="message"><Inp cls="g-msg" val={r.message} /></Field>
      <div className="sug-actions">
        <button
          type="button"
          className="btn primary small"
          onClick={(e) => {
            const card = (e.currentTarget.closest("details") as HTMLElement) || null;
            const body: Record<string, unknown> = { ...collect(card), validated: true };
            if (mode === "pending") body.enabled = true;
            rulesApi.patch(r.id, body).then(onChanged);
          }}
        >
          {mode === "pending" ? "Valider" : "Enregistrer"}
        </button>
        <ConfirmGhost label="Supprimer" onConfirm={() => rulesApi.remove(r.id).then(onChanged)} />
      </div>
    </details>
  );
}
