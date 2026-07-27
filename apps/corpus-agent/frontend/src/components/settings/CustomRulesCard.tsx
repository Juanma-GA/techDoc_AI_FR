import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useDoubleClickConfirm } from "../../hooks/useDoubleClickConfirm";
import { settingsApi } from "../../lib/api";
import type { CustomRule, RulesLegacyOut } from "../../lib/types";

const SEVERITIES = ["low", "medium", "high"];

function DeleteButton({ onDelete }: { onDelete: () => void }) {
  const { t } = useTranslation();
  const { armed, handleClick } = useDoubleClickConfirm(onDelete);
  return (
    <button type="button" className={`btn small ${armed ? "danger" : "ghost"}`} onClick={handleClick}>
      {armed ? t("common.confirm") : t("common.delete")}
    </button>
  );
}

/** Une regle personnalisee editable inline (libelle / consigne / severite). */
function RuleRow({
  rule,
  onChange,
  onDelete,
  onValidate,
}: {
  rule: CustomRule;
  onChange: (patch: Partial<CustomRule>) => void;
  onDelete: () => void;
  onValidate?: () => void;
}) {
  const { t } = useTranslation();
  const enabled = rule.enabled !== false;
  return (
    <tr style={enabled ? undefined : { opacity: 0.55 }}>
      <td>
        <label className="switch" title={enabled ? t("settings.ruleEnabledOn") : t("settings.ruleEnabledOff")}>
          <input type="checkbox" checked={enabled} onChange={(e) => onChange({ enabled: e.target.checked })} />
          <span className="track" />
        </label>
      </td>
      <td><input className="input" value={rule.label} onChange={(e) => onChange({ label: e.target.value })} /></td>
      <td><textarea value={rule.consigne} onChange={(e) => onChange({ consigne: e.target.value })} /></td>
      <td>
        <select className="input" value={rule.severity ?? "medium"} onChange={(e) => onChange({ severity: e.target.value })}>
          {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </td>
      <td className="row" style={{ gap: "0.35rem" }}>
        {onValidate && (
          <button type="button" className="btn small primary" onClick={onValidate}>{t("settings.validate")}</button>
        )}
        <DeleteButton onDelete={onDelete} />
      </td>
    </tr>
  );
}

/**
 * Gestion editable des regles personnalisees + file de validation. Les regles
 * importees (validated=false) attendent ici avant de participer a l'analyse.
 */
export function CustomRulesCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const query = useQuery<RulesLegacyOut>({ queryKey: ["rules-legacy"], queryFn: settingsApi.rulesLegacy });
  const [draft, setDraft] = useState<CustomRule[] | null>(null);

  const stored: CustomRule[] = query.data?.rules.regles_personnalisees ?? query.data?.rules.custom_rules ?? [];
  const rules = draft ?? stored;
  const dirty = draft !== null;

  const save = useMutation({
    mutationFn: (next: CustomRule[]) => settingsApi.saveCustomRules(next),
    onSuccess: async () => {
      setDraft(null);
      await qc.invalidateQueries({ queryKey: ["rules-legacy"] });
    },
  });
  const validateAll = useMutation({
    mutationFn: () => settingsApi.validateAllRules(),
    onSuccess: async () => {
      setDraft(null);
      await qc.invalidateQueries({ queryKey: ["rules-legacy"] });
    },
  });

  function patch(index: number, p: Partial<CustomRule>) {
    setDraft(rules.map((r, i) => (i === index ? { ...r, ...p } : r)));
  }
  function remove(index: number) {
    setDraft(rules.filter((_, i) => i !== index));
  }

  const pending = rules.filter((r) => r.validated === false);
  const active = rules.filter((r) => r.validated !== false);

  function renderTable(list: CustomRule[], markPending: boolean) {
    return (
      <table className="rules-table">
        <thead>
          <tr>
            <th>{t("settings.ruleActive")}</th>
            <th>{t("rules.vcLabel")}</th>
            <th>{t("rules.aiGuidelines")}</th>
            <th>{t("redacteur.filterSeverity")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {list.map((r) => {
            const index = rules.indexOf(r);
            return (
              <RuleRow
                key={r.id ?? index}
                rule={r}
                onChange={(p) => patch(index, p)}
                onDelete={() => remove(index)}
                onValidate={markPending ? () => patch(index, { validated: true }) : undefined}
              />
            );
          })}
        </tbody>
      </table>
    );
  }

  if (query.isLoading) return <div className="card"><div className="empty-state">{t("common.loading")}</div></div>;

  return (
    <div className="card">
      <h2 className="card-title">{t("settings.customRulesTitle")}</h2>
      <div className="label">{t("settings.customRulesIntro")}</div>
      <div className="label">{t("settings.refColumnPlaceholder")}</div>

      {pending.length > 0 && (
        <>
          <div className="rules-section-title">{t("settings.pendingQueue", { count: pending.length })}</div>
          <div className="banner warn">{t("settings.pendingHint")}</div>
          {renderTable(pending, true)}
          <button type="button" className="btn secondary" disabled={validateAll.isPending} onClick={() => validateAll.mutate()}>
            {t("settings.validateAll")}
          </button>
        </>
      )}

      <div className="rules-section-title">{t("settings.activeRules", { count: active.length })}</div>
      {active.length === 0 ? (
        <div className="empty-state" style={{ fontStyle: "italic" }}>{t("settings.noCustomRules")}</div>
      ) : (
        renderTable(active, false)
      )}

      <div className="row" style={{ gap: "0.5rem", marginTop: "0.75rem" }}>
        <button type="button" className="btn primary" disabled={!dirty || save.isPending} onClick={() => save.mutate(rules)}>
          {save.isPending ? t("common.loading") : t("common.save")}
        </button>
        {dirty && (
          <button type="button" className="btn ghost" onClick={() => setDraft(null)}>{t("common.cancel")}</button>
        )}
      </div>
    </div>
  );
}
