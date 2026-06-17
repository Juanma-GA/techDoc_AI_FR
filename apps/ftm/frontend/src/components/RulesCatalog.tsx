/**
 * Catálogo de règles métier en lecture seule — affiché dans l'onglet Paramètres.
 * Deux fetches parallèles : /settings/rules/catalog (structure) + /settings/rules
 * (état résolu + custom rules + instructions libres). Export Markdown côté client.
 */
import { useQueries } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { Badge, Card, CardContent, CardHeader, CardTitle } from "@internal/ui";
import {
  resources,
  type CatalogRule,
  type CustomRule,
  type ResolvedRule,
  type RulesCatalogOut,
} from "../lib/api";

// ── Family metadata (mirrors preview.html _RULES_FAMILY_ORDER / _LABELS) ──
const FAMILY_ORDER = [
  "script", "granule", "texte_general", "rechanges", "outillages",
  "lubrifiant", "infrastructure", "entete_recap", "mise_en_securite",
  "preliminaires", "valeurs_num", "serrage", "fixer", "verrouiller",
  "complementaires", "illustrations",
] as const;

const FAMILY_LABELS: Record<string, string> = {
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

// ── Severity → Badge variant ──────────────────────────────────────────────
function sevVariant(sev: string): "danger" | "warning" | "info" {
  return sev === "high" ? "danger" : sev === "medium" ? "warning" : "info";
}

// ── Param value renderer (read-only) ─────────────────────────────────────
function ParamValue({ type, value }: { type: string; value: unknown }) {
  if (type === "bool") {
    return (
      <input
        type="checkbox"
        checked={Boolean(value)}
        disabled
        className="cursor-not-allowed opacity-60"
      />
    );
  }
  if (type === "list[str]") {
    const list = Array.isArray(value) ? (value as string[]) : [];
    return (
      <textarea
        readOnly
        rows={Math.min(6, Math.max(2, list.length || 2))}
        value={list.join("\n")}
        className="w-full rounded border bg-bg px-2 py-1 font-mono text-xs text-fg-dim opacity-70"
      />
    );
  }
  if (type === "map[str,str]") {
    const dict =
      value && typeof value === "object" ? (value as Record<string, string>) : {};
    const lines = Object.entries(dict)
      .map(([k, v]) => `${k} => ${v}`)
      .join("\n");
    return (
      <textarea
        readOnly
        rows={3}
        value={lines}
        className="w-full rounded border bg-bg px-2 py-1 font-mono text-xs text-fg-dim opacity-70"
      />
    );
  }
  return (
    <input
      type={type === "int" || type === "float" ? "number" : "text"}
      readOnly
      value={value == null ? "" : String(value)}
      className="w-full rounded border bg-bg px-2 py-1 text-sm text-fg-dim opacity-70"
    />
  );
}

// ── Single rule block ─────────────────────────────────────────────────────
function RuleBlock({
  rule,
  resolved,
}: {
  rule: CatalogRule;
  resolved: ResolvedRule | undefined;
}) {
  const { t } = useTranslation();
  const enabled = resolved ? resolved.enabled : rule.enabled_default;
  const runnable = resolved ? resolved.runnable : true;
  const resolvedParams: Record<string, unknown> = resolved?.params ?? {};
  const name = t(rule.name_key, { defaultValue: rule.id });
  const desc = t(rule.description_key, { defaultValue: "" });

  return (
    <div className="rounded-md border border-border bg-bg-elev p-3 space-y-2">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="checkbox"
          checked={enabled}
          disabled
          className="cursor-not-allowed opacity-60"
        />
        <span className="text-sm font-semibold text-fg">{name}</span>
        <Badge variant={sevVariant(rule.severity)}>{rule.severity}</Badge>
        {rule.anomaly_types.length > 0 && (
          <code className="text-xs text-fg-dim">
            → {rule.anomaly_types.join(", ")}
          </code>
        )}
        {!runnable && (
          <Badge
            variant="warning"
            title={`Capacités manquantes : ${rule.requires.join(", ")}`}
          >
            non runnable
          </Badge>
        )}
      </div>

      {/* Description */}
      {desc && <p className="text-xs text-fg-dim leading-relaxed">{desc}</p>}

      {/* Params */}
      {Object.keys(rule.params).length > 0 && (
        <div className="space-y-1 pl-1">
          {Object.keys(rule.params).map((pname) => {
            const pspec = rule.params[pname];
            if (!pspec) return null;
            const label = t(pspec.name_key, { defaultValue: pname });
            const val =
              pname in resolvedParams ? resolvedParams[pname] : pspec.default;
            return (
              <div key={pname}>
                <p className="mb-0.5 text-xs text-fg-dim">{label}</p>
                <ParamValue type={pspec.type} value={val} />
              </div>
            );
          })}
        </div>
      )}

      {/* Examples */}
      {rule.examples.length > 0 && (
        <details className="mt-1">
          <summary className="cursor-pointer text-xs text-fg-dim">
            Exemples ({rule.examples.length})
          </summary>
          <ul className="mt-1 space-y-0.5 pl-2">
            {rule.examples.map((ex, i) => (
              <li key={i} className="text-xs">
                <span className={ex.valid ? "text-green-400" : "text-red-400"}>
                  {ex.valid ? "✓" : "✗"}
                </span>{" "}
                <code className="rounded bg-card-hover px-1">{ex.text}</code>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

// ── Custom rules table ────────────────────────────────────────────────────
function CustomRulesTable({ rules }: { rules: CustomRule[] }) {
  const { t } = useTranslation();
  if (!rules.length) {
    return (
      <p className="text-xs italic text-fg-dim">
        {t("settings.customRulesEmpty")}
      </p>
    );
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs uppercase tracking-wider text-fg-dim">
          <th className="pb-1 pr-3 w-1/4">Label</th>
          <th className="pb-1 pr-3">Consigne</th>
          <th className="pb-1 w-20">Criticité</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {rules.map((r, i) => (
          <tr key={i}>
            <td className="py-1 pr-3 align-top">
              <input
                readOnly
                value={r.label}
                className="w-full rounded border bg-bg px-2 py-1 text-xs text-fg-dim opacity-70"
              />
            </td>
            <td className="py-1 pr-3 align-top">
              <textarea
                readOnly
                rows={2}
                value={r.consigne}
                className="w-full rounded border bg-bg px-2 py-1 text-xs text-fg-dim opacity-70"
              />
            </td>
            <td className="py-1 align-top">
              <input
                readOnly
                value={r.severity}
                className="w-full rounded border bg-bg px-2 py-1 text-center text-xs text-fg-dim opacity-70"
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── Markdown export (pure, no server round-trip) ──────────────────────────
function exportRulesAsMarkdown(
  catalog: RulesCatalogOut,
  t: TFunction,
) {
  const { rules, resolved } = catalog;
  const resolvedById: Record<string, ResolvedRule> = Object.fromEntries(
    resolved.map((r) => [r.id, r]),
  );

  const lines: string[] = [];
  lines.push("# Règles métier FTM Agent", "");
  lines.push(`État du moteur exporté le ${new Date().toISOString()}`, "");
  lines.push(
    `${rules.length} règles réparties en ${FAMILY_ORDER.length} sections.`,
    "Les règles désactivées sont marquées ✗ ; les non-runnable signalent une capacité manquante.",
    "",
    "---",
    "",
  );

  const byFamily: Record<string, CatalogRule[]> = {};
  for (const r of rules) {
    (byFamily[r.family] ??= []).push(r);
  }

  for (const fam of FAMILY_ORDER) {
    const famRules = byFamily[fam];
    if (!famRules?.length) continue;
    lines.push(`## ${FAMILY_LABELS[fam] ?? fam}`, "");

    for (const rule of famRules) {
      const res: { enabled: boolean; params: Record<string, unknown>; runnable: boolean } =
        resolvedById[rule.id] ?? {
          enabled: rule.enabled_default,
          params: {} as Record<string, unknown>,
          runnable: true,
        };

      const status = res.enabled
        ? res.runnable
          ? "✓ activée"
          : "⚠ activée mais non runnable"
        : "✗ désactivée";

      const name = t(rule.name_key, { defaultValue: rule.id }) as string;
      const desc = t(rule.description_key, { defaultValue: "" }) as string;

      lines.push(`### ${name} (\`${rule.id}\`)`, "");
      lines.push(`- **Statut** : ${status}`);
      lines.push(`- **Sévérité** : \`${rule.severity}\``);
      if (rule.anomaly_types.length) {
        lines.push(
          `- **Type(s) d'anomalie** : ${rule.anomaly_types.map((a) => `\`${a}\``).join(", ")}`,
        );
      }
      if (rule.requires.length) {
        lines.push(
          `- **Capacités requises** : ${rule.requires.map((c) => `\`${c}\``).join(", ")}`,
        );
      }
      lines.push("");
      if (desc) lines.push(desc, "");

      const paramNames = Object.keys(rule.params);
      if (paramNames.length) {
        lines.push("**Paramètres :**", "");
        for (const pname of paramNames) {
          const pspec = rule.params[pname];
          if (!pspec) continue;
          const label = t(pspec.name_key, { defaultValue: pname }) as string;
          const val =
            pname in res.params ? res.params[pname] : pspec.default;
          const valStr = Array.isArray(val)
            ? val.length
              ? "\n" + (val as unknown[]).map((v) => `  - ${String(v)}`).join("\n")
              : "*(liste vide)*"
            : `\`${String(val ?? "")}\``;
          lines.push(
            `- **${label}** (\`${pname}\` · \`${pspec.type}\`) : ${valStr}`,
          );
        }
        lines.push("");
      }

      if (rule.examples.length) {
        lines.push("**Exemples :**", "");
        for (const ex of rule.examples) {
          const noteStr = ex.note_key
            ? ` — ${t(ex.note_key, { defaultValue: ex.note_key }) as string}`
            : "";
          lines.push(`- ${ex.valid ? "✓" : "✗"} \`${ex.text}\`${noteStr}`);
        }
        lines.push("");
      }
    }
  }

  lines.push("---", "");
  lines.push(
    "*Généré depuis `app/core/rules_catalog.py` — la source de vérité des règles.*",
    "",
  );

  const blob = new Blob([lines.join("\n")], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const stamp = new Date().toISOString().slice(0, 10);
  const a = document.createElement("a");
  a.href = url;
  a.download = `RULES-${stamp}.md`;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}

// ── Main export ───────────────────────────────────────────────────────────
export function RulesCatalog() {
  const { t } = useTranslation();

  const [catalogQuery, legacyQuery] = useQueries({
    queries: [
      {
        queryKey: ["settings", "rules", "catalog"],
        queryFn: resources.settings.getCatalog,
      },
      {
        queryKey: ["settings", "rules", "legacy"],
        queryFn: resources.settings.getLegacyRules,
      },
    ],
  });

  const catalog = catalogQuery.data;
  const legacy = legacyQuery.data;
  const isLoading = catalogQuery.isPending || legacyQuery.isPending;
  const overridden = legacy?.overridden ?? false;
  const customRules = legacy?.rules.regles_personnalisees ?? [];
  const instructionsLibres = legacy?.rules.instructions_libres ?? "";

  const resolvedById: Record<string, ResolvedRule> = Object.fromEntries(
    (catalog?.resolved ?? []).map((r) => [r.id, r]),
  );

  const byFamily: Record<string, CatalogRule[]> = {};
  for (const r of catalog?.rules ?? []) {
    (byFamily[r.family] ??= []).push(r);
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle>{t("settings.rulesSection")}</CardTitle>
          {overridden && (
            <Badge variant="info">{t("settings.rulesOverride")}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Read-only banner */}
        <div className="rounded-md border border-brand/30 bg-brand/10 px-4 py-3 text-sm text-fg">
          {t("settings.rulesReadOnlyBanner")}
        </div>

        {/* Export MD + hint */}
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={!catalog}
            onClick={() => catalog && exportRulesAsMarkdown(catalog, t)}
            className="rounded border px-3 py-1.5 text-sm text-fg-dim transition-colors hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
          >
            {t("settings.exportRulesMd")}
          </button>
          <span className="text-xs text-fg-dim">
            {t("settings.exportRulesMdHint")}
          </span>
        </div>

        <p className="text-xs text-fg-dim">{t("settings.atmColumnsMoved")}</p>

        {/* Catalog blocks */}
        {isLoading && (
          <p className="text-sm text-fg-dim">{t("common.loading")}</p>
        )}

        {!isLoading && catalog && (
          <div className="space-y-4">
            {FAMILY_ORDER.map((fam) => {
              const famRules = byFamily[fam];
              if (!famRules?.length) return null;
              return (
                <div key={fam}>
                  <h3 className="mb-2 text-sm font-semibold text-fg">
                    {FAMILY_LABELS[fam] ?? fam}
                  </h3>
                  <div className="space-y-2">
                    {famRules.map((rule) => (
                      <RuleBlock
                        key={rule.id}
                        rule={rule}
                        resolved={resolvedById[rule.id]}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Custom rules */}
        <div>
          <h3 className="mb-1 text-sm font-semibold text-fg">
            {t("settings.customRules")}
          </h3>
          <p className="mb-1 text-xs text-fg-dim">
            {t("settings.customRulesIntro")}
          </p>
          <p className="mb-2 text-xs text-fg-dim">
            {t("settings.refColumnPlaceholder")}
          </p>
          {!isLoading && <CustomRulesTable rules={customRules} />}
        </div>

        {/* Instructions libres */}
        <div>
          <h3 className="mb-1 text-sm font-semibold text-fg">
            {t("settings.freeInstructions")}
          </h3>
          <textarea
            readOnly
            rows={5}
            value={instructionsLibres}
            className="w-full rounded-md border bg-bg px-3 py-2 text-sm text-fg-dim opacity-70"
          />
        </div>
      </CardContent>
    </Card>
  );
}
