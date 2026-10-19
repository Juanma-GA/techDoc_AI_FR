import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ClientRule } from "../hooks/useClientConfig";
import { localizedRuleCode } from "../lib/suggestionText";

type RuleGroup = {
  code: string;
  label: string;
  rules: ClientRule[];
  allRules: ClientRule[];
};

export function ClientRuleBundles({
  rules,
  allRules,
  targetRuleCode,
  localizeRule,
  bulkUpdatePending,
  ruleUpdatePending,
  onToggleRule,
  onToggleBundle,
}: {
  rules: ClientRule[];
  allRules: ClientRule[];
  targetRuleCode: string | null;
  localizeRule: (rule: ClientRule, field: "name" | "description") => string;
  bulkUpdatePending: boolean;
  ruleUpdatePending: boolean;
  onToggleRule: (code: string, active: boolean) => void;
  onToggleBundle: (rules: ClientRule[], active: boolean) => void;
}) {
  const { t } = useTranslation();
  const [expandedRuleCodes, setExpandedRuleCodes] = useState<Set<string>>(() => new Set());
  const [expandedBundleCodes, setExpandedBundleCodes] = useState<Set<string> | null>(null);
  const groups = rules.reduce<RuleGroup[]>((result, rule) => {
    let group = result.find((item) => item.code === rule.bundle_code);
    if (!group) {
      group = {
        code: rule.bundle_code,
        label: rule.bundle_label,
        rules: [],
        allRules: allRules.filter((item) => item.bundle_code === rule.bundle_code),
      };
      result.push(group);
    }
    group.rules.push(rule);
    return result;
  }, []);

  useEffect(() => {
    const target = rules.find((rule) => rule.code === targetRuleCode);
    if (!target) return;
    setExpandedRuleCodes((current) => new Set(current).add(target.code));
    setExpandedBundleCodes((current) => {
      const next = new Set(current ?? rules.map((rule) => rule.bundle_code));
      next.add(target.bundle_code);
      return next;
    });
  }, [rules, targetRuleCode]);

  useEffect(() => {
    if (!targetRuleCode || !rules.some((rule) => rule.code === targetRuleCode)) return;
    const frame = window.requestAnimationFrame(() => {
      const row = document.getElementById(`client-rule-${targetRuleCode}`);
      if (typeof row?.scrollIntoView === "function") {
        row.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [expandedBundleCodes, rules, targetRuleCode]);

  const executionLabel = (execution: ClientRule["execution"]) =>
    t(`rules.compiled.${execution}`);

  const renderRules = (rows: ClientRule[]) => (
    <div className="table-scroll">
      <table className="rules-table client-rules-table">
        <thead>
          <tr>
            <th>{t("rules.form.enabled")}</th>
            <th>{t("rules.client.rule")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((rule) => (
            <tr
              id={`client-rule-${rule.code}`}
              key={rule.code}
              className={rule.code === targetRuleCode ? "row-selected" : undefined}
              style={rule.active ? undefined : { opacity: 0.62 }}
            >
              <td>
                <label
                  className="switch"
                  title={rule.active ? t("rules.disable") : t("rules.enable")}
                >
                  <input
                    type="checkbox"
                    aria-label={`${rule.active ? t("rules.disable") : t("rules.enable")} ${localizeRule(rule, "name")}`}
                    checked={rule.active}
                    disabled={ruleUpdatePending}
                    onChange={(event) => onToggleRule(rule.code, event.target.checked)}
                  />
                  <span className="track" />
                </label>
              </td>
              <td className="rule-name-cell">
                <details
                  open={expandedRuleCodes.has(rule.code)}
                  onToggle={(event) => {
                    const isOpen = event.currentTarget.open;
                    setExpandedRuleCodes((current) => {
                      const next = new Set(current);
                      if (isOpen) next.add(rule.code);
                      else next.delete(rule.code);
                      return next;
                    });
                  }}
                >
                  <summary className="client-rule-summary">
                    <span className="badge default">#{rule.rule_number}</span>
                    <strong>{localizeRule(rule, "name")}</strong>
                    <span className="label">{localizedRuleCode(rule.code, t)}</span>
                  </summary>
                  <p className="client-rule-description">
                    {localizeRule(rule, "description")}
                  </p>
                </details>
                <div className="client-rule-meta">
                  <span className={`badge ${rule.execution === "unsupported" ? "default" : "success"}`}>
                    {executionLabel(rule.execution)}
                  </span>
                  <span className="badge default">
                    {t(`reviewer.suggestion.severity.${rule.severity}`)}
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <>
      {groups.map((group) => {
        const isOpen =
          expandedBundleCodes === null || expandedBundleCodes.has(group.code);
        const allActive = group.allRules.every((rule) => rule.active);
        const actionKey = allActive ? "rules.client.disableAll" : "rules.client.enableAll";
        return (
          <div
            key={group.code}
            className="row"
            style={{
              alignItems: "flex-start",
              flexWrap: "nowrap",
              gap: 8,
              marginBottom: 8,
              width: "100%",
            }}
          >
            <details
              className="collapsible"
              open={isOpen}
              onToggle={(event) => {
                const nextOpen = event.currentTarget.open;
                setExpandedBundleCodes((current) => {
                  const next = new Set(current ?? rules.map((rule) => rule.bundle_code));
                  if (nextOpen) next.add(group.code);
                  else next.delete(group.code);
                  return next;
                });
              }}
              style={{ flex: 1, minWidth: 0 }}
            >
              <summary className="collapsible-summary" style={{ flexWrap: "wrap" }}>
                <ChevronRight size={16} aria-hidden="true" />
                <strong>{group.label}</strong>
                <span className="label">{group.code}</span>
                <span className="badge default">
                  {rules.filter((rule) => rule.bundle_code === group.code).length} {t("rules.client.ruleCount")}
                </span>
              </summary>
              {renderRules(group.rules)}
            </details>
            <button
              type="button"
              className="btn secondary small"
              disabled={bulkUpdatePending}
              aria-label={`${t(actionKey)} ${group.label}`}
              onClick={() => onToggleBundle(group.allRules, !allActive)}
              style={{ flexShrink: 0, minHeight: 40, width: 140, justifyContent: "center" }}
            >
              {t(actionKey)}
            </button>
          </div>
        );
      })}
    </>
  );
}
