import { useQuery } from "@tanstack/react-query";
import { type ReactElement, useState } from "react";
import { useTranslation } from "react-i18next";

import { settingsApi } from "../../lib/api";
import { exportRulesMarkdown } from "../../lib/rulesMarkdown";
import { severityClass } from "../../lib/format";
import type { RuleCatalogEntry, RuleParamSchema, RulesCatalogOut, RulesLegacyOut } from "../../lib/types";

function ParamField({ name, schema, value }: { name: string; schema: RuleParamSchema; value: unknown }) {
  const v = value ?? schema.default;
  let field: ReactElement;
  if (schema.type === "bool") {
    field = <input type="checkbox" checked={!!v} disabled readOnly />;
  } else if (schema.type === "list") {
    field = <textarea readOnly value={Array.isArray(v) ? (v as unknown[]).join("\n") : ""} />;
  } else if (schema.type === "map") {
    const entries = v && typeof v === "object" ? Object.entries(v as Record<string, unknown>) : [];
    field = <textarea readOnly value={entries.map(([k, val]) => `${k} => ${String(val)}`).join("\n")} />;
  } else {
    field = <input className="input" readOnly value={v == null ? "" : String(v)} />;
  }
  return (
    <label className="rule-param">
      <span>{name}</span>
      {field}
    </label>
  );
}

function RuleBlock({ rule, params, runnable }: { rule: RuleCatalogEntry; params: Record<string, unknown>; runnable: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <div className="rule-block">
      <div className="rule-block-head">
        <input type="checkbox" checked disabled readOnly />
        <span className="rule-block-name">{t(rule.name_key)}</span>
        <span className={`badge ${severityClass(rule.severity)}`}>{rule.severity}</span>
        {rule.anomaly_types.map((ty) => (
          <span className="badge off" key={ty}>{ty}</span>
        ))}
        {!runnable && (
          <span className="badge warn" title={`Capabilites manquantes : ${rule.requires.join(", ")}`}>
            non runnable
          </span>
        )}
      </div>
      <div className="rule-block-desc">{t(rule.description_key)}</div>
      {Object.entries(rule.params).map(([pname, schema]) => (
        <ParamField key={pname} name={schema.name_key ? t(schema.name_key) : pname} schema={schema} value={params[pname]} />
      ))}
      {rule.examples.length > 0 && (
        <div className="rule-examples">
          <button type="button" className="btn ghost small" onClick={() => setOpen((o) => !o)}>
            {open ? "▾" : "▸"} {rule.examples.length} ex.
          </button>
          {open &&
            rule.examples.map((ex, i) => (
              <div className={`rule-example ${ex.valid ? "ok" : "bad"}`} key={i}>
                {ex.valid ? "✓" : "✗"} {ex.text}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

// Libellés numérotés + ordre fixe des familles de règles (cf. preview
// _RULES_FAMILY_LABELS / _RULES_FAMILY_ORDER). Hardcodés côté preview : pas
// de clé i18n associée — voir note dans le résumé de diff.
const RULES_FAMILY_LABELS: Record<string, string> = {
  script: "1. Script",
  granule: "1. Granule",
  texte_general: "2. Général — Texte & structure",
  rechanges: "3. Rechanges",
  outillages: "4. Outillages",
  lubrifiant: "5. Lubrifiant",
  infrastructure: "6. Infrastructure",
  entete_recap: "7. En-tête du Récapitulatif",
  mise_en_securite: "8. Opérations de mise en sécurité",
  preliminaires: "9. Opérations préliminaires",
  valeurs_num: "10. Valeurs numériques",
  serrage: "11. Serrage",
  fixer: "12. Fixer",
  verrouiller: "13. Verrouiller",
  complementaires: "14. Opérations complémentaires",
  illustrations: "15. Illustrations",
};
const RULES_FAMILY_ORDER: string[] = [
  "script", "granule", "texte_general", "rechanges", "outillages", "lubrifiant",
  "infrastructure", "entete_recap", "mise_en_securite", "preliminaires",
  "valeurs_num", "serrage", "fixer", "verrouiller", "complementaires", "illustrations",
];

export function RulesCatalogCard() {
  const { t } = useTranslation();
  const catalogQuery = useQuery<RulesCatalogOut>({ queryKey: ["rules-catalog"], queryFn: settingsApi.rulesCatalog });
  const legacyQuery = useQuery<RulesLegacyOut>({ queryKey: ["rules-legacy"], queryFn: settingsApi.rulesLegacy });

  const catalog = catalogQuery.data;
  const resolvedById = new Map((catalog?.resolved ?? []).map((r) => [r.id, r]));
  const byFamily = new Map<string, RuleCatalogEntry[]>();
  for (const r of catalog?.rules ?? []) {
    if (!byFamily.has(r.family)) byFamily.set(r.family, []);
    byFamily.get(r.family)!.push(r);
  }
  // Familles dans l'ordre fixe, puis toute famille inconnue à la suite.
  const orderedFamilies = [
    ...RULES_FAMILY_ORDER.filter((f) => byFamily.has(f)),
    ...[...byFamily.keys()].filter((f) => !RULES_FAMILY_ORDER.includes(f)),
  ];

  const legacy = legacyQuery.data?.rules;
  const instructions = legacy?.instructions_libres ?? "";

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 className="card-title" style={{ margin: 0 }}>{t("settings.rules")}</h2>
      </div>
      <div className="banner">{t("settings.rulesReadOnlyBanner")}</div>

      <div className="row" style={{ alignItems: "center" }}>
        {catalog && (
          <button type="button" className="btn secondary small" onClick={() => exportRulesMarkdown(catalog, t)}>
            {t("settings.exportRulesMd")}
          </button>
        )}
        <span className="label" style={{ color: "var(--fg-muted)" }}>{t("settings.exportRulesMdHint")}</span>
      </div>

      <div className="label">{t("settings.atmColumnsMoved")}</div>

      {catalogQuery.isLoading ? (
        <div className="empty-state">{t("common.loading")}</div>
      ) : (
        orderedFamilies.map((family) => (
          <div key={family}>
            <div className="rules-section-title">{RULES_FAMILY_LABELS[family] ?? family}</div>
            {(byFamily.get(family) ?? []).map((r) => (
              <RuleBlock key={r.id} rule={r} params={resolvedById.get(r.id)?.params ?? {}} runnable={resolvedById.get(r.id)?.runnable ?? true} />
            ))}
          </div>
        ))
      )}

      <div className="rules-section-title">{t("rules.aiGuidelines")}</div>
      <div className="label">{t("rules.aiGuidelinesHint")}</div>
      <textarea readOnly rows={5} value={instructions} />
    </div>
  );
}
