import { Plus, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiClientError } from "../lib/api";
import {
  useCreateRule,
  useSuggestRules,
  type RuleSuggestion,
} from "../hooks/useRules";

export function RulesSuggestPanel() {
  const { t } = useTranslation();
  const suggest = useSuggestRules();
  const create = useCreateRule();

  const [picks, setPicks] = useState<Set<number>>(new Set());
  const [appliedMsg, setAppliedMsg] = useState<string | null>(null);

  const runSuggest = (): void => {
    setAppliedMsg(null);
    setPicks(new Set());
    suggest.mutate();
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
      suggest.reset();
    });
  };

  const close = (): void => {
    suggest.reset();
    setPicks(new Set());
    setAppliedMsg(null);
  };

  const errorCode =
    suggest.error instanceof ApiClientError ? suggest.error.code : null;
  const count = suggest.data?.suggestions.length ?? 0;
  const open = !!suggest.data || suggest.isPending || suggest.isError;

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <button
          type="button"
          onClick={runSuggest}
          disabled={suggest.isPending}
          className="btn secondary"
        >
          <Sparkles size={14} />
          {suggest.isPending ? t("rules.suggest.loading") : t("rules.suggest.cta")}
        </button>
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
