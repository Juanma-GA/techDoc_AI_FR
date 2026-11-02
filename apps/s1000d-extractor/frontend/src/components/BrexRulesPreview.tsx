import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { Alert, Badge } from "@internal/ui";

import { getBrexRuleCoverage } from "../lib/brexCoverage";
import type { BrexProfileDetail, BrexRule } from "../lib/api";

function flagLabel(flag: string, t: TFunction) {
  if (flag === "0") return t("migration.brex.flagForbidden");
  if (flag === "1") return t("migration.brex.flagRequired");
  if (flag === "2") return t("migration.brex.flagOptional");
  return t("migration.brex.flagUnknown", { flag });
}

function unsupportedLabel(ruleType: string, t: TFunction) {
  if (ruleType === "nonContextRule") return t("migration.brex.unsupportedNonContext");
  if (ruleType === "notationRule") return t("migration.brex.unsupportedNotation");
  if (ruleType === "snsRules") return t("migration.brex.unsupportedSns");
  return t("migration.brex.unsupportedOther");
}

function supportReasonLabel(reason: string, t: TFunction) {
  return t(`migration.brex.supportReason.${reason}`, {
    defaultValue: t("migration.brex.supportReason.other"),
  });
}

function RuleItem({ rule }: { rule: BrexRule }) {
  const { t } = useTranslation();
  const badgeVariant = rule.support_status === "unsupported"
    ? "warning"
    : rule.support_status === "contextual"
      ? "info"
      : "success";
  return (
    <li className="s1k-brex-rule-item">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={badgeVariant}>
          {t(`migration.brex.supportStatus.${rule.support_status}`)}
        </Badge>
        <Badge variant="info">{flagLabel(rule.allowed_flag, t)}</Badge>
        {rule.rule_id ? <code>{rule.rule_id}</code> : null}
      </div>
      <code
        className="s1k-brex-rule-path block break-words whitespace-pre-wrap"
      >
        {rule.object_path}
      </code>
      {rule.support_reason ? (
        <p className="text-label font-mono uppercase text-fg-dim">
          {supportReasonLabel(rule.support_reason, t)}
        </p>
      ) : null}
      {rule.object_use ? <p>{rule.object_use}</p> : null}
      {rule.rules_context ? (
        <p>
          <span className="text-label font-mono uppercase text-fg-dim">{t("migration.brex.context")}: </span>
          <code
            className="s1k-brex-rule-path break-words whitespace-pre-wrap"
          >
            {rule.rules_context}
          </code>
        </p>
      ) : null}
      {rule.object_values.length ? (
        <div>
          <span className="text-label font-mono uppercase text-fg-dim">
            {t("migration.brex.allowedValues")}
          </span>
          <ul>
            {rule.object_values.map((value, index) => (
              <li key={`${value.value_allowed}-${index}`}>
                <code>{value.value_allowed ?? value.value_text}</code>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </li>
  );
}

export function BrexRulesPreview({ profile }: { profile: BrexProfileDetail }) {
  const { t } = useTranslation();
  const coverage = getBrexRuleCoverage(profile);
  return (
    <div className="s1k-brex-rules-preview">
      <div className="text-label font-mono uppercase text-fg-dim">
        {profile.dmc} — {t("migration.upload.issueValue", { issue: profile.s1000d_issue })}
      </div>
      <details>
        <summary>{t("migration.brex.rulesSummary", { count: coverage.total })}</summary>
        <div className="s1k-brex-rule-list">
          <div className="flex flex-wrap items-center gap-2" role="status">
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
          {profile.rules.length ? (
            <ul>
              {profile.rules.map((rule, index) => (
                <RuleItem key={`${rule.rule_id ?? "rule"}-${index}`} rule={rule} />
              ))}
            </ul>
          ) : (
            <p className="text-label font-mono uppercase text-fg-dim">
              {t("migration.brex.noStructuredRules")}
            </p>
          )}
          {profile.unsupported_rules.length ? (
            <Alert variant="warning" role="note">
              <div>
                {t("migration.brex.unsupportedCount", {
                  count: profile.unsupported_rules.length,
                })}
              </div>
              <ul>
                {profile.unsupported_rules.map((rule, index) => (
                  <li key={`${rule.rule_type}-${rule.rule_id ?? index}`}>
                    <strong>{unsupportedLabel(rule.rule_type, t)}</strong>
                    {rule.rule_id ? <code> {rule.rule_id}</code> : null}
                    {rule.description ? <div>{rule.description}</div> : null}
                  </li>
                ))}
              </ul>
            </Alert>
          ) : null}
        </div>
      </details>
    </div>
  );
}
