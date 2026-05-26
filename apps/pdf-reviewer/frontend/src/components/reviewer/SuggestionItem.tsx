import { Check, Layers, Pencil, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { DiffInline } from "../DiffInline";
import { SeverityBadge } from "../SeverityBadge";
import { UnitChip } from "../UnitChip";
import type { Suggestion } from "../../types/domain";

type Props = {
  suggestion: Suggestion;
  isSelected: boolean;
  /** Number of distinct pages where the exact same anomaly recurs. */
  groupPages: number;
  /** Total still-pending occurrences of the same anomaly. */
  groupOccurrences: number;
  onSelect: () => void;
  onAccept: () => void;
  onReject: () => void;
  onSaveEdit: (newProposedText: string) => void;
  onApplyGroup: () => void;
};

export function SuggestionItem({
  suggestion,
  isSelected,
  groupPages,
  groupOccurrences,
  onSelect,
  onAccept,
  onReject,
  onSaveEdit,
  onApplyGroup,
}: Props) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(suggestion.proposed_text);

  const isApplied = suggestion.status === "applied";
  const isRejected = suggestion.status === "rejected";
  // Surface the grouped action only when the anomaly truly spans pages.
  const isMultiPage = !isApplied && !isRejected && !editing && groupPages > 1;

  return (
    <article
      data-testid="suggestion-item"
      data-suggestion-id={suggestion.id}
      onClick={onSelect}
      className={[
        "rounded-sm border bg-card p-3 text-sm transition-colors",
        isSelected ? "border-bright bg-card-hover" : "hover:bg-card-hover",
      ].join(" ")}
    >
      <header className="mb-2 flex flex-wrap items-center gap-2">
        <SeverityBadge severity={suggestion.severity} />
        {suggestion.rule_kind === "units" ? <UnitChip /> : null}
        <span className="font-mono text-[0.65rem] uppercase tracking-wider text-fg-muted">
          p.{suggestion.page} · {suggestion.rule_code}
        </span>
        {isMultiPage ? (
          <span
            className="inline-flex items-center gap-1 rounded-sm bg-brand/15 px-2 py-0.5 text-[0.65rem] uppercase tracking-wider text-brand-blue-light"
            title={t("reviewer.suggestion.multiPageHint", { pages: groupPages })}
          >
            <Layers size={11} />
            {t("reviewer.suggestion.multiPageBadge", { pages: groupPages })}
          </span>
        ) : null}
        {isApplied ? (
          <span className="ml-auto rounded-sm bg-success/15 px-2 py-0.5 text-[0.65rem] uppercase tracking-wider text-success">
            {t("reviewer.suggestion.applied")}
          </span>
        ) : null}
        {isRejected ? (
          <span className="ml-auto rounded-sm bg-fg-muted/15 px-2 py-0.5 text-[0.65rem] uppercase tracking-wider text-fg-dim">
            {t("reviewer.suggestion.rejected")}
          </span>
        ) : null}
      </header>

      <p className="mb-2 text-fg-dim">{suggestion.message}</p>

      {editing ? (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="mb-2 w-full rounded-sm border bg-bg-2 p-2 font-mono text-xs text-fg focus-visible:ring-2 focus-visible:ring-brand-blue-light"
          rows={2}
        />
      ) : (
        <DiffInline original={suggestion.original_text} proposed={suggestion.proposed_text} />
      )}

      {isMultiPage ? (
        <div className="mt-2 flex items-center justify-between gap-2 rounded-sm bg-brand/10 px-2 py-1.5">
          <span className="text-xs text-fg-dim">
            {t("reviewer.suggestion.multiPageHint", { pages: groupPages })}
          </span>
          <button
            type="button"
            data-testid="suggestion-apply-group"
            onClick={(e) => {
              e.stopPropagation();
              onApplyGroup();
            }}
            className="inline-flex shrink-0 items-center gap-1 rounded-sm bg-brand px-2 py-1 text-xs text-fg hover:bg-brand-blue-light"
          >
            <Layers size={12} />
            {t("reviewer.suggestion.applyGroup", { count: groupOccurrences })}
          </button>
        </div>
      ) : null}

      {!isApplied && !isRejected ? (
        <footer className="mt-3 flex flex-wrap items-center justify-end gap-2">
          {editing ? (
            <>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setEditing(false);
                  setDraft(suggestion.proposed_text);
                }}
                className="rounded-sm border px-2 py-1 text-xs text-fg-dim hover:bg-card-hover hover:text-fg"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setEditing(false);
                  onSaveEdit(draft);
                }}
                className="rounded-sm bg-brand px-2 py-1 text-xs text-fg hover:bg-brand-blue-light"
              >
                {t("common.save")}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onReject();
                }}
                className="inline-flex items-center gap-1 rounded-sm border px-2 py-1 text-xs text-danger hover:bg-danger/10"
              >
                <X size={12} />
                {t("reviewer.suggestion.reject")}
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setEditing(true);
                }}
                className="inline-flex items-center gap-1 rounded-sm border px-2 py-1 text-xs text-fg-dim hover:bg-card-hover hover:text-fg"
              >
                <Pencil size={12} />
                {t("reviewer.suggestion.edit")}
              </button>
              <button
                type="button"
                data-testid="suggestion-accept"
                onClick={(e) => {
                  e.stopPropagation();
                  onAccept();
                }}
                className="inline-flex items-center gap-1 rounded-sm bg-brand px-2 py-1 text-xs text-fg hover:bg-brand-blue-light"
              >
                <Check size={12} />
                {t("reviewer.suggestion.accept")}
              </button>
            </>
          )}
        </footer>
      ) : null}
    </article>
  );
}
