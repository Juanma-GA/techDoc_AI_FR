import { Check, CheckCheck, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { ChecklistImportCard } from "./ChecklistImportCard";
import { ConfirmDialog } from "../components/ConfirmDialog";
import {
  useDeleteRule,
  useCompiledRules,
  usePatchCompiledRule,
  usePatchRule,
  useRules,
  useValidateAllRules,
  type RuleInput,
} from "../hooks/useRules";
import { useStandards, useToggleCatalogRule } from "../hooks/useStandards";
import { useFiltersStore } from "../stores/filtersStore";
import type { Rule } from "../types/domain";
import { RulesSuggestPanel } from "./RulesSuggestPanel";

export function Rules() {
  const { t } = useTranslation();
  const standards = useStandards();
  const rules = useRules();
  const activeStandardVersionIds = useFiltersStore((s) => s.activeStandardVersionIds);
  const compiledRules = useCompiledRules(activeStandardVersionIds);
  const patchCompiled = usePatchCompiledRule();
  const patch = usePatchRule();
  const remove = useDeleteRule();
  const validateAll = useValidateAllRules();
  const toggleCatalogRule = useToggleCatalogRule();

  const [confirmDelete, setConfirmDelete] = useState<Rule | null>(null);

  const versionLabelById = useMemo(() => {
    const map = new Map<string, string>();
    (standards.data ?? []).forEach((s) =>
      s.versions.forEach((v) => map.set(v.id, `${s.code} ${v.label}`)),
    );
    return map;
  }, [standards.data]);

  return (
    <div className="card">
      <h2 className="card-title">{t("rules.title")}</h2>
      <p className="card-sub">{t("rules.subtitle")}</p>

      <ChecklistImportCard />

      <RulesSuggestPanel />

      <div className="rules-section-title">
        {t("rules.compiled.title")} · {compiledRules.data?.length ?? 0}
      </div>
      {activeStandardVersionIds.length === 0 ? (
        <p className="banner warn">{t("rules.compiled.noActiveStandard")}</p>
      ) : (compiledRules.data?.length ?? 0) > 0 ? (
        <div style={{ overflowX: "auto" }}>
          <table className="rules-table">
            <thead>
              <tr>
                <th>{t("rules.form.enabled")}</th>
                <th>{t("rules.compiled.status")}</th>
                <th>{t("rules.form.name")}</th>
                <th>{t("rules.compiled.detail")}</th>
                <th>{t("rules.form.scope")}</th>
              </tr>
            </thead>
            <tbody>
              {compiledRules.data?.map((rule) => (
                <tr key={rule.id} style={rule.active ? undefined : { opacity: 0.7 }}>
                  <td>
                    {rule.source === "standard_rule" && rule.standard_id && rule.standard_version_id ? (
                      <label
                        className="switch"
                        title={rule.active ? t("rules.disable") : t("rules.enable")}
                      >
                        <input
                          type="checkbox"
                          checked={rule.active}
                          onChange={(event) =>
                            toggleCatalogRule.mutate({
                              standardId: rule.standard_id as string,
                              versionId: rule.standard_version_id as string,
                              code: rule.id,
                              enabled: event.target.checked,
                            })
                          }
                          disabled={toggleCatalogRule.isPending}
                        />
                        <span className="track" />
                      </label>
                    ) : rule.source === "user_checklist" ? (
                      <label
                        className="switch"
                        title={rule.active ? t("rules.disable") : t("rules.enable")}
                      >
                        <input
                          type="checkbox"
                          checked={rule.active}
                          onChange={(event) =>
                            patchCompiled.mutate({ id: rule.id, active: event.target.checked })
                          }
                          disabled={patchCompiled.isPending}
                        />
                        <span className="track" />
                      </label>
                    ) : (
                      <span className="badge success">{t("rules.compiled.standardActive")}</span>
                    )}
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        rule.execution === "deterministic" || rule.execution === "semantic"
                          ? "success"
                          : "default"
                      }`}
                    >
                      {t(`rules.compiled.${rule.execution}`)}
                    </span>
                    <span className="label" style={{ marginLeft: 6 }}>
                      {rule.severity}
                    </span>
                  </td>
                  <td>{rule.topic}</td>
                  <td>
                    {rule.detail ?? t("rules.compiled.activeImmediately")}
                  </td>
                  <td><span className="label">{rule.origin_ref ?? t("standards.transverse")}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div>
        {rules.isLoading ? (
          <p className="empty-state">{t("common.loading")}</p>
        ) : rules.data && rules.data.length > 0 ? (
          (() => {
            const all = rules.data ?? [];
            const pending = all.filter((r) => !r.enabled);
            const active = all.filter((r) => r.enabled);
            const scopeOf = (r: Rule): string =>
              r.standard_version_id
                ? versionLabelById.get(r.standard_version_id) ?? r.standard_version_id
                : t("standards.transverse");
            const renderTable = (list: Rule[]) => (
              <div style={{ overflowX: "auto" }}>
                <table className="rules-table">
                  <thead>
                    <tr>
                      <th>{t("rules.form.enabled")}</th>
                      <th>{t("rules.form.name")}</th>
                      <th>{t("rules.form.message")}</th>
                      <th>{t("rules.form.severity")}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((r) => (
                      <RuleRow
                        key={r.id}
                        rule={r}
                        scopeLabel={scopeOf(r)}
                        onSave={(changes) => patch.mutate({ id: r.id, ...changes })}
                        onToggle={() => patch.mutate({ id: r.id, enabled: !r.enabled })}
                        saving={patch.isPending}
                        onDelete={() => setConfirmDelete(r)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            );
            return (
              <>
                {pending.length > 0 ? (
                  <>
                    <div
                      className="row"
                      style={{ alignItems: "center", gap: 10, flexWrap: "wrap" }}
                    >
                      <div className="rules-section-title" style={{ margin: 0 }}>
                        {t("rules.pending")} · {pending.length}
                      </div>
                      <button
                        type="button"
                        className="btn secondary small"
                        disabled={validateAll.isPending}
                        onClick={() => validateAll.mutate()}
                      >
                        <CheckCheck size={14} />
                        {t("rules.import.validateAll")}
                      </button>
                    </div>
                    <p className="banner warn">{t("rules.pendingHint")}</p>
                    {renderTable(pending)}
                  </>
                ) : null}
                <div className="rules-section-title">
                  {t("rules.active")} · {active.length}
                </div>
                {active.length > 0 ? (
                  renderTable(active)
                ) : (
                  <p className="empty-state">{t("rules.activeEmpty")}</p>
                )}
              </>
            );
          })()
        ) : (
          <p className="empty-state">{t("common.empty")}</p>
        )}
      </div>

      <ConfirmDialog
        open={confirmDelete !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmDelete(null);
        }}
        title={t("common.delete")}
        description={confirmDelete?.name}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => {
          if (confirmDelete) remove.mutate(confirmDelete.id);
          setConfirmDelete(null);
        }}
      />
    </div>
  );
}

type RuleRowChanges = Pick<RuleInput, "name" | "message" | "severity">;

/** Ligne de tableau editable inline (toggle switch + nom / message / severite),
 *  design aligne sur la CustomRulesCard de corpus-agent. */
function RuleRow({
  rule,
  scopeLabel,
  onSave,
  onToggle,
  saving,
  onDelete,
}: {
  rule: Rule;
  scopeLabel: string;
  onSave: (changes: Partial<RuleRowChanges>) => void;
  onToggle: () => void;
  saving: boolean;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const [edit, setEdit] = useState<RuleRowChanges>({
    name: rule.name,
    message: rule.message,
    severity: rule.severity,
  });

  const dirty: Partial<RuleRowChanges> = {};
  if (edit.name !== rule.name) dirty.name = edit.name;
  if (edit.message !== rule.message) dirty.message = edit.message;
  if (edit.severity !== rule.severity) dirty.severity = edit.severity;
  const isDirty = Object.keys(dirty).length > 0;

  return (
    <tr style={rule.enabled ? undefined : { opacity: 0.55 }}>
      <td>
        <label
          className="switch"
          title={rule.enabled ? t("rules.disable") : t("rules.enable")}
        >
          <input type="checkbox" checked={rule.enabled} onChange={onToggle} disabled={saving} />
          <span className="track" />
        </label>
      </td>
      <td style={{ minWidth: 180 }}>
        <input
          aria-label={t("rules.form.name")}
          value={edit.name}
          onChange={(e) => setEdit({ ...edit, name: e.target.value })}
          className="input"
        />
        <div className="row" style={{ gap: 4, marginTop: 4, flexWrap: "wrap" }}>
          <span className="badge default">{t(`rules.kind.${rule.kind}`, rule.kind)}</span>
          <span className="label">{scopeLabel}</span>
        </div>
      </td>
      <td style={{ minWidth: 220 }}>
        <textarea
          aria-label={t("rules.form.message")}
          value={edit.message}
          onChange={(e) => setEdit({ ...edit, message: e.target.value })}
        />
      </td>
      <td style={{ minWidth: 110 }}>
        <select
          aria-label={t("rules.form.severity")}
          value={edit.severity}
          onChange={(e) =>
            setEdit({ ...edit, severity: e.target.value as RuleInput["severity"] })
          }
          className="input"
        >
          <option value="info">info</option>
          <option value="warning">warning</option>
          <option value="error">error</option>
        </select>
      </td>
      <td>
        <div className="row" style={{ gap: 4 }}>
          {isDirty ? (
            <button
              type="button"
              onClick={() => onSave(dirty)}
              disabled={saving}
              className="btn primary small"
            >
              <Check size={12} />
              {t("common.save")}
            </button>
          ) : null}
          <button
            type="button"
            aria-label={t("common.delete")}
            onClick={onDelete}
            className="btn ghost small"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </td>
    </tr>
  );
}
