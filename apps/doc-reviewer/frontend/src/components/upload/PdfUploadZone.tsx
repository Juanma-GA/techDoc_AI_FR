import { useCallback, useEffect, useRef } from "react";
import { useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { useTranslation } from "react-i18next";
import { useDemoMode } from "@internal/ui";

import { loadDemoPdf } from "../../lib/demoPdf";

type SharedProps = {
  disabled?: boolean;
  autoOpen?: boolean;
  allowBatch?: boolean;
  pdfOnly?: boolean;
  dropTitle?: string;
  dropHint?: string;
  dropLimit?: string;
  inputLabel?: string;
  rejectedMessage?: string;
  // Import en cours : affiche un retour visuel immediat (spinner + texte). La
  // requete d'upload est SYNCHRONE cote serveur (conversion Word->PDF, portail
  // qualite) et peut prendre quelques secondes — sans ce retour, la dropzone
  // parait figee.
  uploading?: boolean;
};

type SingleFileProps = {
  multiple?: false;
  onFile: (file: File) => void;
  onFiles?: never;
};

type MultipleFilesProps = {
  multiple: true;
  onFiles: (files: File[]) => void;
  onFile?: never;
};

type Props = SharedProps & (SingleFileProps | MultipleFilesProps);

export function PdfUploadZone(props: Props) {
  const {
    disabled,
    uploading,
    autoOpen = false,
    allowBatch = true,
    pdfOnly = false,
    dropTitle,
    dropHint,
    dropLimit,
    inputLabel,
    rejectedMessage,
  } = props;
  const multiple = props.multiple === true;
  const onFile = props.multiple ? undefined : props.onFile;
  const onFiles = props.multiple ? props.onFiles : undefined;
  const { t } = useTranslation();
  const autoOpenHandled = useRef(false);
  const { mode, isReady } = useDemoMode();
  const [demoPdfLoading, setDemoPdfLoading] = useState(false);
  const [demoPdfError, setDemoPdfError] = useState<string | null>(null);
  const [dropError, setDropError] = useState<string | null>(null);
  const isBusy = uploading || demoPdfLoading;
  const title = dropTitle ?? t("documents.upload.dropTitle");
  const hint = dropHint ?? t("documents.upload.dropHint");
  const limit = dropLimit ?? t("documents.upload.dropLimit");

  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      if (rejected.length > 0 && rejectedMessage) setDropError(rejectedMessage);
      else if (accepted.length > 0) setDropError(null);
      if (accepted.length === 0) return;

      setDemoPdfError(null);
      if (multiple) onFiles?.(accepted);
      else if (accepted[0]) onFile?.(accepted[0]);
    },
    [multiple, onFile, onFiles, rejectedMessage],
  );

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    // Formats supportes : PDF natif + Word (.doc/.docx, convertis en PDF fidele
    // au serveur) + archives .zip (etendues cote batch).
    accept: pdfOnly
      ? { "application/pdf": [".pdf"] }
      : {
          "application/pdf": [".pdf"],
          "application/msword": [".doc"],
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
          ...(allowBatch ? { "application/zip": [".zip"] } : {}),
        },
    multiple,
    disabled: disabled || isBusy,
  });

  useEffect(() => {
    if (multiple || !onFile || !autoOpen || autoOpenHandled.current || disabled || isBusy || !isReady) return;
    const uploadFile = onFile;
    autoOpenHandled.current = true;
    if (mode !== "demo") {
      open();
      return;
    }

    setDemoPdfError(null);
    setDemoPdfLoading(true);
    void loadDemoPdf()
      .then(uploadFile)
      .catch((error: unknown) => {
        setDemoPdfError(error instanceof Error ? error.message : String(error));
      })
      .finally(() => setDemoPdfLoading(false));
  }, [autoOpen, disabled, isBusy, isReady, mode, multiple, onFile, open]);

  return (
    <div
      {...getRootProps()}
      className={["dropzone", isDragActive ? "over" : "", disabled || isBusy ? "disabled" : ""]
        .filter(Boolean)
        .join(" ")}
      aria-busy={isBusy || undefined}
    >
      <input {...getInputProps()} aria-label={inputLabel ?? hint} />
      {demoPdfLoading ? (
        <p
          style={{ fontWeight: 600, color: "var(--fg)", margin: 0, display: "flex", alignItems: "center", gap: 8, justifyContent: "center" }}
          role="status"
        >
          <span className="spinner" style={{ width: 14, height: 14 }} />
          {t("demo.pdfLoading")}
        </p>
      ) : uploading ? (
        <p
          style={{ fontWeight: 600, color: "var(--fg)", margin: 0, display: "flex", alignItems: "center", gap: 8, justifyContent: "center" }}
        >
          <span className="spinner" style={{ width: 14, height: 14 }} />
          {t("documents.upload.uploading")}
        </p>
      ) : (
        <div className="flex flex-col items-center gap-2">
          <p style={{ fontWeight: 600, color: "var(--fg)", margin: 0 }}>
            {title}
          </p>
          <p style={{ margin: 0 }}>{hint}</p>
          <p className="label">{limit}</p>
        </div>
      )}
      {dropError ? <p className="error" role="alert">{dropError}</p> : null}
      {demoPdfError ? (
        <p className="error" role="alert">
          {t("demo.pdfLoadError", { message: demoPdfError })}
        </p>
      ) : null}
    </div>
  );
}
