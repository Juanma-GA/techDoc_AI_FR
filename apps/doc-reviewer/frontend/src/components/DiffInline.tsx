import { useMemo } from "react";

import { inlineDiff } from "../lib/diff";

type Props = { original: string; proposed: string };

export function DiffInline({ original, proposed }: Props) {
  const segments = useMemo(() => inlineDiff(original, proposed), [original, proposed]);

  return (
    <div className="diff-inline">
      {segments.map((seg, i) => {
        if (seg.op === 0) return <span key={i}>{seg.text}</span>;
        if (seg.op === -1) {
          return (
            <span key={i} className="diff-del">
              {seg.text}
            </span>
          );
        }
        return (
          <span key={i} className="diff-ins">
            {seg.text}
          </span>
        );
      })}
    </div>
  );
}
