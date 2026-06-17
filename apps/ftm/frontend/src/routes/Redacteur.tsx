/**
 * Vue Rédacteur — anomalies groupées par fichier, filtres 4 axes (type /
 * criticité / confiance IA / statut), PATCH statut par anomalie, bulk
 * fix/reject par fichier, détection doublons SHA, collapse/expand.
 * Port React de la vue `redacteur` de la preview HTML.
 */
import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@internal/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import {
  type AnomalyBulkStatusIn,
  type AnomalyOut,
  type FileOut,
  resources,
} from "../lib/api";

// ----------------------------------------------------------------------------
// Constants
// ----------------------------------------------------------------------------

const ANOMALY_TYPE_LABELS: [string, string][] = [
  ["script", "Script"],
  ["granule", "Granule"],
  ["texte", "Texte"],
  ["ordre_taches", "Ordre des taches"],
  ["tache_induite", "Tache induite"],
  ["orthographe", "Orthographe"],
  ["rechange", "Rechanges"],
  ["outillage", "Outillages"],
  ["infrastructure", "Infrastructure"],
  ["entete", "En-tete Recapitulatif"],
  ["securite", "Mise en securite"],
  ["preliminaire", "Operations preliminaires"],
  ["valeur_numerique", "Valeurs numeriques"],
  ["serrage", "Serrage"],
  ["complementaire", "Operations complementaires"],
  ["illustration", "Illustrations"],
  ["personnalisee", "Regles personnalisees (IA)"],
];

const STATUS_I18N: Record<string, string> = {
  open: "redacteur.statusOpen",
  acknowledged: "redacteur.statusAck",
  fixed: "redacteur.statusFixed",
  rejected: "redacteur.statusRejected",
};

const SEV_VARIANT: Record<string, "danger" | "warning" | "success"> = {
  high: "danger",
  medium: "warning",
  low: "success",
};

const SELECT_CLS =
  "h-8 w-full rounded border border-border bg-bg px-2 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-brand";

// ----------------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------------

type TFn = (key: string, opts?: Record<string, unknown>) => string;

function resolveText(t: TFn, key: string | null, paramsJson: string | null, fallback: string): string {
  if (!key) return fallback;
  try {
    const params = paramsJson ? (JSON.parse(paramsJson) as Record<string, unknown>) : {};
    const resolved = (t as TFn)(key, params);
    return resolved === key ? fallback : resolved;
  } catch {
    return fallback;
  }
}

/** vid → list of OTHER file names sharing the same latest SHA (duplicates). */
function buildDupMap(files: FileOut[]): Record<string, string[]> {
  const bySha: Record<string, Array<{ vid: string; name: string }>> = {};
  for (const f of files) {
    const sorted = [...f.versions].sort((a, b) =>
      a.uploaded_at < b.uploaded_at ? -1 : 1,
    );
    const latest = sorted[sorted.length - 1];
    if (!latest?.sha256) continue;
    (bySha[latest.sha256] ??= []).push({ vid: latest.id, name: f.current_name });
  }
  const result: Record<string, string[]> = {};
  for (const entries of Object.values(bySha)) {
    if (entries.length < 2) continue;
    for (const e of entries) {
      result[e.vid] = entries.filter((x) => x.vid !== e.vid).map((x) => x.name);
    }
  }
  return result;
}

/** file_version_id → file current name. */
function buildVidNames(files: FileOut[]): Record<string, string> {
  const map: Record<string, string> = {};
  for (const f of files) {
    for (const v of f.versions) map[v.id] = f.current_name;
  }
  return map;
}

// ----------------------------------------------------------------------------
// AnomalyRow
// ----------------------------------------------------------------------------

