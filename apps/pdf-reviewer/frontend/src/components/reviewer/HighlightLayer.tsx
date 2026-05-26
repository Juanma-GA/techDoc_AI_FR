import { bboxToCssRect, hasValidBbox, type ViewportLike } from "../../lib/bbox";
import type { Suggestion } from "../../types/domain";

type Props = {
  viewport: ViewportLike | null;
  dpr: number;
  suggestions: Suggestion[];
  selectedSuggestionId: string | null;
  onSuggestionClick: (id: string) => void;
};

const KIND_CLASSES: Record<string, string> = {
  units: "bg-accent-teal/20 ring-1 ring-accent-teal/60 hover:bg-accent-teal/30",
  s1000d: "bg-warning/20 ring-1 ring-warning/60 hover:bg-warning/30",
  custom: "bg-info/20 ring-1 ring-info/60 hover:bg-info/30",
};

const SEVERITY_FALLBACK: Record<string, string> = {
  error: "bg-danger/20 ring-1 ring-danger/60 hover:bg-danger/30",
  warning: "bg-warning/20 ring-1 ring-warning/60 hover:bg-warning/30",
  info: "bg-info/20 ring-1 ring-info/60 hover:bg-info/30",
};

export function HighlightLayer({
  viewport,
  dpr,
  suggestions,
  selectedSuggestionId,
  onSuggestionClick,
}: Props) {
  if (!viewport) return null;

  const sorted = [...suggestions].sort((a, b) => {
    if (a.span_index !== b.span_index) return a.span_index - b.span_index;
    return a.id.localeCompare(b.id);
  });

  // Group counters to label duplicates « 1/2 », « 2/2 » in the tooltip
  // so two occurrences of the same `original_text` are unambiguous.
  const groupTotals = new Map<string, number>();
  for (const s of sorted) {
    const k = s.original_text || s.rule_code;
    groupTotals.set(k, (groupTotals.get(k) ?? 0) + 1);
  }
  const groupCursor = new Map<string, number>();

  return (
    <div className="pointer-events-none absolute inset-0">
      {sorted.map((s) => {
        if (!hasValidBbox(s.bbox)) return null;
        const rect = bboxToCssRect(s.bbox, viewport, dpr);
        if (rect.width <= 0 || rect.height <= 0) return null;
        const baseClass =
          KIND_CLASSES[s.rule_kind] ?? SEVERITY_FALLBACK[s.severity] ?? KIND_CLASSES.custom;
        const isSelected = s.id === selectedSuggestionId;
        const k = s.original_text || s.rule_code;
        const total = groupTotals.get(k) ?? 1;
        const cur = (groupCursor.get(k) ?? 0) + 1;
        groupCursor.set(k, cur);
        const counter = total > 1 ? ` (${cur}/${total})` : "";
        const detectionOnly = !s.proposed_text || s.proposed_text === s.original_text;
        const label = `${s.rule_code}${counter} — ${s.message || ""}`;
        const proposedLine = detectionOnly
          ? "Détection — pas de correction automatique"
          : `Proposé : ${s.proposed_text}`;
        const tooltip =
          `${s.rule_code}${counter} · ${s.severity}\n` +
          `${s.message || ""}\n` +
          `Original : ${s.original_text}\n` +
          `${proposedLine}`;
        return (
          <button
            type="button"
            key={s.id}
            data-testid="highlight"
            data-suggestion-id={s.id}
            onClick={() => onSuggestionClick(s.id)}
            aria-label={label}
            title={tooltip}
            className={[
              "pointer-events-auto absolute cursor-pointer rounded-sm transition-colors",
              baseClass,
              isSelected ? "ring-2 ring-brand-blue-light" : "",
            ].join(" ")}
            style={{
              left: rect.left,
              top: rect.top,
              width: Math.max(rect.width, 4),
              height: Math.max(rect.height, 8),
            }}
          />
        );
      })}
    </div>
  );
}
