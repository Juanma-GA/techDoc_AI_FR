import { ChevronDown, ChevronRight, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ConfirmDialog } from "../ConfirmDialog";
import { useClientRules } from "../../hooks/useClientConfig";
import { useFiltersStore } from "../../stores/filtersStore";
import { localizedRuleCode } from "../../lib/suggestionText";
import type { Suggestion } from "../../types/domain";
import { SuggestionItem } from "./SuggestionItem";

type Props = {
  suggestions: Suggestion[];
  selectedId: string | null;
  focusRequest?: number;
  onSelect: (id: string) => void;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onRejectAll: (ids: string[]) => void;
  onSaveEdit: (id: string, newProposed: string) => void;
  onSaveFeedback: (id: string, feedback: string) => void;
  onUnreject: (id: string) => void;
  onUndo: (id: string) => void;
};

/** Visual identity: every occurrence reported by one rule belongs together. */
function occurrenceKey(s: Suggestion): string {
  return s.rule_code;
}

export function SuggestionPanel({
  suggestions,
  selectedId,
  focusRequest = 0,
  onSelect,
  onAccept,
  onReject,
  onRejectAll,
  onSaveEdit,
  onSaveFeedback,
  onUnreject,
  onUndo,
}: Props) {
  const { t } = useTranslation();
  const clientRules = useClientRules();
  const showUnits = useFiltersStore((s) => s.showUnitConversions);
  const hideAccepted = useFiltersStore((s) => s.hideAccepted);
  const ruleCodeFilter = useFiltersStore((s) => s.ruleCodeFilter);
  const setRuleCodeFilter = useFiltersStore((s) => s.setRuleCodeFilter);
  const containerRef = useRef<HTMLDivElement>(null);
  // Groupes replies par defaut ; un groupe explicitement deplie par
  // l'utilisateur reste ouvert tant qu'il ne le referme pas.
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const [pendingBulkReject, setPendingBulkReject] = useState<{
    ids: string[];
    count: number;
  } | null>(null);
  const lastSelectedId = useRef<string | null>(null);
  const lastFocusRequest = useRef(focusRequest);
  const pendingScrollId = useRef<string | null>(null);

  const ruleCodes = useMemo(() => {
    const set = new Set(suggestions.map((s) => s.rule_code));
    return Array.from(set).sort();
  }, [suggestions]);

  const ruleNumberByCode = useMemo(
    () => new Map((clientRules.data ?? []).map((rule) => [rule.code, rule.rule_number])),
    [clientRules.data],
  );

  const visible = useMemo(() => {
    return suggestions.filter((s) => {
      if (!showUnits && s.rule_kind === "units") return false;
      if (hideAccepted && (s.status === "applied" || s.status === "rejected")) return false;
      if (ruleCodeFilter && s.rule_code !== ruleCodeFilter) return false;
      return true;
    });
  }, [suggestions, showUnits, hideAccepted, ruleCodeFilter]);

  // Bucket visible suggestions by rule and sort the groups by numeric rule number.
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
    return order
      .map((key, index) => ({ key, items: map.get(key)!, index }))
      .sort((left, right) => {
        const leftNumber = ruleNumberByCode.get(left.items[0]!.rule_code);
        const rightNumber = ruleNumberByCode.get(right.items[0]!.rule_code);
        if (leftNumber == null) {
          return rightNumber == null ? left.index - right.index : 1;
        }
        if (rightNumber == null) return -1;
        return leftNumber - rightNumber || left.index - right.index;
      })
      .map(({ key, items }) => ({ key, items }));
  }, [visible, ruleNumberByCode]);

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
    if (lastSelectedId.current === selectedId && lastFocusRequest.current === focusRequest) return;
    lastSelectedId.current = selectedId;
    lastFocusRequest.current = focusRequest;
    const bucket = buckets.find((b) => b.items.some((x) => x.id === selectedId));
    if (bucket && bucket.items.length > 1 && !expanded.has(bucket.key)) {
      pendingScrollId.current = selectedId;
      setExpanded((prev) => new Set(prev).add(bucket.key));
      return;
    }
    pendingScrollId.current = selectedId;
  }, [selectedId, focusRequest, buckets, expanded]);

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
  }, [selectedId, focusRequest, buckets, expanded]);

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
          value={ruleCodeFilter ?? ""}
          onChange={(e) => setRuleCodeFilter(e.target.value || null)}
          aria-label={t("reviewer.panel.filters.rule")}
        >
          <option value="">{t("reviewer.panel.filters.allRules")}</option>
          {ruleCodes.map((code) => (
            <option key={code} value={code}>
              {localizedRuleCode(code, t)}
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
            const ruleNumber = ruleNumberByCode.get(items[0]!.rule_code);
            const ruleHref = `/rules?rule=${encodeURIComponent(items[0]!.rule_code)}`;
            const rejectableItems = items.filter(
              (item) => item.status !== "applied" && item.status !== "rejected",
            );
            const head = items[0]!;
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
                      <span className="suggestion-loc" title={localizedRuleCode(head.rule_code, t)}>
                        {localizedRuleCode(head.rule_code, t)}
                      </span>
                    </button>
                    {ruleNumber != null ? (
                      <Link
                        className="suggestion-bucket-rule-number"
                        to={ruleHref}
                        title={t("rules.client.openRule", { number: ruleNumber })}
                        aria-label={t("rules.client.openRule", { number: ruleNumber })}
                        onClick={(event) => event.stopPropagation()}
                      >
                        #{ruleNumber}
                      </Link>
                    ) : null}
                    <span className="suggestion-bucket-count">
                      {t("reviewer.panel.group.count", { count: items.length })}
                    </span>
                    {rejectableItems.length > 1 ? (
                      <button
                        type="button"
                        className="suggestion-bucket-reject"
                        title={t("reviewer.suggestion.rejectAll")}
                        aria-label={t("reviewer.suggestion.rejectAll")}
                        onClick={() =>
                          setPendingBulkReject({
                            ids: rejectableItems.map((item) => item.id),
                            count: rejectableItems.length,
                          })
                        }
                      >
                        <X size={14} aria-hidden="true" />
                      </button>
                    ) : null}
                  </div>
                ) : null}
                {isExpanded
                  ? items.map((s) => {
                      return (
                        <SuggestionItem
                          key={s.id}
                          suggestion={s}
                          ruleNumber={ruleNumberByCode.get(s.rule_code) ?? null}
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
      <ConfirmDialog
        open={pendingBulkReject !== null}
        onOpenChange={(open) => {
          if (!open) setPendingBulkReject(null);
        }}
        title={t("reviewer.bulkReject.title", { count: pendingBulkReject?.count ?? 0 })}
        confirmLabel={t("reviewer.bulkReject.confirm")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => {
          if (pendingBulkReject) onRejectAll(pendingBulkReject.ids);
        }}
      />
    </aside>
  );
}
