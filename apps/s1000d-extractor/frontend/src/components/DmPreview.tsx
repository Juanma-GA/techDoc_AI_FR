import type { DmPreview as DmPreviewT, PreviewSnippet } from "../lib/api";
import { useTranslation } from "react-i18next";

import { PageFlag, ReviewFlag, ZoneFlag } from "./zoneFlags";

function Line({ s }: { s: PreviewSnippet }) {
  const suspected = s.zone === "header" || s.zone === "footer" || s.zone === "cover" || s.zone === "toc";
  return (
    <div className={`flex flex-wrap items-baseline gap-1.5${suspected ? " rounded-sm border border-warning/40 bg-warning/10 px-2 py-1" : ""}`}>
      <PageFlag page={s.page} />
      <ZoneFlag zone={s.zone} />
      <ReviewFlag zone={s.zone} />
      <span className="text-fg-dim">{s.text}</span>
    </div>
  );
}

export function DmPreview({ preview }: { preview?: DmPreviewT }) {
  const { t } = useTranslation();
  if (!preview || preview.total === 0) {
    return (
      <div className="ml-6 text-label font-mono uppercase text-fg-dim">
        {t("migration.preview.empty")}
      </div>
    );
  }
  const hidden = preview.total - preview.head.length - preview.tail.length;
  return (
    <div className="ml-6 my-0.5 mb-1.5 space-y-1">
      {preview.head.map((s, i) => (
        <Line key={`h${i}`} s={s} />
      ))}
      {hidden > 0 ? (
        <div className="text-label font-mono uppercase text-fg-dim">
          {t("migration.preview.hidden", { count: hidden })}
        </div>
      ) : null}
      {preview.tail.map((s, i) => (
        <Line key={`t${i}`} s={s} />
      ))}
    </div>
  );
}
