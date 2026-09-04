import type { DmPreview as DmPreviewT, PreviewSnippet } from "../lib/api";
import { ReviewFlag, ZoneFlag } from "./zoneFlags";

function Line({ s }: { s: PreviewSnippet }) {
  const suspected = s.zone === "header" || s.zone === "footer" || s.zone === "cover" || s.zone === "toc";
  return (
    <div className={`row${suspected ? " suspected-preview" : ""}`} style={{ gap: 6, alignItems: "baseline" }}>
      {s.page != null ? <span className="badge">p.{s.page}</span> : null}
      <ZoneFlag zone={s.zone} />
      <ReviewFlag zone={s.zone} />
      <span className="txt" style={{ color: "var(--fg-dim)" }}>
        {s.text}
      </span>
    </div>
  );
}

// Apercu debut/fin d'un DM : verifie ses frontieres sans generer le XML.
export function DmPreview({ preview }: { preview?: DmPreviewT }) {
  if (!preview || preview.total === 0) {
    return <div className="label" style={{ paddingLeft: 26 }}>(aucun contenu prévisualisable)</div>;
  }
  const hidden = preview.total - preview.head.length - preview.tail.length;
  return (
    <div style={{ paddingLeft: 26, margin: "2px 0 6px" }}>
      {preview.head.map((s, i) => (
        <Line key={`h${i}`} s={s} />
      ))}
      {hidden > 0 ? (
        <div className="label">⋮ {hidden} bloc(s) intermédiaire(s)</div>
      ) : null}
      {preview.tail.map((s, i) => (
        <Line key={`t${i}`} s={s} />
      ))}
    </div>
  );
}
