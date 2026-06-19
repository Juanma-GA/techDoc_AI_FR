import { Check, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageHeader } from "../components/PageHeader";
import { StandardPicker } from "../components/upload/StandardPicker";
import {
  useCreateRule,
  useDeleteRule,
  usePatchRule,
  useRules,
  type RuleInput,
} from "../hooks/useRules";
import { useStandards } from "../hooks/useStandards";
import type { Rule } from "../types/domain";
import { RulesSuggestPanel } from "./RulesSuggestPanel";

const EMPTY: RuleInput = {
  name: "",
  kind: "term_replace",
  pattern: "",
  replacement: "",
  severity: "warning",
  message: "",
  enabled: true,
  standard_version_id: null,
};

export function Rules() {
  const { t } = useTranslation();
  const standards = useStandards();
  const [filterStdId, setFilterStdId] = useState<string | null>(null);
  const [filterVerId, setFilterVerId] = useState<string | null>(null);
  const rules = useRules({
    standardVersionId: filterVerId,
    includeTransverse: true,
  });
  const create = useCreateRule();
  const patch = usePatchRule();
  const remove = useDeleteRule();

  const [draft, setDraft] = useState<RuleInput>(EMPTY);
  const [confirmDelete, setConfirmDelete] = useState<Rule | null>(null);

  const versionLabelById = useMemo(() => {
    const map = new Map<string, string>();
    (standards.data ?? []).forEach((s) =>
      s.versions.forEach((v) => map.set(v.id, `${s.code} ${v.label}`)),
    );
    return map;
  }, [standards.data]);

  const submit = (): void => {
    if (!draft.name || !draft.pattern) return;
    create.mutate(draft, { onSuccess: () => setDraft(EMPTY) });
  };

  return (
    <div className="pr">
      <PageHeader title={t("rules.title")} subtitle={t("rules.subtitle")} />

      <RulesSuggestPanel />

      <div className="card">
        <div className="card-title">{t("rules.filterTitle")}</div>
        <StandardPicker
          standardId={filterStdId}
          versionId={filterVerId}
          onChange={(stdId, verId) => {
            setFilterStdId(stdId);
            setFilterVerId(verId);
          }}
        />
      </div>

      <section className="grid-2">
        <div className="grow">
          {rules.isLoading ? (
            <p className="empty-state">{t("common.loading")}</p>
          ) : rules.data && rules.data.length > 0 ? (
            <ul className="item-list">
              {rules.data.map((r) => (
                <RuleRow
                  key={r.id}
                  rule={r}
                  scopeLabel={
                    r.standard_version_id
                      ? versionLabelById.get(r.standard_version_id) ?? r.standard_version_id
                      : t("standards.transverse")
                  }
                  onSave={(changes) => patch.mutate({ id: r.id, ...changes })}
                  saving={patch.isPending}
                  onDelete={() => setConfirmDelete(r)}
                />
              ))}
            </ul>
          ) : (
            <p className="empty-state">{t("common.empty")}</p>
          )}
        </div>

        <aside className="card form">
          <div className="card-title">{t("rules.create")}</div>
          <Field label={t("rules.form.name")}>
            <input
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              className="input"
            />
          </Field>
          <Field label={t("rules.form.kind")}>
            <select
              value={draft.kind}
              onChange={(e) =>
                setDraft({ ...draft, kind: e.target.value as RuleInput["kind"] })
              }
              className="input"
            >
              <option value="term_replace">{t("rules.kind.term_replace")}</option>
              <option value="regex_replace">{t("rules.kind.regex_replace")}</option>
              <option value="regex_flag">{t("rules.kind.regex_flag")}</option>
              <option value="field_required">{t("rules.kind.field_required")}</option>
              <option value="section_required">{t("rules.kind.section_required")}</option>
              <option value="step_pattern">{t("rules.kind.step_pattern")}</option>
              <option value="enum_value">{t("rules.kind.enum_value")}</option>
            </select>
          </Field>
          <Field label={t("rules.form.scope")}>
            <select
              value={draft.standard_version_id ?? ""}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  standard_version_id: e.target.value === "" ? null : e.target.value,
                })
              }
              className="input"
            >
              <option value="">{t("standards.transverse")}</option>
              {(standards.data ?? []).flatMap((s) =>
                s.versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    {s.code} {v.label}
                  </option>
                )),
              )}
            </select>
          </Field>
          <Field label={t("rules.form.pattern")}>
            <input
              value={draft.pattern}
              onChange={(e) => setDraft({ ...draft, pattern: e.target.value })}
              className="input mono"
            />
          </Field>
          {draft.kind !== "regex_flag" && draft.kind !== "step_pattern" && draft.kind !== "field_required" && draft.kind !== "section_required" ? (
            <Field label={t("rules.form.replacement")}>
              <input
                value={draft.replacement}
                onChange={(e) => setDraft({ ...draft, replacement: e.target.value })}
                className="input mono"
              />
            </Field>
          ) : null}
          <Field label={t("rules.form.severity")}>
            <select
              value={draft.severity}
              onChange={(e) =>
                setDraft({ ...draft, severity: e.target.value as RuleInput["severity"] })
              }
              className="input"
            >
              <option value="info">info</option>
              <option value="warning">warning</option>
              <option value="error">error</option>
            </select>
          </Field>
          <Field label={t("rules.form.message")}>
            <input
              value={draft.message}
              onChange={(e) => setDraft({ ...draft, message: e.target.value })}
              className="input"
            />
          </Field>
          <button
            type="button"
            onClick={submit}
            disabled={create.isPending || !draft.name || !draft.pattern}
            className="btn primary"
          >
            <Plus size={14} />
            {t("rules.create")}
          </button>
          {create.isError ? (
            <p className="error">{(create.error as Error).message}</p>
          ) : null}
        </aside>
      </section>

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

