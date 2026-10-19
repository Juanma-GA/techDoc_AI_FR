import type { TFunction } from "i18next";
import { Download, FolderOpen, Maximize2, Minus, Plus, Undo2 } from "lucide-react";
import { Button } from "@internal/ui";

import type { OcrResultDto } from "../lib/api";
import type { useImageEditor } from "../hooks/useImageEditor";

type ImageToolbarProps = {
  editor: ReturnType<typeof useImageEditor>;
  result: OcrResultDto | null;
  canUndo: boolean;
  onUndo: () => void;
  onDownload: () => void;
  onDownloadAs: () => void;
  downloading: boolean;
  savingAs: boolean;
  disabled: boolean;
  t: TFunction;
};

export function ImageToolbar({
  editor, result, canUndo, onUndo, onDownload, onDownloadAs, downloading, savingAs, disabled, t,
}: ImageToolbarProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-xs text-fg-dim">
        {editor.manualEditedImage
          ? t("image.editedStatus")
          : result
            ? t("image.resultStatus")
            : t("image.wheelZoom")}
      </p>
      <div className="flex flex-wrap items-center gap-1">
        <Button variant="secondary" size="sm" disabled={disabled || !canUndo} onClick={onUndo}>
          <Undo2 size={15} aria-hidden="true" />
          {t("image.undo")}
        </Button>
        <Button
          variant="secondary"
          size="icon"
          aria-label={t("image.zoomOut")}
          disabled={editor.zoom <= 1}
          onClick={() => editor.setZoomLevel(editor.zoom - 0.25)}
        >
          <Minus size={15} aria-hidden="true" />
        </Button>
        <span className="min-w-12 text-center font-mono text-xs text-fg-dim" aria-live="polite">
          {Math.round(editor.zoom * 100)}%
        </span>
        <Button
          variant="secondary"
          size="icon"
          aria-label={t("image.zoomIn")}
          disabled={editor.zoom >= 4}
          onClick={() => editor.setZoomLevel(editor.zoom + 0.25)}
        >
          <Plus size={15} aria-hidden="true" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("image.resetZoom")}
          disabled={editor.zoom === 1}
          onClick={() => editor.setZoomLevel(1)}
        >
          <Maximize2 size={15} aria-hidden="true" />
        </Button>
        {result || editor.manualEditedImage ? (
          <Button
            variant="secondary" size="sm" disabled={disabled || downloading}
            onClick={onDownload} aria-busy={downloading && !savingAs}
          >
            <Download size={15} aria-hidden="true" />
            {t(downloading && !savingAs ? "image.downloading" : "image.save")}
          </Button>
          <Button
            variant="secondary" size="sm" disabled={disabled || downloading}
            onClick={onDownloadAs} aria-busy={savingAs}
          >
            <FolderOpen size={15} aria-hidden="true" />
            {t(savingAs ? "image.savingAs" : "image.saveAs")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
