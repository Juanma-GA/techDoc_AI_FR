import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { DmPreview } from "../components/DmPreview";
import { PageFlag, RefFlag, TableFlag, ZoneFlag } from "../components/zoneFlags";
import {
  brexApi,
  documentsApi,
  startWizardStream,
  wizardApi,
  type ContextHint,
  type S1000dIssue,
  type TreeNode,
  type WizardState,
} from "../lib/api";

const START_LABELS: Record<string, string> = {
  parse: "Lecture du document…",
  ocr: "PDF scanné : OCR en cours (IA)…",
  infer: "Analyse de la structure…",
  split: "Découpage en Data Modules…",
  classify: "Typage des modules (IA)…",
  done: "Prêt.",
};

const STEP_ORDER: [WizardState["step"], string][] = [
  ["split", "1. Découpage"],
  ["type", "2. Types"],
  ["structure", "3. Structure"],
  ["generate", "4. Génération"],
];

function DmTypeBadge({ type }: { type: string }) {
  return <span className={`badge ${type === "procedural" ? "warn" : "ok"}`}>{type}</span>;
}

// Arbre récursif de la structure (étape 3) + boutons de surcharge (override).
function WizNode({
  dmId,
  node,
  onOverride,
  overrides,
}: {
  dmId: string;
  node: TreeNode;
  onOverride: (dmId: string, nodeId: string, element: string) => void;
  overrides: Record<string, string>;
}) {
  const el = node.candidates?.[0]?.element ?? node.kind;
  const low = node.confidence != null && node.confidence < 0.6 ? " low" : "";
  const ctx = node.context && node.context !== "unknown" ? node.context : null;
  const txt = node.text ? node.text.slice(0, 70) : null;
  const alts = (node.candidates ?? []).slice(1);
  return (
    <li>
      <div className={`tnode${low}`}>
        <span className="el">{el}</span>
        {ctx ? <span className="ctx">{ctx}</span> : null}
        {node.kind === "section" && node.level != null ? (
          <span className="badge info">niv. {node.level}</span>
        ) : null}
        <PageFlag page={node.page} />
        <ZoneFlag zone={node.zone} />
        <TableFlag kind={node.kind} />
        <RefFlag refs={node.refs} />
        {txt ? <span className="txt"> {txt}</span> : null}
        {alts.map((c) => {
          const key = `${dmId}|${node.id}`;
          const chosen = overrides[key] === c.element;
          return (
            <button
              key={c.element}
              type="button"
              className={`btn small ${chosen ? "primary" : "ghost"}`}
              onClick={() => onOverride(dmId, node.id, c.element)}
            >
              {chosen ? `OK ${c.element}` : `→ ${c.element}`}
            </button>
          );
        })}
      </div>
      {(node.children ?? []).length ? (
        <ul>
          {node.children.map((c) => (
            <WizNode
              key={c.id}
              dmId={dmId}
              node={c}
              onOverride={onOverride}
              overrides={overrides}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function Migration() {
  const qc = useQueryClient();
  const brexQuery = useQuery({ queryKey: ["brex"], queryFn: brexApi.list });
  const docsQuery = useQuery({ queryKey: ["s1000d-docs"], queryFn: documentsApi.list });

  // Formulaire de chargement.
  const [file, setFile] = useState<File | null>(null);
  const [issue, setIssue] = useState<S1000dIssue>("5.0");
  const [hint, setHint] = useState<ContextHint>("mixed");
  const [brexId, setBrexId] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);

  // Assistant.
  const [docId, setDocId] = useState<string | null>(null);
  const [wiz, setWiz] = useState<WizardState | null>(null);
  const [starting, setStarting] = useState<{ pct: number; label: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [wizError, setWizError] = useState<string | null>(null);

  // Éditions locales de l'étape courante (réinitialisées à chaque nouvel état).
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [titleEdits, setTitleEdits] = useState<Record<string, string>>({});
  const [typeEdits, setTypeEdits] = useState<Record<string, string>>({});
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [splitLevel, setSplitLevel] = useState("section");
  const [splitMsg, setSplitMsg] = useState<string | null>(null);
  const wizRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSelected(new Set());
    setTitleEdits({});
    setTypeEdits({});
    setOverrides({});
    setSplitMsg(null);
    if (wiz?.split_level) setSplitLevel(wiz.split_level);
    if (wiz && wizRef.current)
      wizRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [wiz]);

  const refreshDocs = () => void qc.invalidateQueries({ queryKey: ["s1000d-docs"] });

  const doStart = async () => {
    if (!file) {
      setLoadError("Choisis un fichier PDF ou Word.");
      return;
    }
    setLoadError(null);
    setWiz(null);
    setWizError(null);
    try {
      const doc = await documentsApi.upload(file, issue, hint, brexId || undefined);
      setDocId(doc.id);
      setStarting({ pct: 5, label: "Démarrage…" });
      await startWizardStream(doc.id, (ev, data) => {
        if (ev === "progress") {
          setStarting({
            pct: (data.pct as number) || 0,
            label: START_LABELS[data.step as string] ?? "Traitement…",
          });
        } else if (ev === "done") {
          setStarting(null);
          setWiz(data as unknown as WizardState);
        } else if (ev === "error") {
          setStarting(null);
          setWizError((data.message as string) || "Échec du démarrage.");
        }
      });
      refreshDocs();
    } catch (e) {
      setStarting(null);
      setLoadError(e instanceof Error ? e.message : String(e));
    }
  };

  const openWizard = async (id: string) => {
    setDocId(id);
    setWiz(null);
    setWizError(null);
    try {
      const st = await wizardApi.get(id);
      setWiz(st);
    } catch {
      // Pas encore démarré : lance le stream de démarrage.
      setStarting({ pct: 5, label: "Démarrage…" });
      try {
        await startWizardStream(id, (ev, data) => {
          if (ev === "progress")
            setStarting({
              pct: (data.pct as number) || 0,
              label: START_LABELS[data.step as string] ?? "Traitement…",
            });
          else if (ev === "done") {
            setStarting(null);
            setWiz(data as unknown as WizardState);
          } else if (ev === "error") {
            setStarting(null);
            setWizError((data.message as string) || "Échec du démarrage.");
          }
        });
      } catch (e) {
        setStarting(null);
        setWizError(e instanceof Error ? e.message : String(e));
      }
    }
  };

  const wizAction = async (action: string, params?: Record<string, unknown>) => {
    if (!docId) return;
    setBusy(true);
    setWizError(null);
    try {
      const st = await wizardApi.action(docId, action, params);
      setWiz(st);
    } catch (e) {
      setWizError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  // Valide le decoupage SANS renvoyer split_level : l'avancement ne doit pas
  // re-decouper (sinon il ecrase les editions manuelles). Le niveau ne change
  // que via « Re-analyser ».
  const validateSplit = () => void wizAction("advance", {});

  // Valide la structure : applique les overrides accumules puis avance.
  const validateStructure = () => {
    const ov = Object.entries(overrides).map(([k, element]) => {
      const [dm_id, node_id] = k.split("|");
      return { dm_id, node_id, element };
    });
    void wizAction("advance", { overrides: ov });
  };

  const imagesQuery = useQuery({
    queryKey: ["s1000d-images", docId],
    queryFn: () => wizardApi.images(docId as string),
    enabled: !!docId && wiz?.step === "generate",
  });

  const brex = brexQuery.data ?? [];
  const docs = docsQuery.data ?? [];
  const images = imagesQuery.data ?? [];

  return (
    <>
      <div className="page-header">
        <h1>Migration</h1>
        <p>Assistant guidé legacy → S1000D.</p>
      </div>

      <div className="card">
        <h2 className="card-title">Charger un document</h2>
        <div className="form">
          <div className="row">
            <label className="grow">
              <div className="label">Document PDF ou Word</div>
              <input
                className="input"
                type="file"
                accept=".pdf,.docx"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </div>
          <div className="row">
            <label className="grow">
              <div className="label">Version S1000D</div>
              <select value={issue} onChange={(e) => setIssue(e.target.value as S1000dIssue)}>
                <option value="5.0">Issue 5.0</option>
                <option value="4.2">Issue 4.2</option>
              </select>
            </label>
            <label className="grow">
              <div className="label">Nature dominante (hint)</div>
              <select value={hint} onChange={(e) => setHint(e.target.value as ContextHint)}>
                <option value="mixed">Mixte</option>
                <option value="descriptive">Descriptif</option>
                <option value="procedural">Procédure</option>
              </select>
            </label>
            <label className="grow">
              <div className="label">BREX projet</div>
              <select value={brexId} onChange={(e) => setBrexId(e.target.value)}>
                <option value="">(aucun BREX)</option>
                {brex.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name} [{b.s1000d_issue}]
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="row">
            <button
              type="button"
              className="btn primary"
              disabled={busy || starting !== null}
              onClick={() => void doStart()}
            >
              Démarrer l'assistant
            </button>
            {loadError ? <span className="error grow">{loadError}</span> : null}
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">Documents</h2>
        {docs.length === 0 ? (
          <div className="empty-state">Aucun document. Charge un PDF/Word ci-dessus.</div>
        ) : (
          docs.map((d) => (
            <div
              key={d.id}
              className="row"
              style={{
                justifyContent: "space-between",
                borderBottom: "1px solid var(--border)",
                padding: "8px 0",
              }}
            >
              <div>
                <div>
                  {d.filename}{" "}
                  <span className={`badge ${d.status === "extracted" ? "ok" : "warn"}`}>
                    {d.status}
                  </span>
                </div>
                <div className="label">{d.source_format.toUpperCase()}</div>
              </div>
              <button
                type="button"
                className="btn secondary small"
                onClick={() => void openWizard(d.id)}
              >
                Ouvrir l'assistant
              </button>
            </div>
          ))
        )}
      </div>

      {/* Assistant */}
      <div ref={wizRef}>
        {starting ? (
          <div className="card">
            <h2 className="card-title">Démarrage de l'assistant</h2>
            <div className="label" style={{ marginBottom: 6 }}>
              {starting.label}
            </div>
            <div className="progress">
              <span style={{ width: `${starting.pct}%` }} />
            </div>
          </div>
        ) : null}

        {wizError ? <div className="card"><div className="error">{wizError}</div></div> : null}

        {wiz ? (
          <>
            <div className="card">
              <div className="row">
                {STEP_ORDER.map(([s, l], i) => (
                  <span key={s} style={{ display: "inline-flex", alignItems: "center" }}>
                    {i > 0 ? <span className="label">&nbsp;→&nbsp;</span> : null}
                    <span className={`badge ${s === wiz.step ? "ok" : ""}`}>{l}</span>
                  </span>
                ))}
              </div>
            </div>

            {wiz.step === "split" ? (
              <div className="card">
                <h2 className="card-title">
                  Étape 1 — Découpage en Data Modules ({wiz.dms.length})
                </h2>
                <div className="row" style={{ marginBottom: 10 }}>
                  <label>
                    <div className="label">Niveau de découpage</div>
                    <select
                      value={splitLevel}
                      onChange={(e) => setSplitLevel(e.target.value)}
                    >
                      <option value="chapter">Chapitre</option>
                      <option value="section">Section</option>
                      <option value="subsection">Sous-section</option>
                    </select>
                  </label>
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={busy}
                    onClick={() => void wizAction("update", { split_level: splitLevel })}
                  >
                    Ré-analyser
                  </button>
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={busy}
                    onClick={() => {
                      const ids = [...selected];
                      if (ids.length < 2) {
                        setSplitMsg("Coche au moins 2 DMs.");
                        return;
                      }
                      void wizAction("update", { op: "merge", ids });
                    }}
                  >
                    Fusionner la sélection
                  </button>
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={busy}
                    onClick={() =>
                      void wizAction("update", { op: "hide_zones", zones: ["header", "footer"] })
                    }
                  >
                    Masquer entêtes/pieds
                  </button>
                  <button
                    type="button"
                    className="btn ghost"
                    disabled={busy || !wiz.can_undo}
                    onClick={() => void wizAction("update", { op: "undo" })}
                  >
                    Annuler
                  </button>
                  {splitMsg ? <span className="error grow">{splitMsg}</span> : null}
                  <button
                    type="button"
                    className="btn primary"
                    style={{ marginLeft: "auto" }}
                    disabled={busy}
                    onClick={validateSplit}
                  >
                    Valider le découpage →
                  </button>
                </div>
                <p className="label">
                  Coche plusieurs DMs puis « Fusionner » ; édite un titre puis
                  « Renommer » ; « Scinder » redécoupe ; « Exclure » retire le bruit.
                </p>
                <div>
                  {wiz.dms.map((d) => (
                    <div
                      key={d.dm_id}
                      style={{ borderBottom: "1px solid var(--border)", padding: "6px 0" }}
                    >
                    <div className="row" style={{ gap: 8 }}>
                      <input
                        type="checkbox"
                        checked={selected.has(d.dm_id)}
                        onChange={() =>
                          setSelected((p) => {
                            const n = new Set(p);
                            if (n.has(d.dm_id)) n.delete(d.dm_id);
                            else n.add(d.dm_id);
                            return n;
                          })
                        }
                      />
                      <input
                        className="input grow"
                        value={titleEdits[d.dm_id] ?? d.title}
                        onChange={(e) =>
                          setTitleEdits((p) => ({ ...p, [d.dm_id]: e.target.value }))
                        }
                      />
                      <DmTypeBadge type={d.dm_type} />
                      <span className="label">{d.node_count}</span>
                      <button
                        type="button"
                        className="btn ghost small"
                        disabled={busy}
                        onClick={() =>
                          void wizAction("update", {
                            op: "rename",
                            id: d.dm_id,
                            title: titleEdits[d.dm_id] ?? d.title,
                          })
                        }
                      >
                        Renommer
                      </button>
                      <button
                        type="button"
                        className="btn ghost small"
                        disabled={busy}
                        onClick={() => void wizAction("update", { op: "split", id: d.dm_id })}
                      >
                        Scinder
                      </button>
                      <button
                        type="button"
                        className="btn danger small"
                        disabled={busy}
                        onClick={() => void wizAction("update", { op: "exclude", id: d.dm_id })}
                      >
                        Exclure
                      </button>
                    </div>
                    <DmPreview preview={d.preview} />
                    </div>
                  ))}
                </div>
                <div className="row" style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn primary"
                    disabled={busy}
                    onClick={validateSplit}
                  >
                    Valider le découpage →
                  </button>
                </div>
              </div>
            ) : null}

            {wiz.step === "type" ? (
              <div className="card">
                <h2 className="card-title">Étape 2 — Type de chaque Data Module</h2>
                <p className="label">
                  Corrige le type proposé (descriptive / procedural / ipd).
                </p>
                <div>
                  {wiz.dms.map((d) => (
                    <div
                      key={d.dm_id}
                      className="row"
                      style={{ borderBottom: "1px solid var(--border)", padding: "6px 0" }}
                    >
                      <span className="grow">{d.title}</span>
                      <select
                        value={typeEdits[d.dm_id] ?? d.dm_type}
                        onChange={(e) =>
                          setTypeEdits((p) => ({ ...p, [d.dm_id]: e.target.value }))
                        }
                      >
                        {["descriptive", "procedural", "ipd"].map((tp) => (
                          <option key={tp} value={tp}>
                            {tp}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
                <div className="row" style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={busy}
                    onClick={() => void wizAction("back")}
                  >
                    ← Retour
                  </button>
                  <button
                    type="button"
                    className="btn primary"
                    disabled={busy}
                    onClick={() => {
                      const types: Record<string, string> = {};
                      for (const d of wiz.dms) types[d.dm_id] = typeEdits[d.dm_id] ?? d.dm_type;
                      void wizAction("advance", { types });
                    }}
                  >
                    Valider les types →
                  </button>
                </div>
              </div>
            ) : null}

            {wiz.step === "structure" ? (
              <>
                <div className="card">
                  <div className="row">
                    <button
                      type="button"
                      className="btn secondary"
                      disabled={busy}
                      onClick={() => void wizAction("back")}
                    >
                      ← Retour
                    </button>
                    <button
                      type="button"
                      className="btn primary"
                      style={{ marginLeft: "auto" }}
                      disabled={busy}
                      onClick={validateStructure}
                    >
                      Valider la structure →
                    </button>
                  </div>
                </div>
                {wiz.dms.map((d) => (
                  <div className="card" key={d.dm_id}>
                    <h2 className="card-title">
                      {d.title} <DmTypeBadge type={d.dm_type} />
                    </h2>
                    <div className="tree">
                      <ul>
                        {(d.tree.children ?? []).map((c) => (
                          <WizNode
                            key={c.id}
                            dmId={d.dm_id}
                            node={c}
                            overrides={overrides}
                            onOverride={(dmId, nodeId, element) =>
                              setOverrides((p) => ({ ...p, [`${dmId}|${nodeId}`]: element }))
                            }
                          />
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
                <div className="card">
                  <div className="row">
                    <button
                      type="button"
                      className="btn secondary"
                      disabled={busy}
                      onClick={() => void wizAction("back")}
                    >
                      ← Retour
                    </button>
                    <button
                      type="button"
                      className="btn primary"
                      disabled={busy}
                      onClick={validateStructure}
                    >
                      Valider la structure →
                    </button>
                  </div>
                </div>
              </>
            ) : null}

            {wiz.step === "generate" ? (
              <div className="card">
                <h2 className="card-title">
                  Étape 4 — Data Modules générés ({wiz.dms.length})
                </h2>
                <div>
                  {wiz.dms.map((d) => (
                    <div
                      key={d.dm_id}
                      className="row"
                      style={{ borderBottom: "1px solid var(--border)", padding: "8px 0" }}
                    >
                      <span className="grow">
                        {d.title} <DmTypeBadge type={d.dm_type} />{" "}
                        <span className={`badge ${d.violation_count ? "warn" : "ok"}`}>
                          {d.violation_count} viol.
                        </span>
                      </span>
                      <a
                        className="btn secondary small"
                        href={docId ? wizardApi.dmXmlUrl(docId, d.dm_id) : "#"}
                      >
                        XML
                      </a>
                    </div>
                  ))}
                </div>
                {images.length ? (
                  <div style={{ marginTop: 16 }}>
                    <h3 className="label">Illustrations extraites ({images.length})</h3>
                    <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
                      {images.map((name) => (
                        <a
                          key={name}
                          href={docId ? wizardApi.imageUrl(docId, name) : "#"}
                          target="_blank"
                          rel="noreferrer"
                          className="label"
                          style={{ display: "inline-flex", flexDirection: "column", gap: 4 }}
                        >
                          <img
                            src={docId ? wizardApi.imageUrl(docId, name) : undefined}
                            alt={name}
                            style={{
                              width: 96,
                              height: 72,
                              objectFit: "cover",
                              border: "1px solid var(--border)",
                              borderRadius: 4,
                            }}
                          />
                          <span style={{ maxWidth: 96, overflow: "hidden", textOverflow: "ellipsis" }}>
                            {name}
                          </span>
                        </a>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="row" style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={busy}
                    onClick={() => void wizAction("back")}
                  >
                    ← Retour
                  </button>
                  <a
                    className="btn primary"
                    href={docId ? wizardApi.zipUrl(docId) : "#"}
                  >
                    Télécharger tout (ZIP)
                  </a>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </>
  );
}
