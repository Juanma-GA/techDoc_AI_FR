import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { anomaliesApi, filesApi, projectsApi } from "../lib/api";
import { categoryOptions, matchesCategory } from "../lib/anomalyCategory";
import { resolveAnomalyText } from "../lib/anomalyText";
import { severityClass } from "../lib/format";
import { useScopeStore } from "../stores/useScopeStore";
import type { AnomalyOut, AnomalyStatus, FileOut, ProjectOut } from "../lib/types";

const STATUSES: AnomalyStatus[] = ["open", "acknowledged", "fixed", "rejected"];
const REJECTION_REASON_KEYS = [
  "redacteur.reason.falsePositive",
  "redacteur.reason.outOfScope",
  "redacteur.reason.alreadyCovered",
  "redacteur.reason.accepted",
] as const;
const STATUS_KEY: Record<AnomalyStatus, string> = {
  open: "redacteur.statusOpen",
  acknowledged: "redacteur.statusAck",
  fixed: "redacteur.statusFixed",
  rejected: "redacteur.statusRejected",
};
const SEV_KEY: Record<string, string> = { high: "redacteur.sevHigh", medium: "redacteur.sevMedium", low: "redacteur.sevLow" };

// Niveau de confiance IA porté par l'anomalie → libellé humain (parité preview `_confLabel`).
function confLabel(c: string | null | undefined): string {
  if (c === "elevee") return "confiance élevée";
  if (c === "moyenne") return "confiance moyenne";
  if (c === "faible") return "confiance faible";
  return "";
}

