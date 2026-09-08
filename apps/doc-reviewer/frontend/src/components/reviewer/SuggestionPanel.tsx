import { ChevronDown, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useFiltersStore } from "../../stores/filtersStore";
import { useRuleResults } from "../../hooks/useSuggestions";
import type { SourceKind, Suggestion } from "../../types/domain";
import { SuggestionItem } from "./SuggestionItem";

type Props = {
  documentId: string;
  suggestions: Suggestion[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onSaveEdit: (id: string, newProposed: string) => void;
  onSaveFeedback: (id: string, feedback: string) => void;
  onUnreject: (id: string) => void;
  onApplyGroup: (id: string) => void;
  onUndo: (id: string) => void;
};

/** Identity of a "same error": rule + detected text + proposed fix. */
function groupKey(s: Suggestion): string {
  return `${s.rule_code}${s.original_text}${s.proposed_text}`;
}

/** Broader identity used to bucket occurrences of the same anomaly (rule +
 * detected text) under one collapsible entry in the panel, independent of
 * the exact proposed fix (which can differ slightly per occurrence). */
function occurrenceKey(s: Suggestion): string {
  return `${s.rule_code}\u0000${s.original_text}`;
}

const PENDING_STATUSES = new Set(["open", "accepted", "edited"]);
const SOURCE_KINDS: SourceKind[] = ["norme", "checklist", "regle", "transverse"];

export function SuggestionPanel({
  documentId,
  suggestions,
  selectedId,
  onSelect,
  onAccept,
  onReject,
  onSaveEdit,
  onSaveFeedback,
  onUnreject,
  onApplyGroup,
  onUndo,
}: Props) {
  const { t } = useTranslation();
  const ruleResults = useRuleResults(documentId);
  const showUnits = useFiltersStore((s) => s.showUnitConversions);
  const hideAccepted = useFiltersStore((s) => s.hideAccepted);
  const sourceKindFilter = useFiltersStore((s) => s.sourceKindFilter);
  const setSourceKindFilter = useFiltersStore((s) => s.setSourceKindFilter);
  const ruleCodeFilter = useFiltersStore((s) => s.ruleCodeFilter);
  const setRuleCodeFilter = useFiltersStore((s) => s.setRuleCodeFilter);
  const containerRef = useRef<HTMLDivElement>(null);
  // Groupes replies par defaut (cle = occurrenceKey) ; un groupe explicitement
  // deplie par l'utilisateur reste ouvert tant qu'il ne le referme pas.
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());

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

  // Map each group key to its still-pending occurrences so an item can
  // tell when the same anomaly recurs across several pages.
  const groups = useMemo(() => {
    const map = new Map<string, Suggestion[]>();
    for (const s of suggestions) {
      if (!PENDING_STATUSES.has(s.status)) continue;
      if (!s.proposed_text || s.proposed_text === s.original_text) continue;
      const key = groupKey(s);
      const arr = map.get(key);
      if (arr) arr.push(s);
      else map.set(key, [s]);
    }
    return map;
  }, [suggestions]);

  // Bucket the *visible* list by occurrence identity, preserving first-seen
  // order, so the panel shows one collapsible row per distinct anomaly
  // instead of every occurrence flattened out.
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

  // Scroll selected item into view when picked from the PDF. A selection
  // hiding inside a collapsed bucket is expanded first so it can be reached.
  useEffect(() => {
    if (!selectedId || !containerRef.current) return;
    const bucket = buckets.find((b) => b.items.some((x) => x.id === selectedId));
    if (bucket && bucket.items.length > 1 && !expanded.has(bucket.key)) {
      setExpanded((prev) => new Set(prev).add(bucket.key));
      return;
    }
    const el = containerRef.current.querySelector<HTMLElement>(
      `[data-suggestion-id="${selectedId}"]`,
    );
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [selectedId, buckets, expanded]);

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
        {(ruleResults.data?.length ?? 0) > 0 ? (
          <section style={{ padding: "0 12px 10px" }}>
            <div className="rules-section-title">{t("reviewer.compiled.title")}</div>
            {ruleResults.data?.map((result) => {
              const location = result.evidence?.location;
              const locationLabel = location?.type === "bbox"
                ? `bbox ${location.bbox.join(", ")}`
                : location?.type === "target_id" ? location.target_id : "";
              return (
                <div key={result.rule_id} className="banner" data-rule-status={result.status} style={{ marginBottom: 6 }}>
                  <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                    <span className={`badge ${result.status === "PASS" ? "success" : "default"}`}>{result.status}</span>
                    <strong>{result.rule_id}</strong>
                    {result.evidence ? <span className="label">{t("reviewer.compiled.location", { page: result.evidence.page, location: locationLabel })}</span> : null}
                  </div>
                  {result.evidence ? (
                    <div className="label">{t("reviewer.compiled.values", {
                      observed: result.evidence.observed_value ?? "—",
                      expected: result.evidence.expected_value ?? "—",
                    })}</div>
                  ) : null}
                </div>
              );
            })}
          </section>
        ) : null}
        {visible.length === 0 ? (
          <p className="empty-state">{t("reviewer.panel.empty")}</p>
        ) : (
          buckets.map(({ key, items }) => {
            const isCollapsible = items.length > 1;
            const isExpanded = !isCollapsible || expanded.has(key);
            const head = items[0]!;
            return (
              <div key={key} className="suggestion-bucket">
                {isCollapsible ? (
                  <button
                    type="button"
                    className="suggestion-bucket-head"
                    onClick={() => toggleExpanded(key)}
                    title={t("reviewer.panel.group.toggle")}
                  >
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    <span className="suggestion-loc">{head.rule_code}</span>
                    <span className="suggestion-msg" style={{ flex: 1, textAlign: "left" }}>
                      {head.message}
                    </span>
                    <span className="badge default">
                      {t("reviewer.panel.group.occurrences", { count: items.length })}
                    </span>
                  </button>
                ) : null}
                {isExpanded
                  ? items.map((s) => {
                      const siblings = groups.get(groupKey(s)) ?? [];
                      const groupPages = new Set(siblings.map((x) => x.page)).size;
                      return (
                        <SuggestionItem
                          key={s.id}
                          suggestion={s}
                          isSelected={s.id === selectedId}
                          groupPages={groupPages}
                          groupOccurrences={siblings.length}
                          onSelect={() => onSelect(s.id)}
                          onAccept={() => onAccept(s.id)}
                          onReject={() => onReject(s.id)}
                          onSaveEdit={(text) => onSaveEdit(s.id, text)}
                          onSaveFeedback={(fb) => onSaveFeedback(s.id, fb)}
                          onUnreject={() => onUnreject(s.id)}
                          onApplyGroup={() => onApplyGroup(s.id)}
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
