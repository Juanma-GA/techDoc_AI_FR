import {
  type ChangeEvent,
  type DragEvent,
  useRef,
  useState,
} from "react";
import { FileUp } from "lucide-react";
import { useTranslation } from "react-i18next";

import { validatePDFFile } from "../files";

type FileDropzoneProps = {
  onFiles: (files: File[]) => void;
  onError: (message: string) => void;
  multiple?: boolean;
  disabled?: boolean;
  label?: string;
  description?: string;
};

export function FileDropzone({
  onFiles,
  onError,
  multiple = false,
  disabled = false,
  label,
  description,
}: FileDropzoneProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const acceptFiles = (list: FileList | File[]) => {
    const selected = Array.from(list);
    if (selected.length === 0) {
      return;
    }
    if (!multiple && selected.length > 1) {
      onError(t("files.singleOnly"));
      return;
    }
    for (const file of selected) {
      const error = validatePDFFile(file, {
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

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.currentTarget.files) {
      acceptFiles(event.currentTarget.files);
    }
    event.currentTarget.value = "";
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (!disabled) {
      acceptFiles(event.dataTransfer.files);
    }
  };

  return (
    <div
      className={`dropzone${dragging ? " dropzone-active" : ""}${disabled ? " dropzone-disabled" : ""}`}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      onClick={() => {
        if (!disabled) {
          inputRef.current?.click();
        }
      }}
      onKeyDown={(event) => {
        if (!disabled && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) {
          setDragging(true);
        }
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        setDragging(false);
      }}
      onDrop={handleDrop}
    >
      <span className="dropzone-icon">
        <FileUp size={22} aria-hidden="true" />
      </span>
      <span className="dropzone-label">{label ?? t("files.dropLabel")}</span>
      <span className="dropzone-description">{description ?? t("files.dropDescription")}</span>
      <span className="dropzone-limit">{t("files.limit")}</span>
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept="application/pdf,.pdf"
        multiple={multiple}
        disabled={disabled}
        onChange={handleChange}
        tabIndex={-1}
        hidden
        aria-hidden="true"
      />
    </div>
  );
}
