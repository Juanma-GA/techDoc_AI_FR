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
    <div className="flex h-topbar-h items-center justify-between gap-4 border-b bg-bg-2 px-4">
      <div className="flex items-center gap-3 text-sm text-fg-dim">
        <span className="font-mono text-fg">{filename}</span>
        <span className="label">v{version}</span>
      </div>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onZoomOut}
          aria-label={t("reviewer.toolbar.zoomOut")}
          className="rounded-sm p-1.5 text-fg-dim hover:bg-card-hover hover:text-fg"
        >
          <ZoomOut size={16} />
        </button>
        <span className="font-mono text-xs text-fg-dim">{Math.round(zoom * 100)}%</span>
        <button
          type="button"
          onClick={onZoomIn}
          aria-label={t("reviewer.toolbar.zoomIn")}
          className="rounded-sm p-1.5 text-fg-dim hover:bg-card-hover hover:text-fg"
        >
          <ZoomIn size={16} />
        </button>

        <span className="mx-3 h-4 w-px bg-border" />

        <button
          type="button"
          onClick={onPrev}
          disabled={page <= 1}
          className="rounded-sm px-2 text-fg-dim hover:bg-card-hover hover:text-fg disabled:opacity-50"
        >
          ◀
        </button>
        <span className="font-mono text-xs text-fg-dim">
          {page}/{totalPages || "?"}
        </span>
        <button
          type="button"
          onClick={onNext}
          disabled={page >= totalPages}
          className="rounded-sm px-2 text-fg-dim hover:bg-card-hover hover:text-fg disabled:opacity-50"
        >
          ▶
        </button>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-pressed={showUnits}
          onClick={() => setShowUnits(!showUnits)}
          className={[
            "inline-flex items-center gap-1 rounded-sm px-2 py-1 text-xs",
            showUnits
              ? "bg-accent-teal/20 text-accent-teal ring-1 ring-accent-teal/40"
              : "text-fg-dim hover:bg-card-hover hover:text-fg",
          ].join(" ")}
        >
          <Ruler size={14} />
          {t("reviewer.toolbar.toggleUnits")}
        </button>
        <button
          type="button"
          onClick={onAnalyze}
          disabled={analyzeStatus === "running"}
          className="inline-flex items-center gap-1 rounded-sm bg-brand px-3 py-1.5 text-xs text-fg hover:bg-brand-blue-light disabled:opacity-60"
        >
          <Play size={14} />
          {analyzeStatus === "running"
            ? t("reviewer.toolbar.analyzing")
            : t("reviewer.toolbar.analyze")}
        </button>
        <button
          type="button"
          onClick={onExport}
          className="inline-flex items-center gap-1 rounded-sm border px-3 py-1.5 text-xs text-fg-dim hover:bg-card-hover hover:text-fg"
        >
          <Download size={14} />
          {t("reviewer.toolbar.export")}
        </button>
      </div>
    </div>
  );
}
