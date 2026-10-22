import { useEffect, useState, type FormEvent } from "react";
import { FileText, PenTool } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button, Card, Spinner } from "@internal/ui";
import { formatOperationError, processPDF } from "../../shared/api";
import { PdfSignaturePreview } from "./PdfSignaturePreview";
import { SignatureSourcePanel } from "./SignatureSourcePanel";
import { defaultSignaturePlacement, type SignaturePlacement } from "./placement";
import "./signature.css";

export function SignatureTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [signatureFile, setSignatureFile] = useState<File | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [placement, setPlacement] = useState<SignaturePlacement>(defaultSignaturePlacement);
  const [previewReady, setPreviewReady] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    setPageNumber(1);
    setPageCount(0);
    setPreviewReady(false);
    setPlacement(defaultSignaturePlacement);
  }, [pdfFile]);

  const saveSignature = (file: File) => {
    setSignatureFile(file);
    setPlacement(defaultSignaturePlacement);
    setError("");
    setSuccess(false);
  };

  const clearSignature = () => {
    setSignatureFile(null);
    setPlacement(defaultSignaturePlacement);
    setSuccess(false);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!pdfFile) {
      setError(t("signature.selectPdf"));
      return;
    }
    if (!signatureFile) {
      setError(t("signature.drawFirst"));
      return;
    }
    if (!previewReady || pageNumber > pageCount) {
      setError(t("signature.previewFailed"));
      return;
    }

    setWorking(true);
    setError("");
    setSuccess(false);
    const data = new FormData();
    data.append("file", pdfFile, pdfFile.name);
    data.append("signature", signatureFile, signatureFile.name);
    data.append("page", String(pageNumber));
    data.append("x", placement.x.toFixed(6));
    data.append("y", placement.y.toFixed(6));
    data.append("width", placement.width.toFixed(6));
    try {
      await processPDF("signature", data, "signed.pdf", t);
      setSuccess(true);
    } catch (reason) {
      setError(formatOperationError(reason, t, "signature.operationFailed"));
    } finally {
      setWorking(false);
    }
  };

  return (
    <form className="workflow-grid signature-workflow" onSubmit={submit}>
      <SignatureSourcePanel
        pdfFile={pdfFile}
        signatureFile={signatureFile}
        language={language}
        disabled={working}
        onPdfFiles={(incoming) => {
            setPdfFile(incoming[0] ?? null);
            setError("");
            setSuccess(false);
          }}
        onError={setError}
        onRemovePdf={() => {
          setPdfFile(null);
          setError("");
          setSuccess(false);
        }}
        onSaveSignature={saveSignature}
        onClearSignature={clearSignature}
      />

      <Card className="panel signature-placement-panel">
        <div className="panel-heading">
          <span className="step-number">03</span>
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
              disabled={working}
              onChange={(event) => {
                setPageNumber(Number(event.currentTarget.value));
                setPreviewReady(false);
              }}
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
          file={pdfFile}
          signature={signatureFile}
          pageNumber={pageNumber}
          placement={placement}
          disabled={working}
          onPageCount={setPageCount}
          onReady={setPreviewReady}
          onPlacementChange={setPlacement}
        />
        <div className="signature-submit">
          <div className="output-preview">
            <span className="output-icon">
              <FileText size={21} aria-hidden="true" />
            </span>
            <span>
              <strong>signed.pdf</strong>
              <small>{t("signature.outputDescription")}</small>
            </span>
          </div>
          <Button
            type="submit"
            disabled={working || !pdfFile || !signatureFile || !previewReady}
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
    </form>
  );
}
