import { UploadCloud } from "lucide-react";
import {
  type DragEvent,
  type ChangeEvent,
  useCallback,
  useRef,
  useState,
} from "react";

import { cn } from "../lib/utils";

export type FileDropzoneProps = {
  onFiles: (files: File[]) => void;
  accept?: string;
  multiple?: boolean;
  disabled?: boolean;
  label?: string;
  description?: string;
  className?: string;
};

/**
 * Zone drag&drop multi-fichiers. États : idle / drag-over / disabled.
 * Cliquer ouvre aussi le file picker (input caché).
 */
export function FileDropzone({
  onFiles,
  accept,
  multiple = true,
  disabled = false,
  label = "Déposez vos fichiers ici",
  description,
  className,
}: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFiles = useCallback(
    (list: FileList | null) => {
      if (!list || list.length === 0) return;
      onFiles(Array.from(list));
    },
    [onFiles],
  );

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (disabled) return;
    handleFiles(e.dataTransfer.files);
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) setIsDragOver(true);
  };

  const onDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
    // reset to allow re-uploading the same file
    e.target.value = "";
  };

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if (!disabled && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      aria-disabled={disabled}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-md bg-card p-6 text-center transition-colors",
        "hover:border-bright hover:bg-card-hover",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue-light",
        isDragOver && "border-bright bg-card-hover",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      <UploadCloud size={28} className="text-fg-dim" aria-hidden="true" />
      <p className="font-medium text-fg">{label}</p>
      {description ? (
        <p className="text-sm text-fg-dim">{description}</p>
      ) : null}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        onChange={onChange}
        className="hidden"
      />
    </div>
  );
}
