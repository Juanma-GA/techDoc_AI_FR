import { ChevronDown, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useFiltersStore } from "../../stores/filtersStore";
import { localizedSuggestionMessage } from "../../lib/suggestionText";
import type { SourceKind, Suggestion } from "../../types/domain";
import { SuggestionItem } from "./SuggestionItem";

type Props = {
  suggestions: Suggestion[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onSaveEdit: (id: string, newProposed: string) => void;
  onSaveFeedback: (id: string, feedback: string) => void;
  onUnreject: (id: string) => void;
  onUndo: (id: string) => void;
};

/** Visual identity: every occurrence reported by one rule belongs together. */
function occurrenceKey(s: Suggestion): string {
  return s.rule_code;
}

const SOURCE_KINDS: SourceKind[] = ["norme", "checklist", "regle", "transverse"];

export function SuggestionPanel({
  suggestions,
  selectedId,
  onSelect,
  onAccept,
  onReject,
  onSaveEdit,
  onSaveFeedback,
  onUnreject,
  onUndo,
}: Props) {
  const { t } = useTranslation();
  const showUnits = useFiltersStore((s) => s.showUnitConversions);
  const hideAccepted = useFiltersStore((s) => s.hideAccepted);
  const sourceKindFilter = useFiltersStore((s) => s.sourceKindFilter);
  const setSourceKindFilter = useFiltersStore((s) => s.setSourceKindFilter);
  const ruleCodeFilter = useFiltersStore((s) => s.ruleCodeFilter);
  const setRuleCodeFilter = useFiltersStore((s) => s.setRuleCodeFilter);
  const containerRef = useRef<HTMLDivElement>(null);
  // Groupes replies par defaut ; un groupe explicitement deplie par
  // l'utilisateur reste ouvert tant qu'il ne le referme pas.
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const lastSelectedId = useRef<string | null>(null);
  const pendingScrollId = useRef<string | null>(null);

  const ruleCodes = useMemo(() => {
    const set = new Set(suggestions.map((s) => s.rule_code));
    return Array.from(set).sort();
  }, [suggestions]);

  const visible = useMemo(() => {
    return suggestions.filter((s) => {
      if (!showUnits && s.rule_kind === "units") return false;
      if (hideAccepted && (s.status === "applied" || s.status === "rejected")) return false;
      if (sourceKindFilter && s.source_kind !== sourceKindFilter) return false;
      if (ruleCodeFilter && s.rule_code !== ruleCodeFilter) return false;
      return true;
    });
  }, [suggestions, showUnits, hideAccepted, sourceKindFilter, ruleCodeFilter]);

  // Bucket the *visible* list by rule, preserving first-seen order, so the
  // panel shows one collapsible row per rule instead of every occurrence.
  const buckets = useMemo(() => {
    const order: string[] = [];
    const map = new Map<string, Suggestion[]>();
    for (const s of visible) {
      const key = occurrenceKey(s);
      const arr = map.get(key);
      if (arr) arr.push(s);
      else {
        map.set(key, [s]);
        order.push(key);
      }
    }
    return order.map((key) => ({ key, items: map.get(key)! }));
  }, [visible]);

  function toggleExpanded(key: string): void {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // A new selection from the PDF may need its rule bucket opened once. The
  // selected id is tracked separately so collapsing that bucket manually
  // never reopens it on the next render.
  useEffect(() => {
    if (!selectedId) {
      lastSelectedId.current = null;
      pendingScrollId.current = null;
      return;
    }
    if (lastSelectedId.current === selectedId) return;
    lastSelectedId.current = selectedId;
    const bucket = buckets.find((b) => b.items.some((x) => x.id === selectedId));
    if (bucket && bucket.items.length > 1 && !expanded.has(bucket.key)) {
      pendingScrollId.current = selectedId;
      setExpanded((prev) => new Set(prev).add(bucket.key));
      return;
    }
    pendingScrollId.current = selectedId;
  }, [selectedId, buckets, expanded]);

  // Scroll only for a newly selected occurrence, never as a side effect of a
  // manual expand/collapse click.
  useEffect(() => {
    const id = pendingScrollId.current;
    if (!id || !containerRef.current) return;
    const bucket = buckets.find((b) => b.items.some((x) => x.id === id));
    if (bucket && bucket.items.length > 1 && !expanded.has(bucket.key)) return;
    const el = containerRef.current.querySelector<HTMLElement>(
      `[data-suggestion-id="${id}"]`,
    );
    if (!el) return;
    pendingScrollId.current = null;
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [buckets, expanded]);

  return (
    <aside className="reviewer-panel">
      <header className="reviewer-panel-head">
        <h2 className="card-title" style={{ margin: 0 }}>
          {t("reviewer.panel.title")}
        </h2>
        <span className="label">{visible.length}</span>
      </header>

      <div className="row" style={{ gap: 8, padding: "0 12px 8px", flexWrap: "wrap" }}>
        <select
          className="input small"
          value={sourceKindFilter ?? ""}
          onChange={(e) => setSourceKindFilter((e.target.value || null) as SourceKind | null)}
          aria-label={t("reviewer.panel.filters.source")}
        >
          <option value="">{t("reviewer.panel.filters.allSources")}</option>
          {SOURCE_KINDS.map((k) => (
            <option key={k} value={k}>
              {t(`source.${k}`)}
            </option>
          ))}
        </select>
        <select
          className="input small"
          value={ruleCodeFilter ?? ""}
          onChange={(e) => setRuleCodeFilter(e.target.value || null)}
          aria-label={t("reviewer.panel.filters.rule")}
        >
          <option value="">{t("reviewer.panel.filters.allRules")}</option>
          {ruleCodes.map((code) => (
            <option key={code} value={code}>
              {code}
            </option>
          ))}
        </select>
      </div>

      <div ref={containerRef} className="reviewer-panel-body">
        {visible.length === 0 ? (
          <p className="empty-state">{t("reviewer.panel.empty")}</p>
        ) : (
          buckets.map(({ key, items }) => {
            const isCollapsible = items.length > 1;
            const isExpanded = !isCollapsible || expanded.has(key);
            const head = items[0]!;
            const headMessage = localizedSuggestionMessage(head, t);
            return (
              <div
                key={key}
                className={isExpanded && isCollapsible ? "suggestion-bucket expanded" : "suggestion-bucket"}
              >
                {isCollapsible ? (
                  <div className="suggestion-bucket-head">
                    <button
                      type="button"
                      className="suggestion-bucket-toggle"
                      onClick={() => toggleExpanded(key)}
                      title={t("reviewer.panel.group.toggle")}
                      aria-expanded={isExpanded}
                    >
                      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      <span className="suggestion-loc">{head.rule_code}</span>
                      <span className="suggestion-msg" style={{ flex: 1, textAlign: "left" }}>
                        {headMessage}
                      </span>
                    </button>
                    <span className="badge default">
                      {t("reviewer.panel.group.occurrences", { count: items.length })}
                    </span>
                  </div>
                ) : null}
                {isExpanded
                  ? items.map((s) => {
                      return (
                        <SuggestionItem
                          key={s.id}
                          suggestion={s}
                          isSelected={s.id === selectedId}
                          onSelect={() => onSelect(s.id)}
                          onAccept={() => onAccept(s.id)}
                          onReject={() => onReject(s.id)}
                          onSaveEdit={(text) => onSaveEdit(s.id, text)}
                          onSaveFeedback={(fb) => onSaveFeedback(s.id, fb)}
                          onUnreject={() => onUnreject(s.id)}
                          onUndo={() => onUndo(s.id)}
                        />
                      );
                    })
                  : null}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
