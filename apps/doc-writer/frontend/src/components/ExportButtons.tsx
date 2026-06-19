import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiClientError, sessionsApi, type ExportFormat } from "../lib/api";
import { PptxPreviewModal } from "./PptxPreviewModal";

type Props = {
  sessionId: string;
  hasTemplate: boolean;
  templateFormat?: "pptx" | "docx" | null;
  templateDocId?: string | null;
  filename?: string;
  ready?: boolean;
};

const FORMATS: { value: ExportFormat; labelKey: string }[] = [
  { value: "md", labelKey: "generate.exportMd" },
  { value: "docx", labelKey: "generate.exportDocx" },
  { value: "pdf", labelKey: "generate.exportPdf" },
  { value: "pptx", labelKey: "generate.exportPptx" },
];

export function ExportButtons({
  sessionId,
  templateFormat,
  templateDocId,
  filename,
  ready = true,
}: Props) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showPptxModal, setShowPptxModal] = useState(false);

  const download = async (fmt: ExportFormat) => {
    if (fmt === "pptx") {
      if (templateFormat === "pptx" && templateDocId) setShowPptxModal(true);
      return;
    }
    setBusy(fmt);
    setError(null);
    try {
      await sessionsApi.download(sessionId, fmt, filename);
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : err instanceof Error
            ? err.message
            : String(err),
      );
    } finally {
      setBusy(null);
    }
  };

  // Template Word/PDF attache : .docx ET .pdf remplissent le template (sortie
  // .docx, mise en page conservee). On relabelle ces deux boutons pour le
  // signaler (le backend route format=pdf vers le remplissage -> .docx).
  const isDocTemplate = templateFormat === "docx";
  const labelFor = (f: { value: ExportFormat; labelKey: string }): string => {
    if (isDocTemplate && f.value === "docx") return t("generate.exportDocxTemplate");
    if (isDocTemplate && f.value === "pdf") return t("generate.exportPdfTemplate");
    return t(f.labelKey);
  };

  return (
    <div className="row" style={{ gap: 6 }}>
      {FORMATS.map((f) => {
        const disabled =
          !ready || busy !== null || (f.value === "pptx" && templateFormat !== "pptx");
        const label = labelFor(f);
        return (
          <button
            key={f.value}
            type="button"
            className="btn secondary small"
            disabled={disabled}
            onClick={() => void download(f.value)}
          >
            {busy === f.value ? `${label}…` : label}
          </button>
        );
      })}
      {error ? <div className="error">{error}</div> : null}

      {showPptxModal && templateDocId ? (
        <PptxPreviewModal
          sessionId={sessionId}
          templateDocId={templateDocId}
          defaultFilename={filename}
          onClose={() => setShowPptxModal(false)}
        />
      ) : null}
    </div>
  );
}
