import { useTranslation } from "react-i18next";

import type { PreparationPageDecision } from "../../types/preparation";

export function PreparationDecisionRow({
  decision,
  saving,
  onDecision,
}: {
  decision: PreparationPageDecision;
  saving: boolean;
  onDecision: (page: number, isModified: boolean) => void;
}) {
  const { t } = useTranslation();
  const resultKey =
    decision.is_modified === true
      ? "preparation.modified"
      : decision.is_modified === false
        ? "preparation.unchanged"
        : decision.decision_status === "no_applicable_rule"
          ? "preparation.noApplicableRule"
          : "preparation.needsReview";
  const reasons = [
    ...decision.failures.map((item) => item.message),
    ...decision.review_reasons.map((item) => item.message),
  ];
  const ruleResults = decision.rule_results ?? [];
  const statusClass = {
    PASS: "ok",
    FAIL: "danger",
    MANUAL: "warn",
    INCONCLUSIVE: "warn",
    UNSUPPORTED: "off",
  } as const;
  const statusKey = {
    PASS: "pass",
    FAIL: "fail",
    MANUAL: "manual",
    INCONCLUSIVE: "inconclusive",
    UNSUPPORTED: "unsupported",
  } as const;
  return (
    <tr>
      <td>{decision.page}</td>
      <td>{decision.page_type ?? "—"}</td>
      <td>{t(resultKey)}</td>
      <td>
        {ruleResults.length > 0 ? (
          <details className="preparation-rule-details">
            <summary>
              {t("preparationUi.ruleResults", { count: ruleResults.length })}
            </summary>
            <ul className="preparation-rule-results">
              {ruleResults.map((result) => (
                <li key={result.rule_id}>
                  <span className={`badge ${statusClass[result.status]}`}>
                    {t(`preparationUi.ruleStatus.${statusKey[result.status]}`)}
                  </span>
                  <div>
                    <strong>{result.title}</strong>
                    {result.status !== "PASS" ? <p>{result.message}</p> : null}
                  </div>
                </li>
              ))}
            </ul>
          </details>
        ) : decision.decision_status === "no_applicable_rule" ? (
          <span className="badge warn">
            {t("preparationUi.noApplicableRule")}
          </span>
        ) : reasons.length > 0 ? (
          reasons.join("; ")
        ) : (
          "—"
        )}
      </td>
      <td>
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
          <button
            type="button"
            className={decision.is_modified === true ? "btn primary small" : "btn secondary small"}
            disabled={saving}
            aria-pressed={decision.is_modified === true}
            onClick={() => onDecision(decision.page, true)}
          >
            {t("preparation.modified")}
          </button>
          <button
            type="button"
            className={decision.is_modified === false ? "btn primary small" : "btn secondary small"}
            disabled={saving}
            aria-pressed={decision.is_modified === false}
            onClick={() => onDecision(decision.page, false)}
          >
            {t("preparation.unchanged")}
          </button>
        </div>
      </td>
    </tr>
  );
}
