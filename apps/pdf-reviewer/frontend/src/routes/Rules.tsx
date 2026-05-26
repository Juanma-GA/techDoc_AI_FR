import { Plus, Trash2 } from "lucide-react";
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
    <div className="flex flex-col">
      <PageHeader title={t("rules.title")} subtitle={t("rules.subtitle")} />

      <RulesSuggestPanel />

      <section className="flex flex-col gap-3 px-6 pt-2">
        <h2 className="font-display text-sm text-fg-dim">{t("rules.filterTitle")}</h2>
        <StandardPicker
          standardId={filterStdId}
          versionId={filterVerId}
          onChange={(stdId, verId) => {
            setFilterStdId(stdId);
            setFilterVerId(verId);
          }}
        />
      </section>

      <section className="grid grid-cols-1 gap-6 p-6 lg:grid-cols-[1fr_360px]">
        <div className="flex flex-col gap-2">
          {rules.isLoading ? (
            <p className="text-fg-dim">{t("common.loading")}</p>
          ) : rules.data && rules.data.length > 0 ? (
            <ul className="flex flex-col gap-2">
              {rules.data.map((r) => (
                <li
                  key={r.id}
                  className="flex items-center justify-between gap-3 rounded-sm border bg-card p-3"
                >
                  <div className="min-w-0">
                    <p className="font-mono text-fg">{r.name}</p>
                    <p className="font-mono text-xs text-fg-dim">
                      {r.kind} · /{r.pattern}/ ·{" "}
                      {r.standard_version_id
                        ? versionLabelById.get(r.standard_version_id) ?? r.standard_version_id
                        : t("standards.transverse")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="flex items-center gap-1 text-xs text-fg-dim">
                      <input
                        type="checkbox"
                        checked={r.enabled}
                        onChange={(e) =>
                          patch.mutate({ id: r.id, enabled: e.target.checked })
                        }
                      />
                      {t("rules.form.enabled")}
                    </label>
                    <button
                      type="button"
                      aria-label={t("common.delete")}
                      onClick={() => setConfirmDelete(r)}
                      className="rounded-sm border p-1 text-fg-dim hover:bg-danger/10 hover:text-danger"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-fg-dim">{t("common.empty")}</p>
          )}
        </div>

        <aside className="flex flex-col gap-3 rounded-lg border bg-card p-4">
          <h2 className="font-display text-fg">{t("rules.create")}</h2>
          <Field label={t("rules.form.name")}>
            <input
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              className="w-full rounded-sm border bg-bg-2 px-2 py-1 text-fg"
            />
          </Field>
          <Field label={t("rules.form.kind")}>
            <select
              value={draft.kind}
              onChange={(e) =>
                setDraft({ ...draft, kind: e.target.value as RuleInput["kind"] })
              }
              className="w-full rounded-sm border bg-bg-2 px-2 py-1 text-fg"
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
              className="w-full rounded-sm border bg-bg-2 px-2 py-1 text-fg"
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
              className="w-full rounded-sm border bg-bg-2 px-2 py-1 font-mono text-fg"
            />
          </Field>
          {draft.kind !== "regex_flag" && draft.kind !== "step_pattern" && draft.kind !== "field_required" && draft.kind !== "section_required" ? (
            <Field label={t("rules.form.replacement")}>
              <input
                value={draft.replacement}
                onChange={(e) => setDraft({ ...draft, replacement: e.target.value })}
                className="w-full rounded-sm border bg-bg-2 px-2 py-1 font-mono text-fg"
              />
            </Field>
          ) : null}
          <Field label={t("rules.form.severity")}>
            <select
              value={draft.severity}
              onChange={(e) =>
                setDraft({ ...draft, severity: e.target.value as RuleInput["severity"] })
              }
              className="w-full rounded-sm border bg-bg-2 px-2 py-1 text-fg"
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
              className="w-full rounded-sm border bg-bg-2 px-2 py-1 text-fg"
            />
          </Field>
          <button
            type="button"
            onClick={submit}
            disabled={create.isPending || !draft.name || !draft.pattern}
            className="inline-flex items-center justify-center gap-1 rounded-sm bg-brand px-3 py-1.5 text-fg hover:bg-brand-blue-light disabled:opacity-50"
          >
            <Plus size={14} />
            {t("rules.create")}
          </button>
          {create.isError ? (
            <p className="text-xs text-danger">{(create.error as Error).message}</p>
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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-fg-dim">
      <span className="label">{label}</span>
      {children}
    </label>
  );
}
