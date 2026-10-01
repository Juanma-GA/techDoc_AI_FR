import { useTranslation } from "react-i18next";

import { localizedRuleCode } from "../../lib/suggestionText";
import type { RuleResult } from "../../types/domain";

type Props = {
  results: RuleResult[];
  isRunning: boolean;
};

export function findInconclusiveResults(results: RuleResult[]): RuleResult[] {
  return results.filter((result) => result.status === "INCONCLUSIVE");
}

export function IncompleteChecksNotice({ results, isRunning }: Props) {
  const { t } = useTranslation();
  const inconclusive = findInconclusiveResults(results);

  if (isRunning || inconclusive.length === 0) return null;

  return (
    <section className="banner warn" role="status" aria-live="polite">
      <strong>
        {t("reviewer.analysis.incomplete.title", { count: inconclusive.length })}
      </strong>
      <p>{t("reviewer.analysis.incomplete.description")}</p>
      <ul>
        {inconclusive.map((result) => {
          const codeLabel = localizedRuleCode(result.rule_id, t);
          const title = result.rule_title?.trim() || codeLabel;
          return (
            <li key={result.rule_id}>
              <span>{title}</span>
              {result.rule_title ? <span className="label">{codeLabel}</span> : null}
              {result.evidence?.page ? (
                <span className="label">
                  {t("reviewer.analysis.incomplete.page", { page: result.evidence.page })}
                </span>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}