import { Button, Checkbox, Input } from "@internal/ui";
import type { TFunction } from "i18next";
import { Trash2 } from "lucide-react";

import type { ReplacementPair } from "../lib/workspace-api";

type PairRowProps = {
  pair: ReplacementPair;
  index: number;
  excel?: boolean;
  disabled: boolean;
  onToggle: (id: number) => void;
  onUpdate: (id: number, field: "reference" | "replacement", value: string) => void;
  onRemove: (id: number) => void;
  t: TFunction;
};

export function ReplacementPairRow({
  pair, index, excel = false, disabled, onToggle, onUpdate, onRemove, t,
}: PairRowProps) {
  const number = index + 1;
  const missingExcelReference = excel && !pair.reference.trim();
  const missingReferenceMessageId = `excel-pair-reference-missing-${pair.id}`;
  return (
    <div
      className={`flex items-center gap-2 rounded-md border p-3 ${
        missingExcelReference ? "border-danger/40 bg-danger/10" : "border-md bg-bg-2"
      }`}
    >
      <Checkbox
        checked={pair.enabled} disabled={disabled}
        aria-label={t(excel ? "image.selectExcelPair" : "image.selectPair", { number })}
        onCheckedChange={() => onToggle(pair.id)}
      />
      <div className="grid min-w-0 flex-1 grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="min-w-0 space-y-1">
          <span className="text-xs text-fg-dim">{t("image.reference")}</span>
          <Input
            value={pair.reference} placeholder={t("image.referencePlaceholder")} disabled={disabled}
            state={missingExcelReference ? "error" : "default"}
            aria-label={excel ? t("image.excelPairReference", { number }) : `${t("image.reference")} ${number}`}
            aria-invalid={missingExcelReference || undefined}
            aria-describedby={missingExcelReference ? missingReferenceMessageId : undefined}
            onChange={(event) => onUpdate(pair.id, "reference", event.target.value)}
          />
        </label>
        <label className="min-w-0 space-y-1">
          <span className="text-xs text-fg-dim">{t("image.newReference")}</span>
          <Input
            value={pair.replacement} placeholder={t("image.replacementPlaceholder")} disabled={disabled}
            aria-label={excel ? t("image.excelPairReplacement", { number }) : `${t("image.newReference")} ${number}`}
            onChange={(event) => onUpdate(pair.id, "replacement", event.target.value)}
          />
        </label>
        {missingExcelReference ? (
          <p id={missingReferenceMessageId} className="col-span-full text-xs text-danger">
            {t("image.excelPairMissingReference")}
          </p>
        ) : null}
      </div>
      <Button
        variant="ghost" size="icon" disabled={disabled}
        aria-label={t(excel ? "image.removeExcelPair" : "image.removePair", { number })}
        onClick={() => onRemove(pair.id)}
      >
        <Trash2 size={16} aria-hidden="true" />
      </Button>
    </div>
  );
}
