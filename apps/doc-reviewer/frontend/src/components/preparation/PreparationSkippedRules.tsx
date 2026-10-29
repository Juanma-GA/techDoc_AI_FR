import { useTranslation } from "react-i18next";

import type { PreparationSkippedRule } from "../../types/preparation";

export function PreparationSkippedRules({ rules }: { rules: PreparationSkippedRule[] }) {
  const { t } = useTranslation();
  if (rules.length === 0) return null;
  return (
    <section className="prep-missing" role="status">
      <h3 className="prep-missing-title">
        {t("preparationUi.skipped.title", { count: rules.length })}
      </h3>
      <p className="hint">{t("preparationUi.skipped.hint")}</p>
      <ul className="prep-skipped-list">
        {rules.map((rule) => (
          <li key={rule.rule_id}>
            <span>{rule.title}</span>
            <span className="prep-type-meta">
              {t("preparationUi.skipped.because", { value: rule.page_types.join(" / ") })}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
