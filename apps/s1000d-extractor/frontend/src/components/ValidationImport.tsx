import { useRef, useState } from "react";
import { Alert, Button } from "@internal/ui";
import { FileUp, FolderOpen, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";

import { collectDroppedFiles } from "../lib/validationDrop";

type Props = {
  loadError: string | null;
  onImport: (files: File[]) => void;
  onError: (error: unknown) => void;
};

export function ValidationImport({ loadError, onImport, onError }: Props) {
  const { t } = useTranslation();
  const fileInput = useRef<HTMLInputElement | null>(null);
  const folderInput = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);

  const importDroppedFiles = async (dataTransfer: DataTransfer) => {
    try {
      onImport(await collectDroppedFiles(dataTransfer));
    } catch (error) {
      onError(error);
    }
  };

  return (
    <>
      <section
        data-testid="validation-import"
        className={`s1k-validation-import${dragging ? " s1k-validation-is-dragging" : ""}`}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (event.currentTarget === event.target) setDragging(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          void importDroppedFiles(event.dataTransfer);
        }}
      >
        <input
          ref={fileInput}
          className="s1k-validation-hidden-input"
          type="file"
          accept=".xml,application/xml,text/xml"
          multiple
          onChange={(event) => {
            onImport(Array.from(event.currentTarget.files ?? []));
            event.currentTarget.value = "";
          }}
        />
        <input
          ref={(element) => {
            folderInput.current = element;
            element?.setAttribute("webkitdirectory", "");
          }}
          className="s1k-validation-hidden-input"
          type="file"
          accept=".xml,application/xml,text/xml"
          multiple
          onChange={(event) => {
            onImport(Array.from(event.currentTarget.files ?? []));
            event.currentTarget.value = "";
          }}
        />

        <div className="s1k-validation-drop-copy">
          <FileUp aria-hidden="true" size={22} />
          <div>
            <strong>{t("validation.dropTitle")}</strong>
            <span className="text-label font-mono uppercase text-fg-dim">
              {t("validation.dropHelp")}
            </span>
          </div>
        </div>
        <div className="s1k-validation-import-actions">
          <Button type="button" onClick={() => fileInput.current?.click()}>
            <FileUp aria-hidden="true" size={16} /> {t("validation.selectFiles")}
          </Button>
          <Button type="button" variant="secondary" onClick={() => folderInput.current?.click()}>
            <FolderOpen aria-hidden="true" size={16} /> {t("validation.selectFolder")}
          </Button>
          <Button type="button" variant="secondary" disabled title={t("validation.brexDisabledHelp")}>
            <ShieldCheck aria-hidden="true" size={16} /> {t("validation.brexDisabled")}
          </Button>
        </div>
      </section>
      {loadError ? <Alert variant="danger">{loadError}</Alert> : null}
    </>
  );
}
