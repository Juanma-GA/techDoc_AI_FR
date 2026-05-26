import { useMemo } from "react";

import { inlineDiff } from "../lib/diff";

type Props = { original: string; proposed: string };

export function DiffInline({ original, proposed }: Props) {
  const segments = useMemo(() => inlineDiff(original, proposed), [original, proposed]);

  return (
    <div className="rounded-sm border bg-bg-2 px-2 py-1.5 font-mono text-xs leading-relaxed text-fg">
      {segments.map((seg, i) => {
        if (seg.op === 0) return <span key={i}>{seg.text}</span>;
        if (seg.op === -1) {
          return (
            <span
              key={i}
              className="bg-danger/20 px-0.5 text-danger line-through decoration-danger/60"
            >
              {seg.text}
            </span>
          );
        }
        return (
          <span key={i} className="bg-success/20 px-0.5 text-success">
            {seg.text}
          </span>
        );
      })}
    </div>
  );
}
