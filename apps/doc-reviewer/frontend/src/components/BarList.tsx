// Barres horizontales libellées — identique au BarList de corpus-agent (mêmes
// dimensions/couleurs, via styles inline sur tokens pour ne dépendre d'aucune
// classe CSS supplémentaire).
export type BarItem = { label: string; value: number; color?: string };

export function BarList({ items }: { items: BarItem[] }) {
  if (!items.length) return <div className="empty-state">—</div>;
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <div>
      {items.map((it) => (
        <div
          key={it.label}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 6,
            fontSize: "0.85rem",
          }}
        >
          <span
            style={{ width: 120, flexShrink: 0, color: "var(--fg-dim)", textAlign: "right" }}
          >
            {it.label}
          </span>
          <span
            style={{
              display: "block",
              flex: 1,
              background: "var(--bg-3)",
              borderRadius: 4,
              height: 18,
              overflow: "hidden",
            }}
          >
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
          <span
            style={{ width: 36, textAlign: "right", fontFamily: '"JetBrains Mono", monospace' }}
          >
            {it.value}
          </span>
        </div>
      ))}
    </div>
  );
}
