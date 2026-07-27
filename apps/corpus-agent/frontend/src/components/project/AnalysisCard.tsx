import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { analysisApi, ApiClientError, filesApi } from "../../lib/api";
import { fmtDate } from "../../lib/format";
import type { AnalysisRunOut, FileOut } from "../../lib/types";

// Champs du résumé d'analyse qui ne sont pas des compteurs d'anomalies.
const NON_TYPE_KEYS = new Set(["indexed_chunks", "chunks", "total", "files", "duration_s"]);

export function AnalysisCard({ pid }: { pid: string }) {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language || "fr").slice(0, 2);
  const qc = useQueryClient();
  const [summary, setSummary] = useState<Record<string, number> | null>(null);
  const [finishedAt, setFinishedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Echantillon : set d'ids selectionnes. Vide = tout le projet.
  const [sample, setSample] = useState<Set<string>>(new Set());

  const filesQuery = useQuery<FileOut[]>({ queryKey: ["files", pid], queryFn: () => filesApi.list(pid) });
  const files = filesQuery.data ?? [];

  const run = useMutation({
    mutationFn: (fileIds?: string[]) => analysisApi.run(pid, fileIds),
    onSuccess: (res: AnalysisRunOut) => {
      setError(null);
      setFinishedAt(res.finished_at);
      try {
        setSummary(JSON.parse(res.summary || "{}") as Record<string, number>);
      } catch {
        setSummary({});
      }
      void qc.invalidateQueries({ queryKey: ["anomalies", pid] });
      void qc.invalidateQueries({ queryKey: ["kpis"] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : String(e)),
  });
  const reset = useMutation({
    mutationFn: () => analysisApi.reset(pid),
    onSuccess: () => {
      setSummary(null);
      setFinishedAt(null);
      void qc.invalidateQueries({ queryKey: ["anomalies", pid] });
      void qc.invalidateQueries({ queryKey: ["kpis"] });
    },
  });

  const typeEntries = summary
    ? Object.entries(summary).filter(([k, v]) => !NON_TYPE_KEYS.has(k) && v > 0)
    : [];
  const total = typeEntries.reduce((a, [, v]) => a + v, 0);

  const toggleFile = (id: string) =>
    setSample((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const sampleIds = sample.size ? [...sample] : undefined;

  return (
    <div className="card">
      <h2 className="card-title">{t("projects.analysis")}</h2>
      <div className="row">
        <button type="button" className="btn primary" onClick={() => run.mutate(sampleIds)} disabled={run.isPending}>
          {run.isPending ? <span className="spinner" /> : null}{" "}
          {sample.size ? t("projects.runAnalysisSample", { count: sample.size }) : t("projects.runAnalysis")}
        </button>
        <button type="button" className="btn secondary" onClick={() => reset.mutate()} disabled={reset.isPending}>
          {t("projects.reset")}
        </button>
      </div>

      {files.length > 1 && (
        <details className="sample-picker" style={{ marginTop: 10 }}>
          <summary className="label">
            {t("projects.sample")} — {sample.size ? t("projects.sampleCount", { count: sample.size, total: files.length }) : t("projects.sampleAll")}
          </summary>
          <div className="label" style={{ margin: "6px 0" }}>{t("projects.sampleHint")}</div>
          <div className="row" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
            {files.map((f) => (
              <label key={f.id} className="row" style={{ gap: "0.35rem", alignItems: "center" }}>
                <input type="checkbox" checked={sample.has(f.id)} onChange={() => toggleFile(f.id)} />
                <span>{f.current_name}</span>
              </label>
            ))}
          </div>
          {sample.size > 0 && (
            <button type="button" className="btn ghost small" style={{ marginTop: 6 }} onClick={() => setSample(new Set())}>
              {t("projects.sampleClear")}
            </button>
          )}
        </details>
      )}
      {run.isPending && (
        <div className="banner" style={{ marginTop: 10 }}>
          {t("projects.analysisRunning")} — {t("projects.analysisRunningHint")}
        </div>
      )}
      {error && <div className="error">{error}</div>}
      {summary && !run.isPending && (
        <>
          <div className="kpi-grid" style={{ marginTop: 12 }}>
            <div className="kpi">
              <div className="label">{t("projects.kpi.totalAnomalies")}</div>
              <div className="kpi-value">{total}</div>
            </div>
            {typeof summary.indexed_chunks === "number" && (
              <div className="kpi">
                <div className="label">{t("projects.kpi.indexed")}</div>
                <div className="kpi-value info">{summary.indexed_chunks}</div>
              </div>
            )}
            {typeEntries.map(([type, v]) => (
              <div className="kpi" key={type}>
                <div className="label">{t(`projects.kpi.type.${type}`)}</div>
                <div className="kpi-value">{v}</div>
              </div>
            ))}
            {total === 0 && (
              <div className="kpi" style={{ gridColumn: "1 / -1" }}>
                <div className="label">{t("projects.kpi.noAnomaliesDetected")}</div>
              </div>
            )}
          </div>
          {finishedAt && (
            <div className="label" style={{ marginTop: 8 }}>
              {t("projects.analysisFinishedAt")} {fmtDate(finishedAt, lang)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
