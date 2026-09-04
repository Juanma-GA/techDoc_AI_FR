import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useTranslation } from "react-i18next";

type Props = {
  onFile: (file: File) => void;
  disabled?: boolean;
  // Import en cours : affiche un retour visuel immediat (spinner + texte). La
  // requete d'upload est SYNCHRONE cote serveur (conversion Word->PDF, portail
  // qualite) et peut prendre quelques secondes — sans ce retour, la dropzone
  // parait figee.
  uploading?: boolean;
};

export function PdfUploadZone({ onFile, disabled, uploading }: Props) {
  const { t } = useTranslation();

  const onDrop = useCallback(
    (accepted: File[]) => {
      const file = accepted[0];
      if (file) onFile(file);
    },
    [onFile],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    // Formats supportes : PDF natif + Word (.doc/.docx, convertis en PDF fidele
    // au serveur) + archives .zip (etendues cote batch).
    accept: {
      "application/pdf": [".pdf"],
      "application/msword": [".doc"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "application/zip": [".zip"],
    },
    multiple: false,
    disabled: disabled || uploading,
  });

  return (
    <div
      {...getRootProps()}
      className={["dropzone", isDragActive ? "over" : "", disabled || uploading ? "disabled" : ""]
        .filter(Boolean)
        .join(" ")}
      aria-busy={uploading || undefined}
    >
      <input {...getInputProps()} aria-label={t("documents.upload.dropHint")} />
      {uploading ? (
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
    </div>
  );
}
