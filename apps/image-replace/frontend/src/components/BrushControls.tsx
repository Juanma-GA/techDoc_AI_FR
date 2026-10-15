import type { TFunction } from "i18next";
import { Sparkles, Trash2 } from "lucide-react";
import { Badge, Button, Input, Select } from "@internal/ui";

import type { useImageEditor } from "../hooks/useImageEditor";
import { MAX_BRUSH_SIZE, MIN_BRUSH_SIZE } from "../hooks/useImageBrush";

type BrushControlsProps = {
  editor: ReturnType<typeof useImageEditor>;
  disabled: boolean;
  t: TFunction;
};

export function BrushControls({ editor, disabled, t }: BrushControlsProps) {
  return (
    <section aria-labelledby="manual-edit-title" className="space-y-3 rounded-md border border-md p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Sparkles size={16} className="text-brand" aria-hidden="true" />
        <h3 id="manual-edit-title" className="text-sm font-medium text-fg">
          {t("image.manualEditLabel")}
        </h3>
        {editor.manualEditedImage ? <Badge variant="success">{t("image.manualResult")}</Badge> : null}
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-end">
        <Button
          variant={editor.brushEnabled ? "primary" : "secondary"}
          aria-pressed={editor.brushEnabled}
          disabled={disabled}
          onClick={() => editor.setBrushEnabled((enabled) => !enabled)}
        >
          {editor.brushEnabled ? t("image.brushDisable") : t("image.brushEnable")}
        </Button>
        <label className="space-y-1">
          <span className="flex justify-between text-xs text-fg-dim">
            <span>{t("image.brushSize")}</span>
            <span className="font-mono">{editor.brushSize} px</span>
          </span>
          <Input
            type="range"
            min={MIN_BRUSH_SIZE}
            max={MAX_BRUSH_SIZE}
            step={2}
            value={editor.brushSize}
            disabled={disabled}
            className="accent-brand-blue"
            onChange={(event) => editor.setBrushSize(Number(event.target.value))}
          />
        </label>
      </div>
      <label className="block space-y-1">
        <span className="text-xs text-fg-dim">{t("image.eraseMode")}</span>
        <Select
          value={editor.eraseMode}
          disabled={disabled}
          options={[
            { value: "lama", label: t("image.lamaMode") },
            { value: "color", label: t("image.colorMode") },
          ]}
          onChange={(event) => editor.setEraseMode(event.target.value === "color" ? "color" : "lama")}
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          disabled={!editor.hasBrushMask || editor.inpainting}
          onClick={editor.clearBrushMask}
        >
          <Trash2 size={15} aria-hidden="true" />
          {t("image.clearMask")}
        </Button>
        <Button
          disabled={!editor.hasBrushMask || editor.inpainting}
          onClick={() => void editor.applyBrush()}
        >
          {editor.inpainting
            ? t(editor.eraseMode === "lama" ? "image.lamaRunning" : "image.colorRunning")
            : t(editor.eraseMode === "lama" ? "image.applyLama" : "image.applyColor")}
        </Button>
      </div>
      <p className="text-xs leading-relaxed text-fg-dim">
        {t(editor.eraseMode === "lama" ? "image.lamaHint" : "image.colorHint")}
      </p>
      {editor.inpaintError ? (
        <p role="alert" className="rounded-sm border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
          {editor.inpaintError}
        </p>
      ) : null}
    </section>
  );
}
