import { ArrowRight, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

type Props = {
  pageCount: number;
  running: boolean;
  onStart: (scope: {
    modifiedOnly: boolean;
    firstPage?: number;
    lastPage?: number;
  }) => void;
  blocked?: boolean;
  blockReason?: string;
};

export function AnalysisPageRange({ pageCount, running, onStart, blocked = false, blockReason }: Props) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<"modified" | "all" | "range">("modified");
  const [firstPage, setFirstPage] = useState(1);
  const [lastPage, setLastPage] = useState(Math.max(pageCount, 1));

  useEffect(() => {
    setFirstPage(1);
    setLastPage(Math.max(pageCount, 1));
  }, [pageCount]);

  const rangeValid =
    pageCount > 0 &&
    firstPage >= 1 &&
    firstPage <= lastPage &&
    lastPage <= pageCount;

  return (
    <span className="row analysis-page-range">
      <select
        className="input analysis-page-range-select"
        value={mode}
        onChange={(event) => setMode(event.target.value as "modified" | "all" | "range")}
        aria-label={t("reviewer.pageScope.label")}
      >
        <option value="modified">{t("reviewer.pageScope.modified")}</option>
        <option value="all">{t("reviewer.pageScope.all")}</option>
        <option value="range">{t("reviewer.pageScope.range")}</option>
      </select>

      {mode === "range" ? (
        <span className="row analysis-page-range-fields">
          <input
            className="input analysis-page-range-input"
            type="number"
            min={1}
            max={Math.max(pageCount, 1)}
            value={firstPage}
            onChange={(event) => setFirstPage(Number(event.target.value))}
            aria-label={t("reviewer.pageScope.first")}
            title={t("reviewer.pageScope.first")}
          />
          <ArrowRight size={14} aria-hidden="true" />
          <input
            className="input analysis-page-range-input"
            type="number"
            min={1}
            max={Math.max(pageCount, 1)}
            value={lastPage}
            onChange={(event) => setLastPage(Number(event.target.value))}
            aria-label={t("reviewer.pageScope.last")}
            title={t("reviewer.pageScope.last")}
          />
        </span>
      ) : null}

      <button
        type="button"
        onClick={() =>
          onStart(
            mode === "range"
              ? { modifiedOnly: false, firstPage, lastPage }
              : { modifiedOnly: mode === "modified" },
          )
        }
        disabled={blocked || running || pageCount < 1 || (mode === "range" && !rangeValid)}
        title={blocked ? blockReason : undefined}
        className="btn secondary small"
      >
        <Play size={14} />
        {running ? t("reviewer.toolbar.analyzing") : t("reviewer.toolbar.analyze")}
      </button>
      {blocked && blockReason ? <span className="hint">{blockReason}</span> : null}
    </span>
  );
}