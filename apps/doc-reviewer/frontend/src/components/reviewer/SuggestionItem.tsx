import { Check, Pencil, Undo2, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { DiffInline } from "../DiffInline";
import { SeverityBadge } from "../SeverityBadge";
import { UnitChip } from "../UnitChip";
import {
  isAiGeneratedSuggestion,
  localizedRuleCode,
  localizedSuggestionMessage,
} from "../../lib/suggestionText";
import type { Suggestion } from "../../types/domain";

type Props = {
  suggestion: Suggestion;
  ruleNumber: number | null;
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
  ruleNumber,
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
  const ruleCodeLabel = localizedRuleCode(suggestion.rule_code, t);
  const sourceKind = isAiGeneratedSuggestion(
    suggestion.source_kind,
    suggestion.rule_code,
    suggestion.proposed_text,
  )
    ? "ai"
    : suggestion.source_kind;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(suggestion.proposed_text);
  const [feedbackDraft, setFeedbackDraft] = useState(suggestion.feedback ?? "");

  const isApplied = suggestion.status === "applied";
  const isRejected = suggestion.status === "rejected";
  const detectionOnly =
    !suggestion.proposed_text || suggestion.proposed_text === suggestion.original_text;

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
          p.{suggestion.page} · {ruleCodeLabel}
        </span>
        {ruleNumber != null ? (
          <Link
            className="badge default suggestion-rule-number"
            to={`/rules?rule=${encodeURIComponent(suggestion.rule_code)}`}
            title={t("rules.client.openRule", { number: ruleNumber })}
            aria-label={t("rules.client.openRule", { number: ruleNumber })}
            onClick={(event) => event.stopPropagation()}
          >
            #{ruleNumber}
          </Link>
        ) : null}
        <span className="badge default" title={t(`reviewer.source.${sourceKind}`)}>
          {t(`reviewer.source.${sourceKind}`)}
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
      {detectionOnly ? (
        <span className="badge default">{t("rules.suggestionDetails.detectionOnly")}</span>
      ) : null}

      {!isApplied && !isRejected ? (
        <footer className="suggestion-actions" style={{ justifyContent: "flex-end" }}>
          {editing && !detectionOnly ? (
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
              {!detectionOnly ? (
                <>
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
              ) : null}
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
