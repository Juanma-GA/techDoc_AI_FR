import { Button, useDemoMode } from "@internal/ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { loadDemoComparisonPdfs } from "../../lib/demoPdf";
import { PdfUploadZone } from "../upload/PdfUploadZone";

type Props = {
  onCompare: (files: File[], referenceIndex: number) => void;
  isCreating: boolean;
  createError: string | null;
};

export function ComparisonSetupCard({ onCompare, isCreating, createError }: Props) {
  const { t } = useTranslation();
  const { mode, isReady } = useDemoMode();
  const [files, setFiles] = useState<File[]>([]);
  const [referenceIndex, setReferenceIndex] = useState(0);
  const [draftError, setDraftError] = useState("");
  const [demoLoading, setDemoLoading] = useState(false);
  const isBusy = isCreating || demoLoading;

  const loadDemoFiles = async (): Promise<void> => {
    setDemoLoading(true);
    setDraftError("");
    try {
      const demoFiles = await loadDemoComparisonPdfs();
      setFiles(demoFiles);
      setReferenceIndex(0);
    } catch (error: unknown) {
      setDraftError(t("comparison.demoLoadError", {
        message: error instanceof Error ? error.message : String(error),
      }));
    } finally {
      setDemoLoading(false);
    }
  };

  const addFiles = (incoming: File[]) => {
    const pdfs = incoming.filter((file) => file.name.toLowerCase().endsWith(".pdf"));
    const next = [...files, ...pdfs];
    setDraftError(pdfs.length !== incoming.length ? t("comparison.pdfOnly") : "");
    if (next.length > 20) {
      setDraftError(t("comparison.filesHint"));
      return;
    }
    setFiles(next);
  };

  const removeDraftFile = (index: number) => {
    setFiles((current) => current.filter((_file, fileIndex) => fileIndex !== index));
    setReferenceIndex((current) => (current === index ? 0 : current > index ? current - 1 : current));
  };

  return (
    <section className="card" aria-labelledby="comparison-new-title">
      <h2 id="comparison-new-title" className="card-title">{t("comparison.newTitle")}</h2>
      <div className="mt-5 space-y-5">
        <div className="space-y-2">
          <p className="hint">{t("comparison.filesHint")}</p>
          <p className="hint">{t("comparison.textLayerOnly")}</p>
        </div>
        {isReady && mode === "demo" ? (
          <div className="space-y-2">
            <Button
              variant="secondary"
              disabled={isBusy}
              aria-busy={demoLoading || undefined}
              onClick={() => void loadDemoFiles()}
            >
              {demoLoading ? t("comparison.demoLoading") : t("comparison.loadDemo")}
            </Button>
            <p className="hint">{t("comparison.demoHint")}</p>
          </div>
        ) : null}
        <div className="space-y-2">
          <p className="label">{t("comparison.filesLabel")}</p>
          <PdfUploadZone
            multiple
            pdfOnly
            onFiles={addFiles}
            disabled={isBusy}
            dropTitle={t("comparison.dropTitle")}
            dropHint={t("comparison.dropHint")}
            dropLimit={t("comparison.dropLimit")}
            inputLabel={t("comparison.filesLabel")}
            rejectedMessage={t("comparison.pdfOnly")}
          />
        </div>
        {draftError ? <p className="error" role="alert">{draftError}</p> : null}
        {files.length ? (
          <div className="space-y-4">
            <div>
              <p className="label mb-2" aria-live="polite">
                {t("comparison.selectedCount", { count: files.length })}
              </p>
              <ul className="item-list">
                {files.map((file, index) => (
                  <li key={`${file.name}-${index}`} className="item-row">
                    <span className="item-main">{file.name}</span>
                    <button
                      type="button"
                      className="btn ghost small"
                      disabled={isBusy}
                      onClick={() => removeDraftFile(index)}
                    >
                      {t("comparison.removeFile")}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            <div className="space-y-2">
              <label className="label" htmlFor="comparison-reference">
                {t("comparison.referenceLabel")}
              </label>
              <select
                id="comparison-reference"
                className="input"
                value={referenceIndex}
                disabled={isBusy}
                onChange={(event) => setReferenceIndex(Number(event.target.value))}
              >
                {files.map((file, index) => (
                  <option key={`${file.name}-${index}`} value={index}>{file.name}</option>
                ))}
              </select>
            </div>
          </div>
        ) : null}
        <div className="space-y-3 border-t border-md pt-4">
          <p className="hint">{t("comparison.retention")}</p>
          {createError ? <p className="error" role="alert">{createError}</p> : null}
          <button
            type="button"
            className="btn primary"
            disabled={files.length < 2 || isBusy}
            onClick={() => onCompare(files, referenceIndex)}
          >
            {isCreating ? t("comparison.working") : t("comparison.compareButton")}
          </button>
        </div>
      </div>
    </section>
  );
}
