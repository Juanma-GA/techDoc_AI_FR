import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useTranslation } from "react-i18next";

type Props = {
  onFile: (file: File) => void;
  disabled?: boolean;
};

export function PdfUploadZone({ onFile, disabled }: Props) {
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
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
    disabled,
  });

  return (
    <div
      {...getRootProps()}
      className={["dropzone", isDragActive ? "over" : "", disabled ? "disabled" : ""]
        .filter(Boolean)
        .join(" ")}
    >
      <input {...getInputProps()} aria-label={t("documents.upload.dropHint")} />
      <p style={{ fontWeight: 600, color: "var(--fg)", margin: 0 }}>
        {t("documents.upload.dropTitle")}
      </p>
      <p style={{ margin: 0 }}>{t("documents.upload.dropHint")}</p>
      <p className="label">{t("documents.upload.dropLimit")}</p>
    </div>
  );
}
