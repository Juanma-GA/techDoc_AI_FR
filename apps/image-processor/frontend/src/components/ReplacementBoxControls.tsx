import type { TFunction } from "i18next";
import { Button, Input } from "@internal/ui";

import type { OcrResultDto } from "../lib/api";
import type { LineBoxOffset } from "../lib/replacement-box-offsets";

const MAX_BOX_OFFSET = 30;

type ReplacementBoxControlsProps = {
  result: OcrResultDto | null;
  selectedLineIndex: number | null;
  disabled: boolean;
  reapplyBlocked: boolean;
  onUpdateOffsets: (offsets: LineBoxOffset[]) => void;
  onApplyToAll: () => void;
  onReapply: () => void;
  t: TFunction;
};

export function ReplacementBoxControls({
  result,
  selectedLineIndex,
  disabled,
  reapplyBlocked,
  onUpdateOffsets,
  onApplyToAll,
  onReapply,
  t,
}: ReplacementBoxControlsProps) {
  const selectedLine = selectedLineIndex == null ? undefined : result?.lines[selectedLineIndex];
  const hasReplacements = Boolean(result?.references.some((reference) => reference.replacement));

  function updateOffset(axis: "x" | "y", value: number) {
    if (!selectedLine || selectedLineIndex == null) return;
    onUpdateOffsets([{
      lineIndex: selectedLineIndex,
      x: axis === "x" ? value : selectedLine.box_offset_x ?? 0,
      y: axis === "y" ? value : selectedLine.box_offset_y ?? 0,
    }]);
  }

  if (!result || result.lines.length === 0) return null;

  return (
    <section aria-labelledby="replacement-box-offset-title" className="space-y-3 rounded-md border border-md p-3">
      <div className="space-y-1">
        <h3 id="replacement-box-offset-title" className="text-sm font-medium text-fg">
          {t("image.replacementBoxOffsets")}
        </h3>
        <p className="text-xs text-fg-dim">{t("image.replacementBoxOffsetHint")}</p>
      </div>
      {selectedLine ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {(["x", "y"] as const).map((axis) => {
            const value = axis === "x"
              ? selectedLine.box_offset_x ?? 0
              : selectedLine.box_offset_y ?? 0;
            const key = axis === "x" ? "image.horizontalOffset" : "image.verticalOffset";
            return (
              <label key={axis} className="space-y-1">
                <span className="flex justify-between gap-2 text-xs text-fg-dim">
                  <span>{t(key)}</span>
                  <span className="font-mono">{value} px</span>
                </span>
                <Input
                  type="range"
                  min={-MAX_BOX_OFFSET}
                  max={MAX_BOX_OFFSET}
                  step={1}
                  value={value}
                  disabled={disabled}
                  className="accent-brand-blue"
                  aria-label={t(key)}
                  onChange={(event) => updateOffset(axis, Number(event.target.value))}
                />
              </label>
            );
          })}
        </div>
      ) : (
        <p className="text-sm text-fg-dim">{t("image.selectReplacementBox")}</p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          disabled={disabled || !selectedLine || !hasReplacements}
          onClick={onApplyToAll}
        >
          {t("image.applyBoxOffsetsToAll")}
        </Button>
        <Button
          type="button"
          disabled={disabled || !hasReplacements || reapplyBlocked}
          onClick={onReapply}
        >
          {t("image.reapplyReplacements")}
        </Button>
      </div>
      {reapplyBlocked ? (
        <p className="text-xs text-fg-dim">{t("image.reapplyBrushBlocked")}</p>
      ) : null}
    </section>
  );
}
