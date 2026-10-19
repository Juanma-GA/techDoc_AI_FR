import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

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

function RuleItem({ rule }: { rule: BrexRule }) {
  const { t } = useTranslation();
  return (
    <li className="brex-rule-item">
      <div className="row">
        <span className={`badge ${rule.supported ? "info" : "warn"}`}>
          {t(rule.supported ? "migration.brex.supported" : "migration.brex.notSupported")}
        </span>
        <span className="badge info">{flagLabel(rule.allowed_flag, t)}</span>
        {rule.rule_id ? <code>{rule.rule_id}</code> : null}
      </div>
      <code
        className="brex-rule-path"
        style={{ display: "block", overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}
      >
        {rule.object_path}
      </code>
      {rule.object_use ? <p>{rule.object_use}</p> : null}
      {rule.rules_context ? (
        <p>
          <span className="label">{t("migration.brex.context")}: </span>
          <code
            className="brex-rule-path"
            style={{ overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}
          >
            {rule.rules_context}
          </code>
        </p>
      ) : null}
      {rule.object_values.length ? (
        <div>
          <span className="label">{t("migration.brex.allowedValues")}</span>
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
  const ruleCount = profile.rules.length + profile.unsupported_rules.length;
  return (
    <div className="brex-rules-preview">
      <div className="label">
        {profile.dmc} — {t("migration.upload.issueValue", { issue: profile.s1000d_issue })}
      </div>
      <details>
        <summary>{t("migration.brex.rulesSummary", { count: ruleCount })}</summary>
        <div className="brex-rule-list">
          {profile.rules.length ? (
            <ul>
              {profile.rules.map((rule, index) => (
                <RuleItem key={`${rule.rule_id ?? "rule"}-${index}`} rule={rule} />
              ))}
            </ul>
          ) : (
            <p className="label">{t("migration.brex.noStructuredRules")}</p>
          )}
          {profile.unsupported_rules.length ? (
            <div className="banner warn" role="note">
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
            </div>
          ) : null}
        </div>
      </details>
    </div>
  );
}
