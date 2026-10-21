import type { TFunction } from "i18next";
import { Image as ImageIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, EmptyState } from "@internal/ui";

import type { OcrResultDto } from "../lib/api";
import { useImageEditor } from "../hooks/useImageEditor";
import { BrushControls } from "./BrushControls";
import { ImageToolbar } from "./ImageToolbar";

type ImagePreviewProps = {
  imageFile: File | null;
  imageUrl: string;
  result: OcrResultDto | null;
  disabled: boolean;
  manuallyEdited: boolean;
  canUndo: boolean;
  onUndo: () => void;
  onDownload: () => void;
  onDownloadAs: () => void;
  downloading: boolean;
  savingAs: boolean;
  onImageEdited: (image: string, mode: "lama" | "color") => void;
  onInpaintingChange: (busy: boolean) => void;
  onSelectLine: (lineIndex: number) => void;
  t: TFunction;
};

export function ImagePreview({
  imageFile,
  imageUrl,
  result,
  disabled,
  manuallyEdited,
  canUndo,
  onUndo,
  onDownload,
  onDownloadAs,
  downloading,
  savingAs,
  onImageEdited,
  onInpaintingChange,
  onSelectLine,
  t,
}: ImagePreviewProps) {
  const editor = useImageEditor({
    imageFile, imageUrl, manuallyEdited, onImageEdited, onInpaintingChange, t,
  });
  const replacedLines = new Set((result?.references ?? []).flatMap((item) =>
    item.line_indices.slice(0, item.replacement_count ?? 0),
  ));

  if (!editor.previewImage) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("image.resultTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            icon={ImageIcon}
            title={t("image.emptyPreviewTitle")}
            description={t("image.emptyPreviewDescription")}
            className="min-h-80 border-dashed bg-bg-2 shadow-none"
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle className="mb-0">{t("image.resultTitle")}</CardTitle>
        <p className="text-sm text-fg-dim">{t("image.resultDescription")}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <ImageToolbar
          editor={editor} result={result} canUndo={canUndo} onUndo={onUndo}
          onDownload={onDownload} onDownloadAs={onDownloadAs}
          downloading={downloading} savingAs={savingAs} disabled={disabled} t={t}
        />
        <div
          ref={editor.previewRef}
          className={`relative flex max-h-[70vh] min-h-72 items-center justify-center overflow-hidden rounded-md border border-md bg-bg-2 p-3 ${
            editor.zoom > 1 && !editor.brushEnabled ? "cursor-grab" : ""
          } ${editor.dragging ? "cursor-grabbing" : ""}`}
          onPointerDown={editor.startPan}
          onPointerMove={editor.movePan}
          onPointerUp={editor.stopPan}
          onPointerCancel={editor.stopPan}
        >
          <div
            className="relative max-h-full max-w-full origin-center"
            style={{ transform: `translate(${editor.pan.x}px, ${editor.pan.y}px) scale(${editor.zoom})` }}
          >
            <img
              src={editor.previewImage}
              alt={result ? t("image.resultImageAlt") : t("image.sourceImageAlt")}
              draggable={false}
              className="block max-h-[65vh] max-w-full select-none object-contain"
              onLoad={editor.prepareCanvas}
            />
            {result ? (
              <svg
                className="pointer-events-none absolute inset-0 h-full w-full"
                viewBox={`0 0 ${result.width} ${result.height}`}
                role="group"
                aria-label={t("image.recognizedBoxes")}
              >
                {result.lines.map((line, index) => {
                  const reference = result.references.find((item) => item.line_indices.includes(index));
                  const replaced = replacedLines.has(index);
                  const canSelect = !disabled && !editor.brushEnabled;
                  return line.box.length >= 3 ? (
                    <polygon
                      key={index}
                      points={line.box.map(([x, y]) => `${x},${y}`).join(" ")}
                      className={`pointer-events-auto cursor-pointer focus-visible:stroke-brand focus-visible:stroke-2 ${
                        replaced
                          ? "fill-danger stroke-danger"
                          : "fill-transparent stroke-brand-blue-light"
                      }`}
                      fillOpacity={replaced ? 0.15 : undefined}
                      strokeWidth="1"
                      vectorEffect="non-scaling-stroke"
                      role="button"
                      tabIndex={canSelect ? 0 : -1}
                      aria-disabled={!canSelect}
                      aria-label={t(
                        reference ? "image.editRecognizedReplacement" : "image.replaceRecognizedLine",
                        { reference: reference?.reference ?? line.text },
                      )}
                      onPointerDown={(event) => event.stopPropagation()}
                      onClick={() => {
                        if (canSelect) onSelectLine(index);
                      }}
                      onKeyDown={(event) => {
                        if (canSelect && (event.key === "Enter" || event.key === " ")) {
                          event.preventDefault();
                          onSelectLine(index);
                        }
                      }}
                    />
                  ) : null;
                })}
              </svg>
            ) : null}
            <canvas
              ref={editor.canvasRef}
              className={`absolute inset-0 h-full w-full ${
                editor.brushEnabled && !disabled
                  ? "cursor-crosshair touch-none"
                  : "pointer-events-none"
              }`}
              aria-label={t("image.brushMask")}
              onPointerDown={editor.startBrush}
              onPointerMove={editor.moveBrush}
              onPointerUp={editor.stopBrush}
              onPointerCancel={editor.stopBrush}
            />
          </div>
        </div>
        <BrushControls editor={editor} disabled={disabled} t={t} />
        {result ? (
          <p className="text-xs text-fg-dim">
            {t("image.imageMeta", {
              width: result.width,
              height: result.height,
              lines: result.lines.length,
              filename: result.filename,
            })}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
