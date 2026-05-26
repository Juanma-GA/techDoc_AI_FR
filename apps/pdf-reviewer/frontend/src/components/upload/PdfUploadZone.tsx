import { UploadCloud } from "lucide-react";
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
      className={[
        "flex h-44 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-bg-2 text-center transition-colors",
        isDragActive ? "border-bright bg-card-hover" : "border-md hover:bg-card-hover",
        disabled ? "cursor-not-allowed opacity-50" : "",
      ].join(" ")}
    >
      <input {...getInputProps()} aria-label={t("documents.upload.dropHint")} />
      <UploadCloud size={28} className="text-fg-dim" aria-hidden="true" />
      <p className="text-sm text-fg-dim">{t("documents.upload.dropHint")}</p>
    </div>
  );
}
