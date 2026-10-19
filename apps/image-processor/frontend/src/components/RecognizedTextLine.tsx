import { useEffect, useState } from "react";
import type { TFunction } from "i18next";
import { Button } from "@internal/ui";
import { Pencil } from "lucide-react";

import type { OcrResultDto } from "../lib/api";
import { RecognizedTextEditor, type RecognizedTextEditTarget } from "./RecognizedTextEditor";

type RecognizedTextLineProps = {
  result: OcrResultDto;
  lineIndex: number;
  matched: boolean;
  disabled: boolean;
  onReplaceLine: (
    lineIndex: number,
    reference: string,
    replacement: string,
    referenceIndex: number | null,
  ) => Promise<boolean>;
  onUndoLine: (lineIndex: number, referenceIndex: number) => Promise<boolean>;
  t: TFunction;
};

export function RecognizedTextLine({
  result,
  lineIndex,
  matched,
  disabled,
  onReplaceLine,
  onUndoLine,
  t,
}: RecognizedTextLineProps) {
  const [editing, setEditing] = useState<RecognizedTextEditTarget | null>(null);
  const line = result.lines[lineIndex];

  useEffect(() => {
    setEditing(null);
  }, [result]);
  if (!line) return null;

  const matchedTargets = result.references.flatMap((reference, referenceIndex) =>
    reference.line_indices.includes(lineIndex)
      ? [{
          reference: reference.reference,
          replacement: reference.replacement ?? "",
          referenceIndex,
          undo: reference.undo ?? null,
        }]
      : [],
  );
  const targets = matchedTargets.length > 0
    ? matchedTargets
    : line.text.trim()
      ? [{ reference: line.text, replacement: "", referenceIndex: null, undo: null }]
      : [];
  const firstTarget = targets[0];

  function openEditor(target: RecognizedTextEditTarget) {
    setEditing(target);
  }

  function cancelEdit() {
    setEditing(null);
  }

  return (
    <li
      data-ocr-line-index={lineIndex}
      className={`space-y-1 rounded-sm px-2 py-1.5 ${
        matched ? "bg-brand/10 text-fg" : "text-fg-dim"
      }`}
    >
      <div className="flex items-start gap-3">
        {firstTarget ? (
          <Button
            type="button"
            variant="ghost"
            disabled={disabled}
            aria-label={t(
              firstTarget.referenceIndex === null
                ? "image.replaceRecognizedLine"
                : "image.editRecognizedReplacement",
              { reference: firstTarget.reference },
            )}
            className="h-auto min-w-0 flex-1 justify-start whitespace-normal px-1 py-0 text-left font-normal"
            onClick={() => openEditor(firstTarget)}
          >
            <span className="flex min-w-0 items-center gap-2">
              <span className="break-all text-sm underline decoration-dotted underline-offset-4">
                {line.text}
              </span>
              <Pencil size={14} className="shrink-0" aria-hidden="true" />
            </span>
          </Button>
        ) : (
          <span className="min-w-0 flex-1 break-all text-sm">{line.text}</span>
        )}
        <span className="shrink-0 font-mono text-xs">
          {Math.round(line.confidence * 100)}%
        </span>
      </div>
      {targets.length > 1 ? (
        <div className="flex flex-wrap gap-1">
          {targets.slice(1).map((target) => (
            <Button
              key={`${target.reference}-${target.referenceIndex}`}
              type="button"
              size="sm"
              variant="secondary"
              disabled={disabled}
              aria-label={t("image.editRecognizedReplacement", {
                reference: target.reference,
              })}
              onClick={() => openEditor(target)}
            >
              {target.reference}
            </Button>
          ))}
        </div>
      ) : null}
      {editing ? (
        <RecognizedTextEditor
          key={`${editing.reference}-${editing.referenceIndex}`}
          target={editing}
          lineIndex={lineIndex}
          disabled={disabled}
          onReplaceLine={onReplaceLine}
          onUndoLine={onUndoLine}
          onClose={cancelEdit}
          t={t}
        />
      ) : null}
    </li>
  );
}
