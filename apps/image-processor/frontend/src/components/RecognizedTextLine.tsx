import { useEffect, useState, type KeyboardEvent } from "react";
import type { TFunction } from "i18next";
import { Button, Input } from "@internal/ui";
import { Pencil } from "lucide-react";

import type { OcrResultDto } from "../lib/api";

type EditingTarget = {
  reference: string;
  replacement: string;
  referenceIndex: number | null;
};

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
  t: TFunction;
};

export function RecognizedTextLine({
  result,
  lineIndex,
  matched,
  disabled,
  onReplaceLine,
  t,
}: RecognizedTextLineProps) {
  const [editing, setEditing] = useState<EditingTarget | null>(null);
  const [replacement, setReplacement] = useState("");
  const [saving, setSaving] = useState(false);
  const line = result.lines[lineIndex];

  useEffect(() => {
    setEditing(null);
    setReplacement("");
  }, [result]);
  if (!line) return null;

  const matchedTargets = result.references.flatMap((reference, referenceIndex) =>
    reference.line_indices.includes(lineIndex)
      ? [{
          reference: reference.reference,
          replacement: reference.replacement ?? "",
          referenceIndex,
        }]
      : [],
  );
  const targets = matchedTargets.length > 0
    ? matchedTargets
    : line.text.trim()
      ? [{ reference: line.text, replacement: "", referenceIndex: null }]
      : [];
  const firstTarget = targets[0];
  const inputId = `recognized-replacement-${lineIndex}-${editing?.referenceIndex ?? "line"}`;

  function openEditor(target: EditingTarget) {
    setEditing(target);
    setReplacement(target.replacement);
  }

  function cancelEdit() {
    setEditing(null);
    setReplacement("");
  }

  async function submitEdit() {
    if (!editing || disabled || saving || !replacement.trim()) return;
    setSaving(true);
    try {
      if (await onReplaceLine(
        lineIndex,
        editing.reference,
        replacement,
        editing.referenceIndex,
      )) {
        cancelEdit();
      }
    } finally {
      setSaving(false);
    }
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
        <div
          role="group"
          aria-label={t("image.replacementValue", { reference: editing.reference })}
          className="flex flex-col gap-2 rounded-md border border-md bg-bg-2 p-2 sm:flex-row"
          onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => {
            if (event.key === "Escape" && !saving) {
              event.preventDefault();
              cancelEdit();
            } else if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submitEdit();
            }
          }}
        >
          <label htmlFor={inputId} className="sr-only">
            {t("image.replacementValue", { reference: editing.reference })}
          </label>
          <Input
            id={inputId}
            autoFocus
            value={replacement}
            disabled={disabled || saving}
            aria-label={t("image.replacementValue", { reference: editing.reference })}
            onChange={(event) => setReplacement(event.target.value)}
            placeholder={t("image.replacementPlaceholder")}
            className="min-w-0 flex-1"
          />
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              disabled={disabled || saving || !replacement.trim()}
              onClick={() => void submitEdit()}
            >
              {saving ? t("image.applyingLineReplacement") : t("image.applyLineReplacement")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={saving}
              onClick={cancelEdit}
            >
              {t("image.cancelLineReplacement")}
            </Button>
          </div>
        </div>
      ) : null}
    </li>
  );
}
