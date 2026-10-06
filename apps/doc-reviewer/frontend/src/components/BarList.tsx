// Barres horizontales libellées — identique au BarList de corpus-agent (mêmes
// dimensions/couleurs, via styles inline sur tokens pour ne dépendre d'aucune
// classe CSS supplémentaire).
export type BarItem = { label: string; value: number; color?: string };

export function BarList({ items }: { items: BarItem[] }) {
  if (!items.length) return <div className="empty-state">—</div>;
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <div className="bar-list">
      {items.map((it) => (
        <div key={it.label} className="bar-list-row">
          <span className="bar-list-label" title={it.label}>
            {it.label}
          </span>
          <span className="bar-list-track">
            <span
              style={{
                display: "block",
                height: "100%",
                minWidth: 2,
                borderRadius: 4,
                width: `${(it.value / max) * 100}%`,
                background: it.color ?? "var(--brand)",
              }}
            />
          </span>
          <span className="bar-list-value">{it.value}</span>
        </div>
      ))}
    </div>
  );
}
