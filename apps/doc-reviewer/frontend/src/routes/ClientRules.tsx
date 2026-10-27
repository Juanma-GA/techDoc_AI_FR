import { Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import {
  useClientConfig,
  useClientRules,
  usePatchClientRule,
  usePatchClientRuleBundle,
  type ClientRule,
} from "../hooks/useClientConfig";
import { ClientRuleBundles } from "./ClientRuleBundles";

export function ClientRules() {
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();
  const config = useClientConfig();
  const clientRules = useClientRules();
  const patchClientRule = usePatchClientRule();
  const patchClientRuleBundle = usePatchClientRuleBundle();
  const [search, setSearch] = useState("");
  const [activeScope, setActiveScope] = useState<ClientRule["scope"]>("verification");
  const targetRuleCode = searchParams.get("rule");
  const query = search.trim().toLocaleLowerCase();
  const numberQuery = query.startsWith("#") ? query.slice(1) : query;
  const locale = i18n.language.toLowerCase().startsWith("en") ? "en" : "fr";
  const allRules = clientRules.data ?? [];
  const scopedRules = useMemo(
    () => allRules.filter((rule) => rule.scope === activeScope),
    [activeScope, allRules],
  );
  useEffect(() => {
    const target = allRules.find((rule) => rule.code === targetRuleCode);
    if (target) setActiveScope(target.scope);
  }, [allRules, targetRuleCode]);
  const localizeRule = useCallback(
    (rule: ClientRule, field: "name" | "description") => {
      const catalogKey = `clientRuleCatalog.${rule.code}.${field}`;
      const translated = t(catalogKey);
      const catalogTranslation = translated === catalogKey ? "" : translated;
      return catalogTranslation || rule.translations[locale]?.[field] || rule[field];
    },
    [locale, t],
  );
  const filtered = useMemo(
    () =>
      scopedRules.filter((rule) =>
        [rule.code, rule.name, localizeRule(rule, "name"), localizeRule(rule, "description")].some(
          (value) => value.toLocaleLowerCase().includes(query),
        ) || String(rule.rule_number).includes(numberQuery),
      ),
    [localizeRule, numberQuery, query, scopedRules],
  );
  if (config.isLoading || clientRules.isLoading) {
    return <p className="empty-state">{t("common.loading")}</p>;
  }
  if (config.isError || clientRules.isError || !config.data || !clientRules.data) {
    return (
      <section className="card">
        <p className="banner warn">{t("rules.client.loadFailed")}</p>
        <button
          type="button"
          className="btn secondary small"
          onClick={() => {
            void config.refetch();
            void clientRules.refetch();
          }}
        >
          {t("common.retry")}
        </button>
      </section>
    );
  }

  return (
    <section className="card">
      <div className="row" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h2 className="card-title">{config.data.label}</h2>
        </div>
        <label className="row" style={{ gap: 8, minWidth: 220, flexWrap: "nowrap" }}>
          <Search size={16} aria-hidden="true" />
          <input
            type="search"
            className="input"
            style={{ width: "auto", flex: 1, minWidth: 0 }}
            aria-label={t("rules.client.search")}
            placeholder={t("rules.client.search")}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
      </div>

      <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 8, marginBottom: 16 }}>
        <span className="label">{filtered.length} {t("rules.client.ruleCount")}</span>
      </div>

      <div
        className="row"
        role="group"
        aria-label={t("rules.client.scopeSelector")}
        style={{ gap: 8, flexWrap: "wrap", marginBottom: 16 }}
      >
        {(["verification", "preparation"] as const).map((scope) => {
          const selected = activeScope === scope;
          const count = allRules.filter((rule) => rule.scope === scope).length;
          return (
            <button
              key={scope}
              type="button"
              className={`btn small ${selected ? "primary" : "secondary"}`}
              aria-pressed={selected}
              onClick={() => setActiveScope(scope)}
            >
              {t(`rules.client.scope.${scope}`)} <span className="badge default">{count}</span>
            </button>
          );
        })}
      </div>

      {patchClientRule.isError ? <p className="banner warn">{t("rules.client.saveFailed")}</p> : null}
      {patchClientRuleBundle.isError ? (
        <p className="banner warn">{t("rules.client.bulkSaveFailed")}</p>
      ) : null}
      {filtered.length > 0 ? (
        <ClientRuleBundles
          rules={filtered}
          allRules={scopedRules}
          targetRuleCode={targetRuleCode}
          localizeRule={localizeRule}
          bulkUpdatePending={patchClientRuleBundle.isPending || patchClientRule.isPending}
          ruleUpdatePending={patchClientRuleBundle.isPending}
          onToggleRule={(code, active) => patchClientRule.mutate({ code, active })}
          onToggleBundle={(rules, active) => patchClientRuleBundle.mutate({ rules, active })}
        />
      ) : (
        <p className="empty-state">
          {scopedRules.length === 0
            ? t("rules.client.scopeEmpty")
            : t("rules.client.searchEmpty")}
        </p>
      )}
    </section>
  );
}
