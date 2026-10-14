import {
  type ChangeEvent,
  type DragEvent,
  useRef,
  useState,
} from "react";
import { FileUp } from "lucide-react";

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
  label = "Déposez votre PDF ici",
  description = "ou parcourez les fichiers de votre ordinateur",
}: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const acceptFiles = (list: FileList | File[]) => {
    const selected = Array.from(list);
    if (selected.length === 0) {
      return;
    }
    if (!multiple && selected.length > 1) {
      onError("Sélectionnez un seul fichier PDF pour cette opération.");
      return;
    }
    for (const file of selected) {
      const error = validatePDFFile(file);
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
      <span className="dropzone-label">{label}</span>
      <span className="dropzone-description">{description}</span>
      <span className="dropzone-limit">PDF · 250 Mo maximum par fichier</span>
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept="application/pdf,.pdf"
        multiple={multiple}
        disabled={disabled}
        onChange={handleChange}
        tabIndex={-1}
      />
    </div>
  );
}
