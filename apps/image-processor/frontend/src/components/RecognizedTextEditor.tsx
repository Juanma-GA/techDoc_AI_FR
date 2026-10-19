import { useState, type KeyboardEvent } from "react";
import type { TFunction } from "i18next";
import { Button, Input } from "@internal/ui";
import { Undo2 } from "lucide-react";

import type { OcrReferenceUndoDto } from "../lib/api";

export type RecognizedTextEditTarget = {
  reference: string;
  replacement: string;
  referenceIndex: number | null;
  undo: OcrReferenceUndoDto | null;
};

type RecognizedTextEditorProps = {
  target: RecognizedTextEditTarget;
  lineIndex: number;
  disabled: boolean;
  onReplaceLine: (
    lineIndex: number,
    reference: string,
    replacement: string,
    referenceIndex: number | null,
  ) => Promise<boolean>;
  onUndoLine: (lineIndex: number, referenceIndex: number) => Promise<boolean>;
  onClose: () => void;
  t: TFunction;
};

export function RecognizedTextEditor({
  target,
  lineIndex,
  disabled,
  onReplaceLine,
  onUndoLine,
  onClose,
  t,
}: RecognizedTextEditorProps) {
  const [replacement, setReplacement] = useState(target.replacement);
  const inputId = `recognized-replacement-${lineIndex}-${target.referenceIndex ?? "line"}`;

  async function submitEdit() {
    if (disabled || !replacement.trim()) return;
    if (await onReplaceLine(lineIndex, target.reference, replacement, target.referenceIndex)) {
      onClose();
    }
  }

  async function undoEdit() {
    if (disabled || target.referenceIndex === null || !target.undo) return;
    if (await onUndoLine(lineIndex, target.referenceIndex)) onClose();
  }

  return (
    <div
      role="group"
      aria-label={t("image.replacementValue", { reference: target.reference })}
      className="flex flex-col gap-2 rounded-md border border-md bg-bg-2 p-2 sm:flex-row"
      onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => {
        if (event.key === "Escape" && !disabled) {
          event.preventDefault();
          onClose();
        } else if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          void submitEdit();
        }
      }}
    >
      <label htmlFor={inputId} className="sr-only">
        {t("image.replacementValue", { reference: target.reference })}
      </label>
      <Input
        id={inputId}
        autoFocus
        value={replacement}
        disabled={disabled}
        aria-label={t("image.replacementValue", { reference: target.reference })}
        onChange={(event) => setReplacement(event.target.value)}
        placeholder={t("image.replacementPlaceholder")}
        className="min-w-0 flex-1"
      />
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          disabled={disabled || !replacement.trim()}
          onClick={() => void submitEdit()}
        >
          {t("image.applyLineReplacement")}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={disabled}
          onClick={onClose}
        >
          {t("image.cancelLineReplacement")}
        </Button>
        {target.undo ? (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={disabled}
            onClick={() => void undoEdit()}
          >
            <Undo2 size={15} aria-hidden="true" />
            {t("image.undoLineReplacement")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
