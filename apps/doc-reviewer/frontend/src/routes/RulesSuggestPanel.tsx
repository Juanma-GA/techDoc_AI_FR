import { Plus, Upload, X } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiClientError } from "../lib/api";
import {
  useCreateRule,
  useSuggestRules,
  useSuggestRulesFromFiles,
  type RuleSuggestion,
} from "../hooks/useRules";

export function RulesSuggestPanel() {
  const { t } = useTranslation();
  const suggestDocs = useSuggestRules();
  const suggestFiles = useSuggestRulesFromFiles();
  const create = useCreateRule();
  const fileRef = useRef<HTMLInputElement>(null);

  const [picks, setPicks] = useState<Set<number>>(new Set());
  const [appliedMsg, setAppliedMsg] = useState<string | null>(null);

  // Affichage pilote par la derniere source utilisee (fichiers conformes OU
  // documents deja uploades).
  const suggest =
    suggestFiles.data || suggestFiles.isPending || suggestFiles.isError
      ? suggestFiles
      : suggestDocs;

  const runSuggest = (): void => {
    setAppliedMsg(null);
    setPicks(new Set());
    suggestFiles.reset();
    suggestDocs.mutate();
  };

  const runSuggestFromFiles = (files: File[]): void => {
    if (files.length === 0) return;
    setAppliedMsg(null);
    setPicks(new Set());
    suggestDocs.reset();
    suggestFiles.mutate(files);
  };

  const togglePick = (idx: number): void => {
    setPicks((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const applySelected = (): void => {
    const items = suggest.data?.suggestions ?? [];
    const chosen = [...picks].map((i) => items[i]).filter(Boolean) as RuleSuggestion[];
    if (chosen.length === 0) {
      setAppliedMsg(t("rules.suggest.appliedNone"));
      return;
    }
    Promise.all(
      chosen.map((s) =>
        create.mutateAsync({
          name: s.name,
          kind: s.kind,
          pattern: s.pattern,
          replacement: s.replacement,
          severity: s.severity,
          message: s.message,
          enabled: true,
        }),
      ),
    ).then(() => {
      setAppliedMsg(t("rules.suggest.applied", { count: chosen.length }));
      setPicks(new Set());
      suggestDocs.reset();
      suggestFiles.reset();
    });
  };

  const close = (): void => {
    suggestDocs.reset();
    suggestFiles.reset();
    setPicks(new Set());
    setAppliedMsg(null);
  };

  const errorCode =
    suggest.error instanceof ApiClientError ? suggest.error.code : null;
  const count = suggest.data?.suggestions.length ?? 0;
  const open = !!suggest.data || suggest.isPending || suggest.isError;

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={runSuggest}
            disabled={suggest.isPending}
            className="btn secondary"
          >
            {suggestDocs.isPending ? t("rules.suggest.loading") : t("rules.suggest.cta")}
          </button>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept=".pdf,.doc,.docx"
            style={{ display: "none" }}
            onChange={(e) => {
              runSuggestFromFiles(Array.from(e.target.files ?? []));
              if (fileRef.current) fileRef.current.value = "";
            }}
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={suggest.isPending}
            className="btn secondary"
            title={t("rules.suggest.fromFilesHint")}
          >
            <Upload size={14} />
            {suggestFiles.isPending ? t("rules.suggest.loading") : t("rules.suggest.fromFiles")}
          </button>
        </div>
        {appliedMsg ? <span className="success">{appliedMsg}</span> : null}
      </div>

      {open ? (
        <section className="card">
          <header className="row" style={{ justifyContent: "space-between" }}>
            <div className="card-title">{t("rules.suggest.title")}</div>
            <div className="row">
              {suggest.data ? (
                <span className="card-sub">
                  {t("rules.suggest.docsAnalyzed", {
                    count: suggest.data.documents_analyzed,
                  })}
                </span>
              ) : null}
              <button
                type="button"
                onClick={close}
                aria-label={t("rules.suggest.close")}
                className="btn ghost small"
              >
                <X size={14} />
              </button>
            </div>
          </header>

          {suggest.isPending ? (
            <p className="empty-state">{t("rules.suggest.loading")}</p>
          ) : suggest.isError ? (
            <p className="error">
              {errorCode && t(`errors.${errorCode}`, { defaultValue: "" })
                ? t(`errors.${errorCode}`)
                : (suggest.error as Error).message}
            </p>
          ) : count === 0 ? (
            <p className="empty-state">{t("rules.suggest.empty")}</p>
          ) : (
            <>
              <ul className="item-list">
                {suggest.data!.suggestions.map((s, idx) => (
                  <li
                    key={`${s.kind}-${s.pattern}-${idx}`}
                    className="item-row"
                  >
                    <input
                      id={`pick-${idx}`}
                      type="checkbox"
                      checked={picks.has(idx)}
                      onChange={() => togglePick(idx)}
                    />
                    <label htmlFor={`pick-${idx}`} className="item-main" style={{ cursor: "pointer" }}>
                      <div className="item-name">{s.name}</div>
                      <div className="item-meta">
                        {t(`rules.kind.${s.kind}`)} · /{s.pattern}/
                        {s.replacement ? ` → ${s.replacement}` : ""} · {s.severity}
                      </div>
                      {s.message ? (
                        <div className="item-meta">{s.message}</div>
                      ) : null}
                    </label>
                  </li>
                ))}
              </ul>
              <div className="row" style={{ justifyContent: "flex-end", marginTop: 12 }}>
                <button
                  type="button"
                  onClick={applySelected}
                  disabled={create.isPending || picks.size === 0}
                  className="btn primary"
                >
                  <Plus size={14} />
                  {t("rules.suggest.applySelected", { count: picks.size })}
                </button>
              </div>
            </>
          )}
        </section>
      ) : null}
    </>
  );
}
