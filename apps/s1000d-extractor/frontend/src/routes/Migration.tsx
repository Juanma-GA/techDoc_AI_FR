import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { DmPreview } from "../components/DmPreview";
import { PageFlag, RefFlag, ReviewFlag, TableFlag, ZoneFlag } from "../components/zoneFlags";
import {
  brexApi,
  documentsApi,
  migrationInputsApi,
  pdfCutApi,
  resourcesApi,
  startWizardStream,
  wizardApi,
  type ContextHint,
  type DmrlRow,
  type MigrationInputKind,
  type PdfCutDetection,
  type ResourceKind,
  type S1000dIssue,
  type TreeNode,
  type WizardState,
} from "../lib/api";

const DM_TYPES = ["descriptive", "procedural", "ipd"] as const;
const DEFAULT_STEPS: WizardState["step"][] = ["split", "type", "structure", "generate"];

function ConfirmButton({
  label,
  onConfirm,
}: {
  label: string;
  onConfirm: () => void;
}) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  return (
    <button
      type="button"
      className="btn danger small"
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
      {armed ? "Cliquer encore pour confirmer" : label}
    </button>
  );
}

// Les enums du backend ne sont jamais rendus tels quels (HR21) : ils passent par
// une cle i18n.
function DmTypeBadge({ type }: { type: string }) {
  const { t } = useTranslation();
  return (
    <span className={`badge ${type === "procedural" ? "warn" : "ok"}`}>
      {t(`dmType.${type}`, { defaultValue: type })}
    </span>
  );
}

