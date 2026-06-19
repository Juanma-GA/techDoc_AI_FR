import { useQueryClient } from "@tanstack/react-query";
import { Lock, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageHeader } from "../components/PageHeader";
import {
  useCreateRule,
  useDeleteRule,
  usePatchRule,
  type RuleInput,
} from "../hooks/useRules";
import {
  useCreateStandard,
  useCreateVersion,
  useDeleteStandard,
  useDeleteVersion,
  useStandardVersionDetail,
  useStandards,
} from "../hooks/useStandards";
import type { Rule, Standard } from "../types/domain";

const CUSTOM_RULE_KINDS: Rule["kind"][] = [
  "term_replace",
  "regex_replace",
  "regex_flag",
  "field_required",
  "section_required",
  "step_pattern",
  "enum_value",
];

export function Standards(): JSX.Element {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const standards = useStandards();
  const createStd = useCreateStandard();
  const createVer = useCreateVersion();
  const deleteStd = useDeleteStandard();
  const deleteVer = useDeleteVersion();
  const createRule = useCreateRule();
  const patchRule = usePatchRule();
  const deleteRule = useDeleteRule();

  const items: Standard[] = standards.data ?? [];

  const [selectedStd, setSelectedStd] = useState<string | null>(null);
  const [selectedVer, setSelectedVer] = useState<string | null>(null);
  const [draftCode, setDraftCode] = useState("");
  const [draftLabel, setDraftLabel] = useState("");
  const [draftDescription, setDraftDescription] = useState("");
  const [draftVersion, setDraftVersion] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<Standard | null>(null);
  const [confirmDeleteRule, setConfirmDeleteRule] = useState<Rule | null>(null);
  const [ruleName, setRuleName] = useState("");
  const [ruleKind, setRuleKind] = useState<Rule["kind"]>("term_replace");
  const [ruleSeverity, setRuleSeverity] = useState<Rule["severity"]>("warning");
  const [rulePattern, setRulePattern] = useState("");
  const [ruleReplacement, setRuleReplacement] = useState("");
  const [ruleMessage, setRuleMessage] = useState("");

  const current = useMemo(
    () => items.find((s) => s.id === selectedStd) ?? items[0] ?? null,
    [items, selectedStd],
  );
  const versions = current?.versions ?? [];
  const activeVersion = useMemo(
    () => versions.find((v) => v.id === selectedVer) ?? versions[0] ?? null,
    [versions, selectedVer],
  );
  const detail = useStandardVersionDetail(
    current?.id ?? null,
    activeVersion?.id ?? null,
  );

  // Custom rules attached to the selected version live in the version detail
  // query (custom_rules). The rule hooks only invalidate ["rules"], so refresh
  // the detail query too after every write.
  const invalidateDetail = (): void => {
    void qc.invalidateQueries({ queryKey: ["standard-version"] });
  };

  const submitStandard = (): void => {
    if (!draftCode.trim() || !draftLabel.trim()) return;
    const description = draftDescription.trim();
    createStd.mutate(
      {
        code: draftCode.trim(),
        label: draftLabel.trim(),
        ...(description ? { description } : {}),
      },
      {
        onSuccess: () => {
          setDraftCode("");
          setDraftLabel("");
          setDraftDescription("");
        },
      },
    );
  };

  const submitVersion = (): void => {
    if (!current || current.builtin || !draftVersion.trim()) return;
    createVer.mutate(
      { standardId: current.id, label: draftVersion.trim() },
      { onSuccess: () => setDraftVersion("") },
    );
  };

  const resetRuleDraft = (): void => {
    setRuleName("");
    setRuleKind("term_replace");
    setRuleSeverity("warning");
    setRulePattern("");
    setRuleReplacement("");
    setRuleMessage("");
  };

  const submitRule = (): void => {
    if (!activeVersion || !ruleName.trim() || !rulePattern.trim()) return;
    const body: RuleInput = {
      name: ruleName.trim(),
      kind: ruleKind,
      pattern: rulePattern.trim(),
      replacement: ruleReplacement,
      severity: ruleSeverity,
      message: ruleMessage,
      enabled: true,
      standard_version_id: activeVersion.id,
    };
    createRule.mutate(body, {
      onSuccess: () => {
        resetRuleDraft();
        invalidateDetail();
      },
    });
  };

  const toggleRule = (rule: Rule): void => {
    patchRule.mutate(
      { id: rule.id, enabled: !rule.enabled },
      { onSuccess: invalidateDetail },
    );
  };

  return (
    <div>
      <PageHeader title={t("standards.title")} subtitle={t("standards.subtitle")} />

      <section
        className="grid-2"
        style={{ gridTemplateColumns: "260px 1fr", alignItems: "start" }}
      >
        <aside className="card">
          <h2 className="card-title">{t("standards.listTitle")}</h2>
          {standards.isLoading ? (
            <p className="empty-state">{t("common.loading")}</p>
          ) : (
            <ul className="item-list">
              {items.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedStd(s.id);
                      setSelectedVer(s.versions[0]?.id ?? null);
                    }}
                    className={[
                      "item-row clickable",
                      (current?.id ?? null) === s.id ? "active" : "",
                    ].join(" ")}
                  >
                    <span className="item-name label">{s.code}</span>
                    {s.builtin ? (
                      <Lock size={12} aria-label={t("standards.builtin")} />
                    ) : (
                      <button
                        type="button"
                        aria-label={t("common.delete")}
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmDelete(s);
                        }}
                        className="btn small danger"
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="card" style={{ marginTop: "1rem" }}>
            <h3 className="card-title">{t("standards.createCustom")}</h3>
            <div className="form">
              <input
                placeholder={t("standards.codePlaceholder")}
                value={draftCode}
                onChange={(e) => setDraftCode(e.target.value)}
                className="input mono"
              />
              <input
                placeholder={t("standards.labelPlaceholder")}
                value={draftLabel}
                onChange={(e) => setDraftLabel(e.target.value)}
                className="input"
              />
              <input
                placeholder={t("standards.descPlaceholder", {
                  defaultValue: "Description (optionnelle)",
                })}
                value={draftDescription}
                onChange={(e) => setDraftDescription(e.target.value)}
                className="input"
              />
              <button
                type="button"
                onClick={submitStandard}
                disabled={createStd.isPending || !draftCode || !draftLabel}
                className="btn small primary"
              >
                <Plus size={12} />
                {t("standards.create")}
              </button>
            </div>
          </div>
        </aside>

        <article className="card">
          {current ? (
            <>
              <header className="row">
                <div className="grow">
                  <h2 className="card-title">{current.label}</h2>
                  <p className="card-sub">{current.description}</p>
                </div>
                <span className="badge default">
                  {current.builtin ? t("standards.builtin") : t("standards.custom")}
                </span>
              </header>

              <div className="row">
                {versions.map((v) => (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => setSelectedVer(v.id)}
                    className={[
                      "btn small",
                      (activeVersion?.id ?? null) === v.id ? "primary" : "secondary",
                    ].join(" ")}
                  >
                    {v.label}
                    {!v.builtin ? ` (${t("standards.custom")})` : ""}
                  </button>
                ))}
                {!current.builtin ? (
                  <>
                    <input
                      placeholder={t("standards.versionPlaceholder")}
                      value={draftVersion}
                      onChange={(e) => setDraftVersion(e.target.value)}
                      className="input"
                    />
                    <button
                      type="button"
                      onClick={submitVersion}
                      disabled={createVer.isPending || !draftVersion}
                      className="btn small secondary"
                    >
                      <Plus size={12} />
                      {t("standards.addVersion")}
                    </button>
                  </>
                ) : null}
                {activeVersion && !activeVersion.builtin ? (
                  <button
                    type="button"
                    onClick={() =>
                      deleteVer.mutate({
                        standardId: current.id,
                        versionId: activeVersion.id,
                      })
                    }
                    className="btn small danger"
                  >
                    {t("standards.deleteVersion")}
                  </button>
                ) : null}
              </div>

              <section className="card">
                <h3 className="card-title">{t("standards.catalogTitle")}</h3>
                {detail.isLoading ? (
                  <p className="empty-state">{t("common.loading")}</p>
                ) : detail.data && detail.data.catalog.length > 0 ? (
                  <ul className="item-list">
                    {detail.data.catalog.map((c) => (
                      <li key={c.code} className="item-row">
                        <div className="item-main">
                          <p className="row">
                            <span className="item-name label grow">{c.code}</span>
                            <span className="badge default">{c.kind} · {c.severity}</span>
                          </p>
                          <p className="item-name">{c.title}</p>
                          <p className="item-meta">{c.description}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty-state">{t("standards.catalogEmpty")}</p>
                )}
              </section>

              <section className="card">
                <h3 className="card-title">
                  {t("rules.title")}
                  {detail.data ? ` · ${detail.data.custom_rules.length}` : ""}
                </h3>

                {detail.data && detail.data.custom_rules.length > 0 ? (
                  <ul className="item-list">
                    {detail.data.custom_rules.map((r) => (
                      <li key={r.id} className="item-row">
                        <div className="item-main">
                          <p className="item-name label">{r.name}</p>
                          <p className="item-meta">
                            {r.kind} · /{r.pattern}/ · {r.severity}
                          </p>
                        </div>
                        <label className="checkbox">
                          <input
                            type="checkbox"
                            checked={r.enabled}
                            onChange={() => toggleRule(r)}
                          />
                          {t("rules.form.enabled")}
                        </label>
                        <div className="item-actions">
                          <button
                            type="button"
                            aria-label={t("common.delete")}
                            onClick={() => setConfirmDeleteRule(r)}
                            className="btn small danger"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty-state">
                    {t("standards.customRulesEmpty", {
                      defaultValue: "Aucune règle custom sur cette version",
                    })}
                  </p>
                )}

                {activeVersion ? (
                  <div className="form" style={{ marginTop: "1rem" }}>
                    <h4 className="field-label">
                      {t("standards.addCustomRule", {
                        defaultValue: "Ajouter une règle custom à cette version",
                      })}
                    </h4>
                    <div className="row">
                      <input
                        placeholder={t("rules.form.name")}
                        value={ruleName}
                        onChange={(e) => setRuleName(e.target.value)}
                        className="input grow"
                        style={{ minWidth: "10rem" }}
                      />
                      <select
                        value={ruleKind}
                        onChange={(e) => setRuleKind(e.target.value as Rule["kind"])}
                        className="input"
                      >
                        {CUSTOM_RULE_KINDS.map((k) => (
                          <option key={k} value={k}>
                            {t(`rules.kind.${k}`)}
                          </option>
                        ))}
                      </select>
                      <select
                        value={ruleSeverity}
                        onChange={(e) => setRuleSeverity(e.target.value as Rule["severity"])}
                        className="input"
                      >
                        <option value="info">info</option>
                        <option value="warning">warning</option>
                        <option value="error">error</option>
                      </select>
                    </div>
                    <div className="row">
                      <input
                        placeholder={t("rules.form.pattern")}
                        value={rulePattern}
                        onChange={(e) => setRulePattern(e.target.value)}
                        className="input mono grow"
                        style={{ minWidth: "10rem" }}
                      />
                      <input
                        placeholder={t("rules.form.replacement")}
                        value={ruleReplacement}
                        onChange={(e) => setRuleReplacement(e.target.value)}
                        className="input mono grow"
                        style={{ minWidth: "10rem" }}
                      />
                    </div>
                    <input
                      placeholder={t("rules.form.message")}
                      value={ruleMessage}
                      onChange={(e) => setRuleMessage(e.target.value)}
                      className="input"
                    />
                    <button
                      type="button"
                      onClick={submitRule}
                      disabled={createRule.isPending || !ruleName.trim() || !rulePattern.trim()}
                      className="btn small primary"
                      style={{ width: "fit-content" }}
                    >
                      <Plus size={12} />
                      {t("rules.create")}
                    </button>
                  </div>
                ) : (
                  <p className="empty-state">{t("standards.noVersion")}</p>
                )}
              </section>
            </>
          ) : (
            <p className="empty-state">{t("standards.selectStandard")}</p>
          )}
        </article>
      </section>

      <ConfirmDialog
        open={confirmDelete !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmDelete(null);
        }}
        title={t("standards.confirmDelete")}
        description={confirmDelete?.label}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => {
          if (confirmDelete) deleteStd.mutate(confirmDelete.id);
          setConfirmDelete(null);
        }}
      />

      <ConfirmDialog
        open={confirmDeleteRule !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmDeleteRule(null);
        }}
        title={t("common.delete")}
        description={confirmDeleteRule?.name}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => {
          if (confirmDeleteRule) {
            deleteRule.mutate(confirmDeleteRule.id, { onSuccess: invalidateDetail });
          }
          setConfirmDeleteRule(null);
        }}
      />
    </div>
  );
}
