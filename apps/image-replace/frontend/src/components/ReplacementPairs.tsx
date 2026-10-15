import type { TFunction } from "i18next";
import { Plus, Trash2 } from "lucide-react";
import { Button, Input } from "@internal/ui";

import type { ReplacementPair } from "../hooks/useImageReplace";

type ReplacementPairsProps = {
  pairs: ReplacementPair[];
  disabled: boolean;
  onAdd: () => void;
  onUpdate: (id: number, field: "reference" | "replacement", value: string) => void;
  onRemove: (id: number) => void;
  t: TFunction;
};

export function ReplacementPairs({
  pairs,
  disabled,
  onAdd,
  onUpdate,
  onRemove,
  t,
}: ReplacementPairsProps) {
  return (
    <section aria-labelledby="replacement-pairs-title" className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 id="replacement-pairs-title" className="label">
          {t("image.pairsTitle")}
        </h3>
        <span className="rounded-sm bg-bg-2 px-2 py-1 font-mono text-xs text-fg-dim">
          {pairs.length}
        </span>
      </div>

      {pairs.length > 0 ? (
        <div className="space-y-2">
          {pairs.map((pair, index) => (
            <div
              key={pair.id}
              className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-2 rounded-md border border-md bg-bg-2 p-3"
            >
              <div className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
                <label className="min-w-0 space-y-1">
                  <span className="text-xs text-fg-dim">{t("image.reference")}</span>
                  <Input
                    value={pair.reference}
                    placeholder={t("image.referencePlaceholder")}
                    disabled={disabled}
                    aria-label={`${t("image.reference")} ${index + 1}`}
                    onChange={(event) => onUpdate(pair.id, "reference", event.target.value)}
                  />
                </label>
                <label className="min-w-0 space-y-1">
                  <span className="text-xs text-fg-dim">{t("image.newReference")}</span>
                  <Input
                    value={pair.replacement}
                    placeholder={t("image.replacementPlaceholder")}
                    disabled={disabled}
                    aria-label={`${t("image.newReference")} ${index + 1}`}
                    onChange={(event) => onUpdate(pair.id, "replacement", event.target.value)}
                  />
                </label>
              </div>
              <Button
                variant="ghost"
                size="icon"
                disabled={disabled}
                aria-label={t("image.removePair", { number: index + 1 })}
                onClick={() => onRemove(pair.id)}
              >
                <Trash2 size={16} aria-hidden="true" />
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-md border border-dashed border-md p-3 text-center text-sm text-fg-dim">
          {t("image.emptyPairs")}
        </p>
      )}

      <Button variant="secondary" className="w-full" disabled={disabled} onClick={onAdd}>
        <Plus size={16} aria-hidden="true" />
        {t("image.addPair")}
      </Button>
      <p className="text-xs leading-relaxed text-fg-dim">{t("image.pairHint")}</p>
    </section>
  );
}