type RuleRowChanges = Pick<
  RuleInput,
  "name" | "kind" | "pattern" | "severity" | "enabled"
>;

function RuleRow({
  rule,
  scopeLabel,
  onSave,
  saving,
  onDelete,
}: {
  rule: Rule;
  scopeLabel: string;
  onSave: (changes: Partial<RuleRowChanges>) => void;
  saving: boolean;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const [edit, setEdit] = useState<RuleRowChanges>({
    name: rule.name,
    kind: rule.kind,
    pattern: rule.pattern,
    severity: rule.severity,
    enabled: rule.enabled,
  });

  const dirty: Partial<RuleRowChanges> = {};
  if (edit.name !== rule.name) dirty.name = edit.name;
  if (edit.kind !== rule.kind) dirty.kind = edit.kind;
  if (edit.pattern !== rule.pattern) dirty.pattern = edit.pattern;
  if (edit.severity !== rule.severity) dirty.severity = edit.severity;
  if (edit.enabled !== rule.enabled) dirty.enabled = edit.enabled;
  const isDirty = Object.keys(dirty).length > 0;

  return (
    <li className="item-row">
      <div className="row">
        <input
          aria-label={t("rules.form.name")}
          value={edit.name}
          onChange={(e) => setEdit({ ...edit, name: e.target.value })}
          className="input mono grow"
        />
        <select
          aria-label={t("rules.form.kind")}
          value={edit.kind}
          onChange={(e) =>
            setEdit({ ...edit, kind: e.target.value as RuleInput["kind"] })
          }
          className="input"
        >
          <option value="term_replace">{t("rules.kind.term_replace")}</option>
          <option value="regex_replace">{t("rules.kind.regex_replace")}</option>
          <option value="regex_flag">{t("rules.kind.regex_flag")}</option>
          <option value="field_required">{t("rules.kind.field_required")}</option>
          <option value="section_required">{t("rules.kind.section_required")}</option>
          <option value="step_pattern">{t("rules.kind.step_pattern")}</option>
          <option value="enum_value">{t("rules.kind.enum_value")}</option>
        </select>
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
      </div>
      <div className="row">
        <input
          aria-label={t("rules.form.pattern")}
          value={edit.pattern}
          onChange={(e) => setEdit({ ...edit, pattern: e.target.value })}
          className="input mono grow"
        />
        <label className="checkbox">
          <input
            type="checkbox"
            checked={edit.enabled}
            onChange={(e) => setEdit({ ...edit, enabled: e.target.checked })}
          />
          {t("rules.form.enabled")}
        </label>
        <span className="label">{scopeLabel}</span>
        <div className="item-actions">
          <button
            type="button"
            onClick={() => onSave(dirty)}
            disabled={!isDirty || saving}
            className="btn primary small"
          >
            <Check size={12} />
            {t("common.save")}
          </button>
          <button
            type="button"
            aria-label={t("common.delete")}
            onClick={onDelete}
            className="btn ghost small"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </li>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}
