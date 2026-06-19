// Barres horizontales libellées (port de preview.html::bar) pour la
// répartition par sévérité / par type.
export type BarItem = { label: string; value: number; color?: string };

export function BarList({ items }: { items: BarItem[] }) {
  if (!items.length) return <div className="empty-state">—</div>;
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <div>
      {items.map((it) => (
        <div className="bar-row" key={it.label}>
          <span className="bar-label">{it.label}</span>
          <span className="bar-track">
            <span
              className="bar-fill"
              style={{ width: `${(it.value / max) * 100}%`, background: it.color ?? "var(--brand)" }}
            />
          </span>
          <span className="bar-count">{it.value}</span>
        </div>
      ))}
    </div>
  );
}
