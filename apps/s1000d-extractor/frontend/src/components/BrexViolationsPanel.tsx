import { useTranslation } from "react-i18next";
import { Badge } from "@internal/ui";

import type { DmValidationViolation } from "../lib/wizardTypes";

type Props = {
  hasProfile: boolean;
  isComplete: boolean;
  violations: DmValidationViolation[];
};

function severityVariant(severity: DmValidationViolation["severity"]): "info" | "warning" {
  return severity === "info" ? "info" : "warning";
}

function reportableViolations(violations: DmValidationViolation[]): DmValidationViolation[] {
  return violations.filter((violation) => violation.severity === "error");
}

export function hasBrexViolationsToShow({ hasProfile, isComplete, violations }: Props): boolean {
  return hasProfile && isComplete && reportableViolations(violations).length > 0;
}

export function BrexViolationsPanel({ hasProfile, isComplete, violations }: Props) {
  const { t } = useTranslation();
  const actualViolations = reportableViolations(violations);
  if (!hasBrexViolationsToShow({ hasProfile, isComplete, violations })) return null;

  const hasWarnings = actualViolations.some((violation) => violation.severity !== "info");
  const badgeVariant = hasWarnings ? "warning" : "info";

  return (
    <section className="s1k-validation-violations" aria-label={t("migration.generate.brexCheckTitle")}>
      <h3 className="text-label font-mono uppercase text-fg-dim">
        {t("migration.generate.brexCheckTitle")}
      </h3>
      <details>
        <summary>
          <Badge variant={badgeVariant}>
            {t("migration.generate.brexViolations", { count: actualViolations.length })}
          </Badge>
        </summary>
        <div className="s1k-validation-violations">
          {actualViolations.map((violation, index) => (
            <article
              className="s1k-validation-violation"
              key={`${violation.rule}-${violation.brex_rule_id ?? index}`}
            >
              <div className="s1k-validation-violation-meta">
                <Badge variant={severityVariant(violation.severity)}>
                  {t(`migration.generate.brexSeverity.${violation.severity}`)}
                </Badge>
                <Badge variant="info">{violation.rule}</Badge>
                {violation.brex_rule_id ? (
                  <code className="break-all">
                    {t("migration.generate.brexRuleId")}: {violation.brex_rule_id}
                  </code>
                ) : null}
                {violation.brex_severity_level ? (
                  <span className="text-label font-mono uppercase text-fg-dim">
                    {t("migration.generate.brexSeverityLevel")}: {violation.brex_severity_level}
                  </span>
                ) : null}
              </div>
              <p>{violation.message}</p>
              {violation.path && violation.path !== "/" ? (
                <code className="s1k-validation-error-path break-all">
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
