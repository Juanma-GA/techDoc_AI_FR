import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleHelp, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { DmPreview } from "../components/DmPreview";
import { PageFlag, RefFlag, ReviewFlag, TableFlag, ZoneFlag } from "../components/zoneFlags";
import {
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
  type WizardDm,
  type WizardState,
} from "../lib/api";

export function getCommonMissingFields(
  dms: readonly Pick<WizardDm, "missing_fields">[],
): string[] {
  if (dms.length < 2) return [];
  const firstFields = [...new Set(dms[0].missing_fields ?? [])];
  return firstFields.filter((field) => dms.every((dm) => dm.missing_fields?.includes(field)));
}

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
    <span className="badge info">
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
  const navigate = useNavigate();
  const qc = useQueryClient();
  const docsQuery = useQuery({ queryKey: ["s1000d-docs"], queryFn: documentsApi.list });

  // Formulaire de chargement.
  const [file, setFile] = useState<File | null>(null);
  const [issue, setIssue] = useState<S1000dIssue>("4.2");
  const hint: ContextHint = "mixed";
  const [loadError, setLoadError] = useState<string | null>(null);
  // Ressources client optionnelles, attachees au document avant le decoupage.
  const [resourceFiles, setResourceFiles] = useState<Partial<Record<ResourceKind, File>>>({});

  // Assistant.
  const [docId, setDocId] = useState<string | null>(null);
  const [wiz, setWiz] = useState<WizardState | null>(null);
  const [starting, setStarting] = useState<{
    pct: number;
    label: string;
    indeterminate?: boolean;
  } | null>(null);
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
        setIssue(mapping.issue === "5.0" ? "4.2" : mapping.issue);
        const entries = (Object.entries(mapping.files) as [
          MigrationInputKind,
          { filename: string },
        ][]).filter(([kind]) => kind !== "brex_rules" && kind !== "cir");
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

  const normalizeWizard = async (
    id: string,
    initial: WizardState,
    includeSplit = false,
  ): Promise<WizardState> => {
    let state = initial;
    if (state.step === "dmrl") state = await wizardApi.action(id, "advance", {});
    if (state.step === "split") {
      if (!includeSplit) return state;
      state = await wizardApi.action(id, "advance", {});
    }
    if (state.step === "type") state = await wizardApi.action(id, "advance", { types: {} });
    if (state.step === "structure") {
      state = await wizardApi.action(id, "advance", { overrides: [] });
    }
    return state;
  };

  const startAnalysis = async (id: string) => {
    setStarting({ pct: 5, label: t("migration.start.starting"), indeterminate: true });
    await startWizardStream(id, (ev, data) => onStreamEvent(ev, data, id));
    refreshDocs();
  };

  const startDocument = async (id: string, sourceFormat: string) => {
    setStarting({ pct: 5, label: t("migration.start.starting"), indeterminate: true });
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

  const onStreamEvent = (ev: string, data: Record<string, unknown>, activeDocId?: string) => {
    if (ev === "progress") {
      const step = String(data.step ?? "");
      setStarting({
        pct: typeof data.pct === "number" ? data.pct : 0,
        label: stepLabel(step),
        indeterminate: ["ocr", "infer", "split", "classify"].includes(step),
      });
    } else if (ev === "done") {
      setPdfCut(null);
      const id = activeDocId ?? docId;
      const initial = data as unknown as WizardState;
      if (!id) {
        setStarting(null);
        setWiz(initial);
        return;
      }
      setStarting({ pct: 100, label: t("migration.start.preparing") });
      setBusy(true);
      void normalizeWizard(id, initial)
        .then(setWiz)
        .catch((error: unknown) => {
          setWizError(error instanceof Error ? error.message : String(error));
        })
        .finally(() => {
          setStarting(null);
          setBusy(false);
          refreshDocs();
        });
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
      const doc = await documentsApi.upload(file, issue, hint);
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
    let state: WizardState;
    try {
      state = await wizardApi.get(id);
    } catch {
      try {
        const doc = await documentsApi.get(id);
        await startDocument(id, doc.source_format);
      } catch (e) {
        setStarting(null);
        setWizError(e instanceof Error ? e.message : String(e));
      }
      return;
    }
    try {
      setWiz(await normalizeWizard(id, state));
    } catch (e) {
      setWizError(e instanceof Error ? e.message : String(e));
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

  const validateAndGenerate = async () => {
    if (!docId) return;
    setBusy(true);
    setWizError(null);
    try {
      const current = await wizardApi.get(docId);
      setWiz(await normalizeWizard(docId, current, true));
      refreshDocs();
    } catch (error) {
      setWizError(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

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

  const docs = docsQuery.data ?? [];
  const images = imagesQuery.data ?? [];
  const generationDms = wiz?.step === "generate" ? wiz.dms : [];
  const commonMissingFields = getCommonMissingFields(generationDms);
  const commonMissingFieldSet = new Set(commonMissingFields);
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
              </select>
            </label>
            <label className="grow">
              <div className="migration-upload-label">
                <span className="label">{t("migration.upload.brex")}</span>
                <span className="migration-upload-status" id="migration-brex-status">
                  {t("migration.upload.inDevelopment")}
                </span>
              </div>
              <select
                className="input"
                value=""
                disabled
                aria-describedby="migration-brex-status"
              >
                <option value="">{t("migration.upload.inDevelopment")}</option>
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
              <div className="migration-upload-label">
                <span className="label">{t("migration.upload.cir")}</span>
                <span className="migration-upload-status" id="migration-cir-status">
                  {t("migration.upload.inDevelopment")}
                </span>
              </div>
              <input
                className="input"
                type="file"
                accept=".xml"
                disabled
                aria-describedby="migration-cir-status"
              />
            </label>
            <div className="grow">
              <div className="migration-upload-label">
                <label className="label" htmlFor="migration-dm-header">
                  {t("migration.upload.dmHeader")}
                </label>
                <button
                  type="button"
                  className="migration-upload-help"
                  title={t("migration.upload.dmHeaderHelp")}
                  aria-label={t("migration.upload.dmHeaderHelp")}
                >
                  <CircleHelp aria-hidden="true" size={15} />
                </button>
              </div>
              <input
                id="migration-dm-header"
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
            </div>
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
                  {starting.indeterminate ? null : <span>{starting.pct}%</span>}
                </div>
                <div
                  className={`progress${starting.indeterminate ? " indeterminate" : ""}`}
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={starting.indeterminate ? undefined : starting.pct}
                  aria-valuetext={starting.indeterminate ? starting.label : undefined}
                >
                  <span
                    style={starting.indeterminate ? undefined : { width: `${starting.pct}%` }}
                  />
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

        {wiz ? (
          <>
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
                <p className="label">{t("migration.analysis.help")}</p>
                {wiz.resources?.dmrl_count ? (
                  <p className="label">
                    {t("migration.split.dmrlDriven", { count: wiz.resources.dmrl_count })}
                  </p>
                ) : null}
                <details className="migration-split-review">
                  <summary>{t("migration.split.review", { count: wiz.dms.length })}</summary>
                  <div className="migration-split-review-content">
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
                  </div>
                </details>
                <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
                  <button
                    type="button"
                    className="btn primary"
                    disabled={busy}
                    onClick={validateAndGenerate}
                  >
                    {busy
                      ? t("migration.analysis.processing")
                      : t("migration.analysis.validate")}
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
                <div className="row" style={{ marginBottom: 12 }}>
                  {wiz.resources?.dmrl_count && docId ? (
                    <a className="btn secondary" href={resourcesApi.pmcUrl(docId)}>
                      {t("migration.generate.pmc")}
                    </a>
                  ) : null}
                  {docId && wiz.dms.some((dm) => dm.has_xml) ? (
                    <button
                      type="button"
                      className="btn secondary"
                      onClick={() => navigate("/validation", {
                        state: {
                          generated: {
                            documentId: docId,
                            dmIds: wiz.dms.filter((dm) => dm.has_xml).map((dm) => dm.dm_id),
                          },
                        },
                      })}
                    >
                      <ShieldCheck aria-hidden="true" size={15} /> {t("migration.generate.validate")}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="btn primary"
                    style={{ marginLeft: "auto" }}
                    disabled={
                      busy ||
                      !docId ||
                      wiz.dms.length === 0 ||
                      wiz.dms.some((dm) => !dm.has_xml)
                    }
                    title={
                      wiz.dms.some((dm) => !dm.has_xml)
                        ? t("migration.generate.generationPending")
                        : undefined
                    }
                    onClick={() => {
                      if (docId) window.location.assign(wizardApi.zipUrl(docId));
                    }}
                  >
                    {t("migration.generate.zip")}
                  </button>
                </div>
                {commonMissingFields.length ? (
                  <div className="banner warn" role="status" style={{ marginBottom: 12 }}>
                    <strong>{t("migration.generate.commonMissingFields")}</strong>
                    <details style={{ marginTop: 8 }}>
                      <summary>
                        {t("migration.generate.missingFields", {
                          count: commonMissingFields.length,
                        })}
                      </summary>
                      <ul>
                        {commonMissingFields.map((field) => (
                          <li key={field} style={{ overflowWrap: "anywhere" }}>
                            {field}
                          </li>
                        ))}
                      </ul>
                    </details>
                  </div>
                ) : null}
                <div>
                  {wiz.dms.map((dm) => {
                    const dmMissingFields = (dm.missing_fields ?? []).filter(
                      (field) => !commonMissingFieldSet.has(field),
                    );
                    const hasXsdFailure = dm.xsd_valid === false;
                    return (
                      <div
                        key={dm.dm_id}
                        style={{ borderBottom: "1px solid var(--border)", padding: "8px 0" }}
                      >
                        <div className="row">
                          <span className="grow">
                            {dm.is_orphan ? t("migration.dm.orphan") : dm.title}{" "}
                            <DmTypeBadge type={dm.dm_type} />{" "}
                            {dm.cir_unresolved?.length ? (
                              <span className="badge warn" title={dm.cir_unresolved.join(", ")}>
                                {t("migration.generate.cirUnresolved", {
                                  count: dm.cir_unresolved.length,
                                })}
                              </span>
                            ) : null}
                          </span>
                          {docId && dm.has_xml ? (
                            <a
                              className="btn secondary small"
                              href={wizardApi.dmXmlUrl(docId, dm.dm_id)}
                            >
                              {t("migration.generate.xml")}
                            </a>
                          ) : (
                            <button
                              type="button"
                              className="btn secondary small"
                              disabled
                              title={t("migration.generate.generationPending")}
                            >
                              {t("migration.generate.xml")}
                            </button>
                          )}
                        </div>
                        {hasXsdFailure || dmMissingFields.length ? (
                          <div
                            className={hasXsdFailure ? "alert error" : "banner warn"}
                            role={hasXsdFailure ? "alert" : "status"}
                            style={{ marginTop: 8 }}
                          >
                            <strong>
                              {hasXsdFailure
                                ? t("migration.generate.xsdIncomplete")
                                : dm.xsd_valid === true
                                  ? t("migration.generate.missingDataWarning")
                                  : t("migration.generate.xsdNoDetails")}
                            </strong>
                            {hasXsdFailure && dm.xsd_violations?.length ? (
                              <ul>
                                {dm.xsd_violations.map((violation, index) => (
                                  <li key={`${violation.rule}-${index}`}>
                                    <code>{violation.path}</code>: {violation.message}
                                  </li>
                                ))}
                              </ul>
                            ) : null}
                            {hasXsdFailure && !dm.xsd_violations?.length ? (
                              <p>{t("migration.generate.xsdNoDetails")}</p>
                            ) : null}
                          </div>
                        ) : null}
                        {dmMissingFields.length ? (
                          <details style={{ marginTop: 8 }}>
                            <summary>
                              {t("migration.generate.missingFields", {
                                count: dmMissingFields.length,
                              })}
                            </summary>
                            <ul>
                              {dmMissingFields.map((field) => (
                                <li key={field} style={{ overflowWrap: "anywhere" }}>
                                  {field}
                                </li>
                              ))}
                            </ul>
                          </details>
                        ) : null}
                      </div>
                    );
                  })}
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
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </>
  );
}
