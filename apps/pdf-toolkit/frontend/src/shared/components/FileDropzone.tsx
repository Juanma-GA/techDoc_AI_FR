import { FileDropzone as SharedFileDropzone } from "@internal/ui";
import { useTranslation } from "react-i18next";

import { validateImageFile, validatePDFFile } from "../files";

type FileType = "pdf" | "image";
type FileDropzoneProps = {
  onFiles: (files: File[]) => void;
  onError: (message: string) => void;
  multiple?: boolean;
  disabled?: boolean;
  fileType?: FileType;
  label?: string;
  description?: string;
};

export function FileDropzone({
  onFiles,
  onError,
  multiple = false,
  disabled = false,
  fileType = "pdf",
  label,
  description,
}: FileDropzoneProps) {
  const { t } = useTranslation();
  const imageFiles = fileType === "image";

  const acceptFiles = (selected: File[]) => {
    if (selected.length === 0) {
      return;
    }
    if (!multiple && selected.length > 1) {
      onError(t(imageFiles ? "files.imageSingleOnly" : "files.singleOnly"));
      return;
    }
    for (const file of selected) {
      const error = imageFiles
        ? validateImageFile(file, {
            tooLarge: (name) => t("files.tooLarge", { name }),
            notImage: (name) => t("files.notImage", { name }),
          })
        : validatePDFFile(file, {
            tooLarge: (name) => t("files.tooLarge", { name }),
            notPdf: (name) => t("files.notPdf", { name }),
          });
      if (error) {
        onError(error);
        return;
      }
    }
    onError("");
    onFiles(selected);
  };

  return (
    <div>
      <SharedFileDropzone
        onFiles={acceptFiles}
        accept={imageFiles ? "image/png,image/jpeg,.png,.jpg,.jpeg" : "application/pdf,.pdf"}
        multiple={multiple}
        disabled={disabled}
        label={label ?? t("files.dropLabel")}
        description={description ?? t("files.dropDescription")}
      />
      <p className="dropzone-limit">{t(imageFiles ? "files.imageLimit" : "files.limit")}</p>
    </div>
  );
}
