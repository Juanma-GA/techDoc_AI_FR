import { ArrowRight, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

type Props = {
  pageCount: number;
  running: boolean;
  onStart: (range?: { firstPage: number; lastPage: number }) => void;
};

export function AnalysisPageRange({ pageCount, running, onStart }: Props) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<"all" | "range">("all");
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
    <span className="row" style={{ gap: 6, alignItems: "center" }}>
      <select
        className="input"
        value={mode}
        onChange={(event) => setMode(event.target.value as "all" | "range")}
        aria-label={t("reviewer.pageScope.label")}
        style={{ width: 180, minWidth: 180, flexShrink: 0 }}
      >
        <option value="all">{t("reviewer.pageScope.all")}</option>
        <option value="range">{t("reviewer.pageScope.range")}</option>
      </select>

      {mode === "range" ? (
        <span className="row" style={{ gap: 4, alignItems: "center" }}>
          <input
            className="input"
            type="number"
            min={1}
            max={Math.max(pageCount, 1)}
            value={firstPage}
            onChange={(event) => setFirstPage(Number(event.target.value))}
            aria-label={t("reviewer.pageScope.first")}
            title={t("reviewer.pageScope.first")}
            style={{ width: 64 }}
          />
          <ArrowRight size={14} aria-hidden="true" />
          <input
            className="input"
            type="number"
            min={1}
            max={Math.max(pageCount, 1)}
            value={lastPage}
            onChange={(event) => setLastPage(Number(event.target.value))}
            aria-label={t("reviewer.pageScope.last")}
            title={t("reviewer.pageScope.last")}
            style={{ width: 64 }}
          />
        </span>
      ) : null}

      <button
        type="button"
        onClick={() => onStart(mode === "range" ? { firstPage, lastPage } : undefined)}
        disabled={running || pageCount < 1 || (mode === "range" && !rangeValid)}
        className="btn secondary small"
      >
        <Play size={14} />
        {running ? t("reviewer.toolbar.analyzing") : t("reviewer.toolbar.analyze")}
      </button>
    </span>
  );
}