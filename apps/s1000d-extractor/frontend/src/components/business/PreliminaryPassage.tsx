import { Button, Input, Select, Textarea } from "@internal/ui";
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

export function PreliminaryPassage({ dmId, passage, text, disabled, editDisabled, selected, onSelect, onAction, onEdit }: Props) {
  const { t } = useTranslation();
  const length = Array.from(passage.source_text).length;
  const [splitAt, setSplitAt] = useState(Math.max(1, Math.floor(length / 2)));
  const base = { dm_id: dmId, passage_id: passage.id };
  const decide = (destination: ReviewAction["destination"]) =>
    onAction({ ...base, op: "decide", destination });
  return (
    <article className={`rounded-sm border p-3 space-y-3 ${selected ? "border-bright bg-bg-3" : "bg-card"}`}>
      <Button variant="ghost" size="sm" onClick={onSelect} aria-pressed={selected}>
        {t("preliminary.sourceAt", { page: passage.page ?? t("preliminary.unlocated") })}
      </Button>
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
            { value: "", label: t("preliminary.category.review") },
            ...reviewDestinations.map((value) => ({ value, label: t(`preliminary.category.${value}`) })),
          ]}
          onChange={(event) => {
            const value = reviewDestinations.find((key) => key === event.target.value) ?? null;
            void decide(value);
          }}
        />
      </label>
      {passage.suggested !== "review" && !passage.decision ? (
        <Button size="sm" variant="secondary" disabled={disabled} onClick={() => {
          if (passage.suggested !== "review") void decide(passage.suggested);
        }}>{t("preliminary.accept")}</Button>
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
          <label className="block">
            <span>{t("preliminary.splitAt", { count: length })}</span>
            <Input type="number" min={1} max={length - 1} value={splitAt}
              disabled={disabled || text !== passage.source_text || length < 2}
              aria-label={t("preliminary.splitPosition")}
              onChange={(event) => setSplitAt(Number(event.target.value))} />
          </label>
          <Button size="sm" variant="secondary"
            disabled={disabled || text !== passage.source_text || splitAt < 1 || splitAt >= length}
            onClick={() => void onAction({ ...base, op: "split", split_at: splitAt })}>
            {t("preliminary.split")}
          </Button>
        </div>
      </details>
    </article>
  );
}
