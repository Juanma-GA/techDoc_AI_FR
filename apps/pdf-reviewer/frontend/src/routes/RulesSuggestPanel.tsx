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
      <div className="flex items-center justify-between gap-3 px-6 pt-4">
        <button
          type="button"
          onClick={runSuggest}
          disabled={suggest.isPending}
          className="inline-flex items-center gap-2 rounded-sm border border-brand/40 bg-brand/10 px-3 py-1.5 text-sm text-brand hover:bg-brand/20 disabled:opacity-50"
        >
          <Sparkles size={14} />
          {suggest.isPending ? t("rules.suggest.loading") : t("rules.suggest.cta")}
        </button>
        {appliedMsg ? <span className="text-xs text-success">{appliedMsg}</span> : null}
      </div>

      {open ? (
        <section className="mx-6 mt-3 rounded-lg border bg-card p-4">
          <header className="mb-3 flex items-center justify-between gap-2">
            <h2 className="font-display text-fg">{t("rules.suggest.title")}</h2>
            <div className="flex items-center gap-3">
              {suggest.data ? (
                <span className="text-xs text-fg-dim">
                  {t("rules.suggest.docsAnalyzed", {
                    count: suggest.data.documents_analyzed,
                  })}
                </span>
              ) : null}
              <button
                type="button"
                onClick={close}
                aria-label={t("rules.suggest.close")}
                className="rounded-sm border p-1 text-fg-dim hover:bg-bg-2"
              >
                <X size={14} />
              </button>
            </div>
          </header>

          {suggest.isPending ? (
            <p className="text-fg-dim">{t("rules.suggest.loading")}</p>
          ) : suggest.isError ? (
            <p className="text-xs text-danger">
              {errorCode && t(`errors.${errorCode}`, { defaultValue: "" })
                ? t(`errors.${errorCode}`)
                : (suggest.error as Error).message}
            </p>
          ) : count === 0 ? (
            <p className="text-fg-dim">{t("rules.suggest.empty")}</p>
          ) : (
            <>
              <ul className="flex flex-col gap-2">
                {suggest.data!.suggestions.map((s, idx) => (
                  <li
                    key={`${s.kind}-${s.pattern}-${idx}`}
                    className="flex items-start gap-3 rounded-sm border bg-bg-2 p-3"
                  >
                    <input
                      id={`pick-${idx}`}
                      type="checkbox"
                      checked={picks.has(idx)}
                      onChange={() => togglePick(idx)}
                      className="mt-1"
                    />
                    <label htmlFor={`pick-${idx}`} className="flex-1 cursor-pointer">
                      <div className="font-mono text-sm text-fg">{s.name}</div>
                      <div className="font-mono text-xs text-fg-dim">
                        {t(`rules.kind.${s.kind}`)} · /{s.pattern}/
                        {s.replacement ? ` → ${s.replacement}` : ""} · {s.severity}
                      </div>
                      {s.message ? (
                        <div className="mt-1 text-xs text-fg-dim">{s.message}</div>
                      ) : null}
                    </label>
                  </li>
                ))}
              </ul>
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={applySelected}
                  disabled={create.isPending || picks.size === 0}
                  className="inline-flex items-center gap-1 rounded-sm bg-brand px-3 py-1.5 text-fg hover:bg-brand-blue-light disabled:opacity-50"
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
