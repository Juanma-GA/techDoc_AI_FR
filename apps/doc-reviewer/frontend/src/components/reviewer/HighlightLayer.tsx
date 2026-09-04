import { bboxToPercentRect, hasValidBbox } from "../../lib/bbox";
import type { Suggestion } from "../../types/domain";

type Props = {
  suggestions: Suggestion[];
  selectedSuggestionId: string | null;
  onSuggestionClick: (id: string) => void;
};

/**
 * Calque de surlignage superpose a la page PDF rendue. Les overlays sont
 * positionnes en POURCENTAGES (cf. bboxToPercentRect) sur un conteneur
 * `absolute; inset:0` qui couvre exactement la page — donc l'alignement est
 * correct quel que soit le zoom / dpr, comme dans l'ancien preview.html.
 */
export function HighlightLayer({
  suggestions,
  selectedSuggestionId,
  onSuggestionClick,
}: Props) {
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
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
      {sorted.map((s) => {
        if (!hasValidBbox(s.bbox)) return null;
        const rect = bboxToPercentRect(s.bbox);
        if (!rect || rect.width <= 0 || rect.height <= 0) return null;
        const isSelected = s.id === selectedSuggestionId;
        const k = s.original_text || s.rule_code;
        const total = groupTotals.get(k) ?? 1;
        const cur = (groupCursor.get(k) ?? 0) + 1;
        groupCursor.set(k, cur);
        const counter = total > 1 ? ` (${cur}/${total})` : "";
        const detectionOnly = !s.proposed_text || s.proposed_text === s.original_text;
        const label = `${s.rule_code}${counter} · ${s.message || ""}`;
        const proposedLine = detectionOnly
          ? "Détection · pas de correction automatique"
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
              "pdf-highlight",
              s.severity === "error" ? "error" : "",
              isSelected ? "active" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            style={{
              pointerEvents: "auto",
              left: `${rect.left}%`,
              top: `${rect.top}%`,
              width: `${rect.width}%`,
              height: `${rect.height}%`,
            }}
          />
        );
      })}
    </div>
  );
}
