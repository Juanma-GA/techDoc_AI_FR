/**
 * OverTimeChart — histogramme empile (1 baton par run d'analyse), segmente par
 * famille d'anomalies. Les 6 familles couvrent les 17 types ANOMALY_TYPES du
 * backend, donc la somme des segments egale le total du run. Port React du
 * `renderOverTimeChart` de la preview HTML. Couleurs depuis les tokens design
 * (var(--color-accent-*) / var(--color-semantic-success)) — aucun hex en dur.
 */
import { useTranslation } from "react-i18next";

import { type KpiOverTimePoint } from "../lib/api";

type Series = { keys: string[]; color: string; labelKey: string };

const SERIES: Series[] = [
  { keys: ["script", "granule"], color: "var(--color-accent-orange)", labelKey: "manager.fam.scriptGranule" },
  { keys: ["texte", "orthographe", "entete"], color: "var(--color-accent-yellow)", labelKey: "manager.fam.texte" },
  {
    keys: ["ordre_taches", "tache_induite", "preliminaire", "securite", "complementaire"],
    color: "var(--color-semantic-success)",
    labelKey: "manager.fam.taches",
  },
  { keys: ["rechange", "outillage", "infrastructure"], color: "var(--color-accent-pink)", labelKey: "manager.fam.logistique" },
  { keys: ["valeur_numerique", "serrage"], color: "var(--color-accent-purple)", labelKey: "manager.fam.valeurs" },
  { keys: ["illustration", "personnalisee"], color: "var(--color-accent-teal)", labelKey: "manager.fam.illustration" },
];

const W = 640;
const H = 220;
const PT = 12;
const PB = 32;
const PL = 40;
const PR = 12;

function famSum(run: KpiOverTimePoint, s: Series): number {
  return s.keys.reduce((acc, key) => acc + Number(run[key] ?? 0), 0);
}

export function OverTimeChart({ runs }: { runs: KpiOverTimePoint[] }) {
  const { t, i18n } = useTranslation();

  if (!runs.length) {
    return <div className="py-6 text-center text-fg-muted">—</div>;
  }

  const labels = SERIES.map((s) => t(s.labelKey));

  let maxY = 1;
  for (const r of runs) {
    const sum = SERIES.reduce((acc, s) => acc + famSum(r, s), 0);
    if (sum > maxY) maxY = sum;
  }

  const n = runs.length;
  const areaW = W - PL - PR;
  const areaH = H - PT - PB;
  const slotW = areaW / n;
  const barW = Math.min(slotW * 0.7, 40);
  const barOffset = (slotW - barW) / 2;
  const y = (v: number) => PT + areaH - (v / maxY) * areaH;

  const fmtDay = (iso: string) => (iso || "").substring(0, 10);
  const fmtTip = (iso: string) => {
    try {
      return new Date(iso).toLocaleString(i18n.language, { dateStyle: "short", timeStyle: "short" });
    } catch {
      return iso;
    }
  };

  // Batons empiles.
  const bars = runs.map((r, i) => {
    const x0 = PL + i * slotW + barOffset;
    let stackBase = 0;
    const segments = SERIES.map((s, si) => {
      const v = famSum(r, s);
      if (v === 0) return null;
      const rectY = y(stackBase + v);
      const rectH = (v / maxY) * areaH;
      stackBase += v;
      return (
        <rect key={si} x={x0} y={rectY} width={barW} height={rectH} fill={s.color}>
          <title>{`${fmtTip(r.started_at)} — ${labels[si]}: ${v}`}</title>
        </rect>
      );
    });
    return (
      <g key={r.run_id || i}>
        {segments}
        {stackBase > 0 && (
          <text
            x={x0 + barW / 2}
            y={y(stackBase) - 4}
            textAnchor="middle"
            fontSize={10}
            fill="var(--color-text-base)"
            className="font-mono"
          >
            {stackBase}
          </text>
        )}
      </g>
    );
  });

  // Axe Y : 3 graduations.
  const ticks = [0, Math.round(maxY / 2), maxY].map((v, i) => (
    <g key={i}>
      <line
        x1={PL}
        x2={W - PR}
        y1={y(v)}
        y2={y(v)}
        stroke="var(--color-border-base)"
        strokeDasharray="2 4"
      />
      <text
        x={PL - 6}
        y={y(v) + 4}
        textAnchor="end"
        fontSize={10}
        fill="var(--color-text-dim)"
        className="font-mono"
      >
        {v}
      </text>
    </g>
  ));

  // Etiquettes X (toutes si n <= 5, sinon debut/milieu/fin).
  const xIdx = n <= 5 ? runs.map((_, i) => i) : [0, Math.floor(n / 2), n - 1];
  const xLabels = xIdx.map((i) => {
    const cx = PL + i * slotW + slotW / 2;
    return (
      <text
        key={i}
        x={cx}
        y={H - PB + 14}
        textAnchor="middle"
        fontSize={10}
        fill="var(--color-text-dim)"
        className="font-mono"
      >
        {fmtDay(runs[i]?.started_at ?? "")}
      </text>
    );
  });

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img">
        {ticks}
        {bars}
        {xLabels}
      </svg>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
        {SERIES.map((s, i) => (
          <span key={i} className="inline-flex items-center gap-1 text-xs text-fg-dim">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ background: s.color }}
            />
            {labels[i]}
          </span>
        ))}
      </div>
    </div>
  );
}
