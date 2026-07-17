import type { MouseEvent } from "react";

import type { FlowDto, ZoneDto } from "../lib/api";

type Props = {
  flow: FlowDto | undefined;
  loading: boolean;
  error: string | null;
  zoneByTarget: Record<string, ZoneDto>;
  emptyHint: string;
  loadingHint: string;
  onPick: (zid: string, e: MouseEvent) => void;
  // Mode 'aperçu de rendu' (export) : quand fourni, une zone affiche le contenu
  // REELLEMENT rempli (mapping[zone.id]) au lieu du texte du template. Absent
  // (ZonesManagerPanel) -> affiche le texte/label du template (inchangé).
  mapping?: Record<string, string>;
  // Zones ignorées côté modale (Set d'ids de zone). Reflète le style 'skipped'
  // en direct, en plus de z.active === false.
  skippedIds?: Set<string>;
};

// Apercu 'flux document' pour les templates Word/PDF : le document dans l'ordre
// de lecture (paragraphes + tableaux), chaque bloc-zone surligne (memes couleurs
// que le SVG PPTX, via les classes zone-regex / zone-llm) et cliquable -> meme
// popover. Pendant lineaire du rendu SVG positionne, reserve au PPTX.
export function DocFlowPreview({
  flow,
  loading,
  error,
  zoneByTarget,
  emptyHint,
  loadingHint,
  onPick,
  mapping,
  skippedIds,
}: Props) {
  if (loading) {
    return <div className="doc-flow doc-flow-msg">{loadingHint}</div>;
  }
  if (error) {
    return <div className="doc-flow doc-flow-msg error">{error}</div>;
  }
  const blocks = flow?.blocks ?? [];
  if (blocks.length === 0) {
    return <div className="doc-flow doc-flow-msg">{emptyHint}</div>;
  }

  // Classe de surlignage d'un bloc/cellule selon la zone associee (par target).
  const zoneClass = (id: string, text: string): string => {
    const z = zoneByTarget[id];
    if (z) {
      const base =
        z.kind === "xxx" || z.kind === "placeholder" ? "zone-regex" : "zone-llm";
      const skipped = z.active === false || (skippedIds?.has(z.id) ?? false);
      return base + (skipped ? " skipped" : "");
    }
    return text.trim() ? "label" : "empty";
  };

  // Texte affiché d'un bloc : contenu rempli (mapping) en mode aperçu de rendu,
  // sinon texte d'origine du template.
  const displayText = (id: string, rawText: string): string => {
    const z = zoneByTarget[id];
    if (z && mapping) return mapping[z.id] ?? "";
    return rawText;
  };

  // Chip de section affiche quand la localisation change (Corps / En-tete / Pied).
  let prevLocation = "";

  return (
    <div className="doc-flow">
      {blocks.map((b) => {
        const locChip =
          b.location && b.location !== prevLocation ? b.location : null;
        prevLocation = b.location || prevLocation;

        if (b.type === "table") {
          return (
            <div key={b.id}>
              {locChip ? <div className="doc-flow-loc">{locChip}</div> : null}
              <table className="doc-flow-table">
                <tbody>
                  {b.rows.map((row, ri) => (
                    <tr key={ri}>
                      {row.map((cell) => {
                        const z = zoneByTarget[cell.id];
                        const cls = zoneClass(cell.id, cell.text);
                        const content = displayText(cell.id, cell.text);
                        const title = z?.label?.trim() ?? "";
                        const showTitle =
                          !!z && !!title && title !== content.trim();
                        return (
                          <td
                            key={cell.id}
                            className={`doc-flow-cell ${cls}`}
                            onClick={z ? (e) => onPick(z.id, e) : undefined}
                            title={title || undefined}
                          >
                            {showTitle ? (
                              <span className="doc-flow-ztitle">{title}</span>
                            ) : null}
                            {content ? (
                              <span className="doc-flow-ztext">{content}</span>
                            ) : z && !title ? (
                              <span className="doc-flow-ztext muted">{emptyHint}</span>
                            ) : null}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        const z = zoneByTarget[b.id];
        const cls = zoneClass(b.id, b.text);
        const content = displayText(b.id, b.text);
        const title = z?.label?.trim() ?? "";
        const showTitle = !!z && !!title && title !== content.trim();
        return (
          <div key={b.id}>
            {locChip ? <div className="doc-flow-loc">{locChip}</div> : null}
            <div
              className={`doc-flow-block ${cls}`}
              onClick={z ? (e) => onPick(z.id, e) : undefined}
              title={title || undefined}
            >
              {showTitle ? (
                <span className="doc-flow-ztitle">{title}</span>
              ) : null}
              {content ? (
                <span className="doc-flow-ztext">{content}</span>
              ) : z && !title ? (
                <span className="doc-flow-ztext muted">{emptyHint}</span>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
