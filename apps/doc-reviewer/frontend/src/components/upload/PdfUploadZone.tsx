import { useCallback, useEffect, useRef } from "react";
import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { useTranslation } from "react-i18next";
import { useDemoMode } from "@internal/ui";

import { loadDemoPdf } from "../../lib/demoPdf";

type Props = {
  onFile: (file: File) => void;
  disabled?: boolean;
  autoOpen?: boolean;
  allowBatch?: boolean;
  // Import en cours : affiche un retour visuel immediat (spinner + texte). La
  // requete d'upload est SYNCHRONE cote serveur (conversion Word->PDF, portail
  // qualite) et peut prendre quelques secondes — sans ce retour, la dropzone
  // parait figee.
  uploading?: boolean;
};

export function PdfUploadZone({
  onFile,
  disabled,
  uploading,
  autoOpen = false,
  allowBatch = true,
}: Props) {
  const { t } = useTranslation();
  const autoOpenHandled = useRef(false);
  const { mode, isReady } = useDemoMode();
  const [demoPdfLoading, setDemoPdfLoading] = useState(false);
  const [demoPdfError, setDemoPdfError] = useState<string | null>(null);
  const isBusy = uploading || demoPdfLoading;

  const onDrop = useCallback(
    (accepted: File[]) => {
      const file = accepted[0];
      if (file) {
        setDemoPdfError(null);
        onFile(file);
      }
    },
    [onFile],
  );

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    // Formats supportes : PDF natif + Word (.doc/.docx, convertis en PDF fidele
    // au serveur) + archives .zip (etendues cote batch).
    accept: {
      "application/pdf": [".pdf"],
      "application/msword": [".doc"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      ...(allowBatch ? { "application/zip": [".zip"] } : {}),
    },
    multiple: false,
    disabled: disabled || isBusy,
  });

  useEffect(() => {
    if (!autoOpen || autoOpenHandled.current || disabled || isBusy || !isReady) return;
    autoOpenHandled.current = true;
    if (mode !== "demo") {
      open();
      return;
    }

    setDemoPdfError(null);
    setDemoPdfLoading(true);
    void loadDemoPdf()
      .then(onFile)
      .catch((error: unknown) => {
        setDemoPdfError(error instanceof Error ? error.message : String(error));
      })
      .finally(() => setDemoPdfLoading(false));
  }, [autoOpen, disabled, isBusy, isReady, mode, onFile, open]);

  return (
    <div
      {...getRootProps()}
      className={["dropzone", isDragActive ? "over" : "", disabled || isBusy ? "disabled" : ""]
        .filter(Boolean)
        .join(" ")}
      aria-busy={isBusy || undefined}
    >
      <input {...getInputProps()} aria-label={t("documents.upload.dropHint")} />
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
        <>
          <p style={{ fontWeight: 600, color: "var(--fg)", margin: 0 }}>
            {t("documents.upload.dropTitle")}
          </p>
          <p style={{ margin: 0 }}>{t("documents.upload.dropHint")}</p>
          <p className="label">{t("documents.upload.dropLimit")}</p>
        </>
      )}
      {demoPdfError ? (
        <p className="error" role="alert">
          {t("demo.pdfLoadError", { message: demoPdfError })}
        </p>
      ) : null}
    </div>
  );
}
