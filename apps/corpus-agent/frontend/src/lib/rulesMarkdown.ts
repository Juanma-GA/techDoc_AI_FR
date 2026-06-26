import type { TFunction } from "i18next";

import type { RulesCatalogOut } from "./types";

// Génère un RULES.md reflétant le catalogue (port de _exportRulesAsMarkdown du
// preview) puis déclenche le téléchargement côté client.
export function exportRulesMarkdown(catalog: RulesCatalogOut, t: TFunction): void {
  const lines: string[] = ["# Règles métier Corpus Agent", ""];
  const byFamily = new Map<string, RulesCatalogOut["rules"]>();
  for (const r of catalog.rules) {
    if (!byFamily.has(r.family)) byFamily.set(r.family, []);
    byFamily.get(r.family)!.push(r);
  }
  for (const [family, rules] of byFamily) {
    lines.push(`## ${family}`, "");
    for (const r of rules) {
      lines.push(`### ${t(r.name_key)}`);
      lines.push(`- sévérité : ${r.severity}`);
      if (r.anomaly_types.length) lines.push(`- types : ${r.anomaly_types.join(", ")}`);
      lines.push("", t(r.description_key), "");
      for (const ex of r.examples) {
        lines.push(`- ${ex.valid ? "✓" : "✗"} \`${ex.text}\``);
      }
      lines.push("");
    }
  }
  const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "RULES.md";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
