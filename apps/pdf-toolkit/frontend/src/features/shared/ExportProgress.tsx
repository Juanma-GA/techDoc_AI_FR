import { useTranslation } from "react-i18next";

import type { ExportProgressState } from "../../shared/api";

type ExportProgressProps = {
  progress: ExportProgressState;
};

export function ExportProgress({ progress }: ExportProgressProps) {
  const { t } = useTranslation();
  const percentage =
    progress.percentage === null
      ? null
      : Math.max(0, Math.min(100, Math.round(progress.percentage)));
  const label =
    progress.phase === "pages" && progress.total !== undefined
      ? t("exportProgress.pages", {
          completed: progress.completed ?? 0,
          total: progress.total,
        })
      : t(`exportProgress.${progress.phase}`);

  return (
    <div className="export-progress">
      <div className="export-progress-label">
        <span aria-live="polite">{label}</span>
        {percentage !== null ? <span>{percentage}%</span> : null}
      </div>
      <div
        className={`export-progress-track${percentage === null ? " export-progress-indeterminate" : ""}`}
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percentage ?? undefined}
        aria-valuetext={percentage === null ? label : `${percentage}%`}
      >
        {percentage !== null ? (
          <span className="export-progress-fill" style={{ width: `${percentage}%` }} />
        ) : null}
      </div>
    </div>
  );
}
