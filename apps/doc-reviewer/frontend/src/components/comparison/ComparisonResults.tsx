import { buttonVariants } from "@internal/ui";
import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  comparisonApi,
  type ComparisonChange,
  type ComparisonDetail,
} from "../../lib/comparisonApi";
import { ComparisonWorkspace } from "./ComparisonWorkspace";

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
  const [selection, setSelection] = useState<{ documentIndex: number; groupId: string } | null>(null);
  const reference = comparison.report.documents[comparison.report.reference_index];
  const selectedPair = comparison.report.comparisons.find(
    (pair) => pair.document_index === selection?.documentIndex,
  );
  const selectedChanges = selectedPair?.changes.filter(
    (change) => change.group_id === selection?.groupId,
  ) ?? [];
  const removed = selectedChanges.filter((change) => change.kind === "removed");
  const added = selectedChanges.filter((change) => change.kind === "added");

  useEffect(() => setSelection(null), [comparison.id]);

  return (
    <section className="card" aria-labelledby="comparison-results-title">
      <h2 id="comparison-results-title" className="card-title">{t("comparison.resultsTitle")}</h2>
      <div className="mt-5 space-y-6">
        <div className="space-y-3">
          <p className="label">{t("comparison.reference")}: {reference?.filename ?? comparison.title}</p>
          {comparison.file_count > 2 ? <p className="hint">{t("comparison.exportAllHint")}</p> : null}
          <a
            data-comparison-download
            className={buttonVariants({ variant: "secondary" })}
            href={comparisonApi.exportUrl(comparison.id, language)}
            download
          >
            <Download size={16} className="shrink-0" aria-hidden="true" />
            <span>{t(comparison.file_count > 2 ? "comparison.exportAll" : "comparison.exportOne")}</span>
          </a>
        </div>
        <ComparisonWorkspace
          comparison={comparison}
          language={language}
          onSelectDifference={setSelection}
        />
        <section className="comparison-difference-detail" aria-labelledby="comparison-selected-difference">
          <h3 id="comparison-selected-difference">{t("comparison.selectedDifference")}</h3>
          {selection ? (
            <div className="comparison-difference-columns">
              <DifferenceText
                filename={reference?.filename ?? comparison.title}
                changes={removed}
                emptyLabel={t("comparison.noRemovedText")}
                pageLabel={(page) => t("comparison.page", { page })}
              />
              <DifferenceText
                filename={selectedPair?.filename ?? t("comparison.candidate")}
                changes={added}
                emptyLabel={t("comparison.noAddedText")}
                pageLabel={(page) => t("comparison.page", { page })}
              />
            </div>
          ) : <p className="hint">{t("comparison.selectDifferenceHint")}</p>}
        </section>
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

function DifferenceText({
  filename,
  changes,
  emptyLabel,
  pageLabel,
}: {
  filename: string;
  changes: ComparisonChange[];
  emptyLabel: string;
  pageLabel: (page: number) => string;
}) {
  return (
    <div>
      <h4>{filename}</h4>
      {changes.length ? (
        <ul>
          {changes.map((change, index) => (
            <li key={`${change.group_id}-${change.page}-${index}`}>
              <span className="label">{pageLabel(change.page)}</span>
              <pre>{change.text}</pre>
            </li>
          ))}
        </ul>
      ) : <p className="hint">{emptyLabel}</p>}
    </div>
  );
}
