import { FileDropzone } from "@internal/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { settingsApi } from "../../lib/api";
import { severityClass } from "../../lib/format";
import type { CustomRule, RulesLegacyOut, SpecRule } from "../../lib/types";

const norm = (s: string) => s.toLowerCase().replace(/\s+/g, " ").trim();
const newId = () => crypto.randomUUID().replace(/-/g, "").slice(0, 8);

/**
 * Genere des regles depuis un document de reference (from-spec) : l'IA propose
 * des regles, l'utilisateur coche celles a garder -> elles rejoignent la
 * checklist EN ATTENTE de validation (validated:false), avec dedup par consigne.
 */
export function SpecGenerateCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const rulesQuery = useQuery<RulesLegacyOut>({ queryKey: ["rules-legacy"], queryFn: settingsApi.rulesLegacy });
  const existing: CustomRule[] = rulesQuery.data?.rules.regles_personnalisees ?? [];

  const [proposals, setProposals] = useState<SpecRule[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [filename, setFilename] = useState("");

  async function onPick(f: File | null) {
    setFilename(f?.name ?? "");
    setProposals(null);
    setSelected(new Set());
    setMsg("");
    if (!f) return;
    setBusy(true);
    try {
      const out = await settingsApi.rulesFromSpec(f);
      setProposals(out.regles);
      setSelected(new Set(out.regles.map((_, i) => i)));
      if (out.regles.length === 0) setMsg(t("settings.specGenNone"));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function toggle(i: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  async function addSelected() {
    if (!proposals) return;
    setBusy(true);
    setMsg("");
    try {
      const seen = new Set(existing.map((r) => norm(r.consigne)));
      const toAdd: CustomRule[] = [];
      let skipped = 0;
      proposals.forEach((p, i) => {
        if (!selected.has(i)) return;
        const key = norm(p.consigne);
        if (!key || seen.has(key)) {
          skipped += 1;
          return;
        }
        seen.add(key);
        toAdd.push({
          id: newId(),
          label: p.label,
          consigne: p.consigne,
          severity: p.severity,
          validated: false,
        });
      });
      if (toAdd.length > 0) {
        await settingsApi.saveCustomRules([...existing, ...toAdd]);
        await qc.invalidateQueries({ queryKey: ["rules-legacy"] });
      }
      setMsg(t("settings.specGenAdded", { added: toAdd.length, skipped }));
      setProposals(null);
      setSelected(new Set());
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2 className="card-title">{t("settings.specGenTitle")}</h2>
      <div className="label">{t("settings.specGenIntro")}</div>

      <FileDropzone
        accept=".docx,.doc,.pdf,.txt,.md,.xml"
        multiple={false}
        disabled={busy}
        label={t("settings.chooseReference")}
        description={filename || t("settings.referenceFormats")}
        onFiles={(files) => void onPick(files[0] ?? null)}
      />
      {busy && !proposals && <div className="label">{t("settings.specGenAnalyzing")}</div>}

      {proposals && proposals.length > 0 && (
        <>
          <div className="label" style={{ marginTop: "0.5rem" }}>
            {t("settings.specGenProposed", { count: proposals.length })}
          </div>
          <table className="rules-table">
            <thead>
              <tr>
                <th />
                <th>{t("rules.vcLabel")}</th>
                <th>{t("rules.aiGuidelines")}</th>
                <th>{t("redacteur.filterSeverity")}</th>
              </tr>
            </thead>
            <tbody>
              {proposals.map((p, i) => (
                <tr key={i} style={selected.has(i) ? undefined : { opacity: 0.5 }}>
                  <td><input type="checkbox" checked={selected.has(i)} onChange={() => toggle(i)} /></td>
                  <td>{p.label}</td>
                  <td>{p.consigne}</td>
                  <td><span className={`badge ${severityClass(p.severity)}`}>{t(p.severity === "high" ? "redacteur.sevHigh" : p.severity === "medium" ? "redacteur.sevMedium" : "redacteur.sevLow")}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="button" className="btn primary" disabled={busy || selected.size === 0} onClick={addSelected}>
            {t("settings.specGenAddSelected", { count: selected.size })}
          </button>
        </>
      )}
      {msg && <div className="label" style={{ marginTop: "0.5rem" }}>{msg}</div>}
    </div>
  );
}
