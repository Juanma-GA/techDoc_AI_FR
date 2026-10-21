import { useTranslation } from "react-i18next";

import {
  comparisonApi,
  type ComparisonDetail,
} from "../../lib/api";

export function ComparisonResults({
  comparison,
  language,
  isSummarizing,
  summaryError,
  onRetrySummary,
}: {
  comparison: ComparisonDetail;
  language: "fr" | "en";
  isSummarizing: boolean;
  summaryError: string;
  onRetrySummary: () => void;
}) {
  const { t } = useTranslation();
  const reference = comparison.report.documents[comparison.report.reference_index];
  return (
    <section className="card" aria-labelledby="comparison-results-title">
      <h2 id="comparison-results-title" className="card-title">{t("comparison.resultsTitle")}</h2>
      <div className="mt-5 space-y-6">
        <div className="space-y-3">
          <p className="label">{t("comparison.reference")}: {reference?.filename ?? comparison.title}</p>
          {comparison.file_count > 2 ? <p className="hint">{t("comparison.exportZipHint")}</p> : null}
          <a className="btn primary small" href={comparisonApi.exportUrl(comparison.id, language)} download>
            {t(comparison.file_count > 2 ? "comparison.exportAll" : "comparison.exportOne")}
          </a>
        </div>
        <div className="space-y-4">
          {comparison.report.comparisons.map((pair) => (
            <details key={pair.document_index} className="space-y-4 rounded-lg border border-md p-4">
              <summary className="cursor-pointer font-medium">
                {pair.filename} · {t("comparison.addedCount", { count: pair.added_count })} · {t("comparison.removedCount", { count: pair.removed_count })}
              </summary>
              {comparison.file_count > 2 ? (
                <a className="btn ghost small" href={comparisonApi.exportDocumentUrl(comparison.id, pair.document_index, language)} download>
                  {t("comparison.exportOne")}
                </a>
              ) : null}
              {pair.changes.length ? (
                <ul className="mt-4 space-y-3">
                  {pair.changes.map((change, index) => (
                    <li key={`${change.kind}-${change.page}-${index}`} className="flex flex-wrap items-start gap-x-3 gap-y-2">
                      <span className={`badge ${change.kind === "added" ? "ok" : "danger"}`}>
                        {change.kind === "added" ? t("comparison.added") : t("comparison.removed")}
                      </span>
                      <span className="label shrink-0">{t("comparison.page", { page: change.page })}</span>
                      <pre className="min-w-0 flex-1 whitespace-pre-wrap break-words font-mono text-sm">{change.text}</pre>
                    </li>
                  ))}
                </ul>
              ) : <p className="empty-state">{t("comparison.noChanges")}</p>}
            </details>
          ))}
        </div>
        <section className="space-y-4 border-t border-md pt-5" aria-labelledby="comparison-ai-title">
          <h3 id="comparison-ai-title" className="card-title">{t("comparison.aiTitle")}</h3>
          {isSummarizing ? <p role="status">{t("comparison.aiPending")}</p> : null}
          {comparison.ai_status === "disabled" ? <p className="hint">{t("comparison.aiDisabled")}</p> : null}
          {comparison.ai_status === "not_configured" ? <p className="hint">{t("comparison.aiNotConfigured")}</p> : null}
          {comparison.ai_summary ? (
            <div className="space-y-3">
              <p>{comparison.ai_summary.summary}</p>
              <h4 className="label">{t("comparison.aiKeyChanges")}</h4>
              <ul className="list-disc space-y-2 pl-5">
                {comparison.ai_summary.key_changes.map((change, index) => <li key={index}>{change}</li>)}
              </ul>
              <h4 className="label">{t("comparison.aiImpact")}</h4>
              <p>{comparison.ai_summary.impact}</p>
              {comparison.ai_summary_truncated ? <p className="hint">{t("comparison.aiTruncated")}</p> : null}
            </div>
          ) : null}
          {summaryError ? <p className="error" role="alert">{t("comparison.aiError", { message: summaryError })}</p> : null}
          {comparison.ai_status !== "completed" && !isSummarizing ? (
            <button type="button" className="btn secondary small" onClick={onRetrySummary} disabled={isSummarizing}>
              {t("comparison.aiRetry")}
            </button>
          ) : null}
        </section>
      </div>
    </section>
  );
}
