import { FileText, PenTool, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button, Card } from "@internal/ui";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";
import { SignaturePad } from "./SignaturePad";

type SignatureSourcePanelProps = {
  pdfFile: File | null;
  signatureFile: File | null;
  firstName: string;
  lastName: string;
  dateValue: string;
  language: string;
  disabled: boolean;
  onPdfFiles: (files: File[]) => void;
  onError: (message: string) => void;
  onRemovePdf: () => void;
  onFirstNameChange: (value: string) => void;
  onLastNameChange: (value: string) => void;
  onDateChange: (value: string) => void;
  onSaveSignature: (file: File) => void;
  onClearSignature: () => void;
};

export function SignatureSourcePanel({
  pdfFile,
  signatureFile,
  firstName,
  lastName,
  dateValue,
  language,
  disabled,
  onPdfFiles,
  onError,
  onRemovePdf,
  onFirstNameChange,
  onLastNameChange,
  onDateChange,
  onSaveSignature,
  onClearSignature,
}: SignatureSourcePanelProps) {
  const { t } = useTranslation();

  return (
    <Card className="panel">
      <div className="panel-heading">
        <span className="step-number">01</span>
        <div>
          <h2>{t("signature.stepFile")}</h2>
          <p>{t("signature.stepFileDescription")}</p>
        </div>
      </div>
      <FileDropzone disabled={disabled} onFiles={onPdfFiles} onError={onError} />
      {pdfFile ? (
        <div className="selected-file">
          <span className="file-row-icon">
            <FileText size={17} aria-hidden="true" />
          </span>
          <span className="file-details">
            <span className="file-name">{pdfFile.name}</span>
            <span className="file-size">{formatFileSize(pdfFile.size, language)}</span>
          </span>
          <Button
            type="button"
            variant="ghost"
            className="icon-button remove-button"
            disabled={disabled}
            onClick={onRemovePdf}
            aria-label={t("files.remove")}
          >
            <X size={16} aria-hidden="true" />
          </Button>
        </div>
      ) : null}
      <div className="signature-details-section">
        <div className="panel-heading signature-subheading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("signature.stepDetails")}</h2>
            <p>{t("signature.detailsDescription")}</p>
          </div>
        </div>
        <div className="signature-details-grid">
          <label>
            <span>{t("signature.firstNameLabel")}</span>
            <input
              type="text"
              autoComplete="given-name"
              maxLength={100}
              value={firstName}
              disabled={disabled}
              onChange={(event) => onFirstNameChange(event.currentTarget.value)}
            />
          </label>
          <label>
            <span>{t("signature.lastNameLabel")}</span>
            <input
              type="text"
              autoComplete="family-name"
              maxLength={100}
              value={lastName}
              disabled={disabled}
              onChange={(event) => onLastNameChange(event.currentTarget.value)}
            />
          </label>
          <label>
            <span>{t("signature.dateLabel")}</span>
            <input
              type="date"
              value={dateValue}
              disabled={disabled}
              onChange={(event) => onDateChange(event.currentTarget.value)}
            />
          </label>
        </div>
      </div>
      <div className="signature-draw-section">
        <div className="panel-heading signature-subheading">
          <span className="step-number">03</span>
          <div>
            <h2>{t("signature.stepDraw")}</h2>
            <p>{t("signature.stepDrawDescription")}</p>
          </div>
        </div>
        <SignaturePad
          disabled={disabled || !pdfFile}
          onSave={onSaveSignature}
          onClear={onClearSignature}
        />
        {signatureFile ? (
          <p className="feedback feedback-success" role="status">
            <PenTool size={15} aria-hidden="true" />
            {t("signature.ready")}
          </p>
        ) : null}
      </div>
      <p className="privacy-hint">{t("signature.privacy")}</p>
    </Card>
  );
}
