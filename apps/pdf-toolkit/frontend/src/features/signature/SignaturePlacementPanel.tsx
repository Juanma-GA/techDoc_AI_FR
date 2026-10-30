import { FileText, PenTool } from "lucide-react";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import { Button, Card, Input, Spinner } from "@internal/ui";
import type { ExportProgressState } from "../../shared/api";
import { ExportProgress } from "../shared/ExportProgress";
import { PdfSignaturePreview } from "./PdfSignaturePreview";
import type { SignaturePlacement, TextPlacement } from "./placement";

type SignaturePlacementPanelProps = {
  file: File | null;
  signature: File | null;
  nameText: string;
  dateText: string;
  pageNumber: number;
  pageCount: number;
  placement: SignaturePlacement;
  namePlacement: TextPlacement;
  datePlacement: TextPlacement;
  disabled: boolean;
  working: boolean;
  outputName: string;
  exportProgress: ExportProgressState;
  previewReady: boolean;
  error: string;
  success: boolean;
  onPageCount: (count: number) => void;
  onPageChange: (page: number) => void;
  onReady: (ready: boolean) => void;
  onPlacementChange: (placement: SignaturePlacement) => void;
  onNamePlacementChange: (placement: TextPlacement) => void;
  onDatePlacementChange: (placement: TextPlacement) => void;
  onOutputNameChange: (name: string) => void;
};

export function SignaturePlacementPanel({
  file,
  signature,
  nameText,
  dateText,
  pageNumber,
  pageCount,
  placement,
  namePlacement,
  datePlacement,
  disabled,
  working,
  outputName,
  exportProgress,
  previewReady,
  error,
  success,
  onPageCount,
  onPageChange,
  onReady,
  onPlacementChange,
  onNamePlacementChange,
  onDatePlacementChange,
  onOutputNameChange,
}: SignaturePlacementPanelProps) {
  const { t } = useTranslation();
  const outputNameId = useId();

  return (
    <Card className="panel signature-placement-panel">
      <div className="panel-heading">
        <span className="step-number">04</span>
        <div>
          <h2>{t("signature.stepPlace")}</h2>
          <p>{t("signature.stepPlaceDescription")}</p>
        </div>
      </div>
      {pageCount > 0 ? (
        <label className="signature-page-select">
          <span>{t("signature.pageLabel")}</span>
          <select
            value={pageNumber}
            disabled={disabled}
            onChange={(event) => onPageChange(Number(event.currentTarget.value))}
          >
            {Array.from({ length: pageCount }, (_, index) => index + 1).map((page) => (
              <option key={page} value={page}>
                {t("signature.pageOption", { page })}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <PdfSignaturePreview
        file={file}
        signature={signature}
        nameText={nameText}
        dateText={dateText}
        pageNumber={pageNumber}
        placement={placement}
        namePlacement={namePlacement}
        datePlacement={datePlacement}
        disabled={disabled}
        onPageCount={onPageCount}
        onReady={onReady}
        onPlacementChange={onPlacementChange}
        onNamePlacementChange={onNamePlacementChange}
        onDatePlacementChange={onDatePlacementChange}
      />
      <div className="signature-submit">
        <div className="output-preview">
          <span className="output-icon">
            <FileText size={21} aria-hidden="true" />
          </span>
          <span>
            <label className="field-label" htmlFor={outputNameId}>
              {t("exportOptions.fileName")}
            </label>
            <Input
              id={outputNameId}
              value={outputName}
              disabled={working}
              aria-describedby={`${outputNameId}-help`}
              onChange={(event) => onOutputNameChange(event.currentTarget.value)}
            />
            <small>{t("signature.outputDescription")}</small>
          </span>
        </div>
        <p className="input-help" id={`${outputNameId}-help`}>
          {t("exportOptions.saveLocationHint")}
        </p>
        {working ? <ExportProgress progress={exportProgress} /> : null}
        <Button
          type="submit"
          disabled={working || !file || !signature || !previewReady}
          className="action-button"
        >
          {working ? <Spinner aria-label={t("common.loading")} /> : <PenTool size={18} />}
          {working ? t("signature.working") : t("signature.action")}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("signature.success", { fileName: "signed.pdf" })}
            </p>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
