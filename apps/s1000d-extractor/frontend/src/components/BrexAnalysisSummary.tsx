import { useQuery } from "@tanstack/react-query";
import { Alert, Badge } from "@internal/ui";
import { useTranslation } from "react-i18next";

import { brexApi } from "../lib/api";
import { getBrexRuleCoverage } from "../lib/brexCoverage";
import { formatApiError } from "../lib/migrationUtils";
import type { DmValidationViolation, WizardDm } from "../lib/wizardTypes";

type DmSummary = Pick<WizardDm, "dm_id" | "title" | "has_xml" | "brex_violations">;

type Props = {
  hasProfile: boolean;
  profileId: string | null;
  dms: DmSummary[];
};

type WarningGroup = {
  violation: DmValidationViolation;
  affectedDmIds: Set<string>;
};

function groupWarnings(dms: DmSummary[]): WarningGroup[] {
  const groups = new Map<string, WarningGroup>();
  for (const dm of dms) {
    if (!dm.has_xml) continue;
    for (const violation of dm.brex_violations ?? []) {
      if (violation.severity === "error") continue;
      const key = JSON.stringify([
        violation.severity,
        violation.rule,
        violation.brex_rule_id ?? null,
        violation.brex_severity_level ?? null,
        violation.path,
        violation.message,
      ]);
      const group = groups.get(key) ?? {
        violation,
        affectedDmIds: new Set<string>(),
      };
      group.affectedDmIds.add(dm.dm_id);
      groups.set(key, group);
    }
  }
  return [...groups.values()];
}

function severityVariant(severity: DmValidationViolation["severity"]): "info" | "warning" {
  return severity === "info" ? "info" : "warning";
}

export function BrexAnalysisSummary({ hasProfile, profileId, dms }: Props) {
  const { t } = useTranslation();
  const profileQuery = useQuery({
    queryKey: ["s1000d-brex", profileId],
    queryFn: () => {
      if (!profileId) throw new Error("BREX profile ID is required.");
      return brexApi.detail(profileId);
    },
    enabled: hasProfile && Boolean(profileId),
  });

  if (!hasProfile) return null;

  const completedDms = dms.filter((dm) => dm.has_xml);
  const analysisComplete = dms.length > 0 && completedDms.length === dms.length;
  const errors = completedDms.flatMap((dm) =>
    (dm.brex_violations ?? []).filter((violation) => violation.severity === "error"),
  );
  const errorDmCount = new Set(
    completedDms
      .filter((dm) => (dm.brex_violations ?? []).some((violation) => violation.severity === "error"))
      .map((dm) => dm.dm_id),
  ).size;
  const warningGroups = groupWarnings(completedDms);
  const coverage = profileQuery.data ? getBrexRuleCoverage(profileQuery.data) : null;
  const partial =
    warningGroups.length > 0 ||
    (coverage !== null && coverage.unsupported > 0);
  const coverageError = !profileId
    ? t("migration.generate.brexProfileIdMissing")
    : t("migration.generate.brexCoverageError", {
        message: formatApiError(t, profileQuery.error),
      });

  return (
    <section className="s1k-validation-violations" aria-labelledby="brex-analysis-summary-title">
      <h3 id="brex-analysis-summary-title" className="text-label font-mono uppercase text-fg-dim">
        {t("migration.generate.brexAnalysisTitle")}
      </h3>

      {coverage ? (
        <div className="flex flex-wrap gap-2" role="status">
          <Badge variant="success">
            {t("migration.brex.coverageAutomatic", { count: coverage.automatic })}
          </Badge>
          <Badge variant="info">
            {t("migration.brex.coverageContextual", { count: coverage.contextual })}
          </Badge>
          <Badge variant={coverage.unsupported ? "warning" : "success"}>
            {t("migration.brex.coverageUnsupported", { count: coverage.unsupported })}
          </Badge>
        </div>
      ) : null}

      {profileQuery.isLoading ? (
        <p className="text-sm text-fg-dim" role="status">{t("migration.generate.brexCoverageLoading")}</p>
      ) : null}
      {profileQuery.isError || !profileId ? (
        <Alert variant="danger">{coverageError}</Alert>
      ) : null}

      {!analysisComplete ? (
        <Alert variant="warning">
          {t("migration.generate.brexAnalysisPending", {
            completed: completedDms.length,
            total: dms.length,
          })}
        </Alert>
      ) : null}

      {analysisComplete && coverage ? (
        errors.length ? (
          <Alert variant="danger">
            <strong>
              {t("migration.generate.brexViolationsFound", {
                count: errors.length,
                dmCount: errorDmCount,
              })}
            </strong>
            {partial ? (
              <p>{t("migration.generate.brexPartialStatus")}</p>
            ) : null}
          </Alert>
        ) : (
          <Alert variant={partial ? "warning" : "success"}>
            <strong>{t("migration.generate.brexNoViolations")}</strong>
            {partial ? (
              <p>{t("migration.generate.brexPartialStatus")}</p>
            ) : null}
          </Alert>
        )
      ) : null}

      {warningGroups.length ? (
        <details>
          <summary>
            {t("migration.generate.brexWarningGroupCount", { count: warningGroups.length })}
          </summary>
          <div className="s1k-validation-violations">
            {warningGroups.map(({ violation, affectedDmIds }) => (
              <article
                className="s1k-validation-violation"
                key={JSON.stringify([
                  violation.rule,
                  violation.brex_rule_id,
                  violation.path,
                  violation.message,
                ])}
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
                  <span className="text-label font-mono uppercase text-fg-dim">
                    {t("migration.generate.brexAffectedDms", {
                      count: affectedDmIds.size,
                      total: completedDms.length,
                    })}
                  </span>
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
      ) : null}
    </section>
  );
}
