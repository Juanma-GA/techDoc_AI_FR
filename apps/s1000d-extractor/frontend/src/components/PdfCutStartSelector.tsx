import { useTranslation } from "react-i18next";

import { pdfCutApi, type PdfCutDetection } from "../lib/api";

type PdfCutStartSelectorProps = {
  docId: string;
  detection: PdfCutDetection;
  selectedTitle: string;
  startPage: number | null;
  endPage: number | null;
  busy: boolean;
  onTitleChange: (title: string) => void;
  onDetect: (title: string) => void;
  onStartPageChange: (page: number | null) => void;
  onEndPageChange: (page: number | null) => void;
  onConfirm: () => void;
};

export function PdfCutStartSelector({
  docId,
  detection,
  selectedTitle,
  startPage,
  endPage,
  busy,
  onTitleChange,
  onDetect,
  onStartPageChange,
  onEndPageChange,
  onConfirm,
}: PdfCutStartSelectorProps) {
  const { t } = useTranslation();

  return (
    <div className="card">
      <h2 className="card-title">{t("migration.upload.pdfCut.title")}</h2>
      <p className="label">{t("migration.upload.pdfCut.help")}</p>
      {detection.dmrl_titles.length ? (
        <div className="row" style={{ alignItems: "end", marginBottom: 12 }}>
          <label className="grow">
            <div className="label">{t("migration.upload.pdfCut.firstDmTitle")}</div>
            <select
              className="input"
              value={selectedTitle}
              disabled={busy}
              onChange={(event) => onTitleChange(event.target.value)}
            >
              {detection.dmrl_titles.map((title, index) => (
                <option key={`${index}-${title}`} value={title}>
                  {title}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="btn secondary"
            disabled={busy || !selectedTitle}
            onClick={() => onDetect(selectedTitle)}
          >
            {busy
              ? t("migration.upload.pdfCut.searching")
              : t("migration.upload.pdfCut.detectWithTitle")}
          </button>
        </div>
      ) : null}
      <div className="row" style={{ alignItems: "end" }}>
        <label>
          <div className="label">{t("migration.upload.pdfCut.startPage")}</div>
          <input
            className="input"
            type="number"
            min={1}
            max={detection.total_pages}
            value={startPage ?? ""}
            disabled={busy}
            onChange={(event) => onStartPageChange(Number(event.target.value) || null)}
          />
        </label>
        <label>
          <div className="label">{t("migration.upload.pdfCut.endPage")}</div>
          <input
            className="input"
            type="number"
            min={1}
            max={detection.total_pages}
            value={endPage ?? ""}
            disabled={busy}
            onChange={(event) => onEndPageChange(Number(event.target.value) || null)}
          />
        </label>
        <button
          type="button"
          className="btn primary"
          disabled={
            busy ||
            startPage == null ||
            endPage == null ||
            startPage > endPage
          }
          onClick={onConfirm}
        >
          {t("migration.upload.pdfCut.validate")}
        </button>
      </div>
      {startPage != null ? (
        <img
          src={pdfCutApi.previewUrl(docId, startPage)}
          alt={t("migration.upload.pdfCut.previewAlt", { page: startPage })}
          style={{
            display: "block",
            maxWidth: "100%",
            maxHeight: 560,
            marginTop: 16,
            objectFit: "contain",
            border: "1px solid var(--border)",
          }}
        />
      ) : null}
    </div>
  );
}
