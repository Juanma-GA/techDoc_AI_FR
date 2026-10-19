import type { TFunction } from "i18next";
import { Badge, Card, CardContent, CardHeader, CardTitle } from "@internal/ui";
import { CheckCircle2, Circle, ScanText } from "lucide-react";

import type { OcrResultDto } from "../lib/api";

type OcrResultsProps = {
  result: OcrResultDto | null;
  t: TFunction;
};

export function OcrResults({ result, t }: OcrResultsProps) {
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
        </CardHeader>
        <CardContent>
          {result.lines.length > 0 ? (
            <ul className="max-h-80 space-y-1 overflow-auto">
              {result.lines.map((line, index) => (
                <li
                  key={`${index}-${line.text}`}
                  className={`flex items-start justify-between gap-3 rounded-sm px-2 py-1.5 ${
                    matchedLines.has(index) ? "bg-brand/10 text-fg" : "text-fg-dim"
                  }`}
                >
                  <span className="break-all text-sm">{line.text}</span>
                  <span className="shrink-0 font-mono text-xs">
                    {Math.round(line.confidence * 100)}%
                  </span>
                </li>
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
