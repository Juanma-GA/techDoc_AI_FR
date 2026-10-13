import { useTranslation } from "react-i18next";

import { localizedRuleCode } from "../../lib/suggestionText";
import type { RuleResult } from "../../types/domain";

type Props = {
  results: RuleResult[];
  isRunning: boolean;
};

export function findInconclusiveResults(results: RuleResult[]): RuleResult[] {
  return results.filter(
    (result) =>
      result.status === "INCONCLUSIVE" || (result.inconclusive_pages?.length ?? 0) > 0,
  );
}

export function IncompleteChecksNotice({ results, isRunning }: Props) {
  const { t } = useTranslation();
  const inconclusive = findInconclusiveResults(results);

  if (isRunning || inconclusive.length === 0) return null;

  return (
    <details className="banner warn" role="status" aria-live="polite">
      <summary className="incomplete-checks-summary">
        <strong>
          {t("reviewer.analysis.incomplete.title", { count: inconclusive.length })}
        </strong>
      </summary>
      <p>{t("reviewer.analysis.incomplete.description")}</p>
      <ul>
        {inconclusive.map((result) => {
          const codeLabel = localizedRuleCode(result.rule_id, t);
          const title = result.rule_title?.trim() || codeLabel;
          const pages = result.inconclusive_pages?.length
            ? result.inconclusive_pages
            : result.evidence?.page
              ? [result.evidence.page]
              : [];
          return (
            <li key={result.rule_id}>
              <span>{title}</span>
              {result.rule_title ? <span className="label">{codeLabel}</span> : null}
              {pages.length > 0 ? (
                <span className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                  {pages.map((page) => (
                    <span className="badge info" key={`${result.rule_id}-${page}`}>
                      {t("reviewer.analysis.incomplete.page", { page })}
                    </span>
                  ))}
                </span>
              ) : null}
            </li>
          );
        })}
      </ul>
    </details>
  );
}