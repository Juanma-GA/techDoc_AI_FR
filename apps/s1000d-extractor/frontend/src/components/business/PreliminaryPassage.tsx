import { Button, Input, Select, Textarea } from "@internal/ui";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { reviewDestinations, type ReviewAction, type ReviewPassage } from "../../lib/preliminaryTypes";

type Props = {
  dmId: string;
  passage: ReviewPassage;
  text: string;
  disabled: boolean;
  editDisabled: boolean;
  selected: boolean;
  onSelect: () => void;
  onAction: (action: ReviewAction) => Promise<boolean>;
  onEdit: (action: ReviewAction & { passage_id: string; text: string }) => void;
};

function sourceWords(text: string): Array<{ text: string; end: number }> {
  const words: Array<{ text: string; end: number }> = [];
  const matcher = /\S+/gu;
  let match: RegExpExecArray | null;
  while ((match = matcher.exec(text)) !== null) {
    words.push({ text: match[0], end: matcher.lastIndex });
  }
  return words;
}

export function PreliminaryPassage({ dmId, passage, text, disabled, editDisabled, selected, onSelect, onAction, onEdit }: Props) {
  const { t } = useTranslation();
  const words = sourceWords(passage.source_text);
  const [splitAfter, setSplitAfter] = useState(Math.max(1, Math.floor(words.length / 2)));
  const [expanded, setExpanded] = useState(!passage.decision);
  const base = { dm_id: dmId, passage_id: passage.id };
  const decide = (destination: ReviewAction["destination"]) =>
    onAction({ ...base, op: "decide", destination });
  const pendingLabel = passage.suggested === "review"
    ? t("preliminary.category.review")
    : t(`preliminary.category.${passage.suggested}`);
  const splitWord = words[splitAfter - 1];
  const splitOffset = splitWord?.end ?? 0;
  const splitAt = Array.from(passage.source_text.slice(0, splitOffset)).length;
  const firstPart = passage.source_text.slice(0, splitOffset).trim();
  const secondPart = passage.source_text.slice(splitOffset).trim();
  const acceptProposal = async () => {
    if (passage.suggested !== "review" && await decide(passage.suggested)) {
      setExpanded(false);
    }
  };
  return (
    <article className={`rounded-sm border p-3 space-y-3 ${selected ? "border-bright bg-bg-3" : "bg-card"}`}>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={onSelect} aria-pressed={selected}>
          {t("preliminary.sourceAt", { page: passage.page ?? t("preliminary.unlocated") })}
        </Button>
        {!expanded ? (
          <p className="min-w-0 flex-1 truncate text-sm text-fg-dim" title={passage.text}>
            {passage.decision
              ? t("preliminary.decisionSummary", { category: t(`preliminary.category.${passage.decision}`) })
              : t("preliminary.proposed", { category: t(`preliminary.category.${passage.suggested}`) })}
            {" — "}{passage.text}
          </p>
        ) : null}
        <Button variant="ghost" size="sm" aria-expanded={expanded}
          aria-controls={`preliminary-passage-${passage.id}`}
          aria-label={t(expanded ? "preliminary.collapsePassage" : "preliminary.expandPassage")}
          onClick={() => setExpanded((open) => !open)}>
          {expanded
            ? <ChevronUp className="h-4 w-4" aria-hidden="true" />
            : <ChevronDown className="h-4 w-4" aria-hidden="true" />}
        </Button>
      </div>
      <div id={`preliminary-passage-${passage.id}`} hidden={!expanded} className="space-y-3">
        <p className="whitespace-pre-wrap">{passage.text}</p>
        <p className="text-sm text-fg-dim">
          {t("preliminary.proposed", { category: t(`preliminary.category.${passage.suggested}`) })}
          {" - "}{t(`preliminary.rule.${passage.rule}`)}
        </p>
        <label className="block space-y-1">
          <span>{t("preliminary.destination")}</span>
          <Select
            aria-label={t("preliminary.destination")}
            value={passage.decision ?? ""}
            disabled={disabled}
            options={[
              { value: "", label: pendingLabel },
              ...reviewDestinations.map((value) => ({ value, label: t(`preliminary.category.${value}`) })),
            ]}
            onChange={(event) => {
              const value = reviewDestinations.find((key) => key === event.target.value) ?? null;
              void decide(value);
            }}
          />
        </label>
        {passage.suggested !== "review" && !passage.decision ? (
          <Button size="sm" variant="secondary" disabled={disabled} onClick={() => void acceptProposal()}>
            {t("preliminary.accept")}
          </Button>
        ) : null}
        <details>
          <summary className="cursor-pointer text-fg-dim">{t("preliminary.editSplit")}</summary>
          <div className="space-y-3 pt-3">
            <label className="block">
              <span>{t("preliminary.correctedText")}</span>
              <Textarea value={text} disabled={editDisabled} aria-label={t("preliminary.correctedText")}
                onChange={(event) => onEdit({
                  ...base, op: "decide", text: event.target.value,
                })} />
            </label>
            <p className="text-sm text-fg-dim">{t("preliminary.autosave")}</p>
            {words.length >= 2 ? (
              <>
                <label className="block space-y-1">
                  <span>{t("preliminary.splitAt", {
                    word: splitWord?.text ?? "", index: splitAfter, count: words.length,
                  })}</span>
                  <Input type="range" min={1} max={words.length - 1} step={1} value={splitAfter}
                    disabled={disabled || text !== passage.source_text}
                    aria-label={t("preliminary.splitPosition")}
                    aria-valuetext={t("preliminary.splitPositionValue", {
                      word: splitWord?.text ?? "", index: splitAfter, count: words.length,
                    })}
                    onChange={(event) => setSplitAfter(Number(event.currentTarget.value))} />
                </label>
                <div role="group" aria-label={t("preliminary.splitPreview")}
                  className="grid gap-3 sm:grid-cols-2">
                  <div className="min-w-0 rounded-sm border bg-bg-2 p-2">
                    <p className="text-xs text-fg-dim">{t("preliminary.splitFirstPart")}</p>
                    <p className="whitespace-pre-wrap break-words">{firstPart}</p>
                  </div>
                  <div className="min-w-0 rounded-sm border bg-bg-2 p-2">
                    <p className="text-xs text-fg-dim">{t("preliminary.splitSecondPart")}</p>
                    <p className="whitespace-pre-wrap break-words">{secondPart}</p>
                  </div>
                </div>
                <Button size="sm" variant="secondary"
                  disabled={disabled || text !== passage.source_text}
                  onClick={() => void onAction({ ...base, op: "split", split_at: splitAt })}>
                  {t("preliminary.split")}
                </Button>
              </>
            ) : <p className="text-sm text-fg-dim">{t("preliminary.splitUnavailable")}</p>}
          </div>
        </details>
      </div>
    </article>
  );
}