function AnomalyRow({ anomaly, pid }: { anomaly: AnomalyOut; pid: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [isPending, setIsPending] = useState(false);

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const status = e.target.value;
    setIsPending(true);
    void resources.anomalies
      .updateStatus(anomaly.id, status)
      .then((updated) => {
        qc.setQueryData<AnomalyOut[]>(["anomalies", pid], (old) =>
          old?.map((a) => (a.id === updated.id ? updated : a)) ?? [],
        );
      })
      .finally(() => setIsPending(false));
  }

  const message = resolveText(
    t as TFn,
    anomaly.message_key,
    anomaly.message_params_json,
    anomaly.message,
  );
  const suggestion = resolveText(
    t as TFn,
    anomaly.suggestion_key,
    anomaly.suggestion_params_json,
    anomaly.suggestion,
  );

  return (
    <div className="border-b py-2.5 last:border-0">
      <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
        <Badge>{anomaly.type}</Badge>
        <Badge variant={SEV_VARIANT[anomaly.severity] ?? "default"}>{anomaly.severity}</Badge>
        {anomaly.confidence && anomaly.confidence !== "elevee" && (
          <Badge>{anomaly.confidence}</Badge>
        )}
        <select
          className="ml-auto h-7 rounded border border-border bg-bg px-2 text-xs text-fg focus:outline-none disabled:opacity-50"
          value={anomaly.status}
          disabled={isPending}
          onChange={handleChange}
        >
          {Object.entries(STATUS_I18N).map(([val, key]) => (
            <option key={val} value={val}>
              {t(key)}
            </option>
          ))}
        </select>
      </div>
      <p className="text-sm text-fg">{message}</p>
      {anomaly.location && (
        <p className="mt-0.5 text-xs text-fg-dim">{anomaly.location}</p>
      )}
      {suggestion && (
        <p className="mt-0.5 text-xs italic text-fg-muted">→ {suggestion}</p>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// FileBlock
// ----------------------------------------------------------------------------

function FileBlock({
  vid,
  name,
  dupOfNames,
  anomalies,
  pid,
  isCollapsed,
  onToggle,
}: {
  vid: string;
  name: string;
  dupOfNames: string[] | undefined;
  anomalies: AnomalyOut[];
  pid: string;
  isCollapsed: boolean;
  onToggle: (vid: string) => void;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [bulkPending, setBulkPending] = useState(false);

  const openIds = anomalies
    .filter((a) => a.status === "open" || a.status === "acknowledged")
    .map((a) => a.id);

  function handleBulk(status: string) {
    if (!openIds.length || bulkPending) return;
    setBulkPending(true);
    const body: AnomalyBulkStatusIn = { ids: openIds, status };
    void resources.anomalies
      .bulkStatus(body)
      .then(() => qc.invalidateQueries({ queryKey: ["anomalies", pid] }))
      .finally(() => setBulkPending(false));
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 bg-bg-2 px-4 py-2.5 text-left hover:bg-card-hover"
        onClick={() => onToggle(vid)}
      >
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <span className="shrink-0 text-xs text-fg-dim transition-transform" style={{ display: "inline-block", transform: isCollapsed ? "rotate(-90deg)" : "rotate(0deg)" }}>
            ▼
          </span>
          <span className="min-w-0 truncate text-sm font-medium text-fg">{name}</span>
          {dupOfNames && dupOfNames.length > 0 && (
            <Badge variant="danger" title={`${t("files.duplicateOf")} : ${dupOfNames.join(", ")}`}>
              {t("files.duplicate")}
            </Badge>
          )}
          <Badge variant="danger" className="shrink-0">{anomalies.length}</Badge>
        </div>
        <div className="flex shrink-0 items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
          <Button
            variant="ghost"
            size="sm"
            disabled={!openIds.length || bulkPending}
            onClick={() => handleBulk("fixed")}
          >
            {t("redacteur.bulkFix")} ({openIds.length})
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={!openIds.length || bulkPending}
            onClick={() => handleBulk("rejected")}
          >
            {t("redacteur.bulkReject")} ({openIds.length})
          </Button>
        </div>
      </button>

      {!isCollapsed && (
        <div className="divide-y px-4 py-1">
          {anomalies.map((a) => (
            <AnomalyRow key={a.id} anomaly={a} pid={pid} />
          ))}
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// Main route
// ----------------------------------------------------------------------------

export function Redacteur() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const pidParam = searchParams.get("pid");

  const [pid, setPid] = useState<string>(pidParam ?? "");
  const [filterType, setFilterType] = useState("");
  const [filterSev, setFilterSev] = useState("");
  const [filterConf, setFilterConf] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [collapsedVids, setCollapsedVids] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (pidParam) setSearchParams({}, { replace: true });
  }, []);

  // --- Data ------------------------------------------------------------------

  const [projects, setProjects] = useState<Array<{ id: string; name: string }>>([]);
  const [files, setFiles] = useState<FileOut[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    void resources.projects.list().then(setProjects).catch(() => {});
  }, []);

  useEffect(() => {
    if (!pid) { setFiles([]); setAnomalies([]); return; }
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setLoading(true);
    setLoadError(false);
    Promise.all([
      resources.files.list(pid),
      resources.anomalies.list(pid),
    ])
      .then(([f, a]) => {
        if (ac.signal.aborted) return;
        setFiles(f);
        // exclude dmc_missing (covered by project Reference card)
        setAnomalies(a.filter((x) => x.type !== "dmc_missing"));
        setCollapsedVids(new Set());
      })
      .catch(() => { if (!ac.signal.aborted) setLoadError(true); })
      .finally(() => { if (!ac.signal.aborted) setLoading(false); });
    return () => ac.abort();
  }, [pid]);

  // Sync React Query cache for optimistic status updates
  const qc = useQueryClient();
  useEffect(() => {
    if (!pid) return;
    qc.setQueryData<AnomalyOut[]>(["anomalies", pid], anomalies);
  }, [anomalies, pid, qc]);

  // Keep local anomalies state in sync when React Query cache is mutated by child rows
  useEffect(() => {
    if (!pid) return;
    const unsubscribe = qc.getQueryCache().subscribe((event) => {
      if (
        event.type === "updated" &&
        event.query.queryKey[0] === "anomalies" &&
        event.query.queryKey[1] === pid
      ) {
        const data = event.query.state.data as AnomalyOut[] | undefined;
        if (data) setAnomalies(data.filter((x) => x.type !== "dmc_missing"));
      }
    });
    return unsubscribe;
  }, [pid, qc]);

  // --- Derived ---------------------------------------------------------------

  const filtered = useMemo(
    () =>
      anomalies.filter((a) => {
        if (filterType && a.type !== filterType) return false;
        if (filterSev && a.severity !== filterSev) return false;
        if (filterConf && a.confidence !== filterConf) return false;
        if (filterStatus && a.status !== filterStatus) return false;
        return true;
      }),
    [anomalies, filterType, filterSev, filterConf, filterStatus],
  );

  const byFile = useMemo(() => {
    const groups: Record<string, AnomalyOut[]> = {};
    for (const a of filtered) {
      const key = a.file_version_id ?? "_orphan";
      (groups[key] ??= []).push(a);
    }
    return groups;
  }, [filtered]);

  const vidNames = useMemo(() => buildVidNames(files), [files]);
  const dupMap = useMemo(() => buildDupMap(files), [files]);

  const fileVids = Object.keys(byFile);

  // --- Collapse handlers -----------------------------------------------------

  const handleToggle = useCallback((vid: string) => {
    setCollapsedVids((prev) => {
      const next = new Set(prev);
      if (next.has(vid)) next.delete(vid);
      else next.add(vid);
      return next;
    });
  }, []);

  function handleCollapseAll() {
    setCollapsedVids(new Set(fileVids));
  }
  function handleExpandAll() {
    setCollapsedVids(new Set());
  }

  // --- Render ----------------------------------------------------------------

  return (
    <div className="px-8 py-6">
      <PageHeader title={t("nav.redacteur")} subtitle={t("page.redacteur")} />

      {/* Project selector */}
      <Card className="mb-4">
        <CardHeader className="p-4 pb-0">
          <CardTitle className="text-base">{t("redacteur.selectProject")}</CardTitle>
        </CardHeader>
        <CardContent>
          <select
            className={SELECT_CLS}
            value={pid}
            onChange={(e) => setPid(e.target.value)}
          >
            <option value="">{t("common.selectProject")}</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </CardContent>
      </Card>

      {!pid && (
        <p className="text-sm text-fg-muted">{t("common.empty")}</p>
      )}

      {pid && (
        <Card>
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-base">{t("redacteur.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            {/* Filter bar */}
            <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
              <label className="flex flex-col gap-1">
                <span className="text-xs text-fg-dim">{t("redacteur.filterCategory")}</span>
                <select className={SELECT_CLS} value={filterType} onChange={(e) => setFilterType(e.target.value)}>
                  <option value="">{t("redacteur.filterAll")}</option>
                  {ANOMALY_TYPE_LABELS.map(([val, lbl]) => (
                    <option key={val} value={val}>{lbl}</option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs text-fg-dim">{t("redacteur.filterSeverity")}</span>
                <select className={SELECT_CLS} value={filterSev} onChange={(e) => setFilterSev(e.target.value)}>
                  <option value="">{t("redacteur.filterAll")}</option>
                  <option value="high">{t("redacteur.sevHigh")}</option>
                  <option value="medium">{t("redacteur.sevMedium")}</option>
                  <option value="low">{t("redacteur.sevLow")}</option>
                </select>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs text-fg-dim">{t("redacteur.filterConfidence")}</span>
                <select className={SELECT_CLS} value={filterConf} onChange={(e) => setFilterConf(e.target.value)}>
                  <option value="">{t("redacteur.filterAll")}</option>
                  <option value="elevee">{t("redacteur.confHigh")}</option>
                  <option value="moyenne">{t("redacteur.confMedium")}</option>
                  <option value="faible">{t("redacteur.confLow")}</option>
                </select>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs text-fg-dim">{t("redacteur.filterStatus")}</span>
                <select className={SELECT_CLS} value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
                  <option value="">{t("redacteur.filterAll")}</option>
                  {Object.entries(STATUS_I18N).map(([val, key]) => (
                    <option key={val} value={val}>{t(key)}</option>
                  ))}
                </select>
              </label>
            </div>

            {/* Loading / error */}
            {loading && <p className="py-4 text-sm text-fg-muted">{t("common.loading")}</p>}
            {loadError && <p className="py-4 text-sm text-danger">{t("errors.generic")}</p>}

            {/* Global toolbar */}
            {!loading && !loadError && fileVids.length > 0 && (
              <div className="mb-3 flex gap-2">
                <Button variant="ghost" size="sm" onClick={handleCollapseAll}>
                  {t("redacteur.collapseAll")}
                </Button>
                <Button variant="ghost" size="sm" onClick={handleExpandAll}>
                  {t("redacteur.expandAll")}
                </Button>
              </div>
            )}

            {/* File blocks */}
            {!loading && !loadError && fileVids.length === 0 && (
              <div className="py-6 text-center text-sm text-fg-muted">—</div>
            )}

            <div className="flex flex-col gap-2">
              {fileVids.map((vid) => (
                <FileBlock
                  key={vid}
                  vid={vid}
                  name={vid === "_orphan" ? t("redacteur.orphanFile") : (vidNames[vid] ?? vid)}
                  dupOfNames={vid !== "_orphan" ? dupMap[vid] : undefined}
                  anomalies={byFile[vid] ?? []}
                  pid={pid}
                  isCollapsed={collapsedVids.has(vid)}
                  onToggle={handleToggle}
                />
              ))}
            </div>

            {/* CSV export */}
            {!loading && anomalies.length > 0 && (
              <div className="mt-4 flex justify-end">
                <a
                  href={resources.anomalies.exportCsvUrl(pid)}
                  download
                  className="text-xs text-fg-dim underline hover:text-fg"
                >
                  Export CSV
                </a>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
