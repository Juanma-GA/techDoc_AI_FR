import { Button, Input, SelectMenu, Textarea } from "@internal/ui";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useState, type MouseEvent } from "react";
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
  const [expanded, setExpanded] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const base = { dm_id: dmId, passage_id: passage.id };
  const pageLabel = passage.page === null
    ? t("preliminary.unlocated")
    : t("preliminary.page", { page: passage.page });
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
  const decisionLabel = t(passage.decision ? "preliminary.decisionSummary" : "preliminary.proposed", {
    category: passage.decision ? t(`preliminary.category.${passage.decision}`) : pendingLabel,
  });
  const togglePassage = () => {
    const next = !expanded;
    setExpanded(next);
    setDetailsOpen(next);
  };
  const expandPassage = (event: MouseEvent<HTMLElement>) => {
    const target = event.target;
    if (!(target instanceof Element) ||
        target.closest("button, input, textarea, select, label, summary, [data-passage-details]")) return;
    togglePassage();
  };
  return (
    <article onClick={expandPassage}
      className={`cursor-pointer rounded-sm border p-3 space-y-3 transition-colors hover:bg-bg-2 ${
        selected ? "border-bright bg-bg-3" : "bg-card"
      }`}>
      <div className="grid min-w-0 gap-3 sm:grid-cols-[minmax(0,1fr)_14rem] sm:items-start">
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <Button variant="ghost" size="sm" aria-pressed={selected}
              aria-label={t("preliminary.sourceAt", { page: passage.page ?? t("preliminary.unlocated") })}
              onClick={onSelect}>{pageLabel}</Button>
            <span className="min-w-0 flex-1 truncate text-sm text-fg-dim" title={decisionLabel}>
              {decisionLabel}
            </span>
            <Button variant="ghost" size="sm" aria-expanded={expanded}
              aria-controls={`preliminary-passage-${passage.id}`} className="shrink-0"
              aria-label={t(expanded ? "preliminary.collapsePassage" : "preliminary.expandPassage")}
              onClick={togglePassage}>
              {expanded
                ? <ChevronUp className="h-4 w-4" aria-hidden="true" />
                : <ChevronDown className="h-4 w-4" aria-hidden="true" />}
              <span>{t(expanded ? "preliminary.collapsePassage" : "preliminary.expandPassage")}</span>
            </Button>
          </div>
          <p className="mt-2 line-clamp-2 whitespace-pre-wrap break-words">{passage.text}</p>
        </div>
        <label className="block space-y-1">
          <span>{t("preliminary.destination")}</span>
          <SelectMenu
            label={t("preliminary.destination")}
            value={passage.decision ?? ""}
            disabled={disabled}
            options={[
              { value: "", label: pendingLabel },
              ...reviewDestinations.map((value) => ({ value, label: t(`preliminary.category.${value}`) })),
            ]}
            onValueChange={(selectedValue) => {
              const value = reviewDestinations.find((key) => key === selectedValue) ?? null;
              void decide(value);
            }}
          />
        </label>
      </div>
      <div id={`preliminary-passage-${passage.id}`} hidden={!expanded} className="space-y-3 border-t border-md pt-3">
        <p className="text-sm text-fg-dim">{t(`preliminary.rule.${passage.rule}`)}</p>
        <details data-passage-details open={detailsOpen} onToggle={(event) => {
          setDetailsOpen(event.currentTarget.open);
        }}>
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
