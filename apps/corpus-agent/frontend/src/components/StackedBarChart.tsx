import { useTranslation } from "react-i18next";

import { CATEGORY_COLORS } from "../lib/families";
import { fmtDate } from "../lib/format";

type Run = {
  run_id: string;
  started_at: string;
  total: number;
  // Repartition des anomalies du run par categorie (Sujet de la checklist).
  categories: Record<string, number>;
};

// Histogramme empile de l'evolution des anomalies par run, empile par
// CATEGORIE (« Sujet » de la checklist). Les categories sont dynamiques : la
// legende et les couleurs sont derivees des donnees.
export function StackedBarChart({ runs }: { runs: Run[] }) {
  const { i18n } = useTranslation();
  const lang = (i18n.language || "fr").slice(0, 2);

  if (!runs.length) return <div className="empty-state">—</div>;

  // Union des categories, triees par volume total decroissant : ordre
  // d'empilement + couleurs stables d'un run a l'autre.
  const totals = new Map<string, number>();
  for (const r of runs) {
    for (const [c, v] of Object.entries(r.categories ?? {})) {
      totals.set(c, (totals.get(c) ?? 0) + (typeof v === "number" ? v : 0));
    }
  }
  const cats = [...totals.entries()].sort((a, b) => b[1] - a[1]).map(([c]) => c);
  const colorOf = (c: string) => CATEGORY_COLORS[Math.max(0, cats.indexOf(c)) % CATEGORY_COLORS.length];

  if (!cats.length) return <div className="empty-state">—</div>;

  const W = 640, H = 220, PT = 12, PB = 32, PL = 40, PR = 12;
  const runSum = (r: Run) =>
    Object.values(r.categories ?? {}).reduce((acc, v) => acc + (typeof v === "number" ? v : 0), 0);

  let maxY = 1;
  for (const r of runs) maxY = Math.max(maxY, runSum(r));

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
            <text x={PL - 6} y={y(v) + 4} textAnchor="end" fontSize="10" fill="var(--fg-dim)" style={{ fontFamily: "var(--font-mono)" }}>
              {v}
            </text>
          </g>
        ))}
        {runs.map((r, i) => {
          const x0 = PL + i * slotW + barOffset;
          let stackBase = 0;
          const segs = cats.map((c) => {
            const v = r.categories?.[c] ?? 0;
            if (!v) return null;
            const rectY = y(stackBase + v);
            const rectH = (v / maxY) * areaH;
            stackBase += v;
            return (
              <rect key={c} x={x0} y={rectY} width={barW} height={rectH} fill={colorOf(c)}>
                <title>{`${fmtDate(String(r.started_at), lang)} — ${c}: ${v}`}</title>
              </rect>
            );
          });
          return (
            <g key={`bar-${i}`}>
              {segs}
              {stackBase > 0 && (
                <text x={x0 + barW / 2} y={y(stackBase) - 4} textAnchor="middle" fontSize="10" fill="var(--fg)" style={{ fontFamily: "var(--font-mono)" }}>
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
            <text key={`x-${i}`} x={cx} y={H - PB + 14} textAnchor="middle" fontSize="10" fill="var(--fg-dim)" style={{ fontFamily: "var(--font-mono)" }}>
              {d}
            </text>
          );
        })}
      </svg>
      <div className="chart-legend">
        {cats.map((c) => (
          <span className="chart-legend-item" key={c}>
            <span className="chart-legend-swatch" style={{ background: colorOf(c) }} />
            {c}
          </span>
        ))}
      </div>
    </>
  );
}
