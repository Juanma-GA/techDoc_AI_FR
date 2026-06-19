import { Download, Play, Ruler, ZoomIn, ZoomOut } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useFiltersStore } from "../../stores/filtersStore";

type Props = {
  filename: string;
  version: number;
  zoom: number;
  page: number;
  totalPages: number;
  analyzeStatus: "idle" | "running" | "done" | "error";
  onZoomIn: () => void;
  onZoomOut: () => void;
  onPrev: () => void;
  onNext: () => void;
  onAnalyze: () => void;
  onExport: () => void;
};

export function ReviewerToolbar({
  filename,
  version,
  zoom,
  page,
  totalPages,
  analyzeStatus,
  onZoomIn,
  onZoomOut,
  onPrev,
  onNext,
  onAnalyze,
  onExport,
}: Props) {
  const { t } = useTranslation();
  const showUnits = useFiltersStore((s) => s.showUnitConversions);
  const setShowUnits = useFiltersStore((s) => s.setShowUnitConversions);

  return (
    <div className="reviewer-toolbar">
      <div className="reviewer-toolbar-group">
        <span className="label">{filename}</span>
        <span className="badge default">v{version}</span>
      </div>

      <div className="reviewer-toolbar-group">
        <button
          type="button"
          onClick={onZoomOut}
          aria-label={t("reviewer.toolbar.zoomOut")}
          className="btn ghost small"
        >
          <ZoomOut size={16} />
        </button>
        <span className="label">{Math.round(zoom * 100)}%</span>
        <button
          type="button"
          onClick={onZoomIn}
          aria-label={t("reviewer.toolbar.zoomIn")}
          className="btn ghost small"
        >
          <ZoomIn size={16} />
        </button>

        <button
          type="button"
          onClick={onPrev}
          disabled={page <= 1}
          className="btn ghost small"
        >
          ◀
        </button>
        <span className="label">
          {page}/{totalPages || "?"}
        </span>
        <button
          type="button"
          onClick={onNext}
          disabled={page >= totalPages}
          className="btn ghost small"
        >
          ▶
        </button>
      </div>

      <div className="reviewer-toolbar-group">
        <button
          type="button"
          aria-pressed={showUnits}
          onClick={() => setShowUnits(!showUnits)}
          className={["btn small", showUnits ? "secondary" : "ghost"].join(" ")}
        >
          <Ruler size={14} />
          {t("reviewer.toolbar.toggleUnits")}
        </button>
        <button
          type="button"
          onClick={onAnalyze}
          disabled={analyzeStatus === "running"}
          className="btn primary small"
        >
          <Play size={14} />
          {analyzeStatus === "running"
            ? t("reviewer.toolbar.analyzing")
            : t("reviewer.toolbar.analyze")}
        </button>
        <button type="button" onClick={onExport} className="btn secondary small">
          <Download size={14} />
          {t("reviewer.toolbar.export")}
        </button>
      </div>
    </div>
  );
}
