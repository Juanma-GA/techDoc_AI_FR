import { useRef, useState } from "react";

type Props = {
  accept: string;
  multiple?: boolean;
  disabled?: boolean;
  title: string;
  hint: string;
  onFiles: (files: File[]) => void;
};

// Dropzone identique au preview (.dropzone) : click + drag & drop, input cache.
export function PreviewDropzone({
  accept,
  multiple = false,
  disabled,
  title,
  hint,
  onFiles,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);

  return (
    <div
      className={`dropzone${drag ? " dragover" : ""}`}
      onClick={() => {
        if (!disabled) inputRef.current?.click();
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        if (!disabled && e.dataTransfer.files.length) {
          onFiles(Array.from(e.dataTransfer.files));
        }
      }}
    >
      <strong>{title}</strong>
      <span>{hint}</span>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        style={{ display: "none" }}
        onChange={(e) => {
          const files = e.target.files;
          if (files && files.length) onFiles(Array.from(files));
          e.currentTarget.value = "";
        }}
      />
    </div>
  );
}
