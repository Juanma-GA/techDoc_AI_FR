import { useRef, type PointerEvent as ReactPointerEvent } from "react";
import type { TFunction } from "i18next";
import { Image as ImageIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, EmptyState } from "@internal/ui";

import type { OcrResultDto } from "../lib/api";
import { useImageEditor } from "../hooks/useImageEditor";
import { BrushControls } from "./BrushControls";
import { ImageToolbar } from "./ImageToolbar";
import { ReplacementBoxControls } from "./ReplacementBoxControls";
import type { LineBoxOffset } from "../lib/replacement-box-offsets";
import { clampLineBoxOffset } from "../lib/replacement-box-offsets";

const DRAG_THRESHOLD_PX = 2;
const DRAG_SENSITIVITY = 0.25;

type BoxDrag = {
  pointerId: number;
  lineIndex: number;
  startX: number;
  startY: number;
  offsetX: number;
  offsetY: number;
  moved: boolean;
};

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
  onSelectBox: (lineIndex: number) => void;
  selectedLineIndex: number | null;
  reapplyBlocked: boolean;
  onUpdateLineOffsets: (offsets: LineBoxOffset[]) => void;
  onApplyOffsetsToAll: () => void;
  onReapplyReplacements: () => void;
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
  onSelectBox,
  selectedLineIndex,
  reapplyBlocked,
  onUpdateLineOffsets,
  onApplyOffsetsToAll,
  onReapplyReplacements,
  t,
}: ImagePreviewProps) {
  const boxDrag = useRef<BoxDrag | null>(null);
  const suppressNextClick = useRef(false);
  const editor = useImageEditor({
    imageFile, imageUrl, manuallyEdited, onImageEdited, onInpaintingChange, t,
  });
  const replacedLines = new Set((result?.references ?? []).flatMap((item) =>
    item.line_indices.slice(0, item.replacement_count ?? 0),
  ));

  function startBoxDrag(
    event: ReactPointerEvent<SVGPolygonElement>,
    lineIndex: number,
    offsetX: number,
    offsetY: number,
  ) {
    event.stopPropagation();
    if (!result || !replacedLines.has(lineIndex) || disabled || editor.brushEnabled) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    boxDrag.current = {
      pointerId: event.pointerId,
      lineIndex,
      startX: event.clientX,
      startY: event.clientY,
      offsetX,
      offsetY,
      moved: false,
    };
  }

  function moveBoxDrag(event: ReactPointerEvent<SVGPolygonElement>) {
    const drag = boxDrag.current;
    if (!result || !drag || drag.pointerId !== event.pointerId) return;
    const deltaX = event.clientX - drag.startX;
    const deltaY = event.clientY - drag.startY;
    if (!drag.moved && Math.hypot(deltaX, deltaY) < DRAG_THRESHOLD_PX) return;
    const line = result.lines[drag.lineIndex];
    if (!line) return;
    drag.moved = true;
    onSelectBox(drag.lineIndex);

    const svg = event.currentTarget.ownerSVGElement;
    const bounds = svg?.getBoundingClientRect();
    if (!bounds?.width || !bounds.height) return;
    const bounded = clampLineBoxOffset(
      line.original_box ?? line.box,
      Math.round(drag.offsetX + deltaX * result.width / bounds.width * DRAG_SENSITIVITY),
      Math.round(drag.offsetY + deltaY * result.height / bounds.height * DRAG_SENSITIVITY),
      result.width,
      result.height,
    );
    onUpdateLineOffsets([{ lineIndex: drag.lineIndex, ...bounded }]);
  }

  function stopBoxDrag(event: ReactPointerEvent<SVGPolygonElement>) {
    const drag = boxDrag.current;
    if (drag?.pointerId !== event.pointerId) return;
    boxDrag.current = null;
    if (drag.moved && event.type === "pointerup") {
      suppressNextClick.current = true;
      window.setTimeout(() => {
        suppressNextClick.current = false;
      }, 0);
    }
  }

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
                          ? selectedLineIndex === index
                            ? "fill-danger stroke-brand stroke-2"
                            : "fill-danger stroke-danger"
                          : selectedLineIndex === index
                            ? "fill-transparent stroke-brand stroke-2"
                            : "fill-transparent stroke-brand-blue-light"
                      }`}
                      style={replaced ? { touchAction: "none" } : undefined}
                      fillOpacity={replaced ? 0.06 : undefined}
                      strokeOpacity={replaced ? 0.06 : undefined}
                      strokeWidth="1"
                      vectorEffect="non-scaling-stroke"
                      role="button"
                      tabIndex={canSelect ? 0 : -1}
                      aria-disabled={!canSelect}
                      aria-pressed={selectedLineIndex === index}
                      aria-label={t(
                        reference ? "image.editRecognizedReplacement" : "image.replaceRecognizedLine",
                        { reference: reference?.reference ?? line.text },
                      )}
                      onPointerDown={(event) => startBoxDrag(
                        event,
                        index,
                        line.box_offset_x ?? 0,
                        line.box_offset_y ?? 0,
                      )}
                      onPointerMove={moveBoxDrag}
                      onPointerUp={stopBoxDrag}
                      onPointerCancel={stopBoxDrag}
                      onLostPointerCapture={stopBoxDrag}
                      onClick={(event) => {
                        if (suppressNextClick.current) {
                          suppressNextClick.current = false;
                          event.preventDefault();
                          event.stopPropagation();
                          return;
                        }
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
        <ReplacementBoxControls
          result={result}
          selectedLineIndex={selectedLineIndex}
          disabled={disabled}
          reapplyBlocked={reapplyBlocked}
          onUpdateOffsets={onUpdateLineOffsets}
          onApplyToAll={onApplyOffsetsToAll}
          onReapply={onReapplyReplacements}
          t={t}
        />
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
