import { useEffect, useRef } from "react";
import type { TFunction } from "i18next";
import { Badge, Card, CardContent, CardHeader, CardTitle } from "@internal/ui";
import { CheckCircle2, Circle, ScanText } from "lucide-react";

import type { OcrResultDto } from "../lib/api";
import { RecognizedTextLine } from "./RecognizedTextLine";

type OcrResultsProps = {
  result: OcrResultDto | null;
  disabled: boolean;
  selectionRequest: { lineIndex: number; requestId: number } | null;
  onSelectionHandled: (requestId: number) => void;
  onReplaceLine: (
    lineIndex: number,
    reference: string,
    replacement: string,
    referenceIndex: number | null,
  ) => Promise<boolean>;
  onUndoLine: (lineIndex: number) => Promise<boolean>;
  t: TFunction;
};

export function OcrResults({
  result,
  disabled,
  selectionRequest,
  onSelectionHandled,
  onReplaceLine,
  onUndoLine,
  t,
}: OcrResultsProps) {
  const recognizedLinesRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!selectionRequest) return;
    const row = recognizedLinesRef.current?.querySelector<HTMLElement>(
      `[data-ocr-line-index="${selectionRequest.lineIndex}"]`,
    );
    if (typeof row?.scrollIntoView === "function") {
      row.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    row?.querySelector<HTMLButtonElement>("button")?.click();
    onSelectionHandled(selectionRequest.requestId);
  }, [selectionRequest, onSelectionHandled]);

  if (!result) return null;

  const foundCount = result.references.filter((item) => item.found).length;
  const matchedLines = new Set(result.references.flatMap((item) => item.line_indices));

  return (
    <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="mb-0">{t("image.references")}</CardTitle>
            <Badge variant={foundCount > 0 ? "success" : "default"}>
              {t("image.matchedCount", { found: foundCount, total: result.references.length })}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {result.references.length === 0 ? (
            <p className="text-sm text-fg-dim">{t("image.noneProvided")}</p>
          ) : (
            <ul className="space-y-2">
              {result.references.map((item, index) => (
                <li
                  key={`${item.reference}-${index}`}
                  className="flex flex-wrap items-center gap-2 rounded-md border border-md bg-bg-2 p-3"
                >
                  {item.found ? (
                    <CheckCircle2 size={17} className="text-success" aria-hidden="true" />
                  ) : (
                    <Circle size={17} className="text-fg-muted" aria-hidden="true" />
                  )}
                  <span className="flex min-w-0 flex-1 flex-wrap items-center gap-2 font-mono text-sm">
                    <code className="text-fg">{item.reference}</code>
                    {item.replacement ? (
                      <>
                        <span aria-hidden="true" className="text-fg-muted">-&gt;</span>
                        <code className="text-brand">{item.replacement}</code>
                      </>
                    ) : null}
                  </span>
                  <Badge variant={item.found ? "success" : "warning"}>
                    {item.replacement
                      ? item.replacement_count
                        ? t("image.replacementApplied", { count: item.replacement_count })
                        : item.found
                          ? t("image.foundNotReplaced")
                          : t("image.notFound")
                      : item.found
                        ? t("image.found")
                        : t("image.notFound")}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ScanText size={17} aria-hidden="true" />
            {t("image.recognizedText")}
          </CardTitle>
          <p className="text-xs text-fg-dim">{t("image.editRecognizedHint")}</p>
        </CardHeader>
        <CardContent>
          {result.lines.length > 0 ? (
            <ul ref={recognizedLinesRef} className="max-h-80 space-y-1 overflow-auto">
              {result.lines.map((line, index) => (
                <RecognizedTextLine
                  key={`${index}-${line.text}`}
                  result={result}
                  lineIndex={index}
                  matched={matchedLines.has(index)}
                  disabled={disabled}
                  onReplaceLine={onReplaceLine}
                  onUndoLine={onUndoLine}
                  t={t}
                />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-fg-dim">{t("image.noText")}</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
