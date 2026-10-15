import type { TFunction } from "i18next";
import { Cpu, ImagePlus, Trash2 } from "lucide-react";
import { Button, Card, CardContent, CardHeader, CardTitle, FileDropzone } from "@internal/ui";

import type { useImageReplace } from "../hooks/useImageReplace";
import { ExcelMapping } from "./ExcelMapping";
import { ReplacementPairs } from "./ReplacementPairs";

type ImageInputPanelProps = {
  workflow: ReturnType<typeof useImageReplace>;
  disabled: boolean;
  t: TFunction;
};

export function ImageInputPanel({ workflow, disabled, t }: ImageInputPanelProps) {
  const imageDescription = workflow.imageFile
    ? `${(workflow.imageFile.size / 1024 / 1024).toFixed(2)} MB`
    : t("image.imageTypes");
  const excelDescription = workflow.excelFile
    ? `${(workflow.excelFile.size / 1024 / 1024).toFixed(2)} MB`
    : t("image.excelTypes");

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-md bg-brand/10 text-brand">
            <ImagePlus size={18} aria-hidden="true" />
          </span>
          <div>
            <CardTitle className="mb-0">{t("image.inputTitle")}</CardTitle>
            <p className="text-sm text-fg-dim">{t("image.inputDescription")}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <section aria-labelledby="image-input-label" className="space-y-2">
          <h3 id="image-input-label" className="label">{t("image.imageLabel")}</h3>
          <FileDropzone
            onFiles={workflow.chooseImage}
            accept="image/png,image/jpeg,image/webp,image/bmp,image/tiff"
            multiple={false}
            disabled={disabled}
            label={workflow.imageFile?.name ?? t("image.imagePrompt")}
            description={imageDescription}
            className="min-h-32"
          />
        </section>

        <section aria-labelledby="excel-input-label" className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h3 id="excel-input-label" className="label">{t("image.excelLabel")}</h3>
            <span className="font-mono text-xs text-fg-dim">.xlsx / .xlsm</span>
          </div>
          {!workflow.excelFile ? (
            <FileDropzone
              onFiles={workflow.chooseExcel}
              accept=".xlsx,.xlsm"
              multiple={false}
              disabled={disabled}
              label={t("image.excelPrompt")}
              description={excelDescription}
              className="min-h-24"
            />
          ) : (
            <div className="flex items-center gap-2 rounded-md border border-md bg-bg-2 px-3 py-2">
              <Cpu size={16} className="shrink-0 text-fg-dim" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate text-sm text-fg" title={workflow.excelFile.name}>
                {workflow.excelFile.name}
              </span>
              <span className="shrink-0 font-mono text-xs text-fg-dim">{excelDescription}</span>
              <Button
                variant="ghost"
                size="icon"
                disabled={disabled}
                aria-label={t("image.removeExcel")}
                title={t("image.removeExcel")}
                onClick={workflow.removeExcel}
              >
                <Trash2 size={16} aria-hidden="true" />
              </Button>
            </div>
          )}
          <ExcelMapping mapping={workflow} disabled={disabled} t={t} />
        </section>

        <ReplacementPairs
          pairs={workflow.replacementPairs}
          excelPairs={workflow.excelPairs}
          showExcelPairs={workflow.excelSelectionConfigured}
          excelPairsLoading={workflow.excelPairsLoading}
          excelPairsReady={workflow.excelPairsReady}
          disabled={disabled}
          onAdd={workflow.addPair}
          onUpdate={workflow.updatePair}
          onRemove={workflow.removePair}
          onUpdateExcel={workflow.updateExcelPair}
          onRemoveExcel={workflow.removeExcelPair}
          t={t}
        />

        {workflow.error ? (
          <p role="alert" className="rounded-sm border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
            {workflow.error}
          </p>
        ) : null}
        <Button
          type="submit"
          size="lg"
          className="w-full"
          disabled={!workflow.imageFile || disabled || !workflow.excelSelectionReady}
        >
          {workflow.loading ? (
            <span role="status">{t("image.runningOcr")}</span>
          ) : (
            t("image.runOcr")
          )}
        </Button>
        {workflow.loading ? (
          <p className="text-xs text-fg-dim">{t("image.modelDownloadHint")}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
