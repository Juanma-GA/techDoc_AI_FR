import { Check, Pencil, Undo2, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { DiffInline } from "../DiffInline";
import { SeverityBadge } from "../SeverityBadge";
import { UnitChip } from "../UnitChip";
import { localizedSuggestionMessage } from "../../lib/suggestionText";
import type { Suggestion } from "../../types/domain";

type Props = {
  suggestion: Suggestion;
  isSelected: boolean;
  onSelect: () => void;
  onAccept: () => void;
  onReject: () => void;
  onSaveEdit: (newProposedText: string) => void;
  /** Persist the free-text rejection motif (corpus-agent-style). */
  onSaveFeedback: (feedback: string) => void;
  /** Un-reject: put a rejected suggestion back to `open`. */
  onUnreject: () => void;
  onUndo: () => void;
};

export function SuggestionItem({
  suggestion,
  isSelected,
  onSelect,
  onAccept,
  onReject,
  onSaveEdit,
  onSaveFeedback,
  onUnreject,
  onUndo,
}: Props) {
  const { t } = useTranslation();
  const message = localizedSuggestionMessage(suggestion, t);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(suggestion.proposed_text);
  const [feedbackDraft, setFeedbackDraft] = useState(suggestion.feedback ?? "");

  const isApplied = suggestion.status === "applied";
  const isRejected = suggestion.status === "rejected";

  return (
    <article
      data-testid="suggestion-item"
      data-suggestion-id={suggestion.id}
      onClick={onSelect}
      className={isSelected ? "suggestion active" : "suggestion"}
    >
      <header className="suggestion-head">
        <SeverityBadge severity={suggestion.severity} />
        {suggestion.rule_kind === "units" ? <UnitChip /> : null}
        <span className="suggestion-loc">
          p.{suggestion.page} · {suggestion.rule_code}
        </span>
        <span className="badge default" title={t(`source.${suggestion.source_kind}`)}>
          {t(`source.${suggestion.source_kind}`)}
        </span>
        {isApplied ? (
          <span className="badge ok" style={{ marginLeft: "auto" }}>
            {t("reviewer.suggestion.applied")}
          </span>
        ) : null}
        {isRejected ? (
          <span className="badge off" style={{ marginLeft: "auto" }}>
            {t("reviewer.suggestion.rejected")}
          </span>
        ) : null}
      </header>

      <p className="suggestion-msg">{message}</p>

      {editing ? (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="input mono"
          rows={2}
        />
      ) : (
        <DiffInline original={suggestion.original_text} proposed={suggestion.proposed_text} />
      )}

      {!isApplied && !isRejected ? (
        <footer className="suggestion-actions" style={{ justifyContent: "flex-end" }}>
          {editing ? (
            <>
              <button
                type="button"
                className="btn secondary small"
                onClick={(e) => {
                  e.stopPropagation();
                  setEditing(false);
                  setDraft(suggestion.proposed_text);
                }}
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                className="btn primary small"
                onClick={(e) => {
                  e.stopPropagation();
                  setEditing(false);
                  onSaveEdit(draft);
                }}
              >
                {t("common.save")}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="btn danger small"
                onClick={(e) => {
                  e.stopPropagation();
                  onReject();
                }}
              >
                <X size={12} />
                {t("reviewer.suggestion.reject")}
              </button>
              <button
                type="button"
                className="btn secondary small"
                onClick={(e) => {
                  e.stopPropagation();
                  setEditing(true);
                }}
              >
                <Pencil size={12} />
                {t("reviewer.suggestion.edit")}
              </button>
              <button
                type="button"
                className="btn primary small"
                data-testid="suggestion-accept"
                onClick={(e) => {
                  e.stopPropagation();
                  onAccept();
                }}
              >
                <Check size={12} />
                {t("reviewer.suggestion.accept")}
              </button>
            </>
          )}
        </footer>
      ) : null}

      {isRejected ? (
        <div style={{ marginTop: 8 }} onClick={(e) => e.stopPropagation()}>
          <label className="label" htmlFor={`fb-${suggestion.id}`}>
            {t("reviewer.suggestion.feedbackLabel")}
          </label>
          <input
            id={`fb-${suggestion.id}`}
            type="text"
            className="input"
            data-testid="suggestion-feedback"
            placeholder={t("reviewer.suggestion.feedbackPlaceholder")}
            value={feedbackDraft}
            onChange={(e) => setFeedbackDraft(e.target.value)}
            onBlur={() => {
              if (feedbackDraft !== (suggestion.feedback ?? "")) onSaveFeedback(feedbackDraft);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
            }}
          />
          <div className="suggestion-actions" style={{ justifyContent: "flex-end", marginTop: 6 }}>
            <button
              type="button"
              className="btn ghost small"
              data-testid="suggestion-unreject"
              onClick={onUnreject}
            >
              <Undo2 size={12} />
              {t("reviewer.suggestion.unreject")}
            </button>
          </div>
        </div>
      ) : null}

      {isApplied ? (
        <footer className="suggestion-actions" style={{ justifyContent: "flex-end" }}>
          <button
            type="button"
            className="btn ghost small"
            data-testid="suggestion-undo"
            onClick={(e) => {
              e.stopPropagation();
              onUndo();
            }}
          >
            <Undo2 size={12} />
            {t("reviewer.suggestion.undo")}
          </button>
        </footer>
      ) : null}
    </article>
  );
}
