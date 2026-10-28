import { Plus, Search, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog";
import {
  useClientConfig,
  useClientPreparationPageTitles,
  useClientRules,
  usePatchClientRule,
  usePatchClientRuleBundle,
  useSaveClientPreparationPageTitles,
  type ClientRule,
} from "../hooks/useClientConfig";
import { ClientRuleBundles } from "./ClientRuleBundles";

export function ClientRules() {
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();
  const config = useClientConfig();
  const clientRules = useClientRules();
  const preparationPageTitles = useClientPreparationPageTitles(
    config.data?.client_code === "THALES",
  );
  const patchClientRule = usePatchClientRule();
  const patchClientRuleBundle = usePatchClientRuleBundle();
  const savePreparationPageTitles = useSaveClientPreparationPageTitles();
  const [search, setSearch] = useState("");
  const [activeScope, setActiveScope] = useState<ClientRule["scope"] | "pageTitles">(
    "verification",
  );
  const [newTitle, setNewTitle] = useState("");
  const [titleToRemove, setTitleToRemove] = useState<string | null>(null);
  const [duplicateTitle, setDuplicateTitle] = useState(false);
  const targetRuleCode = searchParams.get("rule");
  const query = search.trim().toLocaleLowerCase();
  const numberQuery = query.startsWith("#") ? query.slice(1) : query;
  const locale = i18n.language.toLowerCase().startsWith("en") ? "en" : "fr";
  const allRules = clientRules.data ?? [];
  const scopedRules = useMemo(
    () =>
      activeScope === "pageTitles"
        ? []
        : allRules.filter((rule) => rule.scope === activeScope),
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
  const pageTitles = preparationPageTitles.data?.titles ?? [];
  const filteredTitles = useMemo(
    () => pageTitles.filter((title) => title.toLocaleLowerCase().includes(query)),
    [pageTitles, query],
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
        {config.data.client_code === "THALES" ? (
          <button
            type="button"
            className={`btn small ${activeScope === "pageTitles" ? "primary" : "secondary"}`}
            aria-pressed={activeScope === "pageTitles"}
            onClick={() => setActiveScope("pageTitles")}
          >
            {t("rules.client.pageTitles.tab")}{" "}
            <span className="badge default">{pageTitles.length}</span>
          </button>
        ) : null}
      </div>

      {activeScope === "pageTitles" ? (
        <section aria-labelledby="preparation-page-titles-heading">
          <div className="row" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <div>
              <h3 id="preparation-page-titles-heading" className="card-title">
                {t("rules.client.pageTitles.title")}
              </h3>
              <p className="muted">{t("rules.client.pageTitles.description")}</p>
            </div>
            <span className="label">
              {filteredTitles.length} {t("rules.client.pageTitles.count")}
            </span>
          </div>
          {preparationPageTitles.isLoading ? (
            <p className="empty-state">{t("common.loading")}</p>
          ) : preparationPageTitles.isError ? (
            <div>
              <p className="banner warn">{t("rules.client.pageTitles.loadFailed")}</p>
              <button
                type="button"
                className="btn secondary small"
                onClick={() => void preparationPageTitles.refetch()}
              >
                {t("common.retry")}
              </button>
            </div>
          ) : (
            <>
              {savePreparationPageTitles.isError ? (
                <p className="banner warn">{t("rules.client.pageTitles.saveFailed")}</p>
              ) : null}
              <form
                className="row"
                style={{ gap: 8, margin: "16px 0", alignItems: "end", flexWrap: "wrap" }}
                onSubmit={(event) => {
                  event.preventDefault();
                  const title = newTitle.trim().replace(/\s+/g, " ");
                  if (!title) return;
                  if (pageTitles.some((item) => item.toLocaleLowerCase() === title.toLocaleLowerCase())) {
                    setDuplicateTitle(true);
                    return;
                  }
                  setDuplicateTitle(false);
                  savePreparationPageTitles.mutate(
                    [...pageTitles, title],
                    { onSuccess: () => setNewTitle("") },
                  );
                }}
              >
                <label style={{ flex: "1 1 260px" }}>
                  <span className="label">{t("rules.client.pageTitles.inputLabel")}</span>
                  <input
                    className="input"
                    value={newTitle}
                    maxLength={80}
                    aria-label={t("rules.client.pageTitles.inputLabel")}
                    onChange={(event) => {
                      setNewTitle(event.target.value);
                      setDuplicateTitle(false);
                    }}
                  />
                </label>
                <button
                  type="submit"
                  className="btn primary"
                  disabled={!newTitle.trim() || savePreparationPageTitles.isPending}
                >
                  <Plus size={16} aria-hidden="true" />
                  {t("rules.client.pageTitles.add")}
                </button>
              </form>
              {duplicateTitle ? (
                <p className="banner warn">{t("rules.client.pageTitles.duplicate")}</p>
              ) : null}
              {savePreparationPageTitles.isPending ? (
                <p className="empty-state" role="status">
                  {t("rules.client.pageTitles.saving")}
                </p>
              ) : null}
              {filteredTitles.length ? (
                <ul
                  style={{
                    display: "grid",
                    gap: 8,
                    listStyle: "none",
                    margin: 0,
                    padding: 0,
                  }}
                >
                  {filteredTitles.map((title) => (
                    <li
                      key={title}
                      className="row card"
                      style={{
                        justifyContent: "space-between",
                        gap: 12,
                        alignItems: "center",
                        padding: 12,
                      }}
                    >
                      <span>{title}</span>
                      <button
                        type="button"
                        className="btn danger small"
                        aria-label={`${t("rules.client.pageTitles.remove")} ${title}`}
                        disabled={savePreparationPageTitles.isPending}
                        onClick={() => setTitleToRemove(title)}
                      >
                        <Trash2 size={16} aria-hidden="true" />
                        {t("rules.client.pageTitles.remove")}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="empty-state">
                  {query
                    ? t("rules.client.searchEmpty")
                    : t("rules.client.pageTitles.empty")}
                </p>
              )}
            </>
          )}
          <ConfirmDialog
            open={titleToRemove !== null}
            onOpenChange={(open) => {
              if (!open) setTitleToRemove(null);
            }}
            title={t("rules.client.pageTitles.removeTitle")}
            description={titleToRemove ?? undefined}
            confirmLabel={t("rules.client.pageTitles.confirmRemove")}
            cancelLabel={t("common.cancel")}
            destructive
            confirmDisabled={savePreparationPageTitles.isPending}
            onConfirm={() => {
              if (titleToRemove) {
                savePreparationPageTitles.mutate(
                  pageTitles.filter((title) => title !== titleToRemove),
                );
              }
              setTitleToRemove(null);
            }}
          />
        </section>
      ) : (
        <>
          <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 8, marginBottom: 16 }}>
            <span className="label">{filtered.length} {t("rules.client.ruleCount")}</span>
          </div>
          {patchClientRule.isError ? (
            <p className="banner warn">{t("rules.client.saveFailed")}</p>
          ) : null}
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
        </>
      )}
    </section>
  );
}