// Un appariement `contains` peut ancrer un DM au mauvais endroit : il ne doit
// jamais s'afficher comme une certitude.
function MatchBadge({ row }: { row: DmrlRow }) {
  const { t } = useTranslation();
  if (!row.matched) return <span className="badge warn">{t("migration.match.notFound")}</span>;
  const page = row.page ?? "?";
  if (row.match_rank === "exact")
    return <span className="badge ok">{t("migration.match.exact", { page })}</span>;
  return (
    <span className="badge warn" title={row.matched_text}>
      {t(`migration.match.${row.match_rank || "contains"}`, { page })}
    </span>
  );
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
  const { t } = useTranslation();
  const el = node.candidates?.[0]?.element ?? node.kind;
  const low = node.confidence != null && node.confidence < 0.6 ? " low" : "";
  const suspected = node.zone === "header" || node.zone === "footer" || node.zone === "cover" || node.zone === "toc";
  const ctx = node.context && node.context !== "unknown" ? node.context : null;
  const alts = (node.candidates ?? []).slice(1);
  return (
    <li>
      <div className={`tnode${low}${suspected ? " suspected" : ""}`}>
        <span className="el">{el}</span>
        {ctx ? <span className="ctx">{t(`dmType.${ctx}`, { defaultValue: ctx })}</span> : null}
        {node.kind === "section" && node.level != null ? (
          <span className="badge info">{t("migration.structure.level", { level: node.level })}</span>
        ) : null}
        <PageFlag page={node.page} />
        <ZoneFlag zone={node.zone} />
        <ReviewFlag zone={node.zone} />
        <TableFlag kind={node.kind} />
        <RefFlag refs={node.refs} />
        {/* Texte complet : la coupe visuelle est faite en CSS, la donnee reste intacte. */}
        {node.text ? (
          <span className="txt tnode-text" title={node.text}>
            {" "}
            {node.text}
          </span>
        ) : null}
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
  const { t } = useTranslation();
  const qc = useQueryClient();
  const brexQuery = useQuery({ queryKey: ["brex"], queryFn: brexApi.list });
  const docsQuery = useQuery({ queryKey: ["s1000d-docs"], queryFn: documentsApi.list });

  // Formulaire de chargement.
  const [file, setFile] = useState<File | null>(null);
  const [issue, setIssue] = useState<S1000dIssue>("4.2");
  const [hint, setHint] = useState<ContextHint>("mixed");
  const [brexId, setBrexId] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  // Ressources client optionnelles, attachees au document avant le decoupage.
  const [resourceFiles, setResourceFiles] = useState<Partial<Record<ResourceKind, File>>>({});

  // Assistant.
  const [docId, setDocId] = useState<string | null>(null);
  const [wiz, setWiz] = useState<WizardState | null>(null);
  const [starting, setStarting] = useState<{ pct: number; label: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [wizError, setWizError] = useState<string | null>(null);
  const [pdfCut, setPdfCut] = useState<{
    docId: string;
    detection: PdfCutDetection;
    startPage: number | null;
    endPage: number | null;
  } | null>(null);
  const [pdfCutBusy, setPdfCutBusy] = useState(false);

  // Éditions locales de l'étape courante (réinitialisées à chaque nouvel état).
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [titleEdits, setTitleEdits] = useState<Record<string, string>>({});
  const [dmrlEdits, setDmrlEdits] = useState<Record<number, string>>({});
  const [typeEdits, setTypeEdits] = useState<Record<string, string>>({});
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [splitLevel, setSplitLevel] = useState("section");
  const [splitMsg, setSplitMsg] = useState<string | null>(null);
  const wizRef = useRef<HTMLDivElement>(null);
  const inputRefs = useRef<Partial<Record<MigrationInputKind, HTMLInputElement | null>>>({});
  const mappingTouched = useRef(false);

  const restoreFileInput = (kind: MigrationInputKind, fileToRestore: File) => {
    const input = inputRefs.current[kind];
    if (!input || typeof DataTransfer === "undefined") return;
    const transfer = new DataTransfer();
    transfer.items.add(fileToRestore);
    input.files = transfer.files;
  };

  useEffect(() => {
    let cancelled = false;
    const loadSavedInputs = async () => {
      try {
        const mapping = await migrationInputsApi.read();
        if (cancelled || mappingTouched.current) return;
        setIssue(mapping.issue);
        setHint(mapping.context_hint);
        setBrexId(mapping.brex_id ?? "");
        const entries = Object.entries(mapping.files) as [
          MigrationInputKind,
          { filename: string },
        ][];
        const loaded = await Promise.all(
          entries.map(async ([kind, metadata]) => {
            try {
              return [kind, await migrationInputsApi.file(kind, metadata.filename)] as const;
            } catch {
              return null;
            }
          }),
        );
        if (cancelled || mappingTouched.current) return;
        const restoredResources: Partial<Record<ResourceKind, File>> = {};
        for (const item of loaded) {
          if (!item) continue;
          const [kind, restoredFile] = item;
          restoreFileInput(kind, restoredFile);
          if (kind === "document") setFile(restoredFile);
          else restoredResources[kind] = restoredFile;
        }
        setResourceFiles(restoredResources);
      } catch {
        // No mapping exists on a fresh installation.
      }
    };
    void loadSavedInputs();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setSelected(new Set());
    setTitleEdits({});
    setDmrlEdits({});
    setTypeEdits({});
    setOverrides({});
    setSplitMsg(null);
    if (wiz?.split_level) setSplitLevel(wiz.split_level);
  }, [wiz]);

  useEffect(() => {
    if (wiz?.step && wizRef.current) {
      wizRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [wiz?.step]);

  useEffect(() => {
    const onDocumentsReset = () => {
      setDocId(null);
      setWiz(null);
      setStarting(null);
      setPdfCut(null);
      setWizError(null);
    };
    window.addEventListener("s1000d-documents-reset", onDocumentsReset);
    return () => window.removeEventListener("s1000d-documents-reset", onDocumentsReset);
  }, []);

  const refreshDocs = () => void qc.invalidateQueries({ queryKey: ["s1000d-docs"] });

  const startAnalysis = async (id: string) => {
    setStarting({ pct: 5, label: t("migration.start.starting") });
    await startWizardStream(id, onStreamEvent);
    refreshDocs();
  };

  const startDocument = async (id: string, sourceFormat: string) => {
    setStarting({ pct: 5, label: t("migration.start.starting") });
    if (sourceFormat === "pdf") {
      const detection = await pdfCutApi.detect(id);
      if (
        detection.validation_required &&
        (detection.selected_page == null || detection.selected_end_page == null)
      ) {
        setPdfCut({
          docId: id,
          detection,
          startPage: detection.selected_page ?? detection.default_start_page,
          endPage: detection.selected_end_page ?? detection.total_pages,
        });
        setStarting(null);
        refreshDocs();
        return;
      }
    }
    await startAnalysis(id);
  };

  const stepLabel = (step: unknown) =>
    t(`migration.start.${String(step)}`, { defaultValue: t("migration.start.fallback") });

  const onStreamEvent = (ev: string, data: Record<string, unknown>) => {
    if (ev === "progress") {
      setStarting({ pct: (data.pct as number) || 0, label: stepLabel(data.step) });
    } else if (ev === "done") {
      setStarting(null);
      setPdfCut(null);
      setWiz(data as unknown as WizardState);
    } else if (ev === "error") {
      setStarting(null);
      setWizError((data.message as string) || t("migration.start.failed"));
    }
  };

  const doStart = async () => {
    if (!file) {
      setLoadError(t("migration.upload.noFile"));
      return;
    }
    setLoadError(null);
    setWiz(null);
    setWizError(null);
    setPdfCut(null);
    try {
      const doc = await documentsApi.upload(file, issue, hint, brexId || undefined);
      setDocId(doc.id);
      // La DMRL doit etre attachee AVANT le demarrage : elle pilote le decoupage.
      for (const [kind, resource] of Object.entries(resourceFiles)) {
        if (resource) await resourcesApi.upload(doc.id, kind as ResourceKind, resource);
      }
      await startDocument(doc.id, doc.source_format);
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
      try {
        const doc = await documentsApi.get(id);
        await startDocument(id, doc.source_format);
      } catch (e) {
        setStarting(null);
        setWizError(e instanceof Error ? e.message : String(e));
      }
    }
  };

  const confirmPdfCut = async () => {
    if (!pdfCut || pdfCut.startPage == null || pdfCut.endPage == null) return;
    const pending = pdfCut;
    const startPage = pending.startPage;
    const endPage = pending.endPage;
    if (startPage == null || endPage == null) return;
    if (startPage > endPage) {
      setLoadError(t("migration.upload.pdfCut.invalidRange"));
      return;
    }
    setPdfCutBusy(true);
    setLoadError(null);
    try {
      await pdfCutApi.confirm(pending.docId, startPage, endPage);
      setPdfCut(null);
      await startAnalysis(pending.docId);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally {
      setPdfCutBusy(false);
    }
  };

  const deleteDocument = async (id: string) => {
    try {
      const confirmToken = btoa(Math.random().toString()).substring(0, 16);
      await documentsApi.delete(id, confirmToken);
      if (docId === id) {
        setDocId(null);
        setWiz(null);
      }
      setWizError(null);
      refreshDocs();
    } catch (e) {
      setWizError(e instanceof Error ? e.message : String(e));
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

  const validateTypes = () => {
    const types: Record<string, string> = {};
    for (const d of wiz?.dms ?? []) types[d.dm_id] = typeEdits[d.dm_id] ?? d.dm_type;
    void wizAction("advance", { types });
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
        <h1>{t("migration.title")}</h1>
        <p>{t("migration.subtitle")}</p>
      </div>

      <div className="card">
        <h2 className="card-title">{t("migration.upload.title")}</h2>
        <div className="form">
          <div className="row">
            <label className="grow">
              <div className="label">{t("migration.upload.file")}</div>
              <input
                className="input"
                type="file"
                accept=".pdf,.docx"
                ref={(element) => {
                  inputRefs.current.document = element;
                }}
                onChange={(e) => {
                  mappingTouched.current = true;
                  setFile(e.target.files?.[0] ?? null);
                }}
              />
            </label>
          </div>
          <div className="row">
            <label className="grow">
              <div className="label">{t("migration.upload.issue")}</div>
              <select
                value={issue}
                onChange={(e) => {
                  mappingTouched.current = true;
                  setIssue(e.target.value as S1000dIssue);
                }}
              >
                <option value="4.2">{t("migration.upload.issueValue", { issue: "4.2" })}</option>
                <option value="4.1">{t("migration.upload.issueValue", { issue: "4.1" })}</option>
                <option value="5.0">{t("migration.upload.issueValue", { issue: "5.0" })}</option>
              </select>
            </label>
            <label className="grow">
              <div className="label">{t("migration.upload.hint")}</div>
              <select
                value={hint}
                onChange={(e) => {
                  mappingTouched.current = true;
                  setHint(e.target.value as ContextHint);
                }}
              >
                <option value="mixed">{t("migration.upload.hintMixed")}</option>
                <option value="descriptive">{t("dmType.descriptive")}</option>
                <option value="procedural">{t("dmType.procedural")}</option>
              </select>
            </label>
            <label className="grow">
              <div className="label">{t("migration.upload.brex")}</div>
              <select
                value={brexId}
                onChange={(e) => {
                  mappingTouched.current = true;
                  setBrexId(e.target.value);
                }}
              >
                <option value="">{t("migration.upload.brexNone")}</option>
                {brex.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name} [{b.s1000d_issue}]
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="row">
            <label className="grow">
              <div className="label">{t("migration.upload.dmrl")}</div>
              <input
                className="input"
                type="file"
                accept=".xlsx,.xlsm,.csv,.json"
                ref={(element) => {
                  inputRefs.current.dmrl = element;
                }}
                onChange={(e) => {
                  mappingTouched.current = true;
                  setResourceFiles((p) => ({ ...p, dmrl: e.target.files?.[0] }));
                }}
              />
            </label>
            <label className="grow">
              <div className="label">{t("migration.upload.cir")}</div>
              <input
                className="input"
                type="file"
                accept=".xml"
                ref={(element) => {
                  inputRefs.current.cir = element;
                }}
                onChange={(e) => {
                  mappingTouched.current = true;
                  setResourceFiles((p) => ({ ...p, cir: e.target.files?.[0] }));
                }}
              />
            </label>
            <label className="grow">
              <div className="label">{t("migration.upload.rules")}</div>
              <input
                className="input"
                type="file"
                accept=".json"
                ref={(element) => {
                  inputRefs.current.brex_rules = element;
                }}
                onChange={(e) => {
                  mappingTouched.current = true;
                  setResourceFiles((p) => ({ ...p, brex_rules: e.target.files?.[0] }));
                }}
              />
            </label>
            <label className="grow">
              <div className="label">{t("migration.upload.dmHeader")}</div>
              <input
                className="input"
                type="file"
                accept=".json,.xml"
                ref={(element) => {
                  inputRefs.current.dm_header = element;
                }}
                onChange={(e) => {
                  mappingTouched.current = true;
                  setResourceFiles((p) => ({ ...p, dm_header: e.target.files?.[0] }));
                }}
              />
            </label>
          </div>
          <div className="row">
            <button
              type="button"
              className="btn primary"
              disabled={busy || starting !== null || pdfCut !== null || pdfCutBusy}
              onClick={() => void doStart()}
            >
              {t("migration.upload.start")}
            </button>
            {starting ? (
              <div style={{ minWidth: 240, flex: "1 1 280px" }}>
                <div
                  className="label"
                  style={{ display: "flex", justifyContent: "space-between", gap: 12 }}
                >
                  <span>{starting.label}</span>
                  <span>{starting.pct}%</span>
                </div>
                <div
                  className="progress"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={starting.pct}
                >
                  <span style={{ width: `${starting.pct}%` }} />
                </div>
              </div>
            ) : null}
            {loadError ? <span className="error grow">{loadError}</span> : null}
          </div>
        </div>
      </div>

      {pdfCut ? (
        <div className="card">
          <h2 className="card-title">{t("migration.upload.pdfCut.title")}</h2>
          <p className="label">{t("migration.upload.pdfCut.help")}</p>
          <div className="row" style={{ alignItems: "end" }}>
            <label>
              <div className="label">{t("migration.upload.pdfCut.startPage")}</div>
              <input
                className="input"
                type="number"
                min={1}
                max={pdfCut.detection.total_pages}
                value={pdfCut.startPage ?? ""}
                disabled={pdfCutBusy}
                onChange={(e) =>
                  setPdfCut((current) =>
                    current ? { ...current, startPage: Number(e.target.value) || null } : current,
                  )
                }
              />
            </label>
            <label>
              <div className="label">{t("migration.upload.pdfCut.endPage")}</div>
              <input
                className="input"
                type="number"
                min={1}
                max={pdfCut.detection.total_pages}
                value={pdfCut.endPage ?? ""}
                disabled={pdfCutBusy}
                onChange={(e) =>
                  setPdfCut((current) =>
                    current ? { ...current, endPage: Number(e.target.value) || null } : current,
                  )
                }
              />
            </label>
            <button
              type="button"
              className="btn primary"
              disabled={
                pdfCutBusy ||
                pdfCut.startPage == null ||
                pdfCut.endPage == null ||
                pdfCut.startPage > pdfCut.endPage
              }
              onClick={() => void confirmPdfCut()}
            >
              {t("migration.upload.pdfCut.validate")}
            </button>
          </div>
          {pdfCut.startPage != null ? (
            <img
              src={pdfCutApi.previewUrl(pdfCut.docId, pdfCut.startPage)}
              alt={t("migration.upload.pdfCut.previewAlt", { page: pdfCut.startPage })}
              style={{
                display: "block",
                maxWidth: "100%",
                maxHeight: 560,
                marginTop: 16,
                objectFit: "contain",
                border: "1px solid var(--border)",
              }}
            />
          ) : null}
        </div>
      ) : null}

      <div className="card">
        <h2 className="card-title">{t("migration.docs.title")}</h2>
        {docs.length === 0 ? (
          <div className="empty-state">{t("migration.docs.empty")}</div>
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
                    {t(`docStatus.${d.status}`, { defaultValue: d.status })}
                  </span>
                </div>
                <div className="label">{d.source_format.toUpperCase()}</div>
              </div>
              <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
                <button
                  type="button"
                  className="btn secondary small"
                  onClick={() => void openWizard(d.id)}
                >
                  {t("migration.docs.open")}
                </button>
                <ConfirmButton
                  label={t("migration.docs.delete")}
                  onConfirm={() => void deleteDocument(d.id)}
                />
              </div>
            </div>
          ))
        )}
      </div>

      {/* Assistant */}
      <div ref={wizRef}>
        {wizError ? <div className="card"><div className="error">{wizError}</div></div> : null}

        {wiz?.resources?.errors?.length ? (
          <div className="card">
            {wiz.resources.errors.map((e) => (
              <div key={e} className="error">
                {t("migration.resource.notApplied", { detail: e })}
              </div>
            ))}
          </div>
        ) : null}

        {wiz?.resources?.has_dm_header ? (
          <div className="card">
            <span className="badge ok">{t("migration.resource.headerLoaded")}</span>{" "}
            <span className="label">{t("migration.resource.headerLoadedHelp")}</span>
          </div>
        ) : null}

        {wiz ? (
          <>
            <div className="card">
              <div className="row" style={{ alignItems: "center" }}>
                {(wiz.steps ?? DEFAULT_STEPS).map((s, i) => (
                  <span key={s} style={{ display: "inline-flex", alignItems: "center" }}>
                    {i > 0 ? <span className="label">&nbsp;→&nbsp;</span> : null}
                    <span className={`badge ${s === wiz.step ? "ok" : ""}`}>
                      {i + 1}. {t(`migration.step.${s}`)}
                    </span>
                  </span>
                ))}
                {wiz.resources?.dmrl_count && docId ? (
                  <>
                    <a
                      className="btn secondary small"
                      style={{ marginLeft: "auto" }}
                      href={resourcesApi.pmcUrl(docId)}
                    >
                      {t("migration.generate.pmc")}
                    </a>
                    {wiz.step === "generate" ? (
                      <a
                        className="btn primary small"
                        href={wizardApi.zipUrl(docId)}
                      >
                        {t("migration.generate.zip")}
                      </a>
                    ) : null}
                  </>
                ) : null}
              </div>
            </div>

            {wiz.step === "dmrl" ? (
              <div className="card">
                <h2 className="card-title">
                  {t("migration.dmrl.title", { count: wiz.dmrl?.length ?? 0 })}
                </h2>
                <p className="label">
                  {t("migration.dmrl.help")}{" "}
                  {t("migration.dmrl.counts", {
                    missing: (wiz.dmrl ?? []).filter((r) => !r.matched).length,
                    uncertain: (wiz.dmrl ?? []).filter(
                      (r) => r.matched && r.match_rank !== "exact",
                    ).length,
                  })}
                </p>
                <div className="row" style={{ marginBottom: 10 }}>
                  <button
                    type="button"
                    className="btn primary"
                    style={{ marginLeft: "auto" }}
                    disabled={busy}
                    onClick={() => void wizAction("advance", {})}
                  >
                    {t("migration.dmrl.validate")}
                  </button>
                </div>
                <div>
                  {(wiz.dmrl ?? []).map((row) => (
                    <div
                      key={row.index}
                      className="row"
                      style={{ borderBottom: "1px solid var(--border)", padding: "6px 0" }}
                    >
                      <span className="badge info">{row.arbo || t("common.none")}</span>
                      <input
                        className="input grow"
                        value={dmrlEdits[row.index] ?? row.title}
                        onChange={(e) =>
                          setDmrlEdits((p) => ({ ...p, [row.index]: e.target.value }))
                        }
                      />
                      <select
                        value={row.dm_type || "descriptive"}
                        onChange={(e) =>
                          void wizAction("update", {
                            op: "set_type",
                            index: row.index,
                            dm_type: e.target.value,
                          })
                        }
                      >
                        {DM_TYPES.map((tp) => (
                          <option key={tp} value={tp}>
                            {t(`dmType.${tp}`)}
                          </option>
                        ))}
                      </select>
                      <MatchBadge row={row} />
                      <span className="label" title={row.dmc}>
                        {row.dmc || t("common.none")}
                      </span>
                      <span
                        className="label"
                        title={row.icn || undefined}
                        style={{ maxWidth: 280, whiteSpace: "pre-line", overflowWrap: "anywhere" }}
                      >
                        <strong>{t("migration.dmrl.icn")}:</strong>{" "}
                        {row.icn || t("common.none")}
                      </span>
                      <button
                        type="button"
                        className="btn ghost small"
                        disabled={busy}
                        onClick={() =>
                          void wizAction("update", {
                            op: "rename",
                            index: row.index,
                            title: dmrlEdits[row.index] ?? row.title,
                          })
                        }
                      >
                        {t("migration.dmrl.rename")}
                      </button>
                      <button
                        type="button"
                        className="btn danger small"
                        disabled={busy}
                        onClick={() =>
                          void wizAction("update", { op: "exclude", index: row.index })
                        }
                      >
                        {t("migration.dmrl.exclude")}
                      </button>
                    </div>
                  ))}
                </div>
                <div className="row" style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn primary"
                    style={{ marginLeft: "auto" }}
                    disabled={busy}
                    onClick={() => void wizAction("advance", {})}
                  >
                    {t("migration.dmrl.validate")}
                  </button>
                </div>
              </div>
            ) : null}

            {wiz.step === "split" ? (
              <div className="card">
                <h2 className="card-title">
                  {t("migration.split.title", { count: wiz.dms.length })}
                </h2>
                {wiz.resources?.dmrl_count ? (
                  <p className="label">
                    <span className="badge ok">{t("migration.step.dmrl")}</span>{" "}
                    {t("migration.split.dmrlDriven", { count: wiz.resources.dmrl_count })}
                  </p>
                ) : null}
                <div className="row" style={{ marginBottom: 10 }}>
                  <label>
                    <div className="label">{t("migration.split.level")}</div>
                    <select
                      value={splitLevel}
                      onChange={(e) => setSplitLevel(e.target.value)}
                    >
                      <option value="chapter">{t("migration.split.levelChapter")}</option>
                      <option value="section">{t("migration.split.levelSection")}</option>
                      <option value="subsection">{t("migration.split.levelSubsection")}</option>
                    </select>
                  </label>
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={busy}
                    onClick={() => void wizAction("update", { split_level: splitLevel })}
                  >
                    {t("migration.split.reanalyze")}
                  </button>
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={busy}
                    onClick={() => {
                      const ids = [...selected];
                      if (ids.length < 2) {
                        setSplitMsg(t("migration.split.needTwo"));
                        return;
                      }
                      void wizAction("update", { op: "merge", ids });
                    }}
                  >
                    {t("migration.split.merge")}
                  </button>
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={busy}
                    onClick={() =>
                      void wizAction("update", { op: "hide_zones", zones: ["header", "footer"] })
                    }
                  >
                    {t("migration.split.hideZones")}
                  </button>
                  <button
                    type="button"
                    className="btn ghost"
                    disabled={busy || !wiz.can_undo}
                    onClick={() => void wizAction("update", { op: "undo" })}
                  >
                    {t("migration.split.undo")}
                  </button>
                  {splitMsg ? <span className="error grow">{splitMsg}</span> : null}
                  <button
                    type="button"
                    className="btn primary"
                    style={{ marginLeft: "auto" }}
                    disabled={busy}
                    onClick={validateSplit}
                  >
                    {t("migration.split.validate")}
                  </button>
                </div>
                <p className="label">{t("migration.split.help")}</p>
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
                        value={titleEdits[d.dm_id] ?? (d.is_orphan ? t("migration.dm.orphan") : d.title)}
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
                        {t("migration.split.rename")}
                      </button>
                      <button
                        type="button"
                        className="btn ghost small"
                        disabled={busy}
                        onClick={() => void wizAction("update", { op: "split", id: d.dm_id })}
                      >
                        {t("migration.split.split")}
                      </button>
                      <button
                        type="button"
                        className="btn danger small"
                        disabled={busy}
                        onClick={() => void wizAction("update", { op: "exclude", id: d.dm_id })}
                      >
                        {t("migration.split.exclude")}
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
                    {t("migration.split.validate")}
                  </button>
                </div>
              </div>
            ) : null}

            {wiz.step === "type" ? (
              <div className="card">
                <h2 className="card-title">{t("migration.type.title")}</h2>
                <div className="row" style={{ marginBottom: 10 }}>
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={busy}
                    onClick={() => void wizAction("back")}
                  >
                    {t("common.back")}
                  </button>
                  <button
                    type="button"
                    className="btn primary"
                    style={{ marginLeft: "auto" }}
                    disabled={busy}
                    onClick={validateTypes}
                  >
                    {t("migration.type.validate")}
                  </button>
                </div>
                <p className="label">{t("migration.type.help")}</p>
                <div>
                  {wiz.dms.map((d) => (
                    <div
                      key={d.dm_id}
                      className="row"
                      style={{ borderBottom: "1px solid var(--border)", padding: "6px 0" }}
                    >
                      <span className="grow">
                        {d.is_orphan ? t("migration.dm.orphan") : d.title}
                      </span>
                      <select
                        value={typeEdits[d.dm_id] ?? d.dm_type}
                        onChange={(e) =>
                          setTypeEdits((p) => ({ ...p, [d.dm_id]: e.target.value }))
                        }
                      >
                        {DM_TYPES.map((tp) => (
                          <option key={tp} value={tp}>
                            {t(`dmType.${tp}`)}
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
                    {t("common.back")}
                  </button>
                  <button
                    type="button"
                    className="btn primary"
                    disabled={busy}
                    onClick={validateTypes}
                  >
                    {t("migration.type.validate")}
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
                      {t("common.back")}
                    </button>
                    <button
                      type="button"
                      className="btn primary"
                      style={{ marginLeft: "auto" }}
                      disabled={busy}
                      onClick={validateStructure}
                    >
                      {t("migration.structure.validate")}
                    </button>
                  </div>
                </div>
                {wiz.dms.map((d) => (
                  <div className="card" key={d.dm_id}>
                    <h2 className="card-title">
                      {d.is_orphan ? t("migration.dm.orphan") : d.title}{" "}
                      <DmTypeBadge type={d.dm_type} />
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
                      {t("common.back")}
                    </button>
                    <button
                      type="button"
                      className="btn primary"
                      disabled={busy}
                      onClick={validateStructure}
                    >
                      {t("migration.structure.validate")}
                    </button>
                  </div>
                </div>
              </>
            ) : null}

            {wiz.step === "generate" ? (
              <div className="card">
                <h2 className="card-title">
                  {t("migration.generate.title", { count: wiz.dms.length })}
                </h2>
                <div>
                  {wiz.dms.map((d) => (
                    <div
                      key={d.dm_id}
                      className="row"
                      style={{ borderBottom: "1px solid var(--border)", padding: "8px 0" }}
                    >
                      <span className="grow">
                        {d.is_orphan ? t("migration.dm.orphan") : d.title}{" "}
                        <DmTypeBadge type={d.dm_type} />{" "}
                        <span className={`badge ${d.violation_count ? "warn" : "ok"}`}>
                          {t("migration.generate.violations", { count: d.violation_count })}
                        </span>
                        {d.missing_fields?.length ? (
                          <span className="badge warn">
                            {t("migration.generate.missingFields", {
                              count: d.missing_fields.length,
                            })}
                          </span>
                        ) : null}
                        {d.cir_unresolved?.length ? (
                          <span className="badge warn">
                            {t("migration.generate.cirUnresolved", {
                              count: d.cir_unresolved.length,
                            })}
                          </span>
                        ) : null}
                      </span>
                      <a
                        className="btn secondary small"
                        href={docId ? wizardApi.dmXmlUrl(docId, d.dm_id) : "#"}
                      >
                        {t("migration.generate.xml")}
                      </a>
                    </div>
                  ))}
                </div>
                {images.length ? (
                  <div style={{ marginTop: 16 }}>
                    <h3 className="label">
                      {t("migration.generate.images", { count: images.length })}
                    </h3>
                    <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
                      {images.map((name, i) => (
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
                            alt={t("migration.generate.imageAlt", { index: i + 1 })}
                            style={{
                              width: 96,
                              height: 72,
                              objectFit: "cover",
                              border: "1px solid var(--border)",
                              borderRadius: 4,
                            }}
                          />
                          <span
                            title={name}
                            style={{ maxWidth: 96, overflow: "hidden", textOverflow: "ellipsis" }}
                          >
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
                    {t("common.back")}
                  </button>
                  <a
                    className="btn primary"
                    href={docId ? wizardApi.zipUrl(docId) : "#"}
                  >
                    {t("migration.generate.zip")}
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
