import { useTranslation } from "react-i18next";

import type { DmValidationViolation } from "../lib/wizardTypes";

type Props = {
  hasProfile: boolean;
  isComplete: boolean;
  violations: DmValidationViolation[];
};

function severityClass(severity: DmValidationViolation["severity"]): string {
  return severity === "info" ? "info" : "warn";
}

export function BrexViolationsPanel({ hasProfile, isComplete, violations }: Props) {
  const { t } = useTranslation();
  const actualViolations = violations.filter((violation) => violation.severity === "error");
  if (!hasProfile || !isComplete || !actualViolations.length) return null;

  const hasWarnings = actualViolations.some((violation) => violation.severity !== "info");
  const badgeClass = hasWarnings ? "warn" : "info";

  return (
    <section className="validation-violations" aria-label={t("migration.generate.brexCheckTitle")}>
      <h3 className="label">{t("migration.generate.brexCheckTitle")}</h3>
      <details>
        <summary>
          <span className={`badge ${badgeClass}`}>
            {t("migration.generate.brexViolations", { count: actualViolations.length })}
          </span>
        </summary>
        <div className="validation-violations">
          {actualViolations.map((violation, index) => (
            <article
              className="validation-violation"
              key={`${violation.rule}-${violation.brex_rule_id ?? index}`}
            >
              <div className="validation-violation-meta">
                <span className={`badge ${severityClass(violation.severity)}`}>
                  {t(`migration.generate.brexSeverity.${violation.severity}`)}
                </span>
                <span className="badge info">{violation.rule}</span>
                {violation.brex_rule_id ? (
                  <code style={{ overflowWrap: "anywhere" }}>
                    {t("migration.generate.brexRuleId")}: {violation.brex_rule_id}
                  </code>
                ) : null}
                {violation.brex_severity_level ? (
                  <span className="label">
                    {t("migration.generate.brexSeverityLevel")}: {violation.brex_severity_level}
                  </span>
                ) : null}
              </div>
              <p>{violation.message}</p>
              {violation.path && violation.path !== "/" ? (
                <code className="validation-error-path" style={{ overflowWrap: "anywhere" }}>
                  {violation.path}
                </code>
              ) : null}
            </article>
          ))}
        </div>
      </details>
    </section>
  );
}
