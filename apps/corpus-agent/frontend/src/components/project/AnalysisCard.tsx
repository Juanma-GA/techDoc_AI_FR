import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { analysisApi, ApiClientError, filesApi } from "../../lib/api";
import { fmtDate } from "../../lib/format";
import type { AnalysisRunOut, FileOut } from "../../lib/types";

// Champs du résumé d'analyse qui ne sont pas des compteurs d'anomalies.
const NON_TYPE_KEYS = new Set([
  "indexed_chunks", "chunks", "total", "files", "duration_s",
  "suppressed_rejected",
  // Signaux de "ce run a-t-il vraiment eu de quoi verifier" (cf. plus bas),
  // pas des types d'anomalie : jamais additionnes dans `total`.
  "llm_used", "active_rules", "verification_status",
]);

type AnalysisSummary = Record<string, number | boolean | string>;
type VerificationStatus = "verified" | "partial" | "not_verified" | "unknown";

export function AnalysisCard({ pid }: { pid: string }) {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language || "fr").slice(0, 2);
  const qc = useQueryClient();
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [finishedAt, setFinishedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Echantillon : set d'ids selectionnes. Vide = tout le projet.
  const [sample, setSample] = useState<Set<string>>(new Set());

  const filesQuery = useQuery<FileOut[]>({ queryKey: ["files", pid], queryFn: () => filesApi.list(pid) });
  const runsQuery = useQuery<AnalysisRunOut[]>({
    queryKey: ["analysis-runs", pid],
    queryFn: () => analysisApi.runs(pid),
  });
  const files = filesQuery.data ?? [];

  useEffect(() => {
    const latest = runsQuery.data?.[0];
    if (!latest) return;
    setFinishedAt(latest.finished_at);
    try {
      setSummary(JSON.parse(latest.summary || "{}") as AnalysisSummary);
    } catch {
      setSummary({});
    }
  }, [runsQuery.data]);

  const run = useMutation({
    mutationFn: (fileIds?: string[]) => analysisApi.run(pid, fileIds),
    onSuccess: (res: AnalysisRunOut) => {
      setError(null);
      setFinishedAt(res.finished_at);
      try {
        setSummary(JSON.parse(res.summary || "{}") as AnalysisSummary);
      } catch {
        setSummary({});
      }
      void qc.invalidateQueries({ queryKey: ["anomalies", pid] });
      void qc.invalidateQueries({ queryKey: ["kpis"] });
      void qc.invalidateQueries({ queryKey: ["analysis-runs", pid] });
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

  const typeEntries: Array<[string, number]> = summary
    ? Object.entries(summary).filter(
        (entry): entry is [string, number] =>
          !NON_TYPE_KEYS.has(entry[0]) &&
          !entry[0].startsWith("files_") &&
          !entry[0].startsWith("evaluation_") &&
          !entry[0].startsWith("rules_") &&
          !entry[0].startsWith("indexing_") &&
          typeof entry[1] === "number" &&
          entry[1] > 0,
      )
    : [];
  const total = typeEntries.reduce((a, [, v]) => a + v, 0);
  const llmUsed = summary?.llm_used === true;
  const activeRules = summary && typeof summary.active_rules === "number" ? summary.active_rules : null;
  const rawVerificationStatus = summary?.verification_status;
  const verificationStatus: VerificationStatus =
    rawVerificationStatus === "verified" ||
    rawVerificationStatus === "partial" ||
    rawVerificationStatus === "not_verified"
      ? rawVerificationStatus
      : "unknown";
  const coverage = {
    verified: typeof summary?.files_verified === "number" ? summary.files_verified : 0,
    selected: typeof summary?.files_selected === "number" ? summary.files_selected : 0,
    parsed: typeof summary?.files_parsed === "number" ? summary.files_parsed : 0,
    empty: typeof summary?.files_empty === "number" ? summary.files_empty : 0,
    parseFailed: typeof summary?.files_parse_failed === "number" ? summary.files_parse_failed : 0,
    missingVersion: typeof summary?.files_without_version === "number" ? summary.files_without_version : 0,
    evaluationFailures: typeof summary?.evaluation_failures === "number" ? summary.evaluation_failures : 0,
    rulesEvaluated: typeof summary?.rules_evaluated === "number" ? summary.rules_evaluated : 0,
    indexingFailures: typeof summary?.indexing_failures === "number" ? summary.indexing_failures : 0,
    suppressedRejected: typeof summary?.suppressed_rejected === "number" ? summary.suppressed_rejected : 0,
  };

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
          <div
            className={`banner${verificationStatus === "verified" ? "" : " warn"}`}
            role={verificationStatus === "verified" ? "status" : "alert"}
            style={{ marginTop: 10 }}
          >
            {t(`projects.kpi.verification.${verificationStatus}`, coverage)}
          </div>
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
            {total === 0 && summary.llm_used === false && (
              <div className="banner warn" style={{ gridColumn: "1 / -1" }}>
                {t("projects.kpi.notVerifiedNoLlm")}
              </div>
            )}
            {total === 0 && llmUsed && activeRules === 0 && (
              <div className="banner warn" style={{ gridColumn: "1 / -1" }}>
                {t("projects.kpi.notVerifiedNoRules")}
              </div>
            )}
            {total === 0 && verificationStatus === "verified" && activeRules !== 0 && (
              <div className="kpi" style={{ gridColumn: "1 / -1" }}>
                <div className="label">
                  {t("projects.kpi.noAnomaliesDetected", { suppressed: coverage.suppressedRejected })}
                </div>
              </div>
            )}
          </div>
          {finishedAt && (
            <div className="label" style={{ marginTop: 8 }}>
              {t("projects.analysisFinishedAt")} {fmtDate(finishedAt, lang)}
            </div>
          )}
          {typeof summary.rule_set_sha256 === "string" && (
            <details className="sample-picker" style={{ marginTop: 8 }}>
              <summary className="label">{t("projects.analysisTrace")}</summary>
              <div className="label" style={{ marginTop: 6 }}>
                {t("projects.analysisTraceModel", {
                  model: typeof summary.llm_model === "string" && summary.llm_model
                    ? summary.llm_model
                    : t("projects.analysisTraceUnavailable"),
                })}
              </div>
              <div className="label">
                {t("projects.analysisTracePrompt", {
                  version: typeof summary.prompt_version === "string" ? summary.prompt_version : "—",
                })}
              </div>
              <div className="label">
                {t("projects.analysisTraceRules", { hash: summary.rule_set_sha256 })}
              </div>
            </details>
          )}
        </>
      )}
    </div>
  );
}
