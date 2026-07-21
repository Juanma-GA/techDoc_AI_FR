import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  templatesApi,
  type ColumnSpec,
  type ColumnType,
  type TemplateDto,
} from "../lib/api";

const TYPE_LABEL: Record<ColumnType, string> = {
  text: "templates.typeText",
  number: "templates.typeNumber",
  date: "templates.typeDate",
  bool: "templates.typeBool",
};
const TYPES = Object.keys(TYPE_LABEL) as ColumnType[];

function emptyColumn(): ColumnSpec {
  return { key: "", label: "", type: "text", rule: "" };
}

export function Templates() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [columns, setColumns] = useState<ColumnSpec[]>([emptyColumn()]);
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [armed, setArmed] = useState<string | null>(null);

  const listQuery = useQuery<TemplateDto[]>({
    queryKey: ["templates"],
    queryFn: templatesApi.list,
  });

  const reset = () => {
    setEditing(null);
    setName("");
    setDescription("");
    setColumns([emptyColumn()]);
  };

  const startEdit = (tpl: TemplateDto) => {
    setEditing(tpl.id);
    setName(tpl.name);
    setDescription(tpl.description);
    setColumns(tpl.columns.length ? tpl.columns : [emptyColumn()]);
    setFeedback(null);
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const cleaned = columns
        .filter((c) => c.key.trim())
        .map((c) => ({ ...c, key: c.key.trim(), label: c.label.trim(), rule: c.rule.trim() }));
      const body = { name: name.trim(), description: description.trim(), columns: cleaned };
      return editing ? templatesApi.update(editing, body) : templatesApi.create(body);
    },
    onSuccess: () => {
      setFeedback({ kind: "ok", text: t("templates.saved") });
      reset();
      void qc.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: (e: Error) => setFeedback({ kind: "error", text: e.message }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => templatesApi.remove(id),
    onSuccess: () => {
      if (editing) reset();
      void qc.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: (e: Error) => setFeedback({ kind: "error", text: e.message }),
  });

  const submit = () => {
    setFeedback(null);
    if (!name.trim()) {
      setFeedback({ kind: "error", text: t("templates.needName") });
      return;
    }
    if (!columns.some((c) => c.key.trim())) {
      setFeedback({ kind: "error", text: t("templates.needColumns") });
      return;
    }
    saveMutation.mutate();
  };

  const setCol = (i: number, patch: Partial<ColumnSpec>) =>
    setColumns((cols) => cols.map((c, j) => (j === i ? { ...c, ...patch } : c)));

  const confirmDelete = (id: string) => {
    if (armed === id) {
      setArmed(null);
      deleteMutation.mutate(id);
    } else {
      setArmed(id);
      setTimeout(() => setArmed((a) => (a === id ? null : a)), 3000);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>{t("routes.templates.title")}</h1>
        <p>{t("routes.templates.sub")}</p>
      </div>

      <div className="card">
        <h2 className="card-title">{t("templates.listTitle")}</h2>
        {listQuery.data && listQuery.data.length ? (
          <div className="file-list">
            {listQuery.data.map((tpl) => (
              <div className="file-row" key={tpl.id}>
                <div className="grow">
                  <div className="file-name">{tpl.name}</div>
                  <div className="file-meta">
                    {t("templates.colCount", { n: tpl.columns.length })}
                    {tpl.description ? ` — ${tpl.description}` : ""}
                  </div>
                </div>
                <button type="button" className="btn ghost" onClick={() => startEdit(tpl)}>
                  {t("templates.edit")}
                </button>
                <button type="button" className="btn danger" onClick={() => confirmDelete(tpl.id)}>
                  {armed === tpl.id ? t("templates.confirmDelete") : t("templates.delete")}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">{t("templates.empty")}</div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">
          {editing ? t("templates.editTitle") : t("templates.createTitle")}
        </h2>
        <div className="form">
          <label>
            <div className="label">{t("templates.name")}</div>
            <input
              className="input"
              value={name}
              placeholder={t("templates.namePlaceholder")}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            <div className="label">{t("templates.description")}</div>
            <input
              className="input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>

          <div className="label">{t("templates.columns")}</div>
          {columns.map((c, i) => (
            <div className="row" key={i} style={{ alignItems: "flex-start" }}>
              <input
                className="input"
                style={{ maxWidth: 140 }}
                placeholder={t("templates.colKey")}
                value={c.key}
                onChange={(e) => setCol(i, { key: e.target.value })}
              />
              <input
                className="input"
                style={{ maxWidth: 160 }}
                placeholder={t("templates.colLabel")}
                value={c.label}
                onChange={(e) => setCol(i, { label: e.target.value })}
              />
              <select
                className="input"
                style={{ maxWidth: 130 }}
                value={c.type}
                onChange={(e) => setCol(i, { type: e.target.value as ColumnType })}
              >
                {TYPES.map((ty) => (
                  <option key={ty} value={ty}>
                    {t(TYPE_LABEL[ty])}
                  </option>
                ))}
              </select>
              <input
                className="input grow"
                placeholder={t("templates.colRulePlaceholder")}
                value={c.rule}
                onChange={(e) => setCol(i, { rule: e.target.value })}
              />
              <button
                type="button"
                className="btn ghost"
                onClick={() => setColumns((cols) => cols.filter((_, j) => j !== i))}
              >
                {t("templates.removeColumn")}
              </button>
            </div>
          ))}
          <div className="row">
            <button
              type="button"
              className="btn secondary"
              onClick={() => setColumns((cols) => [...cols, emptyColumn()])}
            >
              {t("templates.addColumn")}
            </button>
          </div>

          <div className="row">
            <button
              type="button"
              className="btn primary"
              disabled={saveMutation.isPending}
              onClick={submit}
            >
              {t("templates.save")}
            </button>
            {editing ? (
              <button type="button" className="btn ghost" onClick={reset}>
                {t("templates.cancel")}
              </button>
            ) : null}
          </div>
          {feedback ? (
            <div className={feedback.kind === "ok" ? "success" : "error"}>{feedback.text}</div>
          ) : null}
        </div>
      </div>
    </>
  );
}
