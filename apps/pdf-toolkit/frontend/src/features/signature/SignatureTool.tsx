import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { formatOperationError, processPDF } from "../../shared/api";
import { SignaturePlacementPanel } from "./SignaturePlacementPanel";
import { SignatureSourcePanel } from "./SignatureSourcePanel";
import { formatSignatureDate } from "./formatDate";
import {
  defaultDatePlacement,
  defaultNamePlacement,
  defaultSignaturePlacement,
  type SignaturePlacement,
  type TextPlacement,
} from "./placement";
import "./signature.css";

export function SignatureTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [signatureFile, setSignatureFile] = useState<File | null>(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [dateValue, setDateValue] = useState("");
  const [pageNumber, setPageNumber] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [placement, setPlacement] = useState<SignaturePlacement>(defaultSignaturePlacement);
  const [namePlacement, setNamePlacement] = useState<TextPlacement>(defaultNamePlacement);
  const [datePlacement, setDatePlacement] = useState<TextPlacement>(defaultDatePlacement);
  const [previewReady, setPreviewReady] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);
  const nameText = [firstName.trim(), lastName.trim()].filter(Boolean).join(" ");
  const dateText = formatSignatureDate(dateValue, language);

  useEffect(() => {
    setPageNumber(1);
    setPageCount(0);
    setPreviewReady(false);
    setPlacement(defaultSignaturePlacement);
    setNamePlacement(defaultNamePlacement);
    setDatePlacement(defaultDatePlacement);
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
    if (nameText) {
      data.append("name_text", nameText);
      data.append("name_x", namePlacement.x.toFixed(6));
      data.append("name_y", namePlacement.y.toFixed(6));
    }
    if (dateText) {
      data.append("date_text", dateText);
      data.append("date_x", datePlacement.x.toFixed(6));
      data.append("date_y", datePlacement.y.toFixed(6));
    }
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
        firstName={firstName}
        lastName={lastName}
        dateValue={dateValue}
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
        onFirstNameChange={setFirstName}
        onLastNameChange={setLastName}
        onDateChange={setDateValue}
        onSaveSignature={saveSignature}
        onClearSignature={clearSignature}
      />

      <SignaturePlacementPanel
        file={pdfFile}
        signature={signatureFile}
        nameText={nameText}
        dateText={dateText}
        pageNumber={pageNumber}
        pageCount={pageCount}
        placement={placement}
        namePlacement={namePlacement}
        datePlacement={datePlacement}
        disabled={working}
        working={working}
        previewReady={previewReady}
        error={error}
        success={success}
        onPageCount={setPageCount}
        onPageChange={(page) => {
          setPageNumber(page);
          setPreviewReady(false);
        }}
        onReady={setPreviewReady}
        onPlacementChange={setPlacement}
        onNamePlacementChange={setNamePlacement}
        onDatePlacementChange={setDatePlacement}
      />
    </form>
  );
}
