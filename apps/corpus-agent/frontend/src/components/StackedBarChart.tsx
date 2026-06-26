import { useTranslation } from "react-i18next";

import { OVER_TIME_SERIES } from "../lib/families";
import { fmtDate } from "../lib/format";

type Run = Record<string, number | string>;

// Histogramme empilé de l'évolution des anomalies (port SVG de
// preview.html::renderOverTimeChart). 6 familles, axe Y 3 graduations.
export function StackedBarChart({ runs }: { runs: Run[] }) {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language || "fr").slice(0, 2);

  if (!runs.length) return <div className="empty-state">—</div>;

  const W = 640, H = 220, PT = 12, PB = 32, PL = 40, PR = 12;
  const famSum = (r: Run, keys: string[]) =>
    keys.reduce((acc, k) => acc + (typeof r[k] === "number" ? (r[k] as number) : 0), 0);

  let maxY = 1;
  for (const r of runs) {
    const sum = OVER_TIME_SERIES.reduce((acc, s) => acc + famSum(r, s.keys), 0);
    if (sum > maxY) maxY = sum;
  }

  const n = runs.length;
  const areaW = W - PL - PR;
  const areaH = H - PT - PB;
  const slotW = areaW / n;
  const barW = Math.min(slotW * 0.7, 40);
  const barOffset = (slotW - barW) / 2;
  const y = (v: number) => PT + areaH - (v / maxY) * areaH;

  const ticks = [0, Math.round(maxY / 2), maxY];
  const xIdx = n <= 5 ? runs.map((_, i) => i) : [0, Math.floor(n / 2), n - 1];

  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg">
        {ticks.map((v) => (
          <g key={`tick-${v}`}>
            <line x1={PL} x2={W - PR} y1={y(v)} y2={y(v)} stroke="var(--border)" strokeDasharray="2 4" />
            <text x={PL - 6} y={y(v) + 4} textAnchor="end" fontSize="10" fill="var(--fg-dim)" fontFamily="JetBrains Mono">
              {v}
            </text>
          </g>
        ))}
        {runs.map((r, i) => {
          const x0 = PL + i * slotW + barOffset;
          let stackBase = 0;
          const segs = OVER_TIME_SERIES.map((s) => {
            const v = famSum(r, s.keys);
            if (v === 0) return null;
            const rectY = y(stackBase + v);
            const rectH = (v / maxY) * areaH;
            stackBase += v;
            return (
              <rect key={s.labelKey} x={x0} y={rectY} width={barW} height={rectH} fill={s.color}>
                <title>{`${fmtDate(String(r.started_at), lang)} — ${t(s.labelKey)}: ${v}`}</title>
              </rect>
            );
          });
          return (
            <g key={`bar-${i}`}>
              {segs}
              {stackBase > 0 && (
                <text x={x0 + barW / 2} y={y(stackBase) - 4} textAnchor="middle" fontSize="10" fill="var(--fg)" fontFamily="JetBrains Mono">
                  {stackBase}
                </text>
              )}
            </g>
          );
        })}
        {xIdx.map((i) => {
          const d = String(runs[i]?.started_at || "").substring(0, 10);
          const cx = PL + i * slotW + slotW / 2;
          return (
            <text key={`x-${i}`} x={cx} y={H - PB + 14} textAnchor="middle" fontSize="10" fill="var(--fg-dim)" fontFamily="JetBrains Mono">
              {d}
            </text>
          );
        })}
      </svg>
      <div className="chart-legend">
        {OVER_TIME_SERIES.map((s) => (
          <span className="chart-legend-item" key={s.labelKey}>
            <span className="chart-legend-swatch" style={{ background: s.color }} />
            {t(s.labelKey)}
          </span>
        ))}
      </div>
    </>
  );
}