export function Redacteur() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const presel = useScopeStore((s) => s.redacteurProjectId);
  const [pid, setPid] = useState<string>(presel ?? "");
  const [fCategory, setFCategory] = useState("");
  const [fSev, setFSev] = useState("");
  const [fConf, setFConf] = useState("");
  const [fStatus, setFStatus] = useState("");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const projectsQuery = useQuery<ProjectOut[]>({ queryKey: ["projects"], queryFn: projectsApi.list });
  const filesQuery = useQuery<FileOut[]>({ queryKey: ["files", pid], queryFn: () => filesApi.list(pid), enabled: !!pid });
  const anomaliesQuery = useQuery<AnomalyOut[]>({ queryKey: ["anomalies", pid], queryFn: () => anomaliesApi.list(pid), enabled: !!pid });

  const setStatus = useMutation({
    mutationFn: ({ id, status, feedback }: { id: string; status: AnomalyStatus; feedback?: string }) =>
      anomaliesApi.setStatus(id, status, feedback),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["anomalies", pid] }),
  });
  const bulk = useMutation({
    mutationFn: ({ ids, status }: { ids: string[]; status: AnomalyStatus }) => anomaliesApi.bulkStatus(ids, status),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["anomalies", pid] }),
  });

  const filenameOf = useMemo(() => {
    const m = new Map<string, string>();
    for (const f of filesQuery.data ?? []) for (const v of f.versions) m.set(v.id, f.current_name);
    return m;
  }, [filesQuery.data]);

  const anomalies = useMemo(
    () => (anomaliesQuery.data ?? []).filter((a) => a.type !== "dmc_missing"),
    [anomaliesQuery.data],
  );

  // Options du filtre « Catégorie » = Sujets réellement présents dans le projet
  // (cf. `lib/anomalyCategory`). Calculées sur les anomalies NON filtrées pour
  // que le menu ne rétrécisse pas au fil des sélections.
  const catOptions = useMemo(
    () => categoryOptions(anomalies, i18n.language, t("redacteur.filterNoCategory")),
    [anomalies, i18n.language, t],
  );

  const filtered = anomalies.filter(
    (a) =>
      matchesCategory(a, fCategory) &&
      (!fSev || a.severity === fSev) &&
      (!fConf || a.confidence === fConf) &&
      (!fStatus || a.status === fStatus),
  );

  const byFile = useMemo(() => {
    const groups = new Map<string, AnomalyOut[]>();
    for (const a of filtered) {
      const key = a.file_version_id ?? "—";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(a);
    }
    return [...groups.entries()];
  }, [filtered]);

  const toggle = (key: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  return (
    <>
      <div className="page-header">
        <h1>{t("nav.redacteur")}</h1>
        <p>{t("redacteur.title")}</p>
      </div>

      <div className="card">
        <div className="row">
          <select value={pid} onChange={(e) => setPid(e.target.value)} style={{ maxWidth: 280 }}>
            <option value="">{t("redacteur.selectProject")}</option>
            {(projectsQuery.data ?? []).map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          {pid && (
            <button type="button" className="btn ghost small" onClick={() => void anomaliesApi.exportCsv(pid)}>
              CSV
            </button>
          )}
        </div>
      </div>

      {pid && (
        <div className="card">
          <div className="row">
            <Filter value={fCategory} onChange={setFCategory} label={t("redacteur.filterCategory")} options={catOptions} allLabel={t("redacteur.filterAll")} />
            <Filter value={fSev} onChange={setFSev} label={t("redacteur.filterSeverity")} options={["high", "medium", "low"].map((s) => [s, t(SEV_KEY[s] ?? s)])} allLabel={t("redacteur.filterAll")} />
            <Filter value={fConf} onChange={setFConf} label={t("redacteur.filterConfidence")} options={[["elevee", t("redacteur.confHigh")], ["moyenne", t("redacteur.confMedium")], ["faible", t("redacteur.confLow")]]} allLabel={t("redacteur.filterAll")} />
            <Filter value={fStatus} onChange={setFStatus} label={t("redacteur.filterStatus")} options={STATUSES.map((s) => [s, t(STATUS_KEY[s])])} allLabel={t("redacteur.filterAll")} />
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <button type="button" className="btn ghost small" onClick={() => setCollapsed(new Set(byFile.map(([k]) => k)))}>{t("redacteur.collapseAll")}</button>
            <button type="button" className="btn ghost small" onClick={() => setCollapsed(new Set())}>{t("redacteur.expandAll")}</button>
          </div>
        </div>
      )}

      {pid && (anomaliesQuery.isLoading ? (
        <div className="card"><div className="empty-state">{t("common.loading")}</div></div>
      ) : byFile.length === 0 ? (
        <div className="card"><div className="empty-state">—</div></div>
      ) : (
        byFile.map(([key, items]) => {
          const isCollapsed = collapsed.has(key);
          const openIds = items.filter((a) => a.status === "open" || a.status === "acknowledged").map((a) => a.id);
          return (
            <div className={`red-file-block${isCollapsed ? " collapsed" : ""}`} key={key}>
              <div className="red-file-header" onClick={() => toggle(key)}>
                <span><span className="caret">▼</span>{filenameOf.get(key) ?? "—"} <span className="badge danger">{items.length}</span></span>
                <span className="red-file-actions" onClick={(e) => e.stopPropagation()}>
                  <button type="button" className="btn ghost small" disabled={!openIds.length} onClick={() => bulk.mutate({ ids: openIds, status: "fixed" })}>
                    {t("redacteur.bulkFix")} ({openIds.length})
                  </button>
                  <button type="button" className="btn ghost small" disabled={!openIds.length} onClick={() => bulk.mutate({ ids: openIds, status: "rejected" })}>
                    {t("redacteur.bulkReject")} ({openIds.length})
                  </button>
                </span>
              </div>
              <div className="red-anomalies-wrap">
                {items.map((a) => (
                  <AnomalyRow
                    key={a.id}
                    a={a}
                    onStatus={(status, feedback) => setStatus.mutate({ id: a.id, status, feedback })}
                  />
                ))}
              </div>
            </div>
          );
        })
      ))}
    </>
  );
}

function Filter({ value, onChange, label, options, allLabel }: { value: string; onChange: (v: string) => void; label: string; options: Array<readonly [string, string]>; allLabel: string }) {
  return (
    <label className="grow" style={{ minWidth: 160 }}>
      <span className="label">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{allLabel}</option>
        {options.map(([v, l]) => (
          <option key={v} value={v}>{l}</option>
        ))}
      </select>
    </label>
  );
}

function AnomalyRow({
  a,
  onStatus,
}: {
  a: AnomalyOut;
  onStatus: (s: AnomalyStatus, feedback?: string) => void;
}) {
  const { t } = useTranslation();
  const message = resolveAnomalyText(t, a.message, a.message_key, a.message_params_json);
  const suggestion = resolveAnomalyText(t, a.suggestion, a.suggestion_key, a.suggestion_params_json);
  const [feedback, setFeedback] = useState(a.feedback ?? "");
  const rejected = a.status === "rejected";
  return (
    <div className="red-anomaly">
      <div className="red-anomaly-head">
        {a.category && <span className="badge">{a.category}</span>}
        <span className={`badge ${severityClass(a.severity)}`}>{a.severity}</span>
        {a.confidence && <span className="badge off">{confLabel(a.confidence)}</span>}
        <select
          className={`red-status-select st-${a.status}`}
          value={a.status}
          onChange={(e) => onStatus(e.target.value as AnomalyStatus)}
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>{t(STATUS_KEY[s])}</option>
          ))}
        </select>
      </div>
      <div className="red-anomaly-msg">{message}</div>
      {a.location && <div className="red-anomaly-loc">{a.location}</div>}
      {suggestion && <div className="red-anomaly-suggestion">→ {suggestion}</div>}
      {rejected && (
        <>
          <div className="red-reject-reasons">
            {REJECTION_REASON_KEYS.map((key) => (
              <button
                key={key}
                type="button"
                className={`chat-suggestion${feedback === t(key) ? " active" : ""}`}
                onClick={() => {
                  setFeedback(t(key));
                  if (t(key) !== (a.feedback ?? "")) onStatus("rejected", t(key));
                }}
              >
                {t(key)}
              </button>
            ))}
          </div>
          <input
            className="input red-anomaly-feedback"
            placeholder={t("redacteur.feedbackPlaceholder")}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            onBlur={() => {
              if (feedback !== (a.feedback ?? "")) onStatus("rejected", feedback);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
            }}
          />
        </>
      )}
    </div>
  );
}
