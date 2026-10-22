import { FileText, PenTool, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button, Card } from "@internal/ui";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";
import { SignaturePad } from "./SignaturePad";

type SignatureSourcePanelProps = {
  pdfFile: File | null;
  signatureFile: File | null;
  language: string;
  disabled: boolean;
  onPdfFiles: (files: File[]) => void;
  onError: (message: string) => void;
  onRemovePdf: () => void;
  onSaveSignature: (file: File) => void;
  onClearSignature: () => void;
};

export function SignatureSourcePanel({
  pdfFile,
  signatureFile,
  language,
  disabled,
  onPdfFiles,
  onError,
  onRemovePdf,
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
      <div className="signature-draw-section">
        <div className="panel-heading signature-subheading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("signature.stepDraw")}</h2>
            <p>{t("signature.stepDrawDescription")}</p>
          </div>
        </div>
        <SignaturePad disabled={disabled} onSave={onSaveSignature} onClear={onClearSignature} />
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
